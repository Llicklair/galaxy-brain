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

#: Un test que lanza un SUBPROCESO ejercita el código sin dejar ninguna arista de
#: llamada que seguir: para el AST, `subprocess.run([sys.executable, ...])` es una
#: llamada a `subprocess.run` y nada más. Medido en este repo el 5-ago-2026: 17 de
#: 37 ficheros de test entran por ahí, y romper `saferepr.repr_local` hacía fallar
#: `test_end_to_end.py` sin que la selección lo viera. Son opacos, así que van
#: SIEMPRE — un 46% de la suite es un mal precio, pero un falso verde no tiene
#: precio (SCOPE, criterio de muerte de esta familia).
MARCAS_OPACAS = ("subprocess", "Popen", "runpy", "os.system", "os.spawn", "multiprocessing")


def _sin_licencia_para_estrechar(grafo):
    """Los lenguajes del informe que NO pueden estrechar la seleccion, o "".

    Solo aplica al motor multilenguaje, que declara `lenguajes` en su informe. La
    via Python no lo declara y no se toca: es el motor maduro, con su propio
    banco (42/42 sin verdes falsos) y su propia caida segura.
    """
    presentes = grafo.get("lenguajes")
    if not presentes:
        return ""
    from . import lenguajes as tabla

    faltan = [i for i in presentes if not tabla.LENGUAJES.get(i, {}).get("tia")]
    return ", ".join(sorted(faltan))


def _es_test(qual, nodo):
    """Un test que pytest COLECCIONA de verdad.

    El filtro tiene que ser el nombre, no "vive en tests/": un helper como
    `_generar` está en un fichero de tests y el grafo lo ve, pero pytest no lo
    colecciona. Seleccionarlo devuelve `ERROR: not found` y, con él, exit code 4
    — "no tests ran", que en un gate se lee igual de verde que "todo pasó".
    Ese detalle falseó la primera medición de esta idea.
    """
    # Un motor puede MARCAR sus tests, y entonces manda su marca: en JS/TS los
    # casos no son funciones nombradas sino llamadas a `test()`/`it()` dentro de
    # un fichero, asi que el nodo que se puede seleccionar es el modulo. Quien
    # conoce esa convencion es el motor, no este modulo — cablearla aqui obligaria
    # a tocar la seleccion cada vez que entre un lenguaje (ADR 0009).
    if nodo.get("test"):
        return True
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


def _ficheros_opacos(root, ficheros):
    """Los ficheros de test que ejercitan el código por una vía que el AST no ve.

    No se intenta adivinar QUÉ ejercita cada subproceso — eso exigiría interpretar
    argumentos, y adivinar es justo lo que produce el falso verde. Se detecta que
    hay una vía opaca y se corre el fichero entero.
    """
    opacos = set()
    for rel in ficheros:
        path = os.path.join(root, rel.replace("/", os.sep))
        try:
            with open(path, "r", encoding="utf-8-sig", errors="replace") as handle:
                texto = handle.read()
        except OSError:
            # Si no se puede leer, se asume opaco: la duda se resuelve corriéndolo.
            opacos.add(rel)
            continue
        if any(marca in texto for marca in MARCAS_OPACAS):
            opacos.add(rel)
    return opacos


def rangos_del_diff(root):
    """Los tramos que el diff sin commitear AÑADE, por fichero.

    Estaba escrito en `actividad` y hacía falta aquí; es la cuarta lista paralela
    que aparece esta semana, así que se factoriza en vez de copiarse.

    `--relative` no es cosmético: sin él git da las rutas desde el toplevel del
    repo y los nodos las traen desde la raíz analizada, no casa ni un hunk y la
    intersección sale vacía sin decir por qué.
    """
    from . import graph

    diff = graph._git(root, "diff", "--relative", "HEAD", "-U0")
    return changes._hunks_py(diff) if diff else {}


def _rangos_por_fichero(rangos):
    """Las rutas del diff normalizadas para casar con las de los nodos."""
    return {
        os.path.normcase(ruta.replace("/", os.sep)): tramos
        for ruta, tramos in rangos.items()
    }


def simbolos_preexistentes(nodes, rangos):
    """De los símbolos que el diff toca, los que YA EXISTÍAN antes del cambio.

    Un símbolo es NUEVO si su cuerpo entero cae dentro de líneas añadidas: una
    función recién escrita al final del fichero está toda en el hunk. Si asoma
    aunque sea una línea que el hunk no añadió, ese símbolo estaba ahí y el
    cambio lo ha MODIFICADO.

    Existe por lo que midió la tirada del 9-ago. Ante un rechazo del grafo, dos
    de tres agentes hicieron desaparecer la violación tocando código que nadie
    les pidió tocar: uno vació `carrito.Total` y se llevó la suma al módulo de
    impuestos, otro le clavó el 21% como valor por defecto a `total`. Los dos
    veredictos eran CORRECTOS sobre sus hechos —sin ciclos, sin cruces, verdes—
    porque "sin violaciones" era alcanzable degradando el código. El rechazo es
    una presión y el modelo la alivia por donde no hay medida.

    Esto NO acusa: modificar lo que existe es la mitad del trabajo normal. Es un
    hecho para ponerlo delante — del modelo en el peldaño siguiente, y del humano
    en el veredicto.

    Techo declarado (ADR 0008): un símbolo REESCRITO entero cuenta como nuevo,
    porque todas sus líneas son añadidas y desde el diff no se distingue. Se
    calla hacia el lado que no acusa.
    """
    normal = _rangos_por_fichero(rangos)
    previos = []
    for qual in _simbolos_tocados(nodes, rangos):
        nodo = nodes[qual]
        tramos = normal.get(os.path.normcase(nodo.get("file") or ""))
        inicio, fin = nodo.get("line"), nodo.get("end")
        if not tramos or not inicio or not fin:
            continue
        if not any(a <= inicio and fin <= b for a, b in _fusiona(tramos)):
            previos.append(qual)
    return sorted(previos)


def _fusiona(tramos):
    """Tramos solapados o contiguos, en uno. Sin esto, un símbolo partido en dos
    hunks pegados parece asomar fuera de ambos y se contaría como preexistente."""
    fusionados = []
    for a, b in sorted(tramos):
        if fusionados and a <= fusionados[-1][1] + 1:
            fusionados[-1][1] = max(fusionados[-1][1], b)
        else:
            fusionados.append([a, b])
    return [(a, b) for a, b in fusionados]


def _simbolos_tocados(nodes, rangos):
    """Los símbolos cuyo cuerpo intersecta un hunk del diff.

    Misma intersección `[line, end]` × `+c,d` que `changes._onda_del_diff`, pero
    sobre un grafo ya calculado y quedándose con el símbolo más interno: tocar un
    método intersecta también con su clase entera, y sembrar las dos arrastraría
    los tests de todos los demás métodos de esa clase.
    """
    normal = _rangos_por_fichero(rangos)
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


def analyze(root, rev_range=None, staged=False, worktree=False, skip=None,
            include_nested=False, grafo=None):
    """Qué tests correr por lo que cambió, y por qué esos.

    Devuelve siempre `motivo` y `total`: la selección sin su motivo no se puede
    auditar, y sin el total no se sabe si "12 ficheros" es un ahorro o es todo.
    """
    report = {
        "root": root,
        "range": "worktree" if worktree else ("staged" if staged else rev_range),
        "range_error": None,
        "tests": [],          # ficheros a pasar a pytest
        "n_tests": 0,         # funciones de test seleccionadas
        "total_tests": 0,     # funciones de test que hay en el repo
        "total_files": 0,
        "symbols": [],        # los símbolos del diff que dispararon la selección
        "opacos": [],         # ficheros incluidos por lanzar subprocesos, no por el grafo
        "todo": False,        # True = hay que correr la suite entera
        "motivo": "",
        "avisos": [],
    }
    if not os.path.isdir(root):
        report["range_error"] = "la raiz no existe o no es un directorio: %s" % root
        return report

    # `grafo` inyectable por la misma razon que `graph.analyze(constructor=...)`:
    # la seleccion razona sobre nodos y aristas, no sobre un lenguaje, asi que
    # quien elige motor es la CLI y este modulo no conoce a ninguno (ADR 0009).
    if grafo is None:
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

    # Estrechar exige LICENCIA. Un grafo de llamadas incompleto no cuesta ahorro,
    # cuesta un verde falso: si falta una arista, los tests que llegaban por ahi
    # se caen de la seleccion y la suite reducida pasa con el arbol roto. Solo
    # los lenguajes cuyo banco lo midio con rojos reales la tienen (ADR 0009,
    # criterio de aborto 1); el resto corre entero y se dice por que.
    sin_licencia = _sin_licencia_para_estrechar(grafo)
    if sin_licencia:
        return correr_todo(
            "%s: su grafo de llamadas no esta medido lo bastante completo como para "
            "estrechar sin arriesgar un verde falso, asi que se corre todo" % sin_licencia)

    if worktree:
        # Lo que hay escrito en disco y todavia no esta en el indice: el estado
        # de en medio de una edicion. `HEAD` como base incluye tambien lo ya
        # staged, que es lo correcto — durante la edicion importa el conjunto de
        # lo que difiere de lo ultimo commiteado, no como se reparte.
        diff = changes._git_output(root, "diff", "--unified=0", "HEAD")
    elif staged:
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

    alcanzados = _ficheros_de(nodes, tests)
    # Los opacos van siempre: ejercitan el codigo sin dejar arista que seguir.
    opacos = sorted(_ficheros_opacos(root, todos) - set(alcanzados))
    report["opacos"] = opacos
    report["tests"] = sorted(set(alcanzados) | set(opacos))
    report["n_tests"] = len(tests)
    report["motivo"] = "%d test(s) alcanzan los %d simbolo(s) que toca el diff" % (
        len(tests), len(semillas))
    if opacos:
        report["avisos"].append(
            "%d fichero(s) mas por lanzar subprocesos: ejercitan el codigo sin "
            "dejar arista que seguir, asi que van siempre" % len(opacos))
    return report
