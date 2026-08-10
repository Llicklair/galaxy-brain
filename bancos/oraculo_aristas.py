"""El segundo oraculo: contrastar las ARISTAS del grafo contra las que ocurren de verdad.

El de cobertura ([oraculo_cobertura.py]) mide la SELECCION de tests: que ficheros
se pierden. Dice que fallamos, no POR QUE. Su primera tirada dejo 91 falsos
verdes y las dos causas se encontraron a mano, leyendo. Este banco automatiza esa
lectura: mide la capa de abajo, la arista, que es donde esta el defecto.

    verdad     = llamadas que OCURREN al correr la suite (sys.setprofile)
    grafo      = aristas CALLS que el AST dedujo
    HUECO      = verdad - grafo    <- llamadas reales que el grafo no ve

Por que el runtime y no un grafo de terceros. Se probaron los dos candidatos con
mejores numeros publicados y ninguno sobrevive al contacto:

  - PyCG (ICSE'21, 99.2% precision / 69.9% recall) esta ARCHIVADO; el paquete de
    PyPI 0.0.8 se instala como `PyCG` pero su codigo hace `from pycg import ...`,
    asi que ni arranca sin un shim, y con el shim revienta su propio hook de
    imports sobre este paquete (`ImportManagerError`, 22 modulos).
  - HeaderGen 2.0.2 (95.6/95.3) si se mantiene, pero arrastra ~140 paquetes
    —tensorflow, keras, jupyter, scikit-learn, xgboost— porque su caso de uso son
    notebooks de ML. Inaceptable para un banco.
  - Jarvis (+84% precision sobre PyCG) no publica paquete: seria clonar un
    prototipo construido sobre la MISMA maquinaria que acaba de reventar.

Y ademas el runtime es mejor oraculo, no un premio de consolacion: un analisis
estatico con 69.9% de recall solo puede dar una cota inferior discutible, y el
runtime da el HECHO — esta llamada ocurrio. Cero dependencias, que es la regla de
este repo.

Techo declarado, y es el mismo de siempre: solo ve lo que la suite EJERCITA. Un
hueco que ningun test recorre no sale aqui. Este banco mide recall, nunca
precision: que el grafo tenga una arista que la suite no recorrio no es un fallo.

    python bancos/oraculo_aristas.py --correr    # 1) la suite bajo el perfilador
    python bancos/oraculo_aristas.py             # 2) el contraste
"""

import argparse
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "src"))

DATOS = os.path.join(RAIZ, ".oraculo_aristas.json")
FUENTE = os.path.normcase(os.path.join(RAIZ, "src", "galaxybrain"))


def _huella(ficheros):
    """Hash de EXACTAMENTE los ficheros implicados en los datos.

    Los pares se anotan por (fichero, LINEA). Si uno de esos ficheros cambia
    entre la captura y el contraste, las lineas se desplazan y cada par apunta a
    otro simbolo: el informe sale lleno de huecos inventados y parece un
    hallazgo. Un instrumento que puede mentir en silencio tiene que negarse a
    hablar, asi que la huella viaja con los datos.

    Dos iteraciones costo acertar el ALCANCE, y las dos fallaron por el mismo
    lado. Primero se hasheo solo `src`, y la trampa volvio a saltar por `tests`:
    los dos extremos de una arista son nodos, asi que mover un test desplaza al
    LLAMANTE igual que mover `src` desplaza al llamado — media conexion, y una
    guardia que cubre una de las dos entradas se lee como verde. Luego se hasheo
    el arbol ENTERO, y era demasiado: editar un banco invalidaba unos datos que
    ningun banco toca, o sea tres minutos de suite por una linea de comentario.

    Lo correcto es lo exacto: los ficheros que los pares NOMBRAN, ni uno mas.
    Limite declarado: un fichero NUEVO no invalida nada, porque no puede mover
    lineas de los que ya estaban.
    """
    import hashlib

    h = hashlib.sha256()
    for ruta in sorted(ficheros):
        h.update(ruta.encode())
        try:
            with open(ruta, "rb") as fh:
                h.update(fh.read())
        except OSError:
            h.update(b"<ilegible>")
    return h.hexdigest()


def _indice_por_fichero(nodes):
    """fichero absoluto -> [(inicio, fin, qual)], para localizar por linea."""
    idx = {}
    for qual, nodo in nodes.items():
        if nodo.get("kind") not in ("function", "method"):
            continue
        ruta, inicio, fin = nodo.get("file"), nodo.get("line"), nodo.get("end")
        if not (ruta and inicio and fin):
            continue
        clave = os.path.normcase(os.path.abspath(os.path.join(RAIZ, ruta)))
        idx.setdefault(clave, []).append((inicio, fin, qual))
    for lista in idx.values():
        lista.sort()
    return idx


def _localiza(idx, fichero, linea, exacto=False):
    """El simbolo mas ajustado que contiene esa linea. (qual, anidada).

    `co_firstlineno` apunta al primer DECORADOR, no al `def`, asi que la
    contencion estricta falla en funciones decoradas; de ahi el tercer intento,
    que acepta un `def` hasta 5 lineas por debajo. Es una heuristica de
    presentacion del bytecode, no del grafo, y por eso vive aqui y no en src.

    `exacto` es la correccion que costo el primer falso hallazgo de este banco.
    El grafo no emite nodo para las funciones ANIDADAS, asi que un closure cae
    por contencion dentro de su funcion padre — y una llamada a ese closure se
    leia como "arista perdida hacia el padre", que es mentira. Se descubrio con
    `aislado._union -> aislado.converge`: `decir` es un closure de `converge` que
    se le pasa a `_union` como argumento. Para el LLAMADO se exige que la linea
    sea el `def` mismo; para el LLAMANTE no, porque ahi atribuir el closure a su
    funcion padre es lo CORRECTO: es el simbolo que cambia si cambia el closure.
    """
    lista = idx.get(fichero)
    if not lista:
        return None, False
    mejor = None
    for inicio, fin, qual in lista:
        if inicio == linea:
            return qual, False
        if inicio <= linea <= fin:
            if mejor is None or (fin - inicio) < (mejor[1] - mejor[0]):
                mejor = (inicio, fin, qual)
    if mejor:
        return (None, True) if exacto else (mejor[2], True)
    for inicio, _fin, qual in lista:
        if 0 < inicio - linea <= 5:
            return qual, False
    return None, False


def correr_suite(subconjunto=None):
    """La suite bajo `sys.setprofile`, anotando (llamante, llamado) crudos.

    Se anota por (fichero, linea) y NO por nombre: traducir a qual dentro del
    callback multiplicaria el coste por cada llamada de la suite. La traduccion
    va despues, sobre el conjunto ya deduplicado.
    """
    import pytest

    vistos = set()
    prefijo = FUENTE

    def _perfil(frame, evento, arg):
        if evento != "call":
            return
        cod = frame.f_code
        fichero = cod.co_filename
        # Barato y primero: la inmensa mayoria de llamadas de una suite no son
        # nuestras. `normcase` solo sobre las que pasan el filtro.
        if prefijo not in os.path.normcase(fichero):
            return
        padre = frame.f_back
        if padre is None:
            return
        pcod = padre.f_code
        vistos.add((os.path.normcase(pcod.co_filename), pcod.co_firstlineno,
                    os.path.normcase(fichero), cod.co_firstlineno))

    argv = [subconjunto or "tests/", "-q", "-p", "no:cacheprovider"]
    os.chdir(RAIZ)
    print("corriendo la suite bajo el perfilador (mas lenta que la suite sola)...",
          flush=True)
    sys.setprofile(_perfil)
    try:
        rc = pytest.main(argv)
    finally:
        sys.setprofile(None)
    print("pytest devolvio %s | %d pares crudos" % (rc, len(vistos)))
    pares = sorted(vistos)
    implicados = sorted({p[0] for p in pares} | {p[2] for p in pares})
    with open(DATOS, "w", encoding="utf-8") as fh:
        json.dump({"huella": _huella(implicados), "ficheros": implicados,
                   "pares": pares}, fh)
    return int(rc)


def contrastar():
    from galaxybrain import symbols

    if not os.path.exists(DATOS):
        print("no hay datos de ejecucion: corre primero con --correr")
        return 2

    with open(DATOS, encoding="utf-8") as fh:
        guardado = json.load(fh)
    if (not isinstance(guardado, dict)
            or guardado.get("huella") != _huella(guardado.get("ficheros") or [])):
        print("los datos son de OTRO arbol: src cambio desde la captura y las "
              "lineas ya no casan. Vuelve a correr con --correr.")
        return 2
    crudos = guardado["pares"]

    grafo = symbols.analyze(RAIZ)
    nodes = {n["qual"]: n for n in grafo["nodes"]}
    idx = _indice_por_fichero(nodes)
    estaticas = {(o, d) for o, d, t in grafo["edges"] if t == "CALLS"}
    por_valor = set(grafo.get("usados_como_valor") or [])

    reales, sin_localizar, anidadas = set(), 0, 0
    for pf, pl, hf, hl in crudos:
        llamante, _ = _localiza(idx, pf, pl)
        llamado, era_anidada = _localiza(idx, hf, hl, exacto=True)
        if not llamado and era_anidada:
            anidadas += 1
            continue
        if not llamante or not llamado:
            sin_localizar += 1
            continue
        if llamante != llamado:
            reales.add((llamante, llamado))

    if not reales:
        print("NINGUNA llamada localizada: el instrumento esta mudo, no es que el "
              "grafo sea perfecto. Revisa el filtro de ficheros.")
        return 2

    huecos = sorted(reales - estaticas)

    # Las dos causas que ya tienen puerta puesta en la seleccion se cuentan
    # aparte: no son deuda nueva, son deuda YA cubierta rio abajo.
    dunder = [p for p in huecos if p[1].rsplit(".", 1)[-1].startswith("__")]
    valor = [p for p in huecos if p not in dunder and p[1] in por_valor]
    cubiertos = set(dunder) | set(valor)
    crudo = [p for p in huecos if p not in cubiertos]

    print("\n=== ORACULO DE ARISTAS ===")
    print("llamadas reales localizadas   : %d" % len(reales))
    print("a funcion ANIDADA (sin nodo)  : %d  (no es hueco: el grafo no las emite)" % anidadas)
    print("pares sin localizar (ignorados): %d" % sin_localizar)
    print("aristas CALLS del grafo        : %d" % len(estaticas))
    print("HUECOS (ocurren y no estan)    : %d  (%.0f%% de las reales)"
          % (len(huecos), 100 * len(huecos) / max(len(reales), 1)))
    print("  de ellos, despacho implicito : %d  (ya enlazado por _enlaza_dunders)" % len(dunder))
    print("  de ellos, usados como valor  : %d  (la seleccion sube por quien los NOMBRA)"
          % len(valor))
    print("  SIN PUERTA                   : %d  <- la lista de trabajo" % len(crudo))

    if crudo:
        cuenta = {}
        for _o, d in crudo:
            cuenta[d] = cuenta.get(d, 0) + 1
        print("\nlos llamados que mas llamantes pierden:")
        for d, n in sorted(cuenta.items(), key=lambda x: -x[1])[:15]:
            print("  %-52s %d llamante(s)" % (d, n))
        print("\nmuestra de pares sin puerta:")
        for o, d in crudo[:10]:
            print("  %s  ->  %s" % (o, d))
    return 1 if crudo else 0


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--correr", action="store_true",
                   help="corre la suite bajo el perfilador antes de contrastar")
    p.add_argument("--tests", default=None,
                   help="subconjunto de tests (por defecto: tests/)")
    args = p.parse_args()
    if args.correr and correr_suite(args.tests) not in (0, 1):
        sys.exit(2)
    sys.exit(contrastar())
