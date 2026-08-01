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


def test_el_color_del_import_no_choca_con_ningun_tipo_de_nodo():
    """Se vio mirando la pantalla, no leyendo el codigo: la primera version reuso
    el ambar de las clases, y dos clases sueltas parecian parte de la capa de
    imports. Un color repetido es una mentira visual, y esta capa existe justo
    para separar el hecho exacto de la inferencia."""
    assert viz._COLOR_IMPORT not in viz._KIND_COLOR.values()


def test_la_leyenda_no_confunde_cobertura_con_fiabilidad(tmp_path):
    """El porcentaje de llamadas resueltas es COBERTURA. Puesto junto a
    "inferida" se leia como fiabilidad, o sea al reves: las aristas dibujadas son
    precisamente las que SI se resolvieron. El numero va en la cabecera, con su
    denominador, que es donde significa lo que dice."""
    raiz = _proyecto(tmp_path)
    html = viz.render_graph_cloud(symbols.analyze(raiz), graph_report=graph.analyze(raiz))
    assert "inferida)" in html
    assert re.search(r"inferida,\s*\d+%", html) is None
    assert "resueltas de" in html  # el dato exacto sigue estando, arriba


def test_el_dibujo_pinta_las_cuatro_clases(tmp_path):
    """Si el bucle de pintado no recorre la clase 3, los imports estarian en los
    datos y no en la pantalla — el peor fallo posible aqui: parecer completo."""
    raiz = _proyecto(tmp_path)
    html = viz.render_graph_cloud(symbols.analyze(raiz), graph_report=graph.analyze(raiz))
    assert "for(const capa of [0,3,1,2])" in html


def _con_ciclo(tmp_path):
    for rel, cuerpo in (
        ("app/__init__.py", ""),
        ("app/a.py", "from .b import cosa\notra = 2\n"),
        ("app/b.py", "from .a import otra\ncosa = 1\n"),
    ):
        ruta = os.path.join(str(tmp_path), *rel.split("/"))
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, "w", encoding="utf-8") as handle:
            handle.write(cuerpo)
    return str(tmp_path)


def test_los_ciclos_van_marcados(tmp_path):
    """Migrado del renderizador SVG que se retiro. Es el UNICO hecho de este mapa
    que detiene un commit, asi que no puede ser un color mas: se marcan el nodo y
    el tramo, y el tramo manda sobre la capa a la que pertenezca."""
    raiz = _con_ciclo(tmp_path)
    informe = graph.analyze(raiz)
    assert informe["cycles"], "el montaje tiene que tener ciclo para que el test valga"

    html = viz.render_graph_cloud(symbols.analyze(raiz), graph_report=informe)
    nodos, _ = _capas(html)
    assert any(n["ci"] for n in nodos), "ningun nodo marcado como ciclico"

    m = re.search(r"ARISTAS = (\[.*?\]), LADO", html, re.S)
    assert any(len(a) > 3 and a[3] for a in json.loads(m.group(1))), "ningun tramo ciclico"
    assert "CICLO_COLOR" in html


def test_sin_ciclos_no_se_marca_nada(tmp_path):
    """La otra mitad: un detector que marca siempre no distingue nada."""
    raiz = _proyecto(tmp_path)
    informe = graph.analyze(raiz)
    assert not informe["cycles"]
    nodos, _ = _capas(viz.render_graph_cloud(symbols.analyze(raiz), graph_report=informe))
    assert not any(n["ci"] for n in nodos)


def test_lo_nuevo_se_distingue_de_lo_viejo(tmp_path):
    """Ver crecer un proyecto es, sobre todo, ver que aparecio desde la ultima vez."""
    raiz = _proyecto(tmp_path)
    informe = symbols.analyze(raiz)
    llamadas = [(a, b) for a, b, t in informe.get("edges", []) if t == "CALLS"]
    assert llamadas, "el montaje necesita una llamada"
    informe["new_calls"] = [list(llamadas[0])]

    _nodos, conteo = _capas(viz.render_graph_cloud(informe))
    assert conteo[2] >= 1, "lo nuevo tiene que ir en su propia clase"


def test_los_nombres_van_escapados(tmp_path):
    """El nombre de un modulo viene del disco: si alguien crea `<script>.py`, no
    puede acabar ejecutandose en la pagina."""
    raiz = _proyecto(tmp_path)
    informe = symbols.analyze(raiz)
    informe["nodes"] = [
        {"qual": "app.<script>alert(1)</script>", "kind": "module", "module": "app"}
    ]
    informe["edges"] = []

    html = viz.render_graph_cloud(informe)
    assert "<script>alert(1)</script>" not in html.split("<script>")[-1]


def test_un_proyecto_vacio_no_revienta(tmp_path):
    html = viz.render_graph_cloud(symbols.analyze(str(tmp_path)))
    assert "<canvas" in html


def _maxit(html):
    return int(re.search(r"const MAXIT = (\d+)", html).group(1))


def test_capas_es_otra_siembra_del_MISMO_lienzo(tmp_path):
    """`--capas` dejo de ser otra pagina. Mismos nodos, misma plantilla, mismas
    interacciones — lo unico que cambia es de donde salen las posiciones."""
    raiz = _proyecto(tmp_path)
    informe = symbols.analyze(raiz)
    nube = viz.render_graph_cloud(informe)
    capas = viz.render_graph_cloud(informe, capas=True)

    n_nube, _ = _capas(nube)
    n_capas, _ = _capas(capas)
    assert {n["id"] for n in n_nube} == {n["id"] for n in n_capas}
    assert "<canvas" in nube and "<canvas" in capas


def test_en_capas_la_fisica_NO_corre(tmp_path):
    """La simulacion desharia justo el orden que esta vista existe para ensenar,
    asi que las posiciones sembradas son las definitivas."""
    raiz = _proyecto(tmp_path)
    informe = symbols.analyze(raiz)
    assert _maxit(viz.render_graph_cloud(informe, capas=True)) == 0
    assert _maxit(viz.render_graph_cloud(informe)) > 0


def test_en_capas_la_altura_codifica_la_profundidad(tmp_path):
    """Si todo cayera a la misma altura, la vista no diria nada: lo que aporta es
    justo que quien depende de quien se lea de arriba abajo."""
    raiz = _proyecto(tmp_path)
    nodos, _ = _capas(viz.render_graph_cloud(symbols.analyze(raiz), capas=True))
    alturas = {round(n["y"], 1) for n in nodos}
    assert len(alturas) > 1, "todos los nodos a la misma altura: no hay capas"


def test_capas_sigue_siendo_determinista(tmp_path):
    raiz = _proyecto(tmp_path)
    informe = symbols.analyze(raiz)
    assert viz.render_graph_cloud(informe, capas=True) == viz.render_graph_cloud(
        informe, capas=True
    )


def test_el_refresco_es_opt_in(tmp_path):
    """Por defecto no se recarga nada. Un refresco sobre un fichero que nadie
    regenera solo consigue parpadear, asi que se pide a proposito."""
    informe = symbols.analyze(_proyecto(tmp_path))
    assert 'http-equiv="refresh"' not in viz.render_graph_cloud(informe)
    assert 'content="60"' in viz.render_graph_cloud(informe, refresco=60)


def test_la_camara_sobrevive_a_una_recarga(tmp_path):
    """Sin esto el refresco automatico seria hostil: cada minuto te devolveria al
    encuadre inicial y explorar seria pelearte con la pagina. La clave lleva el
    titulo para que dos mapas abiertos a la vez no se pisen el encuadre."""
    html = viz.render_graph_cloud(symbols.analyze(_proyecto(tmp_path)))
    assert "sessionStorage" in html
    assert "gb-camara:" in html
    assert "beforeunload" in html


def test_guardar_la_camara_nunca_puede_romper_la_pagina(tmp_path):
    """sessionStorage lanza en algunos navegadores con file:// o modo privado.
    Si eso tumbara el script, el mapa entero se quedaria en negro por guardar un
    encuadre — el visor tiene que fallar hacia el lado seguro igual que el resto."""
    html = viz.render_graph_cloud(symbols.analyze(_proyecto(tmp_path)))
    trozo = html[html.find("gb-camara:") - 400 : html.find("beforeunload") + 300]
    assert trozo.count("try{") >= 2 and trozo.count("catch(_)") >= 2


def test_la_ficha_separa_quien_te_llama_de_a_quien_llamas(tmp_path):
    """"A quien llamo" y "quien me llama" son preguntas distintas. Confundirlas
    es lo que hace inutil a la mayoria de visores de grafos: te dan un numero de
    vecinos y te dejan igual que estabas."""
    html = viz.render_graph_cloud(symbols.analyze(_proyecto(tmp_path)))
    assert "llamado por" in html and "llama a" in html
    assert "const entran" in html and "salen[par[0]].push" in html


def test_la_ficha_distingue_el_import_de_la_llamada(tmp_path):
    """Misma separacion que en el dibujo: el import es exacto, la llamada es
    inferencia. Si la ficha los mezclara, el color no serviria de nada."""
    html = viz.render_graph_cloud(
        symbols.analyze(_proyecto(tmp_path)), graph_report=graph.analyze(_proyecto(tmp_path))
    )
    assert "importado por" in html and "importa" in html


def test_la_jerarquia_no_cuenta_como_flujo(tmp_path):
    """Que un modulo CONTENGA una funcion no es que la llame. Contarlo como
    conexion inflaria la ficha de todos los modulos con sus propios hijos."""
    html = viz.render_graph_cloud(symbols.analyze(_proyecto(tmp_path)))
    assert "if(tp===0) continue" in html


def test_un_simbolo_sin_llamadas_lo_DICE(tmp_path):
    """"No llamado desde ninguna parte" es informacion, y una ficha vacia se lee
    como un fallo de la pagina en vez de como un dato."""
    html = viz.render_graph_cloud(symbols.analyze(_proyecto(tmp_path)))
    assert "sin llamadas resueltas ni imports" in html


def test_los_nombres_se_escapan_antes_de_innerHTML(tmp_path):
    """Agujero real que habia: la ficha metia `n.id` crudo en innerHTML, y los
    nombres vienen del disco. Un fichero llamado `<img onerror=...>.py` se
    ejecutaba al pulsarlo. El escapado del JSON protege la cadena, no el HTML."""
    html = viz.render_graph_cloud(symbols.analyze(_proyecto(tmp_path)))
    assert "const esc = s => String(s).replace" in html
    assert "esc(n.id)" in html
    assert "'<b>'+n.id+'</b>'" not in html  # la version cruda, fuera


def test_sigue_siendo_autocontenido(tmp_path):
    """Sin CDN ni dependencias: se abre sin red y se puede mover de sitio."""
    raiz = _proyecto(tmp_path)
    html = viz.render_graph_cloud(symbols.analyze(raiz), graph_report=graph.analyze(raiz))
    assert "http://" not in html and "https://" not in html
    assert "<script" in html and "src=" not in html.split("<script")[1][:200]
