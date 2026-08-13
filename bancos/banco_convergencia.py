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


def genera(sembrar=True):
    """El repo base y dos worktrees, uno por 'agente'.

    `sembrar=True` escribe el trabajo de las dos ramas a mano: es el CONTROL, que
    comprueba que `converge` detecta el choque cuando el choque existe.

    `sembrar=False` deja los worktrees LIMPIOS, que es lo unico valido cuando
    escriben agentes de verdad. Sembrar y luego lanzar agentes encima seria
    fabricar el conflicto y llamarlo hallazgo — el experimento no mediria si
    ocurre, solo que yo se escribirlo.
    """
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
        if sembrar:
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


#: Las dos tareas de los agentes REALES. Independientes, plausibles, y ninguno
#: sabe del otro — que es la condicion de la vida real. NO se les pide que
#: choquen: se les pide trabajo normal sobre un contrato compartido, y si el
#: choque aparece es porque aparece.
TAREAS = (
    ("agente-a",
     "En `tienda/precio.py`, `precio()` devuelve euros y tiene que pasar a "
     "devolver CENTIMOS (multiplicar por 100). Adapta lo que haga falta para que "
     "el resto siga comportandose igual desde fuera. Corre `python -m pytest tests/` "
     "antes de terminar. No commitees."),
    ("agente-b",
     "Anade `tienda/informe.py` con una funcion `linea(articulo)` que devuelva "
     "'total: N euros' usando el precio del articulo, y su test en "
     "`tests/test_informe.py`. Corre `python -m pytest tests/` antes de terminar. "
     "No commitees."),
)


def _agente(ruta, prompt, timeout_seg):
    """`claude -p` headless, Opus, dentro del worktree de esa rama."""
    exe = shutil.which("claude")
    if not exe:
        return False, "claude CLI no esta en PATH"
    entorno = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    try:
        r = subprocess.run([exe, "-p", prompt, "--model", "opus",
                            "--permission-mode", "acceptEdits"],
                           cwd=ruta, capture_output=True, text=True,
                           timeout=timeout_seg, env=entorno)
    except subprocess.TimeoutExpired:
        return False, "timeout de %ds" % timeout_seg
    except OSError as error:
        return False, "no arranco: %s" % error
    return r.returncode == 0, "rc=%d" % r.returncode


def tirada(rondas, timeout_seg):
    """Agentes REALES escribiendo, y `converge` mirando. Gasta cuota.

    Presupuesto escrito antes: `rondas` x 2 agentes x `timeout_seg`.

    Y la calibracion, dicha antes de ver nada: con una tasa base publicada del
    5-10%, cuatro rondas tienen ~70% de no ver nada AUNQUE el fenomeno sea real.
    Por eso las tareas tocan un contrato compartido —es lo que pasa de verdad
    cuando dos agentes trabajan a la vez— y por eso un cero aqui NO se leera como
    "no ocurre", sino como "no lo vi en N rondas", que es otra frase.
    """
    print("presupuesto: %d ronda(s) x 2 agentes, tope %ds cada uno\n"
          % (rondas, timeout_seg), flush=True)
    vistos = 0
    for ronda in range(1, rondas + 1):
        _, ramas = genera(sembrar=False)   # los agentes escriben, no yo
        for (nombre, prompt), ruta in zip(TAREAS, ramas):
            ok, motivo = _agente(ruta, prompt, timeout_seg)
            if not ok:
                print("  ronda %d  %s NO CORRIO (%s)" % (ronda, nombre, motivo), flush=True)
        informe = corre()
        ramas_v = {r["nombre"]: r["veredicto"] for r in informe.get("ramas") or []}
        union = (informe.get("union") or {}).get("veredicto")
        choque = informe.get("choque_semantico")
        vistos += 1 if choque else 0
        print("  ronda %d  ramas=%s union=%s  choque=%s"
              % (ronda, {k: ("ok" if v == 0 else "ROJA") for k, v in sorted(ramas_v.items())},
                 "ok" if union == 0 else "ROJA", "SI" if choque else "no"), flush=True)
        limpia()
    print("\n=== CHOQUES SEMANTICOS VISTOS: %d de %d rondas ===" % (vistos, rondas))
    if not vistos:
        print("  cero en %d rondas NO es 'no ocurre': con tasa base del 5-10%%," % rondas)
        print("  esta muestra no puede distinguir una cosa de la otra.")
    return vistos


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
    p.add_argument("--agentes", action="store_true",
                   help="agentes REALES (claude -p, Opus): GASTA CUOTA")
    p.add_argument("--rondas", type=int, default=4, help="rondas de 2 agentes (por defecto 4)")
    p.add_argument("--timeout", type=int, default=300, help="tope por agente en segundos")
    args = p.parse_args()
    if args.limpiar:
        limpia()
        raise SystemExit(0)
    if args.agentes:
        tirada(args.rondas, args.timeout)
        raise SystemExit(0)
    raise SystemExit(main())
