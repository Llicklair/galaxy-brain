"""Fase A — la correlacion: distinguir "el ultimo fallo" de "el fallo de lo que
acabo de ejecutar".

Sin esto, quien lee el historico justo despues de un fallo puede recibir una
captura de ayer y arreglar, con total confianza, el problema equivocado. Ese es
el modo de fallo que estos tests fijan: ante la duda, NO se entrega nada.
"""

import datetime

import pytest

from galaxybrain import cli, store


def _ts(seconds_ago):
    stamp = datetime.datetime.now().astimezone() - datetime.timedelta(seconds=seconds_ago)
    return stamp.isoformat(timespec="seconds")


def _record(ts, exc_type="ValueError", project="/tmp/proyecto"):
    return {
        "schema": 1,
        "ts": ts,
        "exception": {"type": exc_type, "message": "roto", "chain": []},
        "frames": [{"file": "/tmp/proyecto/app.py", "line": 10, "is_library": False}],
        "process": {"project": project, "cwd": project, "pid": 123},
    }


def _hace(seconds):
    return datetime.datetime.now().astimezone() - datetime.timedelta(seconds=seconds)


# --- el primitivo: filtrar por frescura -------------------------------------


def test_since_deja_pasar_lo_reciente(gb_home):
    store.write(_record(_ts(5)))

    assert len(store.read_index(since=_hace(60))) == 1


def test_since_descarta_lo_viejo(gb_home):
    store.write(_record(_ts(3600)))

    assert store.read_index(since=_hace(60)) == []
    assert len(store.read_index()) == 1, "sin since sigue estando en el historico"


def test_load_con_since_no_devuelve_la_captura_vieja(gb_home):
    """El caso que motiva todo esto: pete lo que pete, si la captura no es de
    ahora no se entrega como si lo fuera."""
    store.write(_record(_ts(7200), exc_type="KeyError"))

    assert store.load(since=_hace(120)) is None
    assert store.load()["exception"]["type"] == "KeyError"


def test_load_con_since_elige_la_reciente_habiendo_viejas(gb_home):
    store.write(_record(_ts(9000), exc_type="KeyError"))
    store.write(_record(_ts(2), exc_type="TypeError"))

    record = store.load(since=_hace(60))
    assert record is not None
    assert record["exception"]["type"] == "TypeError"


def test_ts_ilegible_se_descarta_cuando_hay_since(gb_home):
    """No se puede demostrar que sea reciente -> no se entrega. Fallar hacia el
    lado seguro (regla 9), que aqui significa callar en vez de mentir."""
    store.write(_record("no-es-una-fecha"))

    assert store.read_index(since=_hace(60)) == []
    assert len(store.read_index()) == 1


def test_parse_ts_devuelve_none_sin_adivinar():
    assert store.parse_ts(None) is None
    assert store.parse_ts("") is None
    assert store.parse_ts("ayer por la tarde") is None
    assert store.parse_ts("2026-07-29T12:00:00+02:00") is not None


# --- la duracion -------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [("90", 90), ("90s", 90), ("5m", 300), ("2h", 7200), ("1d", 86400), (" 30S ", 30)],
)
def test_duraciones_validas(text, expected):
    assert cli._duration(text) == expected


@pytest.mark.parametrize("text", ["", "   ", "manana", "5x", "-3m", "0s", "m"])
def test_duraciones_invalidas_lanzan(text):
    """Un --since mal escrito no se interpreta 'por lo mejor': interpretarlo
    seria devolver una captura vieja creyendo que es reciente."""
    with pytest.raises(ValueError):
        cli._duration(text)


# --- el contrato del CLI (los codigos de salida son la interfaz) -------------


def test_cli_sale_cero_con_captura_reciente(gb_home, monkeypatch, tmp_path):
    project = tmp_path / "repo"
    project.mkdir()
    monkeypatch.chdir(project)
    store.write(_record(_ts(2), project=str(project)))

    assert cli.main(["last", "--since", "5m", "--json"]) == 0


def test_cli_sale_uno_sin_captura_reciente(gb_home, monkeypatch, tmp_path):
    """Lo que hace util el flag desde un script: 'peto por otra cosa, no hay
    nada que leer' se distingue de 'aqui tienes el estado'."""
    project = tmp_path / "repo"
    project.mkdir()
    monkeypatch.chdir(project)
    store.write(_record(_ts(7200), project=str(project)))

    assert cli.main(["last", "--since", "5m", "--json"]) == 1


def test_cli_sale_dos_con_duracion_invalida(gb_home, monkeypatch, tmp_path):
    """Distinto de 'no hay nada': esto es un error de uso y no debe confundirse
    con una ejecucion limpia sin capturas."""
    monkeypatch.chdir(tmp_path)

    assert cli.main(["last", "--since", "manana"]) == 2


def test_sin_since_el_comportamiento_no_cambia(gb_home, monkeypatch, tmp_path):
    """El contrapeso: `gb last` de siempre sigue devolviendo lo ultimo, sea de
    cuando sea."""
    project = tmp_path / "repo"
    project.mkdir()
    monkeypatch.chdir(project)
    store.write(_record(_ts(99999), project=str(project)))

    assert cli.main(["last", "--json"]) == 0
