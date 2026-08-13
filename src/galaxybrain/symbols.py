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


def _nombres_atados(tree):
    """Todo nombre que el fichero ATA en cualquier parte: defs, clases,
    asignaciones, imports, `except ... as`, bucles.

    Es el censo contra el que se comprueba un `from M import y`, y NO puede ser
    la tabla de simbolos: las constantes no son nodos del grafo y acusar a
    `from m import TARIFA` seria el falso positivo recurrente que mata la
    familia. El censo es deliberadamente ANCHO (un `for y in ...` local tambien
    cuenta, aunque no cree atributo de modulo): se prefiere callar un roto real
    a acusar uno falso — regla 9."""
    nombres = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            nombres.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            nombres.add(node.id)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                nombres.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name != "*":
                    nombres.add(alias.asname or alias.name)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            nombres.add(node.name)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            nombres.update(node.names)
    return nombres


def _sin_censo_posible(tree):
    """`from x import *` o un `__getattr__` de modulo (PEP 562): el modulo puede
    servir nombres que ningun censo estatico ve, asi que no hay acusacion."""
    if any(isinstance(n, ast.FunctionDef) and n.name == "__getattr__" for n in tree.body):
        return True
    return any(isinstance(n, ast.ImportFrom) and any(a.name == "*" for a in n.names)
               for n in ast.walk(tree))


def _imports_rotos(root, modulos):
    """`from M import y` donde M es un modulo DEL PROYECTO e `y` no existe en el.

    El hecho que dejaba ciega a la seleccion de tests: una referencia colgante
    no produce arista, la cadena de llamantes no puede subir por ella, y el
    test del consumidor roto no corre — el falso verde que destapo el control
    'firma' del banco de convergencia (13-ago-2026). El caso sin red ninguna es
    el consumidor VIEJO: no viaja en ningun diff, asi que ningun "test tocado"
    lo rescata. Aqui solo se DECLARA el hecho; que hacer con el lo decide la
    seleccion (ADR 0008: el grafo dice hechos).

    Conservador a proposito (regla 9): solo imports directos del cuerpo del
    modulo — uno dentro de `try`/`if` es un patron de fallback y ya maneja la
    ausencia —, solo destinos del proyecto con censo posible, y con el
    filesystem como arbitro para submodulos que el barrido no vio (skip,
    anidados). Fuera de alcance y dicho: `import M.viejo` roto (sin `from`).
    """
    rotos = []
    censo = {}
    for mod, info in sorted(modulos.items()):
        es_pkg = os.path.basename(info.get("path") or "") == "__init__.py"
        for node in info["tree"].body:
            if not isinstance(node, ast.ImportFrom):
                continue
            base = _resolve_base(node, mod, es_pkg)
            if not base or base not in modulos:
                continue
            destino = modulos[base]
            if base not in censo:
                censo[base] = (None if _sin_censo_posible(destino["tree"])
                               else _nombres_atados(destino["tree"]))
            nombres = censo[base]
            if nombres is None:
                continue
            for alias in node.names:
                if alias.name == "*" or alias.name in nombres:
                    continue
                if (base + "." + alias.name) in modulos:
                    continue                      # importa un submodulo
                if os.path.basename(destino.get("path") or "") == "__init__.py":
                    carpeta = os.path.dirname(os.path.join(root, destino["path"]))
                    if (os.path.exists(os.path.join(carpeta, alias.name)) or
                            os.path.exists(os.path.join(carpeta, alias.name + ".py"))):
                        continue                  # submodulo que el barrido no vio
                rotos.append({
                    "file": (info.get("path") or "").replace(os.sep, "/"),
                    "line": node.lineno,
                    "import": "from %s import %s" % (base, alias.name),
                    "falta": base + "." + alias.name,
                })
    return rotos


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


def _texto_default(node):
    """El default de un parámetro como texto corto. Best-effort: si no se puede
    reproducir, un marcador honesto antes que una firma rota."""
    try:
        texto = ast.unparse(node)
    except Exception:  # noqa: BLE001 - unparse puede fallar con nodos raros
        return "…"
    return texto if len(texto) <= 25 else texto[:24] + "…"


def _firma(node):
    """La firma de un def como la teclearía quien va a LLAMARLO.

    El hecho sintáctico que más ficheros obligaba a abrir: el grafo decía que
    `parse_ts` existe y quién la llama, pero no si es `parse_ts(ts)` o
    `parse_ts(ts, default=None)` (prueba de uso, 4-ago: cinco lecturas de
    fichero solo para ver parámetros). Args con defaults, `/`, `*`, async y los
    decoradores que cambian cómo se llama — todo del AST, cero inferencia.
    """
    a = node.args
    partes = []
    pos = list(a.posonlyargs) + list(a.args)
    defaults = [None] * (len(pos) - len(a.defaults)) + list(a.defaults)
    for arg, default in zip(pos, defaults):
        partes.append(arg.arg if default is None else "%s=%s" % (arg.arg, _texto_default(default)))
    if a.posonlyargs:
        partes.insert(len(a.posonlyargs), "/")
    if a.vararg:
        partes.append("*" + a.vararg.arg)
    elif a.kwonlyargs:
        partes.append("*")
    for arg, default in zip(a.kwonlyargs, a.kw_defaults):
        partes.append(arg.arg if default is None else "%s=%s" % (arg.arg, _texto_default(default)))
    if a.kwarg:
        partes.append("**" + a.kwarg.arg)
    firma = "(%s)" % ", ".join(partes)
    if isinstance(node, ast.AsyncFunctionDef):
        firma = "async " + firma
    marcas = [
        d.id for d in node.decorator_list
        if isinstance(d, ast.Name) and d.id in ("property", "classmethod", "staticmethod")
    ]
    if marcas:
        firma = "@" + " @".join(marcas) + " " + firma
    return firma


def es_de_test(qual):
    """Si el símbolo vive en código de test (primer tramo `test*`/`*tests`).

    Se separa en las cuentas porque "56 llamantes" y "5 de src + 51 de tests"
    cuentan historias distintas a quien va a tocar el símbolo: los tests son
    la red, no la onda.
    """
    primero = (qual or "").split(".", 1)[0].lower()
    return primero.startswith("test") or primero.endswith("tests")


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
        "ends": {},                      # cualificado -> ultima linea del cuerpo
        "sigs": {},                      # cualificado -> firma tecleable
    }
    for node in _def_nodes(tree.body):
        qual = "%s.%s" % (mod, node.name)
        info["functions"][node.name] = qual
        info["docs"][qual] = _resumen(node)
        info["lines"][qual] = node.lineno
        info["ends"][qual] = getattr(node, "end_lineno", None)
        info["sigs"][qual] = _firma(node)
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        qual = "%s.%s" % (mod, node.name)
        metodos = {m.name: "%s.%s" % (qual, m.name) for m in _def_nodes(node.body)}
        info["docs"][qual] = _resumen(node)
        info["lines"][qual] = node.lineno
        info["ends"][qual] = getattr(node, "end_lineno", None)
        bases = [b for b in (_base_name(x) for x in node.bases) if b]
        info["sigs"][qual] = "(%s)" % ", ".join(bases) if bases else ""
        for m in _def_nodes(node.body):
            info["docs"]["%s.%s" % (qual, m.name)] = _resumen(m)
            info["lines"]["%s.%s" % (qual, m.name)] = m.lineno
            info["ends"]["%s.%s" % (qual, m.name)] = getattr(m, "end_lineno", None)
            info["sigs"]["%s.%s" % (qual, m.name)] = _firma(m)
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


def _reexportado(mod, atributo, tabla_global, modulos, saltos=4):
    """`otro.nombre()` donde `nombre` no se DEFINE en `otro`, sino que lo importó.

    `changes._git_output` no existe como `def` en `changes`; la línea 31 de ese
    módulo dice `from .graph import _git as _git_output`. Eso no es una
    conjetura sobre lo que el nombre podría valer en tiempo de ejecución: es la
    sentencia de import, y dice exactamente a qué símbolo apunta. Por eso se
    resuelve aquí y no hace falta romper el ADR 0008 — el grafo sigue diciendo
    hechos.

    Lo destapó `bancos/oraculo_aristas.py` el 10-ago-2026: de las 1.518 llamadas
    que la suite ejecuta de verdad, las ÚNICAS tres que el grafo no veía y que no
    tenían ya una puerta río abajo eran las tres de este patrón, todas contra
    `graph._git`. Se re-exporta en cadena a veces (un `__init__` que reexpone lo
    de un submódulo que a su vez reexpone), de ahí los saltos — con tope, porque
    dos módulos que se importan en círculo colgarían el análisis.
    """
    visto = set()
    for _ in range(saltos):
        if mod not in modulos:
            return None
        destino = modulos[mod]["imports"].get(atributo)
        if not destino or destino in visto:
            return None
        if destino in tabla_global:
            return destino
        visto.add(destino)
        # El nombre viaja: `a.b.c` se parte en módulo `a.b` y atributo `c`.
        mod, _, atributo = destino.rpartition(".")
        if not mod:
            return None
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
                reexport = _reexportado(destino_mod, func.attr, tabla_global, modulos)
                if reexport:
                    return reexport, None
            # `Clase.metodo()` con la clase definida o importada aqui.
            duenio = _resolver_nombre(base.id, modulo, tabla_global)
            if duenio:
                candidato = "%s.%s" % (duenio, func.attr)
                if candidato in tabla_global:
                    return candidato, None
        return None, "atributo-de-variable"

    return None, "expresion-dinamica"


def _llamadas_en(cuerpo, origen, modulo, clase, tabla_global, modulos, aristas, motivos,
                 como_valor=None, nombrado_en=None):
    llamados = set()
    for node in ast.walk(cuerpo):
        if not isinstance(node, ast.Call):
            continue
        llamados.add(id(node.func))
        destino, motivo = _resolver_llamada(node, modulo, clase, tabla_global, modulos)
        if destino and destino != origen:
            aristas.add((origen, destino, "CALLS"))
        elif motivo:
            motivos[motivo] = motivos.get(motivo, 0) + 1

    if como_valor is None:
        return
    if nombrado_en is None:
        nombrado_en = {}
    # Un simbolo NOMBRADO sin llamarlo se esta pasando como valor: a un
    # parametro, a un registro, a un decorador. Desde ahi lo invoca alguien a
    # quien el AST no puede seguir — la llamada acaba siendo `f(...)` sobre una
    # variable, y ahi no hay nada que resolver (ADR 0008: no se adivina).
    #
    # No es un caso raro ni ajeno: gb lo hace en su propio nucleo
    # (`(constructor or build_graph)(root, ...)`), y lo hace cualquier codigo con
    # callbacks, estrategias o inyeccion. Lo destapo el oraculo de cobertura el
    # 10-ago-2026 sobre este mismo repo: 118 de 334 simbolos tenian tests que los
    # EJECUTABAN y la seleccion no elegia, y los cinco bancos escritos a mano
    # habian dado 0/7 porque ninguno usaba ese patron.
    for node in ast.walk(cuerpo):
        if isinstance(node, (ast.Name, ast.Attribute)) and id(node) not in llamados:
            if not isinstance(getattr(node, "ctx", None), ast.Load):
                continue
            destino, _ = _resolver_llamada(_ComoFuncion(node), modulo, clase,
                                           tabla_global, modulos)
            # Solo funciones y metodos. En `modulo.funcion()` el AST tambien
            # visita el `modulo` de la izquierda, y en `Clase.metodo()` la clase:
            # ninguno de los dos se esta pasando a ningun sitio, y contarlos
            # ensuciaria el hecho hasta volverlo inservible.
            if destino and tabla_global.get(destino, {}).get("kind") in ("function", "method"):
                como_valor.add(destino)
                # DONDE se nombró, no solo QUE se nombró. La diferencia es todo:
                # `set_defaults(func=cmd_graph)` dice que quien tenga esa tabla
                # delante puede invocar `cmd_graph`, y ese alguien está escrito
                # aquí, en `origen`. Sin este dato la cadena de llamantes se
                # corta en seco y los tests que llegan por ahí se pierden — eran
                # el 93 de 93 de los falsos verdes medidos el 10-ago-2026.
                nombrado_en.setdefault(destino, set()).add(origen)


class _ComoFuncion:
    """Envuelve un nodo para preguntarle a `_resolver_llamada` a quien nombraria
    si fuera el `func` de una llamada. Reutiliza la resolucion entera —imports,
    `self.`, `Clase.metodo`— en vez de escribir una segunda, que divergiria."""

    def __init__(self, nodo):
        self.func = nodo


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
        "imports_rotos": [],
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

    # Los imports internos que apuntan a algo que ya no existe: hecho duro,
    # declarado para quien seleccione. La decision de correr todo vive en
    # `impacted`, no aqui — el grafo dice hechos, no dictamina.
    report["imports_rotos"] = _imports_rotos(root, modulos)

    # Tabla global de simbolos: modulos, clases, funciones y metodos.
    tabla = {}
    for mod, info in modulos.items():
        docs = info.get("docs") or {}
        lineas = info.get("lines") or {}
        finales = info.get("ends") or {}
        firmas = info.get("sigs") or {}
        ruta = info.get("path", "")
        tabla[mod] = {"kind": "module", "module": mod, "doc": docs.get(mod, ""),
                      "file": ruta, "line": 1, "end": None, "sig": ""}
        for nombre, qual in info["functions"].items():
            tabla[qual] = {
                "kind": "function", "module": mod, "name": nombre, "doc": docs.get(qual, ""),
                "file": ruta, "line": lineas.get(qual), "end": finales.get(qual),
                "sig": firmas.get(qual, ""),
            }
        for nombre, clase in info["classes"].items():
            tabla[clase["qual"]] = {
                "kind": "class", "module": mod, "name": nombre,
                "doc": docs.get(clase["qual"], ""),
                "file": ruta, "line": lineas.get(clase["qual"]),
                "end": finales.get(clase["qual"]),
                "sig": firmas.get(clase["qual"], ""),
            }
            for mname, mqual in clase["methods"].items():
                tabla[mqual] = {"kind": "method", "module": mod, "name": mname,
                                "owner": clase["qual"], "doc": docs.get(mqual, ""),
                                "file": ruta, "line": lineas.get(mqual),
                                "end": finales.get(mqual),
                                "sig": firmas.get(mqual, "")}

    aristas = set()
    motivos = {}
    como_valor = set()
    nombrado_en = {}
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
                         aristas, motivos, como_valor, nombrado_en)
        for nombre, origen_clase in info["classes"].items():
            for m in _def_nodes(
                next(c for c in info["tree"].body
                     if isinstance(c, ast.ClassDef) and c.name == nombre).body
            ):
                _llamadas_en(m, origen_clase["methods"][m.name], info, origen_clase,
                             tabla, modulos, aristas, motivos, como_valor, nombrado_en)
        # Fuera de toda funcion: `TABLA = {"x": handler}` a nivel de modulo es
        # exactamente el mismo caso y es donde viven los registros.
        _llamadas_en(info["tree"], "%s.<modulo>" % info["module"], info, None, tabla,
                     modulos, set(), {}, como_valor, nombrado_en)

    resueltas = len([a for a in aristas if a[2] == "CALLS"])
    builtins_vistos = motivos.pop("builtin", 0)
    sin_resolver = sum(motivos.values())
    report["nodes"] = [dict(qual=q, **d) for q, d in sorted(tabla.items())]
    report["edges"] = sorted([list(a) for a in aristas])
    # Simbolos NOMBRADOS sin llamarlos: se pasan como valor, asi que quien los
    # invoca de verdad no deja arista. La seleccion de tests lo trata como
    # opaco y corre todo, igual que con los subprocesos.
    report["usados_como_valor"] = sorted(como_valor)
    # Y dónde se nombró cada uno. Es un hecho sintáctico —el `Name` está escrito
    # en ese cuerpo— y por eso vive en el grafo; lo que se HACE con él (tratar a
    # ese cuerpo como posible invocador) es sobre-aproximar, y eso vive en la
    # selección, igual que `_enlaza_dunders`. El grafo dice hechos.
    report["nombrado_como_valor_en"] = {k: sorted(v) for k, v in sorted(nombrado_en.items())}
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
        quien = entrantes.get(nodo["qual"], ())
        ficha["callers"] = len(quien)
        ficha["callers_tests"] = sum(1 for q in quien if es_de_test(q))
        ficha["callees"] = len(salientes.get(nodo["qual"], ()))
        fichas.append(ficha)
    # Los mas conectados primero: si hay que cortar, que caiga lo periferico.
    fichas.sort(key=lambda f: (-(f["callers"] + f["callees"]), f["qual"]))
    return fichas[:limite]


def en_linea(report, fichero, linea):
    """El símbolo más interno definido en `fichero` cuyo cuerpo CONTIENE `linea`.

    Para anclar un hecho externo con fichero:línea —un crash de la consola, una
    señal de `check`— a su nodo del grafo. Contención por [line, end] del AST,
    no "el def más cercano por arriba": esa heurística atribuiría al def anterior
    el código de nivel de módulo que viene después. Línea fuera de todo def →
    None, que es la verdad: petó en el cuerpo del módulo, no en un símbolo.
    """
    mejor = None
    objetivo = os.path.normcase(fichero or "")
    for nodo in report["nodes"]:
        if nodo["kind"] == "module":
            continue
        if os.path.normcase(nodo.get("file") or "") != objetivo:
            continue
        inicio, fin = nodo.get("line"), nodo.get("end")
        if not inicio or not fin or not (inicio <= linea <= fin):
            continue
        if mejor is None or inicio > mejor["line"]:
            mejor = nodo
    return mejor


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
        "doc": nodo.get("doc", ""), "sig": nodo.get("sig", ""),
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
