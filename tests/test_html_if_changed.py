"""`--html --if-changed`: no reescribir el mapa si la forma no cambio.

Es la pieza que faltaba para que un hook regenere el HTML en cada edicion sin
gastar 325 ms cada vez. El sello de procedencia ya avisaba de que el mapa estaba
viejo; esto es lo que lo mantiene fresco, y barato.

Mismo principio que `--context --if-changed`: reformatear o reescribir el cuerpo
de una funcion NO mueve la forma, asi que no toca el fichero. Un modulo, una
arista o un ciclo nuevos, si.
"""

import os

from galaxybrain import cli


def _proyecto(tmp_path):
    for rel, cuerpo in (
        ("pkg/__init__.py", ""),
        ("pkg/a.py", "def f():\n    return 1\n"),
        ("pkg/b.py", "def g():\n    return 2\n"),
    ):
        ruta = os.path.join(str(tmp_path), *rel.split("/"))
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, "w", encoding="utf-8") as handle:
            handle.write(cuerpo)
    return str(tmp_path)


def _mtime(path):
    return os.path.getmtime(path)


def test_primera_vez_escribe(tmp_path, gb_home):
    raiz = _proyecto(tmp_path)
    destino = str(tmp_path / "mapa.html")
    assert cli.main(["symbols", raiz, "--html", destino, "--if-changed", "--color", "never"]) == 0
    assert os.path.exists(destino)


def test_sin_cambios_no_reescribe(tmp_path, gb_home):
    raiz = _proyecto(tmp_path)
    destino = str(tmp_path / "mapa.html")
    cli.main(["symbols", raiz, "--html", destino, "--if-changed", "--color", "never"])
    antes = _mtime(destino)

    import time

    time.sleep(0.02)
    cli.main(["symbols", raiz, "--html", destino, "--if-changed", "--color", "never"])
    assert _mtime(destino) == antes, "reescribio sin que la forma cambiara"


def test_un_modulo_nuevo_si_reescribe(tmp_path, gb_home):
    raiz = _proyecto(tmp_path)
    destino = str(tmp_path / "mapa.html")
    cli.main(["symbols", raiz, "--html", destino, "--if-changed", "--color", "never"])
    antes = _mtime(destino)

    import time

    time.sleep(0.02)
    with open(os.path.join(raiz, "pkg", "nuevo.py"), "w", encoding="utf-8") as handle:
        handle.write("def n():\n    return 3\n")
    cli.main(["symbols", raiz, "--html", destino, "--if-changed", "--color", "never"])
    assert _mtime(destino) > antes, "no reescribio pese al modulo nuevo"


def test_reformatear_el_cuerpo_no_reescribe(tmp_path, gb_home):
    """La forma es estructura, no texto: cambiar el interior de una funcion sin
    tocar imports ni firmas no mueve el mapa."""
    raiz = _proyecto(tmp_path)
    destino = str(tmp_path / "mapa.html")
    cli.main(["symbols", raiz, "--html", destino, "--if-changed", "--color", "never"])
    antes = _mtime(destino)

    import time

    time.sleep(0.02)
    with open(os.path.join(raiz, "pkg", "a.py"), "w", encoding="utf-8") as handle:
        handle.write("def f():\n    total = 0 + 1\n    return total\n")
    cli.main(["symbols", raiz, "--html", destino, "--if-changed", "--color", "never"])
    assert _mtime(destino) == antes


def test_si_borran_el_fichero_se_regenera(tmp_path, gb_home):
    """Aunque la forma no haya cambiado: un mapa que ya no esta en disco tiene
    que volver. La memoria de forma no puede fingir que el fichero sigue ahi."""
    raiz = _proyecto(tmp_path)
    destino = str(tmp_path / "mapa.html")
    cli.main(["symbols", raiz, "--html", destino, "--if-changed", "--color", "never"])
    os.remove(destino)
    cli.main(["symbols", raiz, "--html", destino, "--if-changed", "--color", "never"])
    assert os.path.exists(destino)


def test_sin_if_changed_reescribe_siempre(tmp_path, gb_home):
    """El comportamiento por defecto no cambia: sin el flag, cada llamada escribe."""
    raiz = _proyecto(tmp_path)
    destino = str(tmp_path / "mapa.html")
    cli.main(["symbols", raiz, "--html", destino, "--color", "never"])
    antes = _mtime(destino)

    import time

    time.sleep(0.02)
    cli.main(["symbols", raiz, "--html", destino, "--color", "never"])
    assert _mtime(destino) > antes


def test_dos_mapas_distintos_del_mismo_repo_no_se_pisan(tmp_path, gb_home):
    """Nube y capas a ficheros distintos llevan su propia cuenta de forma: que uno
    no cambie no puede impedir que el otro se escriba la primera vez."""
    raiz = _proyecto(tmp_path)
    nube = str(tmp_path / "nube.html")
    capas = str(tmp_path / "capas.html")
    cli.main(["symbols", raiz, "--html", nube, "--if-changed", "--color", "never"])
    cli.main(["symbols", raiz, "--html", capas, "--capas", "--if-changed", "--color", "never"])
    assert os.path.exists(nube) and os.path.exists(capas)
