"""La escalera: el modelo construye, el grafo juzga, y solo se sube si hay hecho.

Tres peldaños, y cada uno **añade un HECHO determinista, nunca una instrucción**.
Es la única forma que este proyecto tiene medida: la información inyectada se
ignoró 12/12; el rechazo determinista corrigió 4/4.

    0  la tarea
    1  la tarea + el rechazo exacto (qué llamante, qué símbolo, fichero:línea)
    2  la tarea anclada al nodo, con el alcance recortado a él y sus llamantes
    3  para — el diff y el worktree son tuyos

La condición de parada no es un contador: **se para cuando dos peldaños seguidos
producen el mismo rechazo**. Eso es un hecho (el modelo no converge) y no una
cuota arbitraria.

Y el veredicto de aceptar sin que nadie lo mire tiene una regla por encima de
todas: **auto-aceptar exige que la ley cubra la zona tocada**. Si el cambio toca
un módulo que ninguna regla menciona, "cero violaciones" no significa correcto —
significa *sin reglas que violar*. Es la misma trampa que una lista de permitidos
vacía, a nivel de arquitectura y con consecuencias peores. Ahí se escala al
humano, siempre.

NUNCA mergea (ADR 0006 y la regla de trabajo): decide ACEPTAR, RECHAZAR o
ESCALAR, y deja el diff donde está.
"""

import json
import os
import subprocess
import sys

ACEPTAR = "aceptar"
RECHAZAR = "rechazar"
ESCALAR = "escalar"

GB = [sys.executable, "-m", "galaxybrain.cli"]


def _corre(cmd, cwd, timeout=1800):
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return 1, ""
    return p.returncode, p.stdout.decode("utf-8", "replace")


def _json(cmd, cwd):
    rc, salida = _corre(cmd, cwd)
    texto = salida.strip()
    if not texto.startswith("{"):
        return None
    try:
        return json.loads(texto)
    except ValueError:
        return None


def _modulos_del_diff(worktree, raiz):
    """Los módulos que el diff toca, por sus ficheros. Vacío si no se puede leer
    el diff — y `decidir` escala ante una lista vacía, que es lo correcto: sin
    saber qué toca el cambio no se puede afirmar que la ley lo cubre."""
    from galaxybrain import graph as g

    rc, salida = _corre(["git", "diff", "--name-only", "HEAD"], worktree, timeout=120)
    if rc != 0:
        return []
    modulos = set()
    for rel in salida.splitlines():
        rel = rel.strip()
        if not rel:
            continue
        entero = os.path.abspath(os.path.join(worktree, rel))
        try:
            if os.path.relpath(entero, raiz).startswith(".."):
                continue          # fuera del alcance analizado
        except ValueError:        # otra unidad de disco en Windows
            continue
        nombre = g.module_name(entero, raiz)
        if nombre:
            modulos.add(nombre)
    return sorted(modulos)


def hechos_del_arbol(worktree, alcance=None, correr_tests=True):
    """Los hechos que `decidir` necesita, derivados del worktree con gb.

    Todo sale de un comando determinista: nada aquí pregunta a un modelo y nada
    se infiere. Lo que no se pueda derivar se deja como `None` o vacío — y
    `decidir` trata `None` como "no comprobado", que escala, jamás como verde.
    """
    raiz = os.path.join(worktree, alcance) if alcance else worktree
    hechos = {
        "tests_verdes": None, "suite_entera": True, "ciclos_nuevos": [],
        "cruces_frontera": [], "cruces_superficie": [], "llamantes_huerfanos": [],
        "modulos_tocados": [], "modulos_sin_regla": [],
    }

    grafo = _json(GB + ["graph", raiz, "--json"], worktree)
    if grafo:
        hechos["ciclos_nuevos"] = grafo.get("new_cycles") or grafo.get("cycles") or []
        hechos["cruces_frontera"] = grafo.get("violations") or []
        hechos["cruces_superficie"] = grafo.get("surface_violations") or []
        hechos["modulos_sin_regla"] = grafo.get("modulos_sin_regla") or []

    seleccion = _json(GB + ["tests", "--worktree", "--json", raiz], worktree)
    if seleccion:
        hechos["suite_entera"] = bool(seleccion.get("todo"))
    # Los modulos tocados salen de los FICHEROS del diff, no de los simbolos: un
    # import anadido es codigo a nivel de modulo y no cae dentro de ninguna
    # funcion, asi que derivarlo de los simbolos dejaba la lista vacia y hacia
    # escalar cambios perfectamente normales.
    hechos["modulos_tocados"] = _modulos_del_diff(worktree, raiz)
    if correr_tests:
        rc, _ = _corre(GB + ["tests", "--worktree", "--run", raiz], worktree)
        hechos["tests_verdes"] = rc == 0
    return hechos


def decidir(hechos):
    """(veredicto, motivo) a partir de HECHOS, sin modelo y sin opinión.

    `hechos` es un dict plano y todo lo que mira es comprobable:

        tests_verdes      bool o None   None = no se pudieron correr
        suite_entera      bool          True si no se estrechó la selección
        ciclos_nuevos     lista
        cruces_frontera   lista
        cruces_superficie lista
        llamantes_huerfanos lista
        modulos_tocados   lista
        modulos_sin_regla lista         los que NINGUNA regla menciona

    El orden importa y no es estético: primero lo que hace imposible juzgar
    (ESCALAR), después lo que es un fallo demostrado (RECHAZAR). Un cambio que
    rompe una frontera Y toca zona sin ley se rechaza — el fallo demostrado gana,
    porque ahí sí hay algo que decir.
    """
    ciclos = hechos.get("ciclos_nuevos") or []
    frontera = hechos.get("cruces_frontera") or []
    superficie = hechos.get("cruces_superficie") or []
    huerfanos = hechos.get("llamantes_huerfanos") or []
    verdes = hechos.get("tests_verdes")

    if verdes is False:
        return RECHAZAR, "los tests estan en rojo"
    if ciclos:
        return RECHAZAR, "ciclo de imports nuevo: %s" % " <-> ".join(ciclos[0])
    if frontera:
        v = frontera[0]
        return RECHAZAR, "cruce de frontera: %s -> %s" % (v.get("importer"), v.get("imported"))
    if superficie:
        v = superficie[0]
        return RECHAZAR, ("superficie publica: %s entra a %s por un simbolo interno"
                          % (v.get("caller"), v.get("callee")))
    if huerfanos:
        return RECHAZAR, "firma cambiada con %d llamante(s) sin actualizar: %s" % (
            len(huerfanos), huerfanos[0])

    # A partir de aqui NO hay ningun fallo demostrado. La pregunta deja de ser
    # "¿esta mal?" y pasa a ser "¿he podido comprobarlo?".
    if verdes is None:
        return ESCALAR, "no se pudieron correr los tests: sin veredicto que aceptar"

    sin_ley = sorted(set(hechos.get("modulos_tocados") or [])
                     & set(hechos.get("modulos_sin_regla") or []))
    if sin_ley:
        return ESCALAR, ("%s sin ninguna regla que lo mencione: aqui 'cero violaciones' "
                         "no es un aprobado, es que no hubo examen" % ", ".join(sin_ley[:3]))
    if not hechos.get("modulos_tocados"):
        return ESCALAR, "no se pudo derivar que modulos toca el cambio"

    detalle = "suite entera" if hechos.get("suite_entera") else "seleccion del grafo"
    return ACEPTAR, "tests verdes (%s), sin ciclos, sin cruces y con la ley cubriendo lo tocado" % detalle


def mismo_rechazo(a, b):
    """¿Dos peldaños produjeron el MISMO rechazo? Es la condición de parada, y es
    un hecho —el modelo no converge— en vez de una cuota de reintentos."""
    return bool(a) and a == b


def escalon(n, tarea, rechazo=None, ancla=None):
    """El prompt del peldaño `n`. Cada uno añade un hecho, nunca una orden.

    Se evita a propósito el lenguaje imperativo ("corrige", "asegúrate de"): lo
    que mueve al modelo, medido, es el hecho que le contradice — no la insistencia.
    """
    if n == 0 or not rechazo:
        return tarea
    bloques = [tarea, "LO QUE EL GRAFO ENCONTRO EN TU INTENTO ANTERIOR:\n- " + rechazo]
    if n >= 2 and ancla:
        bloques.append(
            "ALCANCE: trabaja sobre %s (%s:%s). Sus llamantes son:\n%s"
            % (ancla["symbol"]["qual"], ancla["symbol"]["file"], ancla["symbol"]["line"],
               "\n".join("  - %s (%s:%s)" % (c["qual"], c["file"], c["line"])
                         for c in ancla["callers"][:10]) or "  (ninguno)"))
    return "\n\n".join(bloques)
