"""Resultados -> texto, JSON o CSV. No calcula nada: solo da forma."""

import json
from decimal import ROUND_HALF_UP, Decimal

CERO = Decimal("0")


def importe(x):
    return str(Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def stock(datos, como="texto"):
    filas = sorted(datos.items())
    if como == "json":
        return json.dumps(dict(filas))
    if como == "csv":
        return "\n".join(["sku,cantidad"] + ["%s,%d" % f for f in filas])
    return "\n".join("%s %d" % f for f in filas) or "(sin stock)"


def valoracion(datos, como="texto"):
    skus = {s: {"cantidad": n, "valor": importe(v)} for s, (n, v) in sorted(datos.items())}
    total = importe(sum((v for _n, v in datos.values()), CERO))
    if como == "json":
        return json.dumps({"skus": skus, "total": total})
    if como == "csv":
        return "\n".join(["sku,cantidad,valor"]
                         + ["%s,%d,%s" % (s, d["cantidad"], d["valor"]) for s, d in skus.items()]
                         + ["TOTAL,,%s" % total])
    lineas = ["%s %d %s" % (s, d["cantidad"], d["valor"]) for s, d in skus.items()]
    return "\n".join(lineas + ["total %s" % total])


def _cifras(r):
    return {"ingresos": importe(r["ingresos"]), "coste": importe(r["coste"]),
            "mermas": importe(r["mermas"]),
            "margen": importe(r["ingresos"] - r["coste"] - r["mermas"])}


def margen(datos, como="texto", grupo="skus", negativos=False):
    tot = {"ingresos": CERO, "coste": CERO, "mermas": CERO}
    grupos = {}
    for clave, r in sorted(datos.items()):
        for k in tot:
            tot[k] += r[k]
        if negativos and r["ingresos"] - r["coste"] - r["mermas"] >= 0:
            continue
        grupos[clave] = _cifras(r)
    total = _cifras(tot)
    if como == "json":
        return json.dumps({grupo: grupos, "total": total})
    lineas = ["%s ingresos=%s coste=%s mermas=%s margen=%s"
              % (s, d["ingresos"], d["coste"], d["mermas"], d["margen"]) for s, d in grupos.items()]
    return "\n".join(lineas + ["total margen=%s" % total["margen"]])


def movimientos(filas, como="texto"):
    if como == "json":
        return json.dumps(filas)
    return "\n".join("%(linea)d %(fecha)s %(tipo)s %(cantidad)d saldo=%(saldo)d" % f
                     for f in filas) or "(sin movimientos)"


def rotacion(datos, como="texto"):
    if como == "json":
        return json.dumps(dict(sorted(datos.items())))
    return "\n".join("%s vendidas=%d stock=%d" % (s, d["vendidas"], d["stock"])
                     for s, d in sorted(datos.items())) or "(sin ventas)"


def resumen(datos, como="texto"):
    if como == "json":
        return json.dumps(datos)
    return " ".join("%s=%s" % kv for kv in datos.items())
