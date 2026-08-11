"""`gb tests --run --isolated`: el verde vale sobre el diff, no sobre tu copia.

El invariante de este fichero es uno solo y es el que motivó el comando: **lo que
no viaja en el diff, no viaja**. Un cambio que pasa en la copia de trabajo porque
se apoya en un fichero que nadie añadió tiene que salir ROJO aquí, y decir por qué.

El caso que lo motivó está medido: tres agentes en paralelo el 5-ago-2026, uno
reportó «449 passed» de buena fe y su diff solo, sobre base limpia, no compilaba.
"""

import subprocess

import pytest

from galaxybrain import aislado


def _git(root, *args):
    subprocess.run(["git"] + list(args), cwd=str(root), check=True,
                   capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path):
    """Un repo real con un módulo y un test que lo ejercita, ambos commiteados."""
    root = tmp_path / "proyecto"
    (root / "lib").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "lib" / "__init__.py").write_text("", encoding="utf-8")
    (root / "lib" / "nucleo.py").write_text(
        "def suma(a, b):\n"
        "    return a + b\n",
        encoding="utf-8")
    (root / "tests" / "test_suma.py").write_text(
        "from lib.nucleo import suma\n"
        "\n"
        "\n"
        "def test_suma_va():\n"
        "    assert suma(1, 2) == 3\n",
        encoding="utf-8")
    # Trackeado desde el principio: asi una rama que lo toca produce un cambio que
    # SI viaja, que es lo que hace falta para el escenario del rescate.
    (root / "tests" / "conftest.py").write_text("", encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t.t")
    _git(root, "config", "user.name", "t")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "base")
    return root


def test_sin_repo_git_no_monta_y_dice_por_que(tmp_path):
    suelto = tmp_path / "suelto"
    suelto.mkdir()
    informe = aislado.verifica(str(suelto), ["tests/test_x.py"])
    assert informe["monto"] is False
    assert "git" in informe["motivo"]
    assert informe["exit_code"] is None
    # No haber podido comprobar nada nunca es un pase.
    assert informe["veredicto"] != 0


def test_arbol_sin_cambios_corre_verde(repo):
    informe = aislado.verifica(str(repo), ["tests/test_suma.py"])
    assert informe["monto"] is True
    assert informe["exit_code"] == 0
    assert informe["veredicto"] == 0
    assert informe["corridos"] == ["tests/test_suma.py"]
    assert informe["ausentes"] == []


def test_un_cambio_trackeado_si_viaja(repo):
    # Se rompe el modulo YA trackeado: el diff lo lleva, luego en limpio falla.
    (repo / "lib" / "nucleo.py").write_text(
        "def suma(a, b):\n"
        "    return a - b\n",
        encoding="utf-8")
    informe = aislado.verifica(str(repo), ["tests/test_suma.py"])
    assert informe["monto"] is True
    assert informe["veredicto"] != 0


def test_verde_en_sucio_pero_rojo_en_limpio(repo):
    """El caso medido: el verde se apoyaba en algo que no estaba en el diff."""
    # Un modulo nuevo que NADIE ha añadido a git.
    (repo / "lib" / "extra.py").write_text(
        "def doble(x):\n"
        "    return x * 2\n",
        encoding="utf-8")
    # Y el test (trackeado, luego SI viaja) pasa a depender de el.
    (repo / "tests" / "test_suma.py").write_text(
        "from lib.nucleo import suma\n"
        "from lib.extra import doble\n"
        "\n"
        "\n"
        "def test_suma_va():\n"
        "    assert doble(suma(1, 2)) == 6\n",
        encoding="utf-8")

    # En la copia de trabajo pasa: extra.py esta ahi.
    sucio = subprocess.run(["python", "-m", "pytest", "tests/test_suma.py", "-q"],
                           cwd=str(repo), capture_output=True, text=True)
    assert sucio.returncode == 0, sucio.stdout

    # En limpio no, porque extra.py no viaja.
    informe = aislado.verifica(str(repo), ["tests/test_suma.py"])
    assert informe["monto"] is True
    assert informe["exit_code"] != 0
    assert "lib/extra.py" in informe["sin_trackear"]


def test_un_test_sin_trackear_no_cuela_como_verde(repo):
    """Si el fichero de test no viaja, no hay nada que correr — y eso no es un pase."""
    (repo / "tests" / "test_nuevo.py").write_text(
        "def test_lo_que_sea():\n"
        "    assert True\n",
        encoding="utf-8")
    informe = aislado.verifica(str(repo), ["tests/test_nuevo.py"])
    assert informe["monto"] is True
    assert informe["ausentes"] == ["tests/test_nuevo.py"]
    assert informe["corridos"] == []
    assert informe["exit_code"] is None      # pytest no llego a correr
    assert informe["veredicto"] != 0         # y aun asi no es verde


def test_verificacion_incompleta_no_es_verde(repo):
    """El bug que cazo el primer uso real: pytest dice 0 y la cobertura esta coja.

    Un fichero de test viaja y pasa; otro no viaja. Correr solo el primero deja el
    cambio a medio verificar, y reportar 0 ahi es exactamente el falso verde que
    este modo existe para matar.
    """
    (repo / "tests" / "test_nuevo.py").write_text(
        "def test_lo_que_sea():\n"
        "    assert True\n",
        encoding="utf-8")
    informe = aislado.verifica(
        str(repo), ["tests/test_suma.py", "tests/test_nuevo.py"])
    assert informe["corridos"] == ["tests/test_suma.py"]
    assert informe["ausentes"] == ["tests/test_nuevo.py"]
    assert informe["exit_code"] == 0         # lo que corrio, paso
    assert informe["veredicto"] != 0         # pero la verificacion no esta completa


def test_staged_mira_el_indice_y_no_el_disco(repo):
    (repo / "lib" / "nucleo.py").write_text(
        "def suma(a, b):\n"
        "    return a - b\n",
        encoding="utf-8")
    # Sin añadir al indice: con --staged el diff esta vacio, luego en limpio pasa.
    informe = aislado.verifica(str(repo), ["tests/test_suma.py"], staged=True)
    assert informe["veredicto"] == 0
    # Una vez en el indice, el mismo cambio si viaja.
    _git(repo, "add", "lib/nucleo.py")
    informe = aislado.verifica(str(repo), ["tests/test_suma.py"], staged=True)
    assert informe["veredicto"] != 0


def test_no_deja_worktrees_colgando(repo):
    antes = subprocess.run(["git", "worktree", "list"], cwd=str(repo),
                           capture_output=True, text=True).stdout
    aislado.verifica(str(repo), ["tests/test_suma.py"])
    despues = subprocess.run(["git", "worktree", "list"], cwd=str(repo),
                             capture_output=True, text=True).stdout
    assert antes.strip() == despues.strip()
    assert len(despues.strip().splitlines()) == 1


def test_no_toca_la_copia_de_trabajo(repo):
    original = (repo / "lib" / "nucleo.py").read_text(encoding="utf-8")
    (repo / "lib" / "nucleo.py").write_text(
        "def suma(a, b):\n"
        "    return a - b\n",
        encoding="utf-8")
    sucio = (repo / "lib" / "nucleo.py").read_text(encoding="utf-8")
    aislado.verifica(str(repo), ["tests/test_suma.py"])
    # El arbol del usuario queda exactamente como estaba: el modo aislado mide,
    # no corrige.
    assert (repo / "lib" / "nucleo.py").read_text(encoding="utf-8") == sucio
    assert sucio != original


def test_la_traza_cuenta_lo_que_pasa(repo):
    lineas = []
    aislado.verifica(str(repo), ["tests/test_suma.py"], traza=lineas.append)
    assert any("arbol limpio" in l for l in lineas)
    assert any("pytest" in l for l in lineas)


# --- converge: N ramas en paralelo -----------------------------------------

def _rama(repo, nombre):
    """Un worktree hermano, como el que abre un agente para trabajar."""
    ruta = repo.parent / nombre
    _git(repo, "worktree", "add", "-q", "--detach", str(ruta), "HEAD")
    return ruta


def test_sin_ramas_con_cambios_no_hay_nada_que_verificar(repo):
    informe = aislado.converge(str(repo))
    assert informe["veredicto"] == 0
    assert "ningun worktree" in informe["motivo"]


def test_dos_ramas_sanas_salen_verdes(repo):
    a = _rama(repo, "rama_a")
    b = _rama(repo, "rama_b")
    (a / "lib" / "nucleo.py").write_text(
        "def suma(a, b):\n"
        "    return a + b\n"
        "\n"
        "\n"
        "def triple(x):\n"
        "    return x * 3\n",
        encoding="utf-8")
    (b / "tests" / "test_suma.py").write_text(
        "from lib.nucleo import suma\n"
        "\n"
        "\n"
        "def test_suma_va():\n"
        "    assert suma(2, 2) == 4\n",
        encoding="utf-8")
    informe = aislado.converge(str(repo))
    assert informe["monto"] is True
    assert {r["nombre"] for r in informe["ramas"]} == {"rama_a", "rama_b"}
    assert informe["veredicto"] == 0
    assert informe["rescatados"] == []


def test_caza_el_rescate_accidental(repo):
    """El fallo medido el 5-ago-2026, reproducido.

    Una rama se apoya en un arreglo que hizo OTRA rama en un fichero compartido.
    La union pasa; ella sola, no. Mirando solo el merge se da por buena.
    """
    a = _rama(repo, "rama_a")
    b = _rama(repo, "rama_b")
    # A necesita una fixture que su rama NO trae.
    (a / "tests" / "test_suma.py").write_text(
        "from lib.nucleo import suma\n"
        "\n"
        "\n"
        "def test_suma_va(ayuda):\n"
        "    assert ayuda(suma(1, 2)) == 6\n",
        encoding="utf-8")
    # B, sin saber nada de A, añade justo esa fixture al conftest compartido.
    (b / "tests" / "conftest.py").write_text(
        "import pytest\n"
        "\n"
        "\n"
        "@pytest.fixture\n"
        "def ayuda():\n"
        "    return lambda x: x * 2\n",
        encoding="utf-8")

    informe = aislado.converge(str(repo))
    ramas = {r["nombre"]: r for r in informe["ramas"]}
    assert ramas["rama_a"]["veredicto"] != 0      # sola no se sostiene
    assert ramas["rama_b"]["veredicto"] == 0
    assert informe["union"]["veredicto"] == 0     # juntas pasan
    assert informe["rescatados"] == ["rama_a"]    # y eso es lo que hay que decir
    # El veredicto global no puede ser verde con una rama que no se sostiene.
    assert informe["veredicto"] != 0


def test_una_sola_rama_nunca_es_un_rescate(repo):
    """Con una rama no hay quien rescate a nadie — aunque salga roja."""
    a = _rama(repo, "rama_a")
    (a / "tests" / "test_nuevo.py").write_text(          # no viaja: sin trackear
        "def test_x():\n    assert True\n", encoding="utf-8")
    (a / "lib" / "nucleo.py").write_text(
        "def suma(a, b):\n    return a + b\n\n\ndef n():\n    return 1\n", encoding="utf-8")
    informe = aislado.converge(str(repo))
    assert len(informe["ramas"]) == 1
    assert informe["rescatados"] == []


def test_la_union_hereda_lo_que_no_viaja(repo):
    """Si un test no viaja a la rama, tampoco viaja a la union: no puede ser verde."""
    a = _rama(repo, "rama_a")
    b = _rama(repo, "rama_b")
    (a / "tests" / "test_nuevo.py").write_text(          # sin trackear
        "def test_x():\n    assert True\n", encoding="utf-8")
    (a / "lib" / "nucleo.py").write_text(
        "def suma(a, b):\n    return a + b\n\n\ndef n():\n    return 1\n", encoding="utf-8")
    (b / "tests" / "conftest.py").write_text("# tocado\n", encoding="utf-8")

    informe = aislado.converge(str(repo))
    assert informe["union"]["veredicto"] != 0
    assert "no viajan" in informe["union"]["motivo"]
    assert informe["rescatados"] == []
    assert informe["veredicto"] != 0


def test_bases_distintas_no_inventan_una_union(repo):
    (repo / "lib" / "otro.py").write_text("def x():\n    return 1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "segundo")

    vieja = repo.parent / "rama_vieja"
    _git(repo, "worktree", "add", "-q", "--detach", str(vieja), "HEAD~1")
    nueva = _rama(repo, "rama_nueva")
    (vieja / "lib" / "nucleo.py").write_text(
        "def suma(a, b):\n    return a + b\n\n\ndef z():\n    return 0\n", encoding="utf-8")
    (nueva / "lib" / "nucleo.py").write_text(
        "def suma(a, b):\n    return a + b\n\n\ndef w():\n    return 1\n", encoding="utf-8")

    informe = aislado.converge(str(repo))
    assert informe["union"] is None
    assert "bases distintas" in informe["motivo"]
    assert len(informe["ramas"]) == 2      # cada una sí se verificó por separado


def test_converge_no_deja_worktrees_colgando(repo):
    a = _rama(repo, "rama_a")
    (a / "lib" / "nucleo.py").write_text(
        "def suma(a, b):\n    return a + b\n\n\ndef n():\n    return 1\n", encoding="utf-8")
    antes = subprocess.run(["git", "worktree", "list"], cwd=str(repo),
                           capture_output=True, text=True).stdout
    aislado.converge(str(repo))
    despues = subprocess.run(["git", "worktree", "list"], cwd=str(repo),
                             capture_output=True, text=True).stdout
    assert antes.strip() == despues.strip()


def test_el_entorno_de_un_hook_de_git_no_contamina(repo, monkeypatch, tmp_path):
    """El fallo del 5-ago-2026, fijado: dentro de un hook, git inyecta
    GIT_INDEX_FILE/GIT_DIR, y un git heredandolas opera sobre el repo del hook —
    los fixtures de esta suite acabaron staged en el indice de galaxy-brain.
    El aislado trabaja con el entorno limpio: el repo objetivo lo dice cwd.
    """
    ajeno = tmp_path / "otro-repo"
    ajeno.mkdir()
    _git(ajeno, "init", "-q")
    # El entorno de un hook corriendo en el repo AJENO.
    monkeypatch.setenv("GIT_DIR", str(ajeno / ".git"))
    monkeypatch.setenv("GIT_INDEX_FILE", str(ajeno / ".git" / "index"))

    informe = aislado.verifica(str(repo), ["tests/test_suma.py"])
    assert informe["monto"] is True
    assert informe["veredicto"] == 0
    # Y el repo ajeno sigue sin enterarse de nada.
    ajeno_status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=str(ajeno),
        capture_output=True, text=True,
        env={k: v for k, v in __import__("os").environ.items() if not k.startswith("GIT_")},
    ).stdout
    assert ajeno_status.strip() == ""


# --- la union: lo que un agente CREA tambien tiene que viajar -----------------


def _rama(repo, nombre):
    ruta = repo.parent / nombre
    _git(repo, "worktree", "add", "-q", "--detach", str(ruta), "HEAD")
    return ruta


def test_lo_que_una_rama_CREA_viaja_a_la_union(repo):
    """Cada rama VERDE sola y la union ROJA: el conflicto semantico.

    El sector lo nombra como la clase mas dificil y sin dueno (ago-2026): «el CI
    en verde te dice que los tests que ya tenias siguen pasando; no te dice que
    tres cambios son correctos JUNTOS». Aqui A cambia las unidades y adapta a su
    consumidor; B anade un consumidor NUEVO escrito contra las unidades viejas.
    Los diffs tocan ficheros distintos, asi que el merge sale limpio y git no ve
    nada — el choque es de SIGNIFICADO.

    Y el fallo que esto fija: los ficheros nuevos no van en `git diff HEAD`, asi
    que la union se montaba SIN el trabajo de B y daba VERDE. Un falso verde en
    la capa que existe para cazarlos. El dato ya estaba (`sin_trackear` por
    rama); lo que faltaba era usarlo.
    """
    a = _rama(repo, "rama_a")
    (a / "lib" / "nucleo.py").write_text(
        "def suma(a, b):\n    return (a + b) * 100\n", encoding="utf-8")
    (a / "tests" / "test_suma.py").write_text(
        "from lib.nucleo import suma\n\n\ndef test_suma_va():\n"
        "    assert suma(1, 2) == 300\n", encoding="utf-8")

    b = _rama(repo, "rama_b")
    (b / "lib" / "encima.py").write_text(
        "from lib.nucleo import suma\n\n\ndef doble(x):\n"
        "    return suma(x, x)\n", encoding="utf-8")
    (b / "tests" / "test_encima.py").write_text(
        "from lib.encima import doble\n\n\ndef test_doble():\n"
        "    assert doble(2) == 4\n", encoding="utf-8")

    informe = aislado.converge(str(repo))
    ramas = {r["nombre"]: r["veredicto"] for r in informe["ramas"]}
    assert ramas == {"rama_a": 0, "rama_b": 0}, informe["ramas"]
    assert informe["union"]["veredicto"] != 0, informe["union"]


def test_dos_ramas_que_crean_el_mismo_fichero_distinto_es_colision(repo):
    """Que gane la ultima en copiarse seria inventar un arbol que nadie escribio."""
    a = _rama(repo, "rama_a")
    (a / "lib" / "nuevo.py").write_text("VALOR = 1\n", encoding="utf-8")
    b = _rama(repo, "rama_b")
    (b / "lib" / "nuevo.py").write_text("VALOR = 2\n", encoding="utf-8")

    informe = aislado.converge(str(repo))
    assert informe["union"]["conflictos"], informe["union"]
    assert "nuevo.py" in informe["union"]["motivo"]


def test_el_mismo_fichero_IDENTICO_en_dos_ramas_no_es_colision(repo):
    """Sin nada que decidir no hay conflicto: gritar aqui seria un falso positivo."""
    for nombre in ("rama_a", "rama_b"):
        rama = _rama(repo, nombre)
        (rama / "lib" / "igual.py").write_text("VALOR = 1\n", encoding="utf-8")

    informe = aislado.converge(str(repo))
    assert informe["union"]["conflictos"] == [], informe["union"]
