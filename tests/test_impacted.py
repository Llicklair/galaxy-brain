"""`gb tests`: la seleccion derivada del grafo.

El invariante que gobierna este fichero no es "selecciona poco", es **no miente**:
ante cualquier duda devuelve la suite entera con el motivo escrito. Un falso verde
(la seleccion pasa y la suite entera habria fallado) mata el comando, y por eso hay
un test que lo comprueba de frente ejecutando pytest de verdad.
"""

import os
import subprocess
import sys

import pytest

from galaxybrain import impacted


def _git(root, *args):
    subprocess.run(["git"] + list(args), cwd=str(root), check=True,
                   capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path):
    """Un repo real con un simbolo, un test que lo ejercita y otro que no."""
    root = tmp_path / "proyecto"
    (root / "lib").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "lib" / "__init__.py").write_text("", encoding="utf-8")
    (root / "lib" / "nucleo.py").write_text(
        "def suma(a, b):\n"
        "    return a + b\n"
        "\n"
        "\n"
        "def resta(a, b):\n"
        "    return a - b\n",
        encoding="utf-8")
    (root / "tests" / "__init__.py").write_text("", encoding="utf-8")
    (root / "tests" / "test_suma.py").write_text(
        "from lib.nucleo import suma\n"
        "\n"
        "\n"
        "def test_suma_va():\n"
        "    assert suma(1, 2) == 3\n",
        encoding="utf-8")
    (root / "tests" / "test_resta.py").write_text(
        "from lib.nucleo import resta\n"
        "\n"
        "\n"
        "def test_resta_va():\n"
        "    assert resta(3, 1) == 2\n",
        encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t.t")
    _git(root, "config", "user.name", "t")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "base")
    return root


def _tocar(root, rel, viejo, nuevo):
    path = root / rel
    path.write_text(path.read_text(encoding="utf-8").replace(viejo, nuevo), encoding="utf-8")


def test_selecciona_solo_los_tests_que_alcanzan_lo_tocado(repo):
    _tocar(repo, "lib/nucleo.py", "return a + b", "return b + a")
    _git(repo, "add", "-A")
    report = impacted.analyze(str(repo), staged=True)

    assert report["todo"] is False
    assert report["tests"] == ["tests/test_suma.py"]
    assert "lib.nucleo.suma" in report["symbols"]
    assert report["n_tests"] < report["total_tests"]


def test_el_mismo_veredicto_que_la_suite_entera(repo):
    """El criterio de terminado, ejecutado: misma respuesta, menos trabajo.

    Se rompe `suma` de verdad. Si la seleccion pasara mientras la suite entera
    falla, eso es el falso verde que mata el comando — y este test lo caza.
    """
    _tocar(repo, "lib/nucleo.py", "return a + b", "return a - b")
    _git(repo, "add", "-A")
    report = impacted.analyze(str(repo), staged=True)
    assert report["todo"] is False

    entera = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests"],
                            cwd=str(repo), capture_output=True, text=True)
    seleccion = subprocess.run([sys.executable, "-m", "pytest", "-q"] + report["tests"],
                               cwd=str(repo), capture_output=True, text=True)

    assert entera.returncode != 0, "la suite entera deberia ver el fallo"
    assert seleccion.returncode == entera.returncode, (
        "falso verde: la seleccion no vio lo que la suite entera si ve\n%s" % seleccion.stdout)


def test_tocar_conftest_obliga_a_correr_todo(repo):
    """Un conftest no es llamante de nadie: el AST no puede ver su efecto."""
    (repo / "tests" / "conftest.py").write_text(
        "import pytest\n"
        "\n"
        "\n"
        "@pytest.fixture\n"
        "def algo():\n"
        "    return 1\n",
        encoding="utf-8")
    _git(repo, "add", "-A")
    report = impacted.analyze(str(repo), staged=True)

    assert report["todo"] is True
    assert "conftest.py" in report["motivo"]
    assert len(report["tests"]) == report["total_files"]


def test_un_cambio_fuera_de_todo_simbolo_corre_todo(repo):
    """Una constante a nivel de modulo no cae dentro de ningun def."""
    _tocar(repo, "lib/nucleo.py", "def suma(a, b):", "LIMITE = 10\n\n\ndef suma(a, b):")
    _git(repo, "add", "-A")
    report = impacted.analyze(str(repo), staged=True)

    assert report["todo"] is True
    assert "simbolo" in report["motivo"]


def test_un_diff_vacio_no_selecciona_nada(repo):
    report = impacted.analyze(str(repo), staged=True)
    assert report["tests"] == []
    assert report["todo"] is False
    assert "vacio" in report["motivo"]


def test_los_helpers_de_los_tests_no_entran_en_la_seleccion(repo):
    """El detalle que falseo la primera medicion de esta idea.

    Un helper (`_generar`) vive en un fichero de tests y el grafo lo ve, pero
    pytest no lo colecciona: seleccionarlo como id da `ERROR: not found` y exit
    code 4 — "no tests ran", que en un gate se lee igual de verde que "todo paso".
    """
    assert impacted._es_test("tests.test_x.test_algo", {"kind": "function"}) is True
    assert impacted._es_test("tests.test_x._generar", {"kind": "function"}) is False
    assert impacted._es_test("tests.test_x.Ayuda", {"kind": "class"}) is False
    assert impacted._es_test("lib.nucleo.test_algo", {"kind": "function"}) is False


def test_un_test_tocado_directamente_se_corre_el(repo):
    _tocar(repo, "tests/test_suma.py", "== 3", "== 3  # tocado")
    _git(repo, "add", "-A")
    report = impacted.analyze(str(repo), staged=True)

    assert "tests/test_suma.py" in report["tests"]
    assert report["todo"] is False


def test_sin_tests_que_lo_alcancen_corre_todo_y_lo_dice(repo):
    """Cambiar algo que ningun test ejercita NO es un ahorro: es el dato."""
    (repo / "lib" / "suelto.py").write_text(
        "def nadie_me_llama():\n"
        "    return 1\n",
        encoding="utf-8")
    _git(repo, "add", "-A")
    report = impacted.analyze(str(repo), staged=True)

    assert report["todo"] is True
    assert "ningun test alcanza" in report["motivo"]


def test_una_raiz_que_no_existe_es_error_de_uso(tmp_path):
    report = impacted.analyze(str(tmp_path / "no-existe"))
    assert report["range_error"]
    assert report["tests"] == []


def test_sin_git_no_inventa_una_seleccion(tmp_path):
    """Sin repo git no hay diff: la respuesta segura es todo, no una lista corta."""
    root = tmp_path / "pelado"
    (root / "lib").mkdir(parents=True)
    (root / "lib" / "__init__.py").write_text("", encoding="utf-8")
    (root / "lib" / "x.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    report = impacted.analyze(str(root))
    assert report["todo"] is True or report["tests"] == []
    assert report["motivo"]


def test_la_seleccion_usa_rutas_que_pytest_entiende(repo):
    _tocar(repo, "lib/nucleo.py", "return a + b", "return b + a")
    _git(repo, "add", "-A")
    report = impacted.analyze(str(repo), staged=True)

    for ruta in report["tests"]:
        assert "\\" not in ruta, "las rutas van con / para que pytest las coma en Windows"
        assert os.path.exists(os.path.join(str(repo), ruta))
