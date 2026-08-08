"""La actividad de cada agente, DERIVADA del disco.

El invariante: nadie declara nada. Un agente es un worktree, su rastro es lo que
git ve, y si el agente muere a medias su rastro sigue siendo cierto. Lo que no se
puede derivar —qué cree el agente que está haciendo— no se inventa.
"""

import subprocess

import pytest

from galaxybrain import actividad, symbols


def _git(root, *args):
    subprocess.run(["git"] + list(args), cwd=str(root), check=True,
                   capture_output=True, text=True)


@pytest.fixture
def proyecto(tmp_path):
    """Un repo con dos módulos donde uno llama al otro."""
    root = tmp_path / "proyecto"
    (root / "lib").mkdir(parents=True)
    (root / "lib" / "__init__.py").write_text("", encoding="utf-8")
    (root / "lib" / "nucleo.py").write_text(
        "def suma(a, b):\n"
        "    return a + b\n",
        encoding="utf-8")
    (root / "lib" / "encima.py").write_text(
        "from lib.nucleo import suma\n"
        "\n"
        "\n"
        "def doble(x):\n"
        "    return suma(x, x)\n",
        encoding="utf-8")
    (root / "lib" / "aparte.py").write_text(
        "def nada():\n"
        "    return 0\n",
        encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t.t")
    _git(root, "config", "user.name", "t")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "base")
    return root


def _rama(repo, nombre):
    ruta = repo.parent / nombre
    _git(repo, "worktree", "add", "-q", "--detach", str(ruta), "HEAD")
    return ruta


# --- vecinos: con quién habla lo tocado ------------------------------------

INFORME = {
    "nodes": [
        {"qual": "a", "kind": "module", "module": "a"},
        {"qual": "a.f", "kind": "function", "module": "a"},
        {"qual": "b", "kind": "module", "module": "b"},
        {"qual": "b.g", "kind": "function", "module": "b"},
        {"qual": "c", "kind": "module", "module": "c"},
        {"qual": "c.h", "kind": "function", "module": "c"},
    ],
    "edges": [
        ["a", "a.f", "DEFINES"],
        ["b", "b.g", "DEFINES"],
        ["a.f", "b.g", "CALLS"],
        ["c.h", "a.f", "CALLS"],
    ],
}


def test_los_vecinos_son_los_modulos_con_los_que_habla():
    vecinos = actividad._vecinos(INFORME, ["a"])
    assert vecinos == ["b", "c"]      # a llama a b, y c llama a a


def test_la_estructura_no_cuenta_como_comunicacion():
    """DEFINES es contención, no una llamada: un módulo no 'habla' con su función."""
    solo_estructura = {"nodes": INFORME["nodes"],
                       "edges": [["a", "a.f", "DEFINES"]]}
    assert actividad._vecinos(solo_estructura, ["a"]) == []


def test_lo_ya_tocado_no_sale_como_vecino():
    assert actividad._vecinos(INFORME, ["a", "b"]) == ["c"]


def test_una_llamada_dentro_del_mismo_modulo_no_es_comunicacion():
    dentro = {
        "nodes": [{"qual": "a", "module": "a"}, {"qual": "a.f", "module": "a"},
                  {"qual": "a.g", "module": "a"}],
        "edges": [["a.f", "a.g", "CALLS"]],
    }
    assert actividad._vecinos(dentro, ["a"]) == []


# --- la foto completa -------------------------------------------------------

def test_sin_repo_git_calla(tmp_path):
    suelto = tmp_path / "suelto"
    suelto.mkdir()
    foto = actividad.instantanea(str(suelto), {"nodes": [], "edges": []})
    assert foto["agentes"] == []
    assert "git" in foto["motivo"]


def test_un_arbol_limpio_no_tiene_agentes(proyecto):
    informe = symbols.analyze(str(proyecto))
    foto = actividad.instantanea(str(proyecto), informe)
    assert foto["agentes"] == []


def test_una_rama_con_cambios_aparece_con_lo_que_toca(proyecto):
    informe = symbols.analyze(str(proyecto))
    rama = _rama(proyecto, "rama_a")
    (rama / "lib" / "nucleo.py").write_text(
        "def suma(a, b):\n    return a + b + 0\n", encoding="utf-8")

    foto = actividad.instantanea(str(proyecto), informe)
    nombres = [a["nombre"] for a in foto["agentes"]]
    assert nombres == ["rama_a"]
    agente = foto["agentes"][0]
    assert "lib.nucleo" in agente["nodos"]
    assert agente["misma_base"] is True
    assert agente["hace_seg"] is not None
    # nucleo es llamado por encima: es con quien se comunica.
    assert "lib.encima" in agente["vecinos"]
    assert "lib.aparte" not in agente["vecinos"]


def test_dos_ramas_en_el_mismo_modulo_son_un_cruce(proyecto):
    informe = symbols.analyze(str(proyecto))
    a = _rama(proyecto, "rama_a")
    b = _rama(proyecto, "rama_b")
    (a / "lib" / "nucleo.py").write_text(
        "def suma(a, b):\n    return a + b + 1\n", encoding="utf-8")
    (b / "lib" / "nucleo.py").write_text(
        "def suma(a, b):\n    return a + b + 2\n", encoding="utf-8")

    foto = actividad.instantanea(str(proyecto), informe)
    assert len(foto["agentes"]) == 2
    assert "lib.nucleo" in foto["cruces"]
    assert sorted(foto["por_nodo"]["lib.nucleo"]["agentes"]) == ["rama_a", "rama_b"]


def test_ramas_en_modulos_distintos_no_cruzan(proyecto):
    informe = symbols.analyze(str(proyecto))
    a = _rama(proyecto, "rama_a")
    b = _rama(proyecto, "rama_b")
    (a / "lib" / "nucleo.py").write_text(
        "def suma(a, b):\n    return a + b + 1\n", encoding="utf-8")
    (b / "lib" / "aparte.py").write_text(
        "def nada():\n    return 7\n", encoding="utf-8")

    foto = actividad.instantanea(str(proyecto), informe)
    assert foto["cruces"] == []


def test_una_rama_en_otra_base_se_marca(proyecto):
    (proyecto / "lib" / "nuevo.py").write_text("def q():\n    return 1\n", encoding="utf-8")
    _git(proyecto, "add", "-A")
    _git(proyecto, "commit", "-qm", "segundo")
    informe = symbols.analyze(str(proyecto))

    vieja = proyecto.parent / "rama_vieja"
    _git(proyecto, "worktree", "add", "-q", "--detach", str(vieja), "HEAD~1")
    (vieja / "lib" / "nucleo.py").write_text(
        "def suma(a, b):\n    return a + b + 3\n", encoding="utf-8")

    foto = actividad.instantanea(str(proyecto), informe)
    agente = [a for a in foto["agentes"] if a["nombre"] == "rama_vieja"][0]
    assert agente["misma_base"] is False


def test_un_agente_que_solo_crea_modulos_nuevos_sigue_visible(proyecto):
    """Esconderlo sería esconder justo al que más está construyendo.

    Un módulo recién creado no está en el mapa canónico, así que no casa con
    ningún nodo. El agente aparece igual, y se dice cuántos ficheros suyos aún
    no tienen sitio en el mapa.
    """
    informe = symbols.analyze(str(proyecto))
    rama = _rama(proyecto, "rama_a")
    (rama / "lib" / "recien.py").write_text("def r():\n    return 1\n", encoding="utf-8")

    foto = actividad.instantanea(str(proyecto), informe)
    assert [a["nombre"] for a in foto["agentes"]] == ["rama_a"]
    agente = foto["agentes"][0]
    assert agente["nodos"] == []            # nada que casar en el mapa de ahora
    assert agente["fuera_del_mapa"] == 1    # pero el hecho no se pierde
    assert agente["ficheros"] == 1

# --- cambios: que escribio, exactamente -------------------------------------

def test_la_actividad_baja_al_simbolo_y_no_enciende_el_fichero_entero(proyecto):
    """Reportado mirando el mapa (9-ago): «veo los modulos encenderse pero no
    class/function/method». La capa razonaba en FICHEROS y paraba en el modulo.

    Aqui se edita UNA de las dos funciones de un fichero y se comprueba que solo
    esa se enciende: encender las dos seria el falso positivo que hace que mirar
    el mapa deje de decir nada."""
    # un modulo con DOS funciones en la baseline: sin eso no se puede distinguir
    # "toco el fichero" de "toco esta funcion"
    (proyecto / "lib" / "par.py").write_text(
        "def uno(x):\n    return x + 1\n\n\ndef dos(x):\n    return x + 2\n",
        encoding="utf-8")
    _git(proyecto, "add", "-A")
    _git(proyecto, "commit", "-qm", "dos funciones")

    rama = _rama(proyecto, "agente")
    ruta = rama / "lib" / "par.py"
    ruta.write_text(ruta.read_text(encoding="utf-8").replace(
        "    return x + 2", "    return x + 2 + 0"), encoding="utf-8")

    informe = symbols.analyze(str(proyecto))
    foto = actividad.instantanea(str(proyecto), informe)
    agente = next(a for a in foto["agentes"] if a["nombre"] == "agente")

    assert agente["simbolos"] == ["lib.par.dos"], agente["simbolos"]
    assert "lib.par" in agente["nodos"], "el modulo sigue estando debajo"


def test_el_simbolo_tocado_entra_en_el_indice_por_nodo(proyecto):
    """Sin esto el mapa no puede encenderlo: `por_nodo` es lo que consume."""
    rama = _rama(proyecto, "agente")
    ruta = rama / "lib" / "nucleo.py"
    ruta.write_text(ruta.read_text(encoding="utf-8").replace(
        "    return a + b", "    return a + b + 0"), encoding="utf-8")

    foto = actividad.instantanea(str(proyecto), symbols.analyze(str(proyecto)))

    assert "lib.nucleo.suma" in foto["por_nodo"]
    assert foto["por_nodo"]["lib.nucleo.suma"]["agentes"] == ["agente"]


def test_los_cambios_dicen_la_firma_exacta(proyecto):
    """'Ver exactamente que escriben': la firma del worktree contra el mapa
    canonico — el mismo hecho estrecho que el bucle deriva para enrutar."""
    informe = symbols.analyze(str(proyecto))
    rama = _rama(proyecto, "rama_a")
    (rama / "lib" / "nucleo.py").write_text(
        "def suma(a, b, extra):\n    return a + b + extra\n"
        "\n\ndef resta(a, b):\n    return a - b\n",
        encoding="utf-8")

    foto = actividad.instantanea(str(proyecto), informe)
    cambios = foto["agentes"][0]["cambios"]
    assert "lib.nucleo.suma: (a, b) -> (a, b, extra)" in cambios
    assert "lib.nucleo.resta: (no existia) -> (a, b)" in cambios


def test_borrar_un_simbolo_sale_como_borrado(proyecto):
    informe = symbols.analyze(str(proyecto))
    rama = _rama(proyecto, "rama_a")
    (rama / "lib" / "nucleo.py").write_text("X = 1\n", encoding="utf-8")

    foto = actividad.instantanea(str(proyecto), informe)
    assert "lib.nucleo.suma: (a, b) -> (borrado)" in foto["agentes"][0]["cambios"]


def test_el_fichero_a_medio_escribir_se_dice_ilegible(proyecto):
    """La sintaxis rota de un agente escribiendo es un hecho, no un error: se
    dice con su linea, y desaparece solo cuando el fichero vuelve a parsear."""
    informe = symbols.analyze(str(proyecto))
    rama = _rama(proyecto, "rama_a")
    (rama / "lib" / "nucleo.py").write_text("def suma(a, b:\n", encoding="utf-8")

    foto = actividad.instantanea(str(proyecto), informe)
    (cambio,) = foto["agentes"][0]["cambios"]
    assert "ilegible" in cambio and "lib.nucleo" in cambio


def test_tocar_solo_el_cuerpo_no_inventa_hechos_de_firma(proyecto):
    informe = symbols.analyze(str(proyecto))
    rama = _rama(proyecto, "rama_a")
    (rama / "lib" / "nucleo.py").write_text(
        "def suma(a, b):\n    return b + a\n", encoding="utf-8")

    foto = actividad.instantanea(str(proyecto), informe)
    assert foto["agentes"][0]["cambios"] == []


# --- la consola del agente: su stdout, leido del disco -----------------------

def test_la_consola_del_agente_se_lee_del_log_del_orquestador(proyecto):
    """Convencion <worktree>.consola.log: el stdout del agente teeado por quien
    lo lanza (el bucle lo hace). Derivada del disco — si nadie la escribe, no
    hay terminal y NO se inventa narrativa."""
    informe = symbols.analyze(str(proyecto))
    rama = _rama(proyecto, "rama_a")
    (rama / "lib" / "nucleo.py").write_text(
        "def suma(a, b):\n    return b + a\n", encoding="utf-8")
    (rama.parent / "rama_a.consola.log").write_text(
        "[02:13:05] > Edit lib/nucleo.py\n[02:13:08] corriendo pytest\n",
        encoding="utf-8")

    foto = actividad.instantanea(str(proyecto), informe)
    assert foto["agentes"][0]["consola"] == [
        "[02:13:05] > Edit lib/nucleo.py", "[02:13:08] corriendo pytest"]


def test_sin_log_no_se_inventa_consola(proyecto):
    informe = symbols.analyze(str(proyecto))
    rama = _rama(proyecto, "rama_a")
    (rama / "lib" / "nucleo.py").write_text(
        "def suma(a, b):\n    return b + a\n", encoding="utf-8")
    foto = actividad.instantanea(str(proyecto), informe)
    assert foto["agentes"][0]["consola"] == []


def test_un_agente_con_consola_pero_arbol_limpio_aparece(proyecto):
    """Recien lanzado: aun no toco codigo, pero su consola ya habla — esta
    operando y esconderlo seria mentir por omision."""
    informe = symbols.analyze(str(proyecto))
    _rama(proyecto, "rama_a")
    (proyecto.parent / "rama_a.consola.log").write_text(
        "[02:13:01] $ agente A\n", encoding="utf-8")

    foto = actividad.instantanea(str(proyecto), informe)
    assert [a["nombre"] for a in foto["agentes"]] == ["rama_a"]
    assert foto["agentes"][0]["nodos"] == []
    assert foto["agentes"][0]["hace_seg"] is not None
