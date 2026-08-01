"""`floor <subdir>` responde por el subdirectorio, y tiene que DECIRLO.

Reportado usando gb de verdad (1-ago-2026): `gb floor src` decia "ni git, ni
contenedor, ni CI" y "no encuentro comando de tests" — con el repo justo encima
teniendo git, CI y pytest. Daba 4/8 sin cubrir donde la verdad del proyecto era
1/8.

El numero no esta mal: el suelo se mide donde se lo pides, y `floor src` responde
por `src`. Lo que estaba mal era el SILENCIO. Sin decir que estas mirando una
parte, ese 4/8 se lee como el diagnostico del proyecto entero. Mismo patron que
el gate mudo: la salida es correcta y se entiende al reves.
"""

import os
import subprocess

from galaxybrain import floor, render


def _repo(tmp_path):
    raiz = str(tmp_path)
    for rel, cuerpo in (
        ("pyproject.toml", "[tool.pytest.ini_options]\ntestpaths = ['tests']\n"),
        ("tests/test_algo.py", "def test_ok():\n    assert True\n"),
        ("src/pkg/__init__.py", ""),
        ("src/pkg/a.py", "def f():\n    return 1\n"),
    ):
        ruta = os.path.join(raiz, *rel.split("/"))
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, "w", encoding="utf-8") as handle:
            handle.write(cuerpo)
    subprocess.run(["git", "init", "-q", raiz], capture_output=True)
    return raiz


def test_en_la_raiz_no_avisa_de_nada(tmp_path):
    """El aviso solo aparece cuando aporta. Si saliera siempre seria ruido."""
    informe = floor.analyze(_repo(tmp_path))
    assert informe["subdir_de"] is None
    assert "SUBDIRECTORIO" not in render.render_floor(informe, render.Style(False))


def test_en_un_subdirectorio_lo_dice_y_nombra_la_raiz(tmp_path):
    raiz = _repo(tmp_path)
    informe = floor.analyze(os.path.join(raiz, "src"))

    assert informe["subdir_de"] is not None
    salida = render.render_floor(informe, render.Style(False))
    assert "SUBDIRECTORIO" in salida
    assert "puede estar arriba" in salida


def test_el_aviso_va_pegado_al_titular(tmp_path):
    """Si se fuera al pie, el numero de arriba ya se habria leido como el
    diagnostico del proyecto entero — que es justo el fallo que arregla."""
    raiz = _repo(tmp_path)
    lineas = render.render_floor(
        floor.analyze(os.path.join(raiz, "src")), render.Style(False)
    ).splitlines()
    assert lineas[0].startswith("El suelo de")
    assert "SUBDIRECTORIO" in lineas[1]


def test_el_numero_NO_cambia(tmp_path):
    """No se sube a mirar nada: `floor src` sigue respondiendo por `src`.
    Cambiar la respuesta seria peor que callarla — dejaria de medir lo que pides."""
    raiz = _repo(tmp_path)
    sub = floor.analyze(os.path.join(raiz, "src"))
    assert sub["root"].endswith("src")
    faltan = [l for l in sub["levels"] if l["status"] == "falta"]
    assert faltan, "el subdirectorio sigue sin tests ni git propios, y eso se reporta"


def test_sin_repo_git_no_se_inventa_una_raiz(tmp_path):
    (tmp_path / "suelto").mkdir()
    informe = floor.analyze(str(tmp_path / "suelto"))
    assert informe["subdir_de"] is None
