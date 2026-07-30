"""`gb` — la superficie de lectura.

Empezo con cinco comandos y la regla de que cada uno nuevo se justificaba contra
la frase de SCOPE-v2 (*donde peto y con que estado*). Esa regla se quedo corta
cuando el proyecto se dio un PLANTEAMIENTO por encima del SCOPE, y conviene
decirlo en vez de ir colando comandos: hoy la superficie cubre las tres
propiedades de ese documento, una familia por propiedad.

  last · list · show · on · off · status   ->  baratos de encontrar   (v2)
  graph · symbols                          ->  estructuralmente acotados (v3)
  check                                    ->  imposibles de esconder (Fase B)
  floor                                    ->  el suelo, debajo de las tres

Un comando nuevo tiene que caer en una de esas cuatro. Si no cae, no entra.
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


def _style(args):
    force = getattr(args, "color", None)
    if force == "never":
        return render.Style(False)
    if force == "always":
        return render.Style(True)
    return render.Style(sys.stdout.isatty())


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
        raise ValueError("no entiendo --since %r; usa por ejemplo 90s, 5m, 2h" % text)
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
    if args.json:
        emit(json.dumps(record, ensure_ascii=False, indent=2))
        return 0
    emit(render.render_record(record, _style(args), full=args.full))
    return 0


def cmd_list(args):
    # Se lee todo el histórico para poder contar; el límite se aplica al final,
    # a las firmas agrupadas (o a las líneas si es --chrono).
    entries = store.read_index(project=_project_filter(args))
    if args.chrono:
        payload = entries[: args.n]
        text = render.render_index(payload, _style(args))
    else:
        payload = store.summarize(entries)[: args.n]
        text = render.render_groups(payload, _style(args))
    if args.json:
        emit(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    emit(text)
    return 0


def cmd_show(args):
    record = store.load(args.id, project=_project_filter(args))
    if record is None:
        emit("no encuentro ninguna captura con id '%s'" % args.id)
        return 1
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
        # Regla 10 de ARCHITECTURE-v2: el abandono es dato. Si esto se apaga,
        # que quede dicho por que importa saberlo, no un hook que lo impida.
        emit("apuntalo: por que la has apagado. Ese dato vale mas que la herramienta.")
    return 0 if ok else 1


def cmd_graph(args):
    from . import graph

    root = os.path.abspath(args.path or ".")
    report = graph.analyze(
        root,
        since=args.since,
        boundaries=args.boundaries,
        smells=args.smells,
        include_nested=args.include_nested,
    )
    if args.html:
        from . import viz

        destino = os.path.abspath(args.html)
        try:
            with open(destino, "w", encoding="utf-8") as handle:
                handle.write(viz.render_html(report, title="mapa · %s" % os.path.basename(root)))
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
        from . import viz

        destino = os.path.abspath(args.html)
        try:
            with open(destino, "w", encoding="utf-8") as handle:
                handle.write(
                    (viz.render_symbols_html if args.capas else viz.render_graph_cloud)(
                        report, title="simbolos · %s" % os.path.basename(root)
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
    # error de v1. Informar delante de quien decide es lo que las hace inevitables.
    return 1 if report["range_error"] else 0


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
    entries = store.read_index(limit=1)
    emit("galaxy-brain %s" % __version__)
    emit("  captura automatica : %s" % ("activa" if bootstrap.is_enabled() else "APAGADA"))
    emit("  fichero .pth       : %s" % bootstrap.pth_path())
    emit("  interprete         : %s" % sys.executable)
    emit("  historico          : %s" % config.home())
    emit("  desactivada por env: %s" % ("si (GB_DISABLE)" if config.disabled() else "no"))
    emit("  ultima captura     : %s" % (entries[0]["ts"] if entries else "ninguna"))
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
        "--include-nested",
        action="store_true",
        help="analizar tambien los subproyectos anidados (por defecto se omiten y se dicen)",
    )
    graph_p.add_argument(
        "--html",
        metavar="FICHERO",
        help="escribir el mapa como HTML autocontenido (sin dependencias ni CDN)",
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
