"""`gb tests`: la seleccion derivada del grafo.

El invariante que gobierna este fichero no es "selecciona poco", es **no miente**:
ante cualquier duda devuelve la suite entera con el motivo escrito. Un falso verde
(la seleccion pasa y la suite entera habria fallado) mata el comando, y por eso hay
un test que lo comprueba de frente ejecutando pytest de verdad.
"""

import os
import subprocess
import sys

import pytest

from galaxybrain import impacted


def _git(root, *args):
    subprocess.run(["git"] + list(args), cwd=str(root), check=True,
                   capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path):
    """Un repo real con un simbolo, un test que lo ejercita y otro que no."""
    root = tmp_path / "proyecto"
    (root / "lib").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "lib" / "__init__.py").write_text("", encoding="utf-8")
    (root / "lib" / "nucleo.py").write_text(
        "def suma(a, b):\n"
        "    return a + b\n"
        "\n"
        "\n"
        "def resta(a, b):\n"
        "    return a - b\n",
        encoding="utf-8")
    (root / "tests" / "__init__.py").write_text("", encoding="utf-8")
    (root / "tests" / "test_suma.py").write_text(
        "from lib.nucleo import suma\n"
        "\n"
        "\n"
        "def test_suma_va():\n"
        "    assert suma(1, 2) == 3\n",
        encoding="utf-8")
    (root / "tests" / "test_resta.py").write_text(
        "from lib.nucleo import resta\n"
        "\n"
        "\n"
        "def test_resta_va():\n"
        "    assert resta(3, 1) == 2\n",
        encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t.t")
    _git(root, "config", "user.name", "t")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "base")
    return root


def _tocar(root, rel, viejo, nuevo):
    path = root / rel
    path.write_text(path.read_text(encoding="utf-8").replace(viejo, nuevo), encoding="utf-8")


def test_selecciona_solo_los_tests_que_alcanzan_lo_tocado(repo):
    _tocar(repo, "lib/nucleo.py", "return a + b", "return b + a")
    _git(repo, "add", "-A")
    report = impacted.analyze(str(repo), staged=True)

    assert report["todo"] is False
    assert report["tests"] == ["tests/test_suma.py"]
    assert "lib.nucleo.suma" in report["symbols"]
    assert report["n_tests"] < report["total_tests"]


def test_el_mismo_veredicto_que_la_suite_entera(repo):
    """El criterio de terminado, ejecutado: misma respuesta, menos trabajo.

    Se rompe `suma` de verdad. Si la seleccion pasara mientras la suite entera
    falla, eso es el falso verde que mata el comando — y este test lo caza.
    """
    _tocar(repo, "lib/nucleo.py", "return a + b", "return a - b")
    _git(repo, "add", "-A")
    report = impacted.analyze(str(repo), staged=True)
    assert report["todo"] is False

    entera = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests"],
                            cwd=str(repo), capture_output=True, text=True)
    seleccion = subprocess.run([sys.executable, "-m", "pytest", "-q"] + report["tests"],
                               cwd=str(repo), capture_output=True, text=True)

    assert entera.returncode != 0, "la suite entera deberia ver el fallo"
    assert seleccion.returncode == entera.returncode, (
        "falso verde: la seleccion no vio lo que la suite entera si ve\n%s" % seleccion.stdout)


def test_tocar_conftest_obliga_a_correr_todo(repo):
    """Un conftest no es llamante de nadie: el AST no puede ver su efecto."""
    (repo / "tests" / "conftest.py").write_text(
        "import pytest\n"
        "\n"
        "\n"
        "@pytest.fixture\n"
        "def algo():\n"
        "    return 1\n",
        encoding="utf-8")
    _git(repo, "add", "-A")
    report = impacted.analyze(str(repo), staged=True)

    assert report["todo"] is True
    assert "conftest.py" in report["motivo"]
    assert len(report["tests"]) == report["total_files"]


def test_un_cambio_fuera_de_todo_simbolo_corre_todo(repo):
    """Una constante a nivel de modulo no cae dentro de ningun def."""
    _tocar(repo, "lib/nucleo.py", "def suma(a, b):", "LIMITE = 10\n\n\ndef suma(a, b):")
    _git(repo, "add", "-A")
    report = impacted.analyze(str(repo), staged=True)

    assert report["todo"] is True
    assert "simbolo" in report["motivo"]


def test_un_diff_vacio_no_selecciona_nada(repo):
    report = impacted.analyze(str(repo), staged=True)
    assert report["tests"] == []
    assert report["todo"] is False
    assert "vacio" in report["motivo"]


def test_los_helpers_de_los_tests_no_entran_en_la_seleccion(repo):
    """El detalle que falseo la primera medicion de esta idea.

    Un helper (`_generar`) vive en un fichero de tests y el grafo lo ve, pero
    pytest no lo colecciona: seleccionarlo como id da `ERROR: not found` y exit
    code 4 — "no tests ran", que en un gate se lee igual de verde que "todo paso".
    """
    assert impacted._es_test("tests.test_x.test_algo", {"kind": "function"}) is True
    assert impacted._es_test("tests.test_x._generar", {"kind": "function"}) is False
    assert impacted._es_test("tests.test_x.Ayuda", {"kind": "class"}) is False
    assert impacted._es_test("lib.nucleo.test_algo", {"kind": "function"}) is False


def test_un_test_tocado_directamente_se_corre_el(repo):
    _tocar(repo, "tests/test_suma.py", "== 3", "== 3  # tocado")
    _git(repo, "add", "-A")
    report = impacted.analyze(str(repo), staged=True)

    assert "tests/test_suma.py" in report["tests"]
    assert report["todo"] is False


def test_sin_tests_que_lo_alcancen_corre_todo_y_lo_dice(repo):
    """Cambiar algo que ningun test ejercita NO es un ahorro: es el dato."""
    (repo / "lib" / "suelto.py").write_text(
        "def nadie_me_llama():\n"
        "    return 1\n",
        encoding="utf-8")
    _git(repo, "add", "-A")
    report = impacted.analyze(str(repo), staged=True)

    assert report["todo"] is True
    assert "ningun test alcanza" in report["motivo"]


def test_un_test_que_lanza_subprocesos_entra_siempre(repo):
    """El agujero que casi deja pasar un falso verde.

    Un test que ejercita el codigo lanzando un subproceso no deja NINGUNA arista
    de llamada: para el AST es una llamada a `subprocess.run` y se acabo. Medido
    en el repo de gb: 17 de 37 ficheros entran por ahi, y romper
    `saferepr.repr_local` hacia fallar `test_end_to_end.py` sin que la seleccion
    lo viera. Van siempre, y el informe dice por que.
    """
    (repo / "tests" / "test_e2e.py").write_text(
        "import subprocess\n"
        "import sys\n"
        "\n"
        "\n"
        "def test_por_subproceso():\n"
        "    r = subprocess.run([sys.executable, '-c', 'print(1)'], capture_output=True)\n"
        "    assert r.returncode == 0\n",
        encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "e2e")

    _tocar(repo, "lib/nucleo.py", "return a + b", "return b + a")
    _git(repo, "add", "-A")
    report = impacted.analyze(str(repo), staged=True)

    assert report["todo"] is False, "sigue siendo una seleccion, no la suite entera"
    assert "tests/test_e2e.py" in report["tests"]
    assert "tests/test_e2e.py" in report["opacos"]
    assert "tests/test_resta.py" not in report["tests"], (
        "el que ni alcanza ni es opaco sigue fuera: si no, esto no selecciona nada")
    assert report["avisos"], "un fichero incluido por otra razon se dice en voz alta"


def test_los_opacos_no_se_cuentan_como_alcanzados(repo):
    """`n_tests` cuenta lo que el grafo alcanza; los opacos son ficheros extra.

    Mezclarlos inflaria el porcentaje y haria creer que la seleccion es mas
    precisa de lo que es.
    """
    (repo / "tests" / "test_e2e.py").write_text(
        "import subprocess\n"
        "\n"
        "\n"
        "def test_algo():\n"
        "    assert subprocess is not None\n",
        encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "e2e")

    _tocar(repo, "lib/nucleo.py", "return a + b", "return b + a")
    _git(repo, "add", "-A")
    report = impacted.analyze(str(repo), staged=True)

    assert report["n_tests"] == 1, "solo test_suma_va alcanza el simbolo por el grafo"
    assert len(report["tests"]) == 2, "y ademas entra el opaco"


def test_cargar_por_ruta_con_importlib_tambien_es_opaco(repo):
    """La misma opacidad por otra puerta: `spec_from_file_location` ejercita un
    fichero cuya ruta se arma en tiempo de ejecucion, asi que el AST no puede
    seguirla — igual que un subproceso.

    En este repo lo usan los tests de `bucle/`, que no es un paquete instalable.
    Ninguno colaba porque TODOS traian ademas `subprocess`; depender de que las
    dos marcas viajen juntas es depender de una coincidencia que un refactor
    deshace.
    """
    (repo / "tests" / "test_por_ruta.py").write_text(
        "import importlib.util\n"
        "import os\n"
        "\n"
        "_RUTA = os.path.join(os.path.dirname(__file__), '..', 'lib', 'nucleo.py')\n"
        "_spec = importlib.util.spec_from_file_location('nucleo_suelto', _RUTA)\n"
        "\n"
        "\n"
        "def test_algo():\n"
        "    assert _spec is not None\n",
        encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "por ruta")

    _tocar(repo, "lib/nucleo.py", "return a + b", "return b + a")
    _git(repo, "add", "-A")
    report = impacted.analyze(str(repo), staged=True)

    assert "tests/test_por_ruta.py" in report["opacos"]
    assert "tests/test_por_ruta.py" in report["tests"]
    assert "tests/test_resta.py" not in report["tests"], (
        "sigue siendo una seleccion: marcar de mas no puede ser correr todo")


def test_worktree_ve_lo_que_no_esta_en_el_indice(repo):
    """El caso de en medio de una edicion: escrito en disco, sin `git add`.

    Es el modo que sirve dentro del bucle de un agente, que edita y quiere saber
    que romper ANTES de preparar nada. Con `--staged` ese cambio es invisible.
    """
    _tocar(repo, "lib/nucleo.py", "return a + b", "return b + a")

    staged = impacted.analyze(str(repo), staged=True)
    assert staged["tests"] == [], "sin `git add` no hay nada en el indice"

    worktree = impacted.analyze(str(repo), worktree=True)
    assert worktree["range"] == "worktree"
    assert "tests/test_suma.py" in worktree["tests"]
    assert worktree["todo"] is False


def test_una_raiz_que_no_existe_es_error_de_uso(tmp_path):
    report = impacted.analyze(str(tmp_path / "no-existe"))
    assert report["range_error"]
    assert report["tests"] == []


def test_sin_git_no_inventa_una_seleccion(tmp_path):
    """Sin repo git no hay diff: la respuesta segura es todo, no una lista corta."""
    root = tmp_path / "pelado"
    (root / "lib").mkdir(parents=True)
    (root / "lib" / "__init__.py").write_text("", encoding="utf-8")
    (root / "lib" / "x.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    report = impacted.analyze(str(root))
    assert report["todo"] is True or report["tests"] == []
    assert report["motivo"]


def test_la_seleccion_usa_rutas_que_pytest_entiende(repo):
    _tocar(repo, "lib/nucleo.py", "return a + b", "return b + a")
    _git(repo, "add", "-A")
    report = impacted.analyze(str(repo), staged=True)

    for ruta in report["tests"]:
        assert "\\" not in ruta, "las rutas van con / para que pytest las coma en Windows"
        assert os.path.exists(os.path.join(str(repo), ruta))


# --- la puerta de los pasados como VALOR -------------------------------------
#
# Medida el 10-ago-2026 con los dos oraculos: 93 de 93 falsos verdes trazaban
# aqui. No es que el grafo perdiera la arista — es que la cadena de LLAMANTES se
# cortaba al llegar a un simbolo que alguien pasa como valor, y los tests del
# otro lado se perdian en silencio.


def _puerta(root):
    """llamantes ya enlazados, tal como los arma `impacted.analyze`."""
    from galaxybrain import symbols

    grafo = symbols.analyze(str(root))
    nodes = {n["qual"]: n for n in grafo["nodes"]}
    llamantes = impacted._llamantes(grafo["edges"])
    impacted._enlaza_pasados_como_valor(nodes, llamantes,
                                        grafo.get("nombrado_como_valor_en"))
    return nodes, llamantes


def test_quien_nombra_una_funcion_entra_como_llamante(tmp_path):
    """`p.set_defaults(func=cmd)`: la invocacion real es `args.func(...)`."""
    root = tmp_path / "p"
    (root / "app").mkdir(parents=True)
    (root / "app" / "__init__.py").write_text("", encoding="utf-8")
    (root / "app" / "cli.py").write_text(
        "def cmd_ver(args):\n"
        "    return 1\n"
        "\n"
        "\n"
        "def main():\n"
        "    tabla = {'ver': cmd_ver}\n"
        "    return tabla\n",
        encoding="utf-8")

    nodes, llamantes = _puerta(root)
    assert "app.cli.main" in llamantes.get("app.cli.cmd_ver", set())


def test_un_registro_a_nivel_de_modulo_enlaza_las_funciones_del_modulo(tmp_path):
    """`SONDAS = (_sonda,)` fuera de toda funcion: el cuerpo del modulo no es nodo.

    Enlazarlo no llevaria a ningun test —no tiene llamantes— asi que la cadena
    moriria igual que sin puerta. Era el resto exacto tras el primer arreglo.
    """
    root = tmp_path / "p"
    (root / "app").mkdir(parents=True)
    (root / "app" / "__init__.py").write_text("", encoding="utf-8")
    (root / "app" / "g.py").write_text(
        "def _sonda(x):\n"
        "    return x\n"
        "\n"
        "\n"
        "def self_test():\n"
        "    return [s(1) for _n, s in SONDAS]\n"
        "\n"
        "\n"
        "SONDAS = ((_sonda.__name__, _sonda),)\n",
        encoding="utf-8")

    nodes, llamantes = _puerta(root)
    assert "app.g.self_test" in llamantes.get("app.g._sonda", set())


def test_la_puerta_no_enlaza_funciones_de_otro_modulo(tmp_path):
    """Sobre-aproximar si; inventar que medio repo llama a esto, no."""
    root = tmp_path / "p"
    (root / "app").mkdir(parents=True)
    (root / "app" / "__init__.py").write_text("", encoding="utf-8")
    (root / "app" / "g.py").write_text(
        "def _sonda(x):\n"
        "    return x\n"
        "\n"
        "\n"
        "SONDAS = (_sonda,)\n",
        encoding="utf-8")
    (root / "app" / "otro.py").write_text(
        "def ajeno():\n"
        "    return 2\n",
        encoding="utf-8")

    nodes, llamantes = _puerta(root)
    assert "app.otro.ajeno" not in llamantes.get("app.g._sonda", set())


# --- opacidad INDIRECTA: quien llama a quien lanza -----------------------------
#
# El detector grepeaba el fichero de TEST y solo veia el caso directo.
# `tests/test_cobertura.py` no tiene ni una marca de subproceso y aun asi
# ejercitaba medio `capture` dentro de procesos hijos: llama a
# `bootstrap.coverage()`, y es esa funcion de src la que lanza. El fichero no
# salia opaco, la seleccion no lo elegia, y era un falso verde de verdad — el
# fallo que mata a esta familia. Salio al ensenar al oraculo a mirar dentro de
# los subprocesos (11-ago-2026): 0 falsos verdes pasaron a 60, todos por aqui.


def _proyecto_con_lanzador(tmp_path, arranque):
    """Un repo donde el test NO lanza nada: llama a una funcion de src que si."""
    root = tmp_path / "p"
    (root / "lib").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "lib" / "__init__.py").write_text("", encoding="utf-8")
    (root / "lib" / "arranca.py").write_text(
        "import subprocess\n"
        "import sys\n"
        "\n"
        "\n"
        "def lanza():\n"
        "    return subprocess.run(%s, capture_output=True)\n" % arranque,
        encoding="utf-8")
    (root / "tests" / "__init__.py").write_text("", encoding="utf-8")
    (root / "tests" / "test_indirecto.py").write_text(
        "from lib.arranca import lanza\n"
        "\n"
        "\n"
        "def test_indirecto():\n"
        "    assert lanza() is not None\n",
        encoding="utf-8")
    return root


def _opacos_de(root):
    from galaxybrain import symbols

    grafo = symbols.analyze(str(root))
    nodes = {n["qual"]: n for n in grafo["nodes"]}
    llamantes = impacted._llamantes(grafo["edges"])
    todos = impacted._todos_los_ficheros_de_test(nodes)
    return impacted.ficheros_opacos(str(root), nodes, llamantes, todos)


def test_un_test_que_llama_a_quien_lanza_NUESTRO_codigo_es_opaco(tmp_path):
    """El caso real: el hijo corre nuestro interprete y puede ejercitar
    cualquier cosa sin dejar arista."""
    root = _proyecto_con_lanzador(tmp_path, '[sys.executable, "-c", "pass"]')
    assert "tests/test_indirecto.py" in _opacos_de(root)


def test_lanzar_un_binario_AJENO_no_contagia_opacidad(tmp_path):
    """`graph._git` lanza git, `lenguajes._corre` lanza ast-grep: sus hijos no
    ejecutan una linea de este proyecto, asi que no pueden esconder nada.

    Sin este filtro la regla se contagiaba por medio repo —`_git` lo llama casi
    todo— y los opacos subian de 26 a 43 de 50 ficheros, hundiendo el ahorro del
    30% al 14% SIN comprar seguridad ninguna. Medido el 11-ago-2026.
    """
    root = _proyecto_con_lanzador(tmp_path, '["git", "status"]')
    assert "tests/test_indirecto.py" not in _opacos_de(root)


def test_el_import_interno_roto_devuelve_todo_con_su_motivo(repo):
    """El consumidor VIEJO, el caso sin red: nadie lo toca, asi que ningun diff
    lo trae y ningun "test tocado" lo rescata — y su referencia colgante no
    deja arista por la que subir. Sin esta puerta la seleccion salia estrecha
    y VERDE con un ImportError dentro (control 'firma' del banco de
    convergencia, 13-ago-2026). La promesa de la cabecera —"un simbolo que no
    resuelve devuelve TODO"— se cumple aqui o el falso verde es estructural.
    """
    (repo / "lib" / "carrito.py").write_text(
        "from lib.nucleo import suma\n\n\ndef total(xs):\n    return suma(xs[0], xs[1])\n",
        encoding="utf-8")
    (repo / "tests" / "test_carrito.py").write_text(
        "from lib.carrito import total\n\n\ndef test_total():\n    assert total([1, 2]) == 3\n",
        encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "carrito")
    # El renombre adapta a SU consumidor conocido (carrito); tests/test_suma.py,
    # el consumidor viejo, queda con la referencia colgante y sin viajar.
    _tocar(repo, "lib/nucleo.py", "def suma(", "def suma_total(")
    _tocar(repo, "lib/carrito.py", "import suma", "import suma_total")
    _tocar(repo, "lib/carrito.py", "suma(xs", "suma_total(xs")

    report = impacted.analyze(str(repo), worktree=True)
    assert report["todo"] is True
    assert "import interno roto" in report["motivo"]
    assert "test_suma" in report["motivo"], report["motivo"]
    assert any("test_suma.py" in f for f in report["tests"])
    # Y de frente: la seleccion corre y paga el rojo que antes no se veia.
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "--tb=no",
                        "-p", "no:cacheprovider", *report["tests"]],
                       cwd=str(repo), capture_output=True, text=True)
    assert r.returncode != 0, r.stdout
