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


def test_if_changed_NO_crea_si_no_existe(tmp_path, gb_home):
    """Modo mantenimiento: refresca el mapa que ya hay, no genera uno nuevo. Es
    lo que hace seguro un hook GLOBAL: en un repo donde nunca generaste el mapa,
    el hook no ensucia nada. La presencia del fichero es el opt-in."""
    raiz = _proyecto(tmp_path)
    destino = str(tmp_path / "mapa.html")
    assert cli.main(["symbols", raiz, "--html", destino, "--if-changed", "--color", "never"]) == 0
    assert not os.path.exists(destino), "no debia crear el mapa en modo mantenimiento"


def test_sin_if_changed_si_crea_la_primera_vez(tmp_path, gb_home):
    """La generacion manual —la que hace el usuario— crea el fichero. Ese es el
    opt-in que luego el hook mantiene."""
    raiz = _proyecto(tmp_path)
    destino = str(tmp_path / "mapa.html")
    assert cli.main(["symbols", raiz, "--html", destino, "--color", "never"]) == 0
    assert os.path.exists(destino)


def _generar(raiz, destino):
    """La generacion manual que crea el mapa: sin --if-changed."""
    cli.main(["symbols", raiz, "--html", destino, "--color", "never"])


def test_sin_cambios_no_reescribe(tmp_path, gb_home):
    raiz = _proyecto(tmp_path)
    destino = str(tmp_path / "mapa.html")
    _generar(raiz, destino)
    antes = _mtime(destino)

    import time

    time.sleep(0.02)
    cli.main(["symbols", raiz, "--html", destino, "--if-changed", "--color", "never"])
    assert _mtime(destino) == antes, "reescribio sin que la forma cambiara"


def test_un_modulo_nuevo_si_reescribe(tmp_path, gb_home):
    raiz = _proyecto(tmp_path)
    destino = str(tmp_path / "mapa.html")
    _generar(raiz, destino)
    antes = _mtime(destino)

    import time

    time.sleep(0.02)
    with open(os.path.join(raiz, "pkg", "nuevo.py"), "w", encoding="utf-8") as handle:
        handle.write("def n():\n    return 3\n")
    cli.main(["symbols", raiz, "--html", destino, "--if-changed", "--color", "never"])
    assert _mtime(destino) > antes, "no reescribio pese al modulo nuevo"


def test_una_funcion_nueva_en_un_modulo_existente_SI_reescribe(tmp_path, gb_home):
    """El bug que congelaba el mapa 5 horas: --if-changed comparaba la forma a
    nivel de MODULO (imports, ciclos), pero el mapa dibuja SIMBOLOS. Anadir una
    funcion a un modulo que ya existe no crea ningun import nuevo, asi que la forma
    de modulos no se movia y el mapa se quedaba con 274 simbolos mostrando 275."""
    raiz = _proyecto(tmp_path)
    destino = str(tmp_path / "mapa.html")
    _generar(raiz, destino)
    antes = _mtime(destino)

    import time

    time.sleep(0.02)
    # NO es un modulo nuevo ni un import nuevo: una funcion mas en pkg/a.py.
    with open(os.path.join(raiz, "pkg", "a.py"), "a", encoding="utf-8") as handle:
        handle.write("\n\ndef nueva_funcion():\n    return 99\n")
    cli.main(["symbols", raiz, "--html", destino, "--if-changed", "--color", "never"])
    assert _mtime(destino) > antes, "un simbolo nuevo no disparo la regeneracion"


def test_cambiar_un_docstring_SI_reescribe(tmp_path, gb_home):
    """La ficha muestra el docstring, asi que cambiarlo cambia lo que se ve."""
    raiz = _proyecto(tmp_path)
    with open(os.path.join(raiz, "pkg", "a.py"), "w", encoding="utf-8") as handle:
        handle.write('def f():\n    """Antes."""\n    return 1\n')
    destino = str(tmp_path / "mapa.html")
    _generar(raiz, destino)
    antes = _mtime(destino)

    import time

    time.sleep(0.02)
    with open(os.path.join(raiz, "pkg", "a.py"), "w", encoding="utf-8") as handle:
        handle.write('def f():\n    """Despues, distinto."""\n    return 1\n')
    cli.main(["symbols", raiz, "--html", destino, "--if-changed", "--color", "never"])
    assert _mtime(destino) > antes, "cambiar el docstring no regenero el mapa"


def test_reformatear_el_cuerpo_no_reescribe(tmp_path, gb_home):
    """La forma es estructura, no texto: cambiar el interior de una funcion sin
    tocar imports ni firmas no mueve el mapa."""
    raiz = _proyecto(tmp_path)
    destino = str(tmp_path / "mapa.html")
    _generar(raiz, destino)
    antes = _mtime(destino)

    import time

    time.sleep(0.02)
    with open(os.path.join(raiz, "pkg", "a.py"), "w", encoding="utf-8") as handle:
        handle.write("def f():\n    total = 0 + 1\n    return total\n")
    cli.main(["symbols", raiz, "--html", destino, "--if-changed", "--color", "never"])
    assert _mtime(destino) == antes


def test_si_borran_el_fichero_el_mantenimiento_no_lo_resucita(tmp_path, gb_home):
    """Borrar el mapa es dejar de quererlo. El modo mantenimiento respeta esa
    decision: no lo vuelve a crear. Para tenerlo otra vez, se genera a mano —
    justo el mismo opt-in que la primera vez."""
    raiz = _proyecto(tmp_path)
    destino = str(tmp_path / "mapa.html")
    _generar(raiz, destino)
    os.remove(destino)
    cli.main(["symbols", raiz, "--html", destino, "--if-changed", "--color", "never"])
    assert not os.path.exists(destino)


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


def test_el_mantenimiento_conserva_el_auto_refresh(tmp_path, gb_home):
    """El bug que congelaba la pagina: el hook regenera SIN --refresco, asi que si
    gb no recordara el refresco de la generacion manual, cada regeneracion le
    arrancaria al fichero su <meta refresh> y la pagina dejaria de recargar tras
    la primera vez. El sello se quedaba clavado en una hora."""
    raiz = _proyecto(tmp_path)
    destino = str(tmp_path / "mapa.html")
    # Generacion manual con refresco, como haria el usuario.
    cli.main(["symbols", raiz, "--html", destino, "--refresco", "300", "--color", "never"])
    assert 'content="300"' in open(destino, encoding="utf-8").read()

    # Cambia la forma y mantenimiento SIN --refresco, como el hook.
    with open(os.path.join(raiz, "pkg", "nuevo.py"), "w", encoding="utf-8") as handle:
        handle.write("def n():\n    return 3\n")
    cli.main(["symbols", raiz, "--html", destino, "--if-changed", "--color", "never"])

    assert 'content="300"' in open(destino, encoding="utf-8").read(), (
        "el mantenimiento se comio el auto-refresh: la pagina se congelaria"
    )


def test_sin_refresco_el_mantenimiento_no_lo_inventa(tmp_path, gb_home):
    """Y al reves: si generaste sin refresco, el mantenimiento no debe meterlo."""
    raiz = _proyecto(tmp_path)
    destino = str(tmp_path / "mapa.html")
    cli.main(["symbols", raiz, "--html", destino, "--color", "never"])
    with open(os.path.join(raiz, "pkg", "nuevo.py"), "w", encoding="utf-8") as handle:
        handle.write("def n():\n    return 3\n")
    cli.main(["symbols", raiz, "--html", destino, "--if-changed", "--color", "never"])
    assert 'http-equiv="refresh"' not in open(destino, encoding="utf-8").read()


def test_watch_necesita_html(tmp_path):
    """Vigilar sin decir que fichero escribir no tiene sentido: se avisa, no se
    ignora en silencio."""
    raiz = _proyecto(tmp_path)
    assert cli.main(["symbols", raiz, "--watch", "--color", "never"]) == 2


def test_la_firma_del_arbol_detecta_una_edicion(tmp_path):
    """El corazon de --watch: si un .py cambia de tamano o de mtime, la firma se
    mueve y el watcher reanaliza. Si no lo detectara, el mapa no se actualizaria
    aunque el proceso estuviera vivo — que es justo lo que fallaba con el hook."""
    raiz = _proyecto(tmp_path)
    antes = cli._firma_py(raiz)

    import time

    time.sleep(0.02)
    with open(os.path.join(raiz, "pkg", "a.py"), "a", encoding="utf-8") as handle:
        handle.write("\n\ndef otra():\n    return 2\n")
    assert cli._firma_py(raiz) != antes, "una edicion no movio la firma del arbol"


def test_la_firma_ignora_lo_que_no_es_codigo(tmp_path):
    """Un .html regenerado (el propio mapa) o un __pycache__ no deben disparar el
    watcher: si no, se realimentaria solo. Solo cuentan los .py, y no los de
    directorios ignorados."""
    raiz = _proyecto(tmp_path)
    antes = cli._firma_py(raiz)
    with open(os.path.join(raiz, "mapa.html"), "w", encoding="utf-8") as handle:
        handle.write("<html></html>")
    os.makedirs(os.path.join(raiz, "__pycache__"), exist_ok=True)
    with open(os.path.join(raiz, "__pycache__", "x.py"), "w", encoding="utf-8") as handle:
        handle.write("basura\n")
    assert cli._firma_py(raiz) == antes


def test_dos_mapas_distintos_del_mismo_repo_no_se_pisan(tmp_path, gb_home):
    """Nube y capas a ficheros distintos llevan su propia cuenta de forma: que uno
    no cambie no puede impedir que el otro se escriba la primera vez."""
    raiz = _proyecto(tmp_path)
    nube = str(tmp_path / "nube.html")
    capas = str(tmp_path / "capas.html")
    # Generacion manual de los dos, y luego mantenimiento: que uno no cambie no
    # puede impedir que el otro se refresque.
    cli.main(["symbols", raiz, "--html", nube, "--color", "never"])
    cli.main(["symbols", raiz, "--html", capas, "--capas", "--color", "never"])
    cli.main(["symbols", raiz, "--html", nube, "--if-changed", "--color", "never"])
    cli.main(["symbols", raiz, "--html", capas, "--capas", "--if-changed", "--color", "never"])
    assert os.path.exists(nube) and os.path.exists(capas)
