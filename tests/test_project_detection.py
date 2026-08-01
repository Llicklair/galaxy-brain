"""A que proyecto pertenece un fallo.

Importa mas de lo que parece: si esto se equivoca, `gb last` dentro de tu repo
no encuentra el fallo que acabas de provocar, y la herramienta parece rota
aunque haya capturado todo correctamente.
"""

import subprocess
import sys

from galaxybrain import store

PRELUDIO = "import galaxybrain; galaxybrain.install()\n"


def _repo(tmp_path, name):
    repo = tmp_path / name
    (repo / ".git").mkdir(parents=True)
    return repo


def test_el_proyecto_es_el_del_script_no_el_del_cwd(gb_home, child_env, tmp_path):
    """Lanzar `python ../otro-repo/script.py` desde aqui no convierte el fallo
    en un fallo de aqui."""
    proyecto = _repo(tmp_path, "proyecto-real")
    desde = _repo(tmp_path, "otro-sitio")

    script = proyecto / "app.py"
    script.write_text(PRELUDIO + "raise ValueError('roto')\n", encoding="utf-8")

    subprocess.run(
        [sys.executable, str(script)],
        cwd=str(desde),
        env=child_env,
        capture_output=True,
        text=True,
        timeout=60,
    )

    entrada = store.read_index()[0]
    assert entrada["project"] == str(proyecto)


def test_sin_script_en_disco_se_usa_el_cwd(gb_home, child_env, tmp_path):
    """`python -c` no tiene fichero: ahi el cwd es la unica senal que hay."""
    proyecto = _repo(tmp_path, "proyecto-repl")

    subprocess.run(
        [sys.executable, "-c", PRELUDIO + "raise ValueError('roto')"],
        cwd=str(proyecto),
        env=child_env,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert store.read_index()[0]["project"] == str(proyecto)


def test_un_script_suelto_sin_repo_no_inventa_proyecto(gb_home, child_env, tmp_path):
    suelto = tmp_path / "suelto"
    suelto.mkdir()
    script = suelto / "prueba.py"
    script.write_text(PRELUDIO + "raise ValueError('roto')\n", encoding="utf-8")

    subprocess.run(
        [sys.executable, str(script)],
        cwd=str(suelto),
        env=child_env,
        capture_output=True,
        text=True,
        timeout=60,
    )

    entrada = store.read_index()[0]
    assert entrada["project"] is None
    assert entrada["id"]  # pero el fallo se guarda igual


def test_subdirectorio_profundo_encuentra_la_raiz(gb_home, child_env, tmp_path):
    proyecto = _repo(tmp_path, "monorepo")
    hondo = proyecto / "servicios" / "api" / "src"
    hondo.mkdir(parents=True)
    script = hondo / "main.py"
    script.write_text(PRELUDIO + "raise ValueError('roto')\n", encoding="utf-8")

    subprocess.run(
        [sys.executable, str(script)],
        cwd=str(hondo),
        env=child_env,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert store.read_index()[0]["project"] == str(proyecto)


def test_el_cli_filtra_por_el_proyecto_donde_estas(gb_home, child_env, tmp_path):
    uno = _repo(tmp_path, "repo-uno")
    dos = _repo(tmp_path, "repo-dos")
    for repo, mensaje in ((uno, "fallo-de-uno"), (dos, "fallo-de-dos")):
        script = repo / "app.py"
        script.write_text(PRELUDIO + "raise ValueError(%r)\n" % mensaje, encoding="utf-8")
        subprocess.run(
            [sys.executable, str(script)],
            cwd=str(repo),
            env=child_env,
            capture_output=True,
            text=True,
            timeout=60,
        )

    result = subprocess.run(
        [sys.executable, "-m", "galaxybrain.cli", "list", "--json"],
        cwd=str(uno),
        env=child_env,
        capture_output=True,
        text=True,
        timeout=60,
    )

    import json

    # `gb list` agrupa por firma; el filtro de proyecto debe dejar solo repo-uno.
    grupos = json.loads(result.stdout)
    assert len(grupos) == 1
    assert grupos[0]["last_message"] == "fallo-de-uno"
