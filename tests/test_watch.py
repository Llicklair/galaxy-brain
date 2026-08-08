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


def test_leer_una_captura_regenera_el_mapa_solo(tmp_path, monkeypatch):
    """La sonda mira tambien las fuentes de los anillos y los halos (historico,
    lecturas, git local): leer una captura cambia lo que el mapa DIBUJA sin
    tocar ningun .py. Salio en prueba de uso real: los anillos se quedaban
    viejos hasta el siguiente edit."""
    import time

    from galaxybrain import config, store, viz

    root = _proyecto(tmp_path)
    destino = str(tmp_path / "mapa.html")
    with open(destino, "w", encoding="utf-8") as handle:
        handle.write("x")

    llamadas = []
    original = viz.render_graph_cloud

    def _contando(*args, **kwargs):
        llamadas.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(viz, "render_graph_cloud", _contando)

    tics = {"n": 0}

    def _toca_leidas_y_corta(_segundos):
        tics["n"] += 1
        if tics["n"] == 1:
            with open(str(config.home() / store.READS_NAME), "a", encoding="utf-8") as handle:
                handle.write('{"id": "prueba"}\n')
            return
        raise KeyboardInterrupt

    monkeypatch.setattr(time, "sleep", _toca_leidas_y_corta)
    assert cli.main(["symbols", root, "--html", destino, "--watch"]) == 0
    assert len(llamadas) == 2  # una por el arranque, otra por la LECTURA


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


def test_la_firma_no_baja_a_las_carpetas_de_ruido(tmp_path):
    """El tick del watch no puede pagar el arbol de `.git`.

    Podar con `continue` en vez de sobre `dirs` dejaba que `os.walk` siguiera
    bajando: 290 directorios recorridos en vez de 16 en este repo, 22 ms por
    vuelta en vez de 1 (medido el 5-ago-2026 al presupuestar el sondeo de varios
    arboles a la vez). El coste lo pagaba cada vuelta, hubiera cambios o no.
    """
    (tmp_path / "vivo.py").write_text("x = 1\n", encoding="utf-8")
    for ruido in (".git", "__pycache__", ".venv", "node_modules", ".pytest_cache"):
        hondo = tmp_path / ruido / "hondo"
        hondo.mkdir(parents=True)
        (hondo / "trampa.py").write_text("y = 2\n", encoding="utf-8")

    nombres = [marca[0] for marca in cli._firma_py(str(tmp_path))]
    assert nombres == ["vivo.py"]


def test_una_carpeta_que_solo_CONTIENE_el_nombre_del_ruido_si_se_mira(tmp_path):
    """`.github` no es `.git`: la poda va por nombre exacto, no por subcadena.

    El filtro viejo comparaba la ruta entera contra la subcadena, asi que un
    proyecto colgando de cualquier carpeta con `.git` dentro del nombre se
    quedaba sin vigilar y sin decirlo.
    """
    sitio = tmp_path / ".github" / "scripts"
    sitio.mkdir(parents=True)
    (sitio / "util.py").write_text("z = 3\n", encoding="utf-8")
    nombres = [marca[0] for marca in cli._firma_py(str(tmp_path))]
    assert nombres == ["util.py"]


def test_el_watch_se_apaga_si_el_codigo_de_gb_cambia_en_disco(tmp_path, monkeypatch, capsys):
    """Un watch de 8 horas sirvio un mapa fantasma toda la noche (6-ago-2026):
    su codigo vivia congelado en memoria mientras el disco avanzaba, y piso
    cada regeneracion nueva durante horas (tres cazas falsas hasta dar con el).
    Cambio el codigo en disco -> el vigilante lo dice y MUERE."""
    import time

    root = _proyecto(tmp_path)
    destino = str(tmp_path / "mapa.html")
    with open(destino, "w", encoding="utf-8") as handle:
        handle.write("<!-- viejo -->")

    vueltas = []

    def _cambia_el_codigo(_segundos):
        vueltas.append(1)
        if len(vueltas) == 1:
            monkeypatch.setattr(cli, "_codigo_del_motor", lambda base=None: ("otro",))
            return
        raise AssertionError("el watch dio otra vuelta con el codigo ya cambiado")

    relanzados = []
    monkeypatch.setattr(cli, "_watch_en_fondo", lambda: relanzados.append(1) or 0)
    monkeypatch.setattr(time, "sleep", _cambia_el_codigo)
    rc = cli.main(["symbols", root, "--html", destino, "--watch"])
    assert rc == 0
    # el invariante que importa: NO da otra vuelta con el motor viejo (lo fija
    # el AssertionError de _cambia_el_codigo). Lo que cambia desde el 8-ago es
    # que ya no exige un relanzamiento a mano: se releva a si mismo.
    assert "me reinicio con la version nueva" in capsys.readouterr().out
    assert relanzados == [1]
    assert not os.path.exists(cli._ruta_candado(destino))  # el candado se suelta ANTES


def test_la_firma_del_motor_cambia_si_un_py_cambia(tmp_path):
    base = tmp_path / "paquete"
    base.mkdir()
    (base / "a.py").write_text("x = 1\n", encoding="utf-8")
    antes = cli._codigo_del_motor(str(base))
    (base / "a.py").write_text("x = 1  # tocado\n", encoding="utf-8")
    despues = cli._codigo_del_motor(str(base))
    assert antes != despues
    assert cli._codigo_del_motor(str(tmp_path / "no-existe")) == ()


def test_la_firma_de_actividad_ve_worktrees_y_consolas(tmp_path):
    """Los agentes trabajan en OTRO arbol: sin esta firma, la sonda del watch
    (solo .py del proyecto) dejo el lienzo mudo durante tres tandas enteras del
    bucle (6-ago, reportado mirando el mapa en vivo). Worktree que aparece,
    consola que crece y worktree que se recoge: los tres mueven la firma."""
    root = str(tmp_path)
    assert cli._firma_actividad(root) == ()

    base = os.path.join(root, ".claude", "worktrees")
    os.makedirs(os.path.join(base, "bucle-A"))
    con_worktree = cli._firma_actividad(root)
    assert con_worktree

    log = os.path.join(base, "bucle-A.consola.log")
    with open(log, "w", encoding="utf-8") as handle:
        handle.write("linea\n")
    con_consola = cli._firma_actividad(root)
    assert con_consola != con_worktree

    with open(log, "a", encoding="utf-8") as handle:
        handle.write("otra\n")
    assert cli._firma_actividad(root) != con_consola


def test_el_watch_en_fondo_no_abre_ventanas(monkeypatch):
    """Windows: un proceso DETACHED (sin consola) que lanza `git` hace que el SO
    le cree una ventana a cada hijo — y el watch llama a git en cada
    regeneracion, asi que con un agente trabajando el escritorio parpadeaba
    cada 3 s (reportado en uso real, 8-ago). CREATE_NO_WINDOW le da una consola
    OCULTA que los hijos heredan."""
    import subprocess
    import sys

    capturado = {}

    class _Popen:
        def __init__(self, orden, **kwargs):
            capturado["orden"] = orden
            capturado["kwargs"] = kwargs

    monkeypatch.setattr(subprocess, "Popen", _Popen)
    monkeypatch.setattr(sys, "argv", ["gb", "symbols", "--html", "--watch", "--fondo"])
    assert cli._watch_en_fondo() == 0

    assert "--fondo" not in capturado["orden"]  # el hijo no vuelve a relanzarse
    if os.name == "nt":
        flags = capturado["kwargs"]["creationflags"]
        assert flags & 0x08000000, "falta CREATE_NO_WINDOW: los hijos abriran ventana"
        assert not flags & 0x00000008, "DETACHED_PROCESS es justo lo que provoca el parpadeo"
        assert flags & 0x00000200  # sin morir con el Ctrl+C del padre
    else:
        assert capturado["kwargs"]["start_new_session"] is True


def test_el_watch_se_reinicia_solo_cuando_cambia_el_codigo(tmp_path, monkeypatch, capsys):
    """Morir con el motor viejo es correcto; exigir que alguien lo relance, no.
    Cada commit a gb mataba el watch y habia que rearrancarlo a mano — diez
    veces en una sola sesion (8-ago). Ahora se reinicia solo, y SIEMPRE tras
    soltar el candado: al reves el hijo se encontraria la puerta cerrada."""
    destino = str(tmp_path / "mapa.html")
    with open(destino, "w", encoding="utf-8") as handle:
        handle.write("<html></html>")

    orden = []
    monkeypatch.setattr(cli, "_watch_en_fondo", lambda: orden.append("relanzado") or 0)
    monkeypatch.setattr(cli, "_soltar_candado", lambda c: orden.append("candado suelto"))
    motores = iter(["motor-viejo", "motor-NUEVO"])
    monkeypatch.setattr(cli, "_codigo_del_motor", lambda: next(motores))

    args = type("A", (), {"html": destino, "intervalo": 1, "refresco": 3, "capas": False,
                          "since": None, "path": str(tmp_path)})()
    assert cli._vigilar(str(tmp_path), args) == 0

    salida = capsys.readouterr().out
    assert "me reinicio con la version nueva" in salida
    # el orden importa: primero soltar, luego relanzar
    assert orden == ["candado suelto", "relanzado"]
