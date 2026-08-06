"""Las dos cosas que gb no sabia decir de si mismo.

1. **Cuantas capturas se han LEIDO.** El proyecto medía su latencia, su overhead
   y su recall, y no medía lo único que decide si sirve. Guardar mil fallos que
   nadie abre no es una consola de errores: es un vertedero con índice. Es la
   regla 10 —el abandono es dato— cobrada por fin.

2. **De cuándo es un artefacto exportado.** Un HTML sin sello es indistinguible
   de otro de hace cinco horas, y eso pasó de verdad: se estuvo mirando un mapa
   viejo y nada lo dijo.

Ninguna de las dos blinda nada. Apuntar que dejaste de mirar es lo contrario de
impedir que dejes de mirar.
"""


import json

from galaxybrain import cli, store, viz


def _captura(gb_home, ident, project="/proyecto"):
    registro = {
        "id": ident,
        "ts": "2026-08-01T02:00:00+02:00",
        "exception": {"type": "ValueError", "message": "x"},
        "process": {"project": project},
        "frames": [{"file": "/proyecto/a.py", "line": 1, "function": "f"}],
    }
    store.write(registro)
    return ident


def test_sin_leer_nada_el_contador_esta_a_cero(gb_home):
    _captura(gb_home, "uno")
    capturas, leidas, aperturas = store.read_stats()
    assert (capturas, leidas, aperturas) == (1, 0, 0)


def test_leer_una_captura_la_cuenta(gb_home):
    ident = _captura(gb_home, "uno")
    store.mark_read(ident)
    capturas, leidas, _aperturas = store.read_stats()
    assert (capturas, leidas) == (1, 1)


def test_abrir_dos_veces_el_mismo_fallo_no_son_dos_fallos_aprovechados(gb_home):
    """Lo que mide el termometro es cuantos fallos LLEGARON a mirarse, no cuantas
    veces se abrio la consola. Contar aperturas como capturas inflaria el numero
    justo en el caso en que estas peleando con el mismo bug."""
    ident = _captura(gb_home, "uno")
    store.mark_read(ident)
    store.mark_read(ident)
    capturas, leidas, aperturas = store.read_stats()
    assert (capturas, leidas) == (1, 1)
    assert aperturas == 2  # pero volver tambien se apunta, aparte


def test_una_lectura_de_algo_que_ya_no_existe_no_cuenta(gb_home):
    """El historico se puede borrar. Un recuento que sobreviviera a sus capturas
    diria '5 de 0 leidas', que es aritmetica imposible presentada como dato."""
    store.mark_read("fantasma")
    assert store.read_stats() == (0, 0, 0)


def test_apuntar_una_lectura_nunca_puede_romper_la_lectura(gb_home, monkeypatch):
    """Regla 9: si el apunte falla, ver el fallo sigue funcionando. Es lo unico
    que no se negocia — la consola existe para el momento en que algo ya ha ido
    mal."""

    def _revienta(*_a, **_k):
        raise OSError("disco lleno")

    monkeypatch.setattr("builtins.open", _revienta)
    store.mark_read("uno")  # no lanza


def test_una_linea_corrupta_no_invalida_el_recuento(gb_home):
    ident = _captura(gb_home, "uno")
    store.mark_read(ident)
    with open(store.root() / store.READS_NAME, "a", encoding="utf-8") as handle:
        handle.write("{esto no es json\n")
    assert store.read_stats()[1] == 1


def test_el_html_dice_de_cuando_es(tmp_path):
    informe = {"nodes": [], "edges": [], "root": str(tmp_path)}
    salida = viz.render_graph_cloud(informe, procedencia="generado el 2026-08-01 desde abc1234")
    assert "2026-08-01" in salida
    assert "abc1234" in salida


def test_sin_sello_el_renderizador_sigue_siendo_determinista(tmp_path):
    """El sello lo inyecta quien llama, no se lee del reloj dentro: si `viz`
    mirara la hora, dos capturas del mismo proyecto dejarian de compararse."""
    informe = {"nodes": [], "edges": [], "root": str(tmp_path)}
    assert viz.render_graph_cloud(informe) == viz.render_graph_cloud(informe)
    assert viz.render_graph_cloud(informe, procedencia="A") != viz.render_graph_cloud(
        informe, procedencia="B"
    )


def test_el_sello_no_se_come_lo_que_ya_habia_en_el_pie(tmp_path):
    informe = {
        "nodes": [],
        "edges": [],
        "root": str(tmp_path),
        "unresolved": {"atributo-de-variable": 7},
    }
    salida = viz.render_graph_cloud(informe, procedencia="sello")
    assert "sello" in salida
    assert "sin resolver" in salida


# --- La libreta de usos: la otra mitad del termometro (regla 10) ---------------
#
# read_stats dice si lo capturado se LEE; esto dice si gb se INVOCA siquiera.
# "¿El agente tiene la herramienta en cuenta?" era la unica pregunta del
# proyecto sin instrumento. Mide invocacion, no aprovechamiento: termometro,
# no cura.

def test_cada_invocacion_se_apunta_en_la_libreta(gb_home):
    store.mark_uso("graph --context")
    store.mark_uso("show")
    store.mark_uso("graph --context")
    assert store.uso_stats() == {"graph --context": 2, "show": 1}


def test_los_usos_viejos_caen_fuera_de_la_ventana(gb_home):
    destino = store.root() / store.USOS_NAME
    destino.parent.mkdir(parents=True, exist_ok=True)
    viejo = {"cmd": "show", "ts": "2026-01-01T00:00:00+00:00"}
    destino.write_text(json.dumps(viejo) + "\n", encoding="utf-8")
    store.mark_uso("graph")
    assert store.uso_stats() == {"graph": 1}


def test_una_linea_corrupta_no_invalida_el_recuento_de_usos(gb_home):
    destino = store.root() / store.USOS_NAME
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("esto no es json\n", encoding="utf-8")
    store.mark_uso("last")
    assert store.uso_stats() == {"last": 1}


def test_la_libreta_se_compacta_al_pasar_el_tope(gb_home, monkeypatch):
    """Un termometro no necesita historia infinita: al pasar el tope se queda
    la ventana reciente y lo de hace anos cae."""
    monkeypatch.setattr(store, "_USOS_TOPE", 1)  # cualquier append dispara la compactacion
    destino = store.root() / store.USOS_NAME
    destino.parent.mkdir(parents=True, exist_ok=True)
    viejo = {"cmd": "show", "ts": "2020-01-01T00:00:00+00:00"}
    destino.write_text(json.dumps(viejo) + "\n", encoding="utf-8")
    store.mark_uso("graph")
    contenido = destino.read_text(encoding="utf-8")
    assert "2020-01-01" not in contenido
    assert "graph" in contenido


def test_apuntar_un_uso_nunca_puede_romper_el_comando(gb_home, monkeypatch):
    """Regla 9: el termometro jamas le cuesta nada al que usa la herramienta."""

    def _revienta(*_a, **_k):
        raise OSError("disco lleno")

    monkeypatch.setattr(store, "root", _revienta)
    store.mark_uso("graph")  # si esto lanza, el test falla solo


def test_el_cli_apunta_cada_comando_con_su_etiqueta(gb_home, capsys, tmp_path):
    """La distincion que importa: el empujon del hook (`graph --context`) no se
    confunde con el uso deliberado (`status`). Sin apellido, 40 inyecciones de
    SessionStart se leerian como adopcion."""
    cli.main(["graph", str(tmp_path), "--context"])  # calla (sin modulos), pero corrio
    cli.main(["status"])
    capsys.readouterr()
    stats = store.uso_stats()
    assert stats == {"graph --context": 1, "status": 1}


def test_status_ensena_el_desglose_de_uso(gb_home, capsys):
    store.mark_uso("show")
    store.mark_uso("show")
    cli.main(["status"])
    out = capsys.readouterr().out
    assert "uso (7 dias)" in out
    assert "show 2" in out
    assert "status 1" in out  # el propio status tambien cuenta: transparente


def test_el_gate_del_precommit_se_apunta_con_apellido(gb_home, capsys, tmp_path):
    """`graph --gate` en el pre-commit es maquinaria, no eleccion: sin apellido,
    cada commit inflaria la cifra de uso deliberado."""
    cli.main(["graph", str(tmp_path), "--gate"])
    capsys.readouterr()
    assert store.uso_stats() == {"graph --gate": 1}


def test_exploracion_separa_temporal_efimero_y_sin_sitio():
    """Mas ancho que is_ephemeral: el temporal del sistema (sondas de agentes)
    y las capturas sin sitio tampoco son codigo de proyecto. La ruta es el
    hecho; la intencion no se adivina."""
    import os
    import tempfile

    assert store.es_exploracion({"where": "<string>:1"})
    assert store.es_exploracion({"where": None})
    assert store.es_exploracion({"where": "?"})
    sonda = os.path.join(tempfile.gettempdir(), "sonda", "x.py") + ":3"
    assert store.es_exploracion({"where": sonda})
    assert not store.es_exploracion({"where": os.path.join("src", "a.py") + ":7"})
    assert not store.es_exploracion({"where": os.path.abspath(os.path.join("proyecto", "a.py")) + ":7"})


def test_el_termometro_separa_codigo_de_exploracion(gb_home, capsys):
    """El '13 de 55 leidas' escondia un 6/6 en codigo real (investigacion del
    6-ago, docs/pruebas-de-uso.md): el status separa el denominador para que el
    termometro lea senal y no ruido."""
    import os
    import tempfile

    from galaxybrain import cli

    ident = _captura(gb_home, "real")  # /proyecto/a.py -> codigo
    registro = {
        "id": "sonda",
        "ts": "2026-08-01T03:00:00+02:00",
        "exception": {"type": "ValueError", "message": "x"},
        "process": {"project": "/proyecto"},
        "frames": [{"file": os.path.join(tempfile.gettempdir(), "s", "b.py"), "line": 1, "function": "f"}],
    }
    store.write(registro)
    store.mark_read(ident)

    assert cli.main(["status"]) == 0
    salida = capsys.readouterr().out
    assert "1/1 en codigo de proyecto" in salida
    assert "0/1 exploracion" in salida
