"""Fase B — *imposible de esconder*: qué le hizo un cambio a la evidencia.

Un verde se compra de dos formas, arreglando el código o ablandando lo que lo
comprueba. Estos tests fijan que la segunda salga siempre a la luz, y —igual de
importante— que lo que NO se ha mirado se diga en voz alta.
"""

import os
import subprocess

import pytest

from galaxybrain import changes, cli


@pytest.mark.parametrize(
    "linea,es_debil",
    [
        ("assert True", True),
        ("assert 1", True),
        ("assert True, 'con mensaje'", True),
        ("assert 1 == 1", False),  # comparacion real, no asercion pelada
        ("    assert 1 == 1  # nota", False),
        ("assert True is True", False),
    ],
)
def test_la_asercion_truthy_pelada_se_distingue_de_una_comparacion(linea, es_debil):
    """El patron heredado de v1 terminaba en \\b y casaba DENTRO de `assert 1 == 1`.
    Marcar una comparacion legitima como 'debilitada' es ruido, y el ruido es lo que
    manda una revision a --no-verify."""
    assert changes._matches(changes.WEAKENER, linea) is es_debil


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


def test_quitar_una_asercion_no_se_enmascara_anadiendo_otro_test(tmp_path):
    """El agujero encontrado corriendo esto sobre trabajo real (115ee8c): con el
    neto POR FICHERO, quitar la asercion que fallaba y añadir un test trivial que
    pasa hacia subir el neto y desaparecer la resta. Es la ruta de amaño mas obvia
    despues de borrar el fichero, asi que no puede ser la que se escape."""
    root = _repo(tmp_path)
    _write(
        root,
        "tests/test_app.py",
        "def test_importante():\n    assert caro() == 42\n    assert barato() == 1\n",
    )
    _commit(root, "base")
    _write(
        root,
        "tests/test_app.py",
        "def test_importante():\n    assert barato() == 1\n\n"
        "def test_nuevo_trivial():\n    assert True is True\n    assert 1 == 1\n    assert 2 == 2\n",
    )
    _commit(root, "quita la cara, mete tres triviales")

    report = changes.analyze(root, "HEAD~1..HEAD")
    assert "ASSERT_REMOVED" in _senales(report), "el neto por fichero subia y lo tapaba"
    flag = next(f for f in report["flags"] if f["signal"] == "ASSERT_REMOVED")
    assert "test_importante" in flag["detail"], "y dice en QUE funcion se perdio"


def test_el_borrado_y_el_test_nuevo_en_EL_MISMO_hunk_tampoco_se_enmascaran(tmp_path):
    """La forma REAL del caso, que el primer arreglo no cubrio: cuando el borrado y
    el test nuevo son lineas contiguas, git emite UN SOLO hunk y lo etiqueta con la
    funcion donde empieza. Contar por hunk seguia tapandolo. Reproduce la geometria
    exacta de 115ee8c."""
    root = _repo(tmp_path)
    _write(
        root,
        "tests/test_app.py",
        "def test_uno():\n    x = calcula()\n    assert x == 42\n",
    )
    _commit(root, "base")
    # Se quita la asercion y, PEGADO, se añade un test nuevo con mas aserciones.
    _write(
        root,
        "tests/test_app.py",
        "def test_uno():\n    x = calcula()\n\n\n"
        "def test_nuevo():\n    assert 1 == 1\n    assert 2 == 2\n    assert 3 == 3\n",
    )
    _commit(root, "mismo hunk")

    diff = subprocess.run(
        ["git", "-C", root, "diff", "--unified=0", "HEAD~1..HEAD"],
        capture_output=True, text=True,
    ).stdout
    assert diff.count("@@ -") == 1, "el test solo vale si git emite un unico hunk"
    assert "ASSERT_REMOVED" in _senales(changes.analyze(root, "HEAD~1..HEAD"))


def test_reescribir_aserciones_en_sitio_no_levanta_nada(tmp_path):
    """El contrapeso de los dos anteriores: cambiar una asercion por otra DENTRO de
    la misma funcion es lo que hace cualquiera al actualizar un contrato. Si eso
    chilla, la revision acaba ignorada."""
    root = _repo(tmp_path)
    _write(root, "tests/test_app.py", "def test_uno():\n    assert nombre() == 'viejo'\n")
    _commit(root, "base")
    _write(root, "tests/test_app.py", "def test_uno():\n    assert nombre() == 'nuevo'\n")
    _commit(root, "actualiza el contrato")

    assert changes.analyze(root, "HEAD~1..HEAD")["flags"] == []


def test_un_patron_dentro_de_un_string_no_es_una_senal(tmp_path):
    """El falso positivo que dio en su primer cambio real: marco un
    `@pytest.mark.skip` que vivia DENTRO de una cadena, como dato de prueba de sus
    propios tests. Recurrente por construccion en cualquier repo que testee un
    detector, y el criterio de la Fase B dice que un falso positivo recurrente la
    mata."""
    root = _repo(tmp_path)
    _write(root, "tests/test_app.py", SUITE)
    _commit(root, "base")
    _write(
        root,
        "tests/test_app.py",
        SUITE
        + '\ndef test_del_detector():\n'
        '    fuente = "@pytest.mark.skip\\ndef test_x(): pass"\n'
        '    otra = "assert True"\n'
        '    assert detecta(fuente) and detecta(otra)\n',
    )
    _commit(root, "tests del detector, con patrones como dato")

    assert changes.analyze(root, "HEAD~1..HEAD")["flags"] == []


def test_mencionar_un_marcador_en_un_docstring_no_es_una_senal(tmp_path):
    """El falso positivo que salto en el commit que arreglaba los falsos positivos:
    el detector marco su PROPIO docstring, donde `@pytest.mark.skip` aparece entre
    backticks a mitad de frase. Vaciar literales no bastaba —las lineas interiores
    de una cadena triple no llevan comillas— asi que los decoradores van anclados a
    principio de linea, que es donde estan los de verdad."""
    root = _repo(tmp_path)
    _write(root, "tests/test_app.py", SUITE)
    _commit(root, "base")
    _write(
        root,
        "tests/test_app.py",
        SUITE
        + '\ndef test_documentado():\n'
        '    """Explica por que no usamos `@pytest.mark.skip` aqui,\n'
        '    ni @unittest.skip, ni pytest.skip(...) a media frase.\n'
        '    """\n'
        '    assert 1 == 1\n',
    )
    _commit(root, "docstring que menciona marcadores")

    assert changes.analyze(root, "HEAD~1..HEAD")["flags"] == []


def test_un_skip_de_verdad_sigue_saliendo(tmp_path):
    """El contrapeso del anterior: vaciar las cadenas no puede volver ciego al
    detector para el caso real."""
    root = _repo(tmp_path)
    _write(root, "tests/test_app.py", SUITE)
    _commit(root, "base")
    _write(root, "tests/test_app.py", SUITE + '\n@pytest.mark.skip(reason="luego")\ndef test_x():\n    assert 1\n')
    _commit(root, "skip real, con string dentro")

    assert "SKIP_ADDED" in _senales(changes.analyze(root, "HEAD~1..HEAD"))


def test_staged_mira_el_indice_no_el_commit_anterior(tmp_path):
    """El bug que casi se cuela al enganchar el hook: en pre-commit el commit
    todavia NO EXISTE, asi que un rango revisa el commit ANTERIOR. Aqui se fija
    que --staged mire lo que va a entrar: el commit previo esta limpio y lo
    staged trae el amaño, asi que un rango no veria nada."""
    root = _repo(tmp_path)
    _write(root, "tests/test_app.py", SUITE)
    _write(root, "app.py", "valor = 1\n")
    _commit(root, "base limpia")
    _write(root, "app.py", "valor = 2\n")
    _commit(root, "commit anterior, limpio")

    # Ahora se ablanda un test y se deja EN EL INDICE, sin commitear.
    _write(root, "tests/test_app.py", SUITE.replace("assert 2 == 2", "assert True"))
    _run(root, "git", "add", "-A")

    assert changes.analyze(root, "HEAD~1..HEAD")["flags"] == [], "el rango mira el commit de antes"
    assert "WEAKENER_ADDED" in _senales(changes.analyze(root, staged=True))


def test_staged_declara_la_asimetria_indice_working_tree(tmp_path):
    root = _repo(tmp_path)
    _write(root, "app.py", "valor = 1\n")
    _commit(root, "base")
    _write(root, "app.py", "valor = 2\n")
    _run(root, "git", "add", "-A")

    report = changes.analyze(root, staged=True)
    assert any("sin stagear" in item for item in report["not_covered"])


def test_sin_rango_ni_staged_es_error(tmp_path):
    root = _repo(tmp_path)
    _write(root, "app.py", "v = 1\n")
    _commit(root, "base")

    assert changes.analyze(root, None)["range_error"]


def test_brief_es_una_linea_cuando_no_hay_senales(tmp_path):
    """Un informe largo en CADA commit deja de leerse a la tercera vez, y
    entonces no protege de nada."""
    from galaxybrain import render

    root = _repo(tmp_path)
    _write(root, "app.py", "valor = 1\n")
    _commit(root, "base")
    _write(root, "app.py", "valor = 2\n")
    _run(root, "git", "add", "-A")

    report = changes.analyze(root, staged=True)
    salida = render.render_changes(report, render.Style(False), brief=True)
    assert len(salida.splitlines()) == 1


def test_brief_no_se_calla_cuando_SI_hay_senales(tmp_path):
    from galaxybrain import render

    root = _repo(tmp_path)
    _write(root, "tests/test_app.py", SUITE)
    _commit(root, "base")
    os.remove(os.path.join(root, "tests", "test_app.py"))
    _run(root, "git", "add", "-A")

    report = changes.analyze(root, staged=True)
    salida = render.render_changes(report, render.Style(False), brief=True)
    assert "TEST_FILE_DELETED" in salida
    assert len(salida.splitlines()) > 1


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
