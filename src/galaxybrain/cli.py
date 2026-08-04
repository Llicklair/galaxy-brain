"""`gb` — la superficie de lectura.

Cada comando cae en una familia, una por tipo de hecho determinista sobre el
codigo. Un comando nuevo tiene que caer en una de ellas, o no entra:

  last · list · show · on · off · status   ->  donde peto y con que estado
  graph · symbols                          ->  que forma tiene
  check                                    ->  que le hizo cada cambio
  floor                                    ->  que le falta de base
  memory                                   ->  que se aprendio, cross-repo
"""

import argparse
import datetime
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
    stream = sys.stdout
    try:
        stream.write(text + "\n")
    except UnicodeEncodeError:
        encoding = getattr(stream, "encoding", None) or "utf-8"
        stream.write(text.encode(encoding, "replace").decode(encoding, "replace") + "\n")


def emit_utf8(text):
    """Como emit(), pero UTF-8 fiel — para la memoria, no para el crash.

    En el camino caliente emit() tolera perder un caracter raro de una variable
    antes que tumbar la lectura del fallo. La memoria es lo contrario: una nota
    mal codificada es basura, y su stdout lo consume el hook de SessionStart. Se
    escribe en bytes al buffer para no depender del locale de la consola (cp1252
    en Windows mutila acentos y flechas). Se cae a emit() si no hay buffer.
    """
    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is None:
        emit(text)
        return
    buffer.write((text + "\n").encode("utf-8", "replace"))
    buffer.flush()


def _style(args):
    force = getattr(args, "color", None)
    if force == "never":
        return render.Style(False)
    if force == "always":
        return render.Style(True)
    return render.Style(sys.stdout.isatty())


def _abrir(destino):
    """Abre el artefacto donde TU digas, no donde yo decida.

    Por defecto, el navegador del sistema. `GB_OPEN_CMD` lo sustituye y recibe la
    ruta como ultimo argumento — asi puedes mandarlo a un navegador concreto, a
    un perfil, o a lo que tenga tu editor para renderizar HTML.

    Va por variable de entorno y no cableando un editor porque la regla 6 dice
    que un comando cableado es un bug: gb no sabe en que editas, ni tiene por que.
    Y si tu orden falla, se cae al navegador en vez de dejarte sin abrir nada
    (regla 9: fallar hacia el lado seguro).
    """
    orden = (os.environ.get("GB_OPEN_CMD") or "").strip()
    if orden:
        import shlex
        import shutil
        import subprocess

        try:
            # posix=False en Windows: si no, `shlex` se come las barras invertidas
            # de una ruta como C:\Program Files\... y el comando sale destrozado.
            partes = shlex.split(orden, posix=(os.name != "nt"))
            # Resolver el ejecutable con `which` no es cosmetico en Windows: los
            # lanzadores de editores y de node son ficheros .CMD, y Popen no puede
            # ejecutarlos por nombre — falla con "no se encuentra el archivo".
            # Con la ruta resuelta funcionan, y sin recurrir a shell=True, que
            # traeria de vuelta todos los problemas de comillas.
            resuelto = shutil.which(partes[0]) if partes else None
            if resuelto:
                partes[0] = resuelto
            subprocess.Popen(partes + [destino])
            return
        except (OSError, ValueError) as error:
            sys.stderr.write(
                "[gb] GB_OPEN_CMD fallo (%s); lo abro con el navegador del sistema\n" % error
            )

    import webbrowser

    webbrowser.open("file://" + destino.replace("\\", "/"))


def _procedencia(root):
    """De que commit y de cuando es un artefacto exportado.

    Un HTML sin esto es indistinguible de otro generado hace cinco horas, y eso
    paso de verdad: se estuvo mirando un mapa viejo y nada lo dijo. Un artefacto
    DERIVADO que no sabe decir de que version viene miente por omision en cuanto
    el repo se mueve.

    Va aqui y no en el renderizador a proposito: leer el reloj dentro de `viz`
    lo volveria no determinista, y entonces dos capturas del mismo proyecto
    dejarian de poder compararse.
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


def _html_shape(root, destino, report, graph_report):
    """La forma de lo que el mapa DIBUJA, y donde se recuerda.

    Aqui `report` es el de simbolos. La primera version comparaba `graph.shape`,
    que es la forma a nivel de MODULO (imports, ciclos) — pero el mapa dibuja
    SIMBOLOS, asi que anadir una funcion a un modulo existente no movia la forma y
    el mapa se quedaba congelado con contenido viejo. La huella tiene que incluir
    lo que se ve: cada simbolo (con su tipo y su docstring, que salen en la ficha),
    cada llamada, y ademas el grafo de imports/ciclos.

    Todo listas —no tuplas— para que sobreviva al viaje por JSON: una tupla vuelve
    lista al releer, y la comparacion diria "cambio" siempre.
    """
    import hashlib

    from . import graph

    forma = {
        "sim": sorted(
            [n.get("qual", ""), n.get("kind", ""), n.get("doc", "")]
            for n in report.get("nodes", [])
        ),
        "llam": sorted([a, b, t] for a, b, t in report.get("edges", [])),
    }
    if graph_report is not None:
        forma["g"] = graph.shape(graph_report)
    # El mapa tambien pinta el CICLO DEL ERROR (anillos, ficha, cabecera), asi
    # que su forma registrada tiene que moverse cuando se muevan sus fuentes:
    # una captura nueva, una lectura o un commit que solo cambiara el codigo ya
    # dibujado dejaban --if-changed y el mantenimiento sin regenerar, y el ciclo
    # pintado mentia por omision toda una sesion. Huella barata y DERIVADA
    # (mtime+tamano de los dos jsonl + HEAD), ningun fichero de estado nuevo.
    # index.jsonl es global al home: una captura de OTRO proyecto tambien
    # regenera este mapa — regeneracion de mas, barata e inofensiva. Esto es
    # SOLO la forma del mapa; la del payload --context no lo lleva, su silencio
    # es sagrado.
    huella = []
    for nombre in (store.INDEX_NAME, store.READS_NAME):
        try:
            st = os.stat(str(config.home() / nombre))
            huella.append([nombre, st.st_mtime_ns, st.st_size])
        except OSError:
            huella.append([nombre, 0, 0])
    head = graph._git(root, "rev-parse", "HEAD")
    huella.append(["HEAD", (head or "").strip()])
    forma["ciclo"] = huella
    clave = hashlib.sha256(
        (os.path.normcase(os.path.abspath(root)) + "|" + os.path.normcase(destino)).encode("utf-8")
    ).hexdigest()[:16]
    return forma, config.home() / "html-shape" / (clave + ".json")


def _html_forma_igual(root, destino, report, graph_report):
    """True si el mapa ya esta en disco y su forma coincide con la ultima escrita.
    Solo LEE — no siembra el cache; de eso se encarga _html_registrar_forma tras
    escribir, para que la generacion manual y el mantenimiento compartan memoria."""
    forma, cache = _html_shape(root, destino, report, graph_report)
    try:
        previa = json.loads(cache.read_text(encoding="utf-8")).get("forma")
    except (OSError, ValueError, AttributeError):
        return False
    return os.path.exists(destino) and previa == forma


def _html_registrar_forma(root, destino, report, graph_report, refresco=0):
    """Apunta la forma y el refresco de la generacion recien hecha.

    El refresco se guarda porque el hook regenera con --if-changed y SIN
    --refresco: si no lo recordara, cada regeneracion le arrancaria al fichero su
    propio auto-refresh y la pagina se congelaria tras la primera recarga. Se
    recuerda en la generacion MANUAL (donde el usuario puso --refresco 300) y el
    mantenimiento lo conserva."""
    forma, cache = _html_shape(root, destino, report, graph_report)
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(
            json.dumps({"forma": forma, "refresco": refresco}, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        pass


def _html_refresco_recordado(root, destino, report, graph_report):
    """El --refresco de la ultima generacion manual, para que el mantenimiento no
    lo pierda. 0 si no hay registro."""
    _forma, cache = _html_shape(root, destino, report, graph_report)
    try:
        return int(json.loads(cache.read_text(encoding="utf-8")).get("refresco", 0))
    except (OSError, ValueError, TypeError):
        return 0


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
        emit(_sellado(payload, root))
        return 0

    delta = graph.shape_delta(previa, forma)
    if delta is None:
        # Primera vez que se ve este proyecto: no hay delta posible, va la foto.
        emit(_sellado(payload, root))
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
    return 0


def cmd_list(args):
    # Se lee todo el histórico para poder contar; el límite se aplica al final,
    # a las firmas agrupadas (o a las líneas si es --chrono).
    entries = store.read_index(project=_project_filter(args))
    style = _style(args)

    # --json NUNCA filtra: es la superficie de maquina y los hechos se entregan
    # crudos (regla 6). Quien automatiza decide que hacer con ellos; esconderselo
    # seria mentir por omision a un consumidor que no puede ver el aviso.
    if args.json:
        payload = entries[: args.n] if args.chrono else store.summarize(entries)[: args.n]
        emit(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    ocultos = 0
    if args.chrono:
        text = render.render_index(entries[: args.n], style)
    else:
        # Solo la vista agrupada esconde los efimeros, porque es la libreta de QUE
        # SE ROMPE Y CUANTAS VECES: un `python -c` fallido no se repite jamas, asi
        # que gasta una fila y entierra lo que si vuelve. El timeline crudo sigue
        # crudo, que para eso es el timeline.
        if not args.efimeros:
            reales = [e for e in entries if not store.is_ephemeral(e)]
            ocultos = len(entries) - len(reales)
            entries = reales
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
    return 0


def cmd_show(args):
    record = store.load(args.id, project=_project_filter(args))
    if record is None:
        emit("no encuentro ninguna captura con id '%s'" % args.id)
        return 1
    store.mark_read(record.get("id"), project=record.get("process", {}).get("project"))
    if args.json:
        emit(json.dumps(record, ensure_ascii=False, indent=2))
        return 0
    emit(render.render_record(record, _style(args), full=args.full))
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
    report = graph.analyze(
        root,
        since=args.since,
        boundaries=args.boundaries,
        smells=args.smells,
        include_nested=args.include_nested,
    )
    if args.context:
        return _graph_context(report, root, args.if_changed)
    if args.html:
        from . import symbols as symbols_mod
        from . import viz

        # Un solo grafo. `graph --html` y `symbols --html` llevan a la MISMA
        # pagina: modulos, simbolos, imports y llamadas en un lienzo. Antes eran
        # dos ficheros del mismo sujeto que habia que juntar de cabeza.
        destino = os.path.abspath(args.html)
        simbolos = symbols_mod.analyze(root)
        # Modo mantenimiento (ver cmd_symbols): no crea, solo refresca lo que hay.
        refresco = args.refresco
        if args.if_changed:
            if not os.path.exists(destino):
                return 0
            if _html_forma_igual(root, destino, simbolos, report):
                return 0
            if not refresco:
                refresco = _html_refresco_recordado(root, destino, simbolos, report)
        try:
            with open(destino, "w", encoding="utf-8") as handle:
                handle.write(
                    viz.render_graph_cloud(
                        simbolos,
                        title="mapa · %s" % os.path.basename(root),
                        graph_report=report,
                        procedencia=_procedencia(root),
                        refresco=refresco,
                        # El ciclo del error viaja como los demas extras: el cli
                        # lo computa (aqui, no en cada frame del navegador) y el
                        # renderizador solo dibuja. Informa, no bloquea.
                        ciclo=_ciclo_para_mapa(root, simbolos),
                    )
                )
        except OSError as error:
            sys.stderr.write("[gb graph] no pude escribir %s (%s)\n" % (destino, error))
            return 2
        _html_registrar_forma(root, destino, simbolos, report, refresco)
        emit("mapa escrito en %s" % destino)
        if args.open:
            _abrir(destino)
        return 1 if report.get("root_error") else 0
    if args.json:
        emit(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        emit(render.render_graph(report, _style(args)))
    if args.gate:
        return _graph_gate(report)
    # Una raiz que no existe es un error de uso, se pida gate o no: si devolviera 0
    # aqui, un typo en la ruta pasaria por analisis correcto.
    return 1 if report.get("root_error") else 0


def _firma_py(root):
    """Nombre + tamano + mtime de cada .py del arbol. Barato, y cualquier edicion
    lo mueve — es lo que usa --watch para saber cuando reanalizar."""
    marcas = []
    for base, _dirs, ficheros in os.walk(root):
        if any(p in base for p in (".git", "__pycache__", ".venv", "node_modules")):
            continue
        for f in ficheros:
            if f.endswith(".py"):
                try:
                    st = os.stat(os.path.join(base, f))
                    marcas.append((f, st.st_size, int(st.st_mtime)))
                except OSError:
                    pass
    return sorted(marcas)


def _vigilar(root, args):
    """Regenera el HTML mientras algun .py del arbol cambie. Un proceso vivo, no
    un hook.

    El hook PostToolUse fallaba por demasiados sitios: solo ve las ediciones de
    CLAUDE (no las tuyas a mano), depende de reiniciar la sesion para cargarse, y
    del shell y del PATH del hook. Esto no depende de nada de eso — mira el
    sistema de ficheros directamente. Lo lanzas en una terminal y lo dejas; el
    mapa vive mientras el proceso viva. Es lo que hace un live-server.
    """
    import time

    from . import graph as graph_mod
    from . import symbols as symbols_mod
    from . import viz

    destino = os.path.abspath(args.html)
    intervalo = max(1, args.intervalo)
    refresco = args.refresco or 5  # en watch el auto-refresh tiene sentido por defecto
    anterior = None

    emit("vigilando %s — el mapa se regenera al cambiar cualquier .py (Ctrl+C para parar)" % root)
    try:
        while True:
            actual = _firma_py(root)
            if actual != anterior:
                anterior = actual
                report = symbols_mod.analyze(root, since=args.since)
                if not report["root_error"]:
                    grafo = graph_mod.analyze(root)
                    if not _html_forma_igual(root, destino, report, grafo):
                        try:
                            with open(destino, "w", encoding="utf-8") as handle:
                                handle.write(
                                    viz.render_graph_cloud(
                                        report,
                                        title="mapa · %s" % os.path.basename(root),
                                        capas=args.capas,
                                        graph_report=grafo,
                                        procedencia=_procedencia(root),
                                        refresco=refresco,
                                        ciclo=_ciclo_para_mapa(root, report),
                                    )
                                )
                            _html_registrar_forma(root, destino, report, grafo, refresco)
                            emit("  actualizado %s" % _procedencia(root).split(" desde ")[0])
                        except OSError as error:
                            sys.stderr.write("[gb symbols] no pude escribir %s (%s)\n" % (destino, error))
            time.sleep(intervalo)
    except KeyboardInterrupt:
        emit("\nlisto.")
        return 0


def cmd_calls(args):
    """Quien llama a un simbolo y a quien llama el, con fichero:linea.

    La pregunta puntual que antes respondia una herramienta externa (GitNexus),
    ahora sobre el indice propio de `symbols`: cero procesos ajenos, cero deps.
    """
    from . import symbols

    if args.hook:
        return _calls_hook()

    if not args.simbolo:
        sys.stderr.write("[gb calls] dime un simbolo (nombre pelado o cualificado)\n")
        return 2
    root = os.path.abspath(args.path or ".")
    report = symbols.analyze(root)
    if report["root_error"]:
        sys.stderr.write("[gb calls] %s\n" % report["root_error"])
        return 1
    resultado = symbols.calls(report, args.simbolo, depth=args.depth)
    if args.json:
        emit(json.dumps(resultado, ensure_ascii=False, indent=2))
        return 0
    if not resultado["matches"]:
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
    for m in resultado["matches"]:
        emit(_linea_simbolo(m["symbol"]))
        _emit_onda("le llaman", m["callers"])
        _emit_onda("llama a", m["callees"])
    return 0


def _linea_simbolo(ficha):
    sitio = "%s:%s" % (ficha.get("file") or "?", ficha.get("line") or "?")
    doc = (" — " + ficha["doc"]) if ficha.get("doc") else ""
    return "%s · %s · %s%s" % (ficha["qual"], ficha.get("kind", "?"), sitio, doc)


def _emit_onda(titulo, fichas):
    emit("  %s (%d):" % (titulo, len(fichas)))
    for ficha in fichas:
        sangria = "    " * ficha.get("depth", 1)
        emit("%s%s · %s:%s"
             % (sangria, ficha["qual"], ficha.get("file") or "?", ficha.get("line") or "?"))


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
        datos = json.load(sys.stdin)
    except (ValueError, OSError):
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
        emit("  %s · %d le llaman, llama a %d"
             % (_linea_simbolo(ficha), ficha["callers"], ficha["callees"]))
    emit("  (detalle y onda: gb calls <simbolo> --depth 2)")
    return 0


def cmd_symbols(args):
    from . import symbols

    root = os.path.abspath(args.path or ".")

    if getattr(args, "watch", False):
        if not args.html:
            sys.stderr.write("[gb symbols] --watch necesita --html <fichero>\n")
            return 2
        return _vigilar(root, args)

    report = symbols.analyze(root, since=args.since)
    if report["root_error"]:
        sys.stderr.write("[gb symbols] %s\n" % report["root_error"])
        return 1

    if args.html:
        from . import graph as graph_mod
        from . import viz

        destino = os.path.abspath(args.html)
        grafo = graph_mod.analyze(root)
        refresco = args.refresco
        if getattr(args, "if_changed", False):
            # --if-changed es modo MANTENIMIENTO: refresca el mapa que ya hay, no
            # crea uno nuevo. Si el fichero no existe, no se toca — asi un hook
            # global puede correr en cada repo y solo actua donde TU ya generaste
            # el mapa a mano. La presencia del fichero es el opt-in, y no depende
            # del shell del hook.
            if not os.path.exists(destino):
                return 0
            if _html_forma_igual(root, destino, report, grafo):
                return 0
            # El hook no pasa --refresco; se recupera el de la generacion manual
            # para no arrancarle a la pagina su auto-refresh al regenerar.
            if not refresco:
                refresco = _html_refresco_recordado(root, destino, report, grafo)
        try:
            with open(destino, "w", encoding="utf-8") as handle:
                handle.write(
                    viz.render_graph_cloud(
                        report,
                        title="%s · %s"
                        % ("capas" if args.capas else "mapa", os.path.basename(root)),
                        capas=args.capas,
                        # Un solo grafo: modulos, simbolos, imports y llamadas en
                        # el mismo lienzo. Antes salian dos ficheros que habia que
                        # juntar de cabeza, y eso era el fallo de diseno.
                        graph_report=grafo,
                        procedencia=_procedencia(root),
                        refresco=refresco,
                        ciclo=_ciclo_para_mapa(root, report),
                    )
                )
        except OSError as error:
            sys.stderr.write("[gb symbols] no pude escribir %s (%s)\n" % (destino, error))
            return 2
        _html_registrar_forma(root, destino, report, grafo, refresco)
        emit("mapa de simbolos en %s" % destino)
        if args.open:
            _abrir(destino)
        return 0

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
    graph_p.add_argument(
        "--html",
        metavar="FICHERO",
        help="escribir el mapa como HTML autocontenido (sin dependencias ni CDN)",
    )
    graph_p.add_argument(
        "--refresco",
        type=int,
        default=0,
        metavar="SEGUNDOS",
        help="que la pagina se recargue sola cada N s (necesita que algo regenere el fichero)",
    )
    graph_p.add_argument("--open", action="store_true", help="abrirlo en el navegador")
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
    syms.add_argument("--html", metavar="FICHERO", help="escribirlo como HTML autocontenido")
    syms.add_argument("--capas", action="store_true", help="vista por capas en vez de nube")
    syms.add_argument(
        "--if-changed",
        action="store_true",
        help="con --html: no reescribir si la forma no cambio (barato para un hook)",
    )
    syms.add_argument(
        "--watch",
        action="store_true",
        help="con --html: proceso vivo que regenera el mapa cuando cambie cualquier .py",
    )
    syms.add_argument(
        "--intervalo",
        type=int,
        default=2,
        metavar="SEGUNDOS",
        help="cada cuanto mira el disco en --watch (por defecto 2)",
    )
    syms.add_argument(
        "--refresco",
        type=int,
        default=0,
        metavar="SEGUNDOS",
        help="que la pagina se recargue sola cada N s (necesita que algo regenere el fichero)",
    )
    syms.add_argument("--open", action="store_true", help="abrirlo en el navegador")
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
