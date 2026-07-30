"""El mapa en imagen. La propiedad que importa NO es que sea bonito: es que dos
ejecuciones del mismo grafo den el mismo fichero.

Si las posiciones bailan entre ejecuciones, dos capturas del mismo proyecto no se
pueden comparar — y comparar es justamente para lo que uno mira crecer un proyecto.
Un layout de fuerzas queda mejor y no cumple esto.
"""

import os

from galaxybrain import cli, graph, viz


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


def test_el_mismo_grafo_da_el_mismo_fichero(tmp_path):
    """La propiedad central: determinismo. Sin esto, 'ver crecer el proyecto' es
    ver bailar las cajas."""
    root = _proyecto(tmp_path)

    primero = viz.render_html(graph.analyze(root))
    segundo = viz.render_html(graph.analyze(root))

    assert primero == segundo


def test_pinta_todos_los_modulos_y_todas_las_aristas(tmp_path):
    """Un mapa que se deja cosas fuera miente sobre la forma del proyecto."""
    root = _proyecto(tmp_path)
    report = graph.analyze(root)

    salida = viz.render_html(report)

    assert salida.count('<g class="nodo') == report["modules"]
    assert salida.count('<path class="arista') == report["edges"]


def test_no_pide_nada_a_la_red(tmp_path):
    """Cero dependencias es una regla del proyecto, y un visor no es motivo para
    romperla: ni CDN, ni script externo, ni fuente remota."""
    salida = viz.render_html(graph.analyze(_proyecto(tmp_path)))

    for prohibido in ('src="http', 'href="http', "cdn.", "googleapis", "unpkg"):
        assert prohibido not in salida


def test_los_ciclos_van_marcados(tmp_path):
    """Es el unico hecho del mapa que exige una decision, asi que se ve."""
    root = str(tmp_path)
    _write(root, "app/__init__.py", "")
    _write(root, "app/a.py", "from .b import cosa\notra = 2\n")
    _write(root, "app/b.py", "from .a import otra\ncosa = 1\n")

    report = graph.analyze(root)
    assert report["cycles"], "el montaje tiene que tener ciclo para que el test valga"

    salida = viz.render_html(report)
    assert 'class="nodo ciclo"' in salida
    assert "arista ciclica" in salida


def test_lo_nuevo_se_distingue_de_lo_viejo(tmp_path):
    """Ver crecer un proyecto es, sobre todo, ver que apareció desde la ultima vez."""
    report = graph.analyze(_proyecto(tmp_path))
    report["new_pairs"] = [["app.api", "app.store"]]

    assert "arista nueva" in viz.render_html(report)


def test_un_proyecto_vacio_no_revienta(tmp_path):
    salida = viz.render_html(graph.analyze(str(tmp_path)))
    assert "<svg" in salida


def test_los_nombres_van_escapados(tmp_path):
    """El nombre de un modulo viene del disco: si alguien crea `<script>.py`, no
    puede acabar ejecutandose en la pagina."""
    report = graph.analyze(str(tmp_path))
    report["fan_in"] = {'app.<script>alert(1)</script>': 0}
    report["edge_list"] = []

    salida = viz.render_html(report)
    assert "<script>alert(1)</script>" not in salida.split("<script>")[-1]
    assert "&lt;script&gt;" in salida


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
    assert "<svg" in open(destino, encoding="utf-8").read()


def test_un_destino_imposible_no_pasa_por_bueno(tmp_path):
    root = _proyecto(tmp_path)
    destino = os.path.join(root, "no-existe", "sub", "mapa.html")

    assert cli.main(["graph", root, "--html", destino, "--color", "never"]) == 2
