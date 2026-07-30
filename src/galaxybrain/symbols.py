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

#: `len()`, `open()`, `isinstance()`… NO son simbolos de este proyecto, asi que no
#: resolverlas no es un fallo: es lo correcto. Meterlas en el denominador hundia la
#: cobertura y hacia parecer inutil una tecnica que no lo es — el primer numero que
#: dio este modulo fue 17%, y era una mezcla de peras con manzanas.
_BUILTINS = frozenset(dir(builtins))

from .graph import DEFAULT_SKIP, _iter_py_files, _resolve_base, module_name

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


def _scan_module(mod, tree, is_pkg):
    """Los símbolos que este módulo DEFINE. Todo hecho: está escrito en el fichero."""
    info = {
        "module": mod,
        "functions": {},   # nombre -> cualificado
        "classes": {},     # nombre -> {"qual":..., "bases": [...], "methods": {n: qual}}
        "imports": _imports(tree, mod, is_pkg),
        "tree": tree,
    }
    for node in _def_nodes(tree.body):
        info["functions"][node.name] = "%s.%s" % (mod, node.name)
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        qual = "%s.%s" % (mod, node.name)
        metodos = {m.name: "%s.%s" % (qual, m.name) for m in _def_nodes(node.body)}
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


def analyze(root, skip=DEFAULT_SKIP, include_nested=False):
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
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                tree = ast.parse(handle.read(), filename=path)
        except (SyntaxError, ValueError, RecursionError, MemoryError) as error:
            report["errors"][path] = "%s: %s" % (type(error).__name__, error)
            continue
        modulos[mod] = _scan_module(mod, tree, os.path.basename(path) == "__init__.py")

    # Tabla global de simbolos: modulos, clases, funciones y metodos.
    tabla = {}
    for mod, info in modulos.items():
        tabla[mod] = {"kind": "module", "module": mod}
        for nombre, qual in info["functions"].items():
            tabla[qual] = {"kind": "function", "module": mod, "name": nombre}
        for nombre, clase in info["classes"].items():
            tabla[clase["qual"]] = {"kind": "class", "module": mod, "name": nombre}
            for mname, mqual in clase["methods"].items():
                tabla[mqual] = {"kind": "method", "module": mod, "name": mname,
                                "owner": clase["qual"]}

    aristas = set()
    motivos = {}
    for mod, info in modulos.items():
        for nombre, qual in info["functions"].items():
            aristas.add((mod, qual, "DEFINES"))
        for nombre, clase in info["classes"].items():
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
        for nombre, clase in info["classes"].items():
            origen_clase = info["classes"][nombre]
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
    return report


def coverage(report):
    """Qué proporción de las llamadas CANDIDATAS se pudo demostrar.

    Candidatas = todas menos las de builtins, que nunca podían ser una arista de
    este proyecto. Sigue siendo imperfecto —el denominador conserva los métodos de
    objetos de la stdlib (`handle.read()`), que tampoco lo son— así que este número
    es un **suelo**, no la cifra exacta. Se dice así en vez de venderlo mejor.
    """
    total = report.get("calls_candidates") or 0
    return (report.get("calls_resolved", 0) / total) if total else 0.0
