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
import os
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "src"))

DATOS = os.path.join(RAIZ, ".oraculo.cov")
INI = os.path.join(RAIZ, ".oraculo.ini")


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
    return rc


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


def contrastar():
    from galaxybrain import impacted, symbols

    if not os.path.exists(DATOS):
        print("no hay datos de coverage: corre primero con --correr")
        return 2

    grafo = symbols.analyze(RAIZ)
    nodes = {n["qual"]: n for n in grafo["nodes"]}
    llamantes = impacted._llamantes(grafo["edges"])
    impacted._enlaza_dunders(nodes, llamantes)
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
    # no existe. Un simbolo que se pasa como valor hace que gb corra la suite
    # entera: cuesta ahorro y por eso se cuenta aparte.
    por_valor = set(grafo.get("usados_como_valor") or [])

    fallos, ahorros, total, cayeron = [], [], 0, 0
    for qual, tests_reales in sorted(verdad.items()):
        if qual in por_valor:
            cayeron += 1
            ahorros.append(0.0)
            total += 1
            continue
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
    print("caen a 'corre todo' por valor    : %d  (%.0f%% de los medidos)"
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
    return 1 if fallos else 0


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--correr", action="store_true",
                   help="corre la suite bajo coverage antes de contrastar")
    args = p.parse_args()
    if args.correr and correr_suite() not in (0, 1):
        sys.exit(2)
    sys.exit(contrastar())
