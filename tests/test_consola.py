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


def test_los_compilables_traen_su_fuente():
    """gb trae la FUENTE, no el binario: un .jar o una .dll en el repo no se
    auditan, no valen para otra plataforma y envejecen mal."""
    from galaxybrain import consola

    base = os.path.join(os.path.dirname(consola.__file__), "hooks_lang")
    for lang in consola.COMPILABLES:
        carpeta = os.path.join(base, consola.compilable(lang)["dir"])
        assert os.path.isdir(carpeta), "%s no trae fuente" % lang


def test_sin_la_herramienta_se_dice_CUAL_falta(tmp_path, monkeypatch):
    """«No disponible» a secas no aclara si el problema es tuyo, de gb o de la
    máquina. «Falta javac» sí, y se arregla en un minuto."""
    from galaxybrain import consola

    monkeypatch.setattr("shutil.which", lambda *_a, **_k: None)
    r = consola.compila("java", str(tmp_path))

    assert r["ok"] is False
    assert r["falta"] == ["javac", "jar"]
    assert not r["error"], "no deberia haber intentado nada"


def test_java_kotlin_y_scala_comparten_el_mismo_agente():
    """Corren sobre la misma máquina virtual, así que se construye una vez. Se
    nombran los tres porque el usuario busca SU lenguaje en la lista."""
    from galaxybrain import consola

    salidas = {lang: consola.compilable(lang)["salida"]
               for lang in ("java", "kotlin", "scala")}
    assert set(salidas.values()) == {"gb-agent.jar"}


def test_c_se_construye_distinto_en_cada_plataforma():
    """No es el mismo hook con otra ruta: en Windows es otro mecanismo, otra
    fuente y otra forma de invocarlo."""
    from galaxybrain import consola

    assert consola.compilable("c", "win32")["salida"] == "gb-run.exe"
    assert consola.compilable("c", "linux")["salida"] == "gb-hook.so"
    assert "LD_PRELOAD" in consola.compilable("c", "linux")["exporta"]


def test_construye_todo_no_lanza_aunque_no_haya_nada(tmp_path, monkeypatch):
    """Un instalador que revienta a mitad deja al usuario peor que si no lo
    hubiera ejecutado: sin hooks y sin saber cuáles sí podía tener."""
    from galaxybrain import consola

    monkeypatch.setattr("shutil.which", lambda *_a, **_k: None)
    fichas = consola.construye_todo(str(tmp_path))

    assert {f["lenguaje"] for f in fichas} == set(consola.COMPILABLES)
    assert all(f["falta"] for f in fichas)


def test_go_y_rust_se_despliegan_con_su_envolvente(tmp_path):
    """No tienen gancho instalable, pero eso no es motivo para dejarlos fuera:
    se cubren envolviendo la invocación, y el envolvente es Python puro — no
    hay nada que compilar. Su techo ya está escrito en MECANISMOS."""
    from galaxybrain import consola

    fichas = {f["lenguaje"]: f for f in consola.despliega(str(tmp_path))}
    for lang in ("go", "rust"):
        assert lang in fichas, "%s no se despliega" % lang
        assert fichas[lang]["ruta"].endswith("gb-run.py")
        assert fichas[lang]["ruta"] in fichas[lang]["exporta"]


def test_swift_se_empaqueta_pero_sigue_declarandose_sin_medir():
    """Que compile no es que funcione. Ponerlo en `hook-nativo` porque gb ya
    trae su fuente seria dar por verificado lo que solo está construido, y esa
    es justo la diferencia que este campo existe para marcar."""
    from galaxybrain import consola

    assert "swift" in consola.COMPILABLES
    assert consola.MECANISMOS["swift"]["via"] == "desactivado"
    assert "sin medir" in consola.MECANISMOS["swift"]["techo"]


def test_dart_y_elixir_quedan_fuera_diciendo_por_que():
    """Los dos exigen tocar el código de quien los instala —dart reescribir tu
    main(), elixir editar tu config.exs y tu lib/—, que es el mismo criterio que
    ya tumbó el `set_hook` de rust. Tocar tu código no es instalar."""
    from galaxybrain import consola

    for lang in ("dart", "elixir"):
        assert lang not in consola.HOOKS_EMPAQUETADOS
        assert lang not in consola.COMPILABLES
        assert lang not in consola.HOOKS_ENVOLVENTE
        assert consola.MECANISMOS[lang]["techo"], "%s no dice por que" % lang


def _envolvente():
    """El `gb-run.py` que gb despliega, cargado como modulo (lleva guion)."""
    import importlib.util

    from galaxybrain import consola

    ruta = os.path.join(os.path.dirname(consola.__file__), "hooks_lang", "gb-run.py")
    spec = importlib.util.spec_from_file_location("gb_run_empaquetado", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_el_envolvente_normaliza_los_saltos_de_windows():
    """El fallo que dejaba a rust sin capturar en Windows: el stderr llega con
    CRLF y los patrones de panic piden LF, así que no casaba NUNCA. El
    envolvente decía «stderr capture active» y no escribía un solo registro —
    peor que no capturar, porque el usuario cree que sí."""
    gb_run = _envolvente()
    assert gb_run._normaliza_saltos("a\r\nb") == "a\nb"


def test_el_envolvente_captura_aunque_lances_el_binario_ya_compilado():
    """Miraba solo el nombre del comando: `cargo run` capturaba y `./mi_binario`
    no. Lanzar el binario ya compilado es lo normal, no la excepción."""
    gb_run = _envolvente()
    assert gb_run.needs_stderr_capture("cargo") is True
    assert gb_run.needs_stderr_capture("./petar.exe", ["rust"]) is True
    assert gb_run.needs_stderr_capture("./petar.exe", ["python"]) is False


def test_el_tipo_sale_del_MENSAJE_y_lo_que_no_se_sabe_sigue_siendo_panic():
    """Escribir la constante «panic» disparó el criterio de aborto de la ADR
    0012 — y lo disparó mal: el dato sí estaba en stderr, era el parser el que
    no lo miraba. Lo que no se puede derivar se queda en «panic», declarado y no
    inventado: un tipo a ojo manda a buscar el fallo que no es."""
    gb_run = _envolvente()
    assert gb_run.tipo_de_mensaje("index out of bounds: the len is 2") == "index out of bounds"
    assert "nil pointer" in gb_run.tipo_de_mensaje("runtime error: nil pointer dereference")
    assert gb_run.tipo_de_mensaje("codigo 42") == "panic"
