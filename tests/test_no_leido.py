"""Nunca un veredicto sobre codigo que no se ha leido.

Siempre existira un lenguaje que gb no parsea, asi que esto no es un paso
intermedio hacia el multilenguaje: es la conducta permanente en la frontera.
"No lo veo" y "no esta" son afirmaciones distintas, y confundirlas fabrica el
peor fallo posible — un aprobado sobre un arbol sin abrir.

Cazado probando gb en un proyecto JavaScript (8-ago): `gb check --staged` con el
IVA cambiado del 21% al 10% respondia "Sin senales", y `gb calls total` respondia
"nada llamado 'total'" teniendo `total` delante en src/carrito.js.

La otra mitad del contrato, y la que evita que la cura sea peor: sobre un repo
Python de verdad NO se avisa de nada. Un aviso de mas tambien es ruido.
"""

import os
import subprocess

from galaxybrain import cli, graph, render


def _escribe(root, rel, contenido=""):
    ruta = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write(contenido)


def _repo_js(tmp_path):
    root = str(tmp_path / "app")
    os.makedirs(root, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True, capture_output=True)
    _escribe(root, "package.json", '{"scripts": {"test": "vitest run"}}\n')
    _escribe(root, "src/carrito.js", "export function total(x) { return x * 1.21; }\n")
    _escribe(root, "src/factura.js", 'import { total } from "./carrito.js";\n')
    return root


# --- la frase: lo que hay, y que no se ha mirado -----------------------------


def test_nombra_el_lenguaje_que_no_lee(tmp_path):
    root = _repo_js(tmp_path)

    frase = graph.frase_no_leido(root)

    assert frase and "JavaScript" in frase
    assert "NO he mirado" in frase


def test_sobre_un_repo_python_no_dice_nada(tmp_path):
    """La mitad que impide que la cura sea peor que la enfermedad: si no hay
    nada de otro lenguaje que excusar, no hay aviso. El ruido es lo que hace
    que un informe deje de leerse."""
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
    """El fallo grave: enganchado en un pre-commit de un repo JS, seria una gate
    que aprueba sin abrir un fichero."""
    root = _repo_js(tmp_path)

    salida = render.render_changes(_informe(root, 0), render.Style(False))

    assert "Sin senales" not in salida
    assert "SIN COMPROBAR" in salida and "JavaScript" in salida


def test_el_brief_tambien_lo_dice(tmp_path):
    """El brief es justo lo que ve el hook: si miente ahi, no lo ve nadie."""
    root = _repo_js(tmp_path)

    salida = render.render_changes(_informe(root, 0), render.Style(False), brief=True)

    assert "sin senales" not in salida.lower()
    assert "SIN COMPROBAR" in salida


def test_con_modulos_python_leidos_el_veredicto_es_legitimo(tmp_path):
    """Control: si se leyo Python, "sin senales" es una afirmacion ganada y se
    dice sin adornos — aunque el repo tenga ademas ficheros JS."""
    root = _repo_js(tmp_path)
    _escribe(root, "tools/build.py", "def build():\n    return 1\n")

    salida = render.render_changes(_informe(root, 3), render.Style(False))

    assert "Sin senales" in salida
    assert "SIN COMPROBAR" not in salida


# --- calls: "no esta" vs "no lo veo" -----------------------------------------


def test_calls_sobre_js_declara_el_limite_en_vez_de_negar(tmp_path, capsys):
    root = _repo_js(tmp_path)

    codigo = cli.main(["calls", "total", root])

    salida = capsys.readouterr().out
    assert "nada llamado" not in salida
    assert "no puedo responder" in salida and "JavaScript" in salida
    assert codigo == 1


def test_calls_sigue_diciendo_que_no_esta_lo_que_de_verdad_no_esta(tmp_path, capsys):
    """Control imprescindible: la cura no puede tragarse el caso legitimo."""
    root = str(tmp_path / "py")
    _escribe(root, "modulo.py", "def f():\n    return 1\n")

    cli.main(["calls", "no_existe_xyz", root])

    assert "nada llamado 'no_existe_xyz'" in capsys.readouterr().out
