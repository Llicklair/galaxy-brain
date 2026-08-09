"""La superficie pública: encapsulación declarada, comprobada sobre CALLS.

`-/->` mira IMPORTS entre módulos. Se puede respetar cada frontera de import y
aun así llamar a la función interna de otro módulo — la abstracción se rompe al
nivel del SÍMBOLO, y hasta ahora ahí no había regla posible.

`MOD :: sim1, sim2` dice: a MOD se entra llamando a esos símbolos. Como toda
regla de `.gb-boundaries`, es un HECHO porque lo declaraste tú (regla 9); sin
`::`, esto no comprueba nada y no puede dar un falso positivo.

Y la otra mitad, `modulos_sin_regla`, mide la COBERTURA de la ley. Existe por una
razón concreta: automatizar la aceptación de un cambio sobre "cero violaciones"
es fabricar confianza falsa si la zona tocada no tenía reglas. Es el mismo fallo
que una lista de permitidos vacía, a nivel de arquitectura.
"""

import os

from galaxybrain import graph


def _write(root, rel, content=""):
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


# --- el parser: la superficie convive con las fronteras ----------------------


def test_lee_superficies_junto_a_las_fronteras(tmp_path):
    root = str(tmp_path)
    _write(root, ".gb-boundaries",
           "# la ley\n"
           "app.core  -/->  app.web\n"
           "app.store :: load, save\n")

    d = graph.load_boundaries(root)

    assert d["rules"] == [("app.core", "app.web")]
    assert d["surfaces"] == [("app.store", ("load", "save"))]
    assert not d["malformed"]


def test_una_superficie_sin_simbolos_es_malformada(tmp_path):
    """Enforced nada, así que se avisa en vez de descartarse muda."""
    root = str(tmp_path)
    _write(root, ".gb-boundaries", "app.store ::\n")

    d = graph.load_boundaries(root)

    assert d["surfaces"] == []
    assert d["malformed"] == ["app.store ::"]


def test_sin_fichero_no_hay_superficies_ni_error(tmp_path):
    """Opt-in: la regla que no escribes no puede acusarte."""
    d = graph.load_boundaries(str(tmp_path))

    assert d["surfaces"] == [] and d["error"] is None


# --- la comprobacion, sobre CALLS -------------------------------------------


DE_MODULO = {
    "app.store.load": "app.store",
    "app.store.save": "app.store",
    "app.store._interna": "app.store",
    "app.web.handler": "app.web",
    "app.store.helper": "app.store",
}
SUPERFICIE = [("app.store", ("load", "save"))]


def test_entrar_por_un_simbolo_publico_no_es_violacion():
    v = graph.find_surface_violations(
        [("app.web.handler", "app.store.load")], SUPERFICIE, DE_MODULO)

    assert v == []


def test_entrar_por_un_simbolo_interno_SI_lo_es():
    v = graph.find_surface_violations(
        [("app.web.handler", "app.store._interna")], SUPERFICIE, DE_MODULO)

    assert len(v) == 1
    assert v[0]["caller"] == "app.web.handler"
    assert v[0]["callee"] == "app.store._interna"
    assert v[0]["public"] == ["load", "save"]


def test_dentro_del_propio_modulo_nunca_es_violacion():
    """La superficie regula la ENTRADA, no el uso interno. Acusar aquí haría que
    declarar una superficie castigase al módulo que la declara."""
    v = graph.find_surface_violations(
        [("app.store.helper", "app.store._interna")], SUPERFICIE, DE_MODULO)

    assert v == []


def test_un_modulo_sin_superficie_declarada_no_se_toca():
    v = graph.find_surface_violations(
        [("app.store.load", "app.web.handler")], SUPERFICIE, DE_MODULO)

    assert v == []


def test_un_destino_que_no_esta_en_el_grafo_se_ignora():
    """Sin saber a qué módulo pertenece, acusar sería adivinar."""
    v = graph.find_surface_violations(
        [("app.web.handler", "desconocido.cosa")], SUPERFICIE, DE_MODULO)

    assert v == []


# --- la cobertura de la ley --------------------------------------------------


def test_dice_que_modulos_no_menciona_ninguna_regla():
    nodes = {"app.core", "app.web", "app.store", "app.suelto"}
    rules = [("app.core", "app.web")]

    sin = graph.modulos_sin_regla(nodes, rules, SUPERFICIE)

    assert sin == ["app.suelto"]


def test_sin_reglas_no_hay_nada_cubierto():
    """El caso que importa para automatizar: cero violaciones sobre cero reglas
    no es un aprobado, es una ausencia de examen."""
    nodes = {"a", "b"}

    assert graph.modulos_sin_regla(nodes, [], []) == ["a", "b"]


def test_una_regla_cubre_sus_dos_lados():
    nodes = {"app.core", "app.web"}

    assert graph.modulos_sin_regla(nodes, [("app.core", "app.web")], []) == []
