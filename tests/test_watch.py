"""El watch como proceso que se lanza solo: opt-in por fichero, candado con
latido, y el borrado del mapa como apagador.

Todo el ciclo de vida es de FICHEROS, no de PIDs: el mapa es el opt-in (sin él,
un hook global no vigila nada), el candado caduca solo por mtime, y borrar el
mapa apaga el watch. Nada que preguntarle al sistema de procesos.
"""

import json
import os

from galaxybrain import cli


def _proyecto(tmp_path):
    (tmp_path / "cosa.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    return str(tmp_path)


def _candado_ajeno(destino, pid=999999):
    ruta = cli._ruta_candado(destino)
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as handle:
        json.dump({"pid": pid, "dest": destino}, handle)
    return ruta


def test_watch_if_changed_sin_mapa_no_arranca(tmp_path):
    """El fichero es el opt-in: un hook global corre en CADA repo y solo vigila
    donde el mapa ya se generó a mano."""
    root = _proyecto(tmp_path)
    destino = str(tmp_path / "mapa.html")

    rc = cli.main(["symbols", root, "--html", destino, "--watch", "--if-changed"])
    assert rc == 0
    assert not os.path.exists(destino)


def test_un_candado_fresco_impide_el_segundo_watch(tmp_path, capsys):
    """Dos watchers sobre el mismo mapa se pisarían el fichero: el segundo no
    arranca, y lo dice."""
    root = _proyecto(tmp_path)
    destino = str(tmp_path / "mapa.html")
    ruta = _candado_ajeno(destino)

    rc = cli.main(["symbols", root, "--html", destino, "--watch"])
    assert rc == 0
    assert "ya hay un watch vivo" in capsys.readouterr().out
    assert os.path.exists(ruta)  # el candado del otro no se toca


def test_un_candado_caducado_se_releva_y_se_suelta_al_salir(tmp_path, monkeypatch):
    """Un proceso muerto sin limpiar no puede vetar watchers para siempre: el
    candado caduca solo por mtime, y al salir se suelta."""
    import time

    root = _proyecto(tmp_path)
    destino = str(tmp_path / "mapa.html")
    with open(destino, "w", encoding="utf-8") as handle:
        handle.write("<!-- viejo -->")
    ruta = _candado_ajeno(destino)
    viejo = time.time() - 300
    os.utime(ruta, (viejo, viejo))

    def _corta(_segundos):
        raise KeyboardInterrupt

    monkeypatch.setattr(time, "sleep", _corta)
    rc = cli.main(["symbols", root, "--html", destino, "--watch"])
    assert rc == 0
    assert not os.path.exists(ruta)


def test_borrar_el_mapa_apaga_el_watch(tmp_path, monkeypatch, capsys):
    import time

    root = _proyecto(tmp_path)
    destino = str(tmp_path / "mapa.html")
    with open(destino, "w", encoding="utf-8") as handle:
        handle.write("<!-- viejo -->")

    def _borra_y_sigue(_segundos):
        if os.path.exists(destino):
            os.remove(destino)
            return
        raise AssertionError("el watch dio otra vuelta con el mapa ya borrado")

    monkeypatch.setattr(time, "sleep", _borra_y_sigue)
    rc = cli.main(["symbols", root, "--html", destino, "--watch"])
    assert rc == 0
    assert "watch apagado" in capsys.readouterr().out
    assert not os.path.exists(cli._ruta_candado(destino))


def test_fondo_relanza_sin_la_bandera_y_vuelve(tmp_path, monkeypatch):
    """--fondo es para hooks: relanza el mismo watch como proceso independiente
    (sin --fondo, o se relanzaría a sí mismo eternamente) y vuelve al instante."""
    import subprocess

    root = _proyecto(tmp_path)
    destino = str(tmp_path / "mapa.html")
    with open(destino, "w", encoding="utf-8") as handle:
        handle.write("x")
    ordenes = []

    class _Proceso:
        pid = 4321

    monkeypatch.setattr(subprocess, "Popen", lambda orden, **_k: ordenes.append(orden) or _Proceso())
    monkeypatch.setattr(
        "sys.argv", ["gb", "symbols", root, "--html", destino, "--watch", "--fondo"]
    )

    rc = cli.main(["symbols", root, "--html", destino, "--watch", "--fondo"])
    assert rc == 0
    assert len(ordenes) == 1
    assert "--fondo" not in ordenes[0]
    assert "galaxybrain.cli" in ordenes[0]
