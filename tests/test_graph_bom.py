"""El BOM de UTF-8 no puede borrar un fichero del mapa.

Python compila un `.py` con BOM sin pestanear — el interprete lo descarta al
decodificar. Pero `ast.parse` sobre el texto YA decodificado ve un U+FEFF y lanza
SyntaxError, asi que el fichero caia en `errors` y sus imports desaparecian del
grafo. En Windows eso no es un caso raro: PowerShell y varios editores escriben
UTF-8 con BOM por defecto, y el fallo era mudo (un "sin ciclos" comodo y falso).
"""

import os

from galaxybrain import graph, symbols


def _write(root, rel, content):
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def test_la_premisa_del_bug_leer_en_utf8_pelado_lo_rompe(tmp_path):
    """La premisa, fijada: si dejara de ser verdad, el arreglo sobra.

    El BOM lo quita la DECODIFICACION del fichero, no el compilador — por eso
    `python fichero.py` funciona y `ast.parse(open(...utf-8...).read())` no.
    """
    import ast

    import pytest

    path = tmp_path / "conbom.py"
    path.write_text(graph._BOM + "x = 1\n", encoding="utf-8")

    with pytest.raises(SyntaxError):
        ast.parse(path.read_text(encoding="utf-8"))
    ast.parse(path.read_text(encoding="utf-8-sig"))  # y asi si


def test_un_fichero_con_bom_conserva_sus_aristas(tmp_path):
    root = str(tmp_path)
    _write(root, "pkg/__init__.py", "")
    _write(root, "pkg/a.py", graph._BOM + "from . import b\n")
    _write(root, "pkg/b.py", "")

    report = graph.analyze(root)
    assert report["errors"] == {}
    assert report["edges"] == 1


def test_un_ciclo_no_se_esconde_detras_de_un_bom(tmp_path):
    """El caso caro: la gate daba verde porque los dos ficheros del ciclo no
    parseaban. Un falso negativo en la unica salida de graph que bloquea."""
    root = str(tmp_path)
    _write(root, "pkg/__init__.py", "")
    _write(root, "pkg/a.py", graph._BOM + "from . import b\n")
    _write(root, "pkg/b.py", graph._BOM + "from . import a\n")

    report = graph.analyze(root)
    assert len(report["cycles"]) == 1


def test_symbols_tampoco_pierde_el_fichero(tmp_path):
    root = str(tmp_path)
    _write(root, "pkg/__init__.py", "")
    _write(root, "pkg/a.py", graph._BOM + "def suma(a, b):\n    return a + b\n")

    report = symbols.analyze(root)
    assert any(n["qual"].endswith("suma") for n in report["nodes"])


def test_un_bom_no_invalida_la_primera_regla_de_frontera(tmp_path):
    """Mismo bug, otra puerta: con BOM, la primera linea de `.gb-boundaries` se
    leia como basura y acababa en `malformed` — enforced nada, en silencio."""
    path = tmp_path / ".gb-boundaries"
    path.write_text(graph._BOM + "pkg.a  -/->  pkg.b\n", encoding="utf-8")

    info = graph.load_boundaries(str(tmp_path), str(path))
    assert info["rules"] == [("pkg.a", "pkg.b")]
    assert info["malformed"] == []
