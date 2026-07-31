"""El test que decide si el proyecto existe.

Criterio de terminado (SCOPE.md): ante un fallo real, te dice donde y
con que estado, sin que lo reproduzcas a mano. Estos tests provocan fallos
reales en procesos Python de verdad y comprueban que el estado quedo guardado.

Todo corre en subprocesos a proposito: un hook de excepciones instalado dentro
del propio pytest no demuestra nada sobre un programa real.
"""

import json
import subprocess
import sys
import textwrap

from galaxybrain import store

PRELUDIO = "import galaxybrain; galaxybrain.install()\n"


def run_child(code, env, extra_args=()):
    script = PRELUDIO + textwrap.dedent(code)
    return subprocess.run(
        [sys.executable, "-c", script, *extra_args],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def run_script(tmp_path, code, env, name="programa.py"):
    """Como run_child, pero con un fichero de verdad en disco.

    No es un detalle de fontaneria: el codigo de `python -c` no tiene fuente
    recuperable, asi que solo un fichero real ejercita la captura de contexto.
    """
    path = tmp_path / name
    path.write_text(PRELUDIO + textwrap.dedent(code), encoding="utf-8")
    return path, subprocess.run(
        [sys.executable, str(path)],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_captura_el_estado_de_un_fallo_real(gb_home, child_env):
    result = run_child(
        """
        def cargar(filas):
            total = 0
            for fila in filas:
                total += fila["cantidad"]
            return total

        cargar([{"cantidad": 3}, {"importe": 7}])
        """,
        child_env,
    )

    assert result.returncode != 0

    records = store.read_index()
    assert len(records) == 1, "un fallo real tiene que dejar exactamente un registro"

    record = store.load()
    assert record["exception"]["type"] == "KeyError"

    frame = [f for f in record["frames"] if not f["is_library"]][-1]
    assert frame["function"] == "cargar"
    # Lo que distingue esto de un traceback: el ESTADO.
    assert frame["locals"]["fila"] == "{'importe': 7}"
    assert frame["locals"]["total"] == "3"


def test_el_programa_observado_se_comporta_igual(gb_home, child_env):
    """Regla 9: si la captura estorba, la herramienta muere. El traceback
    original tiene que seguir saliendo, entero, y el codigo de salida igual."""
    result = run_child("raise ValueError('roto')\n", child_env)

    assert result.returncode == 1
    assert "Traceback (most recent call last):" in result.stderr
    assert "ValueError: roto" in result.stderr


def test_deja_una_sola_linea_de_aviso(gb_home, child_env):
    result = run_child("raise ValueError('roto')\n", child_env)
    avisos = [line for line in result.stderr.splitlines() if "galaxy-brain" in line]
    assert len(avisos) == 1


def test_el_aviso_lleva_el_comando_exacto_con_el_id(gb_home, child_env):
    """El aviso es la unica pista que ve quien acaba de lanzar el programa — y
    con captura de stdout de por medio, a veces la unica que vera nunca. Por eso
    lleva el comando ENTERO, con el id dentro: copiar y pegar, sin ventana de
    tiempo ni riesgo de leer el fallo de antes."""
    result = run_child("raise ValueError('roto')\n", child_env)
    aviso = next(line for line in result.stderr.splitlines() if "galaxy-brain" in line)

    assert "gb show " in aviso
    record_id = aviso.split("gb show ")[1].strip()
    assert record_id and record_id != "?"

    from galaxybrain import store

    assert store.load(record_id) is not None, "el id del aviso tiene que cargar de verdad"


def test_gb_quiet_calla_el_aviso_pero_sigue_capturando(gb_home, child_env):
    child_env["GB_QUIET"] = "1"
    result = run_child("raise ValueError('roto')\n", child_env)

    assert "galaxy-brain" not in result.stderr
    assert len(store.read_index()) == 1


def test_gb_disable_no_captura_nada(gb_home, child_env):
    child_env["GB_DISABLE"] = "1"
    result = run_child("raise ValueError('roto')\n", child_env)

    assert "ValueError: roto" in result.stderr
    assert store.read_index() == []


def test_salir_con_sys_exit_no_es_un_fallo(gb_home, child_env):
    run_child("import sys; sys.exit(2)\n", child_env)
    assert store.read_index() == [], "sys.exit es una forma normal de terminar"


def test_captura_excepciones_de_hilos(gb_home, child_env):
    run_child(
        """
        import threading

        def trabajo():
            pieza = "engranaje"
            raise RuntimeError("el hilo peto")

        hilo = threading.Thread(target=trabajo, name="obrero")
        hilo.start()
        hilo.join()
        """,
        child_env,
    )

    record = store.load()
    assert record is not None
    assert record["exception"]["type"] == "RuntimeError"
    assert record["thread"] == "obrero"
    frame = [f for f in record["frames"] if not f["is_library"]][-1]
    assert frame["locals"]["pieza"] == "'engranaje'"


def test_captura_lo_que_python_no_pudo_propagar(gb_home, child_env):
    """La tercera puerta: un `__del__` que revienta.

    El interprete la imprime y sigue — el proceso NO muere, asi que
    `sys.excepthook` no la ve jamas y hasta ahora desaparecia sin dejar rastro.
    Es el mismo hecho (una excepcion que nadie capturo) por otra salida.
    """
    result = run_child(
        """
        class Recurso:
            def __init__(self):
                self.nombre = "conexion"
            def __del__(self):
                raise ValueError("el finalizador peto")

        r = Recurso()
        del r
        print("el programa sigue")
        """,
        child_env,
    )

    # (2) del criterio: el programa observado no cambia de comportamiento.
    assert "el programa sigue" in result.stdout
    assert "el finalizador peto" in result.stderr  # la traza de Python, intacta

    record = store.load()
    assert record is not None
    assert record["exception"]["type"] == "ValueError"
    assert record["source"] == "unraisable"
    frame = [f for f in record["frames"] if not f["is_library"]][-1]
    assert frame["function"] == "__del__"


def test_un_finalizador_en_bucle_no_inunda_el_historico(gb_home, child_env):
    """(5) del criterio. Un `__del__` roto suele estarlo para TODAS las instancias
    de su clase, asi que sin tope un bucle de mil objetos escribiria mil registros:
    enterraria el historico y frenaria el programa observado (regla 4)."""
    result = run_child(
        """
        class Roto:
            def __del__(self):
                raise ValueError("otra vez")

        for _ in range(40):
            Roto()
        print("acabado")
        """,
        child_env,
    )

    assert "acabado" in result.stdout
    guardados = store.read_index()
    assert 0 < len(guardados) <= 10, "el tope no se respeto: %d" % len(guardados)
    # Y se DICE que se ha dejado de guardar: un tope callado se lee como "no paso mas".
    assert "dejo de guardarlos" in result.stderr


def test_sys_exit_dentro_de_un_finalizador_sigue_sin_ser_un_fallo(gb_home, child_env):
    """(3) del criterio: las salidas normales se ignoran por las tres puertas."""
    run_child(
        """
        class Salida:
            def __del__(self):
                raise SystemExit(0)

        s = Salida()
        del s
        """,
        child_env,
    )
    assert store.read_index() == []


def test_gb_no_threads_no_apaga_la_tercera_puerta(gb_home, child_env):
    """`GB_NO_THREADS` existe para no pagar `import threading`. El hook de
    finalizadores no importa nada, asi que apagar los hilos no puede costarte
    ademas los fallos que Python no pudo propagar."""
    child_env["GB_NO_THREADS"] = "1"
    run_child(
        """
        class Roto:
            def __del__(self):
                raise RuntimeError("sin hilos, pero capturado")

        r = Roto()
        del r
        """,
        child_env,
    )

    record = store.load()
    assert record is not None
    assert record["exception"]["type"] == "RuntimeError"


def test_el_frame_de_modulo_no_vomita_dunders(gb_home, child_env, tmp_path):
    """Un frame de modulo trae __builtins__, __loader__, __spec__ y compania.
    Ocho lineas de ruido que sepultan las dos variables que importan."""
    _, _ = run_script(
        tmp_path,
        """
        clientes = ["ana", "beto"]
        raise ValueError('roto')
        """,
        child_env,
    )

    locales = [f for f in store.load()["frames"] if not f["is_library"]][-1]["locals"]

    assert locales["clientes"] == "['ana', 'beto']"
    assert not [name for name in locales if name.startswith("__")]
    # `galaxybrain` aparece porque lo importa el preludio de estos tests; en uso
    # real (via .pth) el programa no importa nada nuestro — lo cubre
    # test_autoinstall.py::test_captura_sin_que_el_programa_sepa_que_existimos.
    assert set(locales) <= {"clientes", "galaxybrain"}


def test_gb_no_threads_ahorra_el_import_pero_conserva_lo_principal(gb_home, child_env):
    """El interruptor de latencia: quien no usa hilos no paga los 5 ms de
    `import threading`, y las excepciones del hilo principal siguen guardandose."""
    child_env["GB_NO_THREADS"] = "1"
    result = run_child(
        """
        import sys
        raise ValueError('roto')
        """,
        child_env,
    )

    assert store.load()["exception"]["type"] == "ValueError"
    assert "threading" not in result.stderr


def test_guarda_la_cadena_de_excepciones(gb_home, child_env):
    run_child(
        """
        try:
            int("no soy un numero")
        except ValueError as error:
            raise RuntimeError("no pude configurar el cliente") from error
        """,
        child_env,
    )

    chain = store.load()["exception"]["chain"]
    assert chain[0]["kind"] == "cause"
    assert chain[0]["type"] == "ValueError"


def test_no_guarda_secretos_de_argv(gb_home, child_env):
    """S3: `sys.argv` entero se guardaba crudo — `mytool --password X` a disco.
    Ahora solo el programa y la cuenta, no los valores de los flags."""
    result = run_child("raise ValueError('roto')\n", child_env,
                       extra_args=["--password", "hunter2-cli", "--token=ghp_secreto"])
    assert result.returncode != 0

    crudo = (gb_home / store.INDEX_NAME).read_text(encoding="utf-8")
    for path in (gb_home / "errors").rglob("*.json"):
        crudo += path.read_text(encoding="utf-8")

    assert "hunter2-cli" not in crudo
    assert "ghp_secreto" not in crudo

    record = store.load()
    proc = record["process"]
    assert proc["argv"] is None          # por defecto no se guarda la lista
    assert proc["argv_count"] >= 3       # pero sí cuántos había (el aviso de que hubo flags)
    assert proc["program"] is not None


def test_gb_keep_argv_restaura_la_lista_completa(gb_home, child_env):
    child_env["GB_KEEP_ARGV"] = "1"
    run_child("raise ValueError('roto')\n", child_env, extra_args=["sub", "--verbose"])
    argv = store.load()["process"]["argv"]
    assert argv is not None
    assert "--verbose" in argv


def test_gb_max_frames_cero_no_miente_ni_conserva_todo(gb_home, child_env, tmp_path):
    """B3: con GB_MAX_FRAMES=0 el recorte conservaba TODO y el contador mentía.
    Con el floor a 1 conserva el frame más interno y el contador es coherente."""
    child_env["GB_MAX_FRAMES"] = "0"
    path, _ = run_script(
        tmp_path,
        """
        def c():
            raise ValueError('x')
        def b():
            c()
        def a():
            b()
        a()
        """,
        child_env,
    )
    record = store.load()
    assert len(record["frames"]) == 1        # el más interno, no "todos"
    assert record["frames_trimmed"] >= 1     # y de verdad recortó


def test_no_escribe_secretos_en_disco(gb_home, child_env):
    run_child(
        """
        def conectar(usuario, password, api_key):
            raise ConnectionError("sin ruta al host")

        conectar("ana", "hunter2", "sk-vive-para-siempre")
        """,
        child_env,
    )

    crudo = (gb_home / store.INDEX_NAME).read_text(encoding="utf-8")
    for path in (gb_home / "errors").rglob("*.json"):
        crudo += path.read_text(encoding="utf-8")

    assert "hunter2" not in crudo
    assert "sk-vive-para-siempre" not in crudo
    assert "ana" in crudo  # lo que no es secreto si se guarda


def _dump_home(gb_home):
    crudo = (gb_home / store.INDEX_NAME).read_text(encoding="utf-8")
    for path in (gb_home / "errors").rglob("*.json"):
        crudo += path.read_text(encoding="utf-8")
    return crudo


def test_no_guarda_secretos_en_lineas_fuente(gb_home, child_env, tmp_path):
    """S1: una asignación sensible en el código fuente cerca del fallo se redacta."""
    run_script(
        tmp_path,
        """
        def cobrar():
            api_key = "AKIA-en-fuente"
            raise RuntimeError("boom")

        cobrar()
        """,
        child_env,
    )
    assert "AKIA-en-fuente" not in _dump_home(gb_home)


def test_no_guarda_secretos_en_el_mensaje(gb_home, child_env):
    """S2: un secreto con forma clave=valor en el mensaje de la excepción se redacta."""
    run_child("raise RuntimeError('auth failed: token=ghp_enmensaje')\n", child_env)
    assert "ghp_enmensaje" not in _dump_home(gb_home)


def test_un_repr_roto_no_tumba_la_captura(gb_home, child_env):
    run_child(
        """
        class Bomba:
            def __repr__(self):
                raise SystemError("explota al mirarme")

        def usar():
            bomba = Bomba()
            vecino = "sigo aqui"
            raise ValueError("el fallo de verdad")

        usar()
        """,
        child_env,
    )

    frame = [f for f in store.load()["frames"] if not f["is_library"]][-1]
    assert "repr() fallo" in frame["locals"]["bomba"]
    assert frame["locals"]["vecino"] == "'sigo aqui'"


def test_incluye_el_codigo_fuente_alrededor_del_fallo(gb_home, child_env, tmp_path):
    """Sin las lineas de codigo, el numero de linea obliga a abrir el fichero,
    que es el paso manual que esto viene a quitar."""
    path, _ = run_script(
        tmp_path,
        """
        def calcular(a, b):
            resultado = a / b
            return resultado

        calcular(1, 0)
        """,
        child_env,
    )

    frame = [f for f in store.load()["frames"] if not f["is_library"]][-1]
    assert frame["file"] == str(path)

    fallo = [line for line in frame["source"] if line["is_fail"]]
    assert len(fallo) == 1
    assert "a / b" in fallo[0]["text"]

    # Y el contexto de alrededor, que es lo que evita abrir el fichero.
    assert any("def calcular" in line["text"] for line in frame["source"])


def test_sin_fuente_recuperable_degrada_en_vez_de_romperse(gb_home, child_env):
    """`python -c`, `exec()` y el REPL no tienen fichero que leer. Ese caso
    existe y la captura tiene que seguir dando lo demas: tipo, mensaje, frames
    y ESTADO. Perder el contexto de fuente no puede costar el registro entero."""
    run_child(
        """
        def calcular(a, b):
            return a / b

        calcular(1, 0)
        """,
        child_env,
    )

    record = store.load()
    frame = [f for f in record["frames"] if not f["is_library"]][-1]
    assert frame["source"] == []
    assert frame["locals"] == {"a": "1", "b": "0"}
    assert record["exception"]["type"] == "ZeroDivisionError"


def test_el_cli_lee_lo_que_el_hook_escribio(gb_home, child_env):
    run_child("raise KeyError('usuario')\n", child_env)

    result = subprocess.run(
        [sys.executable, "-m", "galaxybrain.cli", "last", "--all", "--json"],
        env=child_env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout)["exception"]["type"] == "KeyError"


def test_varios_fallos_se_acumulan_en_el_historico(gb_home, child_env):
    for mensaje in ("uno", "dos", "tres"):
        run_child("raise ValueError(%r)\n" % mensaje, child_env)

    entradas = store.read_index()
    assert [e["message"] for e in entradas] == ["tres", "dos", "uno"]


def test_gb_list_agrupa_por_firma_con_cuenta(gb_home, child_env, tmp_path):
    """La libreta automática: el mismo fallo tres veces es UNA firma con un 3,
    y lo más frecuente sale primero."""
    path, _ = run_script(tmp_path, "d = {}\nd['falta']\n", child_env)  # KeyError, mismo sitio
    for _ in range(2):
        subprocess.run([sys.executable, str(path)], env=child_env,
                       capture_output=True, text=True, timeout=60)
    run_script(tmp_path, "int('no soy numero')\n", child_env, name="otro.py")  # ValueError, otro sitio

    result = subprocess.run(
        [sys.executable, "-m", "galaxybrain.cli", "list", "--all", "--json"],
        env=child_env, capture_output=True, text=True, timeout=60,
    )
    groups = json.loads(result.stdout)

    by_type = {g["type"]: g["count"] for g in groups}
    assert by_type["KeyError"] == 3
    assert by_type["ValueError"] == 1
    assert groups[0]["type"] == "KeyError"  # el más frecuente arriba


def test_cli_status_no_revienta_en_consola_cp1252(gb_home, monkeypatch, tmp_path):
    """B2: gb status escribe rutas (GB_HOME, ejecutable) con print() crudo; en una
    consola cp1252 un carácter fuera de ese codepage reventaba el comando."""
    import io
    import sys as _sys

    from galaxybrain import cli

    monkeypatch.setenv("GB_HOME", str(tmp_path / "日本"))  # fuera de cp1252
    buf = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", newline="")
    monkeypatch.setattr(_sys, "stdout", buf)

    rc = cli.main(["status"])
    buf.flush()
    assert rc == 0  # sin UnicodeEncodeError


def test_cli_show_id_no_encodable_no_revienta(gb_home, monkeypatch):
    """B2: el id lo controla el usuario; `gb show <no-cp1252>` no debe reventar."""
    import io
    import sys as _sys

    from galaxybrain import cli

    buf = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", newline="")
    monkeypatch.setattr(_sys, "stdout", buf)

    rc = cli.main(["show", "日本", "--all"])
    buf.flush()
    assert rc == 1  # id no encontrado, pero sin crash


def test_gb_list_chrono_devuelve_el_timeline_crudo(gb_home, child_env):
    for mensaje in ("uno", "dos"):
        run_child("raise ValueError(%r)\n" % mensaje, child_env)

    result = subprocess.run(
        [sys.executable, "-m", "galaxybrain.cli", "list", "--all", "--chrono", "--json"],
        env=child_env, capture_output=True, text=True, timeout=60,
    )
    entries = json.loads(result.stdout)
    # timeline = una fila por fallo, sin agrupar, más reciente primero
    assert [e["message"] for e in entries] == ["dos", "uno"]
