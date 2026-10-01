"""argparse y orquestacion. El unico modulo que conoce a todos."""

import argparse
import datetime
import sys
from decimal import Decimal

from . import fifo, informes, lectura
from .modelo import EntradaInvalida, StockInsuficiente


def _fecha(texto):
    try:
        datetime.date.fromisoformat(texto)
    except ValueError:
        raise argparse.ArgumentTypeError("fecha invalida: %r" % texto) from None
    return texto


def _minimo(texto):
    n = int(texto)
    if n < 0:
        raise argparse.ArgumentTypeError("minimo invalido")
    return n


def _parser():
    p = argparse.ArgumentParser(prog="almacen")
    sub = p.add_subparsers(dest="comando", required=True)

    def comando(nombre, csv_=False):
        c = sub.add_parser(nombre)
        c.add_argument("csv")
        formato = c.add_mutually_exclusive_group()
        formato.add_argument("--json", action="store_true")
        if csv_:
            formato.add_argument("--csv", dest="como_csv", action="store_true")
        return c

    s = comando("stock", csv_=True)
    s.add_argument("--fecha", type=_fecha)
    s.add_argument("--almacen")
    s.add_argument("--minimo", type=_minimo)
    v = comando("valoracion", csv_=True)
    v.add_argument("--fecha", type=_fecha)
    v.add_argument("--almacen")
    m = comando("margen")
    m.add_argument("--desde", type=_fecha)
    m.add_argument("--hasta", type=_fecha)
    m.add_argument("--por", choices=("sku", "almacen"), default="sku")
    m.add_argument("--negativos", action="store_true")
    k = comando("movimientos")
    k.add_argument("--sku", required=True)
    comando("rotacion")
    comando("resumen")
    return p


def _como(args):
    if getattr(args, "como_csv", False):
        return "csv"
    return "json" if args.json else "texto"


def _ejecuta(args):
    movimientos = lectura.leer(args.csv)
    como = _como(args)
    if args.comando == "stock":
        libro = fifo.procesar(movimientos, hasta=args.fecha)
        datos = fifo.stock(libro.colas, args.almacen, con_ceros=args.minimo is not None)
        if args.minimo is not None:
            datos = {s: n for s, n in datos.items() if n <= args.minimo}
        return informes.stock(datos, como)
    if args.comando == "valoracion":
        libro = fifo.procesar(movimientos, hasta=args.fecha)
        return informes.valoracion(fifo.valor(libro.colas, args.almacen), como)
    if args.comando == "margen":
        libro = fifo.procesar(movimientos, periodo=(args.desde, args.hasta), agrupar=args.por)
        grupo = "skus" if args.por == "sku" else "almacenes"
        return informes.margen(libro.ventas, como, grupo, args.negativos)
    if args.comando == "movimientos":
        return informes.movimientos(fifo.kardex(movimientos, args.sku), como)
    libro = fifo.procesar(movimientos)
    if args.comando == "rotacion":
        stock = fifo.stock(libro.colas, con_ceros=True)
        datos = {s: {"vendidas": n, "stock": stock.get(s, 0)} for s, n in libro.vendidas.items()}
        return informes.rotacion(datos, como)
    valores = fifo.valor(libro.colas)
    ventas = list(libro.ventas.values())
    ingresos = sum((r["ingresos"] for r in ventas), Decimal("0"))
    margen = sum((r["ingresos"] - r["coste"] - r["mermas"] for r in ventas), Decimal("0"))
    return informes.resumen({
        "skus": len(valores), "unidades": sum(n for n, _v in valores.values()),
        "valor": informes.importe(sum((v for _n, v in valores.values()), Decimal("0"))),
        "ingresos": informes.importe(ingresos), "margen": informes.importe(margen),
    }, como)


def main(argv=None):
    args = _parser().parse_args(argv)
    try:
        print(_ejecuta(args))
    except EntradaInvalida as e:
        print(str(e), file=sys.stderr)
        return 2
    except StockInsuficiente as e:
        print(str(e), file=sys.stderr)
        return 3
    return 0
