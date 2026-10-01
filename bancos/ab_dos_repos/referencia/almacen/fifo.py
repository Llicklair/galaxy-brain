"""Stock, capas FIFO y costes por (sku, almacen). Recibe movimientos ya ordenados.

Lineal: el total de cada cola se lleva aparte, no se recalcula sumando capas en
cada movimiento (100.000 filas en menos de 5 s es contrato)."""

from collections import deque
from decimal import Decimal

from .modelo import StockInsuficiente

CERO = Decimal("0")


class _Cola:
    __slots__ = ("capas", "total")

    def __init__(self):
        self.capas = deque()
        self.total = 0

    def mete(self, cantidad, coste):
        self.capas.append([cantidad, coste])
        self.total += cantidad

    def saca(self, cantidad):
        """Las capas consumidas, en orden FIFO: [(cantidad, coste)]."""
        consumidas = []
        while cantidad:
            capa = self.capas[0]
            usa = min(cantidad, capa[0])
            consumidas.append((usa, capa[1]))
            capa[0] -= usa
            cantidad -= usa
            if not capa[0]:
                self.capas.popleft()
        self.total -= sum(c for c, _ in consumidas)
        return consumidas


def procesar(movimientos, hasta=None, periodo=(None, None)):
    """(colas, ventas): colas por (sku, almacen) y, por sku, ingresos/coste/mermas
    de lo que cae en `periodo`. El coste FIFO usa siempre toda la historia."""
    desde, fin = periodo
    colas = {}
    consumos = {}     # linea de venta -> capas que consumio, pendientes de devolver
    precio_venta = {}
    ventas = {}

    def cola(sku, almacen):
        if (sku, almacen) not in colas:
            colas[(sku, almacen)] = _Cola()
        return colas[(sku, almacen)]

    def cuenta(m):
        if (desde is None or m.fecha >= desde) and (fin is None or m.fecha <= fin):
            return ventas.setdefault(m.sku, {"ingresos": CERO, "coste": CERO, "mermas": CERO})
        return None

    for m in movimientos:
        if hasta is not None and m.fecha > hasta:
            break
        origen = cola(m.sku, m.almacen)
        if m.tipo == "entrada":
            origen.mete(m.cantidad, m.precio)
            continue
        if m.tipo == "devolucion":
            pendientes = consumos[m.ref]
            vuelve, coste, falta = [], CERO, m.cantidad
            while falta:
                cantidad, unitario = pendientes[-1]
                usa = min(falta, cantidad)
                vuelve.append((usa, unitario))
                coste += usa * unitario
                falta -= usa
                if usa == cantidad:
                    pendientes.pop()
                else:
                    pendientes[-1] = (cantidad - usa, unitario)
            for cantidad, unitario in vuelve:
                origen.mete(cantidad, unitario)
            r = cuenta(m)
            if r is not None:
                r["ingresos"] -= m.cantidad * precio_venta[m.ref]
                r["coste"] -= coste
            continue
        if m.cantidad > origen.total:
            raise StockInsuficiente("linea %d: stock insuficiente de %s (hay %d, se piden %d)"
                                    % (m.linea, m.sku, origen.total, m.cantidad))
        consumidas = origen.saca(m.cantidad)
        coste = sum((c * u for c, u in consumidas), CERO)
        if m.tipo == "traspaso":
            destino = cola(m.sku, m.destino)
            for cantidad, unitario in consumidas:
                destino.mete(cantidad, unitario)
            continue
        if m.tipo == "salida":
            consumos[m.linea] = list(consumidas)
            precio_venta[m.linea] = m.precio
        r = cuenta(m)
        if r is None:
            continue
        if m.tipo == "salida":
            r["ingresos"] += m.cantidad * m.precio
            r["coste"] += coste
        else:
            r["mermas"] += coste
    return colas, ventas


def stock(colas, almacen=None):
    total = {}
    for (sku, alm), c in colas.items():
        if almacen is None or alm == almacen:
            total[sku] = total.get(sku, 0) + c.total
    return {s: n for s, n in total.items() if n}


def valor(colas, almacen=None):
    total = {}
    for (sku, alm), c in colas.items():
        if almacen is not None and alm != almacen:
            continue
        n, v = total.get(sku, (0, CERO))
        total[sku] = (n + c.total, v + sum((q * u for q, u in c.capas), CERO))
    return {s: nv for s, nv in total.items() if nv[0]}
