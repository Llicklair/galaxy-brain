"""Los símbolos que YA EXISTÍAN y el cambio modifica.

El hecho que faltaba, medido el 9-ago con agentes reales. Ante un rechazo del
grafo, dos de tres hicieron desaparecer la violación tocando código que nadie les
pidió tocar: uno vació `carrito.Total` y se llevó la suma al módulo de impuestos,
otro le clavó el 21 % como valor por defecto a `total`. Los tres veredictos eran
CORRECTOS sobre sus hechos —sin ciclos, sin cruces, verdes— porque "sin
violaciones" era alcanzable degradando el código.

No acusa y no gatea: modificar lo que existe es la mitad del trabajo normal, y
gatearlo sería el proxy que fabrica el `--no-verify` (regla 9). Es un hecho para
ponerlo delante, del modelo en el peldaño siguiente y del humano en el veredicto.
"""

import importlib.util
import os

from galaxybrain import impacted

# `bucle/` no es un paquete instalable: se carga por ruta, igual que en
# tests/test_escalera.py.
_RUTA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "bucle", "escalera.py")
_spec = importlib.util.spec_from_file_location("escalera_de_preexistentes", _RUTA)
escalera = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(escalera)


def _nodo(qual, linea, fin, fichero="src/carrito.js"):
    return {"qual": qual, "file": fichero, "line": linea, "end": fin, "kind": "function"}


# --- la regla: nuevo = todo su cuerpo cae en lineas anadidas -----------------


def test_una_funcion_anadida_entera_NO_es_preexistente():
    """El caso de rust: `informe` se escribe al final y todo su cuerpo es hunk."""
    nodes = {"iva.informe": _nodo("iva.informe", 5, 11, "src/iva.rs")}

    previos = impacted.simbolos_preexistentes(nodes, {"src/iva.rs": [(5, 11)]})

    assert previos == []


def test_una_funcion_que_asoma_fuera_del_hunk_SI_lo_es():
    """El caso de go y js: `total` ya estaba y el cambio le mete mano dentro."""
    nodes = {"carrito.total": _nodo("carrito.total", 3, 9)}

    previos = impacted.simbolos_preexistentes(nodes, {"src/carrito.js": [(5, 6)]})

    assert previos == ["carrito.total"]


def test_los_dos_a_la_vez_se_separan():
    """El diff real de js: `sumar` es nueva y `total` estaba — solo la segunda."""
    nodes = {"carrito.sumar": _nodo("carrito.sumar", 1, 3),
             "carrito.total": _nodo("carrito.total", 5, 8)}

    previos = impacted.simbolos_preexistentes(
        nodes, {"src/carrito.js": [(1, 3), (6, 6)]})

    assert previos == ["carrito.total"]


def test_un_simbolo_partido_en_dos_hunks_PEGADOS_sigue_siendo_nuevo():
    """Sin fusionar tramos, un cuerpo cubierto por (1,3) y (4,7) parecía asomar
    fuera de ambos y se contaba como preexistente — un falso positivo del propio
    mecanismo, que es lo que esta capa no se puede permitir."""
    nodes = {"m.f": _nodo("m.f", 1, 7, "m.py")}

    assert impacted.simbolos_preexistentes(nodes, {"m.py": [(1, 3), (4, 7)]}) == []


def test_un_fichero_sin_hunks_no_acusa_a_nadie():
    nodes = {"carrito.total": _nodo("carrito.total", 3, 9)}

    assert impacted.simbolos_preexistentes(nodes, {"otro.js": [(1, 99)]}) == []


def test_un_modulo_no_cuenta_como_simbolo():
    """Los módulos no tienen `end` y abarcarían el fichero entero."""
    nodes = {"carrito": {"qual": "carrito", "file": "src/carrito.js",
                         "line": 1, "end": None, "kind": "module"}}

    assert impacted.simbolos_preexistentes(nodes, {"src/carrito.js": [(2, 3)]}) == []


# --- el hecho viaja al peldano siguiente ------------------------------------


def test_el_peldano_le_ensena_lo_que_toco():
    p = escalera.escalon(1, "haz X", rechazo="cruce de frontera: iva -> carrito",
                         preexistentes=["carrito.total"])

    assert "MODIFICO codigo que ya existia" in p
    assert "carrito.total" in p


def test_sin_preexistentes_el_peldano_no_menciona_nada():
    """No se fabrica un aviso vacío: un bloque que siempre aparece deja de leerse."""
    p = escalera.escalon(1, "haz X", rechazo="ciclo de imports nuevo: a <-> b")

    assert "MODIFICO codigo que ya existia" not in p


# --- ...y al veredicto, sin cambiarlo ---------------------------------------


def _hechos(**kw):
    base = {"tests_verdes": True, "suite_entera": True, "ciclos_nuevos": [],
            "cruces_frontera": [], "cruces_llamada": [], "cruces_superficie": [],
            "llamantes_huerfanos": [], "modulos_tocados": ["iva"],
            "modulos_sin_regla": [], "criterio_pasa": True}
    base.update(kw)
    return base


def test_se_dice_en_el_veredicto_pero_NO_lo_cambia():
    """Justo el diff de go: aceptado —y de paso se llevó `carrito.Total`."""
    v, motivo = escalera.decidir(_hechos(simbolos_preexistentes=["carrito.Total"]))

    assert v == escalera.ACEPTAR
    assert "ya existian" in motivo and "carrito.Total" in motivo


def test_sin_preexistentes_el_veredicto_sale_limpio():
    v, motivo = escalera.decidir(_hechos())

    assert v == escalera.ACEPTAR
    assert "ya existian" not in motivo
