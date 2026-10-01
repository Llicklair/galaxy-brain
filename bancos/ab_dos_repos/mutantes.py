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
    ("sin ordenar por fecha", "lectura.py",
     "return sorted(movimientos, key=lambda m: m.fecha)", "return movimientos"),
    ("orden no estable (entradas antes a igual fecha)", "lectura.py",
     "key=lambda m: m.fecha)", "key=lambda m: (m.fecha, m.tipo != 'entrada'))"),
    ("LIFO en vez de FIFO", "fifo.py",
     "capa = cola[0]", "capa = cola[-1]"),
    ("redondeo intermedio en el total", "informes.py",
     'total = importe(sum((v for _n, v in datos.values()), Decimal("0")))',
     'total = importe(sum((Decimal(importe(v)) for _n, v in datos.values()), Decimal("0")))'),
    ("traza ante entrada mala", "cli.py",
     "    except EntradaInvalida as e:\n        print(str(e), file=sys.stderr)\n        return 2\n",
     ""),
    ("el periodo recorta la historia FIFO", "fifo.py",
     "        hay = sum(c[0] for c in cola)",
     "        if not ((desde is None or m.fecha >= desde) and (fin is None or m.fecha <= fin)):\n"
     "            continue\n        hay = sum(c[0] for c in cola)"),
    ("la baja usa su precio", "fifo.py",
     'r["mermas"] += coste', 'r["mermas"] += m.cantidad * m.precio'),
    ("stock incluye los sku a cero", "fifo.py",
     "for s, cola in capas.items()) if n}", "for s, cola in capas.items())}"),
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
