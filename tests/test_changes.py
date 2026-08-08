"""*imposible de esconder*: qué le hizo un cambio a la evidencia.

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
    """El patron anterior terminaba en \\b y casaba DENTRO de `assert 1 == 1`.
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
    """El caso que el test-guard anterior se perdia: al borrarse el fichero, el diff
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
    detector, y el criterio de check dice que un falso positivo recurrente la
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
    """Son PROXIES. Gatear proxies fue el error anterior: un refactor legitimo las
    levanta, y una gate que chilla sin motivo acaba en --no-verify."""
    root = _repo(tmp_path)
    _write(root, "tests/test_app.py", SUITE)
    _commit(root, "base")
    os.remove(os.path.join(root, "tests", "test_app.py"))
    _commit(root, "adios tests")

    report = changes.analyze(root, "HEAD~1..HEAD")
    assert report["flags"], "la senal tiene que existir..."
    assert cli.main(["check", "HEAD~1..HEAD", root, "--color", "never"]) == 0, "...pero no bloquear"


def test_degradar_comparacion_a_truthy_sale_aunque_el_neto_sea_cero(tmp_path):
    """El falso negativo de la prueba de uso real: romper el descuento, cambiar
    `assert total(x) == 90.0` por `assert total(x)` y aniadir un test trivial.
    Neto de aserciones 1<->1, WEAKENER solo cazaba `assert True` literal: paso
    limpio. Una asercion que compara afirma algo; una truthy solo "no es falsy"."""
    root = _repo(tmp_path)
    _write(root, "tests/test_caja.py",
           "def test_descuento():\n    assert total([100], 0.1) == 90.0\n")
    _commit(root, "base")
    _write(root, "tests/test_caja.py",
           "def test_descuento():\n    assert total([100], 0.1)\n")
    _commit(root, "ablanda")

    assert "ASSERT_WEAKENED" in _senales(changes.analyze(root, "HEAD~1..HEAD"))


def test_cambiar_una_comparacion_por_otra_no_chilla(tmp_path):
    """El contrapeso: actualizar el valor esperado conserva la comparacion."""
    root = _repo(tmp_path)
    _write(root, "tests/test_caja.py", "def test_x():\n    assert nombre() == 'viejo'\n")
    _commit(root, "base")
    _write(root, "tests/test_caja.py", "def test_x():\n    assert nombre() == 'nuevo'\n")
    _commit(root, "actualiza")

    assert changes.analyze(root, "HEAD~1..HEAD")["flags"] == []


# --- parse_diff: casos borde ---


def test_rename_con_espacios_en_la_ruta_conserva_el_nombre_entero():
    """La ruta se corta por el prefijo `b/`, no por el primer espacio.

    Un `git mv` a un nombre con espacios sigue siendo un cambio sobre tests: si
    la ruta se truncara, el fichero dejaria de casar con TEST_FILE y las senales
    de ese renombrado se perderian enteras.
    """
    diff = (
        "diff --git a/tests/test caja vieja.py b/tests/test caja nueva.py\n"
        "similarity index 80%\n"
        "rename from tests/test caja vieja.py\n"
        "rename to tests/test caja nueva.py\n"
        "--- a/tests/test caja vieja.py\n"
        "+++ b/tests/test caja nueva.py\n"
        "@@ -1,3 +1,3 @@ def test_uno():\n"
        " def test_uno():\n"
        "-    assert caja() == 1\n"
        "+    assert caja() == 2\n"
    )

    files = changes.parse_diff(diff)

    assert list(files) == ["tests/test caja nueva.py"]
    entrada = files["tests/test caja nueva.py"]
    assert entrada["deleted"] is False
    assert entrada["added"] == ["    assert caja() == 2"]
    assert entrada["removed"] == ["    assert caja() == 1"]
    # el mismo nombre con espacios sobrevive tambien en el rango de la onda
    assert changes._hunks_py(diff) == {"tests/test caja nueva.py": [(1, 3)]}


def test_fichero_borrado_entero_se_atribuye_a_la_ruta_vieja():
    """Con `+++ /dev/null` la unica ruta que queda es la de la cabecera `---`.

    Es el caso mas grave —borrar la evidencia— y el que se perderia mirando solo
    la cabecera `+++`. Ademas no aporta rangos nuevos: un fichero que ya no
    existe no tiene lineas que la onda pueda tocar.
    """
    diff = (
        "diff --git a/tests/test_caja.py b/tests/test_caja.py\n"
        "deleted file mode 100644\n"
        "index 1234567..0000000\n"
        "--- a/tests/test_caja.py\n"
        "+++ /dev/null\n"
        "@@ -1,2 +0,0 @@\n"
        "-def test_uno():\n"
        "-    assert caja() == 1\n"
    )

    files = changes.parse_diff(diff)

    assert list(files) == ["tests/test_caja.py"]
    entrada = files["tests/test_caja.py"]
    assert entrada["deleted"] is True
    assert entrada["added"] == []
    assert entrada["removed"] == ["def test_uno():", "    assert caja() == 1"]
    assert changes._hunks_py(diff) == {}


def test_un_fichero_binario_no_aporta_lineas_ni_ensucia_al_vecino():
    """Un binario no trae `+++` ni hunks: ni entra al informe ni contamina.

    Sus cabeceras (`Binary files ... differ`) caen entre dos ficheros del mismo
    diff; el riesgo real es que se contabilicen como parte del fichero de test
    que va detras.
    """
    diff = (
        "diff --git a/tests/fixtures/blob.png b/tests/fixtures/blob.png\n"
        "new file mode 100644\n"
        "index 0000000..89abcde\n"
        "Binary files /dev/null and b/tests/fixtures/blob.png differ\n"
        "diff --git a/tests/test_caja.py b/tests/test_caja.py\n"
        "index 1111111..2222222 100644\n"
        "--- a/tests/test_caja.py\n"
        "+++ b/tests/test_caja.py\n"
        "@@ -1,2 +1,2 @@ def test_uno():\n"
        " def test_uno():\n"
        "-    assert caja() == 1\n"
        "+    assert caja() == 2\n"
    )

    files = changes.parse_diff(diff)

    assert list(files) == ["tests/test_caja.py"]
    assert files["tests/test_caja.py"]["added"] == ["    assert caja() == 2"]
    assert files["tests/test_caja.py"]["removed"] == ["    assert caja() == 1"]
    assert changes._hunks_py(diff) == {"tests/test_caja.py": [(1, 2)]}


def test_varios_hunks_del_mismo_fichero_se_acumulan_sin_pisarse():
    """Un fichero con N hunks: una entrada, N secciones, N rangos.

    Las secciones son lo que impide que un borrado en una funcion se enmascare
    con un test nuevo en otra, asi que cada hunk tiene que quedar por separado
    ademas de sumar al total del fichero.
    """
    diff = (
        "diff --git a/tests/test_caja.py b/tests/test_caja.py\n"
        "index 1111111..2222222 100644\n"
        "--- a/tests/test_caja.py\n"
        "+++ b/tests/test_caja.py\n"
        "@@ -1,3 +1,3 @@ def test_uno():\n"
        " def test_uno():\n"
        "-    assert caja() == 1\n"
        "+    assert caja() == 2\n"
        "@@ -20,4 +21,5 @@ def test_dos():\n"
        " def test_dos():\n"
        "-    assert caja() == 9\n"
        "+    assert caja() == 8\n"
        "+    assert caja() != 0\n"
    )

    entrada = changes.parse_diff(diff)["tests/test_caja.py"]

    assert entrada["added"] == [
        "    assert caja() == 2",
        "    assert caja() == 8",
        "    assert caja() != 0",
    ]
    assert entrada["removed"] == ["    assert caja() == 1", "    assert caja() == 9"]
    assert [s["func"] for s in entrada["sections"]] == ["def test_uno():", "def test_dos():"]
    assert [(len(s["added"]), len(s["removed"])) for s in entrada["sections"]] == [(1, 1), (2, 1)]
    # cada hunk deja su propio rango `+c,d` para la onda
    assert changes._hunks_py(diff) == {"tests/test_caja.py": [(1, 3), (21, 25)]}
# --- test_signals: casos borde ---


def test_reescribir_una_asercion_en_otro_estilo_no_es_perdida(tmp_path):
    """Migrar `assertEqual(a, b)` a `assert a == b` quita una linea y pone otra
    distinta: no es el mismo texto retocado, es una aserción sustituida por su
    equivalente. Contarlo como perdida seria cobrar peaje por un refactor limpio,
    y ese peaje es lo que manda una revision a --no-verify."""
    root = _repo(tmp_path)
    _write(
        root,
        "tests/test_caja.py",
        "def test_x():\n    self.assertEqual(total(), 6)\n    self.assertIn(3, items())\n",
    )
    _commit(root, "base")
    _write(
        root,
        "tests/test_caja.py",
        "def test_x():\n    assert total() == 6\n    assert 3 in items()\n",
    )
    _commit(root, "migra a assert pelado")

    senales = _senales(changes.analyze(root, "HEAD~1..HEAD"))
    assert "ASSERT_REMOVED" not in senales
    assert "ASSERT_WEAKENED" not in senales


def test_una_asercion_escrita_dentro_de_una_cadena_no_compensa_a_la_que_falta(tmp_path):
    """Lo que vive dentro de un literal es dato, no comprobacion. Si contara como
    aserción puesta, taparia la que se acaba de quitar escribiendo la palabra."""
    root = _repo(tmp_path)
    _write(
        root,
        "tests/test_caja.py",
        "def test_x():\n    assert total() == 6\n    assert nombre() == 'ok'\n",
    )
    _commit(root, "base")
    _write(
        root,
        "tests/test_caja.py",
        "def test_x():\n    plantilla = 'assert total() == 6'\n    assert nombre() == 'ok'\n",
    )
    _commit(root, "cambia la asercion por su texto")

    senales = _senales(changes.analyze(root, "HEAD~1..HEAD"))
    assert "ASSERT_REMOVED" in senales


def test_borrar_una_linea_que_solo_nombra_una_asercion_no_levanta_nada(tmp_path):
    """La otra cara: quitar un literal que MENCIONA un assert no pierde ninguna
    comprobacion, asi que tampoco puede figurar como aserción quitada."""
    root = _repo(tmp_path)
    _write(
        root,
        "tests/test_caja.py",
        "def test_x():\n    plantilla = 'assert total() == 6'\n    assert total() == 6\n",
    )
    _commit(root, "base")
    _write(root, "tests/test_caja.py", "def test_x():\n    assert total() == 6\n")
    _commit(root, "quita el literal")

    assert changes.analyze(root, "HEAD~1..HEAD")["flags"] == []


def test_un_diff_de_solo_borrado_no_se_confunde_con_el_fichero_entero(tmp_path):
    """Un hunk sin una sola linea añadida (`+c,0`) es el caso donde el neto por
    funcion no tiene con que restar. Tiene que salir la perdida, y tiene que salir
    como perdida — no como TEST_FILE_DELETED, que es una señal mas grave."""
    root = _repo(tmp_path)
    _write(
        root,
        "tests/test_caja.py",
        "def test_uno():\n    assert 1 == 1\n    assert 2 == 2\n\n"
        "def test_dos():\n    assert 3 == 3\n",
    )
    _commit(root, "base")
    _write(root, "tests/test_caja.py", "def test_uno():\n    assert 1 == 1\n")
    _commit(root, "solo borra lineas")

    report = changes.analyze(root, "HEAD~1..HEAD")
    senales = _senales(report)
    assert "TEST_FILE_DELETED" not in senales
    assert {"TEST_REMOVED", "ASSERT_REMOVED"} <= senales
    assert report["test_files_changed"] == 1

def test_el_rename_puro_fuera_del_patron_de_tests_sale():
    """Un rename sin cambio de contenido no emite ---/+++ (git solo escribe
    rename from/to): renombrar un fichero de tests fuera del patron era la via
    silenciosa de perder la suite entera sin borrar una linea."""
    diff = (
        "diff --git a/tests/test_util.py b/galaxybrain/util_probado.py\n"
        "similarity index 100%\n"
        "rename from tests/test_util.py\n"
        "rename to galaxybrain/util_probado.py\n"
    )
    senales = changes.test_signals(changes.parse_diff(diff))
    assert [s["signal"] for s in senales] == ["TEST_FILE_RENAMED_OUT"]
    assert "galaxybrain/util_probado.py" in senales[0]["detail"]


def test_el_rename_dentro_del_patron_de_tests_no_levanta_nada():
    diff = (
        "diff --git a/tests/test_a.py b/tests/test_b.py\n"
        "similarity index 100%\n"
        "rename from tests/test_a.py\n"
        "rename to tests/test_b.py\n"
    )
    assert changes.test_signals(changes.parse_diff(diff)) == []


# --- FIRMA_CAMBIADA_SIN_LLAMANTES ------------------------------------------


def test_cambiar_firma_sin_tocar_llamantes_sale(tmp_path):
    """El caso positivo: la firma de una funcion cambia y ningun llamante
    resuelto fue tocado en el diff. Es un HECHO del AST + grafo."""
    root = _repo(tmp_path)
    _write(root, "lib.py", "def helper(x):\n    return x\n")
    _write(root, "app.py", "from lib import helper\n\ndef main():\n    return helper(1)\n")
    _commit(root, "base")
    # Cambia la firma de helper: aniade un parametro.
    _write(root, "lib.py", "def helper(x, y):\n    return x\n")
    _commit(root, "cambia firma sin tocar llamante")

    report = changes.analyze(root, "HEAD~1..HEAD")
    assert "FIRMA_CAMBIADA_SIN_LLAMANTES" in _senales(report)
    flag = next(f for f in report["flags"] if f["signal"] == "FIRMA_CAMBIADA_SIN_LLAMANTES")
    assert "lib.helper" in flag["detail"]
    assert "app.main" in flag["evidence"]


def test_cambiar_firma_Y_actualizar_llamante_no_sale(tmp_path):
    """El control negativo: si el llamante se toca, la senal NO debe salir.
    Un detector que no sabe callarse fabrica los falsos positivos que acaban
    en --no-verify."""
    root = _repo(tmp_path)
    _write(root, "lib.py", "def helper(x):\n    return x\n")
    _write(root, "app.py", "from lib import helper\n\ndef main():\n    return helper(1)\n")
    _commit(root, "base")
    # Cambia la firma Y actualiza el llamante.
    _write(root, "lib.py", "def helper(x, y):\n    return x\n")
    _write(root, "app.py", "from lib import helper\n\ndef main():\n    return helper(1, y=2)\n")
    _commit(root, "cambia firma y actualiza llamante")

    report = changes.analyze(root, "HEAD~1..HEAD")
    assert "FIRMA_CAMBIADA_SIN_LLAMANTES" not in _senales(report)


def test_firma_cambiada_sale_con_staged(tmp_path):
    """La senal tiene que funcionar tambien con --staged, que es el modo que
    usa el pre-commit."""
    root = _repo(tmp_path)
    _write(root, "lib.py", "def helper(x):\n    return x\n")
    _write(root, "app.py", "from lib import helper\n\ndef main():\n    return helper(1)\n")
    _commit(root, "base")
    _write(root, "lib.py", "def helper(x, y):\n    return x\n")
    _run(root, "git", "add", "-A")

    report = changes.analyze(root, staged=True)
    assert "FIRMA_CAMBIADA_SIN_LLAMANTES" in _senales(report)


def test_la_linea_borrada_que_empieza_por_dos_guiones_se_cuenta():
    """El contenido "-- ..." borrado sale en el diff como "---...": el filtro
    antiguo lo confundia con la cabecera y lo infracontaba."""
    diff = (
        "diff --git a/tests/test_sql.py b/tests/test_sql.py\n"
        "--- a/tests/test_sql.py\n"
        "+++ b/tests/test_sql.py\n"
        "@@ -1,2 +1,1 @@\n"
        "-consulta = 1\n"
        "--- comentario sql borrado\n"
    )
    removed = changes.parse_diff(diff)["tests/test_sql.py"]["removed"]
    assert "-- comentario sql borrado" in removed


def test_un_parametro_con_default_NO_levanta_la_senal(tmp_path):
    """Añadir `eco=False` no rompe a ningun llamante: no tocarlos es lo
    CORRECTO. Antes la señal cantaba igual y sobre historia real dio 3 de 3
    avisos ciertos pero inaccionables (8-ago) — exactamente el ruido que manda
    una revision a --no-verify."""
    root = _repo(tmp_path)
    _write(root, "lib.py", "def helper(x):\n    return x\n")
    _write(root, "app.py", "from lib import helper\n\ndef main():\n    return helper(1)\n")
    _commit(root, "base")
    _write(root, "lib.py", "def helper(x, eco=False):\n    return x\n")
    _commit(root, "parametro nuevo CON default: retrocompatible")

    assert "FIRMA_CAMBIADA_SIN_LLAMANTES" not in _senales(changes.analyze(root, "HEAD~1..HEAD"))


def test_la_frontera_de_lo_que_rompe_una_llamada():
    """Lo que decide la señal, aislado: obligatorio nuevo o parametro que se va.
    Con *args/**kwargs no se razona barato y no se acusa (falso negativo antes
    que falso positivo)."""
    rompe = changes._firma_rompe_llamadas
    assert rompe("(a, b)", "(a, b, base)")            # obligatorio nuevo
    assert rompe("(a, b)", "(a)")                     # desaparece uno
    assert not rompe("(a, b)", "(a, b, eco=False)")   # retrocompatible
    assert not rompe("(a, b)", "(a, b)")              # igual
    assert not rompe("(a, **kw)", "(a, b, **kw)")     # no se razona: no se acusa
