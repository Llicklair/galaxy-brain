"""El inglés opt-in: GB_LANG=en traduce el camino del desconocido; el
español sigue siendo el defecto y la fuente — sin GB_LANG nada cambia."""
import os
import subprocess
import sys

from galaxybrain import idioma


def test_sin_gb_lang_todo_pasa_tal_cual(monkeypatch):
    monkeypatch.delenv("GB_LANG", raising=False)
    assert idioma.t("hace %ds") == "hace %ds"
    assert not idioma.en()


def test_con_gb_lang_en_se_traduce_la_plantilla(monkeypatch):
    monkeypatch.setenv("GB_LANG", "en")
    assert idioma.en()
    assert idioma.t("hace %ds") == "%ds ago"
    # lo que no esta en la tabla sale en español TAL CUAL: cobertura
    # declarada, no fingida
    assert idioma.t("esto no esta traducido") == "esto no esta traducido"


def test_el_camino_del_desconocido_en_ingles(tmp_path):
    """Instalar, petar, leer: el primer contacto entero con GB_LANG=en —
    el aviso de captura y la ficha hablan inglés, sin rastro de 'hace'."""
    raiz = tmp_path / "proyecto"
    raiz.mkdir()
    (raiz / "caja.py").write_text("def parte(t, g):\n    return t // g\n",
                                  encoding="utf-8")
    for orden in (["git", "init", "-q"], ["git", "add", "-A"],
                  ["git", "-c", "user.name=t", "-c", "user.email=t@t.t",
                   "commit", "-q", "-m", "base"]):
        subprocess.run(orden, cwd=str(raiz), timeout=60)
    entorno = dict(os.environ, GB_LANG="en", GB_HOME=str(tmp_path / "hogar"))
    muerte = subprocess.run(
        [sys.executable, "-c", "from caja import parte\nparte(1, 0)"],
        cwd=str(raiz), capture_output=True, text=True, timeout=120,
        env=entorno)
    assert "state captured -> gb show" in muerte.stderr
    ficha = subprocess.run(
        [sys.executable, "-m", "galaxybrain.cli", "last"],
        cwd=str(raiz), capture_output=True, text=True, timeout=120,
        env=entorno)
    assert ficha.returncode == 0, ficha.stderr[:300]
    assert " ago" in ficha.stdout        # el tiempo relativo, en inglés
    assert "hace " not in ficha.stdout   # y ni rastro del español


def test_el_verificador_selecciona_en_ingles(tmp_path):
    """Fase 2, el camino rutinario entero: gb tests con GB_LANG=en sobre un
    diff real — cabecera, motivo, disparadores y el pie honesto, en inglés."""
    raiz = tmp_path / "obra"
    (raiz / "tests").mkdir(parents=True)
    (raiz / "caja.py").write_text("def parte(t, g):\n    return t // g\n",
                                  encoding="utf-8")
    (raiz / "tests" / "test_caja.py").write_text(
        "from caja import parte\n\n\ndef test_parte():\n"
        "    assert parte(4, 2) == 2\n", encoding="utf-8")
    for orden in (["git", "init", "-q"], ["git", "add", "-A"],
                  ["git", "-c", "user.name=t", "-c", "user.email=t@t.t",
                   "commit", "-q", "-m", "base"]):
        subprocess.run(orden, cwd=str(raiz), timeout=60)
    # el rango por defecto es HEAD~1..HEAD: el cambio viaja en su commit
    (raiz / "caja.py").write_text(
        "def parte(t, g):\n    return int(t) // g\n", encoding="utf-8")
    for orden in (["git", "add", "-A"],
                  ["git", "-c", "user.name=t", "-c", "user.email=t@t.t",
                   "commit", "-q", "-m", "cambio"]):
        subprocess.run(orden, cwd=str(raiz), timeout=60)
    salida = subprocess.run(
        [sys.executable, "-m", "galaxybrain.cli", "tests"],
        cwd=str(raiz), capture_output=True, text=True, timeout=120,
        env=dict(os.environ, GB_LANG="en"))
    assert salida.returncode == 0, salida.stderr[:300]
    assert "reach the" in salida.stdout              # el motivo estrella
    assert "Triggered by" in salida.stdout
    assert "What this does NOT guarantee:" in salida.stdout
    assert "alcanzan" not in salida.stdout and "ENTERA" not in salida.stdout


def test_el_verificador_sin_git_corre_todo_en_ingles(tmp_path):
    """El fallback a suite entera también habla inglés: sin git no hay diff,
    y eso se dice en voz alta en el idioma pedido."""
    raiz = tmp_path / "sin_git"
    (raiz / "tests").mkdir(parents=True)
    (raiz / "tests" / "test_nada.py").write_text(
        "def test_pasa():\n    assert True\n", encoding="utf-8")
    salida = subprocess.run(
        [sys.executable, "-m", "galaxybrain.cli", "tests"],
        cwd=str(raiz), capture_output=True, text=True, timeout=120,
        env=dict(os.environ, GB_LANG="en"))
    assert salida.returncode == 0, salida.stderr[:300]
    assert "The WHOLE suite" in salida.stdout
    assert "could not read the diff" in salida.stdout
    assert "suite ENTERA" not in salida.stdout


def test_el_brief_de_check_habla_ingles(monkeypatch):
    """La línea que ve cada commit desde el hook, traducida entera."""
    monkeypatch.setenv("GB_LANG", "en")
    from galaxybrain import render
    linea = render.render_changes(
        {"range": "staged", "flags": [], "onda": [],
         "test_files_changed": 0, "staged": True},
        lambda texto, *_: texto, brief=True)
    assert "no signals" in linea and "detail: gb check --staged" in linea
    assert "sin senales" not in linea
