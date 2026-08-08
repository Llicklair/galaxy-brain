"""Nunca un veredicto sobre codigo que no se ha leido.

Por muchos motores que haya, siempre existira un lenguaje que gb no parsea, asi
que esto no es un paso intermedio hacia el multilenguaje: es la conducta
PERMANENTE en la frontera. "No lo veo" y "no esta" son afirmaciones distintas, y
confundirlas fabrica el peor fallo posible — un aprobado sobre un arbol sin abrir.

Cazado probando gb en un proyecto JavaScript (8-ago): `gb check --staged` con el
IVA cambiado del 21% al 10% respondia "Sin senales", y `gb calls total` respondia
"nada llamado 'total'" teniendo `total` delante en src/carrito.js.

Estos tests han usado JS y luego Go como "lenguaje sin motor", y las dos veces se
pusieron rojos al entrar ese lenguaje en la tabla — funcionando exactamente como
deben. Hoy usan Haskell. Lo que se fija no es qué lenguaje falta, sino qué se
responde cuando falta.

La otra mitad del contrato, y la que evita que la cura sea peor: sobre codigo que
SI se lee no se avisa de nada. Un aviso de mas tambien es ruido.
"""

import os

from galaxybrain import cli, graph, render


def _escribe(root, rel, contenido=""):
    ruta = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write(contenido)


def _repo_sin_motor(tmp_path):
    """Un repo real de un lenguaje que gb NO sabe analizar."""
    root = str(tmp_path / "app")
    _escribe(root, "Main.hs",
             "module Main where\n\ntotal :: Int -> Int\ntotal x = x * 2\n")
    _escribe(root, "Util.hs", "module Util where\n\nsuma :: Int -> Int -> Int\nsuma a b = a + b\n")
    return root


# --- la frase: lo que hay, y que no se ha mirado -----------------------------


def test_nombra_el_lenguaje_que_no_lee(tmp_path):
    frase = graph.frase_no_leido(_repo_sin_motor(tmp_path))

    assert frase and "Haskell" in frase
    assert "NO he mirado" in frase


def test_lo_que_SI_tiene_motor_no_produce_aviso(tmp_path):
    """La mitad que impide que la cura sea peor que la enfermedad. Este test
    tambien es el que impide que el aviso se quede viejo: el dia que JS entro en
    la tabla, un aviso cableado habria seguido diciendo "no leo JavaScript"."""
    root = str(tmp_path / "js")
    _escribe(root, "src/carrito.js", "export function total(x) { return x * 1.21; }\n")

    assert graph.frase_no_leido(root) is None


def test_sobre_un_repo_python_no_dice_nada(tmp_path):
    root = str(tmp_path / "py")
    _escribe(root, "modulo.py", "def f():\n    return 1\n")

    assert graph.frase_no_leido(root) is None


def test_un_repo_vacio_tampoco_inventa_aviso(tmp_path):
    assert graph.frase_no_leido(str(tmp_path)) is None


# --- check: el veredicto que no se puede dar ---------------------------------


def _informe(root, modulos):
    return {"range": "HEAD~1..HEAD", "test_files_changed": 0, "flags": [], "onda": [],
            "root": root, "coupling": {"base": "HEAD", "modules": modulos,
                                       "new_pairs": [], "new_violations": []}}


def test_check_no_dice_sin_senales_sobre_codigo_que_no_leyo(tmp_path):
    """El fallo grave: enganchado en un pre-commit, seria una gate que aprueba
    sin abrir un fichero."""
    root = _repo_sin_motor(tmp_path)

    salida = render.render_changes(_informe(root, 0), render.Style(False))

    assert "Sin senales" not in salida
    assert "SIN COMPROBAR" in salida and "Haskell" in salida


def test_el_brief_tambien_lo_dice(tmp_path):
    """El brief es justo lo que ve el hook: si miente ahi, no lo ve nadie."""
    root = _repo_sin_motor(tmp_path)

    salida = render.render_changes(_informe(root, 0), render.Style(False), brief=True)

    assert "sin senales" not in salida.lower()
    assert "SIN COMPROBAR" in salida


def test_con_modulos_leidos_el_veredicto_es_legitimo(tmp_path):
    """Control: si se analizo codigo, "sin senales" es una afirmacion ganada y se
    dice sin adornos — aunque el repo tenga ademas ficheros de otro lenguaje."""
    root = _repo_sin_motor(tmp_path)
    _escribe(root, "tools/build.py", "def build():\n    return 1\n")

    salida = render.render_changes(_informe(root, 3), render.Style(False))

    assert "Sin senales" in salida
    assert "SIN COMPROBAR" not in salida


# --- calls: "no esta" vs "no lo veo" -----------------------------------------


def test_calls_sobre_un_lenguaje_sin_motor_declara_el_limite(tmp_path, capsys):
    root = _repo_sin_motor(tmp_path)

    codigo = cli.main(["calls", "total", root])

    salida = capsys.readouterr().out
    assert "nada llamado" not in salida
    assert "no puedo responder" in salida and "Haskell" in salida
    assert codigo == 1


def test_calls_sigue_diciendo_que_no_esta_lo_que_de_verdad_no_esta(tmp_path, capsys):
    """Control imprescindible: la cura no puede tragarse el caso legitimo."""
    root = str(tmp_path / "py")
    _escribe(root, "modulo.py", "def f():\n    return 1\n")

    cli.main(["calls", "no_existe_xyz", root])

    assert "nada llamado 'no_existe_xyz'" in capsys.readouterr().out
