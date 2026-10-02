"""CSV -> movimientos validados y ordenados por fecha (estable)."""

import csv
import datetime
import os
from decimal import Decimal, InvalidOperation

from .modelo import TIPOS, EntradaInvalida, Movimiento

BASE = ["fecha", "sku", "tipo", "cantidad", "precio"]
CABECERAS = (BASE, BASE + ["almacen", "destino"], BASE + ["almacen", "destino", "ref"])


def _mal(n, motivo):
    return EntradaInvalida("linea %d: %s" % (n, motivo))


def _fecha(texto, n):
    try:
        datetime.date.fromisoformat(texto)
    except ValueError:
        raise _mal(n, "fecha invalida: %r" % texto) from None
    if len(texto) != 10:
        raise _mal(n, "fecha invalida: %r" % texto)
    return texto


def _nombre(texto, n, que):
    if not texto or " " in texto:
        raise _mal(n, "%s invalido" % que)
    return texto


def _fila(fila, n, ancho):
    if len(fila) != ancho:
        raise _mal(n, "se esperaban %d campos" % ancho)
    campos = [c.strip() for c in fila] + [""] * (8 - ancho)
    fecha, sku, tipo, cantidad, precio, almacen, destino, ref = campos
    fecha = _fecha(fecha, n)
    sku = _nombre(sku, n, "sku")
    if tipo not in TIPOS:
        raise _mal(n, "tipo invalido: %r" % tipo)
    try:
        cantidad = int(cantidad)
    except ValueError:
        raise _mal(n, "cantidad invalida: %r" % cantidad) from None
    if cantidad <= 0:
        raise _mal(n, "cantidad invalida: %r" % cantidad)
    try:
        precio = Decimal(precio)
    except InvalidOperation:
        raise _mal(n, "precio invalido: %r" % precio) from None
    if not precio.is_finite() or precio < 0:
        raise _mal(n, "precio invalido")
    almacen = _nombre(almacen, n, "almacen") if ancho > 5 else "central"
    if tipo == "traspaso":
        destino = _nombre(destino, n, "destino")
        if destino == almacen:
            raise _mal(n, "destino igual al origen")
    elif destino:
        raise _mal(n, "destino solo vale en un traspaso")
    if tipo == "devolucion":
        if not ref.isdigit():
            raise _mal(n, "devolucion invalida")
        ref = int(ref)
    elif ref:
        raise _mal(n, "ref solo vale en una devolucion")
    else:
        ref = 0
    return Movimiento(n, fecha, sku, tipo, cantidad, precio, almacen, destino, ref)


def _valida_devoluciones(movimientos):
    """Sin estado FIFO: solo el fichero. ref -> salida del mismo sku, no posterior,
    y lo devuelto de esa venta no supera lo vendido."""
    por_linea = {m.linea: m for m in movimientos}
    devuelto = {}
    for m in movimientos:
        if m.tipo != "devolucion":
            continue
        venta = por_linea.get(m.ref)
        if (venta is None or venta.tipo != "salida" or venta.sku != m.sku
                or (venta.fecha, venta.linea) > (m.fecha, m.linea)):
            raise _mal(m.linea, "devolucion invalida")
        devuelto[m.ref] = devuelto.get(m.ref, 0) + m.cantidad
        if devuelto[m.ref] > venta.cantidad:
            raise _mal(m.linea, "devolucion invalida")


def leer(ruta):
    if not os.path.isfile(ruta):
        raise EntradaInvalida("no existe: %s" % ruta)
    with open(ruta, encoding="utf-8", newline="") as fh:
        filas = list(csv.reader(fh))
    cabecera = [c.strip() for c in filas[0]] if filas else []
    if cabecera not in CABECERAS:
        raise EntradaInvalida("cabecera invalida")
    movimientos = [
        _fila(fila, n, len(cabecera))
        for n, fila in enumerate(filas[1:], start=2)
        if fila and any(c.strip() for c in fila)
    ]
    # sorted es estable: a igual fecha, el orden del fichero.
    movimientos.sort(key=lambda m: m.fecha)
    _valida_devoluciones(movimientos)
    return movimientos
