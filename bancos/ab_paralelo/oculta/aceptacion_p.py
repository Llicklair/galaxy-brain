"""Suite OCULTA del A/B B (paralelo). Ningun agente la ve.

Caja negra (`python -m almacen`), como la de la v2, que se corre a su lado para
el comportamiento heredado. Marcas:
  b      el comando `resumen` (tarea B)
  c      el redondeo bancario (tarea C)
  union  lo que solo existe cuando B y C conviven: `resumen` con redondeo al par

    ALMACEN_REPO=<repo> python -m pytest -q -m "b or c or union" bancos/ab_paralelo/oculta/aceptacion_p.py
"""

import json
import os
import subprocess
import sys

import pytest

REPO = os.environ.get("ALMACEN_REPO", "")
CABECERA = "fecha,sku,tipo,cantidad,precio\n"
BASE = CABECERA + (
    "2026-01-10,A,entrada,10,2.00\n"
    "2026-01-05,A,entrada,5,1.00\n"
    "2026-01-20,A,salida,8,5.00\n"
    "2026-01-15,B,entrada,3,10.333\n"
    "2026-02-01,B,salida,1,20\n"
)


def corre(tmp_path, csv_texto, *args):
    if not REPO:
        pytest.skip("ALMACEN_REPO no apunta a ningun repo")
    ruta = tmp_path / "mov.csv"
    ruta.write_text(csv_texto, encoding="utf-8")
    entorno = dict(os.environ, PYTHONPATH=REPO, GB_DISABLE="1")
    argumentos = [a if a != "{csv}" else str(ruta) for a in args]
    return subprocess.run([sys.executable, "-m", "almacen", *argumentos], cwd=REPO,
                          env=entorno, capture_output=True, text=True, timeout=60)


def como_json(r):
    assert r.returncode == 0, (r.returncode, r.stderr[-800:])
    return json.loads(r.stdout)


# --- B: resumen -------------------------------------------------------------


@pytest.mark.b
def test_resumen_json(tmp_path):
    d = como_json(corre(tmp_path, BASE, "resumen", "{csv}", "--json"))
    assert d["skus"]["A"] == {"stock": 7, "valor": "14.00", "margen": "29.00"}
    assert d["skus"]["B"] == {"stock": 2, "valor": "20.67", "margen": "9.67"}
    assert d["total"] == {"valor": "34.67", "margen": "38.67"}


@pytest.mark.b
def test_resumen_incluye_sku_sin_stock_pero_con_ventas(tmp_path):
    csv_ = CABECERA + "2026-01-01,Z,entrada,2,1\n2026-01-02,Z,salida,2,3\n"
    d = como_json(corre(tmp_path, csv_, "resumen", "{csv}", "--json"))
    assert d["skus"]["Z"] == {"stock": 0, "valor": "0.00", "margen": "4.00"}


@pytest.mark.b
def test_resumen_en_texto(tmp_path):
    r = corre(tmp_path, BASE, "resumen", "{csv}")
    assert r.returncode == 0, r.stderr[-800:]
    lineas = r.stdout.strip().splitlines()
    assert lineas[0] == "A stock=7 valor=14.00 margen=29.00"
    assert lineas[-1] == "total valor=34.67 margen=38.67"


@pytest.mark.b
def test_resumen_con_fichero_malo_es_exit_2_sin_traza(tmp_path):
    r = corre(tmp_path, CABECERA + "2026-13-01,A,entrada,1,1\n", "resumen", "{csv}")
    assert r.returncode == 2 and "Traceback" not in r.stderr


# --- C: redondeo bancario ---------------------------------------------------


@pytest.mark.c
@pytest.mark.parametrize("precio, valor", [("0.005", "0.00"), ("0.015", "0.02"),
                                           ("0.025", "0.02"), ("0.035", "0.04")])
def test_valoracion_al_par(tmp_path, precio, valor):
    d = como_json(corre(tmp_path, CABECERA + "2026-01-01,C,entrada,1,%s\n" % precio,
                        "valoracion", "{csv}", "--json"))
    assert d["skus"]["C"]["valor"] == valor


@pytest.mark.c
def test_valoracion_redondea_solo_al_final_al_par(tmp_path):
    csv_ = CABECERA + "2026-01-01,C,entrada,1,0.005\n2026-01-01,D,entrada,1,0.005\n"
    d = como_json(corre(tmp_path, csv_, "valoracion", "{csv}", "--json"))
    assert d["skus"]["C"]["valor"] == "0.00" and d["total"] == "0.01"


@pytest.mark.c
def test_margen_al_par(tmp_path):
    csv_ = CABECERA + "2026-01-01,M,entrada,1,0\n2026-01-02,M,salida,1,0.125\n"
    d = como_json(corre(tmp_path, csv_, "margen", "{csv}", "--json"))
    assert d["skus"]["M"]["ingresos"] == "0.12"


# --- union: B y C juntos ----------------------------------------------------


@pytest.mark.union
def test_resumen_redondea_al_par(tmp_path):
    csv_ = CABECERA + "2026-01-01,R,entrada,1,0.125\n2026-01-02,S,entrada,1,0\n2026-01-03,S,salida,1,0.045\n"
    d = como_json(corre(tmp_path, csv_, "resumen", "{csv}", "--json"))
    assert d["skus"]["R"]["valor"] == "0.12"
    assert d["skus"]["S"]["margen"] == "0.04"
