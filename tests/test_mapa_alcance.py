"""El mapa es UNO por repo: si cambia de alcance, hay que decirlo.

`gb who <ruta> --html` escribe siempre el mismo `mapa.html`. Analizar el repo
entero en vez de `src/` mete tests, bancos y experimentos en el mismo lienzo —
mas del triple de nodos y clusters sueltos que antes no estaban. Y no se lee
como "otro alcance": se lee como "el codigo ha cambiado".

Paso de verdad el 17-ago-2026 corriendo un diagnostico, y nada lo dijo: el sello
de procedencia llevaba fecha y commit, no la raiz. Lo cazo Marcos mirando el
mapa, que es el peor sitio donde cazar esto.
"""

import os

from galaxybrain import cli


def _mapa(tmp_path, nombre="mapa.html"):
    return os.path.join(str(tmp_path), nombre)


def _proyecto(root):
    """Dos alcances reales dentro del mismo arbol: la raiz y `src/`."""
    os.makedirs(os.path.join(root, "src", "app"), exist_ok=True)
    os.makedirs(os.path.join(root, "tests"), exist_ok=True)
    for rel, txt in (
        ("src/app/__init__.py", ""),
        ("src/app/web.py", "def sirve():\n    return 1\n"),
        ("tests/test_web.py", "def test_algo():\n    assert True\n"),
    ):
        path = os.path.join(root, *rel.split("/"))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(txt)
    return root


def test_el_mapa_estampa_su_alcance(tmp_path):
    root = _proyecto(str(tmp_path))
    destino = _mapa(tmp_path)
    cli.main(["who", os.path.join(root, "src"), "--html", destino])

    assert cli._alcance_de_mapa(destino) == os.path.normcase(
        os.path.abspath(os.path.join(root, "src")))


def test_reescribir_con_OTRO_alcance_avisa(tmp_path, capsys):
    root = _proyecto(str(tmp_path))
    destino = _mapa(tmp_path)

    cli.main(["who", os.path.join(root, "src"), "--html", destino])
    capsys.readouterr()
    cli.main(["who", root, "--html", destino])          # el repo entero

    err = capsys.readouterr().err
    assert "OJO" in err and "mapa era de" in err


def test_reescribir_con_EL_MISMO_alcance_no_dice_nada(tmp_path, capsys):
    """El refresco normal —y el de `--watch`, que reescribe cada pocos
    segundos— no puede soltar un aviso cada vez: un aviso que sale siempre deja
    de leerse, y entonces no avisa del caso que importa."""
    root = _proyecto(str(tmp_path))
    destino = _mapa(tmp_path)

    cli.main(["who", os.path.join(root, "src"), "--html", destino])
    capsys.readouterr()
    cli.main(["who", os.path.join(root, "src"), "--html", destino])

    assert "OJO" not in capsys.readouterr().err


def test_un_mapa_sin_marca_no_inventa_un_alcance(tmp_path, capsys):
    """Los mapas escritos antes de esta marca no tienen de donde sacarla. Se
    callan y se reescriben: afirmar un alcance que no consta seria peor."""
    root = _proyecto(str(tmp_path))
    destino = _mapa(tmp_path)
    with open(destino, "w", encoding="utf-8") as fh:
        fh.write("<html>mapa viejo, sin marca</html>")

    assert cli._alcance_de_mapa(destino) is None
    cli.main(["who", root, "--html", destino])
    assert "OJO" not in capsys.readouterr().err


def test_la_marca_no_rompe_el_html(tmp_path):
    """La marca va delante del documento; el mapa tiene que seguir siendo el
    mismo HTML utilizable."""
    root = _proyecto(str(tmp_path))
    destino = _mapa(tmp_path)
    cli.main(["who", os.path.join(root, "src"), "--html", destino])

    with open(destino, encoding="utf-8") as fh:
        texto = fh.read()
    assert texto.startswith("<!-- gb:alcance ")
    assert "<canvas" in texto or "<script" in texto
