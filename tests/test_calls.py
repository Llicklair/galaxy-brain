"""`gb calls`: quien llama a quien, con fichero:linea — la pieza que cubria una
herramienta externa (GitNexus) y ahora sale del grafo propio.

Lo que se prueba es el contrato del criterio de fase: llamantes y llamados con
su sitio, onda por niveles, ambiguedad devuelta como material (todas las
coincidencias, no un error) y un hook que calla cuando no tiene nada que decir.
"""

import io
import json
import textwrap

from galaxybrain import cli, symbols


def _proyecto(tmp_path):
    (tmp_path / "app.py").write_text(textwrap.dedent('''\
        from lib import ayuda

        def main():
            """Punto de entrada."""
            ayuda()
            interno()

        def interno():
            pass
        '''), encoding="utf-8")
    (tmp_path / "lib.py").write_text(textwrap.dedent('''\
        def ayuda():
            """Una mano."""
            base()

        def base():
            pass
        '''), encoding="utf-8")
    return str(tmp_path)


# --- fichero:linea en el indice ----------------------------------------------


def test_cada_simbolo_lleva_fichero_y_linea(tmp_path):
    report = symbols.analyze(_proyecto(tmp_path))

    nodos = {n["qual"]: n for n in report["nodes"]}
    assert nodos["app.main"]["file"] == "app.py"
    assert nodos["app.main"]["line"] == 3
    assert nodos["lib"]["file"] == "lib.py"
    assert nodos["lib"]["line"] == 1


# --- la consulta -------------------------------------------------------------


def test_llamantes_y_llamados_con_su_sitio(tmp_path):
    report = symbols.analyze(_proyecto(tmp_path))

    res = symbols.calls(report, "ayuda")
    assert [m["symbol"]["qual"] for m in res["matches"]] == ["lib.ayuda"]
    m = res["matches"][0]
    assert [(f["qual"], f["file"]) for f in m["callers"]] == [("app.main", "app.py")]
    assert [f["qual"] for f in m["callees"]] == ["lib.base"]


def test_la_onda_sigue_niveles(tmp_path):
    """depth=2: el que llama al que llama, marcado con su nivel — el radio de
    la onda de un cambio, no una lista plana que mezcla cercania."""
    report = symbols.analyze(_proyecto(tmp_path))

    res = symbols.calls(report, "base", depth=2)
    llamantes = res["matches"][0]["callers"]
    assert [(f["qual"], f["depth"]) for f in llamantes] == [
        ("lib.ayuda", 1), ("app.main", 2),
    ]


def test_nombre_ambiguo_devuelve_todas_las_coincidencias(tmp_path):
    """Ambiguo no es error: es material. Quien pregunta decide cual era."""
    root = _proyecto(tmp_path)
    (tmp_path / "otro.py").write_text("def ayuda():\n    pass\n", encoding="utf-8")

    report = symbols.analyze(root)
    res = symbols.calls(report, "ayuda")
    assert [m["symbol"]["qual"] for m in res["matches"]] == ["lib.ayuda", "otro.ayuda"]


def test_desconocido_es_lista_vacia_no_error(tmp_path):
    report = symbols.analyze(_proyecto(tmp_path))

    assert symbols.calls(report, "no_existe")["matches"] == []


# --- relacionados: lo que alimenta el hook -----------------------------------


def test_relacionados_casa_el_nombre_dentro_de_un_patron(tmp_path):
    """El texto es un patron de Grep, no Python: se tokeniza y se casa por nombre."""
    report = symbols.analyze(_proyecto(tmp_path))

    fichas = symbols.relacionados(report, r"def ayuda\(")
    assert [f["qual"] for f in fichas] == ["lib.ayuda"]
    assert fichas[0]["callers"] == 1
    assert fichas[0]["callees"] == 1
    assert fichas[0]["file"] == "lib.py"


def test_relacionados_calla_sin_coincidencias(tmp_path):
    report = symbols.analyze(_proyecto(tmp_path))

    assert symbols.relacionados(report, "zzz_nada_de_esto") == []


# --- el hook entero, por el CLI ----------------------------------------------


def test_el_hook_calla_cuando_no_hay_nada(tmp_path, monkeypatch, capsys):
    _proyecto(tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(
        {"tool_input": {"pattern": "zzz_nada"}, "cwd": str(tmp_path)}
    )))

    assert cli.main(["calls", "--hook"]) == 0
    assert capsys.readouterr().out == ""


def test_el_hook_devuelve_ficha_con_sitio_y_cuentas(tmp_path, monkeypatch, capsys):
    _proyecto(tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(
        {"tool_input": {"pattern": "ayuda"}, "cwd": str(tmp_path)}
    )))

    assert cli.main(["calls", "--hook"]) == 0
    salida = capsys.readouterr().out
    assert "lib.ayuda" in salida
    assert "lib.py:1" in salida
    assert "1 le llaman" in salida


def test_el_hook_no_revienta_con_stdin_roto(monkeypatch, capsys):
    """Contrato: el hook nunca puede romper la busqueda que lo dispara."""
    monkeypatch.setattr("sys.stdin", io.StringIO("esto no es json"))

    assert cli.main(["calls", "--hook"]) == 0
    assert capsys.readouterr().out == ""
