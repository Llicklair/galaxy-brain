"""Quién está tocando qué, ahora mismo — derivado, no declarado.

Esto **no** es el `gb activity` que se descartó (docs/grafo-neuronal-orquestacion.md,
apartado 0). Aquel pedía a cada agente que anunciara su presencia con un comando, y
en cuanto uno se olvidaba, todo lo construido encima mentía con cara de hecho.

Aquí nadie declara nada: se lee el disco. **Un agente es un worktree** — esa es toda
la atribución que hace falta, y sale gratis porque la identidad del agente ya está en
la ruta donde trabaja. Si el agente muere a medias, su rastro sigue siendo cierto; si
nunca existió, no aparece.

Lo que se puede derivar y lo que no, dicho de frente:

- **Sí**: qué nodos ha tocado, hace cuánto, y a qué nodos se propaga por el grafo de
  llamadas (con quién «se comunica»).
- **No**: qué cree el agente que está haciendo. Su narrativa solo la tiene él, y
  pedírsela nos devolvería al registro declarado que ya se rechazó.
"""

import ast
import json
import os
import time

from . import aislado, changes, impacted
from . import graph as graph_mod
from . import symbols as symbols_mod

# El DEFINES es estructura (un módulo contiene una función), no comunicación. Para
# «con quién habla este nodo» solo cuentan las aristas de llamada.
ESTRUCTURA = ("DEFINES",)


def ficheros_tocados(root):
    """Los .py tocados respecto a HEAD: modificados, añadidos, renombrados o
    sin trackear, estén o no en el índice. Rutas absolutas.

    UNA fuente: `git status --porcelain` trae staged, unstaged y untracked en una
    pasada. Sin repo git devuelve lista vacía y la capa calla (regla 9).
    """
    salida = graph_mod._git(root, "status", "--porcelain")
    if not salida:
        return []
    toplevel = (graph_mod._git(root, "rev-parse", "--show-toplevel") or "").strip()
    base = toplevel or os.path.abspath(root)
    ficheros = []
    for linea in salida.splitlines():
        if len(linea) < 4:
            continue
        estado, ruta = linea[:2], linea[3:]
        if "D" in estado:
            continue  # borrado: ya no hay fichero, luego no hay nodo que marcar
        if " -> " in ruta:
            ruta = ruta.split(" -> ")[-1]
        ruta = ruta.strip().strip('"')
        # Las extensiones se DERIVAN de la tabla de lenguajes, no se escriben:
        # esto decia `.py` a secas y se quedo viejo el dia que entraron los otros
        # 16 motores — un agente trabajando en un .go no salia en el mapa. Tercera
        # vez que una lista paralela se desincroniza (9-ago); por eso ya no hay.
        if not ruta.endswith(changes.EXTENSIONES_FUENTE):
            continue
        ficheros.append(os.path.join(base, *ruta.split("/")))
    return ficheros


def simbolos_tocados(root, informe_simbolos):
    """Los SÍMBOLOS que el agente está editando ahora mismo, no solo sus ficheros.

    La capa de actividad razonaba en ficheros y paraba en el módulo: veías el
    módulo encenderse, nunca la función. La intersección hunk × `[line, end]` ya
    existía y estaba probada en dos sitios (`impacted._simbolos_tocados` y la
    onda del cambio); aquí se reutiliza en vez de escribir una tercera.

    Se queda con el símbolo MÁS INTERNO —tocar un método no enciende su clase
    entera— y devuelve `{}` sin git o sin diff legible: la capa calla hacia el
    lado seguro (regla 9), y el mapa sigue teniendo los módulos.

    Los ficheros sin trackear no tienen diff contra HEAD, así que sus símbolos
    entran ENTEROS: es cierto —el fichero es nuevo del todo— y no se inventa nada.
    """
    nodes = {n["qual"]: n for n in informe_simbolos.get("nodes", []) if n.get("qual")}
    if not nodes:
        return {}
    # `--relative` es obligatorio, no cosmetico: sin el, git da las rutas desde
    # el TOPLEVEL del repo (`src/galaxybrain/graph.py`) y los nodos las traen
    # desde la raiz analizada (`galaxybrain/graph.py`). No casaban, ningun hunk
    # entraba, y la capa encendia el fichero ENTERO — 47 simbolos por editar uno.
    rangos = impacted.rangos_del_diff(root)
    tocados = set(impacted._simbolos_tocados(nodes, rangos)) if rangos else set()

    # los nuevos sin trackear: el diff contra HEAD no los ve
    nuevos = {os.path.normcase(os.path.abspath(f)) for f in ficheros_tocados(root)}
    if nuevos:
        base = os.path.abspath(root)
        for qual, nodo in nodes.items():
            if nodo.get("kind") == "module" or not nodo.get("file"):
                continue
            entero = os.path.normcase(os.path.abspath(os.path.join(base, nodo["file"])))
            if entero in nuevos and not _tiene_diff(rangos, nodo["file"]):
                tocados.add(qual)
    return {q: nodes[q] for q in tocados if q in nodes}


#: Cuanto cuenta un commit como PRESENCIA: 600 s. La cifra nacio emparejada con
#: la onda del mapa (retirado el 13-ago-2026), porque eran la misma pregunta —
#: cuando alguien deja de estar "ahora" — y dos numeros habrian sido dos
#: verdades. El mapa se fue; la pregunta y su respuesta se quedan aqui.
VENTANA_COMMIT = 600


def commitados_recientes(root, informe_simbolos, ahora, ventana=VENTANA_COMMIT, base=""):
    """Los modulos que este arbol COMMITEO hace poco. `(nodos, hace_seg)`.

    La presencia salia solo del arbol sucio, y eso premia al reves: quien
    commitea a menudo es invisible y quien acumula brilla. Medido el 10-ago-2026
    — una sesion entera de trabajo real con el mapa apagado casi todo el rato,
    porque cada cambio se commiteaba en cuanto la medicion aguantaba.

    Un commit de hace veinte segundos ES presencia: la persona esta ahi. Lo que
    no es presencia es un commit de ayer, y de eso ya se encarga la ventana mas
    el envejecido del mapa. Asi que commitear deja de borrarte: te mueve de
    "sucio" a "recien commiteado", y las dos cosas son recientes.

    **Granularidad declarada: MODULO, no simbolo.** El arbol sucio da el simbolo
    exacto porque hay un diff contra HEAD que intersecar; para un rango de
    commits haria falta otra interseccion distinta, y colarla aqui seria
    construir una pieza nueva escondida dentro de esta. El mapa enciende el
    modulo y lo dice.

    `--relative` no es cosmetico: sin el, git da las rutas desde el toplevel del
    repo y los nodos las traen desde la raiz analizada. Es el mismo tropiezo que
    ya documenta `simbolos_tocados`, y por eso se escribe aqui tambien.
    """
    nodes = {n["qual"]: n for n in informe_simbolos.get("nodes", []) if n.get("qual")}
    if not nodes:
        return set(), None
    # `base..HEAD` cuando el arbol va por su cuenta: la historia es COMPARTIDA, y
    # sin acotarla el commit reciente de UNO enciende a todos los worktrees, que
    # nunca tocaron nada. Lo destapo un test que empezo a ver dos agentes donde
    # habia uno — el fixture commitea al montarse y ese commit lo tienen todos.
    # Sin base (el arbol raiz) se mira su propia historia, que ahi si es suya.
    rango = ["%s..HEAD" % base] if base else []
    salida = graph_mod._git(root, "log", *(rango + [
        "--since=%d.seconds.ago" % int(ventana),
        "--name-only", "--relative", "--format=%ct"]))
    if not salida:
        return set(), None

    rutas, reciente = set(), 0
    for linea in salida.splitlines():
        linea = linea.strip()
        if not linea:
            continue
        if linea.isdigit():
            reciente = max(reciente, int(linea))
            continue
        rutas.add(os.path.normcase(os.path.abspath(os.path.join(root, linea))))
    if not rutas:
        return set(), None

    tocados = set()
    for qual, nodo in nodes.items():
        ruta = nodo.get("file")
        if not ruta or nodo.get("kind") != "module":
            continue
        entero = os.path.normcase(os.path.abspath(os.path.join(root, ruta)))
        if entero in rutas:
            tocados.add(qual)
    hace = int(max(0, ahora - reciente)) if reciente else None
    return tocados, hace


def _tiene_diff(rangos, fichero):
    """¿Ese fichero aparece en el diff? Si sí, sus símbolos ya se decidieron por
    hunk y encenderlo entero seria mentir por exceso."""
    objetivo = os.path.normcase(fichero.replace("/", os.sep))
    return any(os.path.normcase(r.replace("/", os.sep)) == objetivo for r in rangos)


def nodos_tocados(root, informe_simbolos):
    """Los nodos módulo cuyo fichero está tocado sin commitear.

    El join es delicado en Windows ('c:' vs 'C:', separadores mezclados): los dos
    lados se comparan por normcase, nunca por igualdad literal.
    """
    modulos = {
        os.path.normcase(n.get("qual") or ""): n.get("qual")
        for n in informe_simbolos.get("nodes", [])
        if n.get("kind") == "module"
    }
    tocados = set()
    for fichero in ficheros_tocados(root):
        try:
            mod = graph_mod.module_name(fichero, root)
        except ValueError:  # otra unidad de disco en Windows
            continue
        qual = modulos.get(os.path.normcase(mod))
        if qual:
            tocados.add(qual)
    return tocados


def modulos_nacientes(root, informe_simbolos):
    """Los módulos que este árbol está CREANDO: ficheros .py tocados cuyo
    nombre de módulo aún no existe en el mapa canónico.

    El complemento exacto de nodos_tocados, con nombre propio: 'cuentas.top
    naciendo' dice más que '+1 fichero fuera del mapa' — sin esto, el agente
    que más construye es el más invisible (medido en la tirada de cuatro,
    14-ago). Mismo join delicado por normcase.
    """
    modulos = {
        os.path.normcase(n.get("qual") or "")
        for n in informe_simbolos.get("nodes", [])
        if n.get("kind") == "module"
    }
    nacientes = set()
    for fichero in ficheros_tocados(root):
        if not fichero.endswith(".py"):
            continue
        try:
            mod = graph_mod.module_name(fichero, root)
        except ValueError:  # otra unidad de disco en Windows
            continue
        if os.path.normcase(mod) not in modulos:
            nacientes.add(mod)
    return sorted(nacientes)


#: Tope de hechos por agente en la foto: la consola tiene que caber en un
#: vistazo, y un refactor masivo se resume, no se vuelca.
MAX_CAMBIOS = 20

#: Lineas de consola por agente en la foto. Mas de las que la terminal enseña
#: a la vez: el sobrante es el material de la lluvia — el mapa las revela de
#: una en una entre recargas para que la conversacion CAIGA, no salte.
MAX_CONSOLA = 40


def _ruta_consola(ruta):
    """Convencion con los orquestadores: la consola del agente (su stdout,
    teeado por quien lo lanza — el bucle lo hace) vive en `<worktree>.consola.log`,
    AL LADO del worktree para no ensuciar su git status."""
    return os.path.normpath(ruta).rstrip("\\/") + ".consola.log"


def consola_de(ruta, max_lineas=MAX_CONSOLA):
    """Las ultimas lineas de la consola del agente, si su orquestador la deja.
    Derivada del disco: si nadie la escribe, no hay terminal — y no se inventa
    narrativa, que es exactamente el registro declarado que se rechazo."""
    try:
        with open(_ruta_consola(ruta), encoding="utf-8", errors="replace") as fh:
            lineas = fh.read().splitlines()
    except OSError:
        return []
    return [ln for ln in lineas if ln.strip()][-max_lineas:]


def escalera_de(ruta):
    """El estado de la escalera de ese worktree, si su orquestador lo deja.

    Mismo contrato que la consola: se DERIVA del disco. Si nadie lo escribe, no
    hay escalera y no se inventa nada. Existe porque un bucle que decide aceptar
    codigo sin que nadie lo mire no puede ser una caja negra — lo que decide y
    por que tiene que estar delante, o la automatizacion se vuelve fe.
    """
    fichero = os.path.normpath(str(ruta).rstrip("\\/")) + ".escalera.json"
    try:
        with open(fichero, encoding="utf-8", errors="replace") as fh:
            datos = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(datos, dict) or not datos.get("peldanos"):
        return None
    return {
        "veredicto": datos.get("veredicto") or "",
        "motivo": (datos.get("motivo") or "")[:220],
        "ancla": datos.get("ancla") or "",
        "peldanos": [{"n": p.get("n"), "veredicto": p.get("veredicto"),
                      "motivo": (p.get("motivo") or "")[:160]}
                     for p in datos["peldanos"][-4:]],
    }


def cambios_de(analisis, ficheros, informe_simbolos):
    """QUÉ escribió exactamente: las firmas de los ficheros tocados del worktree
    contra el mapa canónico. El mismo hecho estrecho que deriva el bucle para
    enrutar («suma: (a, b) -> (a, b, extra)») — la consola habla el idioma de gb,
    no el de «última actividad hace 2s». Derivado del AST, nadie declara nada.

    Un fichero con sintaxis rota se dice ilegible (el agente está a medio
    escribir: es un hecho, no un error). Ficheros fuera del mapa canónico no
    salen aquí — ya los cuenta `fuera_del_mapa`.
    """
    modulos = {
        os.path.normcase(n.get("qual") or ""): n.get("qual")
        for n in informe_simbolos.get("nodes", [])
        if n.get("kind") == "module"
    }
    canon_por_modulo = {}
    for n in informe_simbolos.get("nodes", []):
        if n.get("qual") and n.get("kind") != "module":
            canon_por_modulo.setdefault(n.get("module") or "", {})[n["qual"]] = n.get("sig") or ""
    hechos = []
    for fichero in sorted(ficheros):
        try:
            mod = graph_mod.module_name(fichero, analisis)
        except ValueError:
            continue
        qual_canon = modulos.get(os.path.normcase(mod))
        if not qual_canon:
            continue
        try:
            with open(fichero, encoding="utf-8", errors="replace") as fh:
                arbol = ast.parse(fh.read())
        except OSError:
            continue
        except SyntaxError as error:
            hechos.append("%s: (ilegible ahora mismo: sintaxis rota en linea %s)"
                          % (qual_canon, error.lineno or "?"))
            continue
        info = symbols_mod._scan_module(mod, arbol, fichero.endswith("__init__.py"))
        nuevas = {
            (qual_canon + q[len(mod):] if mod != qual_canon else q): s
            for q, s in info["sigs"].items()
        }
        canon = canon_por_modulo.get(qual_canon, {})
        for q in sorted(set(canon) | set(nuevas)):
            a, b = canon.get(q), nuevas.get(q)
            if a != b:
                hechos.append("%s: %s -> %s" % (
                    q, "(no existia)" if a is None else (a or "()"),
                    "(borrado)" if b is None else (b or "()")))
    if len(hechos) > MAX_CAMBIOS:
        hechos = hechos[:MAX_CAMBIOS] + ["(+%d hecho(s) mas)" % (len(hechos) - MAX_CAMBIOS)]
    return hechos


def _mapa_de_modulos(informe_simbolos):
    """qual del símbolo -> módulo que lo contiene.

    Las aristas del grafo conectan SÍMBOLOS; la capa de cambio solo sabe de
    FICHEROS. Para cruzar las dos hay que subir cada extremo de la arista a su
    módulo, y el informe ya trae ese campo por nodo — no se deduce del prefijo del
    nombre, que fallaría con cualquier símbolo anidado.
    """
    return {
        n.get("qual"): (n.get("module") or n.get("qual"))
        for n in informe_simbolos.get("nodes", [])
        if n.get("qual")
    }


def _vecinos(informe_simbolos, nodos, de_modulo=None):
    """A qué otros módulos se propaga lo tocado: llamantes y llamados, un salto.

    Un salto y no la clausura entera a propósito: la consola de un agente tiene
    que caber en un vistazo. La onda completa ya la da `gb calls --depth N`.
    """
    if not nodos:
        return []
    de_modulo = _mapa_de_modulos(informe_simbolos) if de_modulo is None else de_modulo
    dentro = set(nodos)
    fuera = set()
    for arista in informe_simbolos.get("edges") or ():
        if len(arista) < 2:
            continue
        clase = arista[2] if len(arista) > 2 else ""
        if clase in ESTRUCTURA:
            continue
        mo = de_modulo.get(arista[0], arista[0])
        md = de_modulo.get(arista[1], arista[1])
        if mo == md:
            continue  # llamada dentro del mismo modulo: no es comunicacion
        if mo in dentro and md not in dentro:
            fuera.add(md)
        elif md in dentro and mo not in dentro:
            fuera.add(mo)
    return sorted(x for x in fuera if x)


def instantanea(raiz, informe_simbolos, ahora=None):
    """La foto de quién toca qué, ahora mismo, en todos los worktrees vivos.

    `raiz` es la ruta que se analizó para `informe_simbolos` (p. ej. `.../src`);
    de cada worktree se mira su ruta equivalente, para que los nodos casen con los
    del mapa canónico.

    **Lo que esto mide, dicho de frente: el árbol SUCIO, no el trabajo hecho.**
    La presencia sale de `git status`, así que un agente que commitea a menudo es
    casi invisible y uno que acumula sin commitear brilla mucho — al revés de lo
    que uno querría premiar. Se vio el 10-ago-2026: durante una sesión entera de
    trabajo real el mapa estuvo apagado casi todo el rato, porque cada cambio se
    commiteaba en cuanto la medición aguantaba.

    No se arregla mirando también lo commiteado: eso sería historia, no presencia,
    y el mapa dejaría de responder "¿quién está tocando esto AHORA?" — que es la
    única pregunta que esta capa contesta y que nadie más contesta. Queda escrito
    para que se lea el mapa por lo que dice y no por lo que parece.
    """
    ahora = time.time() if ahora is None else ahora
    foto = {"base": "", "agentes": [], "por_nodo": {}, "cruces": [], "motivo": ""}

    raiz = os.path.abspath(raiz)
    toplevel = (graph_mod._git(raiz, "rev-parse", "--show-toplevel") or "").strip()
    if not toplevel:
        foto["motivo"] = "sin repositorio git: no hay agentes que derivar"
        return foto
    rel = os.path.relpath(raiz, os.path.abspath(toplevel))

    arboles = aislado._worktrees(toplevel)
    cabeza = dict(arboles).get(os.path.abspath(toplevel), "")
    foto["base"] = cabeza[:7]
    de_modulo = _mapa_de_modulos(informe_simbolos)

    for ruta, head in arboles:
        consola = consola_de(ruta)
        # Aqui habia un filtro previo por `_tiene_cambios(ruta) or consola`, y al
        # entrar la tercera fuente —el commit reciente— se quedo colgando: filtraba
        # por dos de tres, asi que un arbol LIMPIO con un commit de hace veinte
        # segundos no llegaba nunca a mirarse. La misma media conexion de siempre.
        # Se quita y manda la puerta de abajo, que ya conoce las tres. Cuesta un
        # `git status` mas por worktree, y esto corre por REGENERACION, no por
        # tick del watch (que solo hace stat).
        analisis = os.path.normpath(os.path.join(ruta, rel)) if rel != "." else ruta
        if not os.path.isdir(analisis):
            continue
        ficheros = ficheros_tocados(analisis)
        # Tercera fuente de presencia, junto al arbol sucio y la consola: lo que
        # este arbol acaba de COMMITEAR. Sin ella, quien trabaja bien desaparece.
        commitados, hace_commit = commitados_recientes(
            analisis, informe_simbolos, ahora,
            # El arbol raiz mira su propia historia; los demas, solo lo que han
            # anadido POR ENCIMA de la base — o el commit de uno los enciende a
            # todos. Se distingue por RUTA y no por HEAD: un worktree recien
            # creado esta en el mismo commit que la raiz y no es la raiz.
            base="" if os.path.abspath(ruta) == os.path.abspath(toplevel) else cabeza)
        if not ficheros and not consola and not commitados:
            continue
        nodos = sorted(nodos_tocados(analisis, informe_simbolos))
        # Los simbolos van APARTE de los modulos, no en su lugar: la propagacion
        # a vecinos (`_vecinos`) razona en modulos y funciona, y reescribirla
        # seria cambiar lo que ya sirve para anadir lo que falta. El mapa
        # enciende el simbolo exacto y sigue teniendo el modulo debajo.
        simbolos = sorted(simbolos_tocados(analisis, informe_simbolos))
        # Un agente que solo esta creando modulos NUEVOS no casa con ningun nodo
        # del mapa canonico — y esconderlo seria esconder justo al que mas esta
        # construyendo. Aparece igual, con la cuenta de lo que aun no tiene sitio
        # en el mapa: es un hecho, y el mapa dira que no lo dibuja todavia.
        reciente = 0.0
        for fichero in ficheros:
            try:
                reciente = max(reciente, os.stat(fichero).st_mtime)
            except OSError:
                pass
        if consola:
            try:  # la consola tambien es actividad: mantiene vivo el cursor
                reciente = max(reciente, os.stat(_ruta_consola(ruta)).st_mtime)
            except OSError:
                pass
        # El commit tambien cuenta para "hace cuanto": si no, quien acaba de
        # commitear saldria con la edad de su ultima edicion sin commitear, que
        # puede ser de hace horas — o sin edad ninguna.
        if hace_commit is not None:
            desde_commit = ahora - hace_commit
            reciente = max(reciente, desde_commit)
        foto["agentes"].append({
            "fuera_del_mapa": max(0, len(ficheros) - len(nodos)),
            # Con NOMBRE: lo que este arbol esta creando y aun no es nodo. El
            # nacedero del mapa los pinta pulsando hasta que la union los haga
            # estrellas de verdad.
            "nacientes": modulos_nacientes(analisis, informe_simbolos),
            # SEPARADO de `nodos`, no sumado: "tiene esto sin commitear" y
            # "acaba de commitear esto" son hechos distintos y el mapa los pinta
            # distinto. Fundirlos ganaria cobertura y perderia precision, que es
            # el intercambio que este proyecto rechaza en todas partes.
            "commitados": sorted(commitados),
            "nombre": os.path.basename(os.path.normpath(ruta)),
            "ruta": ruta,
            "base": head[:7],
            "misma_base": bool(cabeza) and head == cabeza,
            "nodos": nodos,
            # La funcion/clase/metodo EXACTO que esta editando. Es lo que hace
            # util mirar el mapa mientras trabaja: "toca carrito" dice poco,
            # "toca carrito.total, que tiene 26 llamantes" dice lo que importa.
            "simbolos": simbolos,
            "vecinos": _vecinos(informe_simbolos, nodos, de_modulo),
            "ficheros": len(ficheros),
            "hace_seg": int(max(0, ahora - reciente)) if reciente else None,
            # Qué escribió, exactamente: firmas contra el mapa canónico.
            "cambios": cambios_de(analisis, ficheros, informe_simbolos),
            # Su consola en vivo (stdout teeado por el orquestador), si existe.
            "consola": consola,
            # El veredicto del grafo sobre su trabajo, si esta corriendo con
            # escalera. Sin esto, un bucle que acepta codigo solo seria opaco.
            "escalera": escalera_de(ruta),
        })

    for agente in foto["agentes"]:
        # Modulo Y simbolo entran en el mismo indice: el mapa enciende los dos y
        # el cruce (dos agentes en el mismo sitio) se detecta al nivel al que
        # OCURRE — dos agentes en el mismo modulo pero en funciones distintas no
        # es el mismo choque que dos en la misma funcion.
        for qual in list(agente["nodos"]) + list(agente["simbolos"]):
            foto["por_nodo"].setdefault(qual, {"agentes": [], "vecino_de": []})
            foto["por_nodo"][qual]["agentes"].append(agente["nombre"])
        # En su propia lista: el mapa dibuja el commit reciente distinto del
        # arbol sucio, y el CRUCE (dos agentes a la vez) se sigue calculando solo
        # con `agentes` — dos que commitearon el mismo modulo hace rato no estan
        # chocando, y contarlo como choque llenaria el mapa de alarmas falsas.
        for qual in agente.get("commitados") or ():
            foto["por_nodo"].setdefault(qual, {"agentes": [], "vecino_de": []})
            foto["por_nodo"][qual].setdefault("commitaron", []).append(agente["nombre"])
        for qual in agente["vecinos"]:
            foto["por_nodo"].setdefault(qual, {"agentes": [], "vecino_de": []})
            foto["por_nodo"][qual]["vecino_de"].append(agente["nombre"])

    foto["cruces"] = sorted(q for q, d in foto["por_nodo"].items() if len(d["agentes"]) > 1)
    return foto
