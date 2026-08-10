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
import subprocess

# `bucle/` no es un paquete instalable: se carga por ruta, igual que en
# tests/test_escalera.py.
_RUTA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "bucle", "escalera.py")
_spec = importlib.util.spec_from_file_location("escalera_de_preexistentes", _RUTA)
escalera = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(escalera)


def _git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, check=False)


def _repo(tmp_path, contenido):
    root = tmp_path
    (root / "m.py").write_text(contenido, encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t.t")
    _git(root, "config", "user.name", "t")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "base")
    return root


# --- QUE existia se le pregunta a git, no al diff ----------------------------


def test_una_funcion_MODIFICADA_sale_como_preexistente(tmp_path):
    root = _repo(tmp_path, "def viejo():\n    return 1\n")
    (root / "m.py").write_text("def viejo():\n    return 99\n", encoding="utf-8")

    assert escalera._simbolos_preexistentes(str(root)) == ["m.viejo"]


def test_una_funcion_NUEVA_no_sale_aunque_el_diff_la_alinee_mal(tmp_path):
    """El falso positivo que se comió la primera versión, y por qué ya no se
    deduce del diff.

    Se intentó deducirlo así: un símbolo sería nuevo si todo su cuerpo cayera en
    líneas añadidas. Medido el 9-ago con una función recién creada: git alineó su
    llave de cierre con la de la función vieja y la dejó como CONTEXTO, así que el
    cuerpo asomaba una línea fuera del hunk y `iva.informe` —recién escrita— salía
    acusada de preexistente. La alineación de un diff es una heurística de
    presentación; qué existía lo sabe git y se le pregunta a él.
    """
    root = _repo(tmp_path, "def viejo():\n    return 1\n")
    (root / "m.py").write_text(
        "def viejo():\n    return 1\n\n\ndef nuevo():\n    return 2\n", encoding="utf-8")

    assert escalera._simbolos_preexistentes(str(root)) == []


def test_un_fichero_entero_nuevo_no_acusa_a_nadie(tmp_path):
    """No estaba en HEAD: `git show` falla y todos sus símbolos son nuevos."""
    root = _repo(tmp_path, "def viejo():\n    return 1\n")
    (root / "otro.py").write_text("def recien():\n    return 2\n", encoding="utf-8")

    assert escalera._simbolos_preexistentes(str(root)) == []


def test_sin_cambios_no_hay_preexistentes(tmp_path):
    assert escalera._simbolos_preexistentes(str(_repo(tmp_path, "def f():\n    return 1\n"))) == []


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


# --- ¿estaba la ley puesta? --------------------------------------------------


def test_una_regla_mal_escrita_impide_aceptar():
    """`gb graph --gate` bloquea SIEMPRE ante una configuracion de reglas rota,
    porque entonces salen cero cruces y el cero significa "no he mirado". La
    escalera no lo miraba: un cambio que rompiese el propio fichero de reglas
    salia ACEPTADO con la ley entera sin aplicar."""
    v, motivo = escalera.decidir(_hechos(ley_incomprobable=["regla(s) mal escritas: 'a - b'"]))

    assert v == escalera.ESCALAR
    assert "no se estaba comprobando" in motivo


def test_gana_a_la_cobertura_porque_la_invalida():
    """Si la ley no se aplicaba, decir "esta zona no tiene reglas" sobra: no se
    sabe si las tenia. El motivo que se da es el que explica los demas."""
    v, motivo = escalera.decidir(
        _hechos(ley_incomprobable=["el analisis no encontro ni un modulo que mirar"],
                modulos_sin_regla=["iva"]))

    assert v == escalera.ESCALAR
    assert "ni un modulo" in motivo


def test_un_cruce_DEMOSTRADO_sigue_ganando():
    """Orden: primero el fallo demostrado, despues "no he podido comprobarlo".
    Si a pesar de la configuracion rota se vio un cruce, ese cruce es real."""
    v, motivo = escalera.decidir(
        _hechos(ley_incomprobable=["hay otro fichero de reglas que NO se esta aplicando: X"],
                cruces_frontera=[{"importer": "iva", "imported": "carrito"}]))

    assert v == escalera.RECHAZAR


def test_el_informe_limpio_no_inventa_motivos():
    assert escalera._ley_incomprobable(
        {"modules": 4, "boundaries_error": None, "malformed_boundaries": [],
         "unmatched_rules": [], "boundaries_elsewhere": None, "root_error": None}) == []


def test_un_arbol_sin_un_solo_modulo_no_comprueba_nada():
    """Un typo en la ruta del hook y la gate no vuelve a mirar jamas, en verde."""
    assert escalera._ley_incomprobable({"modules": 0}) != []


# --- el fichero NUEVO tambien es un modulo tocado ---------------------------


def test_un_modulo_en_fichero_NUEVO_cuenta_como_tocado(tmp_path):
    """`git diff HEAD` no lista lo que git aún no conoce, y añadir código en un
    fichero nuevo es la forma más normal que tiene un agente de añadir código.

    Medido el 9-ago: un agente extrajo la lógica compartida a un `suma.js` nuevo
    —la solución BUENA— y ese módulo, que ninguna regla menciona, no llegó a la
    comprobación de cobertura. Se aceptó sin el ESCALAR que tocaba: el examen se
    salta creando ficheros.
    """
    root = tmp_path
    (root / "viejo.py").write_text("X = 1\n", encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t.t")
    _git(root, "config", "user.name", "t")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "base")

    (root / "viejo.py").write_text("X = 2\n", encoding="utf-8")
    (root / "nuevo.py").write_text("Y = 3\n", encoding="utf-8")     # sin trackear

    modulos = escalera._modulos_del_diff(str(root), str(root))

    assert modulos == ["nuevo", "viejo"]
