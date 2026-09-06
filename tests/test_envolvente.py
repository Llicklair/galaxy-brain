"""El envolvente (`gb-run`) como armador universal: un proceso no puede cambiar
el entorno de su padre, pero sí el de sus HIJOS. `gb-run <comando>` arma las
variables de hook de los lenguajes detectados y lanza el comando — cobertura
por invocación, sin magia. Es la vía para acercar el arranque no-Python al
`.pth` de Python (decidido el 6-sep-2026, eje escrito en SCOPE.md)."""

import importlib.util
import os
import shutil
import subprocess
import sys

import pytest

import galaxybrain

RUTA_GB_RUN = os.path.join(os.path.dirname(galaxybrain.__file__), "hooks_lang", "gb-run.py")


def _gb_run():
    """Carga fresca: gb-run lee GB_HOME al importar, así que cada test que lo
    cambie necesita su propio módulo."""
    spec = importlib.util.spec_from_file_location("gb_run_bajo_prueba", RUTA_GB_RUN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_arma_node_apendiendo_sin_pisar(tmp_path):
    """APPEND, nunca pisar: el NODE_OPTIONS del usuario suele traer lo suyo
    (--max-old-space-size) y perderlo sería alterar el programa observado."""
    (tmp_path / "app.js").write_text("", encoding="utf-8")
    gb_run = _gb_run()

    detectados = gb_run.detect_languages(str(tmp_path))
    assert "node" in detectados

    env = {"NODE_OPTIONS": "--max-old-space-size=64"}
    gb_run.setup_env(["node"], "sesion-test", env)
    assert env["NODE_OPTIONS"].startswith("--max-old-space-size=64 ")
    assert "gb-hook.js" in env["NODE_OPTIONS"]


def test_armar_dos_veces_no_duplica(tmp_path):
    """Idempotente: gb-run dentro de gb-run (un orquestador que envuelve a
    otro) no puede acabar cargando el hook dos veces."""
    gb_run = _gb_run()
    env = {}
    gb_run.setup_env(["node"], "s1", env)
    una_vez = env["NODE_OPTIONS"]
    gb_run.setup_env(["node"], "s2", env)
    assert env["NODE_OPTIONS"] == una_vez


def test_php_queda_armado_por_ini_heredable(tmp_path, monkeypatch):
    """php no lee el hook por variable directa (auto_prepend_file es ini), pero
    PHP_INI_SCAN_DIR sí se hereda — y el elemento vacío inicial conserva el
    escaneo por defecto. El ini vive en GB_HOME, no en el paquete."""
    monkeypatch.setenv("GB_HOME", str(tmp_path))
    gb_run = _gb_run()

    env = {}
    gb_run.setup_env(["php"], "sesion-test", env)

    ini = tmp_path / "php" / "gb.ini"
    assert ini.is_file()
    assert "auto_prepend_file" in ini.read_text(encoding="utf-8")
    assert "gb-hook.php" in ini.read_text(encoding="utf-8")
    assert env["PHP_INI_SCAN_DIR"].startswith(os.pathsep)
    assert str(tmp_path / "php") in env["PHP_INI_SCAN_DIR"]


def test_gb_home_manda_en_el_almacen_del_envolvente(tmp_path, monkeypatch):
    """`store_universal` murió por ignorar GB_HOME (ADR 0012); el envolvente
    repetía el pecado con Path.home() fijo."""
    monkeypatch.setenv("GB_HOME", str(tmp_path))
    gb_run = _gb_run()
    assert str(gb_run.CRASHES_DIR) == str(tmp_path)


def test_e2e_node_capturado_sin_tocar_el_exit_code(tmp_path):
    """El criterio 5 del ADR 0012, de punta a punta y sin armar nada a mano:
    `gb-run node peta.js` captura el estado Y el programa muere exactamente
    igual que sin envolvente — mismo exit code, su error en stderr."""
    node = shutil.which("node")
    if not node:
        pytest.skip("sin node en esta maquina")

    proyecto = tmp_path / "proy"
    proyecto.mkdir()
    guion = proyecto / "peta.js"
    guion.write_text("throw new Error('demo del envolvente');\n", encoding="utf-8")
    gb_home = tmp_path / "gbhome"

    entorno = dict(os.environ, GB_HOME=str(gb_home))
    entorno.pop("NODE_OPTIONS", None)

    a_pelo = subprocess.run([node, str(guion)], capture_output=True, text=True,
                            timeout=60, cwd=str(proyecto), env=entorno)
    envuelto = subprocess.run([sys.executable, RUTA_GB_RUN, node, str(guion)],
                              capture_output=True, text=True, timeout=60,
                              cwd=str(proyecto), env=entorno)

    assert envuelto.returncode == a_pelo.returncode != 0
    assert "demo del envolvente" in envuelto.stderr
    crashes = gb_home / "crashes.jsonl"
    assert crashes.is_file(), "el hook no escribio en GB_HOME"
    assert "demo del envolvente" in crashes.read_text(encoding="utf-8")


def test_sonda_todos_los_hooks_leen_gb_home():
    """Contra los FUENTES, también los de runtimes que esta máquina no ejecuta:
    un hook que clave ~/.galaxy-brain deja capturas escritas y perdidas en
    cuanto GB_HOME apunte a otro sitio."""
    base = os.path.join(os.path.dirname(galaxybrain.__file__), "hooks_lang")
    hooks = [
        "gb-hook.js", "gb-hook.rb", "gb-hook.lua", "gb-hook.php", "gb-run.py",
        os.path.join("c", "gb_hook.c"), os.path.join("c", "gb_run_win.c"),
        os.path.join("swift", "gb_hook.swift"),
        os.path.join("jvm", "GbAgent.java"),
        os.path.join("dotnet", "GbHook", "StartupHook.cs"),
    ]
    for rel in hooks:
        with open(os.path.join(base, rel), encoding="utf-8") as handle:
            assert "GB_HOME" in handle.read(), "%s no lee GB_HOME" % rel
