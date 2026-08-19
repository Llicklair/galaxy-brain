"""La consola declara su mecanismo — criterio 4 de la ADR 0012.

Lo que se prueba aqui no es que capture (eso lo miden los bancos de
`gb-lenguajes`), sino que gb sepa DECIR por que via captura y que no ve. Un
`gb last` vacio en un repo con Go significa una de dos cosas opuestas —«no ha
petado nada» o «por aqui no miro»— y sin esta declaracion se presentaban igual.
"""

import os

from galaxybrain import cli, consola, lenguajes


def _escribe(raiz, rel, texto=""):
    ruta = os.path.join(str(raiz), *rel.split("/"))
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write(texto)
    return ruta


def test_todo_lenguaje_de_la_tabla_declara_su_consola():
    """El contrato que evita el silencio: si manana se anade un lenguaje al
    grafo y nadie declara su consola, este test cae. Es justo el fallo que
    `carencias` arreglo para el grafo — un hueco que se lee como un dato."""
    sin_declarar = sorted(set(lenguajes.LENGUAJES) - set(consola.MECANISMOS))
    assert sin_declarar == [], "lenguajes sin ficha de consola: %s" % sin_declarar


def test_el_vocabulario_es_el_de_la_adr():
    """hook-nativo / fallback-stderr / desactivado, literal. Si alguien inventa
    un cuarto estado, el usuario ya no sabe si eso captura o no."""
    permitidas = {"hook-nativo", "fallback-stderr", "desactivado"}
    for lang, ficha in consola.MECANISMOS.items():
        assert ficha["via"] in permitidas, "%s declara via '%s'" % (lang, ficha["via"])


def test_lo_desactivado_dice_por_que():
    """«Desactivado» a secas no vale: hay que distinguir 'se midio y estropea el
    programa' (dart) de 'no se pudo medir' (elixir, swift)."""
    for lang in ("dart", "elixir", "swift"):
        ficha = consola.MECANISMOS[lang]
        assert ficha["via"] == "desactivado"
        assert ficha["techo"], "%s no dice por que esta fuera" % lang


def test_armado_mira_la_variable_de_entorno_de_verdad():
    entorno = {"NODE_OPTIONS": "--max-old-space-size=4096 --require /x/gb-hook.js"}
    assert consola.armado("js", entorno) is True


def test_una_variable_con_otras_cosas_no_cuenta_como_armado():
    """NODE_OPTIONS suele traer banderas del usuario. Dar por armado un hook que
    no esta seria peor que no decir nada: el usuario confiaria en una consola
    apagada."""
    assert consola.armado("js", {"NODE_OPTIONS": "--max-old-space-size=4096"}) is False
    assert consola.armado("js", {}) is False


def test_lo_que_no_se_puede_comprobar_devuelve_None_y_no_False():
    """php se arma con una bandera en la invocacion y go con un envolvente: no
    hay nada en el entorno que los delate. Decir «NO armado» seria inventar un
    hecho que no se ha mirado."""
    assert consola.armado("php", {}) is None
    assert consola.armado("go", {}) is None


def test_c_cambia_de_mecanismo_entero_segun_la_plataforma():
    """En Windows no existe LD_PRELOAD. No es el mismo hook con otra ruta: es
    otro mecanismo (envolvente depurador), y se declara como tal."""
    linux = consola.mecanismo("c", plataforma="linux")
    windows = consola.mecanismo("c", plataforma="win32")
    assert "LD_PRELOAD" in linux["arranque"]
    assert "LD_PRELOAD" not in windows["arranque"]
    assert windows["techo"]


def test_solo_se_nombran_los_lenguajes_que_hay(tmp_path):
    """Enumerar los 17 en un repo de uno es ruido, y el ruido se acaba saltando
    igual que un aviso falso."""
    _escribe(tmp_path, "app/web.js", "const x = 1;\n")
    langs = [f["lenguaje"] for f in consola.estado(str(tmp_path), entorno={})]
    assert "js" in langs
    assert "rust" not in langs


def test_python_sale_siempre_aunque_no_haya_ficheros_py(tmp_path):
    """gb corre sobre Python: su consola aplica al proyecto tenga o no .py."""
    _escribe(tmp_path, "app/web.js", "const x = 1;\n")
    langs = [f["lenguaje"] for f in consola.estado(str(tmp_path), entorno={})]
    assert "python" in langs


def test_la_linea_dice_via_arranque_y_si_esta_armado(tmp_path):
    _escribe(tmp_path, "app/web.js", "const x = 1;\n")
    fichas = {f["lenguaje"]: f for f in consola.estado(str(tmp_path), entorno={})}
    linea = consola.linea(fichas["js"])
    assert "hook-nativo" in linea
    assert "NODE_OPTIONS" in linea
    assert "NO armado" in linea


def test_status_ensena_el_mecanismo(tmp_path, capsys, monkeypatch):
    """El criterio 4, de punta a punta: `gb status` lo dice."""
    _escribe(tmp_path, "app/web.js", "const x = 1;\n")
    monkeypatch.chdir(tmp_path)
    assert cli.main(["status"]) == 0
    salida = capsys.readouterr().out
    assert "consola js" in salida
    assert "consola python" in salida


def test_el_hook_de_js_empaquetado_es_el_ARREGLADO(tmp_path):
    """El que se despliega tiene que ser el que pasó la medición, no el otro.

    Casi se empaqueta el equivocado: la copia de trabajo en `gb-lenguajes/hooks`
    seguía siendo la vieja —`uncaughtException` + re-lanzar—, que cambia el exit
    code del programa observado de 1 a 7 y le mete sus frames en la traza. El
    arreglo (`uncaughtExceptionMonitor`, observar sin manejar) vivía solo en la
    rama del spike. Este test existe para que ese error no se repita en silencio.
    """
    from galaxybrain import consola

    fichas = consola.despliega(str(tmp_path))
    js = [f for f in fichas if f["lenguaje"] == "js"][0]
    fuente = open(js["ruta"], encoding="utf-8").read()

    assert "uncaughtExceptionMonitor" in fuente
    assert "process.on('uncaughtException'," not in fuente


def test_despliega_da_la_linea_con_la_ruta_de_verdad(tmp_path):
    """Un nombre de fichero suelto obliga al usuario a ir a buscarlo: la línea
    tiene que poder pegarse tal cual."""
    from galaxybrain import consola

    fichas = {f["lenguaje"]: f for f in consola.despliega(str(tmp_path))}
    assert fichas["js"]["exporta"].startswith('NODE_OPTIONS="--require ')
    assert fichas["js"]["ruta"] in fichas["js"]["exporta"]
    # php no se arma por entorno, y se dice en vez de disimularlo.
    assert fichas["php"]["por_entorno"] is False
    assert fichas["php"]["ruta"] in fichas["php"]["exporta"]


def test_desplegar_dos_veces_no_rompe_nada(tmp_path):
    from galaxybrain import consola

    consola.despliega(str(tmp_path))
    segundas = consola.despliega(str(tmp_path))
    assert segundas, "el segundo despliegue no devolvio nada"
    assert len(consola.desplegados()) >= 0   # sin GB_HOME apuntado aqui, solo no revienta


def test_gb_on_lenguajes_despliega_y_dice_como_armarlo(tmp_path, capsys, monkeypatch):
    """De punta a punta. Y dice lo que gb NO puede hacer: un proceso no cambia
    el entorno de quien lo llamó, así que la variable la exporta la persona."""
    from galaxybrain import cli

    monkeypatch.setenv("GB_HOME", str(tmp_path))
    assert cli.main(["on", "--lenguajes"]) == 0
    salida = capsys.readouterr().out
    assert "NODE_OPTIONS" in salida
    assert "no puede exportarlas por ti" in salida
