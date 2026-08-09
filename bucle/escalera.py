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

Y la pregunta que cierra el circulo: **¿cuándo termina?** El grafo sabe decir si
un cambio es aceptable; no puede decir nunca si el trabajo está hecho — eso no es
una propiedad del código, es de tu intención, y por eso esa capa del suelo jamás
se marca en verde. Lo que sí se puede cerrar es la mitad ejecutable: si el
criterio de terminado está escrito como COMANDO (valla ```gb:terminado en el
SCOPE), se corre, y entonces sí es un hecho. Sin él, el veredicto máximo es
SIN_OBJECIONES — que es lo único que de verdad se ha comprobado.

NUNCA mergea (ADR 0006 y la regla de trabajo): decide, y deja el diff donde está.
"""

import json
import os
import subprocess
import sys

ACEPTAR = "aceptar"
#: Lo que de verdad comprueba el grafo cuando no hay criterio de terminado: que
#: nada de lo que sabe mirar esta roto. NO es "la tarea esta hecha" — eso no es
#: una propiedad del codigo, es de tu intencion, y confundirlas seria dar un
#: veredicto sobre lo que no se ha mirado. El nombre no promete de mas.
SIN_OBJECIONES = "sin-objeciones"
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
        "cruces_frontera": [], "cruces_llamada": [], "cruces_superficie": [],
        "llamantes_huerfanos": [],
        "modulos_tocados": [], "modulos_sin_regla": [],
        "criterio_pasa": None, "criterio_detalle": "",
    }

    grafo = _json(GB + ["graph", raiz, "--json"], worktree)
    if grafo:
        hechos["ciclos_nuevos"] = grafo.get("new_cycles") or grafo.get("cycles") or []
        hechos["cruces_frontera"] = grafo.get("violations") or []
        hechos["cruces_llamada"] = grafo.get("call_violations") or []
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
        # rc 3 = NO SE PUDO comprobar (sin comando de tests declarado). Eso NO es
        # rojo: `decidir` trata None como "no comprobado" y escala, que es lo
        # correcto. Meterlo en el mismo saco que un fallo real produciria el
        # veredicto falso que esta tirada destapo — "los tests estan en rojo"
        # sobre un proyecto cuyos tests nadie llego a correr.
        hechos["tests_verdes"] = None if rc == 3 else rc == 0
        # El criterio de terminado del PROYECTO, declarado en su SCOPE con la
        # valla ```gb:terminado. Sin el, `decidir` no puede decir ACEPTAR — solo
        # SIN_OBJECIONES, que es lo que de verdad ha comprobado.
        from galaxybrain import floor
        hechos["criterio_pasa"], hechos["criterio_detalle"] = floor.correr_criterio(worktree)
    return hechos


def decidir(hechos):
    """(veredicto, motivo) a partir de HECHOS, sin modelo y sin opinión.

    `hechos` es un dict plano y todo lo que mira es comprobable:

        tests_verdes      bool o None   None = no se pudieron correr
        suite_entera      bool          True si no se estrechó la selección
        ciclos_nuevos     lista
        cruces_frontera   lista         la misma regla, vista en los IMPORTS
        cruces_llamada    lista         ...y vista en las LLAMADAS
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
    llamada = hechos.get("cruces_llamada") or []
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
    if llamada:
        v = llamada[0]
        return RECHAZAR, "cruce de frontera por LLAMADA: %s -> %s" % (
            v.get("caller"), v.get("callee"))
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
    limpio = ("tests verdes (%s), sin ciclos, sin cruces y con la ley cubriendo lo tocado"
              % detalle)

    # El ultimo escalon, y el que separa "no rompiste nada" de "esta hecho". Que
    # la tarea este terminada NO es una propiedad del codigo: es de tu intencion,
    # y ninguna herramienta la juzga. Pero si la escribiste como COMANDO
    # (`gb floor` la llama criterio de terminado ejecutable), se puede correr — y
    # entonces si es un hecho.
    criterio = hechos.get("criterio_pasa")
    if criterio is True:
        return ACEPTAR, "%s; y el criterio de terminado PASA" % limpio
    if criterio is False:
        return RECHAZAR, "el criterio de terminado no pasa: la tarea no esta hecha"
    return SIN_OBJECIONES, ("%s — pero no hay criterio de terminado ejecutable, asi que "
                            "nadie ha comprobado si la tarea esta HECHA" % limpio)


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
