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


def test_el_refresco_automatico_respeta_el_alcance_grabado(tmp_path):
    """El caso que hacia inutil todo lo demas.

    Cada comando gb suelta un hijo que regenera el mapa (estigmergia). Analizaba
    siempre la raiz, asi que un mapa hecho a proposito de `src/` volvia al repo
    entero al primer comando gb pasados los 60 s de rebote — y el aviso no se ve,
    porque el hijo manda stderr a DEVNULL. Regenerarlo a mano no servia de nada.
    """
    root = _proyecto(str(tmp_path))
    destino = _mapa(tmp_path)
    cli.main(["who", os.path.join(root, "src"), "--html", destino])

    args = cli._args_del_refresco(root, destino)
    assert args[0] == "who" and "--html" in args
    assert os.path.normcase(args[1]) == os.path.normcase(
        os.path.abspath(os.path.join(root, "src")))


def test_sin_ruta_escrita_manda_el_alcance_QUE_EL_MAPA_YA_TENIA(tmp_path):
    """El agujero que dejaba inútil todo lo demás.

    `who` analizaba el cwd por defecto, y el mapa es UNO por repo: un
    `gb who --html` tecleado desde la raíz reescribía con el árbol entero el
    mapa que estaba acotado a `src`. Pasó TRES veces en un día, dos de ellas
    ejecutando diagnósticos. Ya había un aviso y no bastó — solo se ve en el
    instante, y el refresco automático manda su stderr a DEVNULL.
    """
    root = _proyecto(str(tmp_path))
    mapa = os.path.join(root, "mapa.html")
    cli.main(["who", os.path.join(root, "src"), "--html", mapa])
    assert cli._alcance_de_mapa(mapa).endswith("src")

    # sin ruta escrita, desde la raiz del proyecto: NO debe ampliarse
    hecho = os.getcwd()
    try:
        os.chdir(root)
        cli.main(["who", "--html", mapa])
    finally:
        os.chdir(hecho)

    assert cli._alcance_de_mapa(mapa).endswith("src"), (
        "un `who` sin ruta se ha llevado por delante el alcance elegido")


def test_con_ruta_escrita_manda_la_ruta(tmp_path):
    """El control: si esto no pasara, el alcance sería inamovible y no habría
    forma de ampliarlo. Escribir la ruta es la bandera explícita."""
    root = _proyecto(str(tmp_path))
    mapa = os.path.join(root, "mapa.html")
    cli.main(["who", os.path.join(root, "src"), "--html", mapa])

    cli.main(["who", root, "--html", mapa])           # ruta explicita
    assert not cli._alcance_de_mapa(mapa).endswith("src")


def test_sin_marca_el_refresco_sigue_analizando_la_raiz(tmp_path):
    """Sin alcance grabado no se inventa uno: el comportamiento de siempre."""
    root = _proyecto(str(tmp_path))
    destino = _mapa(tmp_path)
    with open(destino, "w", encoding="utf-8") as fh:
        fh.write("<html>mapa viejo</html>")

    assert cli._args_del_refresco(root, destino) == ["who", "--html"]


def test_un_alcance_que_ya_no_existe_no_deja_el_mapa_sin_refrescar(tmp_path):
    """Si la carpeta grabada desaparecio, el hijo no puede analizarla. Cae a la
    raiz en vez de quedarse sin mapa."""
    root = _proyecto(str(tmp_path))
    destino = _mapa(tmp_path)
    with open(destino, "w", encoding="utf-8") as fh:
        fh.write("<!-- gb:alcance %s -->\n<html></html>"
                 % os.path.join(root, "carpeta-borrada"))

    assert cli._args_del_refresco(root, destino) == ["who", "--html"]


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
