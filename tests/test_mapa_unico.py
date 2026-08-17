"""Un mapa por REPO, sea cual sea la raiz que analices.

`gb who src --html` buscaba `mapa.html` en `src/` — donde no esta, porque vive
en el toplevel — y al no encontrarlo se fabricaba uno propio en GB_HOME con el
slug de `src`. Resultado: tres ficheros para un proyecto (el de la raiz, el del
repo en GB_HOME y el de `src`), y el que el usuario tenia abierto envejeciendo
en silencio. Es el fallo del 14-ago por el otro lado: entonces se escribia
fuera teniendo uno en la raiz; aqui se escribe fuera por mirar una raiz mas
estrecha. El mapa es la fuente de verdad, y una fuente de verdad duplicada no
es una fuente de verdad.
"""

import os
import subprocess
import sys

import pytest

from galaxybrain import lenguajes

necesita_git = pytest.mark.skipif(
    not lenguajes.shutil.which("git"), reason="el destino se decide por el repo"
)


def _proyecto(raiz):
    os.makedirs(os.path.join(raiz, "src", "paquete"), exist_ok=True)
    with open(os.path.join(raiz, "src", "paquete", "__init__.py"), "w") as fh:
        fh.write("")
    with open(os.path.join(raiz, "src", "paquete", "cosa.py"), "w") as fh:
        fh.write("def hacer():\n    return 1\n")
    subprocess.run(["git", "-C", raiz, "init", "-q"], check=True)
    return raiz


def _who(raiz, sub):
    return subprocess.run(
        [sys.executable, "-m", "galaxybrain.cli", "who", sub, "--html"],
        cwd=raiz, capture_output=True, text=True, timeout=300,
    )


@necesita_git
def test_analizar_src_refresca_el_mapa_del_repo(tmp_path):
    raiz = _proyecto(str(tmp_path))
    mapa = os.path.join(raiz, "mapa.html")
    with open(mapa, "w", encoding="utf-8") as fh:
        fh.write("<!-- viejo -->")

    _who(raiz, "src")

    with open(mapa, encoding="utf-8") as fh:
        assert "<!-- viejo -->" not in fh.read(), "el mapa del repo no se refresco"
    assert not os.path.exists(os.path.join(raiz, "src", "mapa.html")), \
        "se fabrico un segundo mapa dentro de src/"


@necesita_git
def test_sin_mapa_en_el_repo_no_se_ensucia_el_proyecto(tmp_path):
    """Regla 7: quien no pidio un mapa no se lo encuentra dentro."""
    raiz = _proyecto(str(tmp_path))
    _who(raiz, "src")
    assert not os.path.exists(os.path.join(raiz, "mapa.html"))
    assert not os.path.exists(os.path.join(raiz, "src", "mapa.html"))
