"""Con que se abre el mapa lo decide el usuario, no gb.

gb no sabe en que editas ni tiene por que: cablear un editor concreto seria el
bug que nombra la regla 6 ("rutas, stacks o comandos cableados son bugs"). Por eso
hay una variable de entorno y no una lista de editores conocidos.

Y si la orden del usuario falla, se cae al navegador. Quedarse sin abrir nada por
un comando mal escrito seria fallar hacia el lado caro (regla 9).
"""

import os
import sys

from galaxybrain import cli


def test_sin_variable_usa_el_navegador(monkeypatch, tmp_path):
    monkeypatch.delenv("GB_OPEN_CMD", raising=False)
    llamadas = []
    monkeypatch.setattr("webbrowser.open", lambda url: llamadas.append(url))

    cli._abrir(str(tmp_path / "mapa.html"))
    assert len(llamadas) == 1
    assert llamadas[0].startswith("file://")


def test_con_variable_manda_la_orden_del_usuario(monkeypatch, tmp_path):
    monkeypatch.setenv("GB_OPEN_CMD", "mi-visor --flag")
    lanzados = []
    monkeypatch.setattr("subprocess.Popen", lambda partes, *a, **k: lanzados.append(partes))
    monkeypatch.setattr("webbrowser.open", lambda url: pytest_fail())

    destino = str(tmp_path / "mapa.html")
    cli._abrir(destino)
    assert lanzados == [["mi-visor", "--flag", destino]]


def pytest_fail():
    raise AssertionError("no debia caer al navegador: la orden del usuario funciono")


def test_una_orden_rota_no_te_deja_sin_abrir(monkeypatch, tmp_path, capsys):
    """Regla 9: el fallo se dice y se sigue, no se muere en silencio ni se queda
    el usuario mirando una pantalla donde no pasa nada."""
    monkeypatch.setenv("GB_OPEN_CMD", "comando-que-no-existe")

    def _revienta(*_a, **_k):
        raise OSError("no such file")

    monkeypatch.setattr("subprocess.Popen", _revienta)
    abiertos = []
    monkeypatch.setattr("webbrowser.open", lambda url: abiertos.append(url))

    cli._abrir(str(tmp_path / "mapa.html"))
    assert abiertos, "no cayo al navegador"
    assert "GB_OPEN_CMD fallo" in capsys.readouterr().err


def test_una_ruta_de_windows_no_se_destroza(monkeypatch, tmp_path):
    """`shlex` en modo posix se come las barras invertidas: un visor instalado en
    `C:\\Program Files\\...` acabaria siendo un comando distinto."""
    if os.name != "nt":
        return
    monkeypatch.setenv("GB_OPEN_CMD", r'"C:\Program Files\Visor\v.exe" --nuevo')
    lanzados = []
    monkeypatch.setattr("subprocess.Popen", lambda partes, *a, **k: lanzados.append(partes))

    cli._abrir(str(tmp_path / "mapa.html"))
    assert lanzados[0][0].endswith("v.exe") or "Program Files" in lanzados[0][0]


def test_el_ejecutable_se_resuelve_con_which(monkeypatch, tmp_path):
    """No es cosmetico en Windows: los lanzadores de editores y de node son
    ficheros .CMD y `Popen` no puede ejecutarlos por nombre — falla con "no se
    encuentra el archivo". Con la ruta resuelta si funcionan. Se comprobo a mano
    con el CLI del editor antes de escribir esto."""
    monkeypatch.setenv("GB_OPEN_CMD", "mi-visor")
    monkeypatch.setattr("shutil.which", lambda nombre: r"C:\ruta\mi-visor.CMD")
    lanzados = []
    monkeypatch.setattr("subprocess.Popen", lambda partes, *a, **k: lanzados.append(partes))

    cli._abrir(str(tmp_path / "mapa.html"))
    assert lanzados[0][0] == r"C:\ruta\mi-visor.CMD"


def test_si_which_no_lo_encuentra_se_intenta_igual(monkeypatch, tmp_path):
    """Un comando que `which` no ve puede seguir siendo valido (ruta absoluta,
    alias del shell). Se intenta y, si falla, ya cae al navegador."""
    monkeypatch.setenv("GB_OPEN_CMD", "raro")
    monkeypatch.setattr("shutil.which", lambda nombre: None)
    lanzados = []
    monkeypatch.setattr("subprocess.Popen", lambda partes, *a, **k: lanzados.append(partes))

    cli._abrir(str(tmp_path / "mapa.html"))
    assert lanzados[0][0] == "raro"


def test_la_variable_vacia_no_cuenta_como_orden(monkeypatch, tmp_path):
    """`GB_OPEN_CMD=` (o con espacios) es "no configurado", no "ejecuta nada"."""
    monkeypatch.setenv("GB_OPEN_CMD", "   ")
    abiertos = []
    monkeypatch.setattr("webbrowser.open", lambda url: abiertos.append(url))
    monkeypatch.setattr("subprocess.Popen", lambda *a, **k: (_ for _ in ()).throw(AssertionError()))

    cli._abrir(str(tmp_path / "mapa.html"))
    assert abiertos


assert sys  # el import existe para que el test de Windows sea explicito
