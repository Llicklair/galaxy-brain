"""Un agente sobre un worktree, con el mapa mirándole. UN comando.

    python bucle/agente.py "arregla X"

Lo que hacía falta teclear antes para llegar aquí: crear el worktree a mano,
escribir un lanzador que teee el stdout a `<worktree>.consola.log`, arrancar el
watch, y buscar la ruta del mapa. Cinco pasos y un script desechable cada vez —
reportado en uso real (8-ago): «hemos gastado demasiados prompts hasta llegar
aquí, esto debería ser más ágil». La norma va en el defecto: lo correcto es lo
que sale sin escribir nada.

Vive en `bucle/` y no en `gb` a propósito: gb PROVEE (el grafo, la actividad
derivada, el mapa), no orquesta (ARCHITECTURE regla 4). Y NO reimplementa el
orquestador: reutiliza sus piezas —el worktree, el teeador de consola, el
formateador de líneas— porque dos copias del mismo lanzador divergen y una de
las dos acaba mintiendo.

NUNCA mergea: al terminar deja el diff y el worktree, y quien decide es el
humano (regla de trabajo: los bucles no mergean).
"""

import argparse
import importlib.util
import os
import re
import sys


def _carga_orquestador():
    """El bucle, cargado por RUTA. `bucle/` no es paquete, asi que `import
    bucle` cae en un namespace package (PEP 420) y el modulo real nunca llega —
    la misma trampa que ya mordio al banco de replay."""
    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bucle.py")
    spec = importlib.util.spec_from_file_location("bucle_del_lanzador", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


bucle = _carga_orquestador()
RAIZ = bucle.RAIZ


def nombre_por_defecto(tarea):
    """Un nombre legible derivado de la tarea: el worktree se llama como lo que
    hace, que es lo que se va a leer en la tarjeta del mapa."""
    palabras = re.findall(r"[a-zA-Z0-9_]+", tarea.lower())[:3]
    return "-".join(palabras) or "agente"


def asegura_mapa():
    """Un watch vivo sobre el repo, si no lo hay. Sin esto la actividad existe
    en disco pero nadie la pinta — el fallo que costo tres tandas invisibles.
    El candado de gb evita duplicados, asi que llamarlo de mas es inofensivo."""
    destino = os.path.join(RAIZ, "mapa.html")
    bucle._corre(bucle.GB + ["symbols", "--html", destino, "--watch", "--fondo",
                             "--refresco", "3"], timeout=60)
    return destino


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="un agente en un worktree, con el mapa mirandole")
    parser.add_argument("tarea", help="que tiene que hacer")
    parser.add_argument("--nombre", help="nombre del worktree (por defecto, de la tarea)")
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--sin-mapa", action="store_true",
                        help="no asegurar el watch (por defecto se arranca si falta)")
    args = parser.parse_args(argv)

    nombre = args.nombre or nombre_por_defecto(args.tarea)
    worktree = bucle.preparar_worktree(nombre)
    print("worktree : %s" % worktree)
    if not args.sin_mapa:
        print("mapa     : file:///%s" % asegura_mapa().replace("\\", "/"))
    print("consola  : %s" % bucle._log_consola(worktree))
    print("-- el agente empieza; su tarjeta aparece en el mapa al primer cambio --\n",
          flush=True)

    try:
        bucle.ejecutar_real({"id": nombre}, worktree, args.tarea, args.timeout, eco=True)
    except RuntimeError as error:
        # Un agente que sale mal no es una excepcion del lanzador: es un hecho
        # de la tirada. Se dice y se sigue al diff, que puede tener trabajo util.
        print("\n[el agente termino mal] %s" % error)

    _rc, diff, _err = bucle._corre(["git", "diff", "--stat", "HEAD"], cwd=worktree)
    print("\n== lo que dejo (SIN commitear, SIN mergear) ==")
    print(bucle._texto(diff).strip() or "(nada)")
    print("\nrevisalo con:  git -C %s diff" % worktree)
    print("y cuando decidas TU:  git -C %s diff | git apply -" % worktree)
    return 0


if __name__ == "__main__":
    sys.exit(main())
