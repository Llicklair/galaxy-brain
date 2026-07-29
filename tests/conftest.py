import os
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture
def gb_home(tmp_path, monkeypatch):
    """Historico aislado por test. Sin esto, los tests escribirian en el
    historico real del usuario, que es justo lo que esta herramienta promete
    no hacer con el repo observado."""
    home = tmp_path / "gb-home"
    monkeypatch.setenv("GB_HOME", str(home))
    monkeypatch.delenv("GB_DISABLE", raising=False)
    monkeypatch.delenv("GB_QUIET", raising=False)
    return home


@pytest.fixture
def child_env(gb_home):
    """Entorno para lanzar un Python hijo con el paquete importable."""
    env = dict(os.environ)
    env["GB_HOME"] = str(gb_home)
    env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
    env.pop("GB_DISABLE", None)
    env.pop("GB_QUIET", None)
    return env
