"""El grafo a nivel de símbolo: funciones, clases, métodos y quién llama a quién.

Un grafo de llamadas honesto exige distinguir dos cosas que se confunden siempre:

- `procesa(x)` donde `procesa` es una función de este proyecto → **hecho sintáctico**.
  El nombre se resuelve mirando defs e imports, sin inferir tipos de nada.
- `objeto.metodo()` donde `objeto` es una variable cualquiera → **no es un hecho**.
  Saber a qué apunta exige inferencia de tipos, y adivinarlo produce aristas falsas
  con pinta de ciertas, que es peor que no tener la arista.

Así que aquí se resuelve **solo lo resoluble**, y lo demás **se cuenta y se dice**.
Un grafo que enseña el 60% presentándolo como el 100% miente; uno que enseña el 60%
diciendo *"resolví 60 de 100 llamadas, y estas 40 no"* es útil y no engaña. Ésa es la
única diferencia que importa, y es la misma disciplina que el resto del proyecto:
declarar lo que no se ha mirado.

Cero dependencias: `ast` y nada más. No hay LSP, ni índice, ni servidor.
"""

import ast
import builtins
import os
import re

from .graph import _BOM, DEFAULT_SKIP, _iter_py_files, _resolve_base, module_name

#: `len()`, `open()`, `isinstance()`… NO son simbolos de este proyecto, asi que no
#: resolverlas no es un fallo: es lo correcto. Meterlas en el denominador hundia la
#: cobertura y hacia parecer inutil una tecnica que no lo es — el primer numero que
#: dio este modulo fue 17%, y era una mezcla de peras con manzanas.
_BUILTINS = frozenset(dir(builtins))

#: Motivos por los que una llamada no se resuelve. Se cuentan por separado porque
#: dicen cosas distintas: mucho `atributo-de-variable` es codigo orientado a objetos
#: (limite real de esta tecnica), mucho `nombre-desconocido` suele ser codigo que
#: llama a librerias (normal y sano).
NO_RESUELTA = ("atributo-de-variable", "nombre-desconocido", "expresion-dinamica")


def _def_nodes(body):
    return [n for n in body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]


def _base_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        izquierda = _base_name(node.value)
        return (izquierda + "." + node.attr) if izquierda else node.attr
    return None


def _imports(tree, mod, is_pkg):
    """Nombre local -> destino punteado. Solo sintaxis: qué nombre trajo cada import."""
    tabla = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name.split(".")[0]
                tabla[local] = alias.name
        elif isinstance(node, ast.ImportFrom):
            base = _resolve_base(node, mod, is_pkg)
            if base is None:
                continue
            for alias in node.names:
                local = alias.asname or alias.name
                tabla[local] = (base + "." + alias.name) if base else alias.name
    return tabla


def _resumen(node):
    """La PRIMERA línea del docstring, o "".

    La prosa que explica un símbolo ya está escrita y vive pegada a él. No hace
    falta generarla: hace falta recogerla. Y esta envejece de otra manera —
    cuando deja de ser cierta, el diff que la contradice pasa por delante de
    alguien, cosa que no le ocurre a un documento aparte (el 60% de la
    documentación caduca en seis meses justamente porque nada la obliga).

    Solo la primera línea: es la que resume, y el resto es el porqué, que no cabe
    en una ficha.
    """
    try:
        texto = ast.get_docstring(node) or ""
    except (TypeError, ValueError):
        return ""
    for linea in texto.splitlines():
        linea = linea.strip()
        if linea:
            return linea
    return ""


def _scan_module(mod, tree, is_pkg):
    """Los símbolos que este módulo DEFINE. Todo hecho: está escrito en el fichero."""
    info = {
        "module": mod,
        "functions": {},   # nombre -> cualificado
        "classes": {},     # nombre -> {"qual":..., "bases": [...], "methods": {n: qual}}
        "imports": _imports(tree, mod, is_pkg),
        "tree": tree,
        "docs": {mod: _resumen(tree)},   # cualificado -> primera linea del docstring
        "lines": {mod: 1},               # cualificado -> linea donde se define
    }
    for node in _def_nodes(tree.body):
        qual = "%s.%s" % (mod, node.name)
        info["functions"][node.name] = qual
        info["docs"][qual] = _resumen(node)
        info["lines"][qual] = node.lineno
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        qual = "%s.%s" % (mod, node.name)
        metodos = {m.name: "%s.%s" % (qual, m.name) for m in _def_nodes(node.body)}
        info["docs"][qual] = _resumen(node)
        info["lines"][qual] = node.lineno
        for m in _def_nodes(node.body):
            info["docs"]["%s.%s" % (qual, m.name)] = _resumen(m)
            info["lines"]["%s.%s" % (qual, m.name)] = m.lineno
        info["classes"][node.name] = {
            "qual": qual,
            "bases": [b for b in (_base_name(x) for x in node.bases) if b],
            "methods": metodos,
        }
    return info


def _resolver_nombre(nombre, modulo, tabla_global):
    """Un nombre suelto a símbolo del proyecto, o None. Defs locales antes que imports."""
    if nombre in modulo["functions"]:
        return modulo["functions"][nombre]
    if nombre in modulo["classes"]:
        return modulo["classes"][nombre]["qual"]
    destino = modulo["imports"].get(nombre)
    if destino and destino in tabla_global:
        return destino
    return None


def _resolver_llamada(node, modulo, clase, tabla_global, modulos):
    """(símbolo destino, motivo). Solo lo demostrable; lo demás, motivo de por qué no."""
    func = node.func

    if isinstance(func, ast.Name):
        destino = _resolver_nombre(func.id, modulo, tabla_global)
        if destino:
            return destino, None
        return None, ("builtin" if func.id in _BUILTINS else "nombre-desconocido")

    if isinstance(func, ast.Attribute):
        base = func.value
        # `self.metodo()` dentro de una clase: el metodo esta escrito ahi al lado.
        if isinstance(base, ast.Name) and base.id in ("self", "cls") and clase is not None:
            qual = clase["methods"].get(func.attr)
            return (qual, None) if qual else (None, "atributo-de-variable")
        if isinstance(base, ast.Name):
            # `modulo.funcion()` donde `modulo` vino de un import: resoluble.
            destino_mod = modulo["imports"].get(base.id)
            if destino_mod and destino_mod in modulos:
                candidato = "%s.%s" % (destino_mod, func.attr)
                if candidato in tabla_global:
                    return candidato, None
            # `Clase.metodo()` con la clase definida o importada aqui.
            duenio = _resolver_nombre(base.id, modulo, tabla_global)
            if duenio:
                candidato = "%s.%s" % (duenio, func.attr)
                if candidato in tabla_global:
                    return candidato, None
        return None, "atributo-de-variable"

    return None, "expresion-dinamica"


def _llamadas_en(cuerpo, origen, modulo, clase, tabla_global, modulos, aristas, motivos):
    for node in ast.walk(cuerpo):
        if not isinstance(node, ast.Call):
            continue
        destino, motivo = _resolver_llamada(node, modulo, clase, tabla_global, modulos)
        if destino and destino != origen:
            aristas.add((origen, destino, "CALLS"))
        elif motivo:
            motivos[motivo] = motivos.get(motivo, 0) + 1


def analyze(root, skip=DEFAULT_SKIP, include_nested=False, since=None):
    """El grafo de símbolos del proyecto, con su cobertura de resolución declarada."""
    report = {
        "root": root,
        "root_error": None,
        "nodes": [],
        "edges": [],
        "calls_total": 0,
        "calls_resolved": 0,
        "unresolved": {},
        "errors": {},
        "not_covered": [],
    }
    if not os.path.isdir(root):
        report["root_error"] = "la raiz no existe o no es un directorio: %s" % root
        return report

    modulos = {}
    for path in _iter_py_files(root, skip, include_nested):
        mod = module_name(path, root)
        if not mod:
            continue
        try:
            # utf-8-sig, no utf-8: con BOM el fichero caia en `errors` y sus
            # simbolos desaparecian del grafo (mismo bug que en graph).
            with open(path, "r", encoding="utf-8-sig", errors="replace") as handle:
                tree = ast.parse(handle.read(), filename=path)
        except (SyntaxError, ValueError, RecursionError, MemoryError) as error:
            report["errors"][path] = "%s: %s" % (type(error).__name__, error)
            continue
        modulos[mod] = _scan_module(mod, tree, os.path.basename(path) == "__init__.py")
        # La ruta RELATIVA a la raiz analizada: lo que un lector (o un agente)
        # puede abrir tal cual desde donde se lanzo el comando.
        modulos[mod]["path"] = os.path.relpath(path, root)

    # Tabla global de simbolos: modulos, clases, funciones y metodos.
    tabla = {}
    for mod, info in modulos.items():
        docs = info.get("docs") or {}
        lineas = info.get("lines") or {}
        ruta = info.get("path", "")
        tabla[mod] = {"kind": "module", "module": mod, "doc": docs.get(mod, ""),
                      "file": ruta, "line": 1}
        for nombre, qual in info["functions"].items():
            tabla[qual] = {
                "kind": "function", "module": mod, "name": nombre, "doc": docs.get(qual, ""),
                "file": ruta, "line": lineas.get(qual),
            }
        for nombre, clase in info["classes"].items():
            tabla[clase["qual"]] = {
                "kind": "class", "module": mod, "name": nombre,
                "doc": docs.get(clase["qual"], ""),
                "file": ruta, "line": lineas.get(clase["qual"]),
            }
            for mname, mqual in clase["methods"].items():
                tabla[mqual] = {"kind": "method", "module": mod, "name": mname,
                                "owner": clase["qual"], "doc": docs.get(mqual, ""),
                                "file": ruta, "line": lineas.get(mqual)}

    aristas = set()
    motivos = {}
    for mod, info in modulos.items():
        for qual in info["functions"].values():
            aristas.add((mod, qual, "DEFINES"))
        for clase in info["classes"].values():
            aristas.add((mod, clase["qual"], "DEFINES"))
            for mqual in clase["methods"].values():
                aristas.add((mqual, clase["qual"], "MEMBER_OF"))
            for base in clase["bases"]:
                destino = _resolver_nombre(base.split(".")[0], info, tabla)
                if destino and destino in tabla:
                    aristas.add((clase["qual"], destino, "EXTENDS"))

        # Llamadas dentro de funciones sueltas y dentro de metodos.
        for node in _def_nodes(info["tree"].body):
            _llamadas_en(node, info["functions"][node.name], info, None, tabla, modulos,
                         aristas, motivos)
        for nombre, origen_clase in info["classes"].items():
            for m in _def_nodes(
                next(c for c in info["tree"].body
                     if isinstance(c, ast.ClassDef) and c.name == nombre).body
            ):
                _llamadas_en(m, origen_clase["methods"][m.name], info, origen_clase,
                             tabla, modulos, aristas, motivos)

    resueltas = len([a for a in aristas if a[2] == "CALLS"])
    builtins_vistos = motivos.pop("builtin", 0)
    sin_resolver = sum(motivos.values())
    report["nodes"] = [dict(qual=q, **d) for q, d in sorted(tabla.items())]
    report["edges"] = sorted([list(a) for a in aristas])
    report["calls_resolved"] = resueltas
    report["calls_builtin"] = builtins_vistos
    report["calls_total"] = resueltas + sin_resolver + builtins_vistos
    #: El denominador honesto: todo menos las llamadas a builtins, que nunca podian
    #: ser una arista de este proyecto.
    report["calls_candidates"] = resueltas + sin_resolver
    report["unresolved"] = dict(sorted(motivos.items()))

    # Lo que esta tecnica NO puede ver, dicho siempre y sin adornos.
    report["not_covered"].append(
        "llamadas sobre variables (`obj.metodo()`): exigen inferencia de tipos. Se "
        "cuentan, no se adivinan — una arista inventada es peor que una arista ausente"
    )
    report["not_covered"].append(
        "funciones anidadas y definidas dentro de funciones: fuera de este barrido"
    )
    report["not_covered"].append(
        "despacho dinamico (`getattr`, registros, decoradores que reenvian): invisible al AST"
    )

    # La pelicula: comparar contra el grafo tal como estaba en `since` (git, no
    # cache). Comparacion por NOMBRE: un renombrado sale como nuevo+desaparecido.
    report["since"] = since
    report["baseline_ok"] = None
    report["new_nodes"] = []
    report["new_calls"] = []
    report["gone_nodes"] = 0
    if since is not None:
        base = baseline(root, since)
        if base is None:
            report["baseline_ok"] = False
            report["not_covered"].append(
                "el delta vs '%s': no pude leer la baseline de git" % since
            )
        else:
            base_nodes, base_calls = base
            ahora = {n["qual"] for n in report["nodes"]}
            calls_ahora = {(a, b) for a, b, t in report["edges"] if t == "CALLS"}
            report["baseline_ok"] = True
            report["new_nodes"] = sorted(ahora - base_nodes)
            report["new_calls"] = sorted([a, b] for a, b in calls_ahora - base_calls)
            report["gone_nodes"] = len(base_nodes - ahora)
    return report


def calls(report, simbolo, depth=1):
    """Quién llama a un símbolo y a quién llama él, con fichero:línea.

    Devuelve material, no veredictos: un nombre ambiguo no es un error, son
    varias coincidencias, y se devuelven todas con sus relaciones. `depth`
    extiende llamantes hacia arriba y llamados hacia abajo siguiendo CALLS —
    el radio de la onda de un cambio. Solo aristas resueltas: lo que el grafo
    no ve (atributos de variable, despacho dinámico) ya lo declara el informe.
    """
    nodos = {n["qual"]: n for n in report["nodes"]}
    entrantes, salientes = _indice_llamadas(report)
    exacto = simbolo in nodos
    objetivos = [simbolo] if exacto else sorted(
        q for q in nodos if q.endswith("." + simbolo)
    )
    matches = []
    for qual in objetivos:
        matches.append({
            "symbol": _ficha(nodos[qual]),
            "callers": _onda(qual, entrantes, nodos, depth),
            "callees": _onda(qual, salientes, nodos, depth),
        })
    return {"query": simbolo, "depth": depth, "matches": matches}


def relacionados(report, texto, limite=8):
    """Los símbolos del proyecto cuyo nombre aparece en un texto de búsqueda.

    Para el hook de PreToolUse: `texto` es un patrón de Grep/Glob, no Python,
    así que se tokeniza a palabras y se casa contra el nombre pelado de cada
    símbolo. Sin coincidencias, lista vacía — y el hook calla: una línea fija
    de "0 resultados" en cada búsqueda es ruido repetido (H6). Cada ficha lleva
    sus cuentas de llamantes/llamados para que el lector decida si le importa
    sin abrir nada.
    """
    palabras = {
        p.lower() for p in re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", texto or "")
    }
    if not palabras:
        return []
    entrantes, salientes = _indice_llamadas(report)
    fichas = []
    for nodo in report["nodes"]:
        nombre = (nodo.get("name") or nodo["qual"].rsplit(".", 1)[-1]).lower()
        if nombre not in palabras:
            continue
        ficha = _ficha(nodo)
        ficha["callers"] = len(entrantes.get(nodo["qual"], ()))
        ficha["callees"] = len(salientes.get(nodo["qual"], ()))
        fichas.append(ficha)
    # Los mas conectados primero: si hay que cortar, que caiga lo periferico.
    fichas.sort(key=lambda f: (-(f["callers"] + f["callees"]), f["qual"]))
    return fichas[:limite]


def _indice_llamadas(report):
    """Las aristas CALLS del informe como dos diccionarios: entrantes y salientes."""
    entrantes = {}
    salientes = {}
    for a, b, tipo in report["edges"]:
        if tipo == "CALLS":
            salientes.setdefault(a, set()).add(b)
            entrantes.setdefault(b, set()).add(a)
    return entrantes, salientes


def _ficha(nodo):
    return {
        "qual": nodo["qual"], "kind": nodo["kind"],
        "file": nodo.get("file", ""), "line": nodo.get("line"),
        "doc": nodo.get("doc", ""),
    }


def _onda(qual, aristas, nodos, depth):
    """BFS sobre CALLS hasta `depth` niveles, sin repetir y sin volver al origen."""
    vistos = {qual}
    frente = [qual]
    resultado = []
    for nivel in range(1, max(depth, 1) + 1):
        siguiente = []
        for actual in frente:
            for vecino in sorted(aristas.get(actual, ())):
                if vecino in vistos:
                    continue
                vistos.add(vecino)
                ficha = _ficha(nodos[vecino]) if vecino in nodos else {"qual": vecino}
                ficha["depth"] = nivel
                resultado.append(ficha)
                siguiente.append(vecino)
        frente = siguiente
    return resultado


def _scan_items(items):
    """El nucleo de analyze() sobre (modulo, ruta, fuente, es_pkg) ya leidos."""
    modulos = {}
    errores = {}
    for mod, ruta, texto, es_pkg in items:
        if texto is None:
            errores[ruta] = "no se pudo leer"
            continue
        try:
            # Mismo motivo que en graph._graph_from_sources: el BOM no es sintaxis
            # para el interprete, pero si para ast.parse sobre texto decodificado.
            tree = ast.parse(texto.lstrip(_BOM), filename=ruta)
        except (SyntaxError, ValueError, RecursionError, MemoryError) as error:
            errores[ruta] = "%s: %s" % (type(error).__name__, error)
            continue
        modulos[mod] = _scan_module(mod, tree, es_pkg)
    return modulos, errores


def baseline(root, ref):
    """El conjunto de aristas CALLS tal como estaba en `ref`, leido de git.

    Sin indice y sin cache, a proposito: una cache puede mentir (el indice de
    GitNexus quedo 6 commits desfasado el mismo dia que se midio contra el), y
    git ya guarda cada version. Devuelve (nodes, calls) o None si no hay repo/ref.
    """
    from .graph import _git, module_name

    repo = _git(root, "rev-parse", "--show-toplevel")
    if repo is None:
        return None
    repo = repo.strip()
    listing = _git(repo, "ls-tree", "-r", "--name-only", ref)
    if listing is None:
        return None
    items = []
    for gitpath in listing.splitlines():
        gitpath = gitpath.strip()
        if not gitpath.endswith(".py"):
            continue
        abspath = os.path.join(repo, *gitpath.split("/"))
        try:
            if os.path.relpath(abspath, root).startswith(".."):
                continue
        except ValueError:
            continue
        mod = module_name(abspath, root)
        if not mod:
            continue
        texto = _git(repo, "show", "%s:%s" % (ref, gitpath))
        items.append((mod, gitpath, texto, gitpath.endswith("__init__.py")))
    modulos, _err = _scan_items(items)
    tabla = set()
    for mod, info in modulos.items():
        tabla.add(mod)
        tabla.update(info["functions"].values())
        for clase in info["classes"].values():
            tabla.add(clase["qual"])
            tabla.update(clase["methods"].values())
    # Reusar el resolutor real: mismas reglas, cero divergencia con analyze().
    tabla_dict = {q: {} for q in tabla}
    aristas = set()
    motivos = {}
    for info in modulos.values():
        for node in _def_nodes(info["tree"].body):
            _llamadas_en(node, info["functions"][node.name], info, None, tabla_dict,
                         modulos, aristas, motivos)
        for nombre, clase in info["classes"].items():
            cuerpo = next(c for c in info["tree"].body
                          if isinstance(c, ast.ClassDef) and c.name == nombre)
            for m in _def_nodes(cuerpo.body):
                _llamadas_en(m, clase["methods"][m.name], info, clase, tabla_dict,
                             modulos, aristas, motivos)
    calls = {(a, b) for a, b, _t in aristas}
    return tabla, calls


def coverage(report):
    """Qué proporción de las llamadas CANDIDATAS se pudo demostrar.

    Candidatas = todas menos las de builtins, que nunca podían ser una arista de
    este proyecto. Sigue siendo imperfecto —el denominador conserva los métodos de
    objetos de la stdlib (`handle.read()`), que tampoco lo son— así que este número
    es un **suelo**, no la cifra exacta. Se dice así en vez de venderlo mejor.
    """
    total = report.get("calls_candidates") or 0
    return (report.get("calls_resolved", 0) / total) if total else 0.0
