"""`gb dead`: candidatos a codigo muerto — proxies con sus limites declarados."""

import subprocess
import sys

from galaxybrain import graph, huerfanos, symbols


def _proyecto(tmp_path):
    raiz = tmp_path / "p"
    raiz.mkdir()
    (raiz / "calc.py").write_text(
        "def suma(a, b):\n    return a + b\n\n"
        "def nadie_me_llama(x):\n    return x\n", encoding="utf-8")
    (raiz / "uso.py").write_text(
        "from calc import suma\n\n\ndef main():\n    return suma(1, 2)\n",
        encoding="utf-8")
    (raiz / "isla.py").write_text("def sola():\n    return 1\n", encoding="utf-8")
    return str(raiz)


def _dead(raiz):
    informe = symbols.analyze(raiz)
    _n, aristas, _e = graph.build_graph(raiz, graph.DEFAULT_SKIP)
    return huerfanos.analyze(informe, aristas)


def test_el_simbolo_sin_llamantes_sale_y_el_llamado_no(tmp_path):
    report = _dead(_proyecto(tmp_path))
    quals = [s["qual"] for s in report["sin_llamantes"]]
    assert "calc.nadie_me_llama" in quals
    assert "calc.suma" not in quals          # tiene llamante: no es candidato


def test_el_modulo_que_nadie_importa_sale_y_el_importado_no(tmp_path):
    report = _dead(_proyecto(tmp_path))
    modulos = [m["module"] for m in report["modulos_huerfanos"]]
    assert "isla" in modulos
    assert "calc" not in modulos             # uso.py lo importa


def test_main_no_es_candidato_lo_invoca_el_runtime(tmp_path):
    report = _dead(_proyecto(tmp_path))
    quals = [s["qual"] for s in report["sin_llamantes"]]
    assert "uso.main" not in quals


def test_los_tests_no_son_candidatos(tmp_path):
    raiz = tmp_path / "p"
    raiz.mkdir()
    (raiz / "calc.py").write_text("def suma(a, b):\n    return a + b\n", encoding="utf-8")
    (raiz / "test_calc.py").write_text(
        "from calc import suma\n\n\ndef test_suma():\n    assert suma(1, 1) == 2\n",
        encoding="utf-8")
    report = _dead(str(raiz))
    quals = [s["qual"] for s in report["sin_llamantes"]]
    assert not any("test" in q for q in quals)


def test_usado_como_valor_no_es_candidato(tmp_path):
    raiz = tmp_path / "p"
    raiz.mkdir()
    (raiz / "calc.py").write_text(
        "def handler(x):\n    return x\n\n\nTABLA = {\"x\": handler}\n",
        encoding="utf-8")
    report = _dead(str(raiz))
    quals = [s["qual"] for s in report["sin_llamantes"]]
    # Pasado como valor en un registro: hay uso aunque no haya llamada.
    assert "calc.handler" not in quals


def test_sin_grafo_de_imports_los_modulos_se_declaran_no_cubiertos(tmp_path):
    raiz = _proyecto(tmp_path)
    informe = symbols.analyze(raiz)
    report = huerfanos.analyze(informe, aristas_imports=None)
    assert report["modulos_huerfanos"] == []
    assert any("imports" in linea for linea in report["not_covered"])


def test_cli_dead_termina_bien_y_dice_sus_limites(tmp_path):
    raiz = _proyecto(tmp_path)
    p = subprocess.run(
        [sys.executable, "-m", "galaxybrain.cli", "dead", raiz],
        capture_output=True, text=True, timeout=120)
    assert p.returncode == 0
    assert "NO puede ver" in p.stdout


def test_el_entry_point_con_guard_main_no_es_huerfano(tmp_path):
    raiz = tmp_path / "p"
    raiz.mkdir()
    (raiz / "principal.py").write_text(
        "def arranca():\n    return 1\n\n\n"
        "if __name__ == \"__main__\":\n    arranca()\n", encoding="utf-8")
    report = _dead(str(raiz))
    modulos = [m["module"] for m in report["modulos_huerfanos"]]
    # El guard es un hecho detectable: el ejecutable del proyecto no es huerfano.
    assert "principal" not in modulos


def test_llamado_solo_desde_tests_sale_en_su_propia_lista(tmp_path):
    raiz = tmp_path / "p"
    raiz.mkdir()
    (raiz / "calc.py").write_text(
        "def viva(x):\n    return x\n\n\ndef zombi(x):\n    return x\n",
        encoding="utf-8")
    (raiz / "app.py").write_text(
        "from calc import viva\n\n\ndef main():\n    return viva(1)\n",
        encoding="utf-8")
    (raiz / "test_calc.py").write_text(
        "from calc import viva, zombi\n\n\n"
        "def test_viva():\n    assert viva(1) == 1\n\n\n"
        "def test_zombi():\n    assert zombi(1) == 1\n", encoding="utf-8")
    report = _dead(str(raiz))
    solo = [s["qual"] for s in report["solo_tests"]]
    # zombi: solo sus tests lo mantienen vivo -> a su lista, no a sin_llamantes
    assert "calc.zombi" in solo
    assert "calc.zombi" not in [s["qual"] for s in report["sin_llamantes"]]
    # viva: la llama produccion ADEMAS del test -> no es candidata a nada
    assert "calc.viva" not in solo


def test_la_mencion_textual_degrada_pero_no_absuelve(tmp_path):
    """La auditoria del 6-sep: de 26 candidatos, ~19 vivos por tabla, string o
    nivel de modulo — rastros que el grafo declara como techo pero el TEXTO
    enseña. El mencionado sigue en la lista (proxy, no veredicto), etiquetado
    y al final; el limpio, delante."""
    raiz = tmp_path
    (raiz / "calc.py").write_text(
        "def por_tabla(x):\n    return x\n\n\n"
        "def de_verdad_muerta(x):\n    return x\n\n\n"
        'TABLA = {"por_tabla": 1}\n', encoding="utf-8")
    report = _dead(str(raiz))

    por_qual = {s["qual"]: s for s in report["sin_llamantes"]}
    assert por_qual["calc.por_tabla"]["menciones"] is True
    assert por_qual["calc.de_verdad_muerta"]["menciones"] is False
    # el limpio va DELANTE: el ruido con cara de hallazgo manda la limpieza a
    # ignorarse, y ya paso una vez
    quals = [s["qual"] for s in report["sin_llamantes"]]
    assert quals.index("calc.de_verdad_muerta") < quals.index("calc.por_tabla")


def test_el_modulo_importado_por_string_queda_marcado(tmp_path):
    """`exec("import pkg.dinamico")` no deja arista (el .pth de gb importa asi
    a autoinstall) — pero el nombre esta entre comillas, y eso se lee."""
    raiz = tmp_path
    (raiz / "dinamico.py").write_text("x = 1\n", encoding="utf-8")
    (raiz / "suelto.py").write_text("y = 2\n", encoding="utf-8")
    (raiz / "arranque.py").write_text(
        'exec("import dinamico")\n', encoding="utf-8")
    report = _dead(str(raiz))

    por_mod = {m["module"]: m for m in report["modulos_huerfanos"]}
    assert por_mod["dinamico"]["menciones"] is True
    assert por_mod["suelto"]["menciones"] is False
