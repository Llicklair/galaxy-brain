import json

from almacen import cli

CSV = ("fecha,sku,tipo,cantidad,precio\n"
       "2026-01-10,A,entrada,10,2.00\n"
       "2026-01-05,A,entrada,5,1.00\n"
       "2026-01-20,A,salida,8,5.00\n"
       "2026-01-15,B,entrada,3,10.333\n"
       "2026-02-01,B,salida,1,20\n")


def test_resumen_json(tmp_path, capsys):
    ruta = tmp_path / "m.csv"
    ruta.write_text(CSV, encoding="utf-8")
    assert cli.main(["resumen", str(ruta), "--json"]) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["skus"]["A"] == {"stock": 7, "valor": "14.00", "margen": "29.00"}
    assert d["total"] == {"valor": "34.67", "margen": "38.67"}


def test_resumen_texto(tmp_path, capsys):
    ruta = tmp_path / "m.csv"
    ruta.write_text(CSV, encoding="utf-8")
    assert cli.main(["resumen", str(ruta)]) == 0
    assert capsys.readouterr().out.splitlines()[-1] == "total valor=34.67 margen=38.67"
