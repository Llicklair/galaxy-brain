"""El grafo de símbolos. Lo que se comprueba aquí NO es cuánto resuelve, sino que
**no se invente nada** y que **diga cuánto no ve**.

Una arista falsa en un grafo de llamadas es peor que una arista ausente: la ausente
se nota al usarlo, la falsa se cree. Por eso la mitad de estos tests comprueban que
ante la duda no salga arista, y que el número de las no resueltas esté a la vista.
"""

import os

from galaxybrain import symbols


def _write(root, rel, content):
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def _calls(report):
    return {(a, b) for a, b, tipo in report["edges"] if tipo == "CALLS"}


# --- lo que SI es un hecho sintactico ---------------------------------------


def test_resuelve_una_llamada_por_nombre(tmp_path):
    root = str(tmp_path)
    _write(root, "app/__init__.py", "")
    _write(root, "app/core.py", "def ayuda():\n    return 1\n\ndef principal():\n    return ayuda()\n")

    assert ("app.core.principal", "app.core.ayuda") in _calls(symbols.analyze(root))


def test_resuelve_a_traves_de_un_import(tmp_path):
    root = str(tmp_path)
    _write(root, "app/__init__.py", "")
    _write(root, "app/util.py", "def limpia(x):\n    return x\n")
    _write(root, "app/core.py", "from app.util import limpia\n\ndef principal():\n    return limpia(1)\n")

    assert ("app.core.principal", "app.util.limpia") in _calls(symbols.analyze(root))


def test_resuelve_un_nombre_reexportado_por_otro_modulo(tmp_path):
    """`otro.nombre()` donde `otro` no lo define: lo importó con otro nombre.

    Es el patrón que `bancos/oraculo_aristas.py` señaló el 10-ago-2026 como la
    única causa sin puerta de las llamadas reales que el grafo no veía — en este
    mismo repo, `changes._git_output` es `graph._git`.
    """
    root = str(tmp_path)
    _write(root, "app/__init__.py", "")
    _write(root, "app/base.py", "def crudo(x):\n    return x\n")
    _write(root, "app/medio.py", "from app.base import crudo as envuelto\n")
    _write(root, "app/core.py",
           "from app import medio\n\ndef principal():\n    return medio.envuelto(1)\n")

    assert ("app.core.principal", "app.base.crudo") in _calls(symbols.analyze(root))


def test_la_reexportacion_en_circulo_no_cuelga(tmp_path):
    """Dos módulos que se re-exportan mutuamente: se corta, no se gira."""
    root = str(tmp_path)
    _write(root, "app/__init__.py", "")
    _write(root, "app/a.py", "from app.b import ping as pong\n")
    _write(root, "app/b.py", "from app.a import pong as ping\n")
    _write(root, "app/core.py",
           "from app import a\n\ndef principal():\n    return a.pong(1)\n")

    # Lo que importa es que TERMINE y no invente: no hay def en ningún extremo.
    assert not [p for p in _calls(symbols.analyze(root)) if p[0] == "app.core.principal"]


def test_resuelve_self_punto_metodo(tmp_path):
    """`self.metodo()` si es demostrable: el metodo esta escrito ahi al lado."""
    root = str(tmp_path)
    _write(root, "app/__init__.py", "")
    _write(
        root, "app/svc.py",
        "class Servicio:\n"
        "    def interno(self):\n        return 1\n"
        "    def publico(self):\n        return self.interno()\n",
    )

    assert ("app.svc.Servicio.publico", "app.svc.Servicio.interno") in _calls(symbols.analyze(root))


def test_registra_herencia_cuando_la_base_es_del_proyecto(tmp_path):
    root = str(tmp_path)
    _write(root, "app/__init__.py", "")
    _write(root, "app/base.py", "class Base:\n    pass\n")
    _write(root, "app/hijo.py", "from app.base import Base\n\nclass Hijo(Base):\n    pass\n")

    extiende = {(a, b) for a, b, t in symbols.analyze(root)["edges"] if t == "EXTENDS"}
    assert ("app.hijo.Hijo", "app.base.Base") in extiende


# --- lo que NO es un hecho: no se adivina, se cuenta -------------------------


def test_no_inventa_arista_para_un_metodo_sobre_una_variable(tmp_path):
    """El limite real de la tecnica. Saber a que apunta `objeto` exige inferir tipos;
    adivinarlo produce una arista falsa, que es peor que ninguna."""
    root = str(tmp_path)
    _write(root, "app/__init__.py", "")
    _write(root, "app/otro.py", "class Cosa:\n    def hacer(self):\n        return 1\n")
    _write(
        root, "app/core.py",
        "def principal(objeto):\n    return objeto.hacer()\n",
    )

    report = symbols.analyze(root)
    assert not any(b.endswith(".hacer") for _a, b in _calls(report)), "no puede inventarsela"
    assert report["unresolved"].get("atributo-de-variable", 0) >= 1, "pero tiene que contarla"


def test_los_builtins_no_hunden_la_cobertura(tmp_path):
    """`len()` no es un simbolo del proyecto: no resolverla es lo correcto, no un
    fallo. Meterla en el denominador hacia parecer inutil una tecnica que no lo es —
    fue el primer numero que dio este modulo."""
    root = str(tmp_path)
    _write(root, "app/__init__.py", "")
    _write(
        root, "app/core.py",
        "def ayuda():\n    return 1\n\n"
        "def principal(xs):\n    return len(xs) + sorted(xs)[0] + ayuda()\n",
    )

    report = symbols.analyze(root)
    assert report["calls_builtin"] >= 2
    assert report["calls_candidates"] == report["calls_total"] - report["calls_builtin"]
    assert symbols.coverage(report) == 1.0, "la unica candidata era ayuda(), y se resolvio"


def test_siempre_declara_lo_que_no_puede_ver(tmp_path):
    report = symbols.analyze(str(tmp_path))

    assert report["not_covered"]
    assert any("inferencia de tipos" in item for item in report["not_covered"])
    assert any("dinamico" in item for item in report["not_covered"])


def test_la_cobertura_es_un_suelo_no_una_cifra_exacta(tmp_path):
    """El denominador conserva metodos de objetos de stdlib (`handle.read()`), que
    tampoco eran del proyecto. Se documenta como suelo en vez de venderlo mejor."""
    assert "suelo" in symbols.coverage.__doc__


# --- contrato general --------------------------------------------------------


def test_es_determinista(tmp_path):
    root = str(tmp_path)
    _write(root, "app/__init__.py", "")
    _write(root, "app/core.py", "def a():\n    return b()\n\ndef b():\n    return 1\n")

    assert symbols.analyze(root)["edges"] == symbols.analyze(root)["edges"]


def test_un_fichero_roto_no_tumba_el_barrido(tmp_path):
    root = str(tmp_path)
    _write(root, "app/__init__.py", "")
    _write(root, "app/roto.py", "def (((\n")
    _write(root, "app/bueno.py", "def vale():\n    return 1\n")

    report = symbols.analyze(root)
    assert report["errors"], "el fichero roto se reporta"
    assert any(n["qual"] == "app.bueno.vale" for n in report["nodes"]), "y el resto se analiza"


def test_raiz_inexistente_es_error(tmp_path):
    assert symbols.analyze(os.path.join(str(tmp_path), "no-existe"))["root_error"]


def test_since_marca_lo_nuevo_leyendo_de_git(tmp_path):
    """La pelicula sin indice: la baseline sale de git, no de una cache — una
    cache puede mentir (el indice de GitNexus quedo 6 commits desfasado el mismo
    dia que se midio contra el). Nuevo = en el working tree y no en la ref."""
    import subprocess

    root = str(tmp_path)
    def _run(*a): subprocess.run(a, cwd=root, check=True, capture_output=True)
    _write(root, "app/__init__.py", "")
    _write(root, "app/core.py", "def vieja():\n    return 1\n")
    _run("git", "init", "-q")
    _run("git", "config", "user.email", "t@t")
    _run("git", "config", "user.name", "t")
    _run("git", "config", "commit.gpgsign", "false")
    _run("git", "add", "-A")
    _run("git", "commit", "-q", "-m", "base")
    _write(root, "app/core.py", "def vieja():\n    return 1\n\ndef nueva():\n    return vieja()\n")

    report = symbols.analyze(root, since="HEAD")
    assert report["baseline_ok"] is True
    assert "app.core.nueva" in report["new_nodes"]
    assert ["app.core.nueva", "app.core.vieja"] in report["new_calls"]
    assert "app.core.vieja" not in report["new_nodes"], "lo preexistente no es nuevo"


def test_since_sin_repo_lo_dice_no_lo_calla(tmp_path):
    root = str(tmp_path)
    _write(root, "app/core.py", "def f():\n    return 1\n")

    report = symbols.analyze(root, since="HEAD")
    assert report["baseline_ok"] is False
    assert any("baseline" in x for x in report["not_covered"])
