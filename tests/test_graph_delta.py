"""El delta gate: fallar solo con acoplamiento cíclico NUEVO vs una baseline de
git. La condición de calidad es no dar falsos positivos — por eso los tests
cubren explícitamente que un ciclo preexistente y encoger un ciclo NO cuentan
como regresión."""

import os
import subprocess

from galaxybrain import graph


def _run(cwd, *args):
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


def _write(root, rel, content):
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def _init_repo(root):
    _run(root, "git", "init", "-q")
    _run(root, "git", "config", "user.email", "t@t")
    _run(root, "git", "config", "user.name", "t")
    _run(root, "git", "config", "commit.gpgsign", "false")  # config del repo de test, no del usuario


def _commit(root, msg):
    _run(root, "git", "add", "-A")
    _run(root, "git", "commit", "-q", "-m", msg)


def test_delta_detecta_ciclo_nuevo(tmp_path):
    root = str(tmp_path)
    _init_repo(root)
    _write(root, "pkg/__init__.py", "")
    _write(root, "pkg/a.py", "X = 1\n")
    _write(root, "pkg/b.py", "from . import a\n")  # b->a, sin ciclo
    _commit(root, "baseline sin ciclo")

    _write(root, "pkg/a.py", "from . import b\n")  # working tree: a<->b, ciclo NUEVO
    report = graph.analyze(root, since="HEAD")

    assert report["baseline_ok"] is True
    assert report["new_pairs"]
    assert any(set(c) == {"pkg.a", "pkg.b"} for c in report["new_cycles"])


def test_delta_no_marca_ciclo_preexistente(tmp_path):
    root = str(tmp_path)
    _init_repo(root)
    _write(root, "pkg/__init__.py", "")
    _write(root, "pkg/a.py", "from . import b\n")
    _write(root, "pkg/b.py", "from . import a\n")  # ciclo YA en la baseline
    _commit(root, "baseline con ciclo")

    _write(root, "pkg/c.py", "X = 1\n")  # cambio ajeno al ciclo
    report = graph.analyze(root, since="HEAD")

    assert report["cycles"]           # el ciclo sigue ahí
    assert report["new_pairs"] == []  # pero no es NUEVO -> no es regresión
    assert report["new_cycles"] == []


def test_delta_encoger_un_ciclo_no_es_regresion(tmp_path):
    root = str(tmp_path)
    _init_repo(root)
    _write(root, "pkg/__init__.py", "")
    _write(root, "pkg/a.py", "from . import b\n")
    _write(root, "pkg/b.py", "from . import c\n")
    _write(root, "pkg/c.py", "from . import d\n")
    _write(root, "pkg/d.py", "from . import a\n")  # ciclo {a,b,c,d}
    _commit(root, "ciclo de 4")

    _write(root, "pkg/c.py", "from . import a\n")  # c cierra antes: ciclo pasa a {a,b,c}
    report = graph.analyze(root, since="HEAD")

    assert report["new_pairs"] == []  # los pares de {a,b,c} ya eran cíclicos: no hay nada nuevo


def test_delta_con_fuente_utf8_no_da_falso_positivo(tmp_path):
    """Regresión: los blobs de git son código con acentos (UTF-8). Si se leen con
    el codec del locale (cp1252 en Windows) se corrompe la baseline y un ciclo
    preexistente parece NUEVO. Aquí el ciclo lleva acentos y NO debe marcarse."""
    root = str(tmp_path)
    _init_repo(root)
    _write(root, "pkg/__init__.py", "")
    _write(root, "pkg/a.py", "from . import b  # configuracion ÁÉÍÓÚ ñ —\n")
    _write(root, "pkg/b.py", "from . import a  # modulo con acentos:\n")  # 0x81: rompe cp1252
    _commit(root, "baseline con ciclo y acentos")

    _write(root, "pkg/c.py", "X = 1\n")  # cambio ajeno al ciclo
    report = graph.analyze(root, since="HEAD")

    assert report["errors"] == {}     # los blobs UTF-8 se leyeron bien
    assert report["cycles"]           # el ciclo existe
    assert report["new_pairs"] == []  # y NO es nuevo (baseline leída correctamente)


def test_delta_con_nombre_de_fichero_acentuado_no_da_falso_positivo(tmp_path):
    """Bug del review: git C-escapa rutas no-ASCII (`"caf\\303\\251.py"`) por
    defecto, el .endswith('.py') falla y el módulo acentuado se cae de la baseline
    -> el ciclo parece NUEVO. Con core.quotePath=false no ocurre."""
    root = str(tmp_path)
    _init_repo(root)
    _write(root, "pkg/__init__.py", "")
    _write(root, "pkg/café.py", "from . import a\n")
    _write(root, "pkg/a.py", "from . import café\n")  # ciclo con nombre acentuado
    _commit(root, "baseline con ciclo acentuado")

    _write(root, "pkg/otro.py", "X = 1\n")  # cambio ajeno
    report = graph.analyze(root, since="HEAD")

    assert report["cycles"]           # el ciclo existe
    assert report["new_pairs"] == []  # y ya estaba en la baseline: NO es nuevo


def test_new_pairs_sale_ordenado(tmp_path):
    """Bug del review: new_pairs se construía iterando un set de frozensets, cuyo
    orden depende de PYTHONHASHSEED -> salida no reproducible."""
    root = str(tmp_path)
    _init_repo(root)
    for name in ("a", "b", "c", "d"):
        _write(root, "pkg/%s.py" % name, "X = 1\n")
    _write(root, "pkg/__init__.py", "")
    _commit(root, "baseline sin ciclos")

    _write(root, "pkg/a.py", "from . import b\n")
    _write(root, "pkg/b.py", "from . import a\n")  # ciclo 1
    _write(root, "pkg/c.py", "from . import d\n")
    _write(root, "pkg/d.py", "from . import c\n")  # ciclo 2
    report = graph.analyze(root, since="HEAD")

    assert len(report["new_pairs"]) == 2
    assert report["new_pairs"] == sorted(report["new_pairs"])  # ordenado, reproducible


def test_delta_no_marca_cruce_de_frontera_preexistente(tmp_path):
    root = str(tmp_path)
    _init_repo(root)
    _write(root, ".gb-boundaries", "app.web -/-> app.db\n")
    _write(root, "app/__init__.py", "")
    _write(root, "app/db.py", "")
    _write(root, "app/web.py", "from app import db\n")  # cruce YA en la baseline
    _commit(root, "baseline con cruce")

    _write(root, "app/otro.py", "X = 1\n")  # cambio ajeno
    report = graph.analyze(root, since="HEAD")

    assert report["violations"]            # el cruce existe
    assert report["new_violations"] == []  # pero ya estaba: no bloquea


def test_delta_marca_cruce_de_frontera_nuevo(tmp_path):
    root = str(tmp_path)
    _init_repo(root)
    _write(root, ".gb-boundaries", "app.web -/-> app.db\n")
    _write(root, "app/__init__.py", "")
    _write(root, "app/db.py", "")
    _write(root, "app/web.py", "X = 1\n")  # baseline SIN cruce
    _commit(root, "baseline limpia")

    _write(root, "app/web.py", "from app import db\n")  # introduce el cruce
    report = graph.analyze(root, since="HEAD")
    assert any(v["importer"] == "app.web" for v in report["new_violations"])

    from galaxybrain import cli

    assert cli.main(["graph", root, "--gate", "--since", "HEAD", "--color", "never"]) == 1


def test_gate_bloquea_cruce_absoluto_aunque_no_haya_baseline(tmp_path):
    """Falso negativo del review: con --since y baseline no disponible, un cruce de
    frontera ABSOLUTO (un hecho, no un delta) debe seguir bloqueando."""
    root = str(tmp_path)
    _init_repo(root)
    _write(root, ".gb-boundaries", "app.web -/-> app.db\n")
    _write(root, "app/__init__.py", "")
    _write(root, "app/db.py", "")
    _write(root, "app/web.py", "from app import db\n")  # cruce presente
    _commit(root, "con cruce")

    from galaxybrain import cli

    # ref inexistente -> baseline_ok False; el cruce absoluto debe bloquear igual
    assert cli.main(["graph", root, "--gate", "--since", "ref-que-no-existe", "--color", "never"]) == 1


def test_build_graph_from_git_none_sin_repo(tmp_path):
    _write(str(tmp_path), "pkg/__init__.py", "")
    assert graph.build_graph_from_git(str(tmp_path), "HEAD") is None


def test_analyze_since_baseline_no_disponible(tmp_path):
    _write(str(tmp_path), "pkg/__init__.py", "")
    report = graph.analyze(str(tmp_path), since="HEAD")  # no es repo git
    assert report["baseline_ok"] is False


def test_cli_gate_since_falla_con_nuevo_y_pasa_sin_el(tmp_path):
    root = str(tmp_path)
    _init_repo(root)
    _write(root, "pkg/__init__.py", "")
    _write(root, "pkg/a.py", "X = 1\n")
    _write(root, "pkg/b.py", "from . import a\n")
    _commit(root, "baseline")

    from galaxybrain import cli

    assert cli.main(["graph", root, "--gate", "--since", "HEAD", "--color", "never"]) == 0
    _write(root, "pkg/a.py", "from . import b\n")  # introduce ciclo
    assert cli.main(["graph", root, "--gate", "--since", "HEAD", "--color", "never"]) == 1


def test_cli_gate_since_tolera_preexistente_pero_estricto_no(tmp_path):
    root = str(tmp_path)
    _init_repo(root)
    _write(root, "pkg/__init__.py", "")
    _write(root, "pkg/a.py", "from . import b\n")
    _write(root, "pkg/b.py", "from . import a\n")
    _commit(root, "baseline con ciclo")

    from galaxybrain import cli

    assert cli.main(["graph", root, "--gate", "--since", "HEAD", "--color", "never"]) == 0  # nada NUEVO
    assert cli.main(["graph", root, "--gate", "--color", "never"]) == 1                     # estricto: hay ciclo


def test_cli_gate_since_sin_baseline_no_bloquea(tmp_path):
    root = str(tmp_path)
    _write(root, "pkg/__init__.py", "")
    _write(root, "pkg/a.py", "from . import b\n")
    _write(root, "pkg/b.py", "from . import a\n")  # hay ciclo, pero no hay repo/baseline

    from galaxybrain import cli

    # No puede comparar -> NO bloquea (un falso positivo acaba en --no-verify).
    assert cli.main(["graph", root, "--gate", "--since", "HEAD", "--color", "never"]) == 0
