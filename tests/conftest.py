import os
import sys
import tempfile
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
SRC = RAIZ / "src"


def _dentro_del_repo(ruta):
    try:
        resuelta = Path(ruta).resolve()
    except (OSError, ValueError):
        return False
    return resuelta == RAIZ or RAIZ in resuelta.parents


def pytest_configure(config):
    """Que `tmp_path` NUNCA caiga dentro del repo, venga como venga el entorno.

    En esta maquina `TMPDIR` apunta al propio repo, asi que pytest creaba sus
    temporales en `galaxy-brain/pytest-of-*/`. Diecinueve tests comprueban cosas
    del tipo "sin repo git no se inventa un proyecto": con su tmp_path DENTRO de
    galaxy-brain encuentran este repo como padre y fallan. Diecinueve rojos que
    no son bugs, en un pre-commit que entonces hay que saltarse.

    Y el modo de fallo simetrico es peor: un test que se apoye en encontrar un
    repo pasaria en verde por el de al lado. Un veredicto que depende de una
    variable de entorno de quien corre la suite no es un veredicto.

    Solo se toca si el entorno ya esta roto, y NUNCA si hay `--basetemp`
    explicito: quien lo pide manda. El destino es un subdirectorio DEDICADO,
    nunca el temporal del usuario a pelo — pytest borra el contenido de basetemp
    al arrancar, y apuntarlo a `%TEMP%` seria vaciarselo entero.
    """
    if getattr(config.option, "basetemp", None):
        return
    if not _dentro_del_repo(tempfile.gettempdir()):
        return                      # entorno sano: no se toca nada

    for candidato in (os.environ.get("TEMP"), os.environ.get("TMP"),
                      "/tmp", str(Path.home())):
        if not candidato or _dentro_del_repo(candidato):
            continue
        # El nombre no lleva "galaxy-brain" a proposito: hay tests que verifican
        # que esa cadena NO aparece en el stderr de un hijo (asi comprueban que
        # la consola esta desactivada), y la ruta del script sale en su traceback.
        destino = Path(candidato) / "gb-pytest"
        try:
            destino.mkdir(parents=True, exist_ok=True)
        except OSError:
            continue
        config.option.basetemp = str(destino)
        # `basetemp` arregla `tmp_path`, pero no a quien pregunta por el temporal
        # del sistema: `tempfile.mkdtemp()` directo y, sobre todo, el codigo de gb
        # que clasifica una captura por si cae bajo `gettempdir()`. Con el temporal
        # apuntando al repo, `src/a.py` cuenta como exploracion y la clasificacion
        # se invierte — no es un test fragil, es gb decidiendo mal. Se sanea para
        # la suite entera, hijos incluidos (heredan este entorno).
        for var in ("TMPDIR", "TEMP", "TMP"):
            os.environ[var] = candidato
        tempfile.tempdir = candidato
        return
    # Sin ningun sitio fuera del repo se sigue adelante: fallar aqui dejaria la
    # suite sin correr, que es peor que correrla con los 19 rojos conocidos.
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
