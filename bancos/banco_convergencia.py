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

    python bancos/banco_convergencia.py                          # controles, gratis
    python bancos/banco_convergencia.py --agentes --pareja firma # agentes: GASTA CUOTA
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

#: Cada pareja es una CLASE de choque distinta. Las dos tareas son independientes,
#: plausibles, y ninguna sabe de la otra — la condicion de la vida real. NO se les
#: pide chocar: trabajo normal sobre un contrato compartido, y si el choque
#: aparece es porque aparece. `siembra_*` es el CONTROL (lo que escribiria un
#: agente tipico, a mano y gratis) y `choque_esperado` la prediccion ESCRITA
#: ANTES de correr nada. Para 'contrato' es False A PROPOSITO: el choque existe
#: pero ningun test lo pisa — que el control lo confirme es lo que declara el
#: techo del detector (converge solo ve lo que algun test corre).
PAREJAS = {
    # Escala numerica del contrato (euros -> centimos). Medida con agentes
    # reales el 13-ago: 4/4 rondas vistas (libreta).
    "escala": {
        "base_extra": {},
        "choque_esperado": True,
        "siembra_a": {
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
        },
        "siembra_b": {
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
        },
        "tareas": (
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
        ),
    },
    # Renombre de un simbolo publico: la referencia del otro agente queda
    # COLGANTE — sin nodo del que subir, la seleccion de la union no llegaba al
    # test de B y daba VERDE con un ImportError dentro. Este control lo destapo
    # el 13-ago-2026 ANTES de gastar un agente; el arreglo (aislado._union:
    # los nuevos entran al indice con -N) quedo fijado en test_aislado.
    "firma": {
        "base_extra": {},
        "choque_esperado": True,
        "siembra_a": {
            "tienda/precio.py": (
                '"""Precio unitario, EN EUROS."""\n\n\n'
                "def precio_unitario(articulo):\n"
                "    return {'pan': 2}.get(articulo, 0)\n"
            ),
            "tienda/carrito.py": (
                "from tienda.precio import precio_unitario\n\n\n"
                "def total(articulos):\n"
                "    return sum(precio_unitario(a) for a in articulos)\n"
            ),
        },
        "siembra_b": {
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
        },
        "tareas": (
            ("agente-a",
             "En `tienda/precio.py` renombra `precio()` a `precio_unitario()` — el "
             "nombre actual es ambiguo. Adapta todos los usos que encuentres. Corre "
             "`python -m pytest tests/` antes de terminar. No commitees."),
            ("agente-b",
             "Anade `tienda/informe.py` con una funcion `linea(articulo)` que devuelva "
             "'total: N euros' usando el precio del articulo, y su test en "
             "`tests/test_informe.py`. Corre `python -m pytest tests/` antes de terminar. "
             "No commitees."),
        ),
    },
    # Formato de un texto compartido. La prediccion lleva condicion: el choque
    # solo es visible si el test de B cruza el contrato (llama a etiqueta() de
    # verdad). El control siembra ESE caso; con agentes reales lo que se mide es
    # justo si testean a traves del contrato o contra un literal congelado.
    "formato": {
        "base_extra": {
            "tienda/etiqueta.py": (
                "from tienda.precio import precio\n\n\n"
                "def etiqueta(articulo):\n"
                "    return '%s: %d EUR' % (articulo, precio(articulo))\n"
            ),
            "tests/test_etiqueta.py": (
                "from tienda.etiqueta import etiqueta\n\n\n"
                "def test_etiqueta():\n"
                "    assert etiqueta('pan') == 'pan: 2 EUR'\n"
            ),
        },
        "choque_esperado": True,
        "siembra_a": {
            "tienda/etiqueta.py": (
                "from tienda.precio import precio\n\n\n"
                "def etiqueta(articulo):\n"
                "    return '%d EUR - %s' % (precio(articulo), articulo)\n"
            ),
            "tests/test_etiqueta.py": (
                "from tienda.etiqueta import etiqueta\n\n\n"
                "def test_etiqueta():\n"
                "    assert etiqueta('pan') == '2 EUR - pan'\n"
            ),
        },
        "siembra_b": {
            "tienda/inventario.py": (
                "def nombre_de(linea):\n"
                "    return linea.split(': ')[0]\n"
            ),
            "tests/test_inventario.py": (
                "from tienda.etiqueta import etiqueta\n"
                "from tienda.inventario import nombre_de\n\n\n"
                "def test_nombre():\n"
                "    assert nombre_de(etiqueta('pan')) == 'pan'\n"
            ),
        },
        "tareas": (
            ("agente-a",
             "En `tienda/etiqueta.py` el formato de `etiqueta()` cambia de "
             "'articulo: N EUR' a 'N EUR - articulo' (peticion de diseno). Adapta lo "
             "que haga falta. Corre `python -m pytest tests/` antes de terminar. No "
             "commitees."),
            ("agente-b",
             "Anade `tienda/inventario.py` con una funcion `nombre_de(linea)` que, "
             "dada una linea producida por `tienda.etiqueta.etiqueta()`, devuelva el "
             "nombre del articulo, y su test en `tests/test_inventario.py`. Corre "
             "`python -m pytest tests/` antes de terminar. No commitees."),
        ),
    },
    # Contrato de comportamiento (0 -> KeyError en desconocidos), disenado para
    # ser INVISIBLE: B solo pisa el camino feliz, asi que la union queda verde
    # con el choque dentro. Si este control dijera choque=SI, o el detector
    # cambio o la comprension del detector esta mal — se investiga.
    "contrato": {
        "base_extra": {},
        "choque_esperado": False,
        "siembra_a": {
            "tienda/precio.py": (
                '"""Precio unitario, EN EUROS. Lanza KeyError si no existe."""\n\n\n'
                "def precio(articulo):\n"
                "    return {'pan': 2}[articulo]\n"
            ),
        },
        "siembra_b": {
            "tienda/stock.py": (
                "from tienda.precio import precio\n\n\n"
                "def disponible(articulo):\n"
                "    return precio(articulo) > 0\n"
            ),
            "tests/test_stock.py": (
                "from tienda.stock import disponible\n\n\n"
                "def test_disponible():\n"
                "    assert disponible('pan')\n"
            ),
        },
        "tareas": (
            ("agente-a",
             "En `tienda/precio.py`, `precio()` devuelve 0 para articulos "
             "desconocidos y eso esconde errores: tiene que pasar a lanzar KeyError. "
             "Adapta lo que haga falta. Corre `python -m pytest tests/` antes de "
             "terminar. No commitees."),
            ("agente-b",
             "Anade `tienda/stock.py` con una funcion `disponible(articulo)` que "
             "devuelva True si el articulo tiene precio mayor que 0, y su test en "
             "`tests/test_stock.py`. Corre `python -m pytest tests/` antes de "
             "terminar. No commitees."),
        ),
    },
}


def _git(cwd, *args):
    return subprocess.run(["git"] + list(args), cwd=cwd, capture_output=True, text=True)


def _escribe(raiz, ficheros):
    for rel, cuerpo in ficheros.items():
        ruta = os.path.join(raiz, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, "w", encoding="utf-8", newline="") as fh:
            fh.write(cuerpo)


def genera(pareja, sembrar=True):
    """El repo base (mas el extra de la pareja) y dos worktrees, uno por 'agente'.

    `sembrar=True` escribe el trabajo de las dos ramas a mano: es el CONTROL, que
    comprueba la PREDICCION de la pareja — incluida la de 'contrato', cuyo choque
    NO debe verse.

    `sembrar=False` deja los worktrees LIMPIOS, que es lo unico valido cuando
    escriben agentes de verdad. Sembrar y luego lanzar agentes encima seria
    fabricar el conflicto y llamarlo hallazgo — el experimento no mediria si
    ocurre, solo que yo se escribirlo.
    """
    shutil.rmtree(BASE, ignore_errors=True)
    os.makedirs(BASE, exist_ok=True)
    _escribe(BASE, MODULOS)
    _escribe(BASE, pareja["base_extra"])
    _git(BASE, "init", "-q")
    _git(BASE, "config", "user.email", "b@b")
    _git(BASE, "config", "user.name", "b")
    _git(BASE, "add", "-A")
    _git(BASE, "commit", "-qm", "base")

    ramas = []
    for nombre, siembra in (("agente-a", pareja["siembra_a"]),
                            ("agente-b", pareja["siembra_b"])):
        ruta = os.path.join(BASE, ".worktrees", nombre)
        _git(BASE, "worktree", "add", "-q", "--detach", ruta, "HEAD")
        if sembrar:
            _escribe(ruta, siembra)
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


def tirada(rondas, timeout_seg, nombre, pareja):
    """Agentes REALES escribiendo la pareja elegida, y `converge` mirando. Gasta cuota.

    Presupuesto escrito antes: `rondas` x 2 agentes x `timeout_seg`.

    Lo que mide (calibrado por la tirada del 13-ago, 4/4 con 'escala'): estas
    tareas ponen el contrato compartido en el camino critico, asi que el numero
    NO es la tasa base del fenomeno — es DETECCION cuando el choque existe, y en
    'formato', ADEMAS, si los agentes testean a traves del contrato o contra un
    literal congelado (solo lo primero hace visible el choque). Un cero se lee
    "no lo vi en N rondas", nunca "no ocurre".
    """
    print("pareja '%s' — presupuesto: %d ronda(s) x 2 agentes, tope %ds cada uno\n"
          % (nombre, rondas, timeout_seg), flush=True)
    vistos = 0
    for ronda in range(1, rondas + 1):
        _, ramas = genera(pareja, sembrar=False)   # los agentes escriben, no yo
        for (quien, prompt), ruta in zip(pareja["tareas"], ramas):
            ok, motivo = _agente(ruta, prompt, timeout_seg)
            if not ok:
                print("  ronda %d  %s NO CORRIO (%s)" % (ronda, quien, motivo), flush=True)
        informe = corre()
        ramas_v = {r["nombre"]: r["veredicto"] for r in informe.get("ramas") or []}
        union = (informe.get("union") or {}).get("veredicto")
        choque = informe.get("choque_semantico")
        vistos += 1 if choque else 0
        print("  ronda %d  ramas=%s union=%s  choque=%s"
              % (ronda, {k: ("ok" if v == 0 else "ROJA") for k, v in sorted(ramas_v.items())},
                 "ok" if union == 0 else "ROJA", "SI" if choque else "no"), flush=True)
        limpia()
    print("\n=== CHOQUES SEMANTICOS VISTOS: %d de %d rondas (pareja '%s') ===" % (vistos, rondas, nombre))
    if not vistos:
        print("  cero en %d rondas NO es 'no ocurre': o no aparecio, o aparecio y" % rondas)
        print("  ningun test lo piso — 'contrato' existe para distinguir esas dos frases.")
    return vistos


def control(nombre, pareja):
    """La pareja sembrada a mano, gratis. Comprueba la PREDICCION, no 'detecta':
    para 'contrato' cumplir es que el choque NO se vea."""
    genera(pareja)
    try:
        informe = corre()
    finally:
        limpia()
    ramas = {r["nombre"]: r["veredicto"] for r in informe.get("ramas") or []}
    union = (informe.get("union") or {}).get("veredicto")
    choque = bool(informe.get("choque_semantico"))
    esperado = pareja["choque_esperado"]
    verdes = bool(ramas) and all(v == 0 for v in ramas.values())
    cumple = verdes and choque == esperado
    print("  %-9s ramas=%s union=%s  choque=%s esperado=%s  -> %s"
          % (nombre, {k: ("ok" if v == 0 else "ROJA") for k, v in sorted(ramas.items())},
             "ok" if union == 0 else "ROJA", "SI" if choque else "no",
             "SI" if esperado else "no", "CUMPLE" if cumple else "NO CUMPLE"))
    return cumple


def main(nombres):
    print("=== BANCO DE CONVERGENCIA — controles sembrados (gratis) ===")
    fallos = [n for n in nombres if not control(n, PAREJAS[n])]
    if fallos:
        print("\nNO CUMPLEN SU PREDICCION: %s — o el detector cambio o la prediccion"
              " estaba mal; se investiga ANTES de gastar agentes" % ", ".join(fallos))
    else:
        print("\ntodas las parejas cumplen su prediccion — incluido el NO-visto de"
              " 'contrato', que declara el techo: converge solo ve lo que algun test pisa")
    return 1 if fallos else 0


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--limpiar", action="store_true", help="quitar los worktrees y salir")
    p.add_argument("--agentes", action="store_true",
                   help="agentes REALES (claude -p, Opus): GASTA CUOTA")
    p.add_argument("--pareja", choices=sorted(PAREJAS), default=None,
                   help="que pareja; sin ella el control corre TODAS y --agentes usa 'escala'")
    p.add_argument("--rondas", type=int, default=4, help="rondas de 2 agentes (por defecto 4)")
    p.add_argument("--timeout", type=int, default=300, help="tope por agente en segundos")
    args = p.parse_args()
    if args.limpiar:
        limpia()
        raise SystemExit(0)
    if args.agentes:
        nombre = args.pareja or "escala"
        tirada(args.rondas, args.timeout, nombre, PAREJAS[nombre])
        raise SystemExit(0)
    raise SystemExit(main([args.pareja] if args.pareja else sorted(PAREJAS)))
