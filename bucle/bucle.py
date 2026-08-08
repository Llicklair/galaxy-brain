"""El bucle: la arista determinista entre agentes estocasticos.

NO es parte de gb y no debe serlo nunca (ARCHITECTURE: gb provee, no orquesta;
docs/grafo-neuronal-orquestacion.md: "si algun dia gb orquesta, este documento
es el bug"). Es el ORQUESTADOR: consume gb por CLI/JSON exactamente como lo
haria cualquier motor externo — esa es la superficie de integracion que el
proyecto promete, asi que este fichero tambien la prueba.

La tesis que implementa (§4, medida el 5-ago-2026): la señal no puede obligar a
un LLM, pero si obliga a un bucle. Los nodos (agentes) son estocasticos; el
determinismo va en las aristas:

    preparar -> lanzar A -> DERIVAR hechos de su diff -> despachar B con el
    MARCO del desfase (defecto desde la 5ª rebanada, 6-ago-2026: el aviso fijo
    corrige 4/4 igual que la señal completa y los hechos solo hacen falta EN el
    rechazo; `--senal-completa` restaura el despacho antiguo) -> VERIFICAR la
    adopcion en el diff de B (v1: estatico, antes de la union; si escribio
    contra la firma vieja, el bucle RECHAZA y reintenta con los hechos y las
    llamadas exactas) -> aterrizar con `gb tests --run --union` -> decidir
    (verde: acta y parar; roja: UN reintento con el fallo como hecho) -> acta
    SIEMPRE.

Nunca mergea (regla de trabajo: los bucles no mergean; el merge lo dirige un
humano). El acta registra que hecho se entrego a quien: con ese registro, una
rama roja-sola con union verde se lee como COORDINADA (escribio para el arbol
futuro por señal) y no como rescatada — la ambiguedad que el checkpoint no
puede resolver solo, resuelta donde toca: en la historia de la tirada, que es
del orquestador.

Ejecutores de agente:
  real     -> `claude -p` (Opus, headless) en el worktree de la tarea.
  simulado -> aplica un parche preparado (--simula DIR con <id>.diff). Sin
              cuota, determinista: es lo que testea la maquinaria del bucle.
"""

import argparse
import ast
import inspect
import io
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GB = [sys.executable, "-m", "galaxybrain.cli"]


def _corre(cmd, cwd=None, entrada=None, timeout=None):
    """Subproceso con el entorno limpio de GIT_* (aviso 4 del protocolo)."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    try:
        r = subprocess.run(cmd, cwd=cwd or RAIZ, capture_output=True,
                           input=entrada, timeout=timeout, env=env)
    except (OSError, subprocess.TimeoutExpired) as error:
        return 1, b"", str(error).encode("utf-8", "replace")
    return r.returncode, r.stdout, r.stderr


def _texto(b):
    return b.decode("utf-8", errors="replace")


def preparar_worktree(id_tarea, raiz=None):
    """Worktree PROPIO en main (aviso 2 del protocolo: el ancla del harness).

    `raiz` permite preparar el worktree de OTRO repo: el lanzador de un agente
    suelto (agente.py) sirve para cualquier proyecto, no solo para este — y
    cablear el repo era justo el bug que aparecio al usarlo de verdad."""
    raiz = raiz or RAIZ
    ruta = os.path.join(raiz, ".claude", "worktrees", "bucle-%s" % id_tarea)
    try:
        os.remove(_log_consola(ruta))  # consola fresca por tirada
    except OSError:
        pass
    _corre(["git", "worktree", "remove", "--force", ruta], cwd=raiz)
    rc, _, err = _corre(["git", "worktree", "add", "--detach", ruta, "main"], cwd=raiz)
    if rc != 0:
        raise RuntimeError("no se pudo preparar %s: %s" % (ruta, _texto(err)))
    return ruta


def quitar_worktree(ruta):
    _corre(["git", "worktree", "remove", "--force", ruta])
    _corre(["git", "worktree", "prune"])


def firmas_de(ruta):
    """qual -> firma, via `gb symbols --json`: el bucle consume gb por CLI."""
    rc, salida, err = _corre(GB + ["symbols", ruta, "--json"])
    if rc != 0:
        raise RuntimeError("gb symbols fallo en %s: %s" % (ruta, _texto(err)[:200]))
    informe = json.loads(_texto(salida))
    return {n["qual"]: n.get("sig", "") for n in informe.get("nodes", []) if n.get("sig")}


def hechos_entre(antes, despues):
    """Los hechos entre dos mapas de firmas. Pura: sin disco, sin subprocesos."""
    hechos = []
    for qual in sorted(set(antes) | set(despues)):
        if antes.get(qual) != despues.get(qual):
            hechos.append("%s: %s -> %s" % (
                qual, antes.get(qual, "(no existia)"), despues.get(qual, "(borrada)")))
    return hechos


def derivar_hechos(worktree, firmas_base):
    """Los hechos del diff de un agente: firmas que cambiaron respecto a la BASE.

    Derivado, no declarado: sale de comparar los dos arboles, no de lo que el
    agente diga que hizo. La base es un worktree LIMPIO de main, nunca el arbol
    del orquestador: su working tree puede llevar cosas sin commitear (este
    propio fichero lo estuvo) y comparar contra el atribuye al agente hechos
    que son del orquestador. Lo cazo el primer test del bucle.
    """
    return hechos_entre(firmas_base, firmas_de(worktree))


def _signature_de(sig_texto):
    """`inspect.Signature` desde el texto de firma de gb, o None si no se puede.
    Los valores por defecto se sustituyen por None antes de compilar: solo
    importa la forma (aridad, nombres), nunca evaluar expresiones ajenas."""
    try:
        arbol = ast.parse("def _f%s: pass" % sig_texto)
        argumentos = arbol.body[0].args
        for lista in (argumentos.defaults, argumentos.kw_defaults):
            for i, valor in enumerate(lista):
                if valor is not None:
                    lista[i] = ast.copy_location(ast.Constant(None), valor)
        espacio = {}
        exec(compile(ast.fix_missing_locations(arbol), "<firma>", "exec"), {}, espacio)
        return inspect.signature(espacio["_f"])
    except Exception:
        return None


def firma_admite(sig_texto, n_posicionales, nombres_kw, posible_metodo=False):
    """True si una llamada con esos argumentos encaja en la firma. Conservadora:
    firma ilegible admite (no se acusa sobre lo que no se puede verificar,
    CLAUDE.md regla 9). `posible_metodo` prueba tambien con un self implicito."""
    firma = _signature_de(sig_texto)
    if firma is None:
        return True
    kwargs = {nombre: None for nombre in nombres_kw}
    for extra in ((0, 1) if posible_metodo else (0,)):
        try:
            firma.bind(*([None] * (n_posicionales + extra)), **kwargs)
            return True
        except TypeError:
            continue
    return False


def lineas_de_diff(texto):
    """fichero -> numeros de linea del lado NUEVO, leidos de las cabeceras @@.

    Vive aparte para que el banco de replay (replay.py) lea un diff GUARDADO
    con este mismo parser: un banco que reimplementa lo que valida no valida
    nada."""
    mapa, fichero = {}, None
    for linea in texto.splitlines():
        if linea.startswith("+++ b/"):
            fichero = linea[6:].strip()
        elif linea.startswith("+++ "):
            fichero = None
        elif linea.startswith("@@ ") and fichero:
            m = re.search(r"\+(\d+)(?:,(\d+))?", linea)
            if m:
                inicio, cuantas = int(m.group(1)), int(m.group(2) or "1")
                mapa.setdefault(fichero, set()).update(range(inicio, inicio + cuantas))
    return mapa


def lineas_anadidas(worktree):
    """fichero -> lineas nuevas segun `git diff HEAD -U0` del worktree. El
    `add -N` mete los ficheros recien creados en el diff sin stagearlos."""
    _corre(["git", "add", "-N", "."], cwd=worktree)
    _rc, salida, _err = _corre(["git", "diff", "HEAD", "-U0"], cwd=worktree)
    return lineas_de_diff(_texto(salida))


def llamadas_contra_firma_vieja(worktree, hechos, lineas=None):
    """Las llamadas AÑADIDAS por el agente que no encajan en la firma nueva del
    hecho entregado — la verificacion de adopcion de v1: estatica, sin modelo,
    antes de la union. Devuelve las infracciones (fichero:linea y por que), no
    un veredicto: son la señal exacta del rechazo. `*args`/`**kw` no se acusan.

    `lineas` (fichero -> nums) se inyecta para replayar un diff ya grabado
    contra un arbol reconstruido; por defecto se derivan del worktree vivo."""
    objetivos = {}
    for hecho in hechos:
        try:
            qual, resto = hecho.split(": ", 1)
            _, nueva = resto.split(" -> ", 1)
        except ValueError:
            continue
        objetivos[qual.rsplit(".", 1)[-1]] = (qual, nueva)
    if not objetivos:
        return []
    infracciones = []
    mapa_lineas = lineas_anadidas(worktree) if lineas is None else lineas
    for fichero, lineas in sorted(mapa_lineas.items()):
        if not fichero.endswith(".py"):
            continue
        try:
            with io.open(os.path.join(worktree, fichero), encoding="utf-8",
                         errors="replace") as fh:
                arbol = ast.parse(fh.read())
        except (OSError, SyntaxError):
            continue
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, ast.Call):
                continue
            fn = nodo.func
            nombre = fn.id if isinstance(fn, ast.Name) else (
                fn.attr if isinstance(fn, ast.Attribute) else None)
            if nombre not in objetivos or nodo.lineno not in lineas:
                continue
            if any(isinstance(a, ast.Starred) for a in nodo.args) or \
               any(k.arg is None for k in nodo.keywords):
                continue
            qual, nueva = objetivos[nombre]
            if nueva == "(borrada)":
                infracciones.append("%s:%d: llama a %s, que la señal da por borrado"
                                    % (fichero, nodo.lineno, qual))
                continue
            nombres_kw = [k.arg for k in nodo.keywords]
            if not firma_admite(nueva, len(nodo.args), nombres_kw,
                                posible_metodo=isinstance(fn, ast.Attribute)):
                infracciones.append(
                    "%s:%d: %s(%d posicional(es)%s) no encaja en la firma nueva %s"
                    % (fichero, nodo.lineno, nombre, len(nodo.args),
                       ", kw: " + ",".join(nombres_kw) if nombres_kw else "", nueva))
    return infracciones


def _ruta_acta(inicio):
    """Donde vive el acta de una tirada: .claude/actas/bucle-<inicio>.json.

    Las actas se ACUMULAN, nunca se pisan: son el dataset del que algun dia se
    aprendera (despacho entregado -> ¿adopto? -> ¿union verde?), y un dataset
    que se sobreescribe no es un dataset. La primera acta viva del proyecto se
    perdio exactamente asi: la tirada de las 00:15 piso la de las 22:40."""
    nombre = "bucle-%s.json" % inicio.replace("-", "").replace(":", "").replace(" ", "-")
    return os.path.join(RAIZ, ".claude", "actas", nombre)


def _reset_worktree(worktree):
    """Un reintento parte de la base, no del intento fallido: fuera cambios,
    fuera stage (incluidos los add -N de la verificacion) y fuera ficheros nuevos."""
    _corre(["git", "reset", "-q", "--"], cwd=worktree)
    _corre(["git", "checkout", "--", "."], cwd=worktree)
    _corre(["git", "clean", "-fd"], cwd=worktree)


def ejecutar_simulado(tarea, worktree, dir_parches):
    parche = os.path.join(dir_parches, "%s.diff" % tarea["id"])
    if not os.path.isfile(parche):
        raise RuntimeError("falta el parche simulado %s" % parche)
    with open(parche, "rb") as fh:
        rc, _, err = _corre(["git", "apply", "--3way", "-"], cwd=worktree,
                            entrada=fh.read())
    if rc != 0:
        raise RuntimeError("el parche %s no aplica: %s" % (parche, _texto(err)[:200]))
    # El simulado tambien deja consola: es lo que permite probar la tuberia
    # entera (log -> actividad -> terminal del mapa) sin gastar un token.
    with io.open(_log_consola(worktree), "a", encoding="utf-8") as fh:
        fh.write("[%s] $ agente %s (simulado)\n[%s] > git apply %s.diff\n"
                 % (time.strftime("%H:%M:%S"), tarea["id"],
                    time.strftime("%H:%M:%S"), tarea["id"]))


def _log_consola(worktree):
    """La consola del agente vive AL LADO del worktree (<ruta>.consola.log),
    no dentro: dentro ensuciaria su git status y el propio agente la veria como
    un cambio suyo. Es la convencion que `gb` (actividad) lee del disco para
    pintar la terminal del agente en el mapa."""
    return os.path.normpath(worktree).rstrip("\\/") + ".consola.log"


def _linea_consola(evento):
    """Un evento stream-json de `claude -p` -> la linea legible de su consola,
    o None si no cuenta nada. Es el stdout REAL del agente (lo que dice y las
    herramientas que usa), no una interpretacion."""
    tipo = evento.get("type")
    if tipo == "assistant":
        partes = []
        for bloque in (evento.get("message") or {}).get("content") or []:
            if bloque.get("type") == "tool_use":
                entrada = bloque.get("input") or {}
                detalle = (entrada.get("file_path") or entrada.get("command")
                           or entrada.get("pattern") or "")
                detalle = " ".join(str(detalle).split())
                partes.append(("> %s %s" % (bloque.get("name", "?"), detalle[:100])).rstrip())
            elif bloque.get("type") == "text" and (bloque.get("text") or "").strip():
                partes.append(" ".join(bloque["text"].split())[:120])
        return "\n".join(partes) or None
    if tipo == "result":
        resultado = " ".join(str(evento.get("result") or "").split())
        return ("= " + resultado[:120]) if resultado else None
    return None


def ejecutar_real(tarea, worktree, prompt, timeout_seg, eco=False):
    exe = shutil.which("claude")
    if not exe:
        raise RuntimeError("claude CLI no esta en PATH: el ejecutor real no puede correr")
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    try:
        proc = subprocess.Popen(
            [exe, "-p", prompt, "--model", "opus", "--permission-mode", "acceptEdits",
             "--output-format", "stream-json", "--verbose"],
            cwd=worktree, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    except OSError as error:
        raise RuntimeError("claude -p no arranco: %s" % error) from error
    verdugo = threading.Timer(timeout_seg, proc.kill)
    verdugo.start()
    try:
        # El stdout del agente, teeado EN VIVO a su consola: el mapa lo va
        # leyendo mientras el agente trabaja. flush por linea a proposito.
        with io.open(_log_consola(worktree), "a", encoding="utf-8") as fh:
            fh.write("[%s] $ agente %s\n" % (time.strftime("%H:%M:%S"), tarea["id"]))
            fh.flush()
            for cruda in proc.stdout:
                try:
                    evento = json.loads(cruda.decode("utf-8", "replace"))
                except ValueError:
                    continue
                linea = _linea_consola(evento)
                if linea:
                    marca = time.strftime("[%H:%M:%S] ")
                    fh.write("".join(marca + l + "\n" for l in linea.split("\n")))
                    fh.flush()
                    if eco:
                        # Con `eco`, la misma linea sale ademas por stdout: quien
                        # lanza UN agente a mano lo mira en su terminal, no solo
                        # en el mapa (bucle/agente.py).
                        print("  " + linea.replace("\n", "\n  "), flush=True)
        err = proc.stderr.read()
        rc = proc.wait()
    finally:
        verdugo.cancel()
    if rc != 0:
        raise RuntimeError("claude -p salio %d: %s" % (rc, _texto(err)[:300]))


#: El marco sin los hechos (5ª rebanada): la 4ª midio que el rechazo pierde
#: autoridad cuando contradice lo que el agente OBSERVA (su arbol viejo, su
#: pytest verde). Este aviso planta el marco del desfase sin derivar nada.
AVISO_DESFASE = ("AVISO DEL ENRUTADOR: hay otros worktrees en vuelo que pueden cambiar "
                 "contratos que tu arbol todavia no ve; que tu pytest local salga verde "
                 "no lo descarta. Escribe pensando en el arbol donde aterriza tu trabajo.")


def componer_prompt(tarea, hechos_enrutados, extra="", aviso=False):
    """El despacho: tarea + señal. La señal son HECHOS, no ordenes — lo que el
    agente haga con ellos es suyo; lo que el bucle haga con el veredicto, no.
    Con `aviso`, el marco del desfase viaja aunque los hechos no."""
    bloques = [
        "Tu directorio de trabajo es el actual (un worktree preparado). Trabaja SOLO aqui.",
        tarea["prompt"],
        "TRAMPA DE ENTORNO: un .pth pre-importa galaxybrain desde el checkout principal. "
        "Corre pytest con PYTHONPATH=<este-dir>;<este-dir>/src desde este directorio. "
        "NO commitees, NO push.",
    ]
    if hechos_enrutados:
        bloques.insert(1, "SEÑAL DEL ENRUTADOR (hechos derivados del grafo de otro worktree "
                          "en vuelo; tu arbol puede estar desfasado respecto a donde aterriza "
                          "tu trabajo):\n" + "\n".join("- " + h for h in hechos_enrutados))
    elif aviso:
        bloques.insert(1, AVISO_DESFASE)
    if extra:
        bloques.append(extra)
    return "\n\n".join(bloques)


def despacho_de(tarea, enrutados, sin_senal=False, aviso_desfase=False):
    """Qué recibe el agente y qué se queda el bucle.

    Con `sin_senal` (4ª rebanada: medida — el rechazo solo corrigió 2/4 sin la
    señal, contra 4/4 con ella) los hechos se DERIVAN y se VERIFICAN igual pero
    no viajan en el despacho: aparecen, exactos, solo en un rechazo. Con
    `aviso_desfase` (5ª rebanada: deshacer el confundido de la 4ª, que quitó
    hechos Y marco a la vez) viaja el AVISO genérico del desfase pero no los
    hechos. Devuelve (prompt, entregados, retenidos)."""
    if (sin_senal or aviso_desfase) and enrutados:
        return componer_prompt(tarea, [], aviso=aviso_desfase), [], list(enrutados)
    return componer_prompt(tarea, enrutados), list(enrutados), []


def extracto_fallo(texto):
    """Las lineas que DICEN el fallo, no la cola cruda del output.

    La primera tirada en vivo lo pago: el recorte de los ultimos 2000 caracteres
    entrego al reintento la lista de ficheros de pytest en vez del TypeError, y
    el agente reintento a ciegas. La señal del reintento tiene que ser tan
    estrecha y tan factual como la del despacho."""
    lineas = [ln for ln in texto.splitlines()
              if re.search(r"FAILED|Error\b|error:|^E\s", ln)]
    return "\n".join(lineas[-15:]) if lineas else texto[-800:]


def veredicto_union():
    """`gb tests --run --union` y su lectura: (exit, union_verde, ramas_rojas)."""
    rc, salida, err = _corre(GB + ["tests", "--run", "--union"], timeout=1800)
    texto = _texto(salida) + _texto(err)
    union_verde = bool(re.search(r"^  ok\s+union", texto, re.M))
    ramas_rojas = re.findall(r"^  ROJA\s+(\S+)", texto, re.M)
    ramas_rojas = [r for r in ramas_rojas if r != "union"]
    return rc, union_verde, ramas_rojas, texto[-2000:]


def capturas_desde(inicio_texto):
    """Las capturas de la consola de gb ocurridas desde el inicio de la tirada,
    consultadas por CLI como todo lo demas. VACIO ES UN HECHO y se escribe al
    acta — que ningun script de agente murio tambien es informacion. (En el
    banco casi siempre sera vacio: pytest atrapa las excepciones y no llegan a
    sys.excepthook; el valor aparece cuando un script o CLI muera de verdad.)"""
    rc, salida, _ = _corre(GB + ["list", "--chrono", "--json", "-n", "50"])
    if rc != 0:
        return []
    try:
        entradas = json.loads(_texto(salida))
    except ValueError:
        return []
    import datetime as _dt
    try:
        inicio = _dt.datetime.strptime(inicio_texto, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return []
    resultado = []
    for entrada in entradas if isinstance(entradas, list) else []:
        try:
            cuando = _dt.datetime.fromisoformat(entrada.get("ts") or "")
            cuando = cuando.astimezone().replace(tzinfo=None)
        except ValueError:
            continue
        if cuando >= inicio:
            resultado.append({"id": (entrada.get("id") or "")[:8],
                              "tipo": entrada.get("type") or "?",
                              "donde": entrada.get("where") or ""})
    return resultado


def interpretar(ramas_rojas, union_verde, entregas):
    """Coordinada o rescatada: la desambiguacion que el checkpoint no puede
    hacer solo (§4A, hallazgo colateral). Una rama roja-sola con union verde
    que RECIBIO señal se lee coordinada: escribio para el arbol futuro. Sin
    señal recibida, es el rescate accidental de siempre y se dice."""
    lectura = {}
    if not union_verde:
        return lectura
    for rama in ramas_rojas:
        id_tarea = rama.replace("bucle-", "")
        lectura[rama] = "coordinada" if entregas.get(id_tarea) else "RESCATADA (revisar)"
    return lectura


def correr(tirada, dir_parches=None, max_reintentos=1, timeout_agente=900, sin_senal=False,
           aviso_desfase=False):
    acta = {
        "inicio": time.strftime("%Y-%m-%d %H:%M:%S"),
        "modo": "simulado" if dir_parches else "real",
        "tareas": [t["id"] for t in tirada["tareas"]],
        "entregas": {},          # id_tarea -> [hechos que recibio en el despacho]
        "senal_retenida": {},    # id_tarea -> [hechos derivados que NO se despacharon]
        "sin_senal": bool(sin_senal),
        "aviso_desfase": bool(aviso_desfase),
        "despachos": {},         # id_tarea -> [texto COMPLETO de cada lanzamiento]
        "adopcion": {},          # id_tarea -> [llamadas contra la firma vieja]
        "reintentos": 0,
        "veredicto": None,
        "lectura_ramas": {},
        "pasos": [],
    }
    worktrees = {}
    try:
        base = preparar_worktree("base")
        worktrees["base"] = base
        firmas_base = firmas_de(base)
        hechos_acumulados = []
        for tarea in tirada["tareas"]:
            wt = preparar_worktree(tarea["id"])
            worktrees[tarea["id"]] = wt
            enrutados = hechos_acumulados if tarea.get("depende_de") else []
            prompt, entregados, retenidos = despacho_de(tarea, enrutados, sin_senal, aviso_desfase)
            if entregados:
                acta["entregas"][tarea["id"]] = list(entregados)
            if retenidos:
                acta["senal_retenida"][tarea["id"]] = list(retenidos)
                acta["pasos"].append("señal retenida a %s: %d hecho(s)"
                                     % (tarea["id"], len(retenidos)))
            # El despacho entero al acta ANTES de lanzar: la variante del
            # despacho ES su texto (derivado sobre declarado — una etiqueta de
            # version se olvida de subir; el texto no puede mentir), y es la
            # columna del dataset que permitira comparar formatos de despacho.
            acta["despachos"].setdefault(tarea["id"], []).append(prompt)
            acta["pasos"].append("lanzada %s (%d hecho(s) en el despacho%s)"
                                 % (tarea["id"], len(entregados),
                                    ", %d retenido(s)" % len(retenidos) if retenidos else ""))
            if dir_parches:
                ejecutar_simulado(tarea, wt, dir_parches)
            else:
                ejecutar_real(tarea, wt, prompt, timeout_agente)
            nuevos = derivar_hechos(wt, firmas_base)
            acta["pasos"].append("derivados de %s: %s" % (tarea["id"], nuevos or "nada"))
            # v1: verificar la adopcion ANTES de la union. El bucle ya conoce el
            # hecho entregado; si el diff del receptor llama contra la firma
            # vieja, el rechazo es del bucle — la señal que si obliga.
            if enrutados:
                infracciones = llamadas_contra_firma_vieja(wt, enrutados)
                if infracciones:
                    acta["adopcion"][tarea["id"]] = list(infracciones)
                    acta["pasos"].append("adopcion de %s: %d llamada(s) contra la señal"
                                         % (tarea["id"], len(infracciones)))
                    if not dir_parches and acta["reintentos"] < max_reintentos:
                        acta["reintentos"] += 1
                        _reset_worktree(wt)
                        if sin_senal or aviso_desfase:
                            # El rechazo es la PRIMERA noticia de los hechos:
                            # lleva los retenidos, ademas de las llamadas exactas.
                            extra = ("RECHAZO DEL BUCLE: tu diff llama contra una "
                                     "firma que otro worktree en vuelo acaba de "
                                     "cambiar. Los hechos:\n"
                                     + "\n".join("- " + h for h in enrutados)
                                     + "\nLas llamadas exactas:\n"
                                     + "\n".join(infracciones))
                            prompt_rechazo = componer_prompt(tarea, [], extra,
                                                             aviso=aviso_desfase)
                        else:
                            extra = ("RECHAZO DEL BUCLE: tu diff llama contra la firma "
                                     "VIEJA teniendo la señal delante. Las llamadas "
                                     "exactas:\n" + "\n".join(infracciones))
                            prompt_rechazo = componer_prompt(tarea, enrutados, extra)
                        acta["entregas"].setdefault(tarea["id"], []).append(
                            "(rechazo por adopcion)")
                        acta["despachos"].setdefault(tarea["id"], []).append(prompt_rechazo)
                        ejecutar_real(tarea, wt, prompt_rechazo, timeout_agente)
                        nuevos = derivar_hechos(wt, firmas_base)
                        restantes = llamadas_contra_firma_vieja(wt, enrutados)
                        acta["pasos"].append(
                            "reintento de %s por adopcion: %s"
                            % (tarea["id"], "%d infraccion(es) aun" % len(restantes)
                               if restantes else "limpio"))
                        if restantes:
                            acta["adopcion"][tarea["id"]] += \
                                ["-- tras el reintento --"] + restantes
            hechos_acumulados.extend(h for h in nuevos if h not in hechos_acumulados)

        intento = acta["reintentos"]
        while True:
            rc, union_verde, ramas_rojas, cola = veredicto_union()
            acta["pasos"].append("union: %s (exit %d; ramas rojas: %s)"
                                 % ("VERDE" if union_verde else "ROJA", rc, ramas_rojas))
            if union_verde or intento >= max_reintentos:
                acta["veredicto"] = "verde" if union_verde else "roja"
                acta["lectura_ramas"] = interpretar(ramas_rojas, union_verde, acta["entregas"])
                acta["cola_union"] = cola
                break
            # UN reintento: la ultima tarea dependiente, con el fallo como hecho.
            intento += 1
            acta["reintentos"] = intento
            ultima = tirada["tareas"][-1]
            wt = worktrees[ultima["id"]]
            _reset_worktree(wt)
            extra = ("REINTENTO: la union de todos los diffs fallo. Los fallos exactos:\n"
                     + extracto_fallo(cola))
            acta["entregas"].setdefault(ultima["id"], []).append("(cola del fallo de union)")
            if dir_parches:
                break  # en simulado no hay reintento distinto que aplicar
            prompt_union = componer_prompt(
                ultima, [] if (sin_senal or aviso_desfase) else hechos_acumulados, extra,
                aviso=aviso_desfase)
            acta["despachos"].setdefault(ultima["id"], []).append(prompt_union)
            ejecutar_real(ultima, wt, prompt_union, timeout_agente)
            acta["pasos"].append("reintento de %s" % ultima["id"])
        # La consola de errores tambien aterriza en el acta: que peto (o que
        # nada peto) durante la tirada es un hecho de la tirada.
        acta["capturas_durante"] = capturas_desde(acta["inicio"])
        # Los diffs se conservan como evidencia; el merge NUNCA es del bucle.
        acta["diffs"] = {}
        for id_tarea, wt in worktrees.items():
            if id_tarea == "base":
                continue
            _corre(["git", "add", "-N", "."], cwd=wt)
            rc, diff, _ = _corre(["git", "diff", "HEAD"], cwd=wt)
            acta["diffs"][id_tarea] = _texto(diff)
    finally:
        for wt in worktrees.values():
            quitar_worktree(wt)
        acta["fin"] = time.strftime("%Y-%m-%d %H:%M:%S")
        destino = _ruta_acta(acta["inicio"])
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        with io.open(destino, "w", encoding="utf-8") as fh:
            json.dump(acta, fh, ensure_ascii=False, indent=2)
    return acta


def resumen_actas(dir_actas=None):
    """La lectura del dataset: una linea por tirada y las frecuencias que
    justifican (o no) girar un tornillo del harness. Solo deriva de lo que hay:
    las actas v0 no tienen campo `adopcion` y se dice `sin dato`, no se inventa.
    Post-hoc y determinista: este es el unico sitio desde el que algun dia se
    'aprende', y nunca esta en el camino de una tirada."""
    dir_actas = dir_actas or os.path.join(RAIZ, ".claude", "actas")
    nombres = sorted(os.listdir(dir_actas)) if os.path.isdir(dir_actas) else []
    lineas, n, con_senal, ignoradas, con_dato, corrigio, rechazos = [], 0, 0, 0, 0, 0, 0
    for nombre in nombres:
        if not nombre.endswith(".json"):
            continue
        try:
            with io.open(os.path.join(dir_actas, nombre), encoding="utf-8") as fh:
                acta = json.load(fh)
        except (OSError, ValueError):
            lineas.append("  %s: ilegible" % nombre)
            continue
        n += 1
        senal = any(not h.startswith("(")
                    for hs in acta.get("entregas", {}).values() for h in hs)
        con_senal += 1 if senal else 0
        adopcion = acta.get("adopcion")
        if adopcion is None:
            estado = "adopcion: sin dato (acta v0)"
        else:
            con_dato += 1
            total = sum(len(v) for v in adopcion.values())
            if total:
                ignoradas += 1
                hubo_rechazo = any("por adopcion" in p for p in acta.get("pasos", []))
                rechazos += 1 if hubo_rechazo else 0
                limpio = any("por adopcion: limpio" in p for p in acta.get("pasos", []))
                corrigio += 1 if limpio else 0
                estado = "adopcion: %d infraccion(es)%s" % (
                    total, ", rechazo corrigio" if limpio else
                    (", rechazo NO corrigio" if hubo_rechazo else ""))
            else:
                estado = "adopcion: limpia"
        retenida = ""
        if acta.get("senal_retenida"):
            retenida = " · señal RETENIDA (%d hecho(s))" % sum(
                len(v) for v in acta["senal_retenida"].values())
            if acta.get("aviso_desfase"):
                retenida += " con AVISO de desfase"
        lineas.append("  %s · %s · %s · señal: %s · %s · reintentos: %d%s%s"
                      % (acta.get("inicio", "?"), acta.get("modo", "?"),
                         acta.get("veredicto", "?"), "si" if senal else "no", estado,
                         acta.get("reintentos", 0), retenida,
                         " · con nota (leerla)" if "_nota" in acta else ""))
    cabecera = "%d tirada(s) · %d con señal · adopcion ignorada %d/%d (con dato) · " \
               "rechazo corrigio %d/%d" % (n, con_senal, ignoradas, con_dato,
                                           corrigio, rechazos)
    return "\n".join([cabecera] + lineas)


def main(argv=None):
    parser = argparse.ArgumentParser(description="el bucle: orquestador determinista sobre gb")
    parser.add_argument("tirada", nargs="?", help="JSON con las tareas de la tirada")
    parser.add_argument("--simula", metavar="DIR",
                        help="ejecutor simulado: DIR con <id>.diff por tarea (sin cuota)")
    parser.add_argument("--resumen", action="store_true",
                        help="leer el dataset de actas: frecuencias y una linea por tirada")
    parser.add_argument("--timeout-agente", type=int, default=900)
    # El defecto es el MARCO (aviso fijo): medido en la 5ª rebanada igual de
    # eficaz que la señal completa (4/4 = 4/4) y mas barato. La norma va en el
    # defecto; desviarse cuesta una bandera.
    modo = parser.add_mutually_exclusive_group()
    modo.add_argument("--senal-completa", action="store_true",
                      help="despachar la señal derivada completa (el defecto hasta la 5ª "
                           "rebanada; medido igual que el aviso, 4/4 vs 4/4)")
    modo.add_argument("--sin-senal", action="store_true",
                      help="brazo desnudo (4ª rebanada): ni señal ni marco; los hechos "
                           "solo viajan en un rechazo (corrigio 2/4 — experimental)")
    modo.add_argument("--aviso-desfase", action="store_true",
                      help="el defecto, explicito: MARCO del desfase sin hechos derivados")
    args = parser.parse_args(argv)
    if args.resumen:
        print(resumen_actas())
        return 0
    if not args.tirada:
        parser.error("hace falta la tirada (o --resumen)")
    with io.open(args.tirada, encoding="utf-8") as fh:
        tirada = json.load(fh)
    acta = correr(tirada, dir_parches=args.simula, timeout_agente=args.timeout_agente,
                  sin_senal=args.sin_senal,
                  aviso_desfase=not (args.senal_completa or args.sin_senal))
    print("veredicto: %s | lectura: %s | acta: %s"
          % (acta["veredicto"], acta["lectura_ramas"] or "(sin ramas rojas)",
             os.path.relpath(_ruta_acta(acta["inicio"]), RAIZ)))
    return 0 if acta["veredicto"] == "verde" else 1


if __name__ == "__main__":
    sys.exit(main())
