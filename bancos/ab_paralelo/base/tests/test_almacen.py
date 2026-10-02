"""Suite del proyecto: el contrato de README.md, por la CLI y por el motor FIFO."""

import json

import pytest

from almacen import cli, fifo, lectura

CABECERA = "fecha,sku,tipo,cantidad,precio\n"

#: Desordenado a proposito: la entrada barata del dia 5 viene DESPUES.
BASE = CABECERA + (
    "2026-01-10,A,entrada,10,2.00\n"
    "2026-01-05,A,entrada,5,1.00\n"
    "2026-01-20,A,salida,8,5.00\n"
    "2026-01-15,B,entrada,3,10.333\n"
    "2026-02-01,B,salida,1,20\n"
)


@pytest.fixture
def csv_(tmp_path):
    def escribe(texto):
        ruta = tmp_path / "mov.csv"
        ruta.write_text(texto, encoding="utf-8")
        return str(ruta)
    return escribe


def corre(capsys, *argv):
    rc = cli.main(list(argv))
    salida = capsys.readouterr()
    return rc, salida.out, salida.err


def como_json(capsys, *argv):
    rc, out, err = corre(capsys, *argv)
    assert rc == 0, err
    return json.loads(out)


def test_stock(capsys, csv_):
    assert como_json(capsys, "stock", csv_(BASE), "--json") == {"A": 7, "B": 2}


def test_stock_a_fecha(capsys, csv_):
    assert como_json(capsys, "stock", csv_(BASE), "--fecha", "2026-01-15", "--json") == {
        "A": 15, "B": 3}


def test_valoracion_fifo(capsys, csv_):
    d = como_json(capsys, "valoracion", csv_(BASE), "--json")
    assert d["skus"]["A"] == {"cantidad": 7, "valor": "14.00"}
    assert d["total"] == "34.67"


def test_valoracion_redondea_medio_centimo_hacia_arriba(capsys, csv_):
    d = como_json(capsys, "valoracion", csv_(CABECERA + "2026-01-01,C,entrada,1,0.005\n"), "--json")
    assert d["skus"]["C"]["valor"] == "0.01"


def test_margen(capsys, csv_):
    d = como_json(capsys, "margen", csv_(BASE), "--json")
    assert d["skus"]["A"] == {"ingresos": "40.00", "coste": "11.00", "mermas": "0.00",
                              "margen": "29.00"}
    assert d["total"]["margen"] == "38.67"


def test_stock_insuficiente_es_exit_3(capsys, csv_):
    rc, _, err = corre(capsys, "stock", csv_(CABECERA + "2026-01-01,A,salida,1,1\n"))
    assert rc == 3 and "stock insuficiente" in err


def test_fila_mala_es_exit_2(capsys, csv_):
    rc, _, err = corre(capsys, "stock", csv_(CABECERA + "2026-13-01,A,entrada,1,1\n"))
    assert rc == 2 and "linea 2" in err


def test_procesar_da_colas_y_ventas(csv_):
    colas, ventas = fifo.procesar(lectura.leer(csv_(BASE)))
    assert fifo.stock(colas) == {"A": 7, "B": 2}
    assert ventas["A"]["ingresos"] == 40
