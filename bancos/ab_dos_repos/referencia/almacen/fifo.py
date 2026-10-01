"""Stock, capas FIFO y costes. Recibe movimientos ya ordenados."""

from collections import deque
from decimal import Decimal

from .modelo import StockInsuficiente

CERO = Decimal("0")


def procesar(movimientos, hasta=None, periodo=(None, None)):
    """(capas, ventas): capas restantes por sku y, por sku, ingresos/coste/mermas
    de las salidas y bajas dentro de `periodo`. El coste FIFO usa toda la historia."""
    desde, fin = periodo
    capas = {}
    resultados = {}
    for m in movimientos:
        if hasta is not None and m.fecha > hasta:
            break
        cola = capas.setdefault(m.sku, deque())
        if m.tipo == "entrada":
            cola.append([m.cantidad, m.precio])
            continue
        hay = sum(c[0] for c in cola)
        if m.cantidad > hay:
            raise StockInsuficiente("linea %d: stock insuficiente de %s (hay %d, se piden %d)"
                                    % (m.linea, m.sku, hay, m.cantidad))
        pendiente, coste = m.cantidad, CERO
        while pendiente:
            capa = cola[0]
            usa = min(pendiente, capa[0])
            coste += usa * capa[1]
            capa[0] -= usa
            pendiente -= usa
            if not capa[0]:
                cola.popleft()
        dentro = (desde is None or m.fecha >= desde) and (fin is None or m.fecha <= fin)
        if not dentro:
            continue
        r = resultados.setdefault(m.sku, {"ingresos": CERO, "coste": CERO, "mermas": CERO})
        if m.tipo == "salida":
            r["ingresos"] += m.cantidad * m.precio
            r["coste"] += coste
        else:
            r["mermas"] += coste
    return capas, resultados


def stock(capas):
    return {sku: n for sku, n in ((s, sum(c[0] for c in cola)) for s, cola in capas.items()) if n}


def valor(capas):
    return {sku: (sum(c[0] for c in cola), sum((c[0] * c[1] for c in cola), CERO))
            for sku, cola in capas.items() if sum(c[0] for c in cola)}
