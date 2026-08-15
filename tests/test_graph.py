"""El analizador de acoplamiento. Un ciclo es un hecho, así que estos tests son
sobre HECHOS: se detecta el ciclo o no. La condición de calidad del gate (casi
cero falsos positivos) se cubre comprobando que un grafo sin ciclos reporta cero."""

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


def test_import_relativo_en_init_resuelve_al_paquete_correcto(tmp_path):
    """Bug del review: `from .x import y` dentro de un __init__.py resolvía un
    nivel demasiado arriba (el paquete de un __init__ es él mismo, no su padre)."""
    root = str(tmp_path)
    _write(root, "pkg/__init__.py", "from .models import User\n")  # pkg -> pkg.models
    _write(root, "pkg/models.py", "class User: pass\n")

    report = graph.analyze(root)
    assert report["fan_in"]["pkg.models"] == 1  # el edge apunta a pkg.models, no a 'models'


def test_ciclo_a_traves_de_init_se_detecta(tmp_path):
    root = str(tmp_path)
    _write(root, "pkg/__init__.py", "from .a import x\n")  # pkg -> pkg.a
    _write(root, "pkg/a.py", "from pkg import y\n")         # pkg.a -> pkg

    report = graph.analyze(root)
    assert any(set(c) == {"pkg", "pkg.a"} for c in report["cycles"])


def test_init_no_inventa_ciclo_falso_con_modulo_homonimo(tmp_path):
    """El off-by-one antes creaba un edge pkg->'models' (top-level) y, con un
    models.py que importa pkg, un CICLO FALSO pkg<->models."""
    root = str(tmp_path)
    _write(root, "pkg/__init__.py", "from .models import User\n")  # correcto: pkg -> pkg.models
    _write(root, "pkg/models.py", "")
    _write(root, "models.py", "from pkg import thing\n")           # top-level models -> pkg

    report = graph.analyze(root)
    assert not any(set(c) == {"pkg", "models"} for c in report["cycles"])


def test_fichero_cp1252_no_tumba_el_analisis(tmp_path):
    """Bug del review: build_graph abría en utf-8 estricto y el except solo cazaba
    OSError; un .py en cp1252 (comunísimo en Windows) reventaba con UnicodeDecodeError."""
    root = str(tmp_path)
    _write(root, "pkg/__init__.py", "")
    path = os.path.join(root, "pkg", "legacy.py")
    with open(path, "w", encoding="cp1252") as handle:
        handle.write("# a\xf1o fiscal\nX = 1\n")  # 0xf1 = ñ en cp1252, byte inválido en utf-8

    report = graph.analyze(root)  # no debe crashear
    assert "pkg.legacy" in report["fan_in"]


def test_fichero_patologico_va_a_errores_sin_crashear(tmp_path):
    """RecursionError/MemoryError de ast.parse no son SyntaxError/ValueError: un
    .py con anidamiento enorme no puede tumbar el análisis entero."""
    root = str(tmp_path)
    _write(root, "pkg/__init__.py", "")
    _write(root, "pkg/ok.py", "X = 1\n")
    # Menos unario encadenado -> MemoryError del parser en TODAS las versiones
    # medidas (3.9-linux y 3.11-windows). La cadena de atributos anterior no
    # explotaba en 3.9-linux (el parser la come iterativa): el primer CI la
    # cazo — una bomba que no detona en todas partes no prueba la garantia.
    _write(root, "pkg/bomba.py", "-" * 20000 + "1\n")

    report = graph.analyze(root)  # la clave: no crashea
    assert any("bomba.py" in loc for loc in report["errors"])
    assert "pkg.ok" in report["fan_in"]  # el resto se analiza igual


def test_cli_graph_gate_falla_con_ciclo_y_pasa_sin_el(tmp_path):
    root = str(tmp_path)
    _write(root, "pkg/__init__.py", "")
    _write(root, "pkg/a.py", "from . import b\n")
    _write(root, "pkg/b.py", "from . import a\n")

    from galaxybrain import cli

    assert cli.main(["graph", root, "--gate", "--color", "never"]) == 1  # ciclo -> gate falla
    assert cli.main(["graph", root, "--color", "never"]) == 0            # por defecto solo muestra


def test_el_gitignore_del_proyecto_manda_sobre_el_walker(tmp_path):
    """Feedback de uso real (7-ago): pytest-of-*/ y tmp*/ IGNORADOS por el
    .gitignore del proyecto salian pintados como modulos sueltos — mapa inflado
    y desincronizado al rotar los temporales. El .gitignore es el hecho
    declarado (regla 6); la lista cableada queda de cinturon para repos sin
    git. Y el matiz que importa: lo NUEVO sin trackear SI se ve (la obra y la
    actividad viven de ello) — solo sobra lo ignorado."""
    import subprocess

    root = str(tmp_path / "repo")
    os.makedirs(root, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True, capture_output=True)
    _write(root, ".gitignore", "basura/\n")
    _write(root, "real.py", "X = 1\n")
    _write(root, "nuevo.py", "Y = 2\n")  # sin trackear, NO ignorado: debe verse
    _write(root, "basura/tmpmod.py", "Z = 3\n")  # ignorado: fuera del mapa

    report = graph.analyze(root)
    assert "real" in report["fan_in"]
    assert "nuevo" in report["fan_in"]
    assert not any("basura" in m for m in report["fan_in"])

    # sin git no hay hecho que leer: se indexa todo, como siempre
    # (hermano del repo, no dentro — o el .gitignore del padre lo alcanzaria)
    suelto = str(tmp_path / "sin-git")
    _write(suelto, "basura/tmpmod.py", "Z = 3\n")
    assert any("basura" in m for m in graph.analyze(suelto)["fan_in"])


def test_apuntar_a_una_raiz_ignorada_la_analiza_igual(tmp_path):
    """El objetivo que se nombra a dedo gana sobre el .gitignore que lo envuelve.

    Cazado usando gb sobre gb (8-ago): `gb symbols <dir>` sobre una carpeta con
    un .py dentro devolvio CERO nodos y ni una palabra del motivo — la regla
    `pytest-of-*/` del repo padre vaciaba la lista de permitidos y el walker se
    quedaba sin nada que recorrer. Un grafo vacio que se lee como "aqui no hay
    nada" es la mentira en verde que este modulo existe para no contar; y
    apuntar a una carpeta ES pedirla, igual que `git add -f`.
    """
    import subprocess

    root = str(tmp_path / "repo")
    os.makedirs(root, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True, capture_output=True)
    _write(root, ".gitignore", "basura/\n")
    _write(root, "real.py", "X = 1\n")
    _write(root, "basura/tmpmod.py", "Z = 3\n")

    # desde la raiz del repo sigue ignorandose (la conducta del 7-ago, intacta)
    assert not any("basura" in m for m in graph.analyze(root)["fan_in"])

    # pero apuntando A la carpeta ignorada, su codigo se ve
    assert "tmpmod" in graph.analyze(os.path.join(root, "basura"))["fan_in"]
