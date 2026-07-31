"""El payload de sesion: el mapa que llega sin que nadie se acuerde de pedirlo.

Motivo (ARCHITECTURE regla 11, ultima frase): lo que hace inevitable una senal no es
que bloquee, es que salga SIEMPRE, delante de quien decide. `graph` ya producia el
hecho; lo que faltaba era que llegara solo.

Lo que fijan estos tests es sobre todo el SILENCIO, que es la mitad fragil. Un
payload que habla cuando no tiene nada nuevo que decir se inyecta en cada sesion y
en cada edicion — y entonces deja de leerse, que es como muere una senal.
"""

import os

from galaxybrain import cli, graph, render


def _write(root, rel, content):
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def test_el_payload_trae_la_forma_de_una_pasada(tmp_path):
    root = str(tmp_path)
    _write(root, "pkg/__init__.py", "")
    _write(root, "pkg/a.py", "from . import b\n")
    _write(root, "pkg/b.py", "")

    payload = render.render_graph_context(graph.analyze(root))
    assert "3 modulos" in payload
    assert "1 aristas" in payload
    assert "pkg.b<-1" in payload  # quien es el nucleo, no solo cuantos hay


def test_sin_modulos_el_payload_es_cero_bytes(tmp_path):
    """Criterio 2. En un proyecto que no es Python no hay nada que mapear, y un
    payload que anuncia "0 modulos" seria ruido inyectado en cada sesion."""
    (tmp_path / "README.md").write_text("solo prosa", encoding="utf-8")
    assert render.render_graph_context(graph.analyze(str(tmp_path))) == ""


def test_una_raiz_que_no_existe_calla(tmp_path):
    """Falla en silencio hacia el lado seguro (regla 9): un hook con una ruta mal
    puesta no debe escupir un error dentro del contexto de cada sesion."""
    assert render.render_graph_context(graph.analyze(str(tmp_path / "no-existe"))) == ""


def test_los_ciclos_van_enteros_y_arriba(tmp_path):
    """Es la unica salida de graph que detiene un commit: no se resume."""
    root = str(tmp_path)
    _write(root, "pkg/__init__.py", "")
    _write(root, "pkg/a.py", "from . import b\n")
    _write(root, "pkg/b.py", "from . import a\n")

    payload = render.render_graph_context(graph.analyze(root))
    assert "CICLO" in payload
    # Por delante solo el titular y el alcance: el hecho que bloquea va arriba.
    lineas = [l.strip() for l in payload.splitlines()]
    assert lineas[2].startswith("CICLO")


def test_la_huella_ignora_el_cuerpo_y_ve_la_forma(tmp_path):
    """Criterio 3, el que hace util el modo tiempo real: reescribir el cuerpo de
    una funcion NO debe repetir el mapa; anadir un import SI."""
    root = str(tmp_path)
    _write(root, "pkg/__init__.py", "")
    _write(root, "pkg/a.py", "def f():\n    return 1\n")
    _write(root, "pkg/b.py", "def g():\n    return 2\n")
    antes = graph.fingerprint(graph.analyze(root))

    _write(root, "pkg/a.py", "def f():\n    total = 40 + 2\n    return total\n")
    assert graph.fingerprint(graph.analyze(root)) == antes

    _write(root, "pkg/a.py", "from . import b\n\n\ndef f():\n    return b.g()\n")
    assert graph.fingerprint(graph.analyze(root)) != antes


def test_un_modulo_nuevo_y_suelto_ya_cambia_la_forma(tmp_path):
    """No trae aristas: si la huella solo mirara `edge_list`, esto pasaria mudo."""
    root = str(tmp_path)
    _write(root, "pkg/__init__.py", "")
    _write(root, "pkg/a.py", "")
    antes = graph.fingerprint(graph.analyze(root))

    _write(root, "pkg/nuevo.py", "")
    assert graph.fingerprint(graph.analyze(root)) != antes


def test_la_misma_carpeta_escrita_distinto_comparte_cache(tmp_path):
    """En Windows `c:\\x` y `C:\\x` son la MISMA carpeta, y abspath no unifica la
    letra de unidad. Cuando no coincidian, el cache no acertaba nunca y
    --if-changed dejaba de callar: el mapa entero repetido en cada edicion."""
    base = str(tmp_path)
    variantes = {base, base.replace(os.sep, "/"), os.path.join(base, "sub", "..")}
    if base[1:2] == ":":  # Windows: la misma unidad en las dos cajas
        variantes |= {base[0].lower() + base[1:], base[0].upper() + base[1:]}

    claves = {cli._shape_cache(v).name for v in variantes}
    assert len(claves) == 1, "una carpeta, una clave: %s" % claves


def test_dos_proyectos_distintos_no_se_pisan_el_cache(tmp_path):
    uno = cli._shape_cache(str(tmp_path / "proyecto-a"))
    otro = cli._shape_cache(str(tmp_path / "proyecto-b"))
    assert uno != otro


def test_un_ciclo_nuevo_cambia_la_forma(tmp_path):
    root = str(tmp_path)
    _write(root, "pkg/__init__.py", "")
    _write(root, "pkg/a.py", "from . import b\n")
    _write(root, "pkg/b.py", "")
    antes = graph.fingerprint(graph.analyze(root))

    _write(root, "pkg/b.py", "from . import a\n")
    assert graph.fingerprint(graph.analyze(root)) != antes
