"""argparse y orquestacion. El unico modulo que conoce a todos."""

import argparse
import datetime
import sys

from . import fifo, informes, lectura
from .modelo import EntradaInvalida, StockInsuficiente


def _fecha(texto):
    try:
        datetime.date.fromisoformat(texto)
    except ValueError:
        raise argparse.ArgumentTypeError("fecha invalida: %r" % texto) from None
    return texto


def _parser():
    p = argparse.ArgumentParser(prog="almacen")
    sub = p.add_subparsers(dest="comando", required=True)
    s = sub.add_parser("stock")
    s.add_argument("csv")
    s.add_argument("--fecha", type=_fecha)
    s.add_argument("--almacen")
    s.add_argument("--json", action="store_true")
    v = sub.add_parser("valoracion")
    v.add_argument("csv")
    v.add_argument("--almacen")
    v.add_argument("--json", action="store_true")
    m = sub.add_parser("margen")
    m.add_argument("csv")
    m.add_argument("--desde", type=_fecha)
    m.add_argument("--hasta", type=_fecha)
    m.add_argument("--json", action="store_true")
    r = sub.add_parser("resumen")
    r.add_argument("csv")
    r.add_argument("--json", action="store_true")
    return p


def _stock(args, movimientos):
    colas, _ = fifo.procesar(movimientos, hasta=args.fecha)
    return informes.stock(fifo.stock(colas, args.almacen), args.json)


def _valoracion(args, movimientos):
    colas, _ = fifo.procesar(movimientos)
    return informes.valoracion(fifo.valor(colas, args.almacen), args.json)


def _margen(args, movimientos):
    _, ventas = fifo.procesar(movimientos, periodo=(args.desde, args.hasta))
    return informes.margen(ventas, args.json)


def _resumen(args, movimientos):
    colas, ventas = fifo.procesar(movimientos)
    return informes.resumen(fifo.stock(colas), fifo.valor(colas), ventas, args.json)


COMANDOS = {
    "stock": _stock,
    "valoracion": _valoracion,
    "margen": _margen,
    "resumen": _resumen,
}


def main(argv=None):
    args = _parser().parse_args(argv)
    try:
        movimientos = lectura.leer(args.csv)
        print(COMANDOS[args.comando](args, movimientos))
    except EntradaInvalida as e:
        print(str(e), file=sys.stderr)
        return 2
    except StockInsuficiente as e:
        print(str(e), file=sys.stderr)
        return 3
    return 0
