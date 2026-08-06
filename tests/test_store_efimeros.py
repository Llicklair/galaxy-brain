"""Las capturas efimeras no son fallos del proyecto, pero tampoco se tiran.

`python -c ...` y la entrada por tuberia producen frames cuyo "fichero" es
`<string>` o `<stdin>`: exploracion, no codigo. Mezclarlas con los fallos reales
llena la libreta de efimeros y entierra lo que si se repite — reportado usando la
herramienta de verdad en otro repo (2026-07-31).

La otra mitad, que es la que importa: se ocultan DICIENDOLO. Ocultar en silencio
seria el mismo fallo que el gate mudo, una lista corta que se lee como "esto es
todo lo que ha pasado".
"""

from galaxybrain import store


def _entry(where):
    return {"type": "ValueError", "where": where, "id": "x", "ts": "2026-07-31T10:00:00+02:00"}


def test_python_c_y_stdin_son_efimeros():
    assert store.is_ephemeral(_entry("<string>:1"))
    assert store.is_ephemeral(_entry("<stdin>:5"))


def test_un_fichero_del_proyecto_no_lo_es():
    assert not store.is_ephemeral(_entry("src/pkg/a.py:7"))
    assert not store.is_ephemeral(_entry("C:/proyecto/src/a.py:7"))


def test_sin_frame_NO_cuenta_como_efimero():
    """Un `?` (tipico de SyntaxError, que no deja frame) tambien le pasa a un
    fichero real. Esconderlo seria peor que el ruido: se perderia un fallo."""
    assert not store.is_ephemeral(_entry("?"))
    assert not store.is_ephemeral(_entry(""))
    assert not store.is_ephemeral({})


def test_gb_last_MARCA_el_efimero_en_vez_de_esconderlo():
    """`list` los aparta; `last` devuelve lo ULTIMO sea lo que sea.

    Presentar un `python -c` de exploracion como "el ultimo fallo" sin decirlo
    manda a buscar en el proyecto algo que nunca estuvo ahi. Pero esconderlo seria
    peor: a veces ES lo que acabas de ejecutar. Se marca. Reportado en uso real.
    """
    from galaxybrain import render

    record = {
        "exception": {"type": "ValueError", "message": "boom"},
        "process": {"project": "/proyecto"},
        "ts": "2026-07-31T10:00:00+02:00",
        "frames": [{"file": "<string>", "line": 1, "function": "<module>"}],
    }
    salida = render.render_record(record, render.Style(False))
    assert "efimero" in salida

    record["frames"] = [{"file": "/proyecto/pkg/a.py", "line": 7, "function": "f"}]
    assert "efimero" not in render.render_record(record, render.Style(False))


def test_el_filtro_deja_pasar_lo_real_y_cuenta_lo_oculto():
    entries = [
        _entry("<string>:1"),
        _entry("src/pkg/a.py:7"),
        _entry("<stdin>:2"),
        _entry("src/pkg/b.py:3"),
    ]
    reales = [e for e in entries if not store.is_ephemeral(e)]
    assert len(reales) == 2
    assert len(entries) - len(reales) == 2  # lo que `gb list` anuncia como oculto


def test_json_y_texto_ensenan_las_mismas_firmas_con_el_mismo_n(monkeypatch, capsys):
    """Con el mismo `-n`, `gb list` y `gb list --json` listan el MISMO conjunto.

    Antes el json no apartaba efimeros y el [:n] hacia el resto: los efimeros
    (mas recientes) empujaban firmas reales fuera de la ventana del json, y la
    maquina veia un listado distinto del humano. Medido 2026-08-06: 4 NameError
    propios en el texto que el --json no traia.
    """
    import json

    from galaxybrain import cli

    # 3 efimeros mas recientes que 2 firmas reales: con -n 3, un json sin filtro
    # se llenaria de efimeros y dejaria fuera las dos reales.
    entries = [_entry("<string>:%d" % i) for i in range(3)] + [
        _entry("src/pkg/a.py:7"),
        _entry("src/pkg/b.py:3"),
    ]
    monkeypatch.setattr(store, "read_index", lambda project=None: entries)
    parser = cli.build_parser()

    cli.cmd_list(parser.parse_args(["list", "-n", "3", "--color", "never"]))
    texto = capsys.readouterr().out

    cli.cmd_list(parser.parse_args(["list", "-n", "3", "--json"]))
    grupos = json.loads(capsys.readouterr().out)
    firmas_json = {(g["type"], g["where"]) for g in grupos}

    assert firmas_json == {
        ("ValueError", "src/pkg/a.py:7"),
        ("ValueError", "src/pkg/b.py:3"),
    }
    for _, where in firmas_json:
        assert where in texto
    # y el texto sigue anunciando lo que aparto, no lo esconde en silencio
    assert "3 efimero(s)" in texto
