"""Grupos en `.gb-boundaries`, y las candidatas que el grafo propone.

Las dos piezas atacan el mismo problema, que es el riesgo real de esta capa: si
declarar fronteras cuesta trabajo, no se declaran, y un gate sin reglas no
comprueba nada. La ley de ESTE repo eran **45 líneas que decían una sola cosa**
—«el núcleo no importa la presentación»— escritas a mano como producto cartesiano
de 15×3. Con ese coste, un módulo nuevo entra sin regla y nadie se entera.

El grupo es azúcar y se expande al parsear, así que de ahí hacia abajo todo el
sistema sigue viendo pares y no hay una segunda semántica que mantener.
"""

import os

from galaxybrain import graph


def _write(root, contenido, nombre=".gb-boundaries"):
    ruta = os.path.join(root, nombre)
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write(contenido)
    return ruta


# --- grupos ------------------------------------------------------------------


def test_un_grupo_se_expande_al_producto(tmp_path):
    root = str(tmp_path)
    _write(root, "BASE = a, b\nBORDE = x, y\nBASE -/-> BORDE\n")

    d = graph.load_boundaries(root)

    assert set(d["rules"]) == {("a", "x"), ("a", "y"), ("b", "x"), ("b", "y")}
    assert not d["malformed"]


def test_las_dos_formas_conviven(tmp_path):
    """Un nombre que no es grupo se queda tal cual: se puede mezclar."""
    root = str(tmp_path)
    _write(root, "BASE = a, b\nBASE -/-> web\nsuelto -/-> otro\n")

    assert set(graph.load_boundaries(root)["rules"]) == {
        ("a", "web"), ("b", "web"), ("suelto", "otro")}


def test_un_grupo_contra_si_mismo_no_acusa_a_sus_miembros(tmp_path):
    """`X -/-> X` diria que `a` no puede importar `a`: un par consigo mismo no es
    una frontera, y dejarlo pasar llenaria el informe de ruido."""
    root = str(tmp_path)
    _write(root, "X = a, b\nX -/-> X\n")

    assert set(graph.load_boundaries(root)["rules"]) == {("a", "b"), ("b", "a")}


def test_un_grupo_vacio_es_malformado(tmp_path):
    """Enforced nada, así que se avisa en vez de descartarse mudo."""
    root = str(tmp_path)
    _write(root, "BASE =\n")

    d = graph.load_boundaries(root)

    assert d["rules"] == [] and d["malformed"] == ["BASE ="]


def test_un_grupo_no_es_por_si_solo_una_regla(tmp_path):
    """Definir el grupo no comprueba nada: hace falta la línea con la flecha."""
    root = str(tmp_path)
    _write(root, "BASE = a, b\n")

    d = graph.load_boundaries(root)

    assert d["rules"] == [] and not d["malformed"]


def test_la_superficie_sigue_leyendose_con_grupos_delante(tmp_path):
    """El `=` no puede comerse las otras dos formas del fichero."""
    root = str(tmp_path)
    _write(root, "BASE = a\napp.store :: load, save\nBASE -/-> web\n")

    d = graph.load_boundaries(root)

    assert d["surfaces"] == [("app.store", ("load", "save"))]
    assert d["rules"] == [("a", "web")]


# --- candidatas propuestas ---------------------------------------------------


def _informe(fan_in, fan_out, aristas):
    return {"fan_in": fan_in, "fan_out": fan_out, "edge_list": aristas}


def test_propone_de_la_base_al_borde():
    """Estable (la importan, no importa) -/-> inestable (importa, no la importan)."""
    p = graph.proponer_fronteras(
        _informe({"nucleo": 3, "util": 2}, {"cli": 2, "main": 2},
                 [["cli", "nucleo"], ["cli", "util"], ["main", "nucleo"], ["main", "util"]]))

    assert set(p["nucleo"]) == {"nucleo", "util"}
    assert set(p["entrada"]) == {"cli", "main"}
    assert {(x["src"], x["dst"]) for x in p["pares"]} == {
        ("nucleo", "cli"), ("nucleo", "main"), ("util", "cli"), ("util", "main")}


def test_NO_propone_una_dependencia_que_YA_existe():
    """Lo que ya se cruza es deuda, no una frontera: proponerlo seria pedir un
    commit roto el mismo dia que pegas el fichero."""
    p = graph.proponer_fronteras(
        _informe({"nucleo": 3, "util": 2}, {"cli": 2, "nucleo": 1},
                 [["cli", "nucleo"], ["cli", "util"], ["nucleo", "cli"]]))

    assert ("nucleo", "cli") not in {(x["src"], x["dst"]) for x in p["pares"]}


def test_marca_las_que_ya_tenias_escritas():
    """El control positivo de la derivacion: si redescubre reglas que escribiste
    a mano, esta encontrando la forma de verdad y no un artefacto."""
    p = graph.proponer_fronteras(
        _informe({"nucleo": 3, "util": 2}, {"cli": 2, "main": 2},
                 [["cli", "nucleo"], ["cli", "util"], ["main", "nucleo"], ["main", "util"]]),
        declaradas=[("nucleo", "cli")])

    marcadas = {(x["src"], x["dst"]) for x in p["pares"] if x["ya_declarada"]}
    assert marcadas == {("nucleo", "cli")}


def test_un_grafo_sin_forma_no_inventa_candidatas():
    """Sin base ni borde no hay nada que proponer, y se dice por que en vez de
    devolver una lista vacia que se lee como "esta todo bien"."""
    p = graph.proponer_fronteras(_informe({"a": 1, "b": 1}, {"a": 1, "b": 1},
                                          [["a", "b"], ["b", "a"]]))

    assert p["pares"] == [] and p["motivo"]


def test_un_repo_diminuto_no_da_candidatas():
    p = graph.proponer_fronteras(_informe({"a": 1}, {"b": 1}, [["b", "a"]]))

    assert p["pares"] == [] and p["motivo"]
