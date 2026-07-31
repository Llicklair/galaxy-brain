"""El delta de forma: en tiempo real se dice QUE cambio, no el mapa otra vez.

Criterio de terminado, escrito antes de implementarlo:
  1. La forma completa persiste en disco y sobrevive a reinicios (por eso se
     guarda entera y no como un hash: con un hash solo se sabe QUE cambio).
  2. Cuando cambia, el aviso desglosa el cambio en vez de repetir el mapa.
  3. Cuando no cambia, cero bytes.
  4. La primera vez en un proyecto —sin forma previa— sale el mapa entero, no un
     delta vacio ni un desglose inventado contra la nada.

Las bajas se prueban igual que las altas: si solo se contaran las altas, quien lee
se quedaria creyendo que un ciclo resuelto sigue ahi.
"""

import os

from galaxybrain import graph, render


def _write(root, rel, content):
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def _forma(root):
    return graph.shape(graph.analyze(root))


def _base(root):
    _write(root, "pkg/__init__.py", "")
    _write(root, "pkg/a.py", "def f():\n    return 1\n")
    _write(root, "pkg/b.py", "def g():\n    return 2\n")


def test_sin_forma_previa_no_hay_delta_posible(tmp_path):
    """Criterio 4: `None` significa "ensena el mapa entero", no "no ha cambiado"."""
    root = str(tmp_path)
    _base(root)
    assert graph.shape_delta(None, _forma(root)) is None


def test_misma_forma_delta_vacio(tmp_path):
    root = str(tmp_path)
    _base(root)
    antes = _forma(root)
    _write(root, "pkg/a.py", "def f():\n    total = 40 + 2\n    return total\n")
    assert graph.shape_delta(antes, _forma(root)) == {}


def test_un_import_nuevo_sale_como_arista_no_como_mapa(tmp_path):
    root = str(tmp_path)
    _base(root)
    antes = _forma(root)
    _write(root, "pkg/a.py", "from . import b\n")

    delta = graph.shape_delta(antes, _forma(root))
    assert delta["edges_added"] == [("pkg.a", "pkg.b")]
    assert not delta["modules_added"]

    texto = render.render_graph_delta(delta, "demo")
    assert "pkg.a->pkg.b" in texto
    assert "modulos," not in texto  # NO es el mapa: es lo que cambio


def test_un_ciclo_nuevo_va_primero_y_entero(tmp_path):
    root = str(tmp_path)
    _base(root)
    _write(root, "pkg/a.py", "from . import b\n")
    antes = _forma(root)
    _write(root, "pkg/b.py", "from . import a\n")

    delta = graph.shape_delta(antes, _forma(root))
    assert delta["cycles_added"]
    texto = render.render_graph_delta(delta, "demo")
    assert texto.splitlines()[1].strip().startswith("CICLO NUEVO")


def test_lo_que_se_arregla_tambien_se_dice(tmp_path):
    """Un ciclo resuelto y un modulo borrado son noticia: sin ellos, el mapa
    mental de quien lee se queda con cosas que ya no existen."""
    root = str(tmp_path)
    _base(root)
    _write(root, "pkg/a.py", "from . import b\n")
    _write(root, "pkg/b.py", "from . import a\n")
    _write(root, "pkg/sobra.py", "")
    antes = _forma(root)

    _write(root, "pkg/b.py", "def g():\n    return 2\n")
    os.remove(os.path.join(root, "pkg", "sobra.py"))

    delta = graph.shape_delta(antes, _forma(root))
    assert delta["cycles_removed"]
    assert delta["modules_removed"] == ["pkg.sobra"]
    texto = render.render_graph_delta(delta, "demo")
    assert "ciclo resuelto" in texto
    assert "-modulos" in texto


def test_un_refactor_grande_se_resume_en_vez_de_listarlo_todo(tmp_path):
    """Una lista de 40 modulos no se lee: se cuenta y se muestran unos pocos."""
    root = str(tmp_path)
    _base(root)
    antes = _forma(root)
    for i in range(12):
        _write(root, "pkg/m%d.py" % i, "")

    texto = render.render_graph_delta(graph.shape_delta(antes, _forma(root)), "demo")
    assert "+modulos 12:" in texto
    assert "+8 mas" in texto  # 4 mostrados, el resto contados


def test_la_forma_sobrevive_a_ir_y_volver_por_json(tmp_path):
    """Criterio 1: lo que se guarda en disco tiene que volver comparable, o cada
    arranque de sesion diria que todo ha cambiado."""
    import json

    root = str(tmp_path)
    _base(root)
    forma = _forma(root)
    ida_y_vuelta = json.loads(json.dumps(forma, ensure_ascii=False))
    assert graph.shape_delta(ida_y_vuelta, forma) == {}
