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


def test_enable_revierte_si_el_entorno_queda_roto(monkeypatch, tmp_path):
    """La comprobacion no es decorativa: ante un .pth invalido, `gb on` tiene
    que dejar el entorno intacto en vez de activarse a medias."""
    monkeypatch.setattr(bootstrap, "PTH_LINE", 'import sys; exec("esto no cierra')
    monkeypatch.setattr(bootstrap, "pth_path", lambda: tmp_path / bootstrap.PTH_NAME)

    ok, mensaje = bootstrap.enable()

    assert ok is False
    assert "revertida" in mensaje
    assert not (tmp_path / bootstrap.PTH_NAME).exists()


def test_verify_detecta_que_el_paquete_no_esta_instalado(monkeypatch, tmp_path):
    monkeypatch.setattr(bootstrap, "pth_path", lambda: tmp_path / bootstrap.PTH_NAME)
    # Sin escribir el .pth, el interprete actual de pytest tampoco tiene el hook
    # puesto por site: verify debe decir que no, no adivinar que si.
    ok, detail = bootstrap.verify()
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
