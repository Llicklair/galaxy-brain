"""Aristas declaradas (`A => B`): el hecho que el codigo no confiesa.

El grafo se DERIVA, nunca se declara (ADR 0001) — pero solo puede derivar lo que
esta escrito en un import. Un repo mixto llama a su servicio en Go por HTTP, a un
worker por subprocess, a otro modulo por CLI: dependencias reales, invisibles para
cualquier analizador estatico, y por tanto ausentes de los ciclos, del fan-in, de
la seleccion de tests y del mapa. `=>` las escribe A MANO en `.gb-boundaries`, y
desde ahi son aristas de primera clase como cualquier otra.

Lo declarado no compite con lo derivado: se suma antes de calcular nada. Y se
escribe `=>` y no `-->` a proposito — ver el test del typo al final.
"""

import os

import pytest

from galaxybrain import graph


def _write(root, rel, content):
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def _proyecto(root, fronteras):
    """Dos modulos Python que NO se importan entre si. Todo lo que aparezca
    entre ellos viene de lo declarado, nunca del analisis."""
    _write(root, "app/__init__.py", "")
    _write(root, "app/web.py", "")
    _write(root, "app/db.py", "")
    _write(root, ".gb-boundaries", fronteras)
    return root


def _aristas(report):
    return {tuple(e) for e in report["edge_list"]}


def test_la_arista_declarada_entra_en_el_grafo(tmp_path):
    root = _proyecto(str(tmp_path), "app.web => app.db\n")
    report = graph.analyze(root)

    assert ("app.web", "app.db") in _aristas(report)
    assert report["fan_out"]["app.web"] == 1
    assert report["fan_in"]["app.db"] == 1
    assert not report["malformed_boundaries"]


def test_un_destino_que_no_es_python_existe_como_nodo(tmp_path):
    """El caso que lo motiva: el otro lado de la dependencia esta en Go, en JS o
    detras de un HTTP, y no hay fichero que analizar. Si la arista apuntara a un
    nodo inexistente, el mapa dibujaria una flecha al vacio."""
    root = _proyecto(str(tmp_path), "app.web => svc.pagos\n")
    report = graph.analyze(root)

    assert ("app.web", "svc.pagos") in _aristas(report)
    assert report["fan_in"]["svc.pagos"] == 1


def test_lo_declarado_cierra_ciclos_y_el_gate_los_ve(tmp_path):
    """La razon de inyectarlas ANTES de calcular: un ciclo que solo existe
    pasando por la dependencia invisible es un ciclo igual. Si se sumaran
    despues, el gate diria 'sin ciclos' sobre un grafo que si los tiene."""
    root = str(tmp_path)
    _write(root, "app/__init__.py", "")
    _write(root, "app/web.py", "from app import db\n")
    _write(root, "app/db.py", "")
    _write(root, ".gb-boundaries", "app.db => app.web\n")   # cierra el circulo

    report = graph.analyze(root)
    assert report["cycles"], "el ciclo web->db->web no aparece"

    from galaxybrain import cli
    assert cli.main(["graph", root, "--gate", "--color", "never"]) == 1


def test_las_fronteras_gobiernan_lo_declarado(tmp_path):
    """Declarar una dependencia no la exime de la ley. Si estuviera exenta,
    `=>` seria la puerta de atras para saltarse cualquier frontera."""
    root = _proyecto(str(tmp_path), "app.web => app.db\napp.web -/-> app.db\n")
    report = graph.analyze(root)

    assert ("app.web", "app.db") in [
        (v["importer"], v["imported"]) for v in report["violations"]]


def test_los_grupos_se_expanden_igual_que_en_las_reglas(tmp_path):
    """Una segunda semantica de grupos seria una segunda cosa que mantener."""
    root = str(tmp_path)
    _write(root, "app/__init__.py", "")
    for mod in ("web", "api", "db"):
        _write(root, "app/%s.py" % mod, "")
    _write(root, ".gb-boundaries", "ENTRADAS = app.web, app.api\nENTRADAS => app.db\n")

    aristas = _aristas(graph.analyze(root))
    assert ("app.web", "app.db") in aristas
    assert ("app.api", "app.db") in aristas


def test_sin_fichero_de_fronteras_no_se_inventa_ninguna(tmp_path):
    root = str(tmp_path)
    _write(root, "app/__init__.py", "")
    _write(root, "app/web.py", "")
    assert _aristas(graph.analyze(root)) == set()


def test_un_lado_vacio_es_malformed_no_mudo(tmp_path):
    root = _proyecto(str(tmp_path), "app.web =>\n")
    report = graph.analyze(root)

    assert "app.web =>" in report["malformed_boundaries"]
    assert _aristas(report) == set()


def test_el_typo_de_la_frontera_no_declara_la_dependencia_contraria(tmp_path):
    """POR QUE el token es `=>` y no `-->`.

    `-->` se obtiene borrando la barra de `-/->`. Con `-->` como arista declarada,
    ese typo de UN caracter no avisaba: convertia "app.web no puede importar
    app.db" en "app.web importa app.db" — la dependencia contraria a la que se
    queria prohibir, y el gate pasando en verde. Dos cosas opuestas no pueden
    diferenciarse en un caracter (regla 9), asi que `-->` sigue siendo malformed.
    """
    root = _proyecto(str(tmp_path), "app.web --> app.db\n")
    report = graph.analyze(root)

    assert "app.web --> app.db" in report["malformed_boundaries"]
    assert _aristas(report) == set()
    assert report["boundaries"] == 0


def test_un_fichero_que_solo_declara_aristas_no_bloquea_el_gate_de_otra_carpeta(tmp_path):
    """El layout de este repo: `src/.gb-boundaries` gatea el paquete y el de la
    raiz declara las dependencias invisibles del arbol entero.

    La salvaguarda de 'hay DOS ficheros de reglas' bloquea (exit 1) porque un
    fichero sin aplicar promete una comprobacion que no se hace. Pero `=>` no
    promete ninguna: describe el grafo, no lo vigila. Bloquear ahi fabrica el
    falso positivo que acaba en `--no-verify` — lo que la salvaguarda venia a
    evitar. Con reglas de verdad (`-/->`) sigue bloqueando: ver el test de al lado.
    """
    from galaxybrain import cli

    root = str(tmp_path)
    _write(root, "src/app/__init__.py", "")
    _write(root, "src/app/web.py", "")
    _write(root, "src/app/db.py", "")
    _write(root, "src/.gb-boundaries", "app.web -/-> app.db\n")
    _write(root, ".gb-boundaries", "tests.humo => app.web\n")   # solo declara

    assert cli.main(["graph", os.path.join(root, "src"), "--gate", "--color", "never"]) == 0


def test_pero_una_REGLA_sin_aplicar_sigue_bloqueando(tmp_path):
    """El control del test de arriba. Lo que se afina es el criterio, no se
    apaga la salvaguarda: un `-/->` que crees activo y no lo esta es protección
    que no tienes, y eso sigue siendo exit 1."""
    from galaxybrain import cli

    root = str(tmp_path)
    _write(root, "src/app/__init__.py", "")
    _write(root, "src/app/web.py", "")
    _write(root, "src/app/db.py", "")
    _write(root, "src/.gb-boundaries", "app.web -/-> app.db\n")
    _write(root, ".gb-boundaries", "app.web -/-> app.otra\n")   # REGLA sin aplicar

    assert cli.main(["graph", os.path.join(root, "src"), "--gate", "--color", "never"]) == 1


def test_el_nodo_cross_language_llega_al_mapa(tmp_path):
    """El mapa lee `edge_list`, pero sus nodos salen del informe de SIMBOLOS, que
    no sabe nada de un modulo en Go. Sin inyectarlo, la arista apunta a un nodo
    que no existe en el lienzo."""
    viz = pytest.importorskip("galaxybrain.viz")
    from galaxybrain import symbols

    root = _proyecto(str(tmp_path), "app.web => svc.pagos\n")
    html = viz.render_graph_cloud(
        symbols.analyze(root), graph_report=graph.analyze(root), gen_ts=0,
    )
    assert "svc.pagos" in html
