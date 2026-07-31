"""`gb graph --self-test`: verificar el gate rompiendolo, no comprobando que pasa.

Motivo (docs/pruebas-de-uso.md, 31-jul-2026): un gate se degrada EN SILENCIO —
sigue devolviendo cero y ya no mira nada. Paso dos veces el mismo dia. Los tests
fijan lo que el autor sabia comprobar; esto fija que el detector sigue detectando
cuando le pones el defecto delante.

Criterio de terminado, escrito antes de implementarlo:
  1. Con gb sano sale 0 y DICE que ha probado (un "OK" mudo seria el mismo fallo).
  2. Si se rompe la deteccion, la sonda correspondiente falla y sale != 0.
     Sin esto el comando seria decorativo: hay que vigilar al vigilante.
  3. No escribe nada dentro del proyecto del usuario ni deja restos.
  4. No necesita git ni red.
  5. Cubre los defectos que ocurrieron DE VERDAD, no casos imaginados.
"""

import os

from galaxybrain import graph, render


def test_con_gb_sano_todas_las_sondas_ven_su_defecto():
    informe = graph.self_test()
    assert informe["failed"] == [], "sondas sin ver su defecto: %s" % informe["failed"]
    assert len(informe["probes"]) >= 6


def test_enumera_lo_probado_en_vez_de_un_ok_mudo():
    """(1) del criterio. Un "todo correcto" sin decir que se comprobo es
    exactamente el silencio que este comando existe para desmontar."""
    salida = render.render_self_test(graph.self_test(), render.Style(False))
    for probe in graph.self_test()["probes"]:
        assert probe["sonda"] in salida


def test_si_se_rompe_la_deteccion_de_ciclos_la_sonda_lo_CAZA(monkeypatch):
    """(2) del criterio, y es la prueba que hace util a todo lo demas: quien
    vigila al vigilante. Se simula la degradacion tipica — el detector deja de
    ver y sigue devolviendo una respuesta perfectamente valida."""
    monkeypatch.setattr(graph, "find_cycles", lambda edges: [])

    informe = graph.self_test()
    assert "ciclo de imports" in informe["failed"]

    salida = render.render_self_test(informe, render.Style(False))
    assert "no he mirado" in salida  # y se dice con esas palabras


def test_si_se_rompe_la_deteccion_de_cruces_tambien(monkeypatch):
    monkeypatch.setattr(graph, "find_violations", lambda edges, rules: [])
    informe = graph.self_test()
    assert "cruce de frontera" in informe["failed"]


def test_un_detector_que_grita_siempre_tampoco_pasa(monkeypatch):
    """La mitad que casi nadie prueba: un gate que dispara con todo pasaria las
    sondas de deteccion y seria inservible. La sonda del proyecto limpio existe
    para eso, asi que tiene que caer cuando el detector se vuelve paranoico."""
    monkeypatch.setattr(graph, "find_cycles", lambda edges: [["falso", "positivo"]])
    informe = graph.self_test()
    assert "proyecto limpio" in informe["failed"]


def test_una_sonda_que_revienta_es_un_fallo_no_un_crash():
    """Si una sonda lanza, el comando tiene que decirlo y seguir con las demas:
    un `--self-test` que se muere a la mitad no informa de nada."""
    original = graph._SONDAS

    def _revienta(raiz):
        raise RuntimeError("sonda rota")

    try:
        graph._SONDAS = original + (("sonda de mentira", "da igual", _revienta),)
        informe = graph.self_test()
    finally:
        graph._SONDAS = original

    assert "sonda de mentira" in informe["failed"]
    detalle = [p for p in informe["probes"] if p["sonda"] == "sonda de mentira"][0]["detalle"]
    assert "reviento" in detalle and "RuntimeError" in detalle


def test_no_ensucia_el_directorio_de_trabajo(tmp_path, monkeypatch):
    """(3) del criterio: el arnes nunca escribe dentro del proyecto observado."""
    monkeypatch.chdir(tmp_path)
    graph.self_test()
    assert list(tmp_path.iterdir()) == []


def test_no_necesita_git(tmp_path, monkeypatch):
    """(4). Si `git` no esta en el PATH esto tiene que seguir contestando: es un
    chequeo sobre la herramienta, no sobre tu repo."""
    monkeypatch.setenv("PATH", str(tmp_path))
    assert graph.self_test()["failed"] == []


def test_cada_sonda_declara_que_espera():
    """El informe se lee sin abrir el codigo: cada linea dice si el gate tenia
    que ver algo o tenia que callar."""
    for probe in graph.self_test()["probes"]:
        assert probe["espera"]
        assert probe["detalle"]
