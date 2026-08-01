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
