"""El ciclo del error, visible: capturado -> leida -> intervenido -> sin reaparecer.

Cada eslabon es un hecho externo (historico, leidas.jsonl, git) y NUNCA un
veredicto: gb no re-ejecuta nada, asi que la ausencia de ocurrencias se etiqueta
como lo que es — "sin reaparecer desde hace N d" — indistinguible de "no corrio".
Estos tests fijan la cadena entera sobre un repo git de verdad, y que la palabra
prohibida no se cuele en ninguna salida.
"""

import datetime
import os
import subprocess

from galaxybrain import changes, cli, graph, store, symbols


def _run(cwd, *args):
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


def _repo(tmp_path):
    root = str(tmp_path / "proyecto")
    os.makedirs(root, exist_ok=True)
    _run(root, "git", "init", "-q")
    _run(root, "git", "config", "user.email", "t@t")
    _run(root, "git", "config", "user.name", "t")
    _run(root, "git", "config", "commit.gpgsign", "false")
    return root


def _commit(root, msg):
    _run(root, "git", "add", "-A")
    _run(root, "git", "commit", "-q", "-m", msg)


def _write(root, rel, content="def f():\n    return 1\n"):
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    return path


def _captura(root, fichero, cuando, tipo="ValueError"):
    """Una captura fingida en el historico, con el ts que pida el test."""
    registro = {
        "ts": cuando.isoformat(timespec="seconds"),
        "exception": {"type": tipo, "message": "boom"},
        "process": {"project": root, "cwd": root, "pid": 1},
        "frames": [{"file": fichero, "line": 2, "is_library": False}],
    }
    assert store.write(registro) is not None
    return registro["id"]


def _ahora():
    return datetime.datetime.now().astimezone()


def test_la_cadena_completa_llega_a_en_silencio_con_un_commit_posterior(tmp_path):
    """Fallo ayer, leido, fichero commiteado hoy y sin volver a petar: los cuatro
    eslabones son hechos y el embudo los cuenta 1-1-1-1."""
    root = _repo(tmp_path)
    fichero = _write(root, "app.py")
    ident = _captura(root, fichero, _ahora() - datetime.timedelta(days=1))
    store.mark_read(ident, project=root)
    _commit(root, "toca app.py despues del fallo")

    ciclo = changes.ciclo_errores(root, store.read_index(project=root), store.read_ids())

    assert ciclo["embudo"] == {
        "capturadas": 1,
        "leidas": 1,
        "intervenidas": 1,
        "sin_reaparecer": 1,
    }
    firma = ciclo["firmas"][0]
    assert firma["estado"] == "en-silencio"
    assert firma["leida"] is True
    assert firma["intervencion"]["commit"]
    # La ventana temporal SIEMPRE explicita: sin ella "sin reaparecer" se leeria
    # como veredicto.
    assert firma["silencio_dias"] is not None and firma["silencio_dias"] >= 0


def test_sin_commit_posterior_al_fallo_la_firma_no_es_intervenida(tmp_path):
    """El fichero se commiteo ANTES de toda ocurrencia: tocarlo antes del fallo
    no es intervenir sobre el fallo."""
    root = _repo(tmp_path)
    fichero = _write(root, "app.py")
    _commit(root, "commit previo al fallo")
    _captura(root, fichero, _ahora() + datetime.timedelta(minutes=5))

    ciclo = changes.ciclo_errores(root, store.read_index(project=root), store.read_ids())

    firma = ciclo["firmas"][0]
    assert firma["intervencion"] is None
    assert firma["estado"] == "capturada"
    assert ciclo["embudo"]["intervenidas"] == 0
    assert ciclo["embudo"]["sin_reaparecer"] == 0


def test_la_firma_reaparecida_tras_la_intervencion_queda_intervenida_y_visible(tmp_path):
    """Commit posterior al primer fallo y la firma volvio a petar despues: la
    intervencion NO se borra — queda 'intervenida' con la reaparicion contada y
    FUERA de sin_reaparecer. Una intervencion que no aguanto es informacion
    valiosa, no ruido (y con la semantica antigua este estado era inalcanzable)."""
    root = _repo(tmp_path)
    fichero = _write(root, "app.py")
    _captura(root, fichero, _ahora() - datetime.timedelta(days=2))
    _commit(root, "intervencion entre las dos ocurrencias")
    _captura(root, fichero, _ahora() + datetime.timedelta(hours=2))

    ciclo = changes.ciclo_errores(root, store.read_index(project=root), store.read_ids())

    firma = ciclo["firmas"][0]
    assert firma["count"] == 2
    assert firma["intervencion"] is not None  # posterior a ALGUNA ocurrencia: basta
    assert firma["estado"] == "intervenida"
    assert firma["reapariciones"] == 1
    assert firma["silencio_dias"] is None  # reaparecida: no hay ventana de silencio
    assert ciclo["embudo"]["intervenidas"] == 1
    assert ciclo["embudo"]["sin_reaparecer"] == 0


def test_el_embudo_diverge_cuando_una_intervencion_no_aguanta(tmp_path):
    """Dos firmas con commit posterior y solo una sin reaparecer: el embudo dice
    2 capturadas · 2 intervenidas · 1 sin reaparecer — el recuento que la
    semantica anterior hacia imposible (intervenidas era siempre igual a
    sin_reaparecer, y el color de 'intervenida' nunca llegaba a pintarse)."""
    root = _repo(tmp_path)
    aguanta = _write(root, "aguanta.py")
    reincide = _write(root, "reincide.py")
    _captura(root, aguanta, _ahora() - datetime.timedelta(days=2), tipo="ValueError")
    _captura(root, reincide, _ahora() - datetime.timedelta(days=2), tipo="KeyError")
    _commit(root, "toca los dos ficheros despues de los fallos")
    _captura(root, reincide, _ahora() + datetime.timedelta(hours=2), tipo="KeyError")

    ciclo = changes.ciclo_errores(root, store.read_index(project=root), store.read_ids())

    assert ciclo["embudo"] == {
        "capturadas": 2,
        "leidas": 0,
        "intervenidas": 2,
        "sin_reaparecer": 1,
    }
    por_tipo = {f["type"]: f for f in ciclo["firmas"]}
    assert por_tipo["ValueError"]["estado"] == "en-silencio"
    assert por_tipo["KeyError"]["estado"] == "intervenida"
    assert por_tipo["KeyError"]["reapariciones"] == 1


def test_la_ficha_ensena_la_reaparicion_tras_la_intervencion(tmp_path):
    """El texto "reaparecida N vez/veces despues" era codigo muerto con la
    semantica antigua; ahora es el rastro visible de la intervencion que no
    aguanto — y jamas puede convivir con "sin reaparecer"."""
    root = _repo(tmp_path)
    fichero = _write(root, "app.py")
    _captura(root, fichero, _ahora() - datetime.timedelta(days=2))
    _commit(root, "intervencion")
    _captura(root, fichero, _ahora() + datetime.timedelta(hours=2))

    ciclo = changes.ciclo_errores(root, store.read_index(project=root), store.read_ids())
    linea = cli._linea_firma(ciclo["firmas"][0])
    assert "tocado despues" in linea
    assert "reaparecida 1 vez/veces despues" in linea
    assert "sin reaparecer" not in linea


def test_la_ventana_de_silencio_menor_de_un_dia_no_dice_cero_dias(tmp_path):
    """Commit de hoy: "sin reaparecer desde hace 0 d" degenera en un cero que no
    informa. Por debajo de 1 dia la ficha usa la granularidad de relative_time
    sobre la fecha del commit de intervencion; a partir de 1 dia, los dias."""
    root = _repo(tmp_path)
    fichero = _write(root, "app.py")
    _captura(root, fichero, _ahora() - datetime.timedelta(hours=6))
    _commit(root, "intervencion de hoy")

    ciclo = changes.ciclo_errores(root, store.read_index(project=root), store.read_ids())
    firma = ciclo["firmas"][0]
    assert firma["estado"] == "en-silencio"
    assert firma["silencio_dias"] == 0
    assert firma["intervencion"]["ts"]  # la fecha que cli necesita para formatear

    linea = cli._linea_firma(firma)
    assert "0 d" not in linea
    # El commit es de hace segundos: relative_time da "hace Ns/Nmin/Nh", nunca dias.
    assert "sin reaparecer desde hace" in linea


def test_el_batch_de_commits_dice_lo_mismo_que_el_camino_por_fichero(tmp_path):
    """Un solo `git log` para todos los ficheros (presupuesto de < 1 s por
    edicion) tiene que devolver EXACTAMENTE lo que devolvia un `git log -1` por
    fichero: el atajo de latencia no puede cambiar el hecho."""
    root = _repo(tmp_path)
    uno = _write(root, "uno.py")
    _commit(root, "commit de uno")
    dos = _write(root, "pkg/dos.py")
    _commit(root, "commit de dos")
    _write(root, "uno.py", "def f():\n    return 2\n")
    _commit(root, "uno otra vez, para que los ultimos commits difieran")

    desde = _ahora() - datetime.timedelta(days=1)
    batch = changes._ultimos_commits(root, [uno, dos], desde)
    assert batch is not None

    claves = {f: os.path.normcase(os.path.normpath(f)) for f in (uno, dos)}
    for fichero, clave in claves.items():
        assert batch[clave] is not None
        assert batch[clave] == changes._ultimo_commit(root, fichero, {})
    # Commits distintos de verdad: si el parseo mezclara cabeceras, coincidirian.
    assert batch[claves[uno]][0] != batch[claves[dos]][0]


def test_una_captura_nueva_invalida_la_forma_registrada_del_mapa(tmp_path):
    """--if-changed y el mantenimiento comparaban solo la forma del CODIGO: una
    captura nueva no regeneraba el mapa y el ciclo pintado mentia por omision
    toda la sesion. La forma registrada lleva ahora la huella del historico."""
    root = _repo(tmp_path)
    fichero = _write(root, "app.py")
    _commit(root, "inicial")
    destino = str(tmp_path / "mapa.html")
    assert cli.main(["graph", root, "--html", destino]) == 0

    informe = symbols.analyze(root)
    grafo = graph.analyze(root)
    assert cli._html_forma_igual(root, destino, informe, grafo) is True

    _captura(root, fichero, _ahora())
    assert cli._html_forma_igual(root, destino, informe, grafo) is False


def test_la_palabra_prohibida_no_aparece_ni_en_status_ni_en_el_html(tmp_path, capsys, monkeypatch):
    """gb no puede verificar un arreglo (seria re-ejecutar), asi que la salida no
    puede afirmarlo ni en el estado mas verde del ciclo. Test literal."""
    root = _repo(tmp_path)
    fichero = _write(root, "app.py")
    ident = _captura(root, fichero, _ahora() - datetime.timedelta(days=1))
    store.mark_read(ident, project=root)
    _commit(root, "toca app.py")
    monkeypatch.chdir(root)

    assert cli.main(["status"]) == 0
    salida = capsys.readouterr().out
    assert "ciclo" in salida
    assert "1 capturadas · 1 leidas · 1 intervenidas · 1 sin reaparecer" in salida
    assert "corregido" not in salida.lower()

    destino = str(tmp_path / "mapa.html")
    assert cli.main(["graph", root, "--html", destino]) == 0
    capsys.readouterr()
    with open(destino, "r", encoding="utf-8") as handle:
        html = handle.read()
    assert "corregido" not in html.lower()
    # Los otros dos sitios: la cabecera lleva el embudo y el nodo su cadena.
    assert "sin reaparecer" in html
    assert "en-silencio" in html
    assert "tocado despues" in html


def test_sin_capturas_del_proyecto_status_no_ensena_embudo(tmp_path, capsys, monkeypatch):
    """Un embudo de ceros seria ruido: la linea solo existe si hay capturas."""
    root = _repo(tmp_path)
    _write(root, "app.py")
    _commit(root, "inicial")
    monkeypatch.chdir(root)

    assert cli.main(["status"]) == 0
    assert "ciclo" not in capsys.readouterr().out


def test_el_join_de_rutas_aguanta_caja_y_separadores_mezclados(tmp_path):
    """La trampa conocida de Windows: los frames guardan la ruta como la vio el
    interprete ('c:' vs 'C:', barras mezcladas) y ya costo un bug de cache. El
    join con git y con el nodo del mapa compara por normcase, no literal."""
    root = _repo(tmp_path)
    fichero = _write(root, "pkg/util.py")
    if os.name == "nt":
        unidad, resto = os.path.splitdrive(fichero)
        variante = unidad.swapcase() + resto.replace("\\", "/")
    else:
        # En POSIX la caja distingue de verdad; la parte portable de la trampa
        # son los separadores redundantes, que normpath unifica.
        variante = os.path.join(root, ".", "pkg", "util.py")
    _captura(root, variante, _ahora() - datetime.timedelta(days=1))
    _commit(root, "toca pkg/util.py")

    ciclo = changes.ciclo_errores(root, store.read_index(project=root), store.read_ids())
    firma = ciclo["firmas"][0]
    assert firma["intervencion"] is not None, "git no encontro el fichero con la ruta variante"
    assert firma["estado"] == "en-silencio"

    # Y la ruta variante aterriza en el nodo del mapa que le corresponde.
    informe = symbols.analyze(root)
    mapa = cli._ciclo_para_mapa(root, informe)
    assert "pkg.util" in mapa["nodos"]
    assert mapa["nodos"]["pkg.util"]["estado"] == "en-silencio"
    assert any("util.py:2" in linea for linea in mapa["nodos"]["pkg.util"]["lineas"])


def test_las_capturas_para_el_mapa_traen_nodo_id_y_estado_de_lectura(tmp_path):
    """La consola de errores entra al lienzo POR DEFECTO: cada captura viaja
    con su nodo del grafo, su id (para `gb show`) y si esta leida — el feed
    del mapa dice `peta` sin que nadie tenga que saber mirar una capa."""
    root = _repo(tmp_path)
    fichero = _write(root, "pkg/util.py")
    _commit(root, "base")
    id_captura = _captura(root, fichero, _ahora())

    informe = symbols.analyze(root)
    (captura,) = cli._capturas_para_mapa(root, informe)
    assert captura["nodo"] == "pkg.util"
    assert captura["id"] == id_captura
    assert captura["tipo"] == "ValueError"
    assert captura["leida"] is False

    store.mark_read(id_captura)
    (releida,) = cli._capturas_para_mapa(root, informe)
    assert releida["leida"] is True


def test_sin_capturas_el_mapa_no_lleva_ni_rastro_de_consola(tmp_path):
    root = _repo(tmp_path)
    _write(root, "pkg/util.py")
    _commit(root, "base")
    assert cli._capturas_para_mapa(root, symbols.analyze(root)) == []
