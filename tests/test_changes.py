"""Fase B — *imposible de esconder*: qué le hizo un cambio a la evidencia.

Un verde se compra de dos formas, arreglando el código o ablandando lo que lo
comprueba. Estos tests fijan que la segunda salga siempre a la luz, y —igual de
importante— que lo que NO se ha mirado se diga en voz alta.
"""

import os
import subprocess

from galaxybrain import changes, cli


def _run(cwd, *args):
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


def _write(root, rel, content):
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def _repo(tmp_path):
    root = str(tmp_path)
    _run(root, "git", "init", "-q")
    _run(root, "git", "config", "user.email", "t@t")
    _run(root, "git", "config", "user.name", "t")
    _run(root, "git", "config", "commit.gpgsign", "false")
    return root


def _commit(root, msg):
    _run(root, "git", "add", "-A")
    _run(root, "git", "commit", "-q", "-m", msg)


SUITE = (
    "def test_uno():\n    assert 1 == 1\n\n"
    "def test_dos():\n    assert 2 == 2\n\n"
    "def test_tres():\n    assert 3 == 3\n"
)


def _senales(report):
    return {f["signal"] for f in report["flags"]}


# --- las cuatro familias de senal ------------------------------------------


def test_borrar_una_definicion_de_test_sale(tmp_path):
    root = _repo(tmp_path)
    _write(root, "tests/test_app.py", SUITE)
    _commit(root, "base")
    _write(root, "tests/test_app.py", "def test_uno():\n    assert 1 == 1\n")
    _commit(root, "quita dos tests")

    assert "TEST_REMOVED" in _senales(changes.analyze(root, "HEAD~1..HEAD"))


def test_borrar_el_fichero_de_tests_entero_sale(tmp_path):
    """El caso que el test-guard de v1 se perdia: al borrarse el fichero, el diff
    dice `+++ /dev/null` y el parser antiguo lo saltaba. Es el amaño mas
    descarado de todos, asi que no puede ser justo el que se escape."""
    root = _repo(tmp_path)
    _write(root, "tests/test_app.py", SUITE)
    _commit(root, "base")
    os.remove(os.path.join(root, "tests", "test_app.py"))
    _commit(root, "adios tests")

    report = changes.analyze(root, "HEAD~1..HEAD")
    assert "TEST_FILE_DELETED" in _senales(report)
    assert report["test_files_changed"] == 1


def test_anadir_un_skip_sale(tmp_path):
    root = _repo(tmp_path)
    _write(root, "tests/test_app.py", SUITE)
    _commit(root, "base")
    _write(root, "tests/test_app.py", SUITE.replace("def test_dos", "@pytest.mark.skip\ndef test_dos"))
    _commit(root, "salta uno")

    assert "SKIP_ADDED" in _senales(changes.analyze(root, "HEAD~1..HEAD"))


def test_ablandar_una_asercion_sale(tmp_path):
    root = _repo(tmp_path)
    _write(root, "tests/test_app.py", SUITE)
    _commit(root, "base")
    _write(root, "tests/test_app.py", SUITE.replace("assert 2 == 2", "assert True"))
    _commit(root, "ablanda"),

    assert "WEAKENER_ADDED" in _senales(changes.analyze(root, "HEAD~1..HEAD"))


def test_perdida_neta_de_aserciones_sale(tmp_path):
    root = _repo(tmp_path)
    _write(root, "tests/test_app.py", "def test_uno():\n    assert 1 == 1\n    assert 2 == 2\n    assert 3 == 3\n")
    _commit(root, "base")
    _write(root, "tests/test_app.py", "def test_uno():\n    assert 1 == 1\n")
    _commit(root, "menos aserciones")

    assert "ASSERT_REMOVED" in _senales(changes.analyze(root, "HEAD~1..HEAD"))


# --- el contrapeso: no chillar sin motivo -----------------------------------


def test_anadir_tests_no_levanta_nada(tmp_path):
    """La condicion de calidad: una revision que chilla cuando haces lo correcto
    acaba ignorada. Añadir cobertura tiene que salir limpio."""
    root = _repo(tmp_path)
    _write(root, "tests/test_app.py", SUITE)
    _commit(root, "base")
    _write(root, "tests/test_app.py", SUITE + "\ndef test_cuatro():\n    assert 4 == 4\n")
    _commit(root, "mas cobertura")

    assert changes.analyze(root, "HEAD~1..HEAD")["flags"] == []


def test_tocar_solo_codigo_de_produccion_no_levanta_nada(tmp_path):
    root = _repo(tmp_path)
    _write(root, "app.py", "valor = 1\n")
    _write(root, "tests/test_app.py", SUITE)
    _commit(root, "base")
    _write(root, "app.py", "valor = 2\n")
    _commit(root, "cambia produccion")

    report = changes.analyze(root, "HEAD~1..HEAD")
    assert report["flags"] == []
    assert report["test_files_changed"] == 0


# --- decir lo que NO se ha mirado -------------------------------------------


def test_siempre_declara_lo_no_cubierto(tmp_path):
    root = _repo(tmp_path)
    _write(root, "app.py", "valor = 1\n")
    _commit(root, "base")
    _write(root, "app.py", "valor = 2\n")
    _commit(root, "cambio")

    report = changes.analyze(root, "HEAD~1..HEAD")
    assert report["not_covered"], "un informe que solo dice lo revisado se lee como si lo cubriera todo"
    assert any("suite" in item for item in report["not_covered"])


def test_sin_reglas_de_frontera_lo_dice(tmp_path):
    """0 reglas cargadas = la parte de fronteras revisa cero. Callarlo dejaria un
    'sin cruces prohibidos' que en realidad significa 'no he mirado'."""
    root = _repo(tmp_path)
    _write(root, "pkg/__init__.py", "")
    _write(root, "pkg/a.py", "valor = 1\n")
    _commit(root, "base")
    _write(root, "pkg/a.py", "valor = 2\n")
    _commit(root, "cambio")

    report = changes.analyze(root, "HEAD~1..HEAD")
    assert any("fronteras" in item for item in report["not_covered"])


def test_rango_ilegible_es_error_no_informe_limpio(tmp_path):
    root = _repo(tmp_path)
    _write(root, "app.py", "valor = 1\n")
    _commit(root, "base")

    report = changes.analyze(root, "no-existe..tampoco")
    assert report["range_error"]
    assert cli.main(["check", "no-existe..tampoco", root, "--color", "never"]) == 1


def test_raiz_inexistente_es_error(tmp_path):
    report = changes.analyze(os.path.join(str(tmp_path), "no-existe"), "HEAD~1..HEAD")
    assert report["range_error"]


# --- el contrato de salida ---------------------------------------------------


def test_las_senales_no_bloquean(tmp_path):
    """Son PROXIES. Gatear proxies fue el error de v1: un refactor legitimo las
    levanta, y una gate que chilla sin motivo acaba en --no-verify."""
    root = _repo(tmp_path)
    _write(root, "tests/test_app.py", SUITE)
    _commit(root, "base")
    os.remove(os.path.join(root, "tests", "test_app.py"))
    _commit(root, "adios tests")

    report = changes.analyze(root, "HEAD~1..HEAD")
    assert report["flags"], "la senal tiene que existir..."
    assert cli.main(["check", "HEAD~1..HEAD", root, "--color", "never"]) == 0, "...pero no bloquear"
