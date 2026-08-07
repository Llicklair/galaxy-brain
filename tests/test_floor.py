"""El suelo: el andamiaje base antes de construir.

La condicion de calidad de este modulo NO es detectar mucho — es **no mentir**. Un
"falta" falso manda a escribir algo que ya existe, y a la segunda vez el informe
deja de leerse. Por eso la mitad de estos tests comprueban que NO diga que falta lo
que si esta, y que declare lo que no puede saber.
"""

import os

from galaxybrain import cli, floor


def _write(root, rel, content=""):
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def _nivel(report, key):
    return next(l for l in report["levels"] if l["key"] == key)


# --- deteccion del comando de tests (regla 6: detectar, nunca asumir) --------


def test_detecta_pytest_por_pyproject(tmp_path):
    root = str(tmp_path)
    _write(root, "pyproject.toml", "[tool.pytest.ini_options]\ntestpaths = ['tests']\n")

    comando, fuente = floor.detect_test_command(root)
    assert comando == "pytest -q"
    assert fuente == "pyproject.toml"


def test_un_repo_go_no_recibe_pytest(tmp_path):
    """Cablear un comando seria un bug (hard rule 6). Un repo Go no corre pytest."""
    root = str(tmp_path)
    _write(root, "go.mod", "module ejemplo\n")

    assert floor.detect_test_command(root)[0] == "go test ./..."


def test_un_repo_node_recibe_npm_test(tmp_path):
    root = str(tmp_path)
    _write(root, "package.json", '{\n "scripts": {\n  "test": "vitest run"\n }\n}\n')

    assert floor.detect_test_command(root)[0] == "npm test"


def test_hay_tests_pero_sin_comando_declarado_se_dice(tmp_path):
    """Ni inventarse un comando ni callar: se dice que hay tests y no como correrlos."""
    root = str(tmp_path)
    _write(root, "tests/test_algo.py", "def test_x():\n    assert 1\n")

    comando, fuente = floor.detect_test_command(root)
    assert comando is None
    assert "tests" in fuente


# --- no mentir sobre lo que si existe ---------------------------------------


def test_encuentra_gb_boundaries_bajo_src(tmp_path):
    """El fallo real de la primera ejecucion: decia 'sin .gb-boundaries' teniendolo
    en src/. Un aviso falso es peor que no avisar."""
    root = str(tmp_path)
    _write(root, "src/.gb-boundaries", "app.core  -/->  app.web\n")

    ruta, reglas = floor.detect_boundaries(root)
    assert ruta == "src/.gb-boundaries"
    assert reglas == 1


def test_sin_adr_es_parcial_no_falta(tmp_path):
    """Solo se puede afirmar que no hay ADR en las rutas convencionales. Las
    decisiones pueden vivir en otros documentos, y esto no las distingue de prosa."""
    root = str(tmp_path)
    _write(root, "DECISIONES.md", "# Por que elegimos X\n")

    nivel = _nivel(floor.analyze(root), "porque")
    assert nivel["status"] == "parcial"
    assert "convencionales" in nivel["detail"]


def test_reconoce_los_adr_convencionales(tmp_path):
    root = str(tmp_path)
    _write(root, "docs/adr/0001-usar-sqlite.md", "# 1. Usar SQLite\n")

    assert _nivel(floor.analyze(root), "porque")["status"] == "ok"


# --- el nivel 1: el unico con numero -----------------------------------------


def test_sin_cronometrar_no_dice_que_es_rapido(tmp_path):
    """Detectar el comando NO es medir el bucle. Dar por bueno lo no medido es
    justo la falsa cobertura que este proyecto lleva toda la sesion cerrando."""
    root = str(tmp_path)
    _write(root, "pyproject.toml", "[tool.pytest.ini_options]\n")

    report = floor.analyze(root)
    assert _nivel(report, "feedback")["status"] == "parcial"
    assert any("cuanto tarda" in item for item in report["not_covered"])


def test_el_umbral_es_el_de_dora(tmp_path):
    assert floor.DORA_FEEDBACK_SECONDS == 600, "diez minutos, la capacidad medida de DORA"


def test_cronometra_de_verdad_cuando_se_pide(tmp_path):
    root = str(tmp_path)
    _write(root, "pyproject.toml", "[tool.pytest.ini_options]\n")

    segundos, ok = floor.time_test_command(root, "python -c \"pass\"")
    assert segundos is not None and segundos >= 0
    assert ok is True


def test_un_comando_que_no_existe_no_revienta_el_informe(tmp_path):
    segundos, ok = floor.time_test_command(str(tmp_path), "comando-que-no-existe-xyz")
    assert ok is False or segundos is not None  # falla, pero devuelve


# --- contexto para agentes ---------------------------------------------------


def test_agents_md_es_el_estandar_y_claude_md_solo_parcial(tmp_path):
    """AGENTS.md lo leen todas las herramientas; CLAUDE.md lo lee una."""
    root = str(tmp_path)
    _write(root, "CLAUDE.md", "# reglas\n")
    assert _nivel(floor.analyze(root), "agentes")["status"] == "parcial"

    _write(root, "AGENTS.md", "# reglas\n")
    assert _nivel(floor.analyze(root), "agentes")["status"] == "ok"


# --- el contrato del informe -------------------------------------------------


def test_el_criterio_de_terminado_nunca_se_da_por_cubierto(tmp_path):
    """No lo puede mirar ninguna herramienta. Marcarlo 'ok' alguna vez seria mentir."""
    report = floor.analyze(str(tmp_path))
    assert _nivel(report, "terminado")["status"] == "no-detectable"


def test_declara_lo_delegado_y_lo_no_cubierto(tmp_path):
    report = floor.analyze(str(tmp_path))
    assert any("Scorecard" in item for item in report["delegated"]), "regla 7: por referencia"
    assert report["not_covered"]
    assert any("techo" in item for item in report["not_covered"])


def test_un_suelo_incompleto_no_bloquea(tmp_path):
    """Es una lista de lo que falta, no un delito. Gatearlo lo volveria ceremonia,
    y la ceremonia fue lo que mato al enfoque anterior."""
    assert cli.main(["floor", str(tmp_path), "--color", "never"]) == 0


# --- el esqueleto: poner los imprescindibles sin fabricar suelo de mentira ----


def test_init_deja_los_imprescindibles(tmp_path):
    root = str(tmp_path)
    hechos = floor.scaffold(root)

    # los ficheros imprescindibles MAS el enganche del pre-commit y el ignore
    # del mapa (7-ago: la conexion no se sugiere, se hace; y el mapa derivado
    # no puede vivir ensuciando el arbol)
    extras = {"core.hooksPath", ".gitignore"}
    assert {h["path"] for h in hechos} == set(floor.SCAFFOLD_FILES) | extras
    assert all(h["action"] == "creado" for h in hechos if h["path"] not in extras)
    assert [h["action"] for h in hechos if h["path"] == "core.hooksPath"] == ["sin-git"]
    assert [h["action"] for h in hechos if h["path"] == ".gitignore"] == ["mapa.html ignorado"]
    for rel in floor.SCAFFOLD_FILES:
        assert os.path.exists(os.path.join(root, *rel.split("/")))


def test_init_NUNCA_pisa_lo_que_ya_existe(tmp_path):
    """Un esqueleto que sobreescribe la ley de un proyecto es peor que no existir."""
    root = str(tmp_path)
    _write(root, "SCOPE.md", "# mi alcance, escrito a mano\n")

    hechos = {h["path"]: h["action"] for h in floor.scaffold(root)}

    assert hechos["SCOPE.md"] == "ya-existia"
    assert "escrito a mano" in open(os.path.join(root, "SCOPE.md"), encoding="utf-8").read()


def test_agents_md_sale_prerelleno_con_lo_detectado(tmp_path):
    """Lo detectable se escribe con su valor real, no como hueco: eso lo pone en el
    nivel que se ejecuta, y lo que se ejecuta no puede pudrirse en silencio."""
    root = str(tmp_path)
    _write(root, "go.mod", "module ejemplo\n")
    floor.scaffold(root)

    contenido = open(os.path.join(root, "AGENTS.md"), encoding="utf-8").read()
    assert "go test ./..." in contenido


def test_un_esqueleto_sin_rellenar_no_cuenta_como_suelo(tmp_path):
    """El cierre del lazo: --init lo crea marcado y analyze lo delata. Un documento
    que existe y no dice nada pasa la lista sin aportar nada."""
    root = str(tmp_path)
    floor.scaffold(root)

    report = floor.analyze(root)
    assert "AGENTS.md" in report["pending"]
    assert _nivel(report, "agentes")["status"] == "esqueleto"


def test_rellenarlo_lo_convierte_en_cubierto(tmp_path):
    root = str(tmp_path)
    floor.scaffold(root)
    _write(root, "AGENTS.md", "# mi proyecto\n\n## Comandos\n\n```bash\npytest -q\n```\n")

    report = floor.analyze(root)
    assert "AGENTS.md" not in report["pending"]
    assert _nivel(report, "agentes")["status"] == "ok"


def test_el_readme_de_adr_no_cuenta_como_decision(tmp_path):
    """Lo crea el propio --init: contarlo dejaria al esqueleto aprobandose a si
    mismo, con cero decisiones registradas."""
    root = str(tmp_path)
    floor.scaffold(root)

    assert _nivel(floor.analyze(root), "porque")["status"] == "parcial"

    _write(root, "docs/adr/0001-usar-sqlite.md", "# 1. Usar SQLite\n")
    assert _nivel(floor.analyze(root), "porque")["status"] == "ok"


def test_init_por_cli_no_bloquea(tmp_path):
    assert cli.main(["floor", str(tmp_path), "--init", "--color", "never"]) == 0


def test_raiz_inexistente_si_es_error(tmp_path):
    root = os.path.join(str(tmp_path), "no-existe")
    assert floor.analyze(root)["root_error"]
    assert cli.main(["floor", root, "--color", "never"]) == 1


def test_detecta_pyrefly_como_gate_de_tipos(tmp_path):
    """pyrefly es el checker de tipos rapido del mercado (Rust, <10 ms); no verlo
    seria el "falta" falso que este modulo existe para no fabricar: mandaria a
    instalar mypy a quien ya tiene los tipos gateados."""
    root = str(tmp_path / "a")
    _write(root, "pyrefly.toml", 'project-includes = ["src"]\n')
    assert floor.detect_gates(root).get("tipos") == "pyrefly.toml"

    root = str(tmp_path / "b")
    _write(root, "pyproject.toml", "[tool.pyrefly]\nproject-includes = ['src']\n")
    assert "pyrefly" in floor.detect_gates(root).get("tipos", "")
