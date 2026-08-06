"""El mapa en imagen. La propiedad que importa NO es que sea bonito: es que dos
ejecuciones del mismo grafo den el mismo fichero.

Si las posiciones bailan entre ejecuciones, dos capturas del mismo proyecto no se
pueden comparar — y comparar es justamente para lo que uno mira crecer un proyecto.
Un layout de fuerzas queda mejor y no cumple esto.
"""

import os

from galaxybrain import cli, viz


def _write(root, rel, content):
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def _proyecto(tmp_path):
    root = str(tmp_path)
    _write(root, "app/__init__.py", "")
    _write(root, "app/config.py", "AJUSTE = 1\n")
    _write(root, "app/store.py", "from app.config import AJUSTE\n")
    _write(root, "app/api.py", "from app.store import AJUSTE\nfrom app.config import AJUSTE as A\n")
    return root


def test_el_layout_de_fuerzas_tambien_es_determinista():
    """Corrige una afirmacion anterior de este proyecto: se dijo que un layout de
    fuerzas renuncia al determinismo, y es falso — solo baila si lo arrancas al azar.
    Con inicio determinista e iteraciones fijas sale identico siempre."""
    nodos = ["a", "b", "c", "d", "e"]
    aristas = [("a", "b"), ("b", "c"), ("c", "d"), ("d", "e"), ("e", "a")]

    assert viz.force_layout(nodos, aristas) == viz.force_layout(nodos, aristas)


def test_el_layout_separa_lo_que_no_esta_conectado():
    """Comprobacion minima de que hace su trabajo: dos grupos sin arista entre ellos
    no pueden acabar amontonados en el mismo punto."""
    nodos = ["a1", "a2", "b1", "b2"]
    pos = viz.force_layout(nodos, [("a1", "a2"), ("b1", "b2")])

    import math

    entre_grupos = math.dist(pos["a1"], pos["b1"])
    dentro = math.dist(pos["a1"], pos["a2"])
    assert entre_grupos > dentro


def test_el_layout_no_amontona_nodos_en_el_borde(tmp_path):
    """Los dos fallos que enseno la captura real del owner, fijados:
    (1) el clamp a la caja apilaba los nodos sueltos en las paredes formando un
    rectangulo; (2) al portar las masas de GitNexus, la repulsion 20x20 vencia a
    la gravedad y el layout explotaba (nodos en x=-6969 sobre un lienzo de 1000).
    El contrato: todo dentro del lienzo y sin pila en el borde."""
    import json as _json
    import re

    from galaxybrain import symbols

    root = _proyecto(tmp_path)
    salida = viz.render_graph_cloud(symbols.analyze(root))
    nodos = _json.loads(re.search(r"const NODOS = (\[.*?\]), ARISTAS", salida, re.S).group(1))

    assert nodos, "el montaje tiene que producir nodos"
    for n in nodos:
        assert 0 <= n["x"] <= 1000 and 0 <= n["y"] <= 1000, "fuera del lienzo: %r" % n["id"]
    en_borde = [n for n in nodos if n["x"] < 20 or n["x"] > 980 or n["y"] < 20 or n["y"] > 980]
    assert len(en_borde) < max(2, len(nodos) // 4), "pila de nodos en el borde"


def test_cada_simbolo_queda_cerca_de_su_modulo(tmp_path):
    """La siembra jerarquica portada de GitNexus: una funcion orbita su modulo.
    Se mide, no se mira: distancia media al modulo < distancia media al centro."""
    import json as _json
    import math
    import re

    from galaxybrain import symbols

    root = _proyecto(tmp_path)
    salida = viz.render_graph_cloud(symbols.analyze(root))
    nodos = _json.loads(re.search(r"const NODOS = (\[.*?\]), ARISTAS", salida, re.S).group(1))

    centros = {n["id"]: (n["x"], n["y"]) for n in nodos if n["k"] == "module"}
    cx = sum(n["x"] for n in nodos) / len(nodos)
    cy = sum(n["y"] for n in nodos) / len(nodos)
    al_modulo, al_centro = [], []
    for n in nodos:
        if n["k"] == "module" or n["g"] not in centros:
            continue
        al_modulo.append(math.dist((n["x"], n["y"]), centros[n["g"]]))
        al_centro.append(math.dist((n["x"], n["y"]), (cx, cy)))
    if al_modulo:
        assert sum(al_modulo) / len(al_modulo) < sum(al_centro) / len(al_centro)


def test_la_nube_incluye_los_simbolos_sin_llamadas(tmp_path):
    """En la primera version un simbolo sin llamadas ni salia — y 'no llamado
    desde ninguna parte' es exactamente algo que se quiere VER."""
    from galaxybrain import symbols

    root = str(tmp_path)
    _write(root, "app/__init__.py", "")
    _write(root, "app/solo.py", "def huerfana():\n    return 1\n")

    salida = viz.render_graph_cloud(symbols.analyze(root))
    assert "huerfana" in salida


def test_la_nube_es_autocontenida_y_determinista(tmp_path):
    root = _proyecto(tmp_path)
    from galaxybrain import symbols

    report = symbols.analyze(root)
    primera = viz.render_graph_cloud(report)

    assert primera == viz.render_graph_cloud(report)
    for prohibido in ('src="http', "cdn.", "sigma", "unpkg"):
        assert prohibido not in primera.lower()


def test_la_nube_lleva_la_cobertura_en_la_cabecera(tmp_path):
    """Un grafo parcial que no dice que es parcial se lee como completo."""
    from galaxybrain import symbols

    salida = viz.render_graph_cloud(symbols.analyze(_proyecto(tmp_path)))
    assert "resueltas de" in salida


def test_el_cli_escribe_el_fichero(tmp_path):
    root = _proyecto(tmp_path)
    destino = os.path.join(root, "mapa.html")

    assert cli.main(["graph", root, "--html", destino, "--color", "never"]) == 0
    assert os.path.exists(destino)
    # `<canvas`, no `<svg`: desde la unificacion, `graph --html` y `symbols --html`
    # llevan a la MISMA pagina — el lienzo con modulos, simbolos, imports y llamadas.
    # Antes eran dos ficheros distintos del mismo sujeto.
    assert "<canvas" in open(destino, encoding="utf-8").read()


def test_un_destino_imposible_no_pasa_por_bueno(tmp_path):
    root = _proyecto(tmp_path)
    destino = os.path.join(root, "no-existe", "sub", "mapa.html")

    assert cli.main(["graph", root, "--html", destino, "--color", "never"]) == 2


def test_los_cuatro_colores_de_tipo_son_distinguibles():
    """`function` y `method` son la inmensa mayoria de los nodos.

    Con esmeralda y teal estaban a ΔE 5,4 en vision NORMAL (el suelo son 15) y la
    nube entera se leia como una mancha verde. Medido el 5-ago-2026 con el
    validador de paleta; el azul sube el par a ΔE 21,1 (8,9 en protanopia).
    """
    colores = [viz._KIND_COLOR[k] for k in ("module", "class", "function", "method")]
    assert len(set(colores)) == 4
    # El par que fallaba, fijado explicitamente para que no vuelva por descuido.
    assert viz._KIND_COLOR["function"] != viz._KIND_COLOR["method"]
    assert viz._KIND_COLOR["method"] == "#60a5fa"


def test_la_leyenda_dibuja_cada_entrada_con_su_marca_real(tmp_path):
    """Una leyenda que pinta todo como punto relleno miente sobre el lienzo.

    Los estados del ciclo son ARO discontinuo y las aristas son LINEA. Con todas
    como punto, se buscaba en el mapa un nodo naranja solido que no existe.
    """
    from galaxybrain import graph, symbols

    root = _proyecto(tmp_path)
    informe = symbols.analyze(root)
    ciclo = {"nodos": {"app.store": {"estado": "capturada", "lineas": []}}}
    # Con el informe de grafo entran los imports, y con ellos las entradas de
    # arista de la leyenda (sin imports no hay aristas que explicar, y calla).
    salida = viz.render_graph_cloud(
        informe, graph_report=graph.analyze(root), ciclo=ciclo, tocados={"app.store"})

    assert 'class="aro" style="color:#f97316"' in salida       # capturada: aro
    assert 'class="linea"' in salida                            # aristas: linea
    assert "box-shadow:0 0 0 3px rgba(" in salida               # en obra: halo
    # Y los tipos siguen siendo punto relleno.
    assert '<i style="background:%s"></i>module' % viz._KIND_COLOR["module"] in salida


def test_rgba_traduce_el_hexadecimal():
    assert viz._rgba("#e879f9", 0.3) == "rgba(232,121,249,0.3)"
    assert viz._rgba("#000000", 1) == "rgba(0,0,0,1)"


def test_la_actividad_viaja_al_mapa_con_color_por_agente(tmp_path):
    """Un color POR AGENTE, no un color para "hay agente".

    Tocado-sin-commitear es un estado del arbol; un agente trabajando es otra
    señal y lleva el color de ESE agente. El nodo lleva la lista `ag` y el
    payload AGENTES trae el color asignado en orden estable (por nombre), para
    que el mismo agente no cambie de color entre regeneraciones.
    """
    import json as _json
    import re

    from galaxybrain import symbols

    root = _proyecto(tmp_path)
    act = {
        "base": "abc1234",
        "agentes": [
            {"nombre": "rama_b", "nodos": ["app.store"], "vecinos": ["app.config"],
             "hace_seg": 5, "fuera_del_mapa": 0, "base": "abc1234", "misma_base": True},
            {"nombre": "rama_a", "nodos": ["app.store"], "vecinos": [],
             "hace_seg": 9, "fuera_del_mapa": 2, "base": "abc1234", "misma_base": True},
        ],
        "por_nodo": {"app.store": {"agentes": ["rama_b", "rama_a"], "vecino_de": []}},
        "cruces": ["app.store"],
    }
    salida = viz.render_graph_cloud(symbols.analyze(root), actividad=act)

    agentes = _json.loads(re.search(r"const AGENTES = (\{.*?\});", salida, re.S).group(1))
    assert set(agentes) == {"rama_a", "rama_b"}
    # Orden alfabetico estable: rama_a primero, luego rama_b.
    assert agentes["rama_a"]["c"] == viz._COLOR_AGENTE[0]
    assert agentes["rama_b"]["c"] == viz._COLOR_AGENTE[1]
    assert agentes["rama_a"]["fuera"] == 2

    nodos = _json.loads(re.search(r"const NODOS = (\[.*?\]), ARISTAS", salida, re.S).group(1))
    store = [n for n in nodos if n["id"] == "app.store"][0]
    assert store["ag"] == ["rama_b", "rama_a"]
    resto = [n for n in nodos if n["id"] != "app.store"]
    assert all(n["ag"] == [] for n in resto)


def test_sin_actividad_el_mapa_no_inventa_agentes(tmp_path):
    import json as _json
    import re

    from galaxybrain import symbols

    root = _proyecto(tmp_path)
    salida = viz.render_graph_cloud(symbols.analyze(root))
    agentes = _json.loads(re.search(r"const AGENTES = (\{.*?\});", salida, re.S).group(1))
    assert agentes == {}


def test_del_quinto_agente_en_adelante_comparten_color(tmp_path):
    """No se genera el color 9: mas alla de la paleta validada, tono neutro y el
    nombre lo dice la consola."""
    import json as _json
    import re

    from galaxybrain import symbols

    root = _proyecto(tmp_path)
    act = {
        "base": "abc1234",
        "agentes": [
            {"nombre": "r%d" % i, "nodos": [], "vecinos": [], "hace_seg": 1,
             "fuera_del_mapa": 0, "base": "abc1234", "misma_base": True}
            for i in range(6)
        ],
        "por_nodo": {},
        "cruces": [],
    }
    salida = viz.render_graph_cloud(symbols.analyze(root), actividad=act)
    agentes = _json.loads(re.search(r"const AGENTES = (\{.*?\});", salida, re.S).group(1))
    colores = [agentes["r%d" % i]["c"] for i in range(6)]
    assert colores[:4] == viz._COLOR_AGENTE
    assert colores[4] == viz._COLOR_AGENTE_EXTRA
    assert colores[5] == viz._COLOR_AGENTE_EXTRA


def test_la_leyenda_lista_cada_agente_vivo_con_su_color(tmp_path):
    """La marca mas nueva del mapa no puede ser la unica sin explicar.

    Cada agente vivo sale en la leyenda con SU color y la marca del lienzo (aro
    solido); la entrada del aro blanco (2+ a la vez) solo existe cuando hay dos
    o mas agentes — una leyenda que explica marcas imposibles tambien miente.
    """
    from galaxybrain import symbols

    root = _proyecto(tmp_path)
    base = {"nodos": [], "vecinos": [], "hace_seg": 1, "fuera_del_mapa": 0,
            "base": "abc1234", "misma_base": True}
    act1 = {"base": "abc1234", "agentes": [dict(base, nombre="rama_a")],
            "por_nodo": {}, "cruces": []}
    act2 = {"base": "abc1234",
            "agentes": [dict(base, nombre="rama_a"), dict(base, nombre="rama_b")],
            "por_nodo": {}, "cruces": []}
    informe = symbols.analyze(root)

    con_uno = viz.render_graph_cloud(informe, actividad=act1)
    assert '<i class="agente" style="color:%s"></i>rama_a' % viz._COLOR_AGENTE[0] in con_uno
    assert "2+ a la vez" not in con_uno          # con un agente no hay cruce posible

    con_dos = viz.render_graph_cloud(informe, actividad=act2)
    assert '<i class="agente" style="color:%s"></i>rama_b' % viz._COLOR_AGENTE[1] in con_dos
    assert "2+ a la vez" in con_dos

    sin_agentes = viz.render_graph_cloud(informe)
    assert 'class="agente"' not in sin_agentes   # sin agentes, la entrada no existe


def test_el_nombre_de_un_agente_no_inyecta_html(tmp_path):
    """El nombre viene del sistema de ficheros: se escapa, no se confia."""
    from galaxybrain import symbols

    act = {"base": "x", "agentes": [
        {"nombre": "<img src=x>", "nodos": [], "vecinos": [], "hace_seg": 1,
         "fuera_del_mapa": 0, "base": "x", "misma_base": True}],
        "por_nodo": {}, "cruces": []}
    salida = viz.render_graph_cloud(symbols.analyze(_proyecto(tmp_path)), actividad=act)
    assert "<img src=x>" not in salida
    assert "&lt;img src=x>" in salida


def test_un_docstring_con_cierre_de_script_no_rompe_la_pagina(tmp_path):
    """La misma exposicion que el nombre del agente, pero preexistente: los
    docstrings viajan en el payload de nodos, y uno que contenga '</script>'
    cerraria la etiqueta y ejecutaria lo que venga detras como HTML."""
    from galaxybrain import symbols

    root = str(tmp_path)
    _write(root, "app/__init__.py", "")
    _write(root, "app/veneno.py",
           '"""Doc con </script><b>html</b> dentro."""\n\n\ndef f():\n    return 1\n')
    salida = viz.render_graph_cloud(symbols.analyze(root))
    cuerpo = salida[salida.index("const NODOS"):]
    assert "</script><b>" not in cuerpo
    assert "\u003c/script>" in cuerpo


def test_la_tarjeta_del_agente_vive_en_el_nodo_no_en_un_panel(tmp_path):
    """El panel de agentes se retiro (6-ago): tarjeta y terminal son UNA pieza
    anclada al nodo del agente. El contenedor de tarjetas viaja siempre (el JS
    lo llena solo si hay agentes); el payload sin actividad llega vacio, asi
    que no puede inventarse un roster."""
    import json as _json
    import re

    from galaxybrain import symbols

    salida = viz.render_graph_cloud(symbols.analyze(_proyecto(tmp_path)))
    assert '<div id="agentes"></div>' not in salida
    assert '<div id="terminales"></div>' in salida
    agentes = _json.loads(re.search(r"const AGENTES = (\{.*?\});", salida, re.S).group(1))
    assert agentes == {}


def test_la_senal_de_sinapsis_solo_se_explica_cuando_puede_existir(tmp_path):
    """La entrada de la señal fluye solo aparece con agentes vivos: sin agentes
    no hay sinapsis que explicar, y una leyenda que explica marcas imposibles
    tambien miente."""
    from galaxybrain import symbols

    informe = symbols.analyze(_proyecto(tmp_path))
    act = {"base": "x", "agentes": [
        {"nombre": "r1", "nodos": ["app.store"], "vecinos": [], "hace_seg": 1,
         "fuera_del_mapa": 0, "base": "x", "misma_base": True}],
        "por_nodo": {"app.store": {"agentes": ["r1"], "vecino_de": []}}, "cruces": []}

    con = viz.render_graph_cloud(informe, actividad=act)
    assert "fluyendo hacia su onda" in con

    sin = viz.render_graph_cloud(informe)
    assert "fluyendo hacia su onda" not in sin

def test_los_cambios_del_agente_viajan_al_payload(tmp_path):
    """La consola necesita el hecho para el evento `escribe` con sustancia."""
    from galaxybrain import symbols

    root = _proyecto(tmp_path)
    act = {"base": "abc1234", "por_nodo": {}, "cruces": [], "agentes": [{
        "nombre": "rama_a", "nodos": [], "vecinos": [], "hace_seg": 1,
        "fuera_del_mapa": 0, "base": "abc1234", "misma_base": True,
        "cambios": ["lib.nucleo.suma: (a, b) -> (a, b, extra)"],
    }]}
    salida = viz.render_graph_cloud(symbols.analyze(root), actividad=act)
    assert '"cambios": ["lib.nucleo.suma: (a, b) -> (a, b, extra)"]' in salida


def test_la_consola_del_agente_viaja_al_payload_y_hay_terminal(tmp_path):
    """La terminal del lienzo muestra el stdout del agente; sin consola en el
    payload no habria nada que anclar encima de sus nodos."""
    from galaxybrain import symbols

    root = _proyecto(tmp_path)
    act = {"base": "abc1234", "por_nodo": {}, "cruces": [], "agentes": [{
        "nombre": "rama_a", "nodos": [], "vecinos": [], "hace_seg": 1,
        "fuera_del_mapa": 0, "base": "abc1234", "misma_base": True,
        "consola": ["[02:13:05] > Edit lib/nucleo.py"],
    }]}
    salida = viz.render_graph_cloud(symbols.analyze(root), actividad=act)
    assert '"consola": ["[02:13:05] > Edit lib/nucleo.py"]' in salida
    assert 'id="terminales"' in salida
    assert "parpadeo" in salida


def test_el_mapa_sobrevive_al_navegador_releyendo(monkeypatch):
    """WinError 32: con --refresco el navegador mantiene el fichero abierto un
    instante y el rename atomico choca — paso DOS veces el 6-ago-2026, cada una
    una regeneracion entera perdida. El escritor reintenta la ventana."""
    intentos = []

    def falla_dos_veces(a, b):
        intentos.append(1)
        if len(intentos) < 3:
            raise OSError(32, "sharing violation")

    monkeypatch.setattr(os, "replace", falla_dos_veces)
    monkeypatch.setattr(cli.time, "sleep", lambda s: None)
    cli._reemplaza_html("a.tmp", "a.html")
    assert len(intentos) == 3


def test_si_la_ventana_no_se_cierra_el_error_sube(monkeypatch):
    """Tres intentos y a decirlo: un reintento infinito seria esconder el fallo."""
    import pytest

    def siempre_falla(a, b):
        raise OSError(32, "sharing violation")

    monkeypatch.setattr(os, "replace", siempre_falla)
    monkeypatch.setattr(cli.time, "sleep", lambda s: None)
    with pytest.raises(OSError):
        cli._reemplaza_html("a.tmp", "a.html")


def test_las_capturas_y_el_suelo_viajan_al_mapa(tmp_path):
    """El grafo como superficie unica: la consola de errores (feed `peta`) y
    el suelo de floor (cabecera) entran al mapa por defecto."""
    from galaxybrain import symbols

    salida = viz.render_graph_cloud(
        symbols.analyze(_proyecto(tmp_path)),
        capturas=[{"id": "abc12345", "ts": "", "tipo": "KeyError",
                   "donde": "x.py:3", "nodo": "app.store", "leida": False}],
        suelo="5/8 capas")
    assert "const CAPTURAS" in salida and '"tipo": "KeyError"' in salida
    assert "suelo: 5/8 capas" in salida


def test_sin_capturas_ni_suelo_el_mapa_calla(tmp_path):
    from galaxybrain import symbols

    salida = viz.render_graph_cloud(symbols.analyze(_proyecto(tmp_path)))
    assert "const CAPTURAS = [];" in salida
    assert "suelo:" not in salida
