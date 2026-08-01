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
        emit(payload)
        return 0

    delta = graph.shape_delta(previa, forma)
    if delta is None:
        # Primera vez que se ve este proyecto: no hay delta posible, va la foto.
        emit(payload)
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
        try:
            with open(destino, "w", encoding="utf-8") as handle:
                handle.write(
                    viz.render_graph_cloud(
                        symbols_mod.analyze(root),
                        title="mapa · %s" % os.path.basename(root),
                        graph_report=report,
                        procedencia=_procedencia(root),
                        refresco=args.refresco,
                    )
                )
        except OSError as error:
            sys.stderr.write("[gb graph] no pude escribir %s (%s)\n" % (destino, error))
            return 2
        emit("mapa escrito en %s" % destino)
        if args.open:
            import webbrowser

            webbrowser.open("file://" + destino.replace("\\", "/"))
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


def cmd_symbols(args):
    from . import symbols

    root = os.path.abspath(args.path or ".")
    report = symbols.analyze(root, since=args.since)
    if report["root_error"]:
        sys.stderr.write("[gb symbols] %s\n" % report["root_error"])
        return 1

    if args.html:
        from . import graph as graph_mod
        from . import viz

        destino = os.path.abspath(args.html)
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
                        graph_report=graph_mod.analyze(root),
                        procedencia=_procedencia(root),
                        refresco=args.refresco,
                    )
                )
        except OSError as error:
            sys.stderr.write("[gb symbols] no pude escribir %s (%s)\n" % (destino, error))
            return 2
        emit("mapa de simbolos en %s" % destino)
        if args.open:
            import webbrowser

            webbrowser.open("file://" + destino.replace("\\", "/"))
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


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
