"""El historico: append-only, fuera del proyecto observado, y tolerante a
ficheros corruptos (un fallo del disco no puede invalidar la libreta entera)."""

import json

from galaxybrain import store


def _record(ts="2026-07-29T12:00:00+02:00", exc_type="ValueError", project="/tmp/proyecto"):
    return {
        "schema": 1,
        "ts": ts,
        "exception": {"type": exc_type, "message": "roto", "chain": []},
        "frames": [
            {"file": "/tmp/proyecto/app.py", "line": 10, "is_library": False},
            {"file": "/usr/lib/python3/json.py", "line": 5, "is_library": True},
        ],
        "process": {"project": project, "cwd": project, "pid": 123},
    }


def test_escribe_fuera_del_proyecto_observado(gb_home, tmp_path):
    project = tmp_path / "mi-repo"
    project.mkdir()
    path = store.write(_record(project=str(project)))

    assert path is not None
    assert gb_home in path.parents
    assert project not in path.parents  # regla 7: no ensuciar el repo observado


def test_el_indice_es_append_only(gb_home):
    store.write(_record(ts="2026-07-29T12:00:00+02:00"))
    store.write(_record(ts="2026-07-29T13:00:00+02:00", exc_type="KeyError"))

    lines = (gb_home / store.INDEX_NAME).read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["type"] == "ValueError"
    assert json.loads(lines[1])["type"] == "KeyError"


def test_el_indice_apunta_al_frame_del_usuario_no_al_de_libreria(gb_home):
    store.write(_record())
    entry = store.read_index()[0]
    assert entry["where"].endswith("app.py:10")


def test_lo_mas_reciente_primero(gb_home):
    store.write(_record(ts="2026-07-29T12:00:00+02:00"))
    store.write(_record(ts="2026-07-29T13:00:00+02:00", exc_type="KeyError"))
    assert [e["type"] for e in store.read_index()] == ["KeyError", "ValueError"]


def test_una_linea_corrupta_no_invalida_el_historico(gb_home):
    store.write(_record())
    with open(gb_home / store.INDEX_NAME, "a", encoding="utf-8") as handle:
        handle.write("{esto no es json\n")
    store.write(_record(exc_type="TypeError"))

    assert len(store.read_index()) == 2


def test_filtra_por_proyecto(gb_home, tmp_path):
    uno, dos = tmp_path / "uno", tmp_path / "dos"
    uno.mkdir()
    dos.mkdir()
    store.write(_record(project=str(uno)))
    store.write(_record(project=str(dos), exc_type="KeyError"))

    assert [e["type"] for e in store.read_index(project=str(uno))] == ["ValueError"]


def test_dos_proyectos_con_el_mismo_nombre_no_se_mezclan(gb_home, tmp_path):
    primero = tmp_path / "a" / "api"
    segundo = tmp_path / "b" / "api"
    primero.mkdir(parents=True)
    segundo.mkdir(parents=True)

    assert store._slug(str(primero)) != store._slug(str(segundo))


def test_load_sin_id_devuelve_el_ultimo(gb_home):
    store.write(_record(ts="2026-07-29T12:00:00+02:00"))
    store.write(_record(ts="2026-07-29T13:00:00+02:00", exc_type="KeyError"))
    assert store.load()["exception"]["type"] == "KeyError"


def test_write_nunca_lanza_aunque_el_registro_sea_basura(gb_home):
    assert store.write({"esto": object()}) is None  # no serializable → None, no excepcion


def test_summarize_agrupa_por_firma_y_cuenta():
    # Entradas de lo más reciente a lo más antiguo, como las da read_index.
    entries = [
        {"type": "KeyError", "where": "a.py:6", "ts": "2026-07-29T15:00:00+02:00",
         "id": "z", "message": "empresa", "project": "/p"},
        {"type": "KeyError", "where": "a.py:6", "ts": "2026-07-29T14:00:00+02:00",
         "id": "y", "message": "pro", "project": "/p"},
        {"type": "ValueError", "where": "b.py:2", "ts": "2026-07-29T13:00:00+02:00",
         "id": "x", "message": "roto", "project": "/p"},
    ]
    groups = store.summarize(entries)

    assert [(g["type"], g["count"]) for g in groups] == [("KeyError", 2), ("ValueError", 1)]
    frecuente = groups[0]
    assert frecuente["last_id"] == "z"                       # la ocurrencia más nueva
    assert frecuente["last_message"] == "empresa"
    assert frecuente["first_ts"].startswith("2026-07-29T14")  # la más antigua del grupo


def test_summarize_mismo_tipo_distinto_sitio_no_se_mezcla():
    entries = [
        {"type": "KeyError", "where": "a.py:6", "ts": "2026-07-29T15:00:00+02:00", "id": "1"},
        {"type": "KeyError", "where": "b.py:9", "ts": "2026-07-29T14:00:00+02:00", "id": "2"},
    ]
    groups = store.summarize(entries)
    assert len(groups) == 2  # misma clase, sitios distintos = dos firmas
    assert all(g["count"] == 1 for g in groups)
