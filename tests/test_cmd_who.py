"""`gb who`: la superficie CLI de la actividad derivada.

La mecanica de `instantanea()` ya la cubre test_actividad.py; aqui se prueba
solo el contrato del comando — que existe, que termina bien y que dice la
verdad cuando no hay nada que derivar.
"""

import subprocess
import sys


def _who(*args):
    return subprocess.run(
        [sys.executable, "-m", "galaxybrain.cli", "who", *args],
        capture_output=True, text=True, timeout=180)


def test_sin_git_lo_dice_y_no_revienta(tmp_path):
    (tmp_path / "calc.py").write_text("def suma(a, b):\n    return a + b\n",
                                      encoding="utf-8")
    p = _who(str(tmp_path))
    assert p.returncode == 0
    assert "sin repositorio git" in p.stdout


def test_json_trae_las_claves_del_contrato(tmp_path):
    import json

    (tmp_path / "calc.py").write_text("def suma(a, b):\n    return a + b\n",
                                      encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), timeout=60)
    p = _who(str(tmp_path), "--json")
    assert p.returncode == 0
    foto = json.loads(p.stdout)
    for clave in ("base", "agentes", "por_nodo", "cruces"):
        assert clave in foto
