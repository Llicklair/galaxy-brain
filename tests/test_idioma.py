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
