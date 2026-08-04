"""La onda del diff: qué símbolos toca un cambio y cuántos les llaman.

INFORMA, nunca gatea (regla 9): "has tocado algo con N llamantes" es un dato
que se pone delante de quien decide; gatearlo fabricaría los falsos positivos
que acaban en `--no-verify`. Y calla entera cuando el diff no toca Python.
"""

import os
import subprocess

from galaxybrain import changes, render


def _run(cwd, *args):
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


def _repo(tmp_path):
    root = str(tmp_path / "proyecto")
    os.makedirs(root, exist_ok=True)
    _run(root, "git", "init", "-q")
    _run(root, "git", "config", "user.email", "t@t")
    _run(root, "git", "config", "user.name", "t")
    _run(root, "git", "config", "commit.gpgsign", "false")
    return root


def _write(root, rel, content="def f():\n    return 1\n"):
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    return path


def _commit(root, msg):
    _run(root, "git", "add", "-A")
    _run(root, "git", "commit", "-q", "-m", msg)


def test_hunks_py_saca_rangos_de_todos_los_py_y_de_nada_mas():
    """Un .txt no tiene nodos; un fichero borrado entero tampoco. Y el hunk de
    solo borrado (+c,0) toca el punto c: el simbolo alrededor sigue afectado."""
    diff = "\n".join([
        "--- a/lib.py",
        "+++ b/lib.py",
        "@@ -2,1 +2,3 @@ def ayuda():",
        "+    x = 1",
        "@@ -9,1 +8,0 @@ def base():",
        "--- a/notas.txt",
        "+++ b/notas.txt",
        "@@ -1 +1,2 @@",
        "+da igual",
        "--- a/borrado.py",
        "+++ /dev/null",
        "@@ -1,3 +0,0 @@",
    ])

    assert changes._hunks_py(diff) == {"lib.py": [(2, 4), (8, 8)]}


def test_la_onda_dice_el_simbolo_tocado_y_sus_llamantes(tmp_path):
    root = _repo(tmp_path)
    _write(root, "lib.py", "def ayuda():\n    return 1\n\ndef base():\n    return 2\n")
    _write(root, "app.py", "from lib import ayuda\n\ndef main():\n    return ayuda()\n")
    _commit(root, "base")
    _write(root, "lib.py", "def ayuda():\n    return 99\n\ndef base():\n    return 2\n")
    _run(root, "git", "add", "-A")

    report = changes.analyze(root, staged=True)
    assert [(t["qual"], t["callers"]) for t in report["onda"]] == [("lib.ayuda", 1)]


def test_tocar_un_metodo_no_lista_tambien_su_clase(tmp_path):
    """El toque intersecta el metodo Y la clase entera que lo contiene; listar
    los dos seria contar el mismo cambio dos veces. Se queda el mas interno."""
    root = _repo(tmp_path)
    _write(root, "cosa.py",
           "class Cosa:\n    def uno(self):\n        return 1\n\n"
           "    def dos(self):\n        return 2\n")
    _commit(root, "base")
    _write(root, "cosa.py",
           "class Cosa:\n    def uno(self):\n        return 99\n\n"
           "    def dos(self):\n        return 2\n")
    _run(root, "git", "add", "-A")

    report = changes.analyze(root, staged=True)
    assert [t["qual"] for t in report["onda"]] == ["cosa.Cosa.uno"]


def test_sin_python_tocado_la_onda_calla(tmp_path):
    root = _repo(tmp_path)
    _write(root, "codigo.py")
    _write(root, "notas.txt", "v1\n")
    _commit(root, "base")
    _write(root, "notas.txt", "v2\n")
    _run(root, "git", "add", "-A")

    report = changes.analyze(root, staged=True)
    assert report["onda"] == []


def test_el_brief_sigue_siendo_una_linea_con_su_recuento_de_onda(tmp_path):
    root = _repo(tmp_path)
    _write(root, "lib.py", "def ayuda():\n    return 1\n")
    _write(root, "app.py", "from lib import ayuda\n\ndef main():\n    return ayuda()\n")
    _commit(root, "base")
    _write(root, "lib.py", "def ayuda():\n    return 99\n")
    _run(root, "git", "add", "-A")

    report = changes.analyze(root, staged=True)
    brief = render.render_changes(report, render.Style(False), brief=True)
    assert "onda: 1 simbolo(s)" in brief
    assert "\n" not in brief

    entero = render.render_changes(report, render.Style(False))
    assert "ONDA del diff" in entero
    assert "lib.ayuda" in entero
