"""El conflicto SEMANTICO entre agentes: cada rama verde sola, la union rota.

El sector lo nombra como la clase mas dificil y sin dueno (ago-2026):

    "cambios que parecen correctos aislados se contradicen al componerse,
     pasando compilacion y linting y fallando en runtime"
    "el CI en verde te dice que los tests que ya tenias siguen pasando; no te
     dice que TRES CAMBIOS son correctos JUNTOS"
    "el codigo mergea limpio, el pipeline se pone verde, y el comportamiento que
     falta espera a que lo descubra un cliente"

Tasa medida fuera: 5-10% de conflictos semanticos entre agentes en paralelo. Y el
veredicto del sector: "la decision semantica se queda con el humano, porque
ningun merge tool puede tomarla". Un merge tool no, porque mira TEXTO. Esto mira
lo que el grafo dice que hay que CORRER sobre el arbol compuesto.

`aislado.converge` ya hace las dos mitades —cada rama sola y luego la union— y
tiene medido el caso INVERSO (el rescate: rojo solo, verde junto, 5-ago-2026).
Lo que este banco comprueba es la direccion que el sector senala:

    VERDE sola + VERDE sola  ->  ROJA junta

Sin fabricar un conflicto de texto: los dos diffs mergean limpios. Se contradicen
en el SIGNIFICADO, que es justo lo que git no ve.

    python bancos/banco_convergencia.py          # el control, sin gastar agentes
"""

import argparse
import os
import shutil
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "src"))
BASE = os.path.join(RAIZ, "bancos", "bench-convergencia")

#: `precio` en EUROS, un consumidor y su test. Dos ficheros distintos a proposito:
#: si las dos ramas tocaran el mismo, git detectaria el conflicto y no habria nada
#: que demostrar. El choque tiene que ser invisible para el merge.
MODULOS = {
    "tienda/__init__.py": "",
    "tienda/precio.py": (
        '"""Precio unitario, EN EUROS."""\n\n\n'
        "def precio(articulo):\n"
        "    return {'pan': 2}.get(articulo, 0)\n"
    ),
    "tienda/carrito.py": (
        "from tienda.precio import precio\n\n\n"
        "def total(articulos):\n"
        "    return sum(precio(a) for a in articulos)\n"
    ),
    "tests/__init__.py": "",
    "tests/test_carrito.py": (
        "from tienda.carrito import total\n\n\n"
        "def test_total():\n"
        "    assert total(['pan']) == 2\n"
    ),
}

#: RAMA A: `precio` pasa a CENTIMOS y adapta a su unico consumidor. Coherente y
#: verde: A toca los dos ficheros que conoce.
RAMA_A = {
    "tienda/precio.py": (
        '"""Precio unitario, EN CENTIMOS."""\n\n\n'
        "def precio(articulo):\n"
        "    return {'pan': 200}.get(articulo, 0)\n"
    ),
    "tienda/carrito.py": (
        "from tienda.precio import precio\n\n\n"
        "def total(articulos):\n"
        "    return sum(precio(a) for a in articulos) / 100\n"
    ),
}

#: RAMA B: anade un consumidor NUEVO, escrito contra el contrato que veia (euros).
#: Verde sola, porque en su arbol `precio` sigue devolviendo euros. Y no toca
#: ninguno de los ficheros de A: el merge sale limpio.
RAMA_B = {
    "tienda/informe.py": (
        "from tienda.precio import precio\n\n\n"
        "def linea(articulo):\n"
        "    return 'total: %d euros' % precio(articulo)\n"
    ),
    "tests/test_informe.py": (
        "from tienda.informe import linea\n\n\n"
        "def test_linea():\n"
        "    assert linea('pan') == 'total: 2 euros'\n"
    ),
}


def _git(cwd, *args):
    return subprocess.run(["git"] + list(args), cwd=cwd, capture_output=True, text=True)


def _escribe(raiz, ficheros):
    for rel, cuerpo in ficheros.items():
        ruta = os.path.join(raiz, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, "w", encoding="utf-8", newline="") as fh:
            fh.write(cuerpo)


def genera():
    """El repo base y dos worktrees, uno por 'agente'."""
    shutil.rmtree(BASE, ignore_errors=True)
    os.makedirs(BASE, exist_ok=True)
    _escribe(BASE, MODULOS)
    _git(BASE, "init", "-q")
    _git(BASE, "config", "user.email", "b@b")
    _git(BASE, "config", "user.name", "b")
    _git(BASE, "add", "-A")
    _git(BASE, "commit", "-qm", "base")

    ramas = []
    for nombre, ficheros in (("agente-a", RAMA_A), ("agente-b", RAMA_B)):
        ruta = os.path.join(BASE, ".worktrees", nombre)
        _git(BASE, "worktree", "add", "-q", "--detach", ruta, "HEAD")
        _escribe(ruta, ficheros)
        ramas.append(ruta)
    return BASE, ramas


def limpia():
    for nombre in ("agente-a", "agente-b"):
        _git(BASE, "worktree", "remove", "--force",
             os.path.join(BASE, ".worktrees", nombre))
    _git(BASE, "worktree", "prune")


def corre():
    """`converge` sobre las dos ramas. Devuelve el informe."""
    from galaxybrain import aislado

    return aislado.converge(BASE, traza=None)


def main():
    genera()
    try:
        informe = corre()
    finally:
        pass

    ramas = {r["nombre"]: r["veredicto"] for r in informe.get("ramas") or []}
    union = (informe.get("union") or {}).get("veredicto")
    print("\n=== BANCO DE CONVERGENCIA ===")
    print("monto la union       : %s" % informe.get("monto"))
    for nombre, veredicto in sorted(ramas.items()):
        print("  %-10s sola     : %s" % (nombre, "VERDE" if veredicto == 0 else "ROJA"))
    print("  union (las dos)    : %s" % ("VERDE" if union == 0 else "ROJA"))
    print("  rescatados         : %s" % (informe.get("rescatados") or "ninguno"))
    if informe.get("motivo"):
        print("  motivo             : %s" % informe["motivo"])

    # El caso que el sector llama el mas dificil: las dos verdes, la union rota.
    verdes = ramas and all(v == 0 for v in ramas.values())
    detecta = verdes and union not in (0, None)
    print("\n%s" % ("DETECTA el conflicto semantico: las dos verdes, la union ROJA"
                    if detecta else
                    "NO lo detecta — y sin eso este banco no demuestra nada"))
    return 0 if detecta else 1


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--limpiar", action="store_true", help="quitar los worktrees y salir")
    args = p.parse_args()
    if args.limpiar:
        limpia()
        raise SystemExit(0)
    raise SystemExit(main())
