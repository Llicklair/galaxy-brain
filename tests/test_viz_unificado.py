"""Un solo grafo: modulos, simbolos, imports y llamadas en el mismo lienzo.

Motivo: `gb graph --html` y `gb symbols --html` producian dos paginas del mismo
sujeto, con CSS y JS duplicados, que habia que juntar de cabeza. Los modulos
SIEMPRE fueron nodos de la nube de simbolos, asi que unificar no exigio inventar
nada: los imports son una clase de arista mas sobre nodos que ya estaban.

Lo que NO se funde son los hechos. El import es exacto y es lo unico que puede
gatear; la llamada es inferencia con 93% de recall. Se dibujan distinto y la
leyenda lo dice, porque mezclarlos en un solo numero acabaria gateando sobre un
proxy (ARCHITECTURE regla 11).
"""

import json
import os
import re

from galaxybrain import graph, symbols, viz


def _proyecto(tmp_path):
    for rel, cuerpo in (
        ("pkg/__init__.py", ""),
        ("pkg/a.py", "from . import b\n\n\ndef llama():\n    return b.g()\n"),
        ("pkg/b.py", "def g():\n    return 2\n"),
    ):
        ruta = os.path.join(str(tmp_path), *rel.split("/"))
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, "w", encoding="utf-8") as handle:
            handle.write(cuerpo)
    return str(tmp_path)


def _capas(html):
    """Las aristas embebidas, contadas por clase: 0 jerarquia, 1 llamada,
    2 llamada nueva, 3 import."""
    m = re.search(r"const NODOS = (\[.*?\]), ARISTAS = (\[.*?\]), LADO", html, re.S)
    nodos, aristas = json.loads(m.group(1)), json.loads(m.group(2))
    conteo = {0: 0, 1: 0, 2: 0, 3: 0}
    for arista in aristas:
        conteo[arista[2]] += 1
    return nodos, conteo


def test_sin_informe_de_grafo_no_hay_aristas_de_import(tmp_path):
    """La unificacion es opt-in: quien pase solo simbolos sigue teniendo lo de antes."""
    raiz = _proyecto(tmp_path)
    _nodos, conteo = _capas(viz.render_graph_cloud(symbols.analyze(raiz)))
    assert conteo[3] == 0


def test_con_los_dos_informes_el_grafo_lo_contiene_todo(tmp_path):
    raiz = _proyecto(tmp_path)
    informe_g = graph.analyze(raiz)
    html = viz.render_graph_cloud(symbols.analyze(raiz), graph_report=informe_g)
    nodos, conteo = _capas(html)

    # Los modulos son nodos de pleno derecho, no un color de fondo.
    assert sum(1 for n in nodos if n["k"] == "module") == informe_g["modules"]
    # Y cada import del analisis esta dibujado: ni uno menos, ni uno inventado.
    assert conteo[3] == informe_g["edges"]
    # Las llamadas siguen ahi: unificar no puede comerse la otra capa.
    assert conteo[1] >= 1


def test_los_imports_unen_nodos_que_ya_existian(tmp_path):
    """Es la razon de que unificar sea barato: no hay nodos nuevos que inventar,
    solo aristas sobre los modulos que la nube ya dibujaba."""
    raiz = _proyecto(tmp_path)
    antes, _ = _capas(viz.render_graph_cloud(symbols.analyze(raiz)))
    despues, _ = _capas(
        viz.render_graph_cloud(symbols.analyze(raiz), graph_report=graph.analyze(raiz))
    )
    assert [n["id"] for n in antes] == [n["id"] for n in despues]


def test_la_leyenda_separa_el_hecho_de_la_inferencia(tmp_path):
    """Un grafo que no dice que mitad es exacta invita a gatear sobre la que no
    se puede gatear. La cobertura tiene que ir EN la imagen."""
    raiz = _proyecto(tmp_path)
    html = viz.render_graph_cloud(symbols.analyze(raiz), graph_report=graph.analyze(raiz))
    assert "import (exacto)" in html
    assert "inferida" in html


def test_el_dibujo_pinta_las_cuatro_clases(tmp_path):
    """Si el bucle de pintado no recorre la clase 3, los imports estarian en los
    datos y no en la pantalla — el peor fallo posible aqui: parecer completo."""
    raiz = _proyecto(tmp_path)
    html = viz.render_graph_cloud(symbols.analyze(raiz), graph_report=graph.analyze(raiz))
    assert "for(const capa of [0,3,1,2])" in html


def test_sigue_siendo_autocontenido(tmp_path):
    """Sin CDN ni dependencias: se abre sin red y se puede mover de sitio."""
    raiz = _proyecto(tmp_path)
    html = viz.render_graph_cloud(symbols.analyze(raiz), graph_report=graph.analyze(raiz))
    assert "http://" not in html and "https://" not in html
    assert "<script" in html and "src=" not in html.split("<script")[1][:200]
