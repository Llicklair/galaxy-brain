"""El historico: append-only, fuera del proyecto observado, y tolerante a
ficheros corruptos (un fallo del disco no puede invalidar la libreta entera)."""

import json
from pathlib import Path

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


def test_load_con_la_captura_borrada_a_mano_no_revienta_ni_miente(gb_home):
    """El indice es append-only pero las capturas son ficheros sueltos: borrar la
    carpeta `errors/` a mano deja entradas huerfanas. Devolver None es lo unico
    honesto — dar la ANTERIOR seria ensenar el estado de otro fallo con la
    confianza del ultimo, que es justo el error que la consola existe para evitar."""
    store.write(_record(ts="2026-07-29T12:00:00+02:00"))
    store.write(_record(ts="2026-07-29T13:00:00+02:00", exc_type="KeyError"))

    ultima = store.read_index()[0]
    Path(ultima["path"]).unlink()

    assert store.load() is None
    assert len(store.read_index()) == 2  # el indice no se toca: sigue siendo el historico
    assert store.load(ultima["id"]) is None


def test_load_con_el_json_de_la_captura_corrupto_devuelve_none(gb_home):
    """Un fichero a medio escribir (disco lleno, proceso matado) no puede
    propagar una excepcion al que viene a LEER un fallo — regla 9."""
    store.write(_record())
    entrada = store.read_index()[0]
    Path(entrada["path"]).write_text("{esto se quedo a medio", encoding="utf-8")

    assert store.load() is None
    assert store.load(entrada["id"]) is None


def test_load_por_prefijo_de_id_y_por_un_id_que_no_existe(gb_home):
    """`gb show` acepta el id recortado del aviso. Un prefijo que no casa con
    nada es None, no la ultima captura por descarte."""
    store.write(_record())
    ident = store.read_index()[0]["id"]

    assert store.load(ident[:8])["exception"]["type"] == "ValueError"
    assert store.load("no-existe-este-id") is None


def test_con_timestamps_iguales_el_orden_es_el_de_escritura_invertido(gb_home):
    """Dos capturas del mismo segundo (dos hilos, un bucle rapido) no pueden
    salir en orden arbitrario: `gb list` seria distinto en cada pasada. El
    desempate lo pone el indice, que es append-only — la ultima escrita, primera."""
    mismo = "2026-07-29T12:00:00+02:00"
    store.write(_record(ts=mismo, exc_type="ValueError"))
    store.write(_record(ts=mismo, exc_type="KeyError"))
    store.write(_record(ts=mismo, exc_type="TypeError"))

    assert [e["type"] for e in store.read_index()] == ["TypeError", "KeyError", "ValueError"]
    assert store.load()["exception"]["type"] == "TypeError"


def test_si_el_home_no_se_puede_crear_se_falla_hacia_el_lado_seguro(gb_home, tmp_path, monkeypatch):
    """Camino caliente: quien llama a write() esta en mitad de la muerte de un
    proceso ajeno. Un home imposible (aqui, un FICHERO donde deberia ir la
    carpeta) devuelve None y deja leer vacio; nunca lanza encima del fallo real."""
    ocupado = tmp_path / "ocupado"
    ocupado.write_text("no soy una carpeta", encoding="utf-8")
    monkeypatch.setenv("GB_HOME", str(ocupado / "gb-home"))

    assert store.write(_record()) is None
    assert store.read_index() == []
    assert store.read_stats() == (0, 0, 0)
    assert store.read_ids() == set()
    assert store.uso_stats() == {}
    store.mark_read("uno")  # silencioso
    store.mark_uso("gb list")  # silencioso

def test_un_id_nulo_en_el_indice_no_revienta_la_carga(gb_home):
    """Una linea de JSON valido con "id": null pasa el filtro de read_index (es
    un dict legal) y reventaba load() con AttributeError (None.startswith).
    Regla 9: un registro raro se salta, no tumba la consulta entera."""
    store.write(_record())
    with open(gb_home / store.INDEX_NAME, "a", encoding="utf-8") as handle:
        handle.write('{"id": null, "ts": "2026-08-06T10:00:00+02:00", '
                     '"type": "X", "where": "a.py:1"}\n')

    buena = next(e for e in store.read_index() if e.get("id"))
    assert store.load(buena["id"][:8]) is not None
    assert store.load("id-que-no-existe") is None


def test_un_syntaxerror_dice_de_que_fichero_viene(gb_home):
    """Un SyntaxError no deja frame —el interprete no llego a ejecutar el
    fichero— pero la excepcion SI sabe cual es. Sin esto se archivaba con sitio
    "?" y, como un `?` puede ser un fichero real, escapaba al filtro de
    efimeros: 7 scripts por stdin acabaron en la cola de pendientes sin decir de
    donde venian (triaje del 8-ago)."""
    registro = {
        "ts": "2026-08-08T10:00:00+02:00",
        "exception": {"type": "SyntaxError", "message": "unterminated string literal",
                      "origen": "<stdin>:24"},
        "process": {"project": "/proyecto"},
        "frames": [],
    }
    assert store.write(registro) is not None
    (entrada,) = store.read_index()
    assert entrada["where"] == "<stdin>:24"
    # y ahora el filtro de efimeros SI puede verlo por lo que es
    assert store.is_ephemeral(entrada)


def test_sin_origen_ni_frames_el_sitio_sigue_siendo_desconocido(gb_home):
    """No se inventa: si la excepcion no sabe de donde viene, se dice."""
    registro = {
        "ts": "2026-08-08T10:00:00+02:00",
        "exception": {"type": "RuntimeError", "message": "x"},
        "process": {"project": "/proyecto"},
        "frames": [],
    }
    store.write(registro)
    assert store.read_index()[0]["where"] is None
