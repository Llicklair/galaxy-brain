"""El mecanismo `.pth`: la propiedad 2 entera (intercepta, no pregunta).

Es lo unico que hace que esto se use sin acordarse de nada, y es tambien lo
unico que puede dejar el entorno peor de como estaba. Se prueba con venvs de
verdad porque razonar sobre el fichero no demuestra nada: un `.pth` roto no
falla al escribirse, falla en el arranque de cada proceso, despues.
"""

import json
import subprocess
import sys
import textwrap
import venv

import pytest

from galaxybrain import bootstrap, store

SRC = str(__import__("pathlib").Path(__file__).resolve().parent.parent / "src")


@pytest.fixture(scope="module")
def entorno(tmp_path_factory):
    """Un venv limpio. Caro (~3 s), asi que uno para todo el modulo."""
    root = tmp_path_factory.mktemp("venv")
    venv.create(root, with_pip=False)
    python = root / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    assert python.exists()

    site = subprocess.run(
        [str(python), "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    # Sin pip: el paquete se hace importable con una linea de ruta en un .pth
    # que se procesa ANTES (orden alfabetico) que el nuestro.
    (__import__("pathlib").Path(site) / "_gbsrc.pth").write_text(SRC + "\n", encoding="utf-8")
    return {"python": str(python), "site": __import__("pathlib").Path(site)}


def _run(entorno, script, env, args=()):
    return subprocess.run(
        [entorno["python"], str(script), *args],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )


def test_la_linea_pth_es_una_sola_linea():
    """Invariante, no casualidad. `site.addpackage` ejecuta el fichero linea a
    linea: si un salto de linea real se cuela en PTH_LINE, cada proceso Python
    del entorno arranca escupiendo un SyntaxError. Cuesta un test y ahorra el
    peor fallo que puede tener esto."""
    assert "\n" not in bootstrap.PTH_LINE
    assert "\r" not in bootstrap.PTH_LINE
    assert bootstrap.PTH_LINE.startswith("import ")  # si no, site la ignora
    compile(bootstrap.PTH_LINE, "<pth>", "exec")  # tiene que ser Python valido


def test_el_arranque_queda_limpio_con_el_pth_puesto(entorno, child_env):
    """Ni una linea en stderr. Un Python que escupe algo en cada arranque es
    una herramienta desinstalada esa misma tarde."""
    (entorno["site"] / bootstrap.PTH_NAME).write_text(
        bootstrap.PTH_LINE + "\n", encoding="utf-8"
    )

    result = subprocess.run(
        [entorno["python"], "-c", "print('vivo')"],
        capture_output=True,
        text=True,
        timeout=60,
        env=child_env,
    )
    assert result.stderr == ""
    assert result.stdout.strip() == "vivo"


def test_captura_sin_que_el_programa_sepa_que_existimos(entorno, child_env, gb_home, tmp_path):
    """El test que justifica todo el mecanismo: un script que NO importa
    galaxybrain, en un proyecto que no sabe nada de esto, y aun asi el fallo
    queda capturado con su estado."""
    (entorno["site"] / bootstrap.PTH_NAME).write_text(
        bootstrap.PTH_LINE + "\n", encoding="utf-8"
    )

    proyecto = tmp_path / "ajeno"
    (proyecto / ".git").mkdir(parents=True)
    script = proyecto / "tarea.py"
    script.write_text(
        textwrap.dedent(
            """
            def procesar(lote):
                pendientes = len(lote)
                return lote["total"]

            procesar([1, 2, 3])
            """
        ),
        encoding="utf-8",
    )

    result = _run(entorno, script, child_env)
    assert result.returncode != 0
    assert "galaxy-brain" in result.stderr  # el aviso de una linea

    record = store.load()
    assert record["exception"]["type"] == "TypeError"
    frame = [f for f in record["frames"] if not f["is_library"]][-1]
    assert frame["function"] == "procesar"
    assert frame["locals"]["pendientes"] == "3"


def test_desactivar_deja_el_entorno_como_estaba(entorno, child_env, gb_home, tmp_path):
    pth = entorno["site"] / bootstrap.PTH_NAME
    pth.write_text(bootstrap.PTH_LINE + "\n", encoding="utf-8")
    pth.unlink()

    script = tmp_path / "otra.py"
    script.write_text("raise ValueError('roto')\n", encoding="utf-8")

    result = _run(entorno, script, child_env)
    assert "galaxy-brain" not in result.stderr
    assert store.read_index() == []


def test_un_pth_huerfano_no_ensucia_el_arranque(entorno, child_env):
    """Si desinstalas el paquete y el .pth se queda, el try/except de la linea
    tiene que tragarse el ImportError en silencio."""
    (entorno["site"] / bootstrap.PTH_NAME).write_text(
        bootstrap.PTH_LINE + "\n", encoding="utf-8"
    )
    (entorno["site"] / "_gbsrc.pth").unlink()  # el paquete deja de existir
    try:
        result = subprocess.run(
            [entorno["python"], "-c", "print('vivo')"],
            capture_output=True,
            text=True,
            timeout=60,
            env=child_env,
        )
        assert result.stderr == ""
        assert result.stdout.strip() == "vivo"
    finally:
        (entorno["site"] / "_gbsrc.pth").write_text(SRC + "\n", encoding="utf-8")


def test_enable_revierte_lo_que_escribio_si_verify_falla(monkeypatch, tmp_path):
    """La lógica de revert de enable(), hermética: si escribimos el .pth y verify
    falla, se borra lo nuestro. Se mockea verify para no depender del intérprete
    que corre los tests (que puede tener gb activo)."""
    pth = tmp_path / bootstrap.PTH_NAME
    monkeypatch.setattr(bootstrap, "pth_path", lambda: pth)
    monkeypatch.setattr(bootstrap, "verify", lambda executable=None: (False, "arranque roto"))

    ok, mensaje = bootstrap.enable()

    assert ok is False
    assert "revertida" in mensaje
    assert not pth.exists()  # escribimos y revertimos: se borra


def test_verify_detecta_un_pth_que_rompe_el_arranque(entorno):
    """Integración real: un .pth con sintaxis rota hace que site escupa un
    traceback en cada arranque (el peor fallo). verify() debe cazarlo."""
    pth = entorno["site"] / bootstrap.PTH_NAME
    pth.write_text('import sys; exec("esto no cierra\n', encoding="utf-8")
    try:
        ok, _detail = bootstrap.verify(executable=entorno["python"])
        assert ok is False
    finally:
        pth.unlink()


def test_verify_ignora_stderr_ajeno_si_el_hook_esta_puesto(entorno):
    """B1: si el hook quedó instalado (stdout '1'), un stderr ajeno en el arranque
    (p.ej. el DeprecationWarning de pkg_resources) NO debe hacer fallar verify()."""
    site = entorno["site"]
    (site / bootstrap.PTH_NAME).write_text(bootstrap.PTH_LINE + "\n", encoding="utf-8")
    # Un .pth que se procesa ANTES (orden alfabético) y escupe a stderr — ruido ajeno.
    noise = site / "_aaa_noise.pth"
    noise.write_text('import sys; sys.stderr.write("DeprecationWarning: algo ajeno\\n")\n',
                     encoding="utf-8")
    try:
        ok, detail = bootstrap.verify(executable=entorno["python"])
        assert ok is True, detail  # el hook está puesto: pasa pese al ruido
    finally:
        noise.unlink()
        (site / bootstrap.PTH_NAME).unlink()


def test_enable_no_borra_un_pth_preexistente_si_verify_falla(monkeypatch, tmp_path):
    """B1: el revert de enable() solo debe borrar lo que ESCRIBIÓ esta llamada.
    Un .pth que ya existía no se borra por un fallo de verify (ruido ajeno)."""
    pth = tmp_path / bootstrap.PTH_NAME
    pth.write_text(bootstrap.PTH_LINE + "\n", encoding="utf-8")  # ya existe, correcto
    monkeypatch.setattr(bootstrap, "pth_path", lambda: pth)
    monkeypatch.setattr(bootstrap, "verify", lambda executable=None: (False, "ruido ajeno"))

    ok, _msg = bootstrap.enable()
    assert ok is False
    assert pth.exists()  # NO lo borra: no lo escribimos nosotros


def test_verify_detecta_que_el_paquete_no_esta_instalado(entorno):
    # Hermético: un venv fresco importa galaxybrain (via _gbsrc.pth) pero NO tiene
    # el hook (no hay galaxybrain.pth), así que verify() debe decir "no instalado".
    # Se usa el venv y no sys.executable a propósito: si gb está activado en el
    # intérprete que corre los tests (p.ej. tras `gb on`), sys.executable SÍ tiene
    # el hook y el test daría un falso fallo.
    pth = entorno["site"] / bootstrap.PTH_NAME
    if pth.exists():
        pth.unlink()
    ok, detail = bootstrap.verify(executable=entorno["python"])
    assert ok is False
    assert "hook no quedo instalado" in detail


def test_el_cli_lee_lo_capturado_por_el_pth(entorno, child_env, gb_home, tmp_path):
    (entorno["site"] / bootstrap.PTH_NAME).write_text(
        bootstrap.PTH_LINE + "\n", encoding="utf-8"
    )
    proyecto = tmp_path / "lectura"
    (proyecto / ".git").mkdir(parents=True)
    script = proyecto / "x.py"
    script.write_text("raise KeyError('plan')\n", encoding="utf-8")
    _run(entorno, script, child_env)

    result = subprocess.run(
        [entorno["python"], "-m", "galaxybrain.cli", "list", "--json"],
        cwd=str(proyecto),
        capture_output=True,
        text=True,
        timeout=60,
        env=child_env,
    )
    entradas = json.loads(result.stdout)
    assert entradas[0]["type"] == "KeyError"
