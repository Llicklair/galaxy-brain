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


def _ley_incomprobable(grafo):
    """Motivos por los que la comprobacion de fronteras NO esta comprobando nada.

    `gb graph --gate` bloquea SIEMPRE ante esto y no lo trata como un cruce: un
    fichero de reglas ilegible, una linea mal escrita, una regla que no casa con
    ningun modulo (typo, o el analisis apuntando a otra raiz) o un arbol donde no
    quedo ni un modulo que mirar. En todos esos casos salen cero violaciones — y
    el cero significa "no he mirado", no "esta limpio". Es el peor modo de fallo
    que puede tener una gate, porque el verde se lee como comprobado.

    La escalera no lo miraba, asi que un cambio que rompiese el propio fichero de
    reglas —o que dejase el analisis apuntando a un arbol vacio— salia ACEPTADO
    con la ley entera sin aplicar. Tercera media conexion del mismo tipo hallada
    hoy (9-ago), y por eso ahora se derivan las dos listas del MISMO informe.

    No rechaza: no se puede saber quien rompio la configuracion, y el veredicto
    honesto ante "no he podido comprobarlo" es ESCALAR.
    """
    motivos = []
    if grafo.get("root_error"):
        motivos.append("la raiz analizada da error: %s" % grafo["root_error"])
    elif not grafo.get("modules"):
        motivos.append("el analisis no encontro ni un modulo que mirar")
    if grafo.get("boundaries_error"):
        motivos.append("no se pudo leer el fichero de reglas: %s" % grafo["boundaries_error"])
    if grafo.get("malformed_boundaries"):
        motivos.append("regla(s) mal escritas: %s"
                       % ", ".join(str(r) for r in grafo["malformed_boundaries"][:3]))
    if grafo.get("unmatched_rules"):
        motivos.append("regla(s) que no casan con ningun modulo (typo o raiz equivocada): %s"
                       % ", ".join(str(r) for r in grafo["unmatched_rules"][:3]))
    if grafo.get("boundaries_elsewhere"):
        motivos.append("hay otro fichero de reglas que NO se esta aplicando: %s"
                       % grafo["boundaries_elsewhere"])
    return motivos


def _simbolos_preexistentes(raiz):
    """Los símbolos que YA EXISTÍAN y este cambio ha modificado.

    Es el hecho que faltaba tras la tirada del 9-ago: ante un rechazo, dos de
    tres agentes hicieron desaparecer la violación tocando código que nadie les
    pidió tocar. No rechaza —modificar lo que existe es trabajo normal—, viaja al
    peldaño siguiente y se dice en el veredicto.

    Vacío si no se puede derivar: callar es el lado seguro, y aquí callar no
    aprueba nada porque el veredicto no depende de esto.
    """
    # Los simbolos se piden a `gb`, no a `symbols.analyze`: el despacho de motor
    # por lenguaje vive en la CLI, y llamar al de Python directamente dejaria
    # este hecho mudo en los 16 lenguajes que no son Python.
    informe = _json(GB + ["symbols", raiz, "--json"], raiz)
    if not informe:
        return []
    try:
        from galaxybrain import impacted

        nodes = {n["qual"]: n for n in informe.get("nodes", []) if n.get("qual")}
        if not nodes:
            return []
        tocados = impacted._simbolos_tocados(nodes, impacted.rangos_del_diff(raiz))
        if not tocados:
            return []
        base = _simbolos_de_la_base(raiz, {nodes[q].get("file") for q in tocados})
        return sorted(q for q in tocados if q in base) if base is not None else []
    except Exception:
        return []


def _simbolos_de_la_base(raiz, ficheros):
    """Los símbolos que existían en HEAD, en los ficheros que el diff toca.

    `None` si no se puede saber — y entonces no se acusa a nadie.

    Primero se intentó deducirlo del propio diff: un símbolo sería nuevo si todo
    su cuerpo cayera en líneas añadidas. **No funciona**, y lo destapó la tirada
    del 9-ago con una función recién creada: git alineó la llave de cierre de la
    función NUEVA con la de la función vieja y la dejó como contexto, así que el
    cuerpo asomaba una línea fuera del hunk y el símbolo salía acusado de
    preexistente. La alineación de un diff es una heurística de presentación y no
    dice qué existía; preguntarle eso es usar un proxy donde hace falta un hecho.

    Se saca de git, que sí lo sabe: la versión en HEAD de esos ficheros —solo
    esos— extraída aparte y pasada por el mismo motor. Las rutas relativas se
    conservan para que los nombres de módulo salgan idénticos y los `qual` se
    puedan comparar.
    """
    import shutil
    import tempfile

    relativos = sorted(f.replace("\\", "/") for f in ficheros if f)
    if not relativos:
        return set()
    tmp = tempfile.mkdtemp(prefix="gb-base-")
    try:
        escritos = 0
        for rel in relativos:
            rc, contenido = _corre(["git", "show", "HEAD:./%s" % rel], raiz, timeout=120)
            if rc != 0:
                continue          # no estaba en HEAD: es un fichero nuevo entero
            destino = os.path.join(tmp, *rel.split("/"))
            os.makedirs(os.path.dirname(destino), exist_ok=True)
            with open(destino, "w", encoding="utf-8", errors="replace") as fh:
                fh.write(contenido)
            escritos += 1
        if not escritos:
            return set()
        informe = _json(GB + ["symbols", tmp, "--json"], tmp)
        if not informe:
            return None
        return {n["qual"] for n in informe.get("nodes", []) if n.get("qual")}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _modulos_del_diff(worktree, raiz):
    """Los módulos que el diff toca, por sus ficheros. Vacío si no se puede leer
    el diff — y `decidir` escala ante una lista vacía, que es lo correcto: sin
    saber qué toca el cambio no se puede afirmar que la ley lo cubre."""
    from galaxybrain import graph as g

    rc, salida = _corre(["git", "diff", "--name-only", "HEAD"], worktree, timeout=120)
    if rc != 0:
        return []
    # Los ficheros NUEVOS no estan en el diff contra HEAD: git no los conoce
    # todavia. Y anadir codigo en un fichero nuevo es la forma mas normal que
    # tiene un agente de anadir codigo, asi que sin esto el hecho "que modulos
    # toca el cambio" se salta justo lo que acaba de aparecer. Medido el 9-ago:
    # un agente extrajo la logica compartida a un `suma.js` nuevo —la solucion
    # BUENA— y ese modulo, que ninguna regla menciona, no llego a la
    # comprobacion de cobertura: se acepto sin el ESCALAR que tocaba. Es el mismo
    # caso que `actividad.simbolos_tocados` ya contemplaba por su cuenta.
    rc_nuevos, nuevos = _corre(["git", "ls-files", "--others", "--exclude-standard"],
                               worktree, timeout=120)
    if rc_nuevos == 0:
        salida += "\n" + nuevos
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
        "llamantes_huerfanos": [], "ley_incomprobable": [],
        "modulos_tocados": [], "modulos_sin_regla": [], "simbolos_preexistentes": [],
        "criterio_pasa": None, "criterio_detalle": "",
    }

    grafo = _json(GB + ["graph", raiz, "--json"], worktree)
    if grafo:
        hechos["ciclos_nuevos"] = grafo.get("new_cycles") or grafo.get("cycles") or []
        hechos["cruces_frontera"] = grafo.get("violations") or []
        hechos["cruces_llamada"] = grafo.get("call_violations") or []
        hechos["ley_incomprobable"] = _ley_incomprobable(grafo)
        hechos["cruces_superficie"] = grafo.get("surface_violations") or []
        hechos["modulos_sin_regla"] = grafo.get("modulos_sin_regla") or []
    else:
        # Sin informe no hay NADA comprobado, y las listas vacias de arriba se
        # leerian como "todo limpio". Es el mismo verde mudo, en su version total.
        hechos["ley_incomprobable"] = ["no se pudo obtener el grafo del arbol"]

    seleccion = _json(GB + ["tests", "--worktree", "--json", raiz], worktree)
    if seleccion:
        hechos["suite_entera"] = bool(seleccion.get("todo"))
    # Los modulos tocados salen de los FICHEROS del diff, no de los simbolos: un
    # import anadido es codigo a nivel de modulo y no cae dentro de ninguna
    # funcion, asi que derivarlo de los simbolos dejaba la lista vacia y hacia
    # escalar cambios perfectamente normales.
    hechos["modulos_tocados"] = _modulos_del_diff(worktree, raiz)
    hechos["simbolos_preexistentes"] = _simbolos_preexistentes(raiz)
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
    #
    # Y la primera de todas: ¿estaba la ley puesta? Cero cruces sobre un fichero
    # de reglas roto no es un aprobado — es que no hubo examen, igual que una
    # lista de permitidos vacia. Va ANTES que todo lo demas porque invalida las
    # comprobaciones de arriba: son ellas las que salieron vacias.
    ley = hechos.get("ley_incomprobable") or []
    if ley:
        return ESCALAR, ("la ley no se estaba comprobando: %s — sin eso, 'cero cruces' "
                         "no significa nada" % ley[0])
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
    # No cambia el veredicto: modificar codigo que existe es trabajo normal, y
    # gatearlo seria el proxy que fabrica el --no-verify (regla 9). Pero se DICE,
    # porque "aceptado" a secas escondia que el arreglo se habia llevado por
    # delante una funcion que nadie mando tocar.
    previos = hechos.get("simbolos_preexistentes") or []
    if previos:
        limpio += "; modifica %d simbolo(s) que ya existian: %s" % (
            len(previos), ", ".join(previos[:3]))

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


def escalon(n, tarea, rechazo=None, ancla=None, preexistentes=()):
    """El prompt del peldaño `n`. Cada uno añade un hecho, nunca una orden.

    Se evita a propósito el lenguaje imperativo ("corrige", "asegúrate de"): lo
    que mueve al modelo, medido, es el hecho que le contradice — no la insistencia.

    `preexistentes` son los símbolos que YA existían y el intento anterior tocó.
    Va sin juicio y sin pedir nada: en la tirada del 9-ago el rechazo empujó a dos
    de tres agentes a quitar la violación estropeando código que no se les pidió
    tocar, y ninguno lo mencionó. Enseñarle lo que acaba de mover es el hecho que
    le faltaba; decidir si estaba bien no es competencia de esta capa.
    """
    if n == 0 or not rechazo:
        return tarea
    bloques = [tarea, "LO QUE EL GRAFO ENCONTRO EN TU INTENTO ANTERIOR:\n- " + rechazo]
    if preexistentes:
        bloques.append(
            "Y ademas, tu intento anterior MODIFICO codigo que ya existia:\n%s"
            % "\n".join("  - %s" % q for q in preexistentes[:10]))
    if n >= 2 and ancla:
        bloques.append(
            "ALCANCE: trabaja sobre %s (%s:%s). Sus llamantes son:\n%s"
            % (ancla["symbol"]["qual"], ancla["symbol"]["file"], ancla["symbol"]["line"],
               "\n".join("  - %s (%s:%s)" % (c["qual"], c["file"], c["line"])
                         for c in ancla["callers"][:10]) or "  (ninguno)"))
    return "\n\n".join(bloques)
