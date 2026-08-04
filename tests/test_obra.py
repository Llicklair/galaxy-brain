"""La capa de cambio: lo TOCADO sin commitear, pintado sobre el mapa.

Un hecho de git (`status --porcelain`), nunca un veredicto (regla 9): informa
de que hay obra en marcha, no bloquea nada. Y calla entera sin repo o con el
arbol limpio — una capa fija de ceros seria ruido repetido (H6).
"""

import os
import subprocess

from galaxybrain import cli, symbols, viz


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


def test_los_tocados_son_modificados_y_nuevos_nunca_borrados_ni_ajenos(tmp_path):
    """Un borrado ya no tiene nodo que marcar, y un .txt nunca lo tuvo."""
    root = _repo(tmp_path)
    _write(root, "limpio.py")
    _write(root, "sucio.py")
    _write(root, "borrado.py")
    _write(root, "notas.txt", "no es python\n")
    _commit(root, "base")
    _write(root, "sucio.py", "def f():\n    return 2\n")
    _write(root, "nuevo.py")
    os.remove(os.path.join(root, "borrado.py"))

    ficheros = {os.path.basename(f) for f in cli._ficheros_tocados(root)}
    assert ficheros == {"sucio.py", "nuevo.py"}


def test_sin_repo_git_la_capa_calla(tmp_path):
    _write(str(tmp_path), "suelto.py")

    assert cli._ficheros_tocados(str(tmp_path)) == []


def test_los_tocados_llegan_al_mapa_como_nodos_modulo(tmp_path):
    root = _repo(tmp_path)
    _write(root, "limpio.py")
    _write(root, "sucio.py")
    _commit(root, "base")
    _write(root, "sucio.py", "def f():\n    return 2\n")

    informe = symbols.analyze(root)
    assert cli._tocados_para_mapa(root, informe) == {"sucio"}


def test_las_posiciones_heredadas_viajan_en_el_html(tmp_path):
    """El auto-refresco reiniciaba la fisica y el mapa bailaba cada N segundos:
    las posiciones sobreviven a la recarga por el mismo canal que la camara."""
    root = _repo(tmp_path)
    _write(root, "solo.py")
    _commit(root, "base")

    html = viz.render_graph_cloud(symbols.analyze(root))
    assert "gb-pos:" in html


def test_el_mapa_pinta_la_obra_y_calla_sin_ella(tmp_path):
    root = _repo(tmp_path)
    _write(root, "solo.py")
    _commit(root, "base")
    informe = symbols.analyze(root)

    con = viz.render_graph_cloud(informe, tocados={"solo"})
    sin = viz.render_graph_cloud(informe, tocados=set())
    assert "en obra" in con
    assert "en obra" not in sin
