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


def test_el_extracto_del_fallo_trae_el_error_no_la_lista_de_ficheros():
    """La primera tirada en vivo reintentro a ciegas: la cola cruda del output
    entregaba la lista de ficheros de pytest en vez del TypeError."""
    texto = (
        "$ -m pytest tests/test_a.py tests/test_b.py tests/test_c.py\n"
        "E       TypeError: calcula() missing 1 required positional argument: 'base'\n"
        "FAILED tests/test_experimento_uso.py::test_directa - TypeError\n"
        "======================= 2 failed, 255 passed ========================\n"
        "  ROJA   union\n")
    extracto = bucle.extracto_fallo(texto)
    assert "TypeError" in extracto
    assert "FAILED" in extracto
    assert "$ -m pytest" not in extracto


def test_sin_lineas_de_error_cae_a_la_cola_y_no_a_vacio():
    assert bucle.extracto_fallo("nada de interes aqui") != ""


# --- adopcion (v1): el bucle rechaza el trabajo que ignoro la señal -----------

HECHO_VIVO = "experimento.nucleo.calcula: (a, b) -> (a, b, base)"


def test_firma_admite_cuenta_los_argumentos():
    assert not bucle.firma_admite("(a, b, base)", 2, [])
    assert bucle.firma_admite("(a, b, base)", 3, [])
    assert bucle.firma_admite("(a, b, base=10)", 2, [])
    assert bucle.firma_admite("(a, b, base)", 2, ["base"])
    assert not bucle.firma_admite("(a, b)", 2, ["inventado"])


def test_firma_ilegible_no_acusa():
    """Regla 9: solo se bloquea sobre hechos. Lo que no se puede verificar, admite."""
    assert bucle.firma_admite("(esto no es una firma", 5, [])


def test_posible_metodo_prueba_el_self_implicito():
    assert bucle.firma_admite("(self, x)", 1, [], posible_metodo=True)
    assert not bucle.firma_admite("(self, x)", 1, [])


def test_caza_la_llamada_de_la_primera_tirada_en_vivo(worktree_real):
    """El caso medido el 5-ago: B escribio `calcula(3, 4)` con el hecho
    (a, b) -> (a, b, base) delante. La verificacion lo encuentra en el diff,
    estatica y sin modelo, ANTES de la union."""
    f = worktree_real / "tests" / "test_experimento_uso.py"
    f.write_text(f.read_text(encoding="utf-8")
                 + "\nfrom experimento.nucleo import calcula\n\n\n"
                   "def test_directa():\n    assert calcula(3, 4) == 34\n",
                 encoding="utf-8")
    infracciones = bucle.llamadas_contra_firma_vieja(str(worktree_real), [HECHO_VIVO])
    assert len(infracciones) == 1
    assert "test_experimento_uso.py" in infracciones[0]
    assert "(a, b, base)" in infracciones[0]


def test_la_llamada_que_adopta_la_firma_nueva_no_se_acusa(worktree_real):
    f = worktree_real / "tests" / "test_experimento_uso.py"
    f.write_text(f.read_text(encoding="utf-8")
                 + "\nfrom experimento.nucleo import calcula\n\n\n"
                   "def test_directa():\n    assert calcula(3, 4, 10) == 34\n",
                 encoding="utf-8")
    assert bucle.llamadas_contra_firma_vieja(str(worktree_real), [HECHO_VIVO]) == []


def test_el_fichero_nuevo_tambien_entra_en_el_diff(worktree_real):
    """Los agentes no commitean: un fichero recien creado solo aparece en el
    diff gracias al add -N. Sin el, la infraccion escaparia."""
    nuevo = worktree_real / "tests" / "test_nuevo_del_agente.py"
    nuevo.write_text("from experimento.nucleo import calcula\n\n\n"
                     "def test_x():\n    assert calcula(1, 2) == 12\n",
                     encoding="utf-8")
    infracciones = bucle.llamadas_contra_firma_vieja(str(worktree_real), [HECHO_VIVO])
    assert len(infracciones) == 1
    assert "test_nuevo_del_agente.py" in infracciones[0]


def test_llamar_a_lo_borrado_es_infraccion(worktree_real):
    hecho = "experimento.nucleo.calcula: (a, b) -> (borrada)"
    f = worktree_real / "tests" / "test_experimento_uso.py"
    f.write_text(f.read_text(encoding="utf-8")
                 + "\nfrom experimento.nucleo import calcula\n\n\n"
                   "def test_directa():\n    assert calcula(3, 4, 10) == 34\n",
                 encoding="utf-8")
    infracciones = bucle.llamadas_contra_firma_vieja(str(worktree_real), [hecho])
    assert len(infracciones) == 1
    assert "borrado" in infracciones[0]


def test_las_llamadas_viejas_no_tocadas_no_se_acusan(worktree_real):
    """experimento/capa.py llama a calcula con la firma vieja en la base — pero
    el agente no lo toco, asi que no es suyo y no se acusa."""
    assert bucle.llamadas_contra_firma_vieja(str(worktree_real), [HECHO_VIVO]) == []
