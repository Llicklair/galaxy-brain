"""El primer día con gb, empaquetado: `floor --init` deja también el pre-commit
enganchable, el contexto de sesión sugiere el camino SOLO en el caso inequívoco
(repo git recién nacido) y cuenta las capturas sin leer para que el agente
decida cuándo tirar del hilo.
"""

import datetime
import json
import os
import subprocess

from galaxybrain import cli, floor, store


def _repo(tmp_path):
    root = str(tmp_path / "nuevo")
    os.makedirs(root, exist_ok=True)
    subprocess.run(("git", "init", "-q"), cwd=root, check=True, capture_output=True)
    return root


def test_init_deja_el_precommit_enganchable(tmp_path):
    root = _repo(tmp_path)

    hechos = {h["path"]: h["action"] for h in floor.scaffold(root)}
    assert hechos[".githooks/pre-commit"] == "creado"
    with open(os.path.join(root, ".githooks", "pre-commit"), encoding="utf-8") as handle:
        hook = handle.read()
    assert "gb graph . --gate --since HEAD" in hook
    assert "gb check --staged" in hook


def test_init_no_pisa_un_precommit_existente(tmp_path):
    """Nunca pisar la ley de un proyecto — tampoco su hook."""
    root = _repo(tmp_path)
    os.makedirs(os.path.join(root, ".githooks"), exist_ok=True)
    with open(os.path.join(root, ".githooks", "pre-commit"), "w", encoding="utf-8") as handle:
        handle.write("#!/bin/sh\nmi hook\n")

    hechos = {h["path"]: h["action"] for h in floor.scaffold(root)}
    assert hechos[".githooks/pre-commit"] == "ya-existia"
    with open(os.path.join(root, ".githooks", "pre-commit"), encoding="utf-8") as handle:
        assert "mi hook" in handle.read()


def test_init_cablea_el_arnes_del_agente(tmp_path):
    """El modelo no sabe que gb existe; lo sabe su contexto. Los tres hooks del
    grafo viajan con el repo — sin esto, la consciencia del LLM era artesania
    del settings global de una sola maquina."""
    root = _repo(tmp_path)

    hechos = {h["path"]: h["action"] for h in floor.scaffold(root)}
    assert hechos[".claude/settings.json"] == "creado"
    with open(os.path.join(root, ".claude", "settings.json"), encoding="utf-8") as handle:
        settings = json.load(handle)  # JSON valido o este open revienta el test
    texto = json.dumps(settings)
    assert "gb graph --context" in texto
    assert "gb graph --context --if-changed" in texto
    assert "gb calls --hook" in texto
    # El pulso del mapa, de serie: sin un watch vivo, la capa de actividad dice
    # cero aunque haya trabajo — una sesion entera paso invisible el 7-ago
    # ("fracaso absoluto", feedback real). --fondo vuelve al instante (hook) y
    # el candado evita duplicados entre sesiones.
    assert "gb symbols --html --watch --fondo" in texto


def test_init_no_pisa_un_settings_existente(tmp_path):
    root = _repo(tmp_path)
    os.makedirs(os.path.join(root, ".claude"), exist_ok=True)
    with open(os.path.join(root, ".claude", "settings.json"), "w", encoding="utf-8") as handle:
        handle.write('{"mio": true}')

    hechos = {h["path"]: h["action"] for h in floor.scaffold(root)}
    assert hechos[".claude/settings.json"] == "ya-existia"
    with open(os.path.join(root, ".claude", "settings.json"), encoding="utf-8") as handle:
        assert json.load(handle) == {"mio": True}


def test_agents_lleva_el_contrato_con_gb(tmp_path):
    """El "cuando lo considere necesario" del agente necesita que el contrato
    este escrito donde el agente lo lee: la plantilla de AGENTS.md."""
    root = _repo(tmp_path)
    floor.scaffold(root)

    with open(os.path.join(root, "AGENTS.md"), encoding="utf-8") as handle:
        agents = handle.read()
    assert "gb calls" in agents
    assert "gb last" in agents
    assert "gb list" in agents


def test_la_sugerencia_solo_en_el_caso_inequivoco(tmp_path):
    root = _repo(tmp_path)
    assert cli._sugerencia_primer_dia(root)  # git + sin python + sin suelo

    floor.scaffold(root)
    assert cli._sugerencia_primer_dia(root) is None  # ya hay suelo

    suelto = str(tmp_path / "carpeta")
    os.makedirs(suelto, exist_ok=True)
    assert cli._sugerencia_primer_dia(suelto) is None  # sin git: silencio (H6)


def test_el_contexto_cuenta_las_capturas_sin_leer(tmp_path):
    root = _repo(tmp_path)
    registro = {
        "ts": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "exception": {"type": "ValueError", "message": "boom"},
        "process": {"project": root, "cwd": root, "pid": 1},
        "frames": [{"file": os.path.join(root, "x.py"), "line": 2, "is_library": False}],
    }
    assert store.write(registro) is not None

    assert cli._capturas_sin_leer(root) == 1
    store.mark_read(registro["id"], project=root)
    assert cli._capturas_sin_leer(root) == 0


def test_init_engancha_el_precommit_solo(tmp_path):
    """La conexion no se sugiere: se hace. 'Acuerdate del git config' fallo en
    uso real el mismo dia que se estreno el arnes (7-ago: hook creado, inactivo,
    y lo tuvo que sugerir el LLM — la norma va en el defecto, no en el prompt)."""
    root = _repo(tmp_path)
    hechos = {h["path"]: h["action"] for h in floor.scaffold(root)}
    assert hechos["core.hooksPath"] == "enganchado"
    salida = subprocess.run(["git", "config", "core.hooksPath"], cwd=root,
                            capture_output=True, text=True)
    assert salida.stdout.strip() == ".githooks"

    # idempotente: la segunda pasada lo encuentra hecho
    hechos = {h["path"]: h["action"] for h in floor.scaffold(root)}
    assert hechos["core.hooksPath"] == "ya-enganchado"


def test_init_respeta_un_hookspath_ajeno(tmp_path):
    """Nunca pisar: si el proyecto ya enruta sus hooks a otro sitio, gb no se
    lo roba — lo dice, y la pista manual queda solo para este caso."""
    root = _repo(tmp_path)
    subprocess.run(["git", "config", "core.hooksPath", "mis-hooks"], cwd=root, check=True)
    hechos = {h["path"]: h["action"] for h in floor.scaffold(root)}
    assert hechos["core.hooksPath"] == "respetado: mis-hooks"
    salida = subprocess.run(["git", "config", "core.hooksPath"], cwd=root,
                            capture_output=True, text=True)
    assert salida.stdout.strip() == "mis-hooks"
