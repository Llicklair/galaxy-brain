"""Lo que la gate NO puede hacer nunca: pasar en verde sin haber comprobado nada.

Dos formas de cubrir cero y no enterarte, ambas reales y encontradas usándola:
(a) apuntarla a una ruta que no existe — un typo en el hook y no vuelve a mirar;
(b) que la raíz solo contenga subproyectos ajenos (fixtures, vendorizados), que
    ahora se podan — si se podan TODOS, no queda nada que gatear.

En los dos casos el contrato es el mismo, el del invariante 4: salir != 0 y
decirlo. Y lo podado se enumera siempre: reducir cobertura en silencio convierte
un "sin ciclos" en una mentira cómoda.
"""

import os
import subprocess

from galaxybrain import cli, graph

# Relativos a proposito: asi el ciclo del anidado existe se llame como se llame
# el paquete, que depende de la raiz desde la que se analice.
CICLO_A = "from .b import cosa\notra = 2\n"
CICLO_B = "from .a import otra\ncosa = 1\n"


def _run(cwd, *args):
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


def _write(root, rel, content):
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def _nested_project(root, rel):
    """Un proyecto ajeno anidado, con ciclo propio, como los fixtures de eval/."""
    _write(root, rel + "/pyproject.toml", "[project]\nname = 'ajeno'\n")
    _write(root, rel + "/otro/__init__.py", "")
    _write(root, rel + "/otro/a.py", CICLO_A)
    _write(root, rel + "/otro/b.py", CICLO_B)


# --- (a) la raiz que no esta -------------------------------------------------


def test_raiz_inexistente_es_error_no_verde(tmp_path):
    root = os.path.join(str(tmp_path), "no-existe")
    report = graph.analyze(root)

    assert report["root_error"]
    assert report["modules"] == 0
    assert cli.main(["graph", root, "--gate", "--color", "never"]) == 1


def test_raiz_inexistente_falla_tambien_sin_gate(tmp_path):
    """Es un error de USO: devolver 0 aqui haria pasar un typo por analisis correcto."""
    root = os.path.join(str(tmp_path), "no-existe")

    assert cli.main(["graph", root, "--color", "never"]) == 1


def test_raiz_sin_modulos_no_pasa_la_gate(tmp_path):
    root = str(tmp_path)
    _write(root, "LEEME.md", "sin python aqui\n")

    assert graph.analyze(root)["modules"] == 0
    assert cli.main(["graph", root, "--gate", "--color", "never"]) == 1


def test_raiz_valida_con_modulos_sigue_pasando(tmp_path):
    """El contrapeso: la gate no se ha vuelto una que chilla por todo."""
    root = str(tmp_path)
    _write(root, "app/__init__.py", "")
    _write(root, "app/uno.py", "valor = 1\n")

    assert cli.main(["graph", root, "--gate", "--color", "never"]) == 0


# --- (b) los subproyectos anidados -------------------------------------------


def test_subproyecto_anidado_se_poda_y_se_dice(tmp_path):
    root = str(tmp_path)
    _write(root, "app/__init__.py", "")
    _write(root, "app/uno.py", "valor = 1\n")
    _nested_project(root, "fixtures/caso1")

    report = graph.analyze(root)

    assert report["cycles"] == []  # el ciclo del ajeno no es mio
    assert report["skipped_nested"] == ["fixtures/caso1"]
    assert cli.main(["graph", root, "--gate", "--color", "never"]) == 0


def test_include_nested_los_vuelve_a_meter(tmp_path):
    """La poda es el defecto, no una decision irreversible."""
    root = str(tmp_path)
    _write(root, "app/__init__.py", "")
    _nested_project(root, "fixtures/caso1")

    report = graph.analyze(root, include_nested=True)

    assert report["cycles"], "con --include-nested el ciclo del anidado vuelve a contar"
    assert report["skipped_nested"] == []


def test_podarlo_todo_no_puede_salir_en_verde(tmp_path):
    """El riesgo que introduce la poda: un monorepo de paquetes con pyproject
    propio se quedaria sin nada que analizar. Verde ahi seria falsa cobertura."""
    root = str(tmp_path)
    _nested_project(root, "paquetes/uno")
    _nested_project(root, "paquetes/dos")

    report = graph.analyze(root)

    assert report["modules"] == 0
    assert len(report["skipped_nested"]) == 2
    assert cli.main(["graph", root, "--gate", "--color", "never"]) == 1


def test_marcador_en_la_propia_raiz_no_se_poda_a_si_misma(tmp_path):
    """El caso normal: el proyecto que analizas tiene su pyproject.toml."""
    root = str(tmp_path)
    _write(root, "pyproject.toml", "[project]\nname = 'mio'\n")
    _write(root, "app/__init__.py", "")
    _write(root, "app/uno.py", "valor = 1\n")

    report = graph.analyze(root)

    assert report["modules"] == 2
    assert report["skipped_nested"] == []


def test_setup_py_tambien_marca_subproyecto(tmp_path):
    root = str(tmp_path)
    _write(root, "app/__init__.py", "")
    _write(root, "vendor/lib/setup.py", "from setuptools import setup\n")
    _write(root, "vendor/lib/mod.py", "valor = 1\n")

    assert graph.analyze(root)["skipped_nested"] == ["vendor/lib"]


def test_baseline_de_git_poda_igual_que_el_working_tree(tmp_path):
    """Si la baseline viera los anidados y el working tree no (o al reves), el
    delta inventaria ciclos 'nuevos' que solo son un cambio de frontera."""
    root = str(tmp_path)
    _run(root, "git", "init", "-q")
    _run(root, "git", "config", "user.email", "t@t")
    _run(root, "git", "config", "user.name", "t")
    _run(root, "git", "config", "commit.gpgsign", "false")
    _write(root, "app/__init__.py", "")
    _write(root, "app/uno.py", "valor = 1\n")
    _nested_project(root, "fixtures/caso1")
    _run(root, "git", "add", "-A")
    _run(root, "git", "commit", "-q", "-m", "base")

    base = graph.build_graph_from_git(root, "HEAD")

    assert base is not None
    _nodes, base_edges, _errors = base
    assert not any(n.startswith("fixtures.") for n in _nodes)
    assert graph.find_cycles(base_edges) == []

    report = graph.analyze(root, since="HEAD")
    assert report["baseline_ok"] is True
    assert report["new_pairs"] == []
