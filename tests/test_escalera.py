"""La decisión de aceptar sin que nadie lo mire.

Es la función más peligrosa del proyecto: un `ACEPTAR` de más deja entrar código
que nadie ha visto. Por eso es PURA —dict entra, veredicto sale— y por eso se
prueba aparte del bucle: lo que decide no puede depender de haber lanzado un
agente.

La ley que la gobierna, y que separa esto de un `--no-verify` automático:

  1. un fallo DEMOSTRADO se rechaza (tests rojos, ciclo, cruce, huérfano)
  2. lo que NO se ha podido comprobar se escala, nunca se acepta
  3. y el caso que da nombre a todo esto: sobre una zona que ninguna regla
     menciona, "cero violaciones" no es un aprobado — es que no hubo examen
"""

import importlib.util
import os

_RUTA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "bucle", "escalera.py")
_spec = importlib.util.spec_from_file_location("escalera_del_banco", _RUTA)
escalera = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(escalera)


def _hechos(**kw):
    """Un cambio limpio y COMPROBADO: la unica forma de llegar a ACEPTAR."""
    base = {
        "tests_verdes": True,
        "suite_entera": False,
        "ciclos_nuevos": [],
        "cruces_frontera": [],
        "cruces_superficie": [],
        "llamantes_huerfanos": [],
        "modulos_tocados": ["app.carrito"],
        "modulos_sin_regla": ["app.otro"],
    }
    base.update(kw)
    return base


# --- el unico camino a ACEPTAR ----------------------------------------------


def test_un_cambio_limpio_y_cubierto_se_acepta():
    veredicto, motivo = escalera.decidir(_hechos())

    assert veredicto == escalera.ACEPTAR
    assert "verdes" in motivo


def test_correr_la_suite_entera_tambien_vale():
    """No estrechar es MAS seguro, no menos: el veredicto sigue siendo real."""
    veredicto, motivo = escalera.decidir(_hechos(suite_entera=True))

    assert veredicto == escalera.ACEPTAR
    assert "suite entera" in motivo


# --- fallos demostrados: RECHAZAR -------------------------------------------


def test_tests_rojos_se_rechaza():
    assert escalera.decidir(_hechos(tests_verdes=False))[0] == escalera.RECHAZAR


def test_un_ciclo_nuevo_se_rechaza():
    v, motivo = escalera.decidir(_hechos(ciclos_nuevos=[["a", "b"]]))
    assert v == escalera.RECHAZAR
    assert "a <-> b" in motivo


def test_un_cruce_de_frontera_se_rechaza():
    v, motivo = escalera.decidir(
        _hechos(cruces_frontera=[{"importer": "core", "imported": "web"}]))
    assert v == escalera.RECHAZAR
    assert "core -> web" in motivo


def test_romper_la_superficie_publica_se_rechaza():
    v, motivo = escalera.decidir(
        _hechos(cruces_superficie=[{"caller": "web.h", "callee": "store._x"}]))
    assert v == escalera.RECHAZAR
    assert "simbolo interno" in motivo


def test_un_llamante_huerfano_se_rechaza():
    v, motivo = escalera.decidir(_hechos(llamantes_huerfanos=["app.web.usa"]))
    assert v == escalera.RECHAZAR
    assert "sin actualizar" in motivo


def test_el_fallo_demostrado_gana_a_la_falta_de_ley():
    """Rompiendo una frontera Y tocando zona sin reglas, se RECHAZA: ahi si hay
    algo concreto que decirle al agente, y escalar seria perder esa señal."""
    v, _ = escalera.decidir(_hechos(
        cruces_frontera=[{"importer": "a", "imported": "b"}],
        modulos_tocados=["sin_ley"], modulos_sin_regla=["sin_ley"]))

    assert v == escalera.RECHAZAR


# --- lo que no se pudo comprobar: ESCALAR, nunca aceptar ---------------------


def test_sin_veredicto_de_tests_se_escala():
    """`None` no es verde. Aceptar aqui seria dar por bueno lo no medido."""
    v, motivo = escalera.decidir(_hechos(tests_verdes=None))

    assert v == escalera.ESCALAR
    assert "sin veredicto" in motivo


def test_tocar_zona_SIN_REGLAS_se_escala():
    """El caso que da nombre a todo esto: cero violaciones donde no hay reglas no
    es un aprobado, es la ausencia de examen."""
    v, motivo = escalera.decidir(
        _hechos(modulos_tocados=["app.suelto"], modulos_sin_regla=["app.suelto"]))

    assert v == escalera.ESCALAR
    assert "no hubo examen" in motivo


def test_si_no_se_sabe_que_toca_se_escala():
    v, motivo = escalera.decidir(_hechos(modulos_tocados=[]))

    assert v == escalera.ESCALAR
    assert "que modulos toca" in motivo


def test_zona_sin_ley_que_NO_se_toca_no_estorba():
    """Solo importa la interseccion: un repo con modulos sin declarar es normal."""
    v, _ = escalera.decidir(
        _hechos(modulos_tocados=["app.carrito"], modulos_sin_regla=["app.otro", "app.mas"]))

    assert v == escalera.ACEPTAR


# --- la parada: un hecho, no una cuota ---------------------------------------


def test_dos_rechazos_iguales_son_la_parada():
    assert escalera.mismo_rechazo("cruce a -> b", "cruce a -> b")
    assert not escalera.mismo_rechazo("cruce a -> b", "tests en rojo")
    assert not escalera.mismo_rechazo("", "")


# --- los peldaños: hechos, no ordenes ----------------------------------------


def test_el_peldano_cero_es_la_tarea_pelada():
    assert escalera.escalon(0, "arregla X") == "arregla X"


def test_el_peldano_uno_anade_el_rechazo_exacto():
    p = escalera.escalon(1, "arregla X", rechazo="cruce de frontera: core -> web")

    assert "arregla X" in p
    assert "core -> web" in p
    # sin lenguaje imperativo: lo que mueve al modelo es el hecho, medido
    assert "corrige" not in p.lower() and "asegurate" not in p.lower()


def test_el_peldano_dos_ancla_y_recorta_el_alcance():
    ancla = {"symbol": {"qual": "app.total", "file": "app.py", "line": 3},
             "callers": [{"qual": "web.h", "file": "web.py", "line": 9}]}

    p = escalera.escalon(2, "arregla X", rechazo="algo", ancla=ancla)

    assert "app.total" in p and "web.h" in p and "ALCANCE" in p


def test_sin_rechazo_no_se_inventa_contexto():
    assert escalera.escalon(2, "arregla X") == "arregla X"
