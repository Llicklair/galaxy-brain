"""El analizador de acoplamiento. Un ciclo es un hecho, así que estos tests son
sobre HECHOS: se detecta el ciclo o no. La condición de calidad de v3 (casi cero
falsos positivos) se cubre comprobando que un grafo sin ciclos reporta cero."""

import os

from galaxybrain import graph


def _write(root, rel, content):
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def test_module_name_consciente_de_src_layout(tmp_path):
    root = str(tmp_path)
    assert graph.module_name(os.path.join(root, "src", "pkg", "mod.py"), root) == "pkg.mod"
    assert graph.module_name(os.path.join(root, "src", "pkg", "__init__.py"), root) == "pkg"
    assert graph.module_name(os.path.join(root, "flat", "x.py"), root) == "flat.x"


def test_detecta_ciclo_con_imports_relativos(tmp_path):
    root = str(tmp_path)
    _write(root, "pkg/__init__.py", "")
    _write(root, "pkg/a.py", "from . import b\n")
    _write(root, "pkg/b.py", "from . import a\n")
    _write(root, "pkg/c.py", "from . import a\n")  # depende de a, sin ciclo

    report = graph.analyze(root)
    assert len(report["cycles"]) == 1
    assert set(report["cycles"][0]) == {"pkg.a", "pkg.b"}
    assert report["fan_in"]["pkg.a"] == 2  # b y c importan a


def test_sin_ciclos_reporta_cero(tmp_path):
    root = str(tmp_path)
    _write(root, "pkg/__init__.py", "")
    _write(root, "pkg/base.py", "X = 1\n")
    _write(root, "pkg/uso.py", "from pkg.base import X\n")  # import absoluto

    report = graph.analyze(root)
    assert report["cycles"] == []
    assert report["fan_in"]["pkg.base"] == 1


def test_import_absoluto_y_from_submodulo(tmp_path):
    root = str(tmp_path)
    _write(root, "app/__init__.py", "")
    _write(root, "app/core.py", "import app.util\nfrom app import helpers\n")
    _write(root, "app/util.py", "")
    _write(root, "app/helpers.py", "")

    report = graph.analyze(root)
    assert report["fan_out"]["app.core"] == 2  # util y helpers


def test_ciclo_de_tres_modulos(tmp_path):
    root = str(tmp_path)
    _write(root, "pkg/__init__.py", "")
    _write(root, "pkg/a.py", "from . import b\n")
    _write(root, "pkg/b.py", "from . import c\n")
    _write(root, "pkg/c.py", "from . import a\n")

    report = graph.analyze(root)
    assert len(report["cycles"]) == 1
    assert set(report["cycles"][0]) == {"pkg.a", "pkg.b", "pkg.c"}


def test_import_externo_no_cuenta_como_acoplamiento(tmp_path):
    root = str(tmp_path)
    _write(root, "pkg/__init__.py", "")
    _write(root, "pkg/m.py", "import os\nimport json\nfrom collections import OrderedDict\n")

    report = graph.analyze(root)
    assert report["fan_out"]["pkg.m"] == 0  # stdlib no es acoplamiento interno


def test_fichero_con_syntax_error_no_tumba_el_analisis(tmp_path):
    root = str(tmp_path)
    _write(root, "pkg/__init__.py", "")
    _write(root, "pkg/ok.py", "x = 1\n")
    _write(root, "pkg/roto.py", "def (:\n")  # syntax error

    report = graph.analyze(root)
    assert any("roto.py" in p for p in report["errors"])
    assert "pkg.ok" in report["fan_in"]  # el resto se analiza igual


def test_ignora_venv_pycache_y_ocultos(tmp_path):
    root = str(tmp_path)
    _write(root, "pkg/__init__.py", "")
    _write(root, "pkg/real.py", "")
    _write(root, ".venv/lib/fantasma.py", "import os\n")
    _write(root, "pkg/__pycache__/cache.py", "")

    mods = set(graph.analyze(root)["fan_in"])
    assert "pkg.real" in mods
    assert not any("fantasma" in m or "cache" in m for m in mods)


def test_cli_graph_gate_falla_con_ciclo_y_pasa_sin_el(tmp_path):
    root = str(tmp_path)
    _write(root, "pkg/__init__.py", "")
    _write(root, "pkg/a.py", "from . import b\n")
    _write(root, "pkg/b.py", "from . import a\n")

    from galaxybrain import cli

    assert cli.main(["graph", root, "--gate", "--color", "never"]) == 1  # ciclo -> gate falla
    assert cli.main(["graph", root, "--color", "never"]) == 0            # por defecto solo muestra
