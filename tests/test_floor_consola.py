"""`gb floor` avisa de los lenguajes del proyecto cuya consola no esta puesta.

Pedido el 24-sep-2026: un repo JS sin NODE_OPTIONS se queda sin capturas y
solo `gb status` lo decia — que es mirarlo solo si ya sabes que mirar. floor es
lo que se corre al llegar a un proyecto, asi que el aviso va ahi. Informa: no
es un nivel, no mueve el siguiente paso ni cuenta en «sin cubrir».
"""

from galaxybrain import floor, render


def _proyecto_js(tmp_path):
    (tmp_path / "app.js").write_text("function main() { return 1; }\n", encoding="utf-8")
    return str(tmp_path)


def test_un_repo_js_sin_node_options_sale_en_el_aviso(tmp_path, monkeypatch):
    monkeypatch.delenv("NODE_OPTIONS", raising=False)
    report = floor.analyze(_proyecto_js(tmp_path))
    langs = {f["lenguaje"]: f for f in report["consola"]}
    assert set(langs) == {"js"}, langs  # python no: no hay ni un .py
    assert langs["js"]["armado"] is False
    texto = render.render_floor(report, lambda s, *_: s)
    assert "gb on --lenguajes" in texto


def test_armado_no_sale(tmp_path, monkeypatch):
    monkeypatch.setenv("NODE_OPTIONS", "--require /x/gb-hook.js")
    report = floor.analyze(_proyecto_js(tmp_path))
    assert report["consola"] == []
    assert "Consola de errores" not in render.render_floor(report, lambda s, *_: s)


def test_el_aviso_no_es_un_nivel(tmp_path, monkeypatch):
    monkeypatch.delenv("NODE_OPTIONS", raising=False)
    report = floor.analyze(_proyecto_js(tmp_path))
    assert all(nivel["key"] != "consola" for nivel in report["levels"])


def test_go_dice_como_se_arma_al_invocar(tmp_path):
    (tmp_path / "main.go").write_text("package main\n\nfunc main() {}\n", encoding="utf-8")
    report = floor.analyze(str(tmp_path))
    langs = {f["lenguaje"]: f for f in report["consola"]}
    assert langs["go"]["armado"] is None
    assert "gb-run.py go run" in render.render_floor(report, lambda s, *_: s)
