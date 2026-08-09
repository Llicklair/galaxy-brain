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


# --- la frontera cruzada con una LLAMADA, sin import de por medio ------------


REGLAS = [("app.iva", "app.carrito")]
DE_MOD = {
    "app.iva.informe": "app.iva",
    "app.carrito.total": "app.carrito",
    "app.iva.tasa": "app.iva",
    "app.web.handler": "app.web",
}


def test_llamar_al_modulo_prohibido_es_un_cruce():
    """`A -/-> B` promete "A no depende de B", y llamar a B es depender de B. Solo
    se miraban IMPORTS, y hay lenguajes donde se alcanza otro modulo SIN
    importarlo: `crate::b::f()` en Rust, o el mismo paquete en Java y C#.

    Medido en una tirada real (9-ago): un agente escribio
    `crate::carrito::total(items)` dentro de `iva`, con la frontera declarada, y
    el gate respondio "sin cruces de frontera" — un falso verde."""
    v = graph.find_call_violations(
        [("app.iva.informe", "app.carrito.total")], REGLAS, DE_MOD)

    assert len(v) == 1
    assert v[0]["caller"] == "app.iva.informe"
    assert v[0]["rule"] == "app.iva -/-> app.carrito"


def test_la_direccion_permitida_no_se_acusa():
    """`carrito` SI puede usar `iva`: la regla tiene una sola direccion."""
    assert graph.find_call_violations(
        [("app.carrito.total", "app.iva.tasa")], REGLAS, DE_MOD) == []


def test_una_llamada_dentro_del_mismo_modulo_nunca_cruza():
    assert graph.find_call_violations(
        [("app.iva.informe", "app.iva.tasa")], REGLAS, DE_MOD) == []


def test_un_modulo_fuera_de_toda_regla_no_se_acusa():
    assert graph.find_call_violations(
        [("app.web.handler", "app.carrito.total")], REGLAS, DE_MOD) == []


def test_sin_reglas_no_hay_cruces():
    """La frontera es opt-in: sin reglas escritas no puede acusar a nadie."""
    assert graph.find_call_violations(
        [("app.iva.informe", "app.carrito.total")], [], DE_MOD) == []


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


# --- los tests estan EXENTOS de la cobertura ---------------------------------


def test_los_modulos_de_test_no_cuentan_como_zona_sin_ley():
    """Un test no es arquitectura. Exigir que `.gb-boundaries` mencione cada
    fichero de test hacía la cobertura imposible de satisfacer: en una tirada
    real (9-ago) js, go y rust escalaron los tres por SUS PROPIOS tests, no por
    el código que habían escrito. Una regla que nadie puede cumplir no informa."""
    nodes = {"app.core", "tests.test_core", "app.core_test", "app.core.spec"}

    assert graph.modulos_sin_regla(nodes, [], []) == ["app.core"]


def test_reconoce_la_convencion_de_cada_lenguaje():
    """Los sufijos y carpetas salen de la TABLA de lenguajes, no de una lista
    escrita aquí: `carrito_test` (Go), `carrito.test` (JS), `tests/` (Rust)."""
    for m in ("carrito_test", "carrito.test", "tests.carrito", "spec.carrito",
              "__tests__.carrito", "test_carrito"):
        assert graph.es_modulo_de_test(m), m


def test_no_confunde_codigo_normal_con_un_test():
    """El riesgo del otro lado: eximir de más deja zonas reales sin vigilar."""
    for m in ("app.core", "app.testigo", "app.latest", "contest", "app.protest"):
        assert not graph.es_modulo_de_test(m), m
