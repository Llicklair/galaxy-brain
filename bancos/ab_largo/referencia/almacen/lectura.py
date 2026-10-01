"""CSV o JSON -> movimientos validados y ordenados por fecha (estable)."""

import csv
import datetime
import json
import os
from decimal import Decimal, InvalidOperation

from .modelo import TIPOS, EntradaInvalida, Movimiento

BASE = ["fecha", "sku", "tipo", "cantidad", "precio"]
CABECERAS = (BASE, BASE + ["almacen", "destino"], BASE + ["almacen", "destino", "ref"])
CAMPOS = BASE + ["almacen", "destino", "ref"]


def _mal(donde, n, motivo):
    return EntradaInvalida("%s %d: %s" % (donde, n, motivo))


def _nombre(texto, donde, n, que):
    if not texto or " " in texto:
        raise _mal(donde, n, "%s invalido" % que)
    return texto


def _fila(campos, n, donde, con_almacen):
    """`campos`: dict con las 8 claves como texto ('' si no vienen)."""
    fecha, sku, tipo = campos["fecha"], campos["sku"], campos["tipo"]
    try:
        datetime.date.fromisoformat(fecha)
    except ValueError:
        raise _mal(donde, n, "fecha invalida: %r" % fecha) from None
    if len(fecha) != 10:
        raise _mal(donde, n, "fecha invalida: %r" % fecha)
    sku = _nombre(sku, donde, n, "sku")
    if tipo not in TIPOS:
        raise _mal(donde, n, "tipo invalido: %r" % tipo)
    try:
        cantidad = int(campos["cantidad"])
    except ValueError:
        raise _mal(donde, n, "cantidad invalida: %r" % campos["cantidad"]) from None
    if cantidad < 0 or (cantidad == 0 and tipo != "ajuste"):
        raise _mal(donde, n, "cantidad invalida: %r" % cantidad)
    try:
        precio = Decimal(campos["precio"])
    except InvalidOperation:
        raise _mal(donde, n, "precio invalido: %r" % campos["precio"]) from None
    if not precio.is_finite() or precio < 0:
        raise _mal(donde, n, "precio invalido")
    almacen = _nombre(campos["almacen"], donde, n, "almacen") if con_almacen else "central"
    destino, ref = campos["destino"], campos["ref"]
    if tipo == "traspaso":
        destino = _nombre(destino, donde, n, "destino")
        if destino == almacen:
            raise _mal(donde, n, "destino igual al origen")
    elif destino:
        raise _mal(donde, n, "destino solo vale en un traspaso")
    if tipo == "devolucion":
        if not ref.isdigit():
            raise _mal(donde, n, "devolucion invalida")
        ref = int(ref)
    elif ref:
        raise _mal(donde, n, "ref solo vale en una devolucion")
    else:
        ref = 0
    return Movimiento(n, fecha, sku, tipo, cantidad, precio, almacen, destino, ref, donde)


def _valida_devoluciones(movimientos):
    por_linea = {m.linea: m for m in movimientos}
    devuelto = {}
    for m in movimientos:
        if m.tipo != "devolucion":
            continue
        venta = por_linea.get(m.ref)
        if (venta is None or venta.tipo != "salida" or venta.sku != m.sku
                or (venta.fecha, venta.linea) > (m.fecha, m.linea)):
            raise _mal(m.donde, m.linea, "devolucion invalida")
        devuelto[m.ref] = devuelto.get(m.ref, 0) + m.cantidad
        if devuelto[m.ref] > venta.cantidad:
            raise _mal(m.donde, m.linea, "devolucion invalida")


def _texto(valor):
    return "" if valor is None else str(valor).strip()


def _leer_csv(ruta):
    with open(ruta, encoding="utf-8", newline="") as fh:
        filas = list(csv.reader(fh))
    cabecera = [c.strip() for c in filas[0]] if filas else []
    if cabecera not in CABECERAS:
        raise EntradaInvalida("cabecera invalida")
    movimientos = []
    for n, fila in enumerate(filas[1:], start=2):
        if not fila or not any(c.strip() for c in fila):
            continue
        if len(fila) != len(cabecera):
            raise _mal("linea", n, "se esperaban %d campos" % len(cabecera))
        campos = dict.fromkeys(CAMPOS, "")
        campos.update(zip(cabecera, (c.strip() for c in fila)))
        movimientos.append(_fila(campos, n, "linea", len(cabecera) > 5))
    return movimientos


def _leer_json(ruta):
    try:
        with open(ruta, encoding="utf-8") as fh:
            datos = json.load(fh)
    except (ValueError, UnicodeDecodeError):
        raise EntradaInvalida("json invalido") from None
    if not isinstance(datos, list):
        raise EntradaInvalida("json invalido")
    movimientos = []
    for n, objeto in enumerate(datos, start=1):
        if not isinstance(objeto, dict):
            raise _mal("elemento", n, "se esperaba un objeto")
        campos = {k: _texto(objeto.get(k)) for k in CAMPOS}
        if not campos["almacen"]:
            campos["almacen"] = "central"
        movimientos.append(_fila(campos, n, "elemento", True))
    return movimientos


def leer(ruta):
    if not os.path.isfile(ruta):
        raise EntradaInvalida("no existe: %s" % ruta)
    movimientos = _leer_json(ruta) if ruta.lower().endswith(".json") else _leer_csv(ruta)
    movimientos.sort(key=lambda m: m.fecha)       # estable: a igual fecha, el orden del fichero
    _valida_devoluciones(movimientos)
    return movimientos
