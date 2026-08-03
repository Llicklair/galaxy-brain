import os
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture(autouse=True)
def gb_home(tmp_path, monkeypatch):
    """Historico aislado por test — para TODOS los tests, no solo los que lo piden.

    Era opt-in y la libreta de usos lo delato: una pasada de la suite metio ~30
    invocaciones en el termometro REAL del usuario, porque los tests que llaman a
    `cli.main` sin pedir este fixture escribian en el home de verdad. La norma va
    en el defecto: el aislamiento no puede depender de que cada test se acuerde."""
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
