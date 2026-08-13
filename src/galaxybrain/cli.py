"""`gb` — la superficie de lectura.

Cada comando cae en una familia, una por tipo de hecho determinista sobre el
codigo. Un comando nuevo tiene que caer en una de ellas, o no entra:

  last · list · show · on · off · status   ->  donde peto y con que estado
  graph · symbols · calls                  ->  que forma tiene
  check                                    ->  que le hizo cada cambio
  floor                                    ->  que le falta de base
  memory                                   ->  que se aprendio, cross-repo
"""

import argparse
import datetime
import errno
import json
import os
import sys

from . import __version__, bootstrap, config, render, store


def emit(text):
    """Escribir sin morir por la codificacion de la consola.

    Lo que se imprime viene del programa observado: una variable puede contener
    un emoji, japones o cualquier cosa. Que eso tumbe la lectura del fallo seria
    la herramienta rompiendose justo en el momento en que la necesitas.
    Se pierde un caracter, no el registro.
    """
    if _STDOUT_ROTO:
        return
    stream = sys.stdout
    try:
        try:
            stream.write(text + "\n")
        except UnicodeEncodeError:
            encoding = getattr(stream, "encoding", None) or "utf-8"
            stream.write(text.encode(encoding, "replace").decode(encoding, "replace") + "\n")
    except (BrokenPipeError, OSError) as error:
        if not _es_tuberia_rota(error):
            raise
        _apagar_stdout()


#: El destino murio (un `| head` que cerro antes): se calla y se sigue — el
#: trabajo del comando no depende de que alguien siga leyendo. La consola se
#: capturo A SI MISMA rompiendose aqui (7-ago, 20260807T024900-efcedd) y el fix
#: salio leyendo ese estado con `gb show`, sin reproducir: el ciclo entero.
_STDOUT_ROTO = False


def _es_tuberia_rota(error):
    """En POSIX el pipe cerrado es BrokenPipeError; en Windows llega como
    OSError(EINVAL) — el matiz exacto que el except de emit no cubria."""
    return isinstance(error, BrokenPipeError) or getattr(error, "errno", None) in (
        errno.EPIPE,
        errno.EINVAL,
    )


def _apagar_stdout():
    """Redirigir stdout a devnull ademas de callarse: sin esto, el flush del
    interprete al salir vuelve a tropezar con la tuberia muerta y ensucia la
    salida con un 'Exception ignored'."""
    global _STDOUT_ROTO
    _STDOUT_ROTO = True
    try:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    except OSError:
        pass


def emit_utf8(text):
    """Como emit(), pero UTF-8 fiel — para la memoria, no para el crash.

    En el camino caliente emit() tolera perder un caracter raro de una variable
    antes que tumbar la lectura del fallo. La memoria es lo contrario: una nota
    mal codificada es basura, y su stdout lo consume el hook de SessionStart. Se
    escribe en bytes al buffer para no depender del locale de la consola (cp1252
    en Windows mutila acentos y flechas). Se cae a emit() si no hay buffer.
    """
    if _STDOUT_ROTO:
        return
    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is None:
        emit(text)
        return
    try:
        buffer.write((text + "\n").encode("utf-8", "replace"))
        buffer.flush()
    except (BrokenPipeError, OSError) as error:
        # La misma frontera que emit(): curar la clase, no la ruta que peto —
        # la leccion de los diez llamantes de `cargar` (libreta, 7-ago).
        if not _es_tuberia_rota(error):
            raise
        _apagar_stdout()


def _style(args):
    force = getattr(args, "color", None)
    if force == "never":
        return render.Style(False)
    if force == "always":
        return render.Style(True)
    return render.Style(sys.stdout.isatty())


def _procedencia(root):
    """De que commit y de cuando es un artefacto exportado.

    Un HTML sin esto es indistinguible de otro generado hace cinco horas, y eso
    paso de verdad: se estuvo mirando un mapa viejo y nada lo dijo. Un artefacto
    DERIVADO que no sabe decir de que version viene miente por omision en cuanto
    el repo se mueve.

    Va aqui y no en el renderizador a proposito: leer el reloj dentro del
    renderizador lo volveria no determinista, y entonces dos capturas del mismo
    proyecto dejarian de poder compararse.
    """
    import datetime

    from . import graph

    momento = datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")
    commit = graph._git(root, "rev-parse", "--short", "HEAD")
    sucio = graph._git(root, "status", "--porcelain")
    if commit:
        marca = commit.strip()
        if sucio and sucio.strip():
            # Sin esto, un mapa de un arbol con cambios sin commitear se atribuye
            # a un commit que NO es lo que estas viendo.
            marca += "+sin-commitear"
        return "generado el %s desde %s" % (momento, marca)
    return "generado el %s (sin repo git)" % momento


def _embudo_ciclo(embudo):
    """El embudo del ciclo del error en una linea. Hechos con su recuento, sin
    veredicto: "sin reaparecer" es lo maximo que se puede afirmar sin re-ejecutar."""
    return "%d capturadas · %d leidas · %d intervenidas · %d sin reaparecer" % (
        embudo["capturadas"],
        embudo["leidas"],
        embudo["intervenidas"],
        embudo["sin_reaparecer"],
    )


def _ciclo_proyecto(root):
    """El ciclo del error del proyecto que contiene a `root`, o None si no hay capturas.

    Se DERIVA en cada llamada de tres fuentes que ya existian —historico,
    leidas.jsonl y git— sin ningun fichero de estado nuevo. Los efimeros
    (`python -c`, stdin) quedan fuera: no son ficheros del proyecto y no tienen
    ciclo posible.
    """
    from . import changes
    from .capture import _project_root

    proyecto = _project_root(root) or os.path.abspath(root)
    entradas = [e for e in store.read_index(project=proyecto) if not store.is_ephemeral(e)]
    if not entradas:
        return None
    return changes.ciclo_errores(proyecto, entradas, store.read_ids())


def _linea_firma(firma):
    """La cadena de una firma como hechos encadenados, para la ficha del mapa:
    "ValueError en a.py:42 — 3 veces, ultima hace 6d · leida · tocado despues
    (abc123) · sin reaparecer desde hace 2 d"."""
    sitio = firma["where"] or "?"
    if firma["file"]:
        _resto, _sep, linea = sitio.rpartition(":")
        sitio = "%s:%s" % (os.path.basename(firma["file"]), linea)
    veces = "1 vez" if firma["count"] == 1 else "%d veces" % firma["count"]
    partes = [
        "%s en %s — %s, ultima %s"
        % (firma["type"] or "?", sitio, veces, render.relative_time(firma["last_ts"]))
    ]
    partes.append("leida" if firma["leida"] else "sin leer")
    if firma["intervencion"]:
        partes.append("tocado despues (%s)" % firma["intervencion"]["commit"])
        if firma["estado"] == "en-silencio":
            # La ventana SIEMPRE explicita: "sin reaparecer" a secas se leeria
            # como un veredicto, y es indistinguible de "no corrio". Por debajo
            # de 1 dia los dias degeneran en un "0 d" que no informa: ahi se usa
            # la granularidad de relative_time sobre la fecha del commit ("hace
            # 3h"). El formateo vive AQUI y no en changes: changes no importa
            # render (frontera declarada), solo devuelve la fecha del commit.
            if (firma["silencio_dias"] or 0) >= 1:
                partes.append("sin reaparecer desde hace %d d" % firma["silencio_dias"])
            else:
                ventana = render.relative_time(firma["intervencion"]["ts"])
                partes.append("sin reaparecer desde %s" % ventana)
        elif firma["reapariciones"]:
            partes.append("reaparecida %d vez/veces despues" % firma["reapariciones"])
    return " · ".join(partes)


#: Orden de los eslabones, del mas pendiente al mas avanzado.
_ESTADOS_CICLO = ("capturada", "leida", "intervenida", "en-silencio")


def _ciclo_para_mapa(root, informe_simbolos):
    """El ciclo del error como viaja al mapa HTML: embudo + estado por nodo modulo.

    El join ruta-de-frame -> nodo es el punto delicado en Windows ('c:' vs 'C:',
    separadores mezclados — ya hubo un bug de cache por eso): los dos lados se
    comparan por normcase, nunca por igualdad literal. En POSIX normcase no toca
    nada y dos rutas con distinta caja siguen siendo distintas.
    """
    from . import graph as graph_mod

    ciclo = _ciclo_proyecto(root)
    if not ciclo:
        return None
    modulos = {
        os.path.normcase(n.get("qual") or ""): n.get("qual")
        for n in informe_simbolos.get("nodes", [])
        if n.get("kind") == "module"
    }
    nodos = {}
    for firma in ciclo["firmas"]:
        if not firma["file"]:
            continue
        try:
            mod = graph_mod.module_name(firma["file"], root)
        except ValueError:  # otra unidad de disco en Windows
            continue
        qual = modulos.get(os.path.normcase(mod))
        if not qual:
            continue
        nodo = nodos.setdefault(qual, {"estado": firma["estado"], "lineas": []})
        # El estado del nodo es el MENOS avanzado de sus firmas: un fichero con
        # una captura sin leer se ensena pendiente aunque otra firma suya este
        # en silencio.
        if _ESTADOS_CICLO.index(firma["estado"]) < _ESTADOS_CICLO.index(nodo["estado"]):
            nodo["estado"] = firma["estado"]
        nodo["lineas"].append(_linea_firma(firma))
    return {"embudo": _embudo_ciclo(ciclo["embudo"]), "nodos": nodos}


def _capturas_para_mapa(root, informe_simbolos, tope=10):
    """Las ultimas capturas del proyecto con su nodo del grafo: el material del
    evento `peta` en la consola del mapa. La consola de errores entra al lienzo
    POR DEFECTO y en movimiento — la capa estatica del ciclo, que habia que
    saber mirar, acumulo 18 sin leer (regla 10: el no-uso se investiga; esta es
    la correccion que salio de investigarlo). Sin capturas, lista vacia y ni
    rastro (regla 9)."""
    from . import changes
    from . import graph as graph_mod
    from .capture import _project_root

    proyecto = _project_root(root) or os.path.abspath(root)
    entradas = [e for e in store.read_index(project=proyecto)
                if not store.is_ephemeral(e)][:tope]
    if not entradas:
        return []
    leidas = store.read_ids()
    modulos = {
        os.path.normcase(n.get("qual") or ""): n.get("qual")
        for n in informe_simbolos.get("nodes", [])
        if n.get("kind") == "module"
    }
    capturas = []
    for entrada in entradas:
        fichero = changes._fichero_de_firma(entrada.get("where") or "")
        nodo = ""
        if fichero:
            try:
                mod = graph_mod.module_name(fichero, root)
                nodo = modulos.get(os.path.normcase(mod)) or ""
            except ValueError:
                pass
        capturas.append({
            "id": entrada.get("id") or "",
            "ts": entrada.get("ts") or "",
            "tipo": entrada.get("type") or "?",
            "donde": entrada.get("where") or "",
            "nodo": nodo,
            "leida": bool(entrada.get("id") in leidas),
        })
    return capturas


def _shape_cache(root):
    """Donde se recuerda la ultima forma vista de un proyecto.

    En config.home(), NUNCA dentro del repo observado (ARCHITECTURE regla 7: el
    arnes no ensucia el proyecto que mira). La clave es el hash de la ruta para que
    dos proyectos distintos no se pisen y ningun nombre raro llegue al sistema de
    ficheros.
    """
    import hashlib

    # normcase, no solo abspath: en Windows `c:\x` y `C:\x` son la MISMA carpeta y
    # abspath no unifica la letra de unidad. Sin esto la clave dependia de como
    # viniera escrito el cwd, el cache no acertaba nunca y --if-changed dejaba de
    # callar — el mapa entero repetido en cada edicion, justo lo que evita. En
    # POSIX normcase no toca nada, asi que un sistema sensible a mayusculas sigue
    # distinguiendo dos rutas que de verdad son distintas.
    ruta = os.path.normcase(os.path.abspath(root))
    clave = hashlib.sha256(ruta.encode("utf-8")).hexdigest()[:16]
    return config.home() / "shape" / (clave + ".json")


def _sellado(payload, root):
    """La foto de sesion con su procedencia en la cabecera.

    El mismo agujero que ya se pago con el HTML (`_procedencia`): el payload viaja
    en el contexto del agente y horas despues se sigue leyendo como actual sin que
    nada diga de cuando es. Solo la foto entera lleva sello — un delta es un
    incremento puntual, y una linea fija en cada edicion es ruido repetido (H6).
    Se computa aqui y no antes: en los caminos que callan (proyecto sin modulos,
    forma identica) no se paga ningun subproceso de git.
    """
    titulo, salto, resto = payload.partition("\n")
    sello = "  " + _procedencia(root)
    if not salto:
        return titulo + "\n" + sello
    return titulo + "\n" + sello + "\n" + resto


def _sugerencia_primer_dia(root):
    """Una linea de arranque, SOLO en el caso inequivoco: hay repo git pero ni
    codigo Python que mapear ni suelo (SCOPE/AGENTS). Un proyecto recien nacido.

    En cualquier otro caso, silencio (H6): una carpeta sin git no ha declarado
    ser un proyecto, y un repo con suelo ya paso su primer dia.
    """
    es_repo = os.path.isdir(os.path.join(root, ".git"))
    hay_suelo = any(
        os.path.exists(os.path.join(root, doc)) for doc in ("SCOPE.md", "AGENTS.md")
    )
    if not es_repo or hay_suelo:
        return None
    return (
        "[gb] repo sin mapa ni suelo — primer dia: `gb floor` dice que falta · "
        "`gb floor --init` deja los documentos base y el pre-commit · el criterio "
        "de terminado lo escribes tu en SCOPE.md"
    )


def _capturas_sin_leer(root):
    """Cuantas capturas no-efimeras de ESTE proyecto siguen sin leer. Un hecho
    del historico, para que quien arranca la sesion decida si tirar del hilo."""
    from .capture import _project_root

    proyecto = _project_root(root) or os.path.abspath(root)
    leidas = store.read_ids()
    return sum(
        1 for e in store.read_index(project=proyecto)
        if not store.is_ephemeral(e) and e.get("id") not in leidas
    )


def _emit_mapa_sesion(payload, root):
    emit(_sellado(payload, root))
    sin_leer = _capturas_sin_leer(root)
    if sin_leer:
        emit(
            "  %d captura(s) sin leer en este proyecto — gb list para el embudo, "
            "gb show <id> para el estado" % sin_leer
        )


def _graph_context(report, root, solo_si_cambia):
    """Payload de sesion: la forma del proyecto de una pasada, o silencio.

    Silencio en los dos casos que importan — sin modulos que mapear (un proyecto que
    no es Python) y, con `--if-changed`, forma identica a la ultima vista. Un aviso
    que se repite igual en cada edicion deja de leerse, y ademas gasta el contexto
    que el resto del proyecto se esfuerza en no gastar (H6).
    """
    from . import graph

    payload = render.render_graph_context(report)
    if not payload:
        sugerencia = _sugerencia_primer_dia(root)
        if sugerencia and not solo_si_cambia:
            emit(sugerencia)
        return 0

    forma = graph.shape(report)
    cache = _shape_cache(root)
    previa = None
    try:
        previa = json.loads(cache.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        # Sin fichero, ilegible o de un formato viejo: se trata como "no habia
        # forma previa". Peor caso, se enseña el mapa entero una vez de mas.
        previa = None

    if previa != forma:
        try:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(forma, ensure_ascii=False), encoding="utf-8")
        except OSError:
            # Regla 9: si el cache no se puede escribir, esto sigue informando.
            pass

    # Sin --if-changed (el arranque de sesion) va el mapa entero: es la foto que
    # orienta, y todavia no hay nada leido con lo que comparar.
    if not solo_si_cambia:
        _emit_mapa_sesion(payload, root)
        return 0

    delta = graph.shape_delta(previa, forma)
    if delta is None:
        # Primera vez que se ve este proyecto: no hay delta posible, va la foto.
        _emit_mapa_sesion(payload, root)
        return 0
    if not delta:
        return 0
    emit(render.render_graph_delta(delta, render.graph_label(report)))
    return 0


def _project_filter(args):
    if getattr(args, "all", False):
        return None
    # Desde el CLI el cwd SI es la senal correcta: lo lanza un humano parado
    # en el proyecto que le interesa.
    from .capture import _project_root

    return _project_root(os.getcwd())


_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def _duration(text):
    """`30s`, `5m`, `2h`, `1d` o un numero pelado (segundos) -> segundos.

    Lanza ValueError con un mensaje util: un --since mal escrito no puede
    interpretarse "por lo mejor", porque el modo de fallo seria devolver una
    captura vieja como si fuera reciente.
    """
    raw = (text or "").strip().lower()
    if not raw:
        raise ValueError("--since vacio; usa por ejemplo 90s, 5m, 2h")
    unit = 1
    if raw[-1] in _UNITS:
        unit = _UNITS[raw[-1]]
        raw = raw[:-1]
    try:
        value = float(raw)
    except ValueError:
        # `from None`: el ValueError de float() no aporta nada a quien escribio mal
        # el flag, y encadenarlo enterraria el mensaje util bajo una traza interna.
        raise ValueError("no entiendo --since %r; usa por ejemplo 90s, 5m, 2h" % text) from None
    if value <= 0:
        raise ValueError("--since tiene que ser positivo (recibido %r)" % text)
    return value * unit


def _ancla_grafo(record):
    """El nodo del grafo donde peto y quien le llama, o None si no se puede decir.

    El frame que manda es el MAS INTERNO que pertenece al proyecto: el fallo
    esta abajo, y los frames de libreria no son nodos de tu grafo. Todo el
    camino calla hacia el lado seguro (regla 9): sin proyecto, sin frame propio
    o sin simbolo que contenga la linea, no se anade nada — la ficha del crash
    ya se enseno entera y este bloque es un extra, no la lectura.
    """
    from . import symbols

    proyecto = (record.get("process") or {}).get("project")
    if not proyecto or not os.path.isdir(proyecto):
        return None
    frame = next(
        (f for f in reversed(record.get("frames") or [])
         if not f.get("is_library") and f.get("file") and f.get("line")),
        None,
    )
    if frame is None:
        return None
    try:
        rel = os.path.relpath(frame["file"], proyecto)
    except ValueError:  # otra unidad de disco en Windows
        return None
    if rel.startswith(".."):
        return None  # el frame vive fuera del proyecto: no es nodo de este grafo
    report = symbols.analyze(proyecto)
    if report.get("root_error"):
        return None
    nodo = symbols.en_linea(report, rel, frame["line"])
    # El ancla resuelve contra el codigo de HOY, y la captura puede ser de hace
    # dias: si el fichero cambio despues, callar (o peor: apuntar a otro def que
    # ahora ocupa esa linea) seria mentir por omision. Salio en la primera
    # prueba de uso real: un NameError de hace 3 dias caia en una linea que ya
    # no pertenece a ningun simbolo, y el ancla callaba como si no hubiera nada
    # que decir (docs/pruebas-de-uso.md, 2026-08-04).
    cambiado = _fichero_movido_despues(proyecto, rel, record.get("ts"))
    if nodo is None and not cambiado:
        return None
    llamantes = []
    if nodo is not None:
        entrantes, _salientes = symbols._indice_llamadas(report)
        llamantes = sorted(entrantes.get(nodo["qual"], ()))
    return {
        "nodo": nodo,
        "llamantes": llamantes,
        "cambiado": cambiado,
        "sitio": "%s:%s" % (rel, frame["line"]),
    }


def _fichero_movido_despues(root, rel, ts):
    """El commit corto si el fichero cambio DESPUES de la captura, "sin-commitear"
    si esta tocado ahora mismo, None si no consta cambio.

    El mismo hecho de git con el que el ciclo del error decide "intervenida":
    aqui decide cuanto fiarse del ancla. Sin repo, sin ts o sin commits, None —
    y el ancla se comporta como siempre.
    """
    from . import graph as graph_mod

    momento = store.parse_ts(ts or "")
    if momento is None:
        return None
    sucio = graph_mod._git(root, "status", "--porcelain", "--", rel)
    if sucio and sucio.strip():
        return "sin-commitear"
    linea = graph_mod._git(root, "log", "-1", "--format=%cI %h", "--", rel)
    if not linea or not linea.strip():
        return None
    fecha, _, corto = linea.strip().partition(" ")
    ultimo = store.parse_ts(fecha)
    if ultimo is not None and ultimo > momento:
        return corto or "si"
    return None


def _emit_ancla(record):
    ancla = _ancla_grafo(record)
    if ancla is None:
        return
    emit("")
    if ancla["nodo"] is None:
        emit(
            "en el grafo: %s cambio despues de esta captura (%s) y la linea ya no "
            "cae en ningun simbolo — el ancla solo sabe leer el codigo de HOY"
            % (ancla["sitio"], ancla["cambiado"])
        )
        return
    from . import symbols

    nodo, llamantes = ancla["nodo"], ancla["llamantes"]
    emit("en el grafo: %s" % _linea_simbolo(nodo))
    if llamantes:
        de_tests = sum(1 for q in llamantes if symbols.es_de_test(q))
        orden = sorted(llamantes, key=lambda q: (symbols.es_de_test(q), q))
        vista = " · ".join(orden[:6])
        if len(orden) > 6:
            vista += " y %d mas" % (len(orden) - 6)
        cuenta = str(len(llamantes))
        if de_tests:
            cuenta = "%d — %d de src, %d de tests" % (
                len(llamantes), len(llamantes) - de_tests, de_tests)
        emit("  le llaman (%s): %s" % (cuenta, vista))
        emit("  (la onda entera: gb calls %s --depth 2)" % (nodo.get("name") or nodo["qual"]))
    else:
        emit("  nadie le llama en el grafo (entrada directa o despacho dinamico)")
    if ancla["cambiado"]:
        emit(
            "  ojo: el fichero cambio despues de la captura (%s) — el ancla apunta "
            "al codigo de HOY" % ancla["cambiado"]
        )


def cmd_last(args):
    since = None
    if getattr(args, "since", None):
        try:
            seconds = _duration(args.since)
        except ValueError as error:
            sys.stderr.write("[gb] %s\n" % error)
            return 2
        since = datetime.datetime.now().astimezone() - datetime.timedelta(seconds=seconds)

    record = store.load(project=_project_filter(args), since=since)
    if record is None:
        if since is not None:
            # Salir != 0 sin captura reciente es lo que hace util este flag desde
            # un script: distingue "peto y aqui esta el estado" de "peto por otra
            # cosa, no hay nada que leer".
            emit("(sin capturas en los ultimos %s para este proyecto)" % args.since)
        else:
            emit("(sin capturas para este proyecto - prueba: gb list --all)")
        return 1
    # Ensenar el estado ES leerlo, tambien en --json: quien automatiza tambien
    # esta consumiendo el fallo. Regla 10 — esto mide el abandono, no lo impide.
    store.mark_read(record.get("id"), project=record.get("process", {}).get("project"))
    if args.json:
        emit(json.dumps(record, ensure_ascii=False, indent=2))
        return 0
    emit(render.render_record(record, _style(args), full=args.full))
    _emit_ancla(record)
    return 0


def cmd_list(args):
    # Se lee todo el histórico para poder contar; el límite se aplica al final,
    # a las firmas agrupadas (o a las líneas si es --chrono).
    entries = store.read_index(project=_project_filter(args))
    style = _style(args)

    # Solo la vista agrupada esconde los efimeros, porque es la libreta de QUE
    # SE ROMPE Y CUANTAS VECES: un `python -c` fallido no se repite jamas, asi
    # que gasta una fila y entierra lo que si vuelve. El timeline crudo sigue
    # crudo, que para eso es el timeline.
    ocultos = 0
    if not args.chrono and not args.efimeros:
        reales = [e for e in entries if not store.is_ephemeral(e)]
        ocultos = len(entries) - len(reales)
        entries = reales

    # --pendientes: la cola de trabajo, no la libreta. Fuera las firmas
    # en-silencio (intervenidas y sin reaparecer): estan controladas, y volver a
    # repasarlas una y otra vez es justo el desgaste que la libreta debia evitar.
    # Se aplica ANTES de la bifurcacion texto/json, como el filtro de efimeros:
    # misma bandera, mismas firmas en ambas salidas.
    controladas = exploracion = 0
    if getattr(args, "pendientes", False):
        raiz = _project_filter(args)
        # La cola es lo que hay que TRABAJAR: solo ficheros DE ESTE PROYECTO.
        # Un script de scratchpad ejecutado con el cwd aqui se archiva con este
        # proyecto, pero su fichero vive en el temporal — y no hay nada que
        # arreglar en el (triaje del 8-ago: 6 de las 8 firmas "pendientes" eran
        # sondas mias). La pregunta no es "¿esta en el temporal?" —un proyecto
        # legitimo puede vivir ahi, como los repos de los tests— sino "¿es
        # codigo de este arbol?". Se dice cuantas se apartan: ocultar en
        # silencio se lee como "esto es todo lo que hay".
        if raiz and not args.efimeros:
            de_aqui = [e for e in entries if store.es_del_proyecto(e, raiz)]
            exploracion = len(entries) - len(de_aqui)
            entries = de_aqui

        if raiz is None:
            # El estado en-silencio se deriva del git de UN proyecto; con --all
            # no hay uno del que derivarlo.
            emit("--pendientes no combina con --all: en-silencio se deriva del git del proyecto")
            return 2
        from . import changes

        ciclo = changes.ciclo_errores(raiz, entries, store.read_ids())
        silencio = {
            (f["type"], f["where"])
            for f in (ciclo["firmas"] if ciclo else [])
            if f["estado"] == "en-silencio"
        }
        if silencio:
            entries = [e for e in entries if (e.get("type"), e.get("where")) not in silencio]
            controladas = len(silencio)

    # El json enseña las MISMAS firmas que el texto con las mismas banderas.
    # Antes no filtraba efimeros ("crudo para maquina") y el [:n] hacia el resto:
    # con el mismo -n, los efimeros empujaban firmas reales fuera de la ventana y
    # la maquina listaba un conjunto DISTINTO del que veia el humano (medido
    # 2026-08-06: 4 NameError propios presentes en texto y ausentes del --json).
    # Crudo de verdad es --efimeros, que destapa lo mismo en ambas salidas.
    if args.json:
        payload = entries[: args.n] if args.chrono else store.summarize(entries)[: args.n]
        emit(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if args.chrono:
        text = render.render_index(entries[: args.n], style)
    else:
        text = render.render_groups(store.summarize(entries)[: args.n], style)
    emit(text)
    # Ocultar en silencio seria el mismo fallo que acabamos de arreglar en el gate:
    # una lista corta se leeria como "esto es todo lo que ha pasado".
    if ocultos:
        emit(
            style(
                "\n(%d efimero(s) oculto(s): `python -c` o stdin, no son ficheros "
                "del proyecto — `--efimeros` para verlos)" % ocultos,
                render.DIM,
            )
        )
    if controladas:
        emit(
            style(
                "\n(%d firma(s) en silencio fuera del listado: controladas — "
                "sin --pendientes se ven)" % controladas,
                render.DIM,
            )
        )
    if exploracion:
        emit(
            style(
                "\n(%d captura(s) fuera del proyecto: viven en otro arbol, aqui no "
                "hay nada que arreglar — sin --pendientes se ven)" % exploracion,
                render.DIM,
            )
        )
    return 0


def cmd_show(args):
    record = store.load(args.id, project=_project_filter(args))
    if record is None:
        # Un id es GLOBALMENTE unico: negarselo a quien lo tiene en la mano
        # porque el cwd es otro proyecto es hostil (paso en uso real, 7-ago: el
        # aviso de un crash de live code, ilegible desde galaxy-brain sin
        # --all). Se entrega — la ficha ya dice de que proyecto es.
        record = store.load(args.id, project=None)
    if record is None:
        emit("no encuentro ninguna captura con id '%s'" % args.id)
        return 1
    store.mark_read(record.get("id"), project=record.get("process", {}).get("project"))
    if args.json:
        emit(json.dumps(record, ensure_ascii=False, indent=2))
        return 0
    emit(render.render_record(record, _style(args), full=args.full))
    _emit_ancla(record)
    return 0


def cmd_on(args):
    ok, message = bootstrap.enable()
    emit(message)
    return 0 if ok else 1


def cmd_off(args):
    ok, message = bootstrap.disable()
    emit(message)
    if ok:
        # Regla 10 de ARCHITECTURE: el abandono es dato. Si esto se apaga,
        # que quede dicho por que importa saberlo, no un hook que lo impida.
        emit("apuntalo: por que la has apagado. Ese dato vale mas que la herramienta.")
    return 0 if ok else 1


def _proponer_fronteras(report, fronteras, args):
    """Candidatas para pegar en `.gb-boundaries`. Propone, nunca escribe.

    El fichero es tuyo y lo firmas tu: una regla que DECLARAS es un hecho, y por
    eso puede bloquear; una que infiere una maquina es una opinion, y las
    opiniones no bloquean (regla 9). Escribirlo solo convertiria el gate en
    opinion enforced, que es la fabrica de falsos positivos.
    """
    from . import graph

    p = graph.proponer_fronteras(report, fronteras.get("rules") or ())
    if args.json:
        emit(json.dumps(p, ensure_ascii=False, indent=2))
        return 0
    st = _style(args)
    if p["motivo"]:
        emit(st("sin candidatas: %s" % p["motivo"], "dim"))
        return 0
    ya = sum(1 for x in p["pares"] if x["ya_declarada"])
    emit(st("FRONTERAS CANDIDATAS", "bold")
         + " - pegalas en .gb-boundaries y borra lo que no")
    emit("")
    emit("BASE  = " + ", ".join(p["nucleo"]))
    emit("BORDE = " + ", ".join(p["entrada"]))
    emit("BASE -/-> BORDE")
    emit("")
    for linea in (
        "BASE  la importan de dentro y ella casi no importa: es el suelo.",
        "BORDE importa mucho y no la importa nadie: es la entrada al sistema.",
        "Son %d pares y NINGUNO existe hoy: se declara lo que tu codigo YA cumple."
        % len(p["pares"]),
        "Una frontera que ya cruzas no es una frontera, es deuda.",
    ):
        emit(st("  " + linea, "dim"))
    if ya:
        emit(st("  %d de esos %d ya los tenias escritos a mano."
                % (ya, len(p["pares"])), "dim"))
    emit("")
    emit(st("  Esto es la FORMA del grafo, no el significado: si un modulo de",
            "dim"))
    emit(st("  presentacion resulta ser estable, sale en BASE. Muevelo tu.", "dim"))
    return 0


def cmd_graph(args):
    from . import graph

    if args.self_test:
        # Dos mitades. Las sondas montan defectos de mentira en un temporal y
        # exigen que el gate los vea. Si ademas das una ruta, se comprueban las
        # relaciones metamorficas sobre ESE codigo — que es donde vivian los
        # fallos reales, porque un fixture solo fija lo que ya sabias comprobar.
        raiz = os.path.abspath(args.path) if args.path else None
        informe_simbolos = None
        if raiz:
            from . import symbols

            informe_simbolos = symbols.analyze(raiz)
        informe = graph.self_test(raiz, informe_simbolos)
        if args.json:
            emit(json.dumps(informe, ensure_ascii=False, indent=2))
        else:
            emit(render.render_self_test(informe, _style(args)))
        return 1 if informe["failed"] else 0

    root = os.path.abspath(args.path or ".")
    # El informe de simbolos solo se calcula si HAY superficies declaradas: la
    # superficie se comprueba sobre CALLS y eso es un segundo analisis del arbol.
    # Quien no las usa no lo paga (regla 2, presupuesto de latencia).
    _fronteras = graph.load_boundaries(root, args.boundaries or graph.find_boundaries(root))
    report = graph.analyze(
        root,
        since=args.since,
        boundaries=args.boundaries,
        smells=args.smells,
        include_nested=args.include_nested,
        constructor=_constructor_de_grafo(root),
        # El informe de simbolos hace falta si hay superficies O fronteras: la
        # frontera tambien se comprueba sobre las LLAMADAS desde que se vio que
        # `crate::b::f()` la cruzaba sin dejar import (9-ago).
        informe_simbolos=(_analiza_simbolos(root)
                          if (_fronteras.get("surfaces") or _fronteras.get("rules"))
                          else None),
    )
    if getattr(args, "proponer_fronteras", False):
        return _proponer_fronteras(report, _fronteras, args)
    if args.context:
        return _graph_context(report, root, args.if_changed)
    if args.json:
        emit(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        emit(render.render_graph(report, _style(args)))
    if args.gate:
        return _graph_gate(report)
    # Una raiz que no existe es un error de uso, se pida gate o no: si devolviera 0
    # aqui, un typo en la ruta pasaria por analisis correcto.
    return 1 if report.get("root_error") else 0


def _constructor_de_grafo(root):
    """El extractor de imports que le toca a `root`, o None para el de Python.

    Misma ley que `_analiza_simbolos`: Python manda cuando hay Python, y la via
    JS entra solo donde el motor maduro no tenia nada que analizar. Devolver
    None —y no `graph.build_graph`— deja intacto el camino por defecto: quien no
    tenga JS no paga ni una comprobacion de mas.
    """
    from . import graph, lenguajes

    if not lenguajes.hay_codigo(root):
        return None
    nodes, _edges, _errores = graph.build_graph(root)
    return None if nodes else lenguajes.build_graph


def _analiza_simbolos(root, since=None):
    """El grafo de simbolos de `root`, con el motor que corresponda.

    La eleccion vive AQUI y no dentro de los motores: la CLI es lo que compone,
    y asi `symbols` (stdlib `ast`) y `lenguajes` (ast-grep por referencia) no se
    conocen entre si. Dos motores que conviven, no uno generico peor que ambos
    (ADR 0009).

    Python manda cuando hay Python: es el motor maduro y el unico sin
    dependencia externa. La via JS entra solo cuando no habia nada que analizar
    — nunca pisa un resultado bueno.
    """
    from . import lenguajes, symbols

    informe = symbols.analyze(root, since=since)
    if informe.get("nodes") or not lenguajes.hay_codigo(root):
        return informe
    informe = lenguajes.analyze(root)
    if since and not informe["root_error"]:
        # Ignorar una bandera en silencio es mentir por omision: el usuario la
        # escribio esperando un delta y recibiria un informe absoluto sin saberlo.
        informe["not_covered"].append(
            "el delta (`--since`) todavia no existe en la via JS/TS: esto es el estado "
            "ACTUAL, no lo que cambio desde %s" % since
        )
    return informe


def cmd_calls(args):
    """Quien llama a un simbolo y a quien llama el, con fichero:linea.

    La pregunta puntual que antes respondia una herramienta externa (GitNexus),
    ahora sobre el indice propio de `symbols`: cero procesos ajenos, cero deps.
    """
    from . import graph, symbols

    if args.hook:
        return _calls_hook()

    if not args.simbolo:
        sys.stderr.write("[gb calls] dime un simbolo (nombre pelado o cualificado)\n")
        return 2
    root = os.path.abspath(args.path or ".")
    report = _analiza_simbolos(root)
    if report["root_error"]:
        sys.stderr.write("[gb calls] %s\n" % report["root_error"])
        return 1
    resultado = symbols.calls(report, args.simbolo, depth=args.depth)
    if args.json:
        emit(json.dumps(resultado, ensure_ascii=False, indent=2))
        return 0
    if not resultado["matches"]:
        # "No esta" y "no lo veo" son afirmaciones distintas, y aqui se confundian:
        # sobre un proyecto JS, `gb calls total` respondia "nada llamado 'total'"
        # teniendo `total` delante, en src/carrito.js (probado 8-ago). Si no se
        # analizo ni un simbolo, lo que corresponde es declarar el limite.
        sin_leer = graph.frase_no_leido(root) if not report["nodes"] else None
        if sin_leer:
            emit("no puedo responder: %s" % sin_leer)
            return 1
        emit("nada llamado '%s' en %s" % (args.simbolo, root))
        # Devolver material tambien al fallar: los cualificados que CONTIENEN el
        # texto son casi siempre lo que se buscaba con el nombre a medias.
        parecidos = sorted(
            n["qual"] for n in report["nodes"]
            if args.simbolo.lower() in n["qual"].lower()
        )[:5]
        if parecidos:
            emit("parecidos: %s" % ", ".join(parecidos))
        return 1
    nombrado_en = report.get("nombrado_como_valor_en") or {}
    for m in resultado["matches"]:
        emit(_linea_simbolo(m["symbol"]))
        _emit_onda("le llaman", m["callers"])
        _emit_onda("llama a", m["callees"])
        _emit_como_valor(m["symbol"]["qual"], nombrado_en)
    return 0


def _emit_como_valor(qual, nombrado_en):
    """Los sitios que NOMBRAN el simbolo sin llamarlo. Callejon sin salida si no.

    `TARIFAS = {'normal': precio}` y luego `TARIFAS[tarifa](...)`: no hay ninguna
    llamada escrita, asi que ni el grafo ni un `grep precio(` la encuentran, y
    quien toque el contrato de `precio` rompe ese sitio sin enterarse.

    El grafo YA lo sabia —`nombrado_como_valor_en`, que es lo que usa la
    seleccion de tests desde el 10-ago-2026— y `gb calls` no lo decia. Media
    conexion, y en la peor superficie posible: `gb calls` es justo lo que un
    agente lee antes de tocar codigo. Salio al montar el experimento de
    correccion (11-ago-2026): el grafo reportaba 2 de 3 llamantes.

    Va en su propia linea y no mezclado con "le llaman" porque no es lo mismo:
    ahi hay una llamada escrita y aqui no. Decirlo junto seria fundir un hecho
    con una advertencia.
    """
    sitios = nombrado_en.get(qual) or []
    if not sitios:
        return
    legibles = [s[: -len(".<modulo>")] + " (a nivel de modulo)"
                if s.endswith(".<modulo>") else s for s in sorted(sitios)]
    emit("  se pasa como VALOR en (%d): %s" % (len(legibles), " · ".join(legibles[:6])))
    emit("      quien lo invoca desde ahi no deja llamada escrita: "
         "si cambias su contrato, mira esos sitios a mano")


def _linea_simbolo(ficha):
    firma = ficha.get("sig") or ""
    if firma and not firma.startswith("("):
        firma = " " + firma  # "async (…)" y "@property (…)" no van pegados al nombre
    sitio = "%s:%s" % (ficha.get("file") or "?", ficha.get("line") or "?")
    doc = (" — " + ficha["doc"]) if ficha.get("doc") else ""
    return "%s%s · %s · %s%s" % (ficha["qual"], firma, ficha.get("kind", "?"), sitio, doc)


def _emit_onda(titulo, fichas):
    from . import symbols

    de_tests = sum(1 for f in fichas if symbols.es_de_test(f["qual"]))
    cuenta = str(len(fichas))
    if de_tests:
        # "56 llamantes" y "5 de src + 51 de tests" cuentan historias distintas:
        # los tests son la red, no la onda.
        cuenta = "%d — %d de src, %d de tests" % (len(fichas), len(fichas) - de_tests, de_tests)
    emit("  %s (%s):" % (titulo, cuenta))
    # src primero dentro de cada nivel: lo que puede romperse antes que la red.
    orden = sorted(fichas, key=lambda f: (f.get("depth", 1), symbols.es_de_test(f["qual"]), f["qual"]))
    # El nivel se DICE, no se sangra. Sangrar cada nivel un poco mas dibujaba un
    # arbol que el dato no sostiene: `descuento.ConDescuento` salia indentado bajo
    # `iva_test.TestIva` y se leia como "a TestIva le llama ConDescuento", cuando
    # el dato solo dice "los dos alcanzan a iva.Iva, uno a un salto y otro a dos".
    # El contenido era correcto —depth 1 y 2 bien puestos— y aun asi la lectura
    # era falsa. Salio USANDO gb sobre los bancos de lenguajes (11-ago-2026), no
    # midiendolo: ninguna metrica mira como se lee una salida, y esta la lee un
    # agente antes de tocar codigo.
    nivel_dicho = 1
    for ficha in orden:
        profundidad = ficha.get("depth", 1)
        if profundidad > nivel_dicho:
            emit("    a %d saltos:" % profundidad)
            nivel_dicho = profundidad
        emit("    %s · %s:%s"
             % (ficha["qual"], ficha.get("file") or "?", ficha.get("line") or "?"))


def _calls_hook():
    """Modo PreToolUse (Grep/Glob): simbolos del proyecto relacionados con lo buscado.

    Lee el JSON del hook por stdin, casa el patron contra los nombres del grafo y
    devuelve fichas con fichero:linea y cuentas de llamadas — lo que hacia el hook
    de GitNexus, ahora determinista y propio. Contrato: NUNCA romper la busqueda
    que lo dispara — cualquier cosa rara (sin stdin, sin patron, raiz sin Python)
    es salir 0 en silencio.
    """
    from . import symbols

    try:
        crudo = sys.stdin.read()
    except (OSError, ValueError):
        return 0
    # El BOM se tolera a proposito: PowerShell 5.1 pipa con BOM (trampa conocida
    # de esta maquina) y `json.loads` lo rechaza. Sin esto, el hook "cumplia" su
    # contrato callando — y un silencio con causa evitable es el peor fallo de
    # un hook, porque es indistinguible de "no habia nada" (se midio 180 ms de
    # supuesta velocidad que eran mudez; docs/pruebas-de-uso.md, 2026-08-04).
    try:
        from .graph import _BOM

        datos = json.loads(crudo.lstrip(_BOM))
    except ValueError:
        return 0
    if not isinstance(datos, dict):
        return 0
    entrada = datos.get("tool_input") or {}
    # `path` queda fuera a proposito: sus tramos ("src", el nombre del paquete)
    # casarian con modulos del grafo en CADA busqueda, y eso es ruido fijo.
    texto = " ".join(
        str(entrada.get(clave) or "") for clave in ("pattern", "query", "glob")
    )
    report = symbols.analyze(os.path.abspath(datos.get("cwd") or "."))
    if report.get("root_error") or not report["nodes"]:
        return 0
    fichas = symbols.relacionados(report, texto)
    if not fichas:
        return 0
    emit("[gb] esos nombres estan en el grafo de simbolos:")
    for ficha in fichas:
        cuentas = "%d le llaman" % ficha["callers"]
        if ficha.get("callers_tests"):
            cuentas += " (%d de tests)" % ficha["callers_tests"]
        emit("  %s · %s, llama a %d" % (_linea_simbolo(ficha), cuentas, ficha["callees"]))
    emit("  (detalle y onda: gb calls <simbolo> --depth 2)")
    return 0


def cmd_symbols(args):
    from . import symbols

    root = os.path.abspath(args.path or ".")

    report = _analiza_simbolos(root, since=args.since)
    if report["root_error"]:
        sys.stderr.write("[gb symbols] %s\n" % report["root_error"])
        return 1

    # El mapa persistente: comparar con la ultima mirada y sobrescribirla.
    # Tambien en --json: un agente que pide JSON tambien "miro", y el delta
    # viaja dentro del informe en vez de perderse.
    from . import mapa

    _viejo = mapa.cargar(root)
    _cambios = mapa.delta(_viejo, report)
    mapa.guardar(root, report)
    report["mapa"] = _cambios

    if args.json:
        emit(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    tipos = {}
    for node in report["nodes"]:
        tipos[node["kind"]] = tipos.get(node["kind"], 0) + 1
    relaciones = {}
    for arista in report["edges"]:
        relaciones[arista[2]] = relaciones.get(arista[2], 0) + 1

    emit("%s" % ", ".join("%d %s" % (v, k) for k, v in sorted(tipos.items())))
    emit(", ".join("%d %s" % (v, k) for k, v in sorted(relaciones.items())))
    if _cambios is None:
        emit("[mapa] primera mirada: %d simbolos guardados" % len(report["nodes"]))
    elif mapa.vacio(_cambios):
        emit("[mapa] sin cambios desde tu ultima mirada (%s)" % _cambios["ts"])
    else:
        emit("[mapa] desde tu ultima mirada (%s): +%d simbolo(s), -%d, "
             "+%d arista(s), -%d" % (
                 _cambios["ts"], len(_cambios["nuevos"]), len(_cambios["idos"]),
                 len(_cambios["aristas_nuevas"]), len(_cambios["aristas_idas"])))
        for q in _cambios["nuevos"][:5]:
            emit("  + %s" % q)
        for q in _cambios["idos"][:5]:
            emit("  - %s" % q)
    if report.get("baseline_ok"):
        emit("vs %s: +%d simbolos, +%d llamadas, -%d desaparecidos"
             % (report["since"], len(report["new_nodes"]), len(report["new_calls"]),
                report["gone_nodes"]))
    elif report.get("baseline_ok") is False:
        emit("vs %s: no pude leer la baseline (repo git? ref valida?)" % report["since"])
    emit("")
    total = report["calls_candidates"]
    emit(
        "llamadas: %d resueltas de %d candidatas (%.0f%%) · %d a builtins, excluidas"
        % (report["calls_resolved"], total, symbols.coverage(report) * 100,
           report["calls_builtin"])
    )
    for motivo, cuantas in report["unresolved"].items():
        emit("  sin resolver · %-24s %d" % (motivo, cuantas))
    emit("")
    emit("Lo que esta tecnica NO puede ver:")
    for item in report["not_covered"]:
        emit("  - %s" % item)
    return 0


def cmd_floor(args):
    from . import floor

    root = os.path.abspath(args.path or ".")
    if args.init:
        if not os.path.isdir(root):
            sys.stderr.write("[gb floor] la raiz no existe: %s\n" % root)
            return 1
        for hecho in floor.scaffold(root):
            emit("  %-9s %s" % (hecho["action"], hecho["path"]))
            # El enganche es automatico desde el 7-ago; la pista solo queda para
            # los casos en que NO se pudo o no se debio (hooksPath ajeno).
            if hecho["path"] == "core.hooksPath" and hecho["action"].startswith(("respetado", "no-pude", "sin-git")):
                emit("            el pre-commit de gb queda SIN enganchar; a mano: "
                     "git config core.hooksPath .githooks")
        emit("")
    report = floor.analyze(root, run_tests=args.time)
    if args.json:
        emit(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        emit(render.render_floor(report, _style(args)))
    # Un suelo incompleto NO es un fallo: es una lista de lo que falta. Solo la
    # raiz inexistente es error de uso. Gatear esto lo volveria ceremonia.
    return 1 if report["root_error"] else 0


def cmd_check(args):
    from . import changes

    root = os.path.abspath(args.path or ".")
    report = changes.analyze(root, args.range, staged=args.staged)
    if args.json:
        emit(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        emit(render.render_changes(report, _style(args), brief=args.brief))
    # Un rango ilegible es error de USO (no hay nada revisado). Las senales, en
    # cambio, NO son motivo de salida != 0: son proxies, y gatear proxies fue el
    # error anterior. Informar delante de quien decide es lo que las hace inevitables.
    return 1 if report["range_error"] else 0


def cmd_tests(args):
    """Qué tests correr por lo que cambió. Sin `--run`, no ejecuta nada.

    El defecto es la lista, no la ejecución: el comando barato y sin sorpresas es
    el que sale sin escribir banderas, y lanzar una suite es gasto que se pide
    aparte. Con `--run` el exit code es el de pytest — ahí sí es un oráculo.
    """
    import subprocess

    from . import impacted

    root = os.path.abspath(args.path or ".")

    if getattr(args, "union", False):
        if not args.run:
            sys.stderr.write("[gb tests] --union ejecuta suites: pide --run explicitamente\n")
            return 2
        if args.staged or args.range:
            sys.stderr.write("[gb tests] --union mira los worktrees registrados, "
                             "no un rango ni el indice\n")
            return 2
        return _corre_union(root)

    report = impacted.analyze(root, args.range, staged=args.staged,
                              worktree=args.worktree, grafo=_analiza_simbolos(root))
    if args.json:
        emit(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        emit(render.render_impacted(report, _style(args), brief=args.brief))

    if report["range_error"]:
        return 1
    if not args.run:
        return 0

    ficheros = report.get("tests") or []
    if not ficheros:
        return 0

    if getattr(args, "isolated", False):
        return _corre_aislado(root, ficheros, staged=args.staged)

    # El runner sale de lo que el PROYECTO declara, no de lo que este arnes esta
    # escrito en Python. Estaba cableado a pytest: sobre un repo JS corria pytest
    # contra ficheros .js, fallaba siempre, y el veredicto "los tests estan en
    # rojo" era MENTIRA — en 16 de los 17 lenguajes que el grafo ya lee. Cazado
    # en la primera tirada real fuera de este repo (9-ago), y es la sexta vez
    # esta semana que una suposicion de Python se queda atras.
    import shutil

    from . import floor

    comando, fuente = floor.detect_test_command(root)
    if not comando:
        emit("")
        emit("no se que comando corre los tests de este proyecto (%s): no ejecuto nada."
             % (fuente or "sin configuracion que lo declare"))
        emit("declaralo en su AGENTS.md o en la config de su ecosistema.")
        return 3        # ni verde ni rojo: NO SE PUDO COMPROBAR

    # `-p no:cacheprovider` no: cambiar el entorno de la suite del usuario para
    # que nuestro atajo quede mas limpio es exactamente lo que un arnes no hace.
    if comando.split()[0] in ("pytest", "python", sys.executable):
        cmd = [sys.executable, "-m", "pytest"] + ficheros
        shell = False
    else:
        # Un runner que no sea pytest no acepta una lista de ficheros sueltos de
        # forma portable (`go test` toma paquetes, `cargo test` no toma ninguno),
        # asi que se corre ENTERO y se dice. Estrechar sin poder hacerlo seria
        # inventarse el ahorro; correr de mas es seguro y honesto.
        binario = comando.split()[0]
        if not shutil.which(binario):
            # El runtime NO esta instalado. Eso no es un test en rojo: es que no
            # se pudo comprobar. Meterlo en el mismo saco daria el falso rojo que
            # esta tirada destapo — `swift test` sin Swift instalado leyendose
            # como "los tests fallan".
            emit("")
            emit("`%s` es el runner de este proyecto (%s) y no esta instalado: "
                 "no ejecuto nada." % (binario, fuente))
            return 3
        cmd, shell = comando, True
        emit("")
        emit("(la seleccion no se puede pasar a `%s`: se corre la suite entera)" % binario)
    emit("")
    emit("$ %s" % (comando if shell else " ".join(cmd[1:])))
    try:
        return subprocess.call(cmd, cwd=root, shell=shell)
    except OSError as error:
        emit("no se pudo lanzar `%s`: %s" % (comando, error))
        return 3


def _corre_union(root):
    """`tests --run --union`: N ramas en paralelo, cada una sola y luego juntas.

    Lo que se lee primero no es el verde: es quien NO se sostiene solo. Un merge
    verde con una rama rota debajo es el fallo que se midio y que nadie ve mirando
    solo el resultado del merge.
    """
    from . import aislado

    informe = aislado.converge(root, traza=emit)

    if not informe["monto"]:
        emit(informe["motivo"] or "no se pudo verificar")
        return informe["veredicto"]

    emit("")
    for rama in informe["ramas"]:
        marca = "ok" if rama["veredicto"] == 0 else "ROJA"
        extra = ""
        if rama["ausentes"]:
            extra = " (%d test(s) no viajan)" % len(rama["ausentes"])
        elif rama["motivo"]:
            extra = " (%s)" % rama["motivo"]
        emit("  %-6s %s%s" % (marca, rama["nombre"], extra))

    union = informe["union"]
    if union is None:
        emit("")
        emit(informe["motivo"])
    else:
        marca = "ok" if union["veredicto"] == 0 else "ROJA"
        emit("  %-6s union%s" % (marca, (" (%s)" % union["motivo"]) if union["motivo"] else ""))

    if informe["rescatados"]:
        emit("")
        emit("RESCATE ACCIDENTAL: la union pasa, pero estas ramas no se sostienen solas:")
        for nombre in informe["rescatados"]:
            emit("  %s" % nombre)
        emit("su verde lo puso otra rama, no su propio trabajo.")

    if informe.get("choque_semantico"):
        # El caso inverso, y el que hay que gritar: ninguna rama esta mal, y
        # juntas rompen. Ninguna puede verlo desde dentro, y el merge sale limpio
        # porque el choque es de SIGNIFICADO y no de texto — por eso ni git ni un
        # merge tool lo cazan. Deducirlo cruzando "todas en ok" con "union ROJA"
        # es justo lo que nadie hace leyendo una salida.
        emit("")
        emit("CHOQUE SEMANTICO: cada rama pasa SOLA y juntas rompen.")
        emit("  ningun merge tool lo ve: los diffs componen limpio y el choque es")
        emit("  de significado. Mira que asume cada una del trabajo de la otra.")

    return informe["veredicto"]


def _corre_aislado(root, ficheros, staged=False):
    """`tests --run --isolated`: el verde vale sobre el diff, no sobre tu copia.

    Si no se pudo montar el arbol limpio NO se cae al modo normal: un verde de
    consolacion sobre el arbol sucio es justo el falso positivo que este modo
    existe para matar. Se dice por que y se sale distinto de cero.
    """
    from . import aislado

    emit("")
    informe = aislado.verifica(root, ficheros, staged=staged, traza=emit)

    if not informe["monto"]:
        emit("no se pudo verificar en limpio: %s" % informe["motivo"])
        return 1

    fuera = informe["sin_trackear"]
    if fuera:
        emit("")
        emit("%d fichero(s) sin trackear NO viajan en el diff:" % len(fuera))
        for rel in fuera[:10]:
            emit("  %s" % rel)
        if len(fuera) > 10:
            emit("  ... y %d mas" % (len(fuera) - 10))

    if informe["ausentes"]:
        emit("")
        emit("%d fichero(s) de test no existen en el arbol limpio (git add?):"
             % len(informe["ausentes"]))
        for rel in informe["ausentes"]:
            emit("  %s" % rel)
        emit("verificacion INCOMPLETA: lo que si corrio no cubre el cambio entero")

    if informe["motivo"]:
        emit(informe["motivo"])
    return informe["veredicto"]


def cmd_delta(args):
    """Los errores clásicos que añadió el cambio. Sale 0 SIEMPRE si pudo mirar.

    Son proxies, y gatear proxies fabrica los falsos positivos que acaban en
    `--no-verify` (regla 11). Lo que las hace inevitables no es bloquear: es que
    salgan delante de quien decide sin tener que acordarse de pedirlas.
    """
    from . import delta as delta_mod

    root = os.path.abspath(args.path or ".")
    report = delta_mod.analyze(root, args.range, staged=args.staged, worktree=args.worktree)
    if args.json:
        emit(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        salida = render.render_delta(report, _style(args), brief=args.brief)
        # En modo hook, callar cuando no hay nada: una linea que siempre dice
        # "nada" deja de leerse, y con ella las que si traen algo.
        if salida and not (args.brief and not delta_mod.total(report)):
            emit(salida)
    return 1 if report["range_error"] else 0


def cmd_memory(args):
    from . import memory

    action = getattr(args, "mem_command", None) or "index"
    if action == "context":
        # El payload de SessionStart. Sale 0 SIEMPRE y calla si no hay nada: una
        # herramienta de memoria jamas debe tumbar el arranque de una sesion.
        payload = memory.context(getattr(args, "project", None))
        if payload:
            emit_utf8(payload)
        return 0
    if action == "recall":
        query = " ".join(getattr(args, "query", []) or [])
        if not query.strip():
            sys.stderr.write("[gb memory] recall necesita palabras de busqueda\n")
            return 2
        for line in memory.recall(query):
            emit_utf8(line)
        return 0
    if action == "add":
        if not args.name or not args.description:
            sys.stderr.write("[gb memory] add necesita --name y --description\n")
            return 2
        body = args.body
        if not body and not sys.stdin.isatty():
            try:
                body = sys.stdin.read().strip()
            except (OSError, ValueError):
                body = ""
        path = memory.add(
            args.name,
            args.description,
            type=args.type,
            scope=args.scope,
            tags=args.tags or "",
            body=body or "",
        )
        emit_utf8("saved: %s [%s] -> %s" % (args.name, args.scope, path))
        return 0
    for line in memory.index_lines():
        emit_utf8(line)
    return 0


def _graph_gate(report):
    """Código de salida del --gate. Con --since, falla solo con ciclos NUEVOS;
    sin --since, estricto (cualquier ciclo). Si no se puede comparar la baseline,
    NO se bloquea (un falso positivo acaba en --no-verify) — se avisa por stderr."""
    # Un problema de CONFIGURACIÓN de reglas enforce nada, así que falla SIEMPRE:
    # fichero ilegible, línea mal escrita, o una regla que no casa con ningún
    # módulo. Pasar en verde con eso sería la falsa cobertura que la gate existe
    # para evitar (el peor fallo de una gate).
    if (
        report.get("boundaries_error")
        or report.get("malformed_boundaries")
        or report.get("unmatched_rules")
    ):
        return 1
    # Una superficie publica rota es un HECHO declarado, igual que un cruce de
    # frontera: alguien entro a un modulo por un simbolo que tu dijiste que no
    # era la puerta. Bloquea por el mismo motivo y con el mismo derecho.
    if report.get("surface_violations"):
        return 1
    # Una frontera cruzada con una LLAMADA es el mismo hecho que cruzarla con un
    # import: llamar a B es depender de B. Bloquea igual.
    if report.get("call_violations"):
        return 1
    # El mismo fallo un escalon mas sutil: no hay error que leer, solo cero reglas
    # y un verde. Que no exista NINGUN .gb-boundaries es legitimo (las fronteras
    # son opt-in); que exista en otra carpeta y no se este aplicando es casi
    # siempre el analisis apuntando al sitio equivocado, y entonces el verde
    # significa "no he mirado", no "esta limpio".
    if report.get("boundaries_elsewhere") and not report.get("boundaries"):
        sys.stderr.write(
            "[gb graph] 0 reglas de frontera cargadas (busque en %s), pero SI existe "
            "%s. Esta gate no esta comprobando ninguna frontera: apunta el analisis a "
            "esa carpeta o mueve el fichero.\n"
            % (report.get("boundaries_path"), report["boundaries_elsewhere"])
        )
        return 1
    # Y la variante con reglas cargadas: DOS fuentes de reglas en el mismo
    # proyecto. La segunda no se esta aplicando, y tragarsela en silencio es el
    # mismo verde mudo con mejor disfraz — crees que TODAS tus fronteras estan
    # comprobadas y la mitad no lo esta. Config rota = falla siempre, como las
    # reglas malformadas. (Un subproyecto anidado con su fichero NO entra aqui:
    # _boundaries_elsewhere lo salta — sus fronteras son suyas.)
    if report.get("boundaries_elsewhere"):
        sys.stderr.write(
            "[gb graph] hay DOS ficheros de reglas: se aplica %s pero tambien existe "
            "%s, que NO se esta aplicando. Fusionalos o borra uno.\n"
            % (report.get("boundaries_path"), report["boundaries_elsewhere"])
        )
        return 1
    # Mismo motivo, un escalon antes: si la raiz no esta, o no quedo NI UN modulo
    # que analizar, esta gate no comprueba nada. Verde aqui seria falsa cobertura
    # permanente — un typo en la ruta del hook y no vuelve a mirar jamas.
    if report.get("root_error"):
        sys.stderr.write("[gb graph] %s\n" % report["root_error"])
        return 1
    if not report["modules"]:
        sys.stderr.write(
            "[gb graph] 0 modulos bajo %s: esta gate no comprueba nada, asi que no "
            "puede pasar en verde. Revisa la ruta%s.\n"
            % (
                report["root"],
                " (o usa --include-nested si el codigo esta en subproyectos)"
                if report.get("skipped_nested")
                else "",
            )
        )
        return 1
    if report["since"] is not None:
        if report["baseline_ok"] is False:
            # Sin baseline no puedo comparar el DELTA de ciclos (y un ciclo
            # preexistente no debe bloquear), pero un cruce de frontera ABSOLUTO es
            # un hecho -> sí bloqueo por él.
            if report["violations"]:
                return 1
            sys.stderr.write(
                "[gb graph] no pude comparar ciclos con '%s'; no bloqueo por eso.\n" % report["since"]
            )
            return 0
        return 1 if (report["new_pairs"] or report["new_violations"]) else 0
    return 1 if (report["cycles"] or report["violations"]) else 0


def cmd_status(args):
    if args.cobertura:
        # La pregunta que no tenia respuesta comprobable: que dispara una captura
        # y que no. Se ejecutan los dos lados de verdad, en procesos aparte y con
        # su propio historico, y se mira quien dejo registro.
        resultados = bootstrap.coverage()
        if args.json:
            emit(json.dumps(resultados, ensure_ascii=False, indent=2))
        else:
            emit(render.render_coverage(resultados, _style(args)))
        return 1 if any(not r["ok"] for r in resultados) else 0

    entries = store.read_index(limit=1)
    emit("galaxy-brain %s" % __version__)
    emit("  captura automatica : %s" % ("activa" if bootstrap.is_enabled() else "APAGADA"))
    emit("  fichero .pth       : %s" % bootstrap.pth_path())
    emit("  interprete         : %s" % sys.executable)
    emit("  historico          : %s" % config.home())
    emit("  desactivada por env: %s" % ("si (GB_DISABLE)" if config.disabled() else "no"))
    emit("  ultima captura     : %s" % (entries[0]["ts"] if entries else "ninguna"))

    # El unico numero que dice si esto SIRVE, y hasta hoy no existia. Capturar
    # mil fallos que nadie abre no es una consola de errores: es un vertedero con
    # indice. Regla 10 — se mide el abandono, no se impide.
    capturas, leidas, aperturas = store.read_stats()
    if capturas:
        detalle = "%d de %d leidas" % (leidas, capturas)
        if aperturas > leidas:
            detalle += " (%d aperturas)" % aperturas
        # El denominador, separado: exploracion (python -c, stdin, scripts del
        # temporal) no se lee y ESTA BIEN no leerla; mezclarla con el codigo de
        # proyecto inflaba la sensacion de abandono (medido 6-ago-2026: "13 de
        # 55" escondia un 6/6 en codigo real — docs/pruebas-de-uso.md).
        entradas = [e for e in store.read_index() if e.get("id")]
        ids_leidas = store.read_ids()
        codigo = [e for e in entradas if not store.es_exploracion(e)]
        cod_leidas = sum(1 for e in codigo if e["id"] in ids_leidas)
        expl = len(entradas) - len(codigo)
        if codigo and expl:
            detalle += " — %d/%d en codigo de proyecto · %d/%d exploracion" % (
                cod_leidas, len(codigo), leidas - cod_leidas, expl,
            )
        if not leidas:
            detalle += " — ninguna se ha mirado todavia"
        emit("  capturas leidas    : %s" % detalle)

    # La otra mitad del termometro: si gb se invoca siquiera. La adopcion era lo
    # unico del proyecto sin medir (SCOPE), y sin instrumento se discute con
    # folklore. El hook se apunta con apellido (`graph --context`): inyectar el
    # mapa no es lo mismo que pedirlo.
    usos = store.uso_stats()
    if usos:
        total = sum(usos.values())
        desglose = " · ".join(
            "%s %d" % (cmd, n) for cmd, n in sorted(usos.items(), key=lambda kv: (-kv[1], kv[0]))
        )
        emit("  uso (7 dias)       : %d invocacion(es) — %s" % (total, desglose))

    # El ciclo del error, visible: cuantas firmas llegaron a cada eslabon. Solo
    # si hay capturas de ESTE proyecto — un embudo de ceros seria ruido. Cada
    # cifra es un hecho (historico, leidas.jsonl, git); ninguna es un veredicto.
    ciclo = _ciclo_proyecto(os.getcwd())
    if ciclo:
        emit("  ciclo              : %s" % _embudo_ciclo(ciclo["embudo"]))
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="gb",
        description="Cuando algo peta, te dice donde y con que estado.",
    )
    parser.add_argument("--version", action="version", version="galaxy-brain %s" % __version__)
    subparsers = parser.add_subparsers(dest="command")

    def common(subparser, with_full=True):
        subparser.add_argument("--json", action="store_true", help="salida cruda")
        subparser.add_argument("--all", action="store_true", help="todos los proyectos")
        subparser.add_argument("--color", choices=["auto", "always", "never"], default="auto")
        if with_full:
            subparser.add_argument("--full", action="store_true", help="todos los frames")

    last = subparsers.add_parser("last", help="el ultimo fallo de este proyecto")
    common(last)
    last.add_argument(
        "--since",
        metavar="DURACION",
        help="solo si hay captura mas nueva que esto (90s, 5m, 2h); si no, salida != 0",
    )
    last.set_defaults(func=cmd_last)

    listing = subparsers.add_parser("list", help="que se rompe y cuantas veces")
    listing.add_argument("-n", type=int, default=20, help="cuantas firmas (o lineas con --chrono)")
    listing.add_argument("--chrono", action="store_true", help="timeline crudo en vez de agrupado")
    listing.add_argument(
        "--efimeros",
        action="store_true",
        help="incluir las capturas de `python -c`/stdin (por defecto se ocultan y se dicen)",
    )
    listing.add_argument(
        "--pendientes",
        action="store_true",
        help="solo lo sin controlar: fuera las firmas en-silencio (se deriva del git del proyecto)",
    )
    common(listing, with_full=False)
    listing.set_defaults(func=cmd_list)

    show = subparsers.add_parser("show", help="un fallo concreto por id")
    show.add_argument("id")
    common(show)
    show.set_defaults(func=cmd_show)

    on = subparsers.add_parser("on", help="activar la captura en este entorno")
    on.set_defaults(func=cmd_on)

    off = subparsers.add_parser("off", help="desactivarla")
    off.set_defaults(func=cmd_off)

    status = subparsers.add_parser("status", help="que hay activo ahora mismo")
    status.add_argument(
        "--cobertura",
        action="store_true",
        help="ejecuta cada modo de fallo y ensena cual deja registro y cual no",
    )
    status.add_argument("--json", action="store_true", help="salida cruda")
    status.add_argument("--color", choices=("auto", "always", "never"), default="auto")
    status.set_defaults(func=cmd_status)

    graph_p = subparsers.add_parser("graph", help="mapa de acoplamiento: imports, ciclos, hotspots")
    graph_p.add_argument("path", nargs="?", default=".", help="raiz del proyecto (por defecto .)")
    graph_p.add_argument("--json", action="store_true", help="salida cruda")
    graph_p.add_argument("--color", choices=["auto", "always", "never"], default="auto")
    graph_p.add_argument("--gate", action="store_true", help="codigo != 0 si hay ciclos (para pre-commit)")
    graph_p.add_argument("--since", metavar="REF", help="comparar con esta ref git; --gate falla solo con ciclos/cruces NUEVOS")
    graph_p.add_argument("--boundaries", metavar="FICHERO", help="reglas de frontera (por defecto .gb-boundaries en la raiz)")
    graph_p.add_argument("--smells", action="store_true", help="proxies de sobreingenieria (ADVISORY, no bloquea)")
    graph_p.add_argument("--proponer-fronteras", action="store_true",
                         dest="proponer_fronteras",
                         help="candidatas para .gb-boundaries derivadas del grafo "
                              "(propone, no escribe ni bloquea)")
    graph_p.add_argument(
        "--self-test",
        action="store_true",
        help="inyecta defectos conocidos y falla si el gate NO los ve (no mira tu proyecto)",
    )
    graph_p.add_argument(
        "--context",
        action="store_true",
        help="el mapa comprimido como payload de sesion; nada si no hay modulos (para hooks)",
    )
    graph_p.add_argument(
        "--if-changed",
        action="store_true",
        help="con --context: callar tambien si la forma no ha cambiado desde la ultima vez",
    )
    graph_p.add_argument(
        "--include-nested",
        action="store_true",
        help="analizar tambien los subproyectos anidados (por defecto se omiten y se dicen)",
    )
    graph_p.set_defaults(func=cmd_graph)

    check = subparsers.add_parser(
        "check", help="que le hizo un cambio a los tests y al acoplamiento"
    )
    check.add_argument(
        "range", nargs="?", default="HEAD~1..HEAD", help="rango git (por defecto HEAD~1..HEAD)"
    )
    check.add_argument("path", nargs="?", default=".", help="raiz del proyecto (por defecto .)")
    check.add_argument(
        "--staged",
        action="store_true",
        help="revisar el indice en vez de un rango (lo unico correcto en un pre-commit)",
    )
    check.add_argument(
        "--brief", action="store_true", help="una linea si no hay senales (para hooks)"
    )
    check.add_argument("--json", action="store_true", help="salida cruda")
    check.add_argument("--color", choices=["auto", "always", "never"], default="auto")
    check.set_defaults(func=cmd_check)

    syms = subparsers.add_parser(
        "symbols", help="grafo de simbolos: quien llama a quien, con su cobertura"
    )
    syms.add_argument("path", nargs="?", default=".", help="raiz del proyecto")
    syms.add_argument("--since", metavar="REF", help="marcar lo NUEVO respecto a esa ref de git")
    syms.add_argument("--json", action="store_true", help="salida cruda")
    syms.add_argument("--color", choices=["auto", "always", "never"], default="auto")
    syms.set_defaults(func=cmd_symbols)

    calls_p = subparsers.add_parser(
        "calls", help="quien llama a un simbolo y a quien llama el, con fichero:linea"
    )
    calls_p.add_argument(
        "simbolo", nargs="?", default="",
        help="nombre pelado o cualificado (p.ej. save o galaxybrain.store.save)",
    )
    calls_p.add_argument("path", nargs="?", default=".", help="raiz del proyecto (por defecto .)")
    calls_p.add_argument(
        "--depth", type=int, default=1, metavar="N",
        help="niveles de onda: 2 = tambien quien llama al que llama",
    )
    calls_p.add_argument("--json", action="store_true", help="salida cruda")
    calls_p.add_argument(
        "--hook", action="store_true",
        help="modo PreToolUse: lee el JSON del hook por stdin y calla si no hay nada",
    )
    calls_p.set_defaults(func=cmd_calls)

    tests_p = subparsers.add_parser(
        "tests", help="que tests toca correr por lo que cambio (derivado del grafo)"
    )
    tests_p.add_argument("range", nargs="?", default=None,
                         help="rango git (por defecto HEAD~1..HEAD)")
    tests_p.add_argument("path", nargs="?", default=".", help="raiz del proyecto (por defecto .)")
    tests_p.add_argument(
        "--staged", action="store_true",
        help="mirar el indice en vez de un rango (lo unico correcto en un pre-commit)",
    )
    tests_p.add_argument(
        "--worktree", action="store_true",
        help="lo que hay escrito en disco vs HEAD (el estado de en medio de una edicion)",
    )
    tests_p.add_argument(
        "--run", action="store_true",
        help="ejecutar pytest con la seleccion (por defecto solo la lista: decidir es tuyo)",
    )
    tests_p.add_argument(
        "--isolated", action="store_true",
        help="con --run: correrlos sobre un arbol limpio de HEAD + tu diff, no sobre tu copia",
    )
    tests_p.add_argument(
        "--union", action="store_true",
        help="con --run: verifica cada worktree con cambios por separado y luego su union",
    )
    tests_p.add_argument("--brief", action="store_true", help="una linea, para hooks")
    tests_p.add_argument("--json", action="store_true", help="salida cruda")
    tests_p.add_argument("--color", choices=("auto", "always", "never"), default="auto")
    tests_p.set_defaults(func=cmd_tests)

    delta_p = subparsers.add_parser(
        "delta", help="que errores clasicos ANADIO este cambio (informa, no bloquea)"
    )
    delta_p.add_argument("range", nargs="?", default=None,
                         help="rango git (por defecto HEAD~1..HEAD)")
    delta_p.add_argument("path", nargs="?", default=".", help="raiz del proyecto (por defecto .)")
    delta_p.add_argument("--staged", action="store_true", help="el indice en vez de un rango")
    delta_p.add_argument("--worktree", action="store_true",
                         help="lo escrito en disco vs HEAD (en medio de una edicion)")
    delta_p.add_argument("--brief", action="store_true", help="una linea, para hooks")
    delta_p.add_argument("--json", action="store_true", help="salida cruda")
    delta_p.add_argument("--color", choices=("auto", "always", "never"), default="auto")
    delta_p.set_defaults(func=cmd_delta)

    floor_p = subparsers.add_parser(
        "floor", help="el andamiaje base: que hay y que falta antes de construir"
    )
    floor_p.add_argument("path", nargs="?", default=".", help="raiz del proyecto (por defecto .)")
    floor_p.add_argument(
        "--time",
        action="store_true",
        help="cronometrar la suite contra el umbral DORA (ejecuta los tests: opt-in)",
    )
    floor_p.add_argument(
        "--init",
        action="store_true",
        help="dejar los documentos imprescindibles (nunca pisa lo que ya existe)",
    )
    floor_p.add_argument("--json", action="store_true", help="salida cruda")
    floor_p.add_argument("--color", choices=["auto", "always", "never"], default="auto")
    floor_p.set_defaults(func=cmd_floor)

    memory_p = subparsers.add_parser(
        "memory", help="memoria permanente cross-repo (vault markdown en ~/.claude/memory-global)"
    )
    mem_sub = memory_p.add_subparsers(dest="mem_command")

    mem_ctx = mem_sub.add_parser(
        "context", help="payload de SessionStart: indice + notas always/proyecto"
    )
    mem_ctx.add_argument(
        "--project", help="proyecto actual (por defecto se deriva de CLAUDE_PROJECT_DIR/cwd)"
    )
    mem_ctx.set_defaults(func=cmd_memory)

    mem_idx = mem_sub.add_parser("index", help="el indice compacto, una linea por nota")
    mem_idx.set_defaults(func=cmd_memory)

    mem_rec = mem_sub.add_parser("recall", help="texto completo de las notas mas relevantes")
    mem_rec.add_argument("query", nargs="*", help="palabras de busqueda")
    mem_rec.set_defaults(func=cmd_memory)

    mem_add = mem_sub.add_parser("add", help="anadir o sobrescribir una nota (cuerpo por --body o stdin)")
    mem_add.add_argument("--name")
    mem_add.add_argument("--description")
    mem_add.add_argument("--type", default="reference")
    mem_add.add_argument("--scope", default="general")
    mem_add.add_argument("--tags", default="")
    mem_add.add_argument("--body", default="")
    mem_add.set_defaults(func=cmd_memory)

    memory_p.set_defaults(func=cmd_memory)

    return parser


def _uso_label(args):
    """Con que nombre se apunta una invocacion en la libreta de usos.

    `graph --context` y los subcomandos de `memory` se apuntan con apellido:
    "el mapa se inyecto 40 veces por hook" y "alguien pidio el mapa" son datos
    opuestos, y el termometro de adopcion (regla 10) vive de esa distincion.
    """
    etiqueta = args.command or ""
    if getattr(args, "context", False):
        etiqueta += " --context"
    elif getattr(args, "gate", False):
        # El pre-commit tambien es invocacion automatica, no eleccion.
        etiqueta += " --gate"
    elif getattr(args, "hook", False):
        # El PreToolUse de busqueda tambien se dispara solo, no es eleccion.
        etiqueta += " --hook"
    elif getattr(args, "fondo", False) or getattr(args, "if_changed", False):
        # El watch de SessionStart y el mantenimiento --if-changed tambien: el
        # termometro solo vale si separa lo elegido de lo que se dispara solo.
        etiqueta += " --auto"
    elif etiqueta == "memory":
        etiqueta += " " + (getattr(args, "mem_command", None) or "index")
    return etiqueta


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    store.mark_uso(_uso_label(args))
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
