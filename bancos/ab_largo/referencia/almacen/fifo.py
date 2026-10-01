"""Stock, capas FIFO y costes por (sku, almacen). Recibe movimientos ya ordenados.

Un `Libro` aplica los movimientos de uno en uno: `procesar` lo recorre entero y el
kardex lo consulta tras cada paso, con la MISMA logica. Lineal: el total de cada cola
se lleva aparte (100.000 filas en menos de 5 s es contrato)."""

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
        if cantidad:
            self.capas.append([cantidad, coste])
            self.total += cantidad

    def saca(self, cantidad):
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


def _vacio():
    return {"ingresos": CERO, "coste": CERO, "mermas": CERO}


class Libro:
    def __init__(self, periodo=(None, None), agrupar="sku"):
        self.desde, self.fin = periodo
        self.agrupar = agrupar
        self.colas = {}
        self.consumos = {}       # linea de venta -> capas que consumio, pendientes de devolver
        self.precio_venta = {}
        self.ventas = {}         # clave (sku o almacen) -> ingresos/coste/mermas del periodo
        self.vendidas = {}       # sku -> salidas - devoluciones (unidades, toda la historia)

    def cola(self, sku, almacen):
        if (sku, almacen) not in self.colas:
            self.colas[(sku, almacen)] = _Cola()
        return self.colas[(sku, almacen)]

    def _cuenta(self, m):
        if (self.desde is None or m.fecha >= self.desde) and (self.fin is None or m.fecha <= self.fin):
            clave = m.sku if self.agrupar == "sku" else m.almacen
            return self.ventas.setdefault(clave, _vacio())
        return None

    def total_sku(self, sku):
        return sum(c.total for (s, _a), c in self.colas.items() if s == sku)

    def aplica(self, m):
        origen = self.cola(m.sku, m.almacen)
        if m.tipo == "entrada":
            origen.mete(m.cantidad, m.precio)
            return
        if m.tipo == "ajuste":
            if m.cantidad > origen.total:
                origen.mete(m.cantidad - origen.total, m.precio)
            elif m.cantidad < origen.total:
                consumidas = origen.saca(origen.total - m.cantidad)
                r = self._cuenta(m)
                if r is not None:
                    r["mermas"] += sum((c * u for c, u in consumidas), CERO)
            return
        if m.tipo == "devolucion":
            pendientes, vuelve, coste, falta = self.consumos[m.ref], [], CERO, m.cantidad
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
            self.vendidas[m.sku] = self.vendidas.get(m.sku, 0) - m.cantidad
            r = self._cuenta(m)
            if r is not None:
                r["ingresos"] -= m.cantidad * self.precio_venta[m.ref]
                r["coste"] -= coste
            return
        if m.cantidad > origen.total:
            raise StockInsuficiente("%s %d: stock insuficiente de %s (hay %d, se piden %d)"
                                    % (m.donde, m.linea, m.sku, origen.total, m.cantidad))
        consumidas = origen.saca(m.cantidad)
        coste = sum((c * u for c, u in consumidas), CERO)
        if m.tipo == "traspaso":
            destino = self.cola(m.sku, m.destino)
            for cantidad, unitario in consumidas:
                destino.mete(cantidad, unitario)
            return
        if m.tipo == "salida":
            self.consumos[m.linea] = list(consumidas)
            self.precio_venta[m.linea] = m.precio
            self.vendidas[m.sku] = self.vendidas.get(m.sku, 0) + m.cantidad
        r = self._cuenta(m)
        if r is None:
            return
        if m.tipo == "salida":
            r["ingresos"] += m.cantidad * m.precio
            r["coste"] += coste
        else:
            r["mermas"] += coste


def procesar(movimientos, hasta=None, periodo=(None, None), agrupar="sku"):
    libro = Libro(periodo, agrupar)
    for m in movimientos:
        if hasta is not None and m.fecha > hasta:
            break
        libro.aplica(m)
    return libro


def kardex(movimientos, sku):
    libro, filas = Libro(), []
    for m in movimientos:
        libro.aplica(m)
        if m.sku == sku:
            filas.append({"linea": m.linea, "fecha": m.fecha, "tipo": m.tipo,
                          "cantidad": m.cantidad, "saldo": libro.total_sku(sku)})
    return filas


def stock(colas, almacen=None, con_ceros=False):
    total = {}
    for (sku, alm), c in colas.items():
        if almacen is None or alm == almacen:
            total[sku] = total.get(sku, 0) + c.total
    return {s: n for s, n in total.items() if n or con_ceros}


def valor(colas, almacen=None):
    total = {}
    for (sku, alm), c in colas.items():
        if almacen is not None and alm != almacen:
            continue
        n, v = total.get(sku, (0, CERO))
        total[sku] = (n + c.total, v + sum((q * u for q, u in c.capas), CERO))
    return {s: nv for s, nv in total.items() if nv[0]}
