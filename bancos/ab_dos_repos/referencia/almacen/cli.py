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
    s.add_argument("--json", action="store_true")
    v = sub.add_parser("valoracion")
    v.add_argument("csv")
    v.add_argument("--json", action="store_true")
    m = sub.add_parser("margen")
    m.add_argument("csv")
    m.add_argument("--desde", type=_fecha)
    m.add_argument("--hasta", type=_fecha)
    m.add_argument("--json", action="store_true")
    return p


def main(argv=None):
    args = _parser().parse_args(argv)
    try:
        movimientos = lectura.leer(args.csv)
        if args.comando == "stock":
            capas, _ = fifo.procesar(movimientos, hasta=args.fecha)
            print(informes.stock(fifo.stock(capas), args.json))
        elif args.comando == "valoracion":
            capas, _ = fifo.procesar(movimientos)
            print(informes.valoracion(fifo.valor(capas), args.json))
        else:
            _, ventas = fifo.procesar(movimientos, periodo=(args.desde, args.hasta))
            print(informes.margen(ventas, args.json))
    except EntradaInvalida as e:
        print(str(e), file=sys.stderr)
        return 2
    except StockInsuficiente as e:
        print(str(e), file=sys.stderr)
        return 3
    return 0
