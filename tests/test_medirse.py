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
import os

from galaxybrain import store, viz


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
