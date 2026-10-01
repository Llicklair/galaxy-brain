"""El control de la suite oculta: cada error tipico sembrado en la referencia
tiene que tumbarla. Una suite que no muerde no puede juzgar a nadie.

    python bancos/ab_dos_repos/mutantes.py

Un mutante que sobrevive es un hueco de la suite oculta, no del agente: se
arregla la suite ANTES de lanzar ningun experimento.
"""

import os
import shutil
import subprocess
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))

#: (nombre, fichero, texto original, texto mutado)
MUTANTES = [
    # --- fases 1 y 2 ---
    ("sin ordenar por fecha", "lectura.py",
     "movimientos.sort(key=lambda m: m.fecha)", "pass"),
    ("orden no estable (entradas antes a igual fecha)", "lectura.py",
     "movimientos.sort(key=lambda m: m.fecha)",
     "movimientos.sort(key=lambda m: (m.fecha, m.tipo != 'entrada'))"),
    ("LIFO en vez de FIFO", "fifo.py",
     "capa = self.capas[0]", "capa = self.capas[-1]"),
    ("redondeo intermedio en el total", "informes.py",
     'total = importe(sum((v for _n, v in datos.values()), Decimal("0")))',
     'total = importe(sum((Decimal(importe(v)) for _n, v in datos.values()), Decimal("0")))'),
    ("traza ante entrada mala", "cli.py",
     "    except EntradaInvalida as e:\n        print(str(e), file=sys.stderr)\n        return 2\n",
     ""),
    ("el periodo recorta la historia FIFO", "fifo.py",
     "        if m.cantidad > origen.total:",
     "        if m.tipo != 'traspaso' and not ((desde is None or m.fecha >= desde)"
     " and (fin is None or m.fecha <= fin)):\n            continue\n"
     "        if m.cantidad > origen.total:"),
    ("la baja usa su precio", "fifo.py",
     'r["mermas"] += coste', 'r["mermas"] += m.cantidad * m.precio'),
    ("stock incluye los sku a cero", "fifo.py",
     "return {s: n for s, n in total.items() if n}", "return dict(total)"),
    # --- rendimiento ---
    ("stock recalculado sumando capas (cuadratico)", "fifo.py",
     "        if m.cantidad > origen.total:",
     "        origen.total = sum(c[0] for c in origen.capas)\n"
     "        if m.cantidad > origen.total:"),
    # --- fase 3 ---
    ("el traspaso pierde el coste de cada capa", "fifo.py",
     "                destino.mete(cantidad, unitario)",
     "                destino.mete(cantidad, consumidas[0][1])"),
    ("el traspaso entra delante", "fifo.py",
     "                destino.mete(cantidad, unitario)",
     "                destino.capas.appendleft([cantidad, unitario])\n"
     "                destino.total += cantidad"),
    ("--almacen ignorado", "fifo.py",
     "        if almacen is None or alm == almacen:", "        if True:"),
    ("destino admitido fuera de un traspaso", "lectura.py",
     "    elif destino:", "    elif False:"),
    # --- fase 4 ---
    ("la devolucion vuelve en orden FIFO", "fifo.py",
     "                cantidad, unitario = pendientes[-1]\n",
     "                cantidad, unitario = pendientes[0]\n"
     "                pendientes.append(pendientes.pop(0))\n"),
    ("la devolucion no resta coste", "fifo.py",
     '                r["coste"] -= coste', "                pass"),
    ("lo devuelto no se suma entre devoluciones", "lectura.py",
     "devuelto[m.ref] = devuelto.get(m.ref, 0) + m.cantidad",
     "devuelto[m.ref] = m.cantidad"),
]


def suite(repo):
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider",
         "-c", os.path.join(AQUI, "oculta", "pytest.ini"),
         os.path.join(AQUI, "oculta", "aceptacion_oculta.py")],
        env=dict(os.environ, ALMACEN_REPO=repo), capture_output=True, text=True)


def main():
    base = suite(os.path.join(AQUI, "referencia"))
    if base.returncode != 0:
        print("la referencia NO pasa la suite oculta: no hay control posible")
        print(base.stdout[-1500:])
        return 1
    print("referencia: suite oculta en verde")
    vivos = 0
    for nombre, fichero, antes, despues in MUTANTES:
        tmp = tempfile.mkdtemp()
        try:
            shutil.copytree(os.path.join(AQUI, "referencia"), os.path.join(tmp, "r"))
            ruta = os.path.join(tmp, "r", "almacen", fichero)
            texto = open(ruta, encoding="utf-8").read()
            if antes not in texto:
                print("  ?? %-48s el texto a mutar no esta (mutante roto)" % nombre)
                vivos += 1
                continue
            open(ruta, "w", encoding="utf-8").write(texto.replace(antes, despues, 1))
            muere = suite(os.path.join(tmp, "r")).returncode != 0
            print("  %s %s" % ("muere " if muere else "VIVE  ", nombre))
            vivos += not muere
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    print("%d de %d mutantes mueren" % (len(MUTANTES) - vivos, len(MUTANTES)))
    return 1 if vivos else 0


if __name__ == "__main__":
    sys.exit(main())
