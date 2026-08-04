"""Qué tests toca correr por lo que cambió — derivado del grafo, no adivinado.

El grafo ya sabe quién llama a quién. Un diff toca símbolos (`changes._onda_del_diff`
ya hace esa intersección). Subiendo por las aristas CALLS desde los símbolos tocados
se llega a los tests que los ejercitan: eso es la selección.

Lo que este módulo NO hace es decidir si el cambio está bien: devuelve la lista y el
motivo, y el que ejecuta pytest es el usuario o el pre-commit. Devolver, no dictaminar
(ARCHITECTURE, regla 2).

**La regla que gobierna el diseño: ante la duda, todo.** Una selección que se deja
fuera un test que habría fallado no es "menos cobertura", es un falso verde — y un
falso verde mata el comando (SCOPE, criterio de muerte de esta familia). Por eso cada
camino dudoso (un `conftest.py` tocado, un fichero fuera del grafo, un símbolo que no
resuelve) devuelve TODO con su motivo escrito, en vez de una lista optimista.
"""

import os

from . import changes, symbols

#: Ficheros que cambian el comportamiento de la suite entera sin aparecer como
#: llamantes de nada: pytest los carga por convención, no por una llamada que el
#: AST pueda ver. Tocarlos obliga a correr todo.
FICHEROS_GLOBALES = ("conftest.py", "pytest.ini", "tox.ini", "setup.cfg", "pyproject.toml")


def _es_test(qual, nodo):
    """Un test que pytest COLECCIONA de verdad.

    El filtro tiene que ser el nombre, no "vive en tests/": un helper como
    `_generar` está en un fichero de tests y el grafo lo ve, pero pytest no lo
    colecciona. Seleccionarlo devuelve `ERROR: not found` y, con él, exit code 4
    — "no tests ran", que en un gate se lee igual de verde que "todo pasó".
    Ese detalle falseó la primera medición de esta idea.
    """
    if not qual.startswith("tests."):
        return False
    if nodo.get("kind") != "function":
        return False
    return qual.rsplit(".", 1)[-1].startswith("test_")


def _llamantes(edges):
    """destino -> {origenes} sobre las aristas CALLS (las DEFINES no propagan)."""
    tabla = {}
    for origen, destino, tipo in edges:
        if tipo == "CALLS":
            tabla.setdefault(destino, set()).add(origen)
    return tabla


def tests_que_alcanzan(nodes, llamantes, semillas, max_depth=8):
    """Cierre transitivo de llamantes desde `semillas` hasta los tests.

    `max_depth` no es una optimización: es el tope que impide que un ciclo de
    llamadas convierta esto en un bucle infinito. Si se agota con frontera
    pendiente lo decimos, porque una selección truncada en silencio es
    exactamente el falso verde que este módulo existe para evitar.
    """
    vistos = set()
    frontera = set(semillas)
    tests = set()
    truncado = False
    for _ in range(max_depth):
        siguiente = set()
        for simbolo in frontera:
            for origen in llamantes.get(simbolo, ()):
                if origen in vistos:
                    continue
                vistos.add(origen)
                if _es_test(origen, nodes.get(origen, {})):
                    tests.add(origen)
                else:
                    siguiente.add(origen)
        frontera = siguiente
        if not frontera:
            break
    else:
        truncado = bool(frontera)
    return tests, truncado


def _ficheros_de(nodes, quals):
    """Los ficheros de test, ordenados. Granularidad de FICHERO, no de test.

    Un id por test (`f.py::test_x`) es frágil: basta que uno no exista para que
    pytest devuelva exit code 4 sin correr nada. Un fichero siempre existe si el
    grafo lo vio.
    """
    ficheros = set()
    for qual in quals:
        ruta = (nodes.get(qual) or {}).get("file") or ""
        if ruta:
            ficheros.add(ruta.replace("\\", "/"))
    return sorted(ficheros)


def _todos_los_ficheros_de_test(nodes):
    return _ficheros_de(nodes, [q for q, n in nodes.items() if _es_test(q, n)])


def _simbolos_tocados(nodes, rangos):
    """Los símbolos cuyo cuerpo intersecta un hunk del diff.

    Misma intersección `[line, end]` × `+c,d` que `changes._onda_del_diff`, pero
    sobre un grafo ya calculado y quedándose con el símbolo más interno: tocar un
    método intersecta también con su clase entera, y sembrar las dos arrastraría
    los tests de todos los demás métodos de esa clase.
    """
    normal = {
        os.path.normcase(ruta.replace("/", os.sep)): tramos
        for ruta, tramos in rangos.items()
    }
    tocados = []
    for qual, nodo in nodes.items():
        if nodo.get("kind") == "module":
            continue
        tramos = normal.get(os.path.normcase(nodo.get("file") or ""))
        if not tramos:
            continue
        inicio, fin = nodo.get("line"), nodo.get("end")
        if not inicio or not fin:
            continue
        if any(a <= fin and inicio <= b for a, b in tramos):
            tocados.append(qual)
    dueños = {nodes[q].get("owner") for q in tocados if nodes[q].get("owner")}
    return sorted(q for q in tocados if q not in dueños)


def analyze(root, rev_range=None, staged=False, skip=None, include_nested=False):
    """Qué tests correr por lo que cambió, y por qué esos.

    Devuelve siempre `motivo` y `total`: la selección sin su motivo no se puede
    auditar, y sin el total no se sabe si "12 ficheros" es un ahorro o es todo.
    """
    report = {
        "root": root,
        "range": "staged" if staged else rev_range,
        "range_error": None,
        "tests": [],          # ficheros a pasar a pytest
        "n_tests": 0,         # funciones de test seleccionadas
        "total_tests": 0,     # funciones de test que hay en el repo
        "total_files": 0,
        "symbols": [],        # los símbolos del diff que dispararon la selección
        "todo": False,        # True = hay que correr la suite entera
        "motivo": "",
        "avisos": [],
    }
    if not os.path.isdir(root):
        report["range_error"] = "la raiz no existe o no es un directorio: %s" % root
        return report

    grafo = symbols.analyze(root, skip=skip or symbols.DEFAULT_SKIP,
                            include_nested=include_nested)
    if grafo.get("root_error"):
        report["range_error"] = grafo["root_error"]
        return report

    nodes = {n["qual"]: n for n in grafo["nodes"]}
    todos = _todos_los_ficheros_de_test(nodes)
    report["total_files"] = len(todos)
    report["total_tests"] = len([q for q, n in nodes.items() if _es_test(q, n)])

    def correr_todo(motivo):
        report["tests"] = todos
        report["n_tests"] = report["total_tests"]
        report["todo"] = True
        report["motivo"] = motivo
        return report

    if staged:
        diff = changes._git_output(root, "diff", "--unified=0", "--cached")
    elif rev_range:
        diff = changes._git_output(root, "diff", "--unified=0", rev_range)
    else:
        rev_range = "HEAD~1..HEAD"
        report["range"] = rev_range
        diff = changes._git_output(root, "diff", "--unified=0", rev_range)

    if diff is None:
        return correr_todo("no se pudo leer el diff (¿sin git, o rango invalido?): todo")
    if not diff.strip():
        report["motivo"] = "el diff esta vacio: nada que correr"
        return report

    rangos = changes._hunks_py(diff)

    # Un fichero global tocado cambia la suite entera sin ser llamante de nada.
    for ruta in rangos:
        base = os.path.basename(ruta)
        if base in FICHEROS_GLOBALES:
            return correr_todo("%s tocado: cambia la suite entera, se corre todo" % base)

    if not rangos:
        return correr_todo("el diff no toca ningun .py que el grafo vea: todo")

    # Los símbolos que el diff toca: la misma intersección que hace la onda del
    # cambio, pero sobre el grafo YA calculado. Llamar a `_onda_del_diff` aquí
    # volvería a analizar el repo entero (lo hace por su cuenta), y el
    # presupuesto de esta familia es el de un pre-commit.
    semillas = _simbolos_tocados(nodes, rangos)
    report["symbols"] = semillas

    if not semillas:
        return correr_todo(
            "el diff toca .py pero no cae dentro de ningun simbolo del grafo "
            "(codigo a nivel de modulo, imports, constantes): todo")

    llamantes = _llamantes(grafo["edges"])
    tests, truncado = tests_que_alcanzan(nodes, llamantes, semillas)
    if truncado:
        return correr_todo("el cierre de llamantes no termino (¿ciclo de llamadas?): todo")

    # Un símbolo de test tocado directamente entra él mismo en la selección.
    for qual in semillas:
        if _es_test(qual, nodes.get(qual, {})):
            tests.add(qual)

    if not tests:
        return correr_todo(
            "ningun test alcanza lo que cambiaste — eso es el dato, no un ahorro: todo")

    report["tests"] = _ficheros_de(nodes, tests)
    report["n_tests"] = len(tests)
    report["motivo"] = "%d test(s) alcanzan los %d simbolo(s) que toca el diff" % (
        len(tests), len(semillas))
    return report
