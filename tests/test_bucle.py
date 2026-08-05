"""El bucle: la parte determinista, testeada sin gastar un token.

El ejecutor LLM (`claude -p`) queda fuera a proposito: es un adaptador
reemplazable y su prueba es la tirada en vivo. Lo que se fija aqui es la
maquinaria que hace de arista: derivar hechos del diff real, componer el
despacho con la señal, y leer el veredicto distinguiendo coordinada de
rescatada — la desambiguacion que motivo el bucle.
"""

import importlib.util
import os
import subprocess

import pytest

_RUTA = os.path.join(os.path.dirname(__file__), "..", "bucle", "bucle.py")
_spec = importlib.util.spec_from_file_location("bucle", _RUTA)
bucle = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bucle)


# --- interpretar: coordinada vs rescatada ------------------------------------

def test_rama_roja_con_senal_recibida_es_coordinada():
    lectura = bucle.interpretar(["bucle-B"], True, {"B": ["calcula: (a,b) -> (a,b,base)"]})
    assert lectura == {"bucle-B": "coordinada"}


def test_rama_roja_sin_senal_es_rescate_y_se_dice():
    lectura = bucle.interpretar(["bucle-B"], True, {})
    assert "RESCATADA" in lectura["bucle-B"]


def test_con_union_roja_no_hay_nada_que_interpretar():
    assert bucle.interpretar(["bucle-B"], False, {"B": ["algo"]}) == {}


# --- componer_prompt: la señal viaja en el despacho ---------------------------

def test_el_despacho_lleva_la_senal_cuando_la_hay():
    tarea = {"id": "B", "prompt": "haz tests"}
    con = bucle.componer_prompt(tarea, ["calcula: (a, b) -> (a, b, base)"])
    assert "SEÑAL DEL ENRUTADOR" in con
    assert "calcula: (a, b) -> (a, b, base)" in con
    sin = bucle.componer_prompt(tarea, [])
    assert "SEÑAL" not in sin


def test_el_reintento_viaja_como_hecho_extra():
    tarea = {"id": "B", "prompt": "haz tests"}
    texto = bucle.componer_prompt(tarea, ["h1"], extra="REINTENTO: la union fallo")
    assert texto.index("REINTENTO") > texto.index("haz tests")


# --- derivar_hechos: del diff real, no de lo declarado ------------------------

def _git(cwd, *args):
    subprocess.run(["git"] + list(args), cwd=str(cwd), check=True,
                   capture_output=True, text=True)


@pytest.fixture
def worktree_real(tmp_path):
    """Un worktree DE ESTE repo, con el banco dentro, para derivar de verdad."""
    ruta = tmp_path / "wt-bucle-test"
    _git(bucle.RAIZ, "worktree", "add", "--detach", str(ruta), "main")
    yield ruta
    subprocess.run(["git", "worktree", "remove", "--force", str(ruta)],
                   cwd=bucle.RAIZ, capture_output=True)
    subprocess.run(["git", "worktree", "prune"], cwd=bucle.RAIZ, capture_output=True)


def test_deriva_el_cambio_de_firma_del_arbol_no_del_relato(worktree_real):
    """La base son las firmas del worktree ANTES de tocarlo — nunca el arbol del
    orquestador, que puede llevar codigo sin commitear y contaminar los hechos
    (paso: la primera version comparaba contra RAIZ y atribuia al agente los
    ficheros sin commitear del propio bucle)."""
    firmas_base = bucle.firmas_de(str(worktree_real))
    nucleo = worktree_real / "experimento" / "nucleo.py"
    texto = nucleo.read_text(encoding="utf-8")
    nucleo.write_text(texto.replace("def calcula(a, b):", "def calcula(a, b, extra):"),
                      encoding="utf-8")

    hechos = bucle.derivar_hechos(str(worktree_real), firmas_base)
    assert any("experimento.nucleo.calcula" in h and "(a, b)" in h and "(a, b, extra)" in h
               for h in hechos)


def test_sin_cambios_no_se_inventan_hechos(worktree_real):
    firmas_base = bucle.firmas_de(str(worktree_real))
    assert bucle.derivar_hechos(str(worktree_real), firmas_base) == []


def test_hechos_entre_es_puro_y_dice_altas_bajas_y_cambios():
    antes = {"m.f": "(a)", "m.g": "(x)"}
    despues = {"m.f": "(a, b)", "m.h": "(z)"}
    hechos = bucle.hechos_entre(antes, despues)
    assert "m.f: (a) -> (a, b)" in hechos
    assert "m.g: (x) -> (borrada)" in hechos
    assert "m.h: (no existia) -> (z)" in hechos
