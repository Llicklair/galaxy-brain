"""La integracion que se pudre: hooks de un proyecto que llaman a un gb que ya
no acepta esa forma, o un pre-commit que existe pero no corre.

Revision del 25-sep-2026 sobre 13 proyectos: en guardia-mvp el SessionStart
llamaba a `gb symbols --fondo`, bandera que ya no existe — fallaba en cada
sesion sin decir nada — y `core.hooksPath` estaba desenganchado, asi que los
commits entraban sin pre-commit. Nada de gb lo detectaba.
"""

import json
import os
import subprocess

from galaxybrain import cli


def _repo(tmp_path):
    root = str(tmp_path / "p")
    os.makedirs(root)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    return root


def _settings(root, *comandos):
    os.makedirs(os.path.join(root, ".claude"), exist_ok=True)
    datos = {"hooks": {"SessionStart": [{"hooks": [
        {"type": "command", "command": c} for c in comandos]}]}}
    with open(os.path.join(root, ".claude", "settings.json"), "w", encoding="utf-8") as f:
        json.dump(datos, f)


def _precommit(root, texto):
    os.makedirs(os.path.join(root, ".githooks"), exist_ok=True)
    with open(os.path.join(root, ".githooks", "pre-commit"), "w", encoding="utf-8") as f:
        f.write(texto)


def test_un_hook_con_una_bandera_que_ya_no_existe_se_dice(tmp_path):
    root = _repo(tmp_path)
    _settings(root, "gb graph --context",
              "gb symbols --html --watch --fondo --refresco 3")

    rotos = cli.integracion_rota(root)
    assert len(rotos) == 1, rotos
    assert "gb symbols --html --watch --fondo --refresco 3" in rotos[0]
    assert "--fondo" in rotos[0] and ".claude/settings.json" in rotos[0]


def test_un_subcomando_que_no_existe_se_dice(tmp_path):
    root = _repo(tmp_path)
    _settings(root, "gb mapa --fondo 2>/dev/null || true")

    rotos = cli.integracion_rota(root)
    assert len(rotos) == 1 and "gb mapa" in rotos[0], rotos


def test_el_precommit_sin_enganchar_se_dice(tmp_path):
    root = _repo(tmp_path)
    _precommit(root, "#!/bin/sh\ngb graph . --gate --since HEAD || exit 1\n")

    rotos = cli.integracion_rota(root)
    assert any("core.hooksPath" in r for r in rotos), rotos

    subprocess.run(["git", "config", "core.hooksPath", ".githooks"], cwd=root, check=True)
    assert cli.integracion_rota(root) == []
    # Absoluto tambien vale (asi lo tiene el propio repo de gb).
    subprocess.run(["git", "config", "core.hooksPath", os.path.join(root, ".githooks")],
                   cwd=root, check=True)
    assert cli.integracion_rota(root) == []


def test_el_propio_repo_de_gb_no_da_falsos_positivos():
    """Control: gb se llama desde su propio hook y sus settings con todas las
    formas vivas (`python -m galaxybrain.cli`, `||`, redirecciones)."""
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    rotos = [r for r in cli.integracion_rota(raiz) if "core.hooksPath" not in r]
    assert rotos == [], rotos


def test_floor_lo_ensena(tmp_path, capsys):
    root = _repo(tmp_path)
    _settings(root, "gb symbols --fondo")

    assert cli.main(["floor", root]) == 0
    salida = capsys.readouterr().out
    assert "INTEGRACION ROTA con gb (1)" in salida, salida


def test_un_hook_que_llama_a_gb_sin_que_gb_este_en_el_path_se_dice(tmp_path, monkeypatch):
    """El caso de nihonworld en un proyecto ya montado: gb en el venv, hooks
    con `gb` a secas. El hook fallara en cada uso y nadie lo vera."""
    import shutil

    root = _repo(tmp_path)
    _settings(root, "gb graph --context")
    monkeypatch.setattr(shutil, "which", lambda n, *a, **k: None)

    rotos = cli.integracion_rota(root)
    assert any("no esta en el PATH" in r for r in rotos), rotos
