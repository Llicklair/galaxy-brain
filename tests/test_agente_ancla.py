"""Lanzar un agente ANCLADO a un simbolo del grafo (`bucle/agente.py --nodo`).

Que aporta el ancla, en orden de fuerza MEDIDA:

  1. verificacion anclada — «cambiaste la firma y no miraste 4 de sus 7
     llamantes» es la arista determinista que obliga (rechazo por adopcion 4/4)
  2. alcance — un fichero y un simbolo en vez del repo entero
  3. contexto inyectado — el mas debil, y el que mas se parece a lo que la
     intuicion diria que importa: la señal preventiva se ignoro 12/12

Por eso los tests de aqui miran sobre todo lo primero. Y el que manda es el
CONTROL POSITIVO: un acusador que acusa siempre es peor que no tener acusador, y
esta version lo hizo — las rutas del grafo salen de la raiz analizada (`src`) y
las del diff de la raiz del repo, asi que no casaba ninguna y todos los llamantes
figuraban como "sin tocar".
"""

import importlib.util
import os
import subprocess

import pytest

_RUTA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "bucle", "agente.py")
_spec = importlib.util.spec_from_file_location("agente_del_banco", _RUTA)
agente = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(agente)


def _git(root, *args):
    subprocess.run(["git", "-C", str(root)] + list(args), check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    """Un repo con `src/` y un simbolo con DOS llamantes."""
    root = tmp_path / "proyecto"
    (root / "src" / "lib").mkdir(parents=True)
    (root / "src" / "lib" / "__init__.py").write_text("", encoding="utf-8")
    (root / "src" / "lib" / "nucleo.py").write_text(
        "def total(xs):\n    return sum(xs)\n", encoding="utf-8")
    (root / "src" / "lib" / "uno.py").write_text(
        "from lib.nucleo import total\n\n\ndef a(xs):\n    return total(xs)\n",
        encoding="utf-8")
    (root / "src" / "lib" / "dos.py").write_text(
        "from lib.nucleo import total\n\n\ndef b(xs):\n    return total(xs) * 2\n",
        encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t.t")
    _git(root, "config", "user.name", "t")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "base")
    return root


# --- resolver el ancla -------------------------------------------------------


def test_resuelve_el_simbolo_con_sus_llamantes(repo):
    nodo, motivo = agente.resuelve_nodo(str(repo), "total", str(repo / "src"))

    assert nodo, motivo
    assert nodo["symbol"]["qual"] == "lib.nucleo.total"
    assert {c["qual"] for c in nodo["callers"]} == {"lib.uno.a", "lib.dos.b"}


def test_un_simbolo_que_no_esta_no_se_sustituye_por_nada(repo):
    """Pedir un sitio concreto y recibir "trabaja donde puedas" seria peor que
    fallar: el agente saldria disparado sobre el repo entero."""
    nodo, motivo = agente.resuelve_nodo(str(repo), "no_existe", str(repo / "src"))

    assert nodo is None
    assert "no hay ningun simbolo" in motivo


def test_un_nombre_ambiguo_pide_el_cualificado(repo):
    (repo / "src" / "lib" / "otro.py").write_text(
        "def total(xs):\n    return 0\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "homonimo")

    nodo, motivo = agente.resuelve_nodo(str(repo), "total", str(repo / "src"))

    assert nodo is None
    assert "ambiguo" in motivo


# --- la verificacion anclada, que es lo que aporta ---------------------------


def test_nombra_a_los_llamantes_que_el_agente_no_toco(repo):
    nodo, _ = agente.resuelve_nodo(str(repo), "total", str(repo / "src"))
    # el agente descuidado: cambia la firma y no mira a nadie
    (repo / "src" / "lib" / "nucleo.py").write_text(
        "def total(xs, iva):\n    return sum(xs) * iva\n", encoding="utf-8")

    sin_tocar = agente.llamantes_sin_tocar(str(repo), nodo)

    assert len(sin_tocar) == 2
    assert any("lib.uno.a" in s for s in sin_tocar)


def test_el_llamante_actualizado_deja_de_figurar(repo):
    """EL control positivo. Sin el, un acusador roto que acusa a todos siempre
    pasa por bueno — y esta version lo estuvo hasta que este test la cazó."""
    nodo, _ = agente.resuelve_nodo(str(repo), "total", str(repo / "src"))
    (repo / "src" / "lib" / "nucleo.py").write_text(
        "def total(xs, iva):\n    return sum(xs) * iva\n", encoding="utf-8")
    (repo / "src" / "lib" / "uno.py").write_text(
        "from lib.nucleo import total\n\n\ndef a(xs):\n    return total(xs, 1.21)\n",
        encoding="utf-8")

    sin_tocar = agente.llamantes_sin_tocar(str(repo), nodo)

    assert len(sin_tocar) == 1, sin_tocar
    assert "lib.dos.b" in sin_tocar[0]


def test_el_prefijo_del_analisis_se_guarda(repo):
    """La causa raiz del acusador roto: rutas de dos origenes distintos."""
    nodo, _ = agente.resuelve_nodo(str(repo), "total", str(repo / "src"))

    assert nodo["prefijo"] == "src"


# --- el encuadre que recibe el agente ---------------------------------------


def test_el_brief_dice_donde_y_contra_que_se_le_verifica(repo):
    nodo, _ = agente.resuelve_nodo(str(repo), "total", str(repo / "src"))

    brief = agente.brief_del_nodo(nodo)

    assert "lib.nucleo.total" in brief
    assert "lib.uno.a" in brief and "lib.dos.b" in brief
    assert "actualiza a sus llamantes" in brief


def test_un_simbolo_sin_llamantes_lo_dice(repo):
    """Callar aqui dejaria al agente creyendo que hay llamantes que vigilar."""
    (repo / "src" / "lib" / "suelto.py").write_text(
        "def nadie_me_llama():\n    return 1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "suelto")
    nodo, _ = agente.resuelve_nodo(str(repo), "nadie_me_llama", str(repo / "src"))

    assert "ninguno en el grafo" in agente.brief_del_nodo(nodo)
