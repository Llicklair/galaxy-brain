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

# El banco de replay, por ruta y apuntado a ESTA instancia del orquestador: sin
# esto cada uno cargaria la suya y la prueba de mutacion no llegaria al codigo
# que corre (bucle/ no es paquete: `import bucle` cae en un namespace package).
_RUTA_REPLAY = os.path.join(os.path.dirname(__file__), "..", "bucle", "replay.py")
_spec_r = importlib.util.spec_from_file_location("replay_del_banco", _RUTA_REPLAY)
replay = importlib.util.module_from_spec(_spec_r)
_spec_r.loader.exec_module(replay)
replay.bucle = bucle


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


#: El banco del enrutador que estos tests necesitan dentro del worktree. Vivía
#: en `experimento/` y en `tests/test_experimento_uso.py`, commiteado en `main`
#: — y eso ataba unos tests de la columna a que el repo publicado siguiera
#: llevando encima un banco que su propio docstring llamaba «desechable». Ahora
#: se fabrica aquí: el material del test viaja CON el test, y el repo puede
#: soltar el banco sin que se caiga nada.
_BANCO = {
    "experimento/__init__.py": "",
    "experimento/nucleo.py": "def calcula(a, b):\n"
                             "    return int(str(a) + str(b))\n",
    "experimento/capa.py": "from experimento.nucleo import calcula\n"
                           "\n"
                           "\n"
                           "def procesa(pares):\n"
                           "    return sum(calcula(a, b) for a, b in pares)\n",
    "tests/test_experimento_uso.py": '"""Tests del banco del enrutador. Desechables, como el banco."""\n'
                                     "\n"
                                     "from experimento.capa import procesa\n"
                                     "\n"
                                     "\n"
                                     "def test_procesa_suma_pares():\n"
                                     "    assert procesa([(1, 2), (3, 4)]) == 12 + 34\n",
}


@pytest.fixture
def worktree_real(tmp_path):
    """Un worktree DE ESTE repo, con el banco dentro, para derivar de verdad.

    El worktree es real —la derivación tiene que leer un árbol de git de verdad,
    no una maqueta— pero el BANCO lo pone el test y no el repo: se escribe y se
    commitea dentro del worktree, que está desprendido, así que `main` no se
    entera.
    """
    ruta = tmp_path / "wt-bucle-test"
    _git(bucle.RAIZ, "worktree", "add", "--detach", str(ruta), "main")
    for rel, contenido in _BANCO.items():
        destino = ruta / rel
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(contenido, encoding="utf-8")
    _git(str(ruta), "add", *_BANCO)
    # `--no-verify` aquí no es saltarse el gate: el pre-commit de este repo corre
    # la suite entera, y esto ES la suite. Sin él, cada fixture relanza los 887
    # tests dentro de un test y la pasada no termina nunca (medido: se colgó).
    _git(str(ruta), "-c", "user.name=t", "-c", "user.email=t@t",
         "commit", "-q", "--no-verify", "-m", "banco del enrutador (fixture)")
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


# --- actas: el dataset se acumula, nunca se pisa ------------------------------

def test_cada_inicio_da_un_acta_distinta_y_ninguna_pisa_a_otra():
    """La primera acta viva del proyecto se perdio por sobreescritura (la
    tirada de las 00:15 del 6-ago piso la de las 22:40 del 5-ago). El nombre
    se deriva del inicio: dos tiradas, dos ficheros."""
    a = bucle._ruta_acta("2026-08-05 22:40:12")
    b = bucle._ruta_acta("2026-08-06 00:15:34")
    assert a != b
    assert a.endswith(os.path.join(".claude", "actas", "bucle-20260805-224012.json"))
    assert b.endswith(os.path.join(".claude", "actas", "bucle-20260806-001534.json"))


def test_el_acta_registra_el_despacho_entero_de_cada_lanzamiento(monkeypatch, tmp_path):
    """La variante del despacho ES su texto (derivado sobre declarado: una
    etiqueta de version se olvida de subir; el texto no miente). Sin esta
    columna, el dataset de actas no puede comparar formatos de despacho."""
    monkeypatch.setattr(bucle, "RAIZ", str(tmp_path))
    monkeypatch.setattr(bucle, "preparar_worktree", lambda i: str(tmp_path / i))
    monkeypatch.setattr(bucle, "quitar_worktree", lambda r: None)
    firmas = iter([{"m.f": "(a)"}, {"m.f": "(a, b)"}, {"m.f": "(a, b)"}])
    monkeypatch.setattr(bucle, "firmas_de", lambda r: next(firmas))
    monkeypatch.setattr(bucle, "ejecutar_simulado", lambda t, w, d: None)
    monkeypatch.setattr(bucle, "llamadas_contra_firma_vieja", lambda w, h: [])
    monkeypatch.setattr(bucle, "veredicto_union", lambda: (0, True, [], "ok"))
    monkeypatch.setattr(bucle, "_corre", lambda *a, **k: (0, b"", b""))
    tirada = {"tareas": [{"id": "A", "prompt": "rompe la firma"},
                         {"id": "B", "prompt": "haz tests", "depende_de": ["A"]}]}

    acta = bucle.correr(tirada, dir_parches="da-igual")

    assert acta["despachos"]["A"] and "rompe la firma" in acta["despachos"]["A"][0]
    assert "SEÑAL DEL ENRUTADOR" in acta["despachos"]["B"][0]
    assert "m.f: (a) -> (a, b)" in acta["despachos"]["B"][0]


# --- resumen: la lectura del dataset, derivada de lo que hay ------------------

def _acta_minima(**extra):
    base = {"inicio": "2026-08-05 22:40:12", "modo": "real", "veredicto": "roja",
            "reintentos": 1, "entregas": {"B": ["m.f: (a) -> (a, b)"]}, "pasos": []}
    base.update(extra)
    return base


def test_el_resumen_dice_sin_dato_para_actas_v0_y_no_inventa(tmp_path):
    import json
    (tmp_path / "bucle-1.json").write_text(json.dumps(_acta_minima()), encoding="utf-8")
    texto = bucle.resumen_actas(str(tmp_path))
    assert "sin dato (acta v0)" in texto
    assert "adopcion ignorada 0/0" in texto


def test_el_resumen_cuenta_el_rechazo_que_corrige(tmp_path):
    import json
    acta = _acta_minima(
        veredicto="verde",
        adopcion={"B": ["t.py:20: f(2 posicional(es)) no encaja en la firma nueva (a, b)"]},
        pasos=["adopcion de B: 1 llamada(s) contra la señal",
               "reintento de B por adopcion: limpio"])
    (tmp_path / "bucle-2.json").write_text(json.dumps(acta, ensure_ascii=False),
                                           encoding="utf-8")
    texto = bucle.resumen_actas(str(tmp_path))
    assert "adopcion ignorada 1/1" in texto
    assert "rechazo corrigio 1/1" in texto


def test_el_resumen_no_confunde_la_senal_con_las_marcas_del_bucle(tmp_path):
    """'(cola del fallo de union)' y '(rechazo por adopcion)' son marcas del
    propio bucle, no hechos enrutados: un acta que solo tenga esas no cuenta
    como despacho con señal."""
    import json
    acta = _acta_minima(entregas={"B": ["(cola del fallo de union)"]})
    (tmp_path / "bucle-3.json").write_text(json.dumps(acta), encoding="utf-8")
    assert "1 tirada(s) · 0 con señal" in bucle.resumen_actas(str(tmp_path))


def test_el_resumen_de_un_directorio_vacio_no_peta(tmp_path):
    assert "0 tirada(s)" in bucle.resumen_actas(str(tmp_path / "no-existe"))

# --- la consola del agente: su stdout, teeado al lado del worktree ------------

def test_la_linea_de_consola_resume_el_evento_stream():
    """El stdout real del agente (stream-json): lo que dice y las herramientas
    que usa, en una linea legible cada uno. Es la fuente de la terminal del
    mapa — narrativa observada, no interpretada."""
    ev = {"type": "assistant", "message": {"content": [
        {"type": "text", "text": "Voy a cambiar   el contrato de calcula."},
        {"type": "tool_use", "name": "Edit", "input": {"file_path": "experimento/nucleo.py"}},
    ]}}
    linea = bucle._linea_consola(ev)
    assert "Voy a cambiar el contrato de calcula." in linea
    assert "> Edit experimento/nucleo.py" in linea
    assert bucle._linea_consola({"type": "result", "result": "listo,  254 tests"}) == "= listo, 254 tests"


def test_eventos_sin_sustancia_no_producen_linea():
    assert bucle._linea_consola({"type": "system"}) is None
    assert bucle._linea_consola({"type": "assistant", "message": {"content": []}}) is None


def test_la_consola_vive_al_lado_del_worktree_no_dentro():
    """Dentro ensuciaria el git status del agente y se veria como cambio suyo."""
    ruta = bucle._log_consola(os.path.join("x", "worktrees", "bucle-A"))
    assert ruta.endswith("bucle-A.consola.log")
    assert os.path.dirname(ruta).endswith("worktrees")


# --- la consola de errores aterriza en el acta --------------------------------

def test_las_capturas_de_la_tirada_se_filtran_por_su_inicio(monkeypatch):
    """El acta registra lo que peto DURANTE la tirada — vacio es un hecho; lo
    de antes no es de esta tirada. Fechas a dias de distancia para que ningun
    huso horario mueva el veredicto."""
    import json as _json
    lista = _json.dumps([
        {"id": "viejo111", "ts": "2026-08-04T00:00:00+02:00",
         "type": "KeyError", "where": "a.py:1"},
        {"id": "nuevo222", "ts": "2026-08-08T00:00:00+02:00",
         "type": "ValueError", "where": "b.py:2"},
    ]).encode("utf-8")
    monkeypatch.setattr(bucle, "_corre", lambda *a, **k: (0, lista, b""))

    capturas = bucle.capturas_desde("2026-08-06 03:00:00")
    assert [c["tipo"] for c in capturas] == ["ValueError"]
    assert capturas[0]["id"] == "nuevo222"


def test_si_la_consola_no_responde_el_acta_no_inventa(monkeypatch):
    monkeypatch.setattr(bucle, "_corre", lambda *a, **k: (1, b"", b"error"))
    assert bucle.capturas_desde("2026-08-06 03:00:00") == []


def test_sin_senal_retiene_el_despacho_pero_no_la_verificacion():
    """4ª rebanada: con --sin-senal los hechos NO viajan en el despacho (el
    agente no ve la señal preventiva) pero el bucle se los queda para verificar
    la adopcion y para el rechazo. La variante es el TEXTO del despacho."""
    tarea = {"id": "B", "prompt": "haz tests", "depende_de": ["A"]}
    hechos = ["calcula(a, b) -> calcula(a, b, base)"]

    prompt, entregados, retenidos = bucle.despacho_de(tarea, hechos, sin_senal=True)
    assert "SEÑAL DEL ENRUTADOR" not in prompt
    assert entregados == []
    assert retenidos == hechos

    prompt, entregados, retenidos = bucle.despacho_de(tarea, hechos, sin_senal=False)
    assert "SEÑAL DEL ENRUTADOR" in prompt
    assert entregados == hechos
    assert retenidos == []

    # sin hechos no hay nada que retener, con o sin bandera
    prompt, entregados, retenidos = bucle.despacho_de(tarea, [], sin_senal=True)
    assert entregados == [] and retenidos == []


def test_aviso_desfase_lleva_el_marco_pero_no_los_hechos():
    """5ª rebanada: el confundido de la 4ª (quito hechos Y marco a la vez) se
    deshace despachando SOLO el marco. El aviso viaja, los hechos se retienen
    para la verificacion y el rechazo."""
    tarea = {"id": "B", "prompt": "haz tests", "depende_de": ["A"]}
    hechos = ["calcula(a, b) -> calcula(a, b, base)"]

    prompt, entregados, retenidos = bucle.despacho_de(tarea, hechos, aviso_desfase=True)
    assert "AVISO DEL ENRUTADOR" in prompt
    assert "SEÑAL DEL ENRUTADOR" not in prompt
    assert "calcula" not in prompt.replace(tarea["prompt"], "")  # los hechos no viajan
    assert entregados == []
    assert retenidos == hechos

    # sin dependencias no hay hechos ni aviso que dar
    prompt, _, _ = bucle.despacho_de({"id": "A", "prompt": "x"}, [], aviso_desfase=True)
    assert "AVISO DEL ENRUTADOR" not in prompt


def test_los_modos_de_despacho_son_excluyentes():
    """El defecto es el marco; desviarse cuesta UNA bandera, no una combinacion
    ambigua. Dos modos a la vez es un error de uso, no una preferencia."""
    try:
        bucle.main(["tirada.json", "--sin-senal", "--senal-completa"])
        raise AssertionError("argparse debia rechazar los modos combinados")
    except SystemExit as e:
        assert e.code == 2


# --- el banco de replay: el verificador contra las tiradas ya vividas ---------


def _repo_con_tirada(tmp_path):
    """Un repo real con el caso del banco: A rompe la firma, B llama a la vieja.
    Devuelve (root, diff, hecho) — el diff tal y como lo guarda un acta."""
    import subprocess

    root = str(tmp_path / "repo")
    os.makedirs(os.path.join(root, "tests"), exist_ok=True)
    def escribe(rel, texto):
        ruta = os.path.join(root, *rel.split("/"))
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, "w", encoding="utf-8") as fh:
            fh.write(texto)

    subprocess.run(["git", "init", "-q"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
    escribe("nucleo.py", "def calcula(a, b):\n    return a * 10 + b\n")
    escribe("tests/test_uso.py", "from nucleo import calcula\n")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=root, check=True,
                   capture_output=True)
    # A rompe el contrato y B escribe contra la firma VIEJA
    escribe("nucleo.py", "def calcula(a, b, base):\n    return a * base + b\n")
    escribe("tests/test_uso.py", "from nucleo import calcula\n\n\ndef test_x():\n"
                                 "    assert calcula(3, 4) == 34\n")
    subprocess.run(["git", "add", "-N", "."], cwd=root, check=True, capture_output=True)
    diff = subprocess.run(["git", "diff", "HEAD"], cwd=root, check=True,
                          capture_output=True).stdout.decode("utf-8", "replace")
    return root, diff, "nucleo.calcula: (a, b) -> (a, b, base)"


def test_el_banco_reproduce_una_infraccion_grabada(tmp_path):
    """El banco rehace el arbol desde los blobs del diff (cat-file) y corre EL
    verificador de verdad — cero cuota, cero agentes."""
    root, diff, hecho = _repo_con_tirada(tmp_path)
    acta = {
        "inicio": "sintetica",
        "tareas": ["B"],
        "entregas": {"B": [hecho]},
        "diffs": {"B": diff},
        "adopcion": {"B": ["tests/test_uso.py:5: ..."]},
        "pasos": ["adopcion de B: 1 llamada(s) contra la señal"],  # rechazo, sin reintento
    }
    (fila,) = replay.replay_acta(acta, root=root)
    assert fila["irrecuperables"] == []
    assert len(fila["obtenido"]) == 1
    assert "tests/test_uso.py:5" in fila["obtenido"][0]


def test_el_banco_SE_PONE_ROJO_si_el_verificador_se_rompe(tmp_path, monkeypatch):
    """La prueba de que el banco sirve: mutar el verificador para que deje
    escapar la infraccion tiene que hacerlo FALLAR. Un banco que no puede
    ponerse rojo no esta midiendo nada."""
    root, diff, hecho = _repo_con_tirada(tmp_path)
    acta = {
        "inicio": "sintetica",
        "tareas": ["B"],
        "entregas": {"B": [hecho]},
        "diffs": {"B": diff},
        "adopcion": {"B": ["tests/test_uso.py:5: no encaja"]},
        "pasos": ["adopcion de B: 1 llamada(s) contra la señal"],
    }
    (sano,) = replay.replay_acta(acta, root=root)
    assert sano["ok"] is True or len(sano["obtenido"]) == 1

    monkeypatch.setattr(bucle, "firma_admite", lambda *a, **k: True)  # el verificador, ciego
    (roto,) = replay.replay_acta(acta, root=root)
    assert roto["obtenido"] == []
    assert roto["ok"] is False  # falso negativo cazado por el banco


def test_la_verdad_de_campo_sale_de_los_pasos_del_acta():
    """El acta anota las infracciones del PRIMER intento y guarda el diff FINAL:
    cual de los dos toca lo dicen los pasos, no una suposicion."""
    limpio = {"adopcion": {"B": ["x"]},
              "pasos": ["adopcion de B: 1", "reintento de B por adopcion: limpio"]}
    assert replay.esperado_del_final(limpio, "B") == []

    quedan = {"adopcion": {"B": ["vieja", replay.MARCA_REINTENTO, "sigue"]},
              "pasos": ["adopcion de B: 1", "reintento de B por adopcion: 1 infraccion(es) aun"]}
    assert replay.esperado_del_final(quedan, "B") == ["sigue"]

    sin_reintento = {"adopcion": {"B": ["vieja"]}, "pasos": ["adopcion de B: 1"]}
    assert replay.esperado_del_final(sin_reintento, "B") == ["vieja"]

    nunca = {"adopcion": {}, "pasos": ["lanzada B (1 hecho(s) en el despacho)"]}
    assert replay.esperado_del_final(nunca, "B") == []


def test_los_hechos_del_replay_incluyen_la_señal_RETENIDA():
    """Los brazos sin señal preventiva retienen los hechos: el banco tiene que
    verificar con ellos igual, o los daria todos por limpios."""
    acta = {"entregas": {"B": ["(rechazo por adopcion)"]},
            "senal_retenida": {"B": ["nucleo.calcula: (a, b) -> (a, b, base)"]}}
    assert replay.hechos_de(acta, "B") == ["nucleo.calcula: (a, b) -> (a, b, base)"]


# --- el lanzador de UN agente: la friccion medida en uso real ----------------


def test_el_nombre_del_worktree_sale_de_la_tarea():
    """La tarjeta del mapa se llama como lo que el agente hace: sin nombre que
    inventar, un paso menos que teclear."""
    _RUTA_AG = os.path.join(os.path.dirname(__file__), "..", "bucle", "agente.py")
    _spec_a = importlib.util.spec_from_file_location("agente_del_banco", _RUTA_AG)
    agente = importlib.util.module_from_spec(_spec_a)
    _spec_a.loader.exec_module(agente)

    assert agente.nombre_por_defecto("arregla el parser de firmas") == "arregla-el-parser"
    assert agente.nombre_por_defecto("¡¿!!") == "agente"           # nunca vacio
    # y NO reimplementa al orquestador: usa SUS piezas (una copia divergiria)
    assert agente.bucle._log_consola is not None
    assert not hasattr(agente, "log_consola"), "el lanzador volvio a duplicar la consola"
    assert not hasattr(agente, "_corre"), "el lanzador volvio a duplicar el subproceso"
