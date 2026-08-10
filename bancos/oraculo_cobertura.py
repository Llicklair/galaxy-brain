"""El oraculo: contrastar la seleccion de tests del GRAFO contra la de EJECUCION.

`gb tests` decide que tests correr subiendo por las aristas CALLS desde lo que
cambio. Es estatico: puede equivocarse por debajo (falta una arista y se cae un
test de la seleccion) y ese es el unico fallo que mata a esta familia — una suite
reducida que pasa con el arbol roto. Hasta hoy eso se medaa con bancos escritos a
mano, seis modulos encadenados: verdad, pero verdad de laboratorio.

`coverage` con contextos dinamicos da la verdad de EJECUCION sobre el repo real:
que test toco de verdad cada linea. Eso es un oraculo independiente y no un
control circular, porque no sale del grafo que se esta juzgando.

    verdad     = tests que EJECUTARON las lineas del simbolo
    seleccion  = tests que el grafo elige si ese simbolo cambia
    FALSO VERDE = verdad - seleccion     <- lo unico que importa

Se compara a nivel de FICHERO porque es lo que gb pasa a pytest, y se le suman
los ficheros opacos, que van siempre: medir contra una version de paja de la
seleccion no mediria nada.

Techo declarado: solo mide simbolos que ALGUN test ejecuta. De los que nadie
ejercita no hay verdad que contrastar — y que no haya es el dato, no un fallo de
la seleccion.

    python bancos/oraculo_cobertura.py --correr     # 1) la suite bajo coverage
    python bancos/oraculo_cobertura.py              # 2) el contraste
"""

import argparse
import json
import os
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "src"))

DATOS = os.path.join(RAIZ, ".oraculo.cov")
INI = os.path.join(RAIZ, ".oraculo.ini")
HUELLA = os.path.join(RAIZ, ".oraculo.huella")


def correr_suite():
    """La suite entera bajo coverage, con un contexto por funcion de test."""
    with open(INI, "w", encoding="utf-8") as fh:
        fh.write("[run]\ndynamic_context = test_function\nsource = src\n")
    print("corriendo la suite bajo coverage (tarda mas que la suite sola)...", flush=True)
    rc = subprocess.call(
        [sys.executable, "-m", "coverage", "run", "--rcfile", INI,
         "--data-file", DATOS, "-m", "pytest", "tests/", "-q"],
        cwd=RAIZ)
    print("pytest devolvio %d" % rc)
    with open(HUELLA, "w", encoding="utf-8") as fh:
        fh.write(_huella_src())
    return rc


def _huella_src():
    """Hash de `src`, que es lo que la cobertura anota por (fichero, LINEA).

    Mismo motivo y misma lección que en `oraculo_aristas.py`: si `src` cambia
    entre la captura y el contraste, las líneas se desplazan y los contextos
    caen dentro de otro símbolo. El informe sigue saliendo, con otro número, y
    nada avisa. Aquí faltaba, y se puso el día en que un arreglo de `symbols.py`
    invalidó en silencio una tirada que ya estaba en disco.
    """
    import hashlib

    h = hashlib.sha256()
    base = os.path.join(RAIZ, "src", "galaxybrain")
    for nombre in sorted(os.listdir(base)):
        if nombre.endswith(".py"):
            with open(os.path.join(base, nombre), "rb") as fh:
                h.update(nombre.encode())
                h.update(fh.read())
    return h.hexdigest()


def _mapa_de_tests(nodes):
    """(modulo_base, funcion) -> qual, para casar el contexto de coverage.

    El contexto que escribe coverage es `test_superficie.test_algo`: el modulo
    tal como lo importa pytest, SIN el paquete. Los qual del grafo llevan
    `tests.` delante. Se casa por los dos ultimos segmentos, que es lo unico que
    ambos comparten — comprobado, no supuesto.
    """
    from galaxybrain import impacted

    mapa = {}
    for qual, nodo in nodes.items():
        if not impacted._es_test(qual, nodo):
            continue
        partes = qual.split(".")
        if len(partes) >= 2:
            mapa[(partes[-2], partes[-1])] = qual
    return mapa


def _verdad_por_simbolo(nodes, mapa):
    """simbolo -> {quals de test que EJECUTARON alguna de sus lineas}."""
    import coverage

    cov = coverage.Coverage(data_file=DATOS)
    cov.load()
    datos = cov.get_data()

    por_fichero = {}
    for medido in datos.measured_files():
        contextos = datos.contexts_by_lineno(medido)
        por_fichero[os.path.normcase(os.path.abspath(medido))] = contextos

    verdad = {}
    for qual, nodo in nodes.items():
        if nodo.get("kind") not in ("function", "method"):
            continue
        inicio, fin = nodo.get("line"), nodo.get("end")
        ruta = nodo.get("file")
        if not (inicio and fin and ruta):
            continue
        clave = os.path.normcase(os.path.abspath(os.path.join(RAIZ, ruta)))
        contextos = por_fichero.get(clave)
        if not contextos:
            continue
        tests = set()
        for linea in range(inicio, fin + 1):
            for ctx in contextos.get(linea, ()):
                if not ctx:
                    continue                       # ejecutado fuera de un test
                partes = ctx.split(".")
                casado = mapa.get((partes[-2], partes[-1])) if len(partes) >= 2 else None
                if casado:
                    tests.add(casado)
        if tests:
            verdad[qual] = tests
    return verdad


def _puerta_que_falla(qual, perdidos, nodes, real, estaticas, por_valor):
    """Que PUERTA de la seleccion dejo escapar este falso verde.

    El grafo acierta el 96% de las aristas (oraculo_aristas, 10-ago-2026) y aun
    asi la seleccion pierde el 27%: el eslabon debil esta rio abajo del grafo, en
    las puertas que sobre-aproximan. Esto las nombra en vez de suponerlas.

    Se sube por el camino REAL —el que registro el perfilador— desde el simbolo
    hasta un test de un fichero perdido, y se devuelve el primer eslabon que el
    grafo no tiene, clasificado por la puerta a la que le tocaba cubrirlo.
    """
    objetivo = set(perdidos)
    visto, cola = set(), [(qual, [qual])]
    while cola:
        q, camino = cola.pop(0)
        if q in visto or len(camino) > 8:
            continue
        visto.add(q)
        for llamante in real.get(q, ()):
            ruta = nodes.get(llamante, {}).get("file")
            nuevo = [llamante] + camino
            if ruta and ruta.replace("\\", "/") in objetivo:
                for a, b in zip(nuevo, nuevo[1:]):
                    if (a, b) in estaticas:
                        continue
                    corto = b.rsplit(".", 1)[-1]
                    if corto.startswith("__") and corto.endswith("__"):
                        return "dunder: _enlaza_dunders no llego", (a, b)
                    if b in por_valor:
                        return "valor: la puerta de opacos no llego", (a, b)
                    return "sin puerta: arista que el grafo no ve", (a, b)
                return "el camino existe entero: falla el CIERRE, no una arista", None
            cola.append((llamante, nuevo))
    return "sin camino real hasta el fichero perdido", None


def contrastar():
    from galaxybrain import impacted, symbols

    if not os.path.exists(DATOS):
        print("no hay datos de coverage: corre primero con --correr")
        return 2
    guardada = ""
    if os.path.exists(HUELLA):
        with open(HUELLA, encoding="utf-8") as fh:
            guardada = fh.read().strip()
    if guardada != _huella_src():
        print("los datos de coverage son de OTRO src: las lineas ya no casan. "
              "Vuelve a correr con --correr.")
        return 2

    grafo = symbols.analyze(RAIZ)
    nodes = {n["qual"]: n for n in grafo["nodes"]}
    llamantes = impacted._llamantes(grafo["edges"])
    impacted._enlaza_dunders(nodes, llamantes)
    impacted._enlaza_pasados_como_valor(nodes, llamantes,
                                        grafo.get("nombrado_como_valor_en"))
    todos = impacted._todos_los_ficheros_de_test(nodes)
    opacos = impacted._ficheros_opacos(RAIZ, todos)

    mapa = _mapa_de_tests(nodes)
    verdad = _verdad_por_simbolo(nodes, mapa)
    if not verdad:
        # Un cero aqui seria el instrumento mudo, no un resultado.
        print("NINGUN simbolo con verdad de ejecucion: el instrumento esta mudo, "
              "no es que la seleccion sea perfecta. Revisa el formato del contexto.")
        return 2

    # Las MISMAS puertas que `impacted.analyze`, o esto mediria una seleccion que
    # no existe. Los pasados como valor SE MIDEN como los demas desde que la
    # seleccion estrecha por el cuerpo que los nombra; se siguen contando aparte
    # porque su camino es sobre-aproximado y conviene saber cuantos son.
    #
    # Antes se saltaban con `continue` y ahorro 0, replicando el "corre todo" de
    # entonces. Cuando la seleccion dejo de caer, el oraculo siguio saltandolos y
    # dio el MISMO numero que antes del cambio: un instrumento que copia la
    # conducta que juzga no puede medir que cambie. Cazado el 10-ago-2026, al ver
    # 27% de ahorro identico antes y despues.
    por_valor = set(grafo.get("usados_como_valor") or [])

    fallos, ahorros, total, cayeron = [], [], 0, 0
    for qual, tests_reales in sorted(verdad.items()):
        if qual in por_valor:
            cayeron += 1
        alcanzados, truncado = impacted.tests_que_alcanzan(nodes, llamantes, {qual})
        if truncado:
            continue                     # gb corre todo aqui: no hay nada que medir
        ficheros_sel = set(impacted._ficheros_de(nodes, alcanzados)) | opacos
        ficheros_verdad = set(impacted._ficheros_de(nodes, tests_reales))
        perdidos = ficheros_verdad - ficheros_sel
        total += 1
        ahorros.append(1 - len(ficheros_sel) / max(len(todos), 1))
        if perdidos:
            fallos.append((qual, sorted(perdidos), len(ficheros_verdad)))

    print("\n=== ORACULO DE COBERTURA ===")
    print("simbolos con verdad de ejecucion : %d" % total)
    print("ficheros de test en el repo      : %d" % len(todos))
    print("pasados como VALOR (camino sobre-aproximado): %d  (%.0f%% de los medidos)"
          % (cayeron, 100 * cayeron / max(total, 1)))
    print("ahorro medio de la seleccion     : %.0f%%"
          % (100 * sum(ahorros) / max(len(ahorros), 1)))
    print("FALSOS VERDES                    : %d" % len(fallos))
    if fallos:
        print("\nlos peores (simbolo -> ficheros que EJECUTAN y la seleccion no elige):")
        for qual, perdidos, n in sorted(fallos, key=lambda x: -len(x[1]))[:12]:
            print("  %-58s %d/%d perdidos" % (qual, len(perdidos), n))
            for f in perdidos[:3]:
                print("      %s" % f)
    if fallos:
        _por_que(fallos, nodes, grafo, por_valor)
    return 1 if fallos else 0


def _por_que(fallos, nodes, grafo, por_valor):
    """La atribucion por puerta. Degrada en silencio si no hay datos de aristas."""
    datos = os.path.join(RAIZ, ".oraculo_aristas.json")
    if not os.path.exists(datos):
        print("\n(sin datos del oraculo de aristas: corre "
              "`python bancos/oraculo_aristas.py --correr` para saber POR QUE)")
        return
    sys.path.insert(0, os.path.join(RAIZ, "bancos"))
    import importlib.util as iu

    spec = iu.spec_from_file_location(
        "_ora_aristas", os.path.join(RAIZ, "bancos", "oraculo_aristas.py"))
    ora = iu.module_from_spec(spec)
    spec.loader.exec_module(ora)

    with open(datos, encoding="utf-8") as fh:
        guardado = json.load(fh)
    if guardado.get("huella") != ora._huella(guardado.get("ficheros") or []):
        print("\n(los datos de aristas son de otro arbol: no se atribuye nada)")
        return

    idx = ora._indice_por_fichero(nodes)
    estaticas = {(a, b) for a, b, t in grafo["edges"] if t == "CALLS"}
    real = {}
    for pf, pl, hf, hl in guardado["pares"]:
        llamante, _ = ora._localiza(idx, pf, pl)
        llamado, _ = ora._localiza(idx, hf, hl, exacto=True)
        if llamante and llamado and llamante != llamado:
            real.setdefault(llamado, set()).add(llamante)

    cuenta, ejemplos = {}, {}
    for qual, perdidos, _n in fallos:
        causa, par = _puerta_que_falla(qual, perdidos, nodes, real, estaticas, por_valor)
        cuenta[causa] = cuenta.get(causa, 0) + 1
        ejemplos.setdefault(causa, (qual, par))

    print("\n=== POR QUE FALLA CADA UNO (la puerta, no el grafo) ===")
    for causa, n in sorted(cuenta.items(), key=lambda x: -x[1]):
        print("  %3d  %s" % (n, causa))
        qual, par = ejemplos[causa]
        print("       ej: %s" % qual)
        if par:
            print("           eslabon roto: %s -> %s" % par)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--correr", action="store_true",
                   help="corre la suite bajo coverage antes de contrastar")
    args = p.parse_args()
    if args.correr and correr_suite() not in (0, 1):
        sys.exit(2)
    sys.exit(contrastar())
