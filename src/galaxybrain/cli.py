"""`gb` — la superficie de lectura.

Cinco comandos y ninguno mas. Cada comando nuevo aqui hay que justificarlo
contra la frase de SCOPE-v2: si no ayuda a saber donde peto y con que estado,
no entra.
"""

import argparse
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


def cmd_last(args):
    record = store.load(project=_project_filter(args))
    if record is None:
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
    report = graph.analyze(root, since=args.since)
    if args.json:
        emit(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        emit(render.render_graph(report, _style(args)))
    if args.gate:
        return _graph_gate(report)
    return 0


def _graph_gate(report):
    """Código de salida del --gate. Con --since, falla solo con ciclos NUEVOS;
    sin --since, estricto (cualquier ciclo). Si no se puede comparar la baseline,
    NO se bloquea (un falso positivo acaba en --no-verify) — se avisa por stderr."""
    if report["since"] is not None:
        if report["baseline_ok"] is False:
            sys.stderr.write(
                "[gb graph] no pude comparar con '%s'; no bloqueo.\n" % report["since"]
            )
            return 0
        return 1 if report["new_pairs"] else 0
    return 1 if report["cycles"] else 0


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
    graph_p.add_argument("--since", metavar="REF", help="comparar con esta ref git; --gate falla solo con ciclos NUEVOS")
    graph_p.set_defaults(func=cmd_graph)

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
