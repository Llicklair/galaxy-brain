"""Reglas de frontera (`.gb-boundaries`): declarar qué capa no puede importar a
cuál y fallar en los cruces. Un cruce prohibido es un hecho (lo declaraste), así
que la barra de casi-cero-falsos-positivos se cubre comprobando (a) que sin
fichero no hay reglas y (b) que la frontera es de punto (no casa por prefijo laxo)."""

import os

from galaxybrain import graph


def _write(root, rel, content):
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def test_load_boundaries_parsea(tmp_path):
    root = str(tmp_path)
    _write(
        root,
        ".gb-boundaries",
        "# reglas de capas\n  web -/-> db  \n\ndomain -/-> web   # comentario\nlinea sin flecha\n",
    )
    parsed = graph.load_boundaries(root)
    rules = parsed["rules"]
    assert ("web", "db") in rules
    assert ("domain", "web") in rules
    assert len(rules) == 2  # los comentarios se ignoran
    assert "linea sin flecha" in parsed["malformed"]  # línea con contenido pero sin -/-> : se avisa
    assert parsed["error"] is None


def test_under_es_frontera_de_punto():
    assert graph._under("myapp.web", "myapp.web")
    assert graph._under("myapp.web.handlers", "myapp.web")
    assert not graph._under("myapp.website", "myapp.web")  # sin falso positivo por prefijo laxo
    assert not graph._under("myapp", "myapp.web")


def test_analyze_detecta_cruce_prohibido(tmp_path):
    root = str(tmp_path)
    _write(root, ".gb-boundaries", "app.web -/-> app.db\n")
    _write(root, "app/__init__.py", "")
    _write(root, "app/web.py", "from app import db\n")  # cruce prohibido
    _write(root, "app/db.py", "")

    report = graph.analyze(root)
    assert report["boundaries"] == 1
    assert any(
        v["importer"] == "app.web" and v["imported"] == "app.db" for v in report["violations"]
    )


def test_sin_fichero_de_fronteras_no_hay_reglas(tmp_path):
    root = str(tmp_path)
    _write(root, "app/__init__.py", "")
    _write(root, "app/web.py", "from app import db\n")
    _write(root, "app/db.py", "")

    report = graph.analyze(root)  # la gate de fronteras es opt-in
    assert report["boundaries"] == 0
    assert report["violations"] == []


def test_frontera_de_punto_no_da_falso_positivo(tmp_path):
    root = str(tmp_path)
    _write(root, ".gb-boundaries", "app.web -/-> app.db\n")
    _write(root, "app/__init__.py", "")
    _write(root, "app/website.py", "from app import db\n")  # website != web: NO viola
    _write(root, "app/db.py", "")

    assert graph.analyze(root)["violations"] == []


def test_regla_que_no_casa_ningun_modulo_se_avisa(tmp_path):
    """El footgun: una regla que no casa con nada (typo o raíz equivocada) nunca
    dispara y da falsa sensación de cobertura. Debe avisarse."""
    root = str(tmp_path)
    _write(root, ".gb-boundaries", "app.web -/-> app.db\ninexistente.x -/-> app.db\n")
    _write(root, "app/__init__.py", "")
    _write(root, "app/web.py", "")
    _write(root, "app/db.py", "")

    report = graph.analyze(root)
    avisadas = [u["rule"] for u in report["unmatched_rules"]]
    assert "inexistente.x -/-> app.db" in avisadas
    assert "app.web -/-> app.db" not in avisadas  # esa sí casa (web y db existen)


def test_regla_con_flecha_mal_escrita_es_malformed_no_muda(tmp_path):
    """El footgun del review: `-->` en vez de `-/->` antes se descartaba en
    silencio y la frontera no enforced nada sin aviso."""
    root = str(tmp_path)
    _write(root, ".gb-boundaries", "app.web --> app.db\n")  # flecha mal
    _write(root, "app/__init__.py", "")

    report = graph.analyze(root)
    assert report["boundaries"] == 0
    assert "app.web --> app.db" in report["malformed_boundaries"]


def test_dos_flechas_en_una_linea_es_malformed(tmp_path):
    root = str(tmp_path)
    _write(root, ".gb-boundaries", "a -/-> b -/-> c\n")
    _write(root, "app/__init__.py", "")

    report = graph.analyze(root)
    assert report["boundaries"] == 0  # no produce una regla basura
    assert report["malformed_boundaries"]


def test_boundaries_explicito_inexistente_es_error(tmp_path):
    root = str(tmp_path)
    _write(root, "app/__init__.py", "")
    report = graph.analyze(root, boundaries=os.path.join(root, "no-existe.txt"))
    assert report["boundaries_error"]  # ruta explícita ausente -> error, no silencio


def test_default_ausente_no_es_error(tmp_path):
    root = str(tmp_path)
    _write(root, "app/__init__.py", "")
    report = graph.analyze(root)  # sin fichero por defecto = opt-in, sin error
    assert report["boundaries_error"] is None


def test_gate_falla_con_config_de_reglas_rota(tmp_path):
    """La gate NUNCA pasa en verde con reglas que no enforced nada."""
    root = str(tmp_path)
    _write(root, "app/__init__.py", "")

    from galaxybrain import cli

    _write(root, ".gb-boundaries", "app.web --> app.db\n")  # flecha mal
    assert cli.main(["graph", root, "--gate", "--color", "never"]) == 1

    _write(root, ".gb-boundaries", "inexistente.x -/-> tampoco.y\n")  # no casa nada
    assert cli.main(["graph", root, "--gate", "--color", "never"]) == 1

    # fichero explícito ilegible
    assert (
        cli.main(["graph", root, "--gate", "--boundaries", os.path.join(root, "typo.txt"), "--color", "never"])
        == 1
    )


def test_cli_gate_falla_con_cruce_y_pasa_sin_el(tmp_path):
    root = str(tmp_path)
    _write(root, ".gb-boundaries", "app.web -/-> app.db\n")
    _write(root, "app/__init__.py", "")
    _write(root, "app/db.py", "")
    _write(root, "app/web.py", "from app import db\n")  # viola

    from galaxybrain import cli

    assert cli.main(["graph", root, "--gate", "--color", "never"]) == 1
    _write(root, "app/web.py", "X = 1\n")  # respeta la regla
    assert cli.main(["graph", root, "--gate", "--color", "never"]) == 0
