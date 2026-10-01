"""CSV -> movimientos validados y ordenados por fecha (estable)."""

import csv
import datetime
import os
from decimal import Decimal, InvalidOperation

from .modelo import TIPOS, EntradaInvalida, Movimiento

CABECERA = ["fecha", "sku", "tipo", "cantidad", "precio"]


def _fecha(texto, n):
    try:
        datetime.date.fromisoformat(texto)
    except ValueError:
        raise EntradaInvalida("linea %d: fecha invalida: %r" % (n, texto)) from None
    if len(texto) != 10:
        raise EntradaInvalida("linea %d: fecha invalida: %r" % (n, texto))
    return texto


def leer(ruta):
    if not os.path.isfile(ruta):
        raise EntradaInvalida("no existe: %s" % ruta)
    with open(ruta, encoding="utf-8", newline="") as fh:
        filas = list(csv.reader(fh))
    if not filas or [c.strip() for c in filas[0]] != CABECERA:
        raise EntradaInvalida("cabecera invalida")
    movimientos = []
    for n, fila in enumerate(filas[1:], start=2):
        if not fila or all(not c.strip() for c in fila):
            continue
        if len(fila) != 5:
            raise EntradaInvalida("linea %d: se esperaban 5 campos" % n)
        fecha, sku, tipo, cantidad, precio = (c.strip() for c in fila)
        fecha = _fecha(fecha, n)
        if not sku or " " in sku:
            raise EntradaInvalida("linea %d: sku invalido" % n)
        if tipo not in TIPOS:
            raise EntradaInvalida("linea %d: tipo invalido: %r" % (n, tipo))
        try:
            cantidad = int(cantidad)
        except ValueError:
            raise EntradaInvalida("linea %d: cantidad invalida: %r" % (n, cantidad)) from None
        if cantidad <= 0:
            raise EntradaInvalida("linea %d: cantidad invalida: %r" % (n, cantidad))
        try:
            precio = Decimal(precio)
        except InvalidOperation:
            raise EntradaInvalida("linea %d: precio invalido: %r" % (n, precio)) from None
        if not precio.is_finite() or precio < 0:
            raise EntradaInvalida("linea %d: precio invalido" % n)
        movimientos.append(Movimiento(n, fecha, sku, tipo, cantidad, precio))
    # sorted es estable: a igual fecha, el orden del fichero.
    return sorted(movimientos, key=lambda m: m.fecha)
