"""Los temporales de la suite no pueden caer dentro del repo.

Diecinueve tests comprueban cosas del tipo "sin repo git no se inventa un
proyecto". Con su `tmp_path` DENTRO de galaxy-brain encuentran este repo como
padre y fallan: diecinueve rojos que no son bugs, en un pre-commit que entonces
hay que saltarse. Y el modo simetrico es peor — un test que se apoye en
encontrar un repo pasaria en verde por el de al lado.

Paso de verdad: en la maquina de Marcos `TMPDIR` apunta al propio repo
(17-ago-2026). El arreglo vive en `conftest.pytest_configure`; esto es el
detector que avisa si alguien lo desarma, y corre en cada pasada.
"""

import os
import subprocess
import sys
import tempfile

from conftest import RAIZ, _dentro_del_repo


def test_tmp_path_cae_fuera_del_repo(tmp_path):
    assert not _dentro_del_repo(tmp_path), (
        "tmp_path esta dentro del repo (%s): los tests de 'sin repo git' van a "
        "encontrar galaxy-brain como padre" % tmp_path)


def test_el_temporal_del_sistema_tambien(tmp_path):
    """No basta con `tmp_path`: hay codigo de gb que clasifica una captura por si
    cae bajo `gettempdir()`, y un `mkdtemp()` directo no pasa por el fixture."""
    assert not _dentro_del_repo(tempfile.gettempdir())
    creado = tempfile.mkdtemp()
    try:
        assert not _dentro_del_repo(creado)
    finally:
        os.rmdir(creado)


def test_un_hijo_hereda_el_temporal_saneado(child_env, tmp_path):
    """Los subprocesos de la suite copian `os.environ`. Si el saneo no viajara,
    un hijo escribiria sus temporales en el repo."""
    p = subprocess.run(
        [sys.executable, "-c", "import tempfile; print(tempfile.gettempdir())"],
        capture_output=True, text=True, env=child_env, timeout=60)
    assert p.returncode == 0
    assert not _dentro_del_repo(p.stdout.strip())


def test_el_detector_reconoce_lo_que_esta_dentro():
    """El control: si `_dentro_del_repo` dijera que no a todo, los tres de arriba
    pasarian sin comprobar nada."""
    assert _dentro_del_repo(RAIZ)
    assert _dentro_del_repo(os.path.join(str(RAIZ), "pytest-of-alguien", "x"))
    assert not _dentro_del_repo(os.path.dirname(str(RAIZ)))
