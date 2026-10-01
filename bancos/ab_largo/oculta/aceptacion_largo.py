"""Suite OCULTA de las fases 5-14 del A/B de largo recorrido. Ningun agente la ve.

Smoke de cada peticion: que el trabajo se HIZO y da lo que pide la spec. Lo de las
fases 1-4 lo juzga la suite de la v2 (bancos/ab_dos_repos/oculta). Aqui lo que se
mide sobre todo es la forma del codigo y el coste por paso; esto solo asegura que
nadie "gana" por no hacer el trabajo.

    ALMACEN_REPO=<repo> python -m pytest -q -c bancos/ab_largo/oculta/pytest.ini bancos/ab_largo/oculta/aceptacion_largo.py
"""

import json
import os
import subprocess
import sys

import pytest

REPO = os.environ.get("ALMACEN_REPO", "")
CAB = "fecha,sku,tipo,cantidad,precio\n"
H7 = "fecha,sku,tipo,cantidad,precio,almacen,destino\n"
H8 = "fecha,sku,tipo,cantidad,precio,almacen,destino,ref\n"

BASE = CAB + (
    "2026-01-10,A,entrada,10,2.00\n"
    "2026-01-05,A,entrada,5,1.00\n"
    "2026-01-20,A,salida,8,5.00\n"
    "2026-01-15,B,entrada,3,10.333\n"
    "2026-02-01,B,salida,1,20\n"
)

TRASPASOS = H7 + (
    "2026-01-01,A,entrada,2,1,central,\n"
    "2026-01-02,A,entrada,2,3,central,\n"
    "2026-01-03,A,traspaso,3,0,central,norte\n"
    "2026-01-01,A,entrada,1,5,norte,\n"
    "2026-01-04,A,salida,2,10,norte,\n"
)

DEVOL = H8 + (
    "2026-01-01,A,entrada,2,1,central,,\n"
    "2026-01-02,A,entrada,2,3,central,,\n"
    "2026-01-03,A,salida,3,10,central,,\n"
    "2026-01-05,A,devolucion,2,0,central,,4\n"
)


def corre(tmp_path, texto, *args, nombre="mov.csv"):
    if not REPO:
        pytest.skip("ALMACEN_REPO no apunta a ningun repo")
    ruta = tmp_path / nombre
    ruta.write_text(texto, encoding="utf-8")
    argumentos = [a if a != "{f}" else str(ruta) for a in args]
    return subprocess.run([sys.executable, "-m", "almacen", *argumentos], cwd=REPO,
                          env=dict(os.environ, PYTHONPATH=REPO, GB_DISABLE="1"),
                          capture_output=True, text=True, timeout=60)


def js(r):
    assert r.returncode == 0, (r.returncode, r.stderr[-400:])
    return json.loads(r.stdout)


# --- fase 5 ----------------------------------------------------------------------

@pytest.mark.fase5
def test_valoracion_a_fecha(tmp_path):
    d = js(corre(tmp_path, BASE, "valoracion", "{f}", "--fecha", "2026-01-15", "--json"))
    assert d == {"skus": {"A": {"cantidad": 15, "valor": "25.00"},
                          "B": {"cantidad": 3, "valor": "31.00"}}, "total": "56.00"}


@pytest.mark.fase5
def test_valoracion_a_fecha_antes_de_todo_lo_demas(tmp_path):
    d = js(corre(tmp_path, BASE, "valoracion", "{f}", "--fecha", "2026-01-07", "--json"))
    assert d == {"skus": {"A": {"cantidad": 5, "valor": "5.00"}}, "total": "5.00"}


# --- fase 6 ----------------------------------------------------------------------

AJUSTES = H7 + (
    "2026-01-01,A,entrada,4,1,central,\n"
    "2026-01-02,A,entrada,4,3,central,\n"
    "2026-01-03,A,ajuste,5,0,central,\n"     # 8 -> 5: salen 3 a 1 (merma 3)
    "2026-01-04,A,ajuste,7,2,central,\n"     # 5 -> 7: entran 2 a 2
)


@pytest.mark.fase6
def test_ajuste_a_menos_es_merma_fifo_y_a_mas_una_capa_nueva(tmp_path):
    d = js(corre(tmp_path, AJUSTES, "valoracion", "{f}", "--json"))
    assert d["skus"]["A"] == {"cantidad": 7, "valor": "17.00"}
    d = js(corre(tmp_path, AJUSTES, "margen", "{f}", "--json"))
    assert d["skus"]["A"] == {"ingresos": "0.00", "coste": "0.00", "mermas": "3.00",
                              "margen": "-3.00"}


@pytest.mark.fase6
def test_ajuste_a_cero_es_valido_y_nunca_falta_stock(tmp_path):
    texto = AJUSTES + "2026-01-05,A,ajuste,0,0,central,\n2026-01-05,A,ajuste,2,5,norte,\n"
    assert js(corre(tmp_path, texto, "stock", "{f}", "--json")) == {"A": 2}


@pytest.mark.fase6
def test_ajuste_con_cantidad_negativa_es_invalido(tmp_path):
    r = corre(tmp_path, AJUSTES + "2026-01-05,A,ajuste,-1,0,central,\n", "stock", "{f}")
    assert r.returncode == 2 and r.stderr.strip().startswith("linea 6"), r.stderr


# --- fase 7 ----------------------------------------------------------------------

MINIMOS = CAB + ("2026-01-01,A,entrada,5,1\n2026-01-01,B,entrada,1,1\n"
                 "2026-01-01,C,entrada,2,1\n2026-01-02,C,salida,2,3\n")


@pytest.mark.fase7
def test_minimo_incluye_los_agotados(tmp_path):
    assert js(corre(tmp_path, MINIMOS, "stock", "{f}", "--minimo", "2", "--json")) == {"B": 1, "C": 0}
    assert js(corre(tmp_path, MINIMOS, "stock", "{f}", "--minimo", "0", "--json")) == {"C": 0}


@pytest.mark.fase7
def test_sin_minimo_no_cambia(tmp_path):
    assert js(corre(tmp_path, MINIMOS, "stock", "{f}", "--json")) == {"A": 5, "B": 1}


# --- fase 8 ----------------------------------------------------------------------

@pytest.mark.fase8
def test_kardex_en_orden_de_proceso_con_saldo_total(tmp_path):
    d = js(corre(tmp_path, TRASPASOS, "movimientos", "{f}", "--sku", "A", "--json"))
    assert [(x["linea"], x["tipo"], x["cantidad"], x["saldo"]) for x in d] == [
        (2, "entrada", 2, 2), (5, "entrada", 1, 3), (3, "entrada", 2, 5),
        (4, "traspaso", 3, 5), (6, "salida", 2, 3)]
    assert d[0]["fecha"] == "2026-01-01"


@pytest.mark.fase8
def test_kardex_de_un_sku_sin_movimientos(tmp_path):
    assert js(corre(tmp_path, TRASPASOS, "movimientos", "{f}", "--sku", "Z", "--json")) == []


# --- fase 9 ----------------------------------------------------------------------

@pytest.mark.fase9
def test_rotacion(tmp_path):
    assert js(corre(tmp_path, BASE, "rotacion", "{f}", "--json")) == {
        "A": {"vendidas": 8, "stock": 7}, "B": {"vendidas": 1, "stock": 2}}


@pytest.mark.fase9
def test_rotacion_descuenta_devoluciones(tmp_path):
    assert js(corre(tmp_path, DEVOL, "rotacion", "{f}", "--json")) == {
        "A": {"vendidas": 1, "stock": 3}}


# --- fase 10 ---------------------------------------------------------------------

def _como_json(texto_csv):
    lineas = texto_csv.strip().split("\n")
    cab = lineas[0].split(",")
    objetos = []
    for linea in lineas[1:]:
        o = dict(zip(cab, linea.split(",")))
        o["cantidad"] = int(o["cantidad"])
        objetos.append({k: v for k, v in o.items() if v != ""})
    return json.dumps(objetos)


@pytest.mark.fase10
def test_el_mismo_fichero_en_json_da_lo_mismo(tmp_path):
    assert js(corre(tmp_path, _como_json(BASE), "stock", "{f}", "--json",
                    nombre="mov.json")) == {"A": 7, "B": 2}
    d = js(corre(tmp_path, _como_json(DEVOL).replace('"ref": "4"', '"ref": "3"'), "valoracion",
                 "{f}", "--json", nombre="mov.json"))
    assert d["skus"]["A"] == {"cantidad": 3, "valor": "7.00"}


@pytest.mark.fase10
def test_json_invalido(tmp_path):
    for texto in ("{no es json", '{"a": 1}'):
        r = corre(tmp_path, texto, "stock", "{f}", nombre="mov.json")
        assert r.returncode == 2 and "json invalido" in r.stderr, r.stderr


@pytest.mark.fase10
def test_en_json_los_errores_dicen_elemento(tmp_path):
    r = corre(tmp_path, '[{"fecha": "2026-01-01", "sku": "A", "tipo": "entrada", '
                        '"cantidad": "x", "precio": 1}]', "stock", "{f}", nombre="mov.json")
    assert r.returncode == 2 and r.stderr.strip().startswith("elemento 1"), r.stderr
    r = corre(tmp_path, '[{"fecha": "2026-01-01", "sku": "A", "tipo": "entrada", "cantidad": 1, '
                        '"precio": 1}, {"fecha": "2026-01-02", "sku": "A", "tipo": "salida", '
                        '"cantidad": 2, "precio": 5}]', "stock", "{f}", nombre="mov.json")
    assert r.returncode == 3
    assert "elemento 2: stock insuficiente de A (hay 1, se piden 2)" in r.stderr


# --- fase 11 ---------------------------------------------------------------------

@pytest.mark.fase11
def test_exportar_stock_y_valoracion_a_csv(tmp_path):
    r = corre(tmp_path, BASE, "stock", "{f}", "--csv")
    assert r.returncode == 0 and r.stdout.strip().splitlines() == ["sku,cantidad", "A,7", "B,2"]
    r = corre(tmp_path, BASE, "valoracion", "{f}", "--csv")
    assert r.stdout.strip().splitlines() == ["sku,cantidad,valor", "A,7,14.00", "B,2,20.67",
                                             "TOTAL,,34.67"]


@pytest.mark.fase11
def test_csv_y_json_a_la_vez_es_un_error(tmp_path):
    assert corre(tmp_path, BASE, "stock", "{f}", "--csv", "--json").returncode == 2


# --- fases 12 y 13 ----------------------------------------------------------------

POR_ALMACEN = TRASPASOS + "2026-01-05,A,baja,1,0,central,\n"


@pytest.mark.fase12
def test_margen_por_almacen(tmp_path):
    d = js(corre(tmp_path, POR_ALMACEN, "margen", "{f}", "--por", "almacen", "--json"))
    assert d["almacenes"] == {
        "norte": {"ingresos": "20.00", "coste": "6.00", "mermas": "0.00", "margen": "14.00"},
        "central": {"ingresos": "0.00", "coste": "0.00", "mermas": "3.00", "margen": "-3.00"}}
    assert d["total"]["margen"] == "11.00"


@pytest.mark.fase12
def test_por_sku_sigue_igual(tmp_path):
    d = js(corre(tmp_path, POR_ALMACEN, "margen", "{f}", "--por", "sku", "--json"))
    assert d["skus"]["A"]["margen"] == "11.00"


@pytest.mark.fase13
def test_negativos_filtra_el_detalle_y_no_el_total(tmp_path):
    d = js(corre(tmp_path, POR_ALMACEN, "margen", "{f}", "--por", "almacen", "--negativos", "--json"))
    assert list(d["almacenes"]) == ["central"] and d["total"]["margen"] == "11.00"
    d = js(corre(tmp_path, POR_ALMACEN, "margen", "{f}", "--negativos", "--json"))
    assert d["skus"] == {} and d["total"]["margen"] == "11.00"


# --- fase 14 ---------------------------------------------------------------------

@pytest.mark.fase14
def test_resumen(tmp_path):
    assert js(corre(tmp_path, BASE, "resumen", "{f}", "--json")) == {
        "skus": 2, "unidades": 9, "valor": "34.67", "ingresos": "60.00", "margen": "38.67"}
