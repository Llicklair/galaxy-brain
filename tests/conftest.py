import os
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# El .pth de la consola importa galaxybrain al ARRANCAR el interprete, antes de
# que este conftest toque sys.path. En el checkout de siempre da igual (es el
# mismo fichero); en una copia de trabajo aparte no: sys.modules ya trae el
# paquete del OTRO checkout y la suite pasa en verde probando codigo que no es
# el que tienes delante. Se echan esas copias para que el import las rehaga
# desde SRC — el sitio del que estos tests dicen hablar.
for _nombre, _modulo in list(sys.modules.items()):
    if _nombre == "galaxybrain" or _nombre.startswith("galaxybrain."):
        _origen = getattr(_modulo, "__file__", None)
        if not _origen or SRC not in Path(_origen).resolve().parents:
            del sys.modules[_nombre]


@pytest.fixture(autouse=True)
def _sin_entorno_de_hook(monkeypatch):
    """El pre-commit corre esta suite DENTRO de un hook, y git inyecta
    GIT_INDEX_FILE / GIT_DIR / GIT_WORK_TREE en el entorno del hook. Un test que
    hace `git add` en su repo temporal, con ese entorno heredado, escribe EN EL
    INDICE DEL REPO REAL — pasó el 5-ago-2026: los fixtures de un test aparecieron
    staged en galaxy-brain, y la suite era roja dentro del hook y verde fuera.
    Se limpia aqui para toda la suite: el aislamiento no puede depender de que
    cada test se acuerde (la misma ley que gb_home)."""
    for var in list(os.environ):
        if var.startswith("GIT_") and var not in ("GIT_SSH", "GIT_SSH_COMMAND"):
            monkeypatch.delenv(var, raising=False)


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
