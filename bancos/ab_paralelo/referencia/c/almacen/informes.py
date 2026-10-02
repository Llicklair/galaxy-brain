"""Resultados -> texto o JSON. No calcula nada: solo da forma."""

import json
from decimal import ROUND_HALF_EVEN, Decimal


def importe(x):
    return str(Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN))


def stock(datos, como_json):
    if como_json:
        return json.dumps(dict(sorted(datos.items())))
    return "\n".join("%s %d" % (s, n) for s, n in sorted(datos.items())) or "(sin stock)"


def valoracion(datos, como_json):
    skus = {s: {"cantidad": n, "valor": importe(v)} for s, (n, v) in sorted(datos.items())}
    total = importe(sum((v for _n, v in datos.values()), Decimal("0")))
    if como_json:
        return json.dumps({"skus": skus, "total": total})
    lineas = ["%s %d %s" % (s, d["cantidad"], d["valor"]) for s, d in skus.items()]
    return "\n".join(lineas + ["total %s" % total])


def margen(datos, como_json):
    skus = {}
    tot = {"ingresos": Decimal("0"), "coste": Decimal("0"), "mermas": Decimal("0")}
    for s, r in sorted(datos.items()):
        m = r["ingresos"] - r["coste"] - r["mermas"]
        skus[s] = {"ingresos": importe(r["ingresos"]), "coste": importe(r["coste"]),
                   "mermas": importe(r["mermas"]), "margen": importe(m)}
        for k in tot:
            tot[k] += r[k]
    total = {k: importe(v) for k, v in tot.items()}
    total["margen"] = importe(tot["ingresos"] - tot["coste"] - tot["mermas"])
    if como_json:
        return json.dumps({"skus": skus, "total": total})
    lineas = ["%s ingresos=%s coste=%s mermas=%s margen=%s"
              % (s, d["ingresos"], d["coste"], d["mermas"], d["margen"]) for s, d in skus.items()]
    return "\n".join(lineas + ["total margen=%s" % total["margen"]])
