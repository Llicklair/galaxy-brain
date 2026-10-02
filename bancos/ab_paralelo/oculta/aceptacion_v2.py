"""Suite de aceptacion OCULTA del experimento A/B (con gb / sin gb).

Ningun agente la ve. Es de caja negra: solo `python -m almacen` y el JSON del
contrato de spec/SCOPE.md y spec/fase2.md, asi que juzga cualquier
implementacion que lo cumpla, se llamen como se llamen sus funciones.

    ALMACEN_REPO=<repo a juzgar> python -m pytest -q bancos/ab_dos_repos/oculta/aceptacion_oculta.py

Los tests de fase 1 comparan solo los campos de fase 1, para seguir siendo
validos despues de la fase 2 (que anade `mermas`).
"""

import json
import os
import subprocess
import sys

import pytest

REPO = os.environ.get("ALMACEN_REPO", "")

CABECERA = "fecha,sku,tipo,cantidad,precio\n"

#: Desordenado a proposito: la entrada barata del dia 5 viene DESPUES.
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
    assert r.returncode == 0, (r.returncode, r.stderr[-500:])
    return json.loads(r.stdout)


def sin_traza(r):
    assert "Traceback" not in r.stderr, r.stderr[-800:]


def campos(d, *claves):
    return {k: d[k] for k in claves}


# --- fase 1: stock --------------------------------------------------------


def test_stock_final(tmp_path):
    assert como_json(corre(tmp_path, BASE, "stock", "{csv}", "--json")) == {"A": 7, "B": 2}


def test_stock_a_fecha_procesa_por_fecha_no_por_linea(tmp_path):
    assert como_json(corre(tmp_path, BASE, "stock", "{csv}", "--fecha", "2026-01-15",
                           "--json")) == {"A": 15, "B": 3}


def test_stock_a_fecha_omite_los_sku_aun_sin_unidades(tmp_path):
    assert como_json(corre(tmp_path, BASE, "stock", "{csv}", "--fecha", "2026-01-07",
                           "--json")) == {"A": 5}


def test_stock_omite_los_sku_a_cero(tmp_path):
    csv_ = CABECERA + "2026-01-01,A,entrada,2,1\n2026-01-02,A,salida,2,3\n2026-01-01,B,entrada,1,1\n"
    assert como_json(corre(tmp_path, csv_, "stock", "{csv}", "--json")) == {"B": 1}


def test_stock_en_texto_funciona(tmp_path):
    r = corre(tmp_path, BASE, "stock", "{csv}")
    assert r.returncode == 0 and r.stdout.strip()


# --- fase 1: valoracion ---------------------------------------------------


def test_valoracion_fifo_con_entradas_desordenadas(tmp_path):
    """Las 8 vendidas consumen las 5 del dia 5 (a 1) y 3 del dia 10: quedan 7 a 2."""
    d = como_json(corre(tmp_path, BASE, "valoracion", "{csv}", "--json"))
    assert d["skus"]["A"] == {"cantidad": 7, "valor": "14.00"}
    assert d["skus"]["B"] == {"cantidad": 2, "valor": "20.67"}
    assert d["total"] == "34.67"


def test_valoracion_redondea_solo_al_final(tmp_path):
    csv_ = CABECERA + "2026-01-01,C,entrada,1,0.005\n2026-01-01,D,entrada,1,0.005\n"
    d = como_json(corre(tmp_path, csv_, "valoracion", "{csv}", "--json"))
    assert d["skus"]["C"]["valor"] == "0.01" and d["skus"]["D"]["valor"] == "0.01"
    assert d["total"] == "0.01"


def test_valoracion_sin_stock_es_vacia_y_total_cero(tmp_path):
    csv_ = CABECERA + "2026-01-01,A,entrada,2,1\n2026-01-02,A,salida,2,3\n"
    assert como_json(corre(tmp_path, csv_, "valoracion", "{csv}", "--json")) == {
        "skus": {}, "total": "0.00"}


def test_valoracion_en_texto_funciona(tmp_path):
    r = corre(tmp_path, BASE, "valoracion", "{csv}")
    assert r.returncode == 0 and r.stdout.strip()


# --- fase 1: margen -------------------------------------------------------


def test_margen_por_sku_con_coste_fifo(tmp_path):
    d = como_json(corre(tmp_path, BASE, "margen", "{csv}", "--json"))
    assert campos(d["skus"]["A"], "ingresos", "coste", "margen") == {
        "ingresos": "40.00", "coste": "11.00", "margen": "29.00"}
    assert campos(d["skus"]["B"], "ingresos", "coste", "margen") == {
        "ingresos": "20.00", "coste": "10.33", "margen": "9.67"}


def test_margen_total(tmp_path):
    d = como_json(corre(tmp_path, BASE, "margen", "{csv}", "--json"))
    assert campos(d["total"], "ingresos", "coste", "margen") == {
        "ingresos": "60.00", "coste": "21.33", "margen": "38.67"}


def test_margen_solo_lista_sku_con_salidas(tmp_path):
    csv_ = BASE + "2026-01-01,Z,entrada,4,1\n"
    assert set(como_json(corre(tmp_path, csv_, "margen", "{csv}", "--json"))["skus"]) == {"A", "B"}


def test_margen_en_texto_funciona(tmp_path):
    r = corre(tmp_path, BASE, "margen", "{csv}")
    assert r.returncode == 0 and r.stdout.strip()


# --- fase 1: orden ---------------------------------------------------------


def test_una_salida_listada_antes_pero_fechada_despues_es_valida(tmp_path):
    csv_ = CABECERA + "2026-01-09,A,salida,2,5\n2026-01-01,A,entrada,2,1\n"
    assert como_json(corre(tmp_path, csv_, "stock", "{csv}", "--json")) == {}


def test_a_igual_fecha_manda_el_orden_del_fichero(tmp_path):
    csv_ = CABECERA + "2026-01-01,A,salida,1,5\n2026-01-01,A,entrada,1,1\n"
    r = corre(tmp_path, csv_, "stock", "{csv}", "--json")
    assert r.returncode == 3, (r.returncode, r.stderr)
    assert "linea 2: stock insuficiente de A (hay 0, se piden 1)" in r.stderr
    sin_traza(r)


# --- fase 1: errores --------------------------------------------------------


def test_fichero_inexistente(tmp_path):
    if not REPO:
        pytest.skip("ALMACEN_REPO no apunta a ningun repo")
    r = subprocess.run([sys.executable, "-m", "almacen", "stock", str(tmp_path / "no.csv")],
                       cwd=REPO, env=dict(os.environ, PYTHONPATH=REPO, GB_DISABLE="1"),
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 2 and "no existe" in r.stderr
    sin_traza(r)


def test_cabecera_invalida(tmp_path):
    r = corre(tmp_path, "fecha,sku,cantidad\n2026-01-01,A,1\n", "stock", "{csv}")
    assert r.returncode == 2 and "cabecera invalida" in r.stderr
    sin_traza(r)


@pytest.mark.parametrize("fila", [
    "2026-01-01,A,entrada,x,1",          # cantidad no entera
    "2026-01-01,A,entrada,-3,1",         # cantidad negativa
    "2026-01-01,A,entrada,0,1",          # cantidad cero
    "2026-01-01,A,regalo,1,1",           # tipo invalido
    "2026-01-01,A,entrada,1,abc",        # precio no decimal
    "2026-01-01,A,entrada,1,-1",         # precio negativo
    "01/02/2026,A,entrada,1,1",          # fecha con otro formato
    "2026-01-01,,entrada,1,1",           # sku vacio
    "2026-01-01,A,entrada,1",            # campos de menos
])
def test_fila_mal_formada_dice_su_linea_sin_traza(tmp_path, fila):
    csv_ = CABECERA + "2026-01-01,OK,entrada,1,1\n" + fila + "\n"
    r = corre(tmp_path, csv_, "stock", "{csv}")
    assert r.returncode == 2, (r.returncode, r.stderr)
    assert r.stderr.strip().startswith("linea 3"), r.stderr
    sin_traza(r)


def test_stock_insuficiente(tmp_path):
    csv_ = CABECERA + "2026-01-01,A,entrada,2,1\n2026-01-02,A,salida,3,5\n"
    r = corre(tmp_path, csv_, "margen", "{csv}", "--json")
    assert r.returncode == 3
    assert "linea 3: stock insuficiente de A (hay 2, se piden 3)" in r.stderr
    sin_traza(r)


# --- fase 2: bajas ------------------------------------------------------------

BAJAS = CABECERA + (
    "2026-01-01,A,entrada,4,1\n"
    "2026-01-02,A,entrada,4,3\n"
    "2026-01-03,A,baja,5,99\n"          # precio ignorado: coste FIFO 4*1 + 1*3
    "2026-01-04,A,salida,2,10\n"         # coste 2*3
    "2026-01-01,M,entrada,2,4\n"
    "2026-01-05,M,baja,1,0\n"
)


@pytest.mark.fase2
def test_baja_consume_fifo_y_va_a_mermas(tmp_path):
    d = como_json(corre(tmp_path, BAJAS, "margen", "{csv}", "--json"))
    assert d["skus"]["A"] == {"ingresos": "20.00", "coste": "6.00", "mermas": "7.00",
                              "margen": "7.00"}


@pytest.mark.fase2
def test_un_sku_solo_con_bajas_sale_en_margen(tmp_path):
    d = como_json(corre(tmp_path, BAJAS, "margen", "{csv}", "--json"))
    assert d["skus"]["M"] == {"ingresos": "0.00", "coste": "0.00", "mermas": "4.00",
                              "margen": "-4.00"}
    assert d["total"] == {"ingresos": "20.00", "coste": "6.00", "mermas": "11.00",
                          "margen": "3.00"}


@pytest.mark.fase2
def test_las_bajas_restan_stock_y_valor(tmp_path):
    assert como_json(corre(tmp_path, BAJAS, "stock", "{csv}", "--json")) == {"A": 1, "M": 1}
    d = como_json(corre(tmp_path, BAJAS, "valoracion", "{csv}", "--json"))
    assert d["skus"]["A"] == {"cantidad": 1, "valor": "3.00"}


@pytest.mark.fase2
def test_baja_sin_stock_es_el_mismo_error(tmp_path):
    csv_ = CABECERA + "2026-01-01,A,entrada,1,1\n2026-01-02,A,baja,2,0\n"
    r = corre(tmp_path, csv_, "stock", "{csv}")
    assert r.returncode == 3
    assert "linea 3: stock insuficiente de A (hay 1, se piden 2)" in r.stderr
    sin_traza(r)


@pytest.mark.fase2
def test_tras_la_fase_2_el_margen_lleva_mermas_a_cero(tmp_path):
    d = como_json(corre(tmp_path, BASE, "margen", "{csv}", "--json"))
    assert d["skus"]["A"]["mermas"] == "0.00" and d["total"]["mermas"] == "0.00"


# --- fase 2: periodo -------------------------------------------------------------

PERIODO = CABECERA + (
    "2026-01-10,A,entrada,10,1\n"
    "2026-01-20,A,entrada,10,2\n"
    "2026-01-25,A,salida,10,5\n"         # consume las 10 a 1
    "2026-03-05,A,salida,5,5\n"          # consume 5 a 2: coste 10, no 5
)


@pytest.mark.fase2
def test_margen_desde_usa_el_coste_fifo_de_toda_la_historia(tmp_path):
    d = como_json(corre(tmp_path, PERIODO, "margen", "{csv}", "--desde", "2026-03-01", "--json"))
    assert campos(d["skus"]["A"], "ingresos", "coste", "margen") == {
        "ingresos": "25.00", "coste": "10.00", "margen": "15.00"}


@pytest.mark.fase2
def test_margen_hasta(tmp_path):
    d = como_json(corre(tmp_path, PERIODO, "margen", "{csv}", "--hasta", "2026-01-31", "--json"))
    assert campos(d["skus"]["A"], "ingresos", "coste") == {"ingresos": "50.00", "coste": "10.00"}


@pytest.mark.fase2
def test_el_periodo_incluye_los_dos_extremos(tmp_path):
    d = como_json(corre(tmp_path, PERIODO, "margen", "{csv}", "--desde", "2026-03-05",
                        "--hasta", "2026-03-05", "--json"))
    assert d["skus"]["A"]["ingresos"] == "25.00"


# --- fase 1: rendimiento -----------------------------------------------------------

#: 50.000 entradas de 1 y 50.000 salidas de 1: una implementacion que recalcula el
#: stock sumando todas las capas en cada salida es cuadratica (minutos).
GRANDE = CABECERA + "\n".join(["2026-01-01,A,entrada,1,1"] * 50000
                              + ["2026-06-01,A,salida,1,2"] * 50000) + "\n"


def test_cien_mil_movimientos_dan_el_resultado(tmp_path):
    d = como_json(corre(tmp_path, GRANDE, "margen", "{csv}", "--json"))
    assert campos(d["skus"]["A"], "ingresos", "coste") == {"ingresos": "100000.00",
                                                          "coste": "50000.00"}


def test_cien_mil_movimientos_en_tiempo(tmp_path):
    """SCOPE: menos de 5 s. Aqui 15 s de margen para no juzgar la maquina: lo que
    se caza es lo cuadratico, que tarda minutos."""
    import time

    inicio = time.time()
    r = corre(tmp_path, GRANDE, "stock", "{csv}", "--json")
    assert r.returncode == 0 and time.time() - inicio < 15, time.time() - inicio


# --- fase 3: almacenes y traspasos ---------------------------------------------------

H7 = "fecha,sku,tipo,cantidad,precio,almacen,destino\n"

#: norte recibe 1 a 5 el dia 1 (listado DESPUES, fechado antes) y luego el traspaso
#: de 3 desde central (2 a 1, 1 a 3), detras. La venta de 2 en norte cuesta 5 + 1.
TRASPASOS = H7 + (
    "2026-01-01,A,entrada,2,1,central,\n"
    "2026-01-02,A,entrada,2,3,central,\n"
    "2026-01-03,A,traspaso,3,0,central,norte\n"
    "2026-01-01,A,entrada,1,5,norte,\n"
    "2026-01-04,A,salida,2,10,norte,\n"
)


@pytest.mark.fase3
def test_stock_suma_todos_los_almacenes(tmp_path):
    assert como_json(corre(tmp_path, TRASPASOS, "stock", "{csv}", "--json")) == {"A": 3}


@pytest.mark.fase3
def test_stock_por_almacen(tmp_path):
    assert como_json(corre(tmp_path, TRASPASOS, "stock", "{csv}", "--almacen", "norte",
                           "--json")) == {"A": 2}
    assert como_json(corre(tmp_path, TRASPASOS, "stock", "{csv}", "--almacen", "central",
                           "--json")) == {"A": 1}
    assert como_json(corre(tmp_path, TRASPASOS, "stock", "{csv}", "--almacen", "sur",
                           "--json")) == {}


@pytest.mark.fase3
def test_el_traspaso_conserva_coste_y_entra_detras(tmp_path):
    d = como_json(corre(tmp_path, TRASPASOS, "valoracion", "{csv}", "--almacen", "norte", "--json"))
    assert d["skus"]["A"] == {"cantidad": 2, "valor": "4.00"}
    d = como_json(corre(tmp_path, TRASPASOS, "margen", "{csv}", "--json"))
    assert campos(d["skus"]["A"], "ingresos", "coste", "margen") == {
        "ingresos": "20.00", "coste": "6.00", "margen": "14.00"}


@pytest.mark.fase3
def test_valoracion_total_suma_almacenes(tmp_path):
    d = como_json(corre(tmp_path, TRASPASOS, "valoracion", "{csv}", "--json"))
    assert d["skus"]["A"] == {"cantidad": 3, "valor": "7.00"} and d["total"] == "7.00"


@pytest.mark.fase3
def test_una_salida_solo_consume_su_almacen(tmp_path):
    csv_ = H7 + "2026-01-01,A,entrada,5,1,central,\n2026-01-02,A,salida,1,9,norte,\n"
    r = corre(tmp_path, csv_, "stock", "{csv}")
    assert r.returncode == 3
    assert "linea 3: stock insuficiente de A (hay 0, se piden 1)" in r.stderr
    sin_traza(r)


@pytest.mark.fase3
def test_traspaso_sin_stock(tmp_path):
    csv_ = H7 + "2026-01-01,A,entrada,1,1,central,\n2026-01-02,A,traspaso,2,0,central,norte\n"
    r = corre(tmp_path, csv_, "stock", "{csv}")
    assert r.returncode == 3
    assert "linea 3: stock insuficiente de A (hay 1, se piden 2)" in r.stderr
    sin_traza(r)


@pytest.mark.fase3
@pytest.mark.parametrize("fila", [
    "2026-01-02,A,traspaso,1,0,central,",          # traspaso sin destino
    "2026-01-02,A,traspaso,1,0,central,central",   # destino igual al origen
    "2026-01-02,A,entrada,1,1,central,norte",      # destino fuera de un traspaso
    "2026-01-02,A,entrada,1,1,,",                  # almacen vacio
])
def test_fila_de_almacen_mal_formada(tmp_path, fila):
    r = corre(tmp_path, H7 + "2026-01-01,A,entrada,5,1,central,\n" + fila + "\n", "stock", "{csv}")
    assert r.returncode == 2 and r.stderr.strip().startswith("linea 3"), (r.returncode, r.stderr)
    sin_traza(r)


@pytest.mark.fase3
def test_el_formato_de_5_columnas_es_el_almacen_central(tmp_path):
    assert como_json(corre(tmp_path, BASE, "stock", "{csv}", "--almacen", "central",
                           "--json")) == {"A": 7, "B": 2}


# --- fase 4: devoluciones -------------------------------------------------------------

H8 = "fecha,sku,tipo,cantidad,precio,almacen,destino,ref\n"

#: La venta (linea 4) consume 2 a 1 y 1 a 3. Devolver 2 trae, de atras adelante,
#: 1 a 3 y 1 a 1 (coste 4), detras de la capa que quedaba (1 a 3): quedan 3 que
#: valen 7. En orden FIFO volverian 2 a 1 (coste 2) y valdrian 5. Sin ventas
#: despues a proposito: una venta posterior puede igualar los totales de los dos
#: ordenes por casualidad (le paso a la primera version de este test, 1-oct-2026).
DEVOL = H8 + (
    "2026-01-01,A,entrada,2,1,central,,\n"
    "2026-01-02,A,entrada,2,3,central,,\n"
    "2026-01-03,A,salida,3,10,central,,\n"
    "2026-01-05,A,devolucion,2,0,central,,4\n"
)


@pytest.mark.fase4
def test_la_devolucion_vuelve_al_coste_de_su_venta_en_orden_inverso(tmp_path):
    d = como_json(corre(tmp_path, DEVOL, "valoracion", "{csv}", "--json"))
    assert d["skus"]["A"] == {"cantidad": 3, "valor": "7.00"}


@pytest.mark.fase4
def test_la_devolucion_resta_ingresos_y_coste(tmp_path):
    d = como_json(corre(tmp_path, DEVOL, "margen", "{csv}", "--json"))
    assert campos(d["skus"]["A"], "ingresos", "coste", "margen") == {
        "ingresos": "10.00", "coste": "1.00", "margen": "9.00"}


@pytest.mark.fase4
def test_dos_devoluciones_siguen_hacia_atras(tmp_path):
    csv_ = H8 + (
        "2026-01-01,A,entrada,2,1,central,,\n"
        "2026-01-02,A,entrada,2,3,central,,\n"
        "2026-01-03,A,salida,3,10,central,,\n"
        "2026-01-04,A,devolucion,1,0,central,,4\n"     # trae 1 a 3
        "2026-01-05,A,devolucion,1,0,central,,4\n"     # trae 1 a 1
    )
    d = como_json(corre(tmp_path, csv_, "valoracion", "{csv}", "--json"))
    assert d["skus"]["A"] == {"cantidad": 3, "valor": "7.00"}
    d = como_json(corre(tmp_path, csv_, "margen", "{csv}", "--json"))
    assert campos(d["skus"]["A"], "ingresos", "coste") == {"ingresos": "10.00", "coste": "1.00"}


@pytest.mark.fase4
def test_la_devolucion_entra_en_el_almacen_de_su_fila(tmp_path):
    csv_ = DEVOL.replace("2026-01-05,A,devolucion,2,0,central,,4",
                         "2026-01-05,A,devolucion,2,0,norte,,4")
    assert como_json(corre(tmp_path, csv_, "stock", "{csv}", "--almacen", "norte",
                           "--json")) == {"A": 2}


@pytest.mark.fase4
def test_la_devolucion_cuenta_en_el_periodo_de_su_fecha(tmp_path):
    d = como_json(corre(tmp_path, DEVOL, "margen", "{csv}", "--desde", "2026-01-05", "--json"))
    assert campos(d["skus"]["A"], "ingresos", "coste", "margen") == {
        "ingresos": "-20.00", "coste": "-4.00", "margen": "-16.00"}


@pytest.mark.fase4
@pytest.mark.parametrize("fila", [
    "2026-01-05,A,devolucion,1,0,central,,2",      # ref a una entrada
    "2026-01-05,A,devolucion,4,0,central,,4",      # mas de lo vendido (3)
    "2026-01-05,B,devolucion,1,0,central,,4",      # ref a una venta de otro sku
    "2026-01-02,A,devolucion,1,0,central,,4",      # antes que su venta
    "2026-01-05,A,devolucion,1,0,central,,",       # sin ref
    "2026-01-05,A,devolucion,1,0,central,,99",     # ref a una linea que no existe
])
def test_devolucion_invalida(tmp_path, fila):
    csv_ = H8 + ("2026-01-01,A,entrada,2,1,central,,\n2026-01-02,A,entrada,2,3,central,,\n"
                 "2026-01-03,A,salida,3,10,central,,\n" + fila + "\n")
    r = corre(tmp_path, csv_, "stock", "{csv}")
    assert r.returncode == 2, (r.returncode, r.stderr)
    assert "linea 5: devolucion invalida" in r.stderr, r.stderr
    sin_traza(r)


@pytest.mark.fase4
def test_lo_devuelto_se_suma_entre_devoluciones(tmp_path):
    csv_ = H8 + ("2026-01-01,A,entrada,4,1,central,,\n2026-01-02,A,salida,3,10,central,,\n"
                 "2026-01-03,A,devolucion,2,0,central,,3\n2026-01-04,A,devolucion,2,0,central,,3\n")
    r = corre(tmp_path, csv_, "stock", "{csv}")
    assert r.returncode == 2 and "linea 5: devolucion invalida" in r.stderr, r.stderr


@pytest.mark.fase4
def test_a_igual_fecha_la_venta_tiene_que_ir_antes(tmp_path):
    csv_ = H8 + ("2026-01-01,A,entrada,4,1,central,,\n2026-01-02,A,devolucion,1,0,central,,4\n"
                 "2026-01-02,A,salida,3,10,central,,\n")
    r = corre(tmp_path, csv_, "stock", "{csv}")
    assert r.returncode == 2 and "linea 3: devolucion invalida" in r.stderr, r.stderr


@pytest.mark.fase4
def test_ref_fuera_de_una_devolucion_es_invalida(tmp_path):
    r = corre(tmp_path, H8 + "2026-01-01,A,entrada,4,1,central,,2\n", "stock", "{csv}")
    assert r.returncode == 2 and r.stderr.strip().startswith("linea 2"), r.stderr
