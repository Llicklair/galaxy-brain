"""`gb calls`: quien llama a quien, con fichero:linea — la pieza que cubria una
herramienta externa (GitNexus) y ahora sale del grafo propio.

Lo que se prueba es el contrato del criterio de fase: llamantes y llamados con
su sitio, onda por niveles, ambiguedad devuelta como material (todas las
coincidencias, no un error) y un hook que calla cuando no tiene nada que decir.
"""

import io
import json
import textwrap

from galaxybrain import cli, symbols
from galaxybrain.graph import _BOM


def _proyecto(tmp_path):
    (tmp_path / "app.py").write_text(textwrap.dedent('''\
        from lib import ayuda

        def main():
            """Punto de entrada."""
            ayuda()
            interno()

        def interno():
            pass
        '''), encoding="utf-8")
    (tmp_path / "lib.py").write_text(textwrap.dedent('''\
        def ayuda():
            """Una mano."""
            base()

        def base():
            pass
        '''), encoding="utf-8")
    return str(tmp_path)


# --- fichero:linea en el indice ----------------------------------------------


def test_cada_simbolo_lleva_fichero_y_linea(tmp_path):
    report = symbols.analyze(_proyecto(tmp_path))

    nodos = {n["qual"]: n for n in report["nodes"]}
    assert nodos["app.main"]["file"] == "app.py"
    assert nodos["app.main"]["line"] == 3
    assert nodos["lib"]["file"] == "lib.py"
    assert nodos["lib"]["line"] == 1


# --- la consulta -------------------------------------------------------------


def test_llamantes_y_llamados_con_su_sitio(tmp_path):
    report = symbols.analyze(_proyecto(tmp_path))

    res = symbols.calls(report, "ayuda")
    assert [m["symbol"]["qual"] for m in res["matches"]] == ["lib.ayuda"]
    m = res["matches"][0]
    assert [(f["qual"], f["file"]) for f in m["callers"]] == [("app.main", "app.py")]
    assert [f["qual"] for f in m["callees"]] == ["lib.base"]


def test_la_onda_sigue_niveles(tmp_path):
    """depth=2: el que llama al que llama, marcado con su nivel — el radio de
    la onda de un cambio, no una lista plana que mezcla cercania."""
    report = symbols.analyze(_proyecto(tmp_path))

    res = symbols.calls(report, "base", depth=2)
    llamantes = res["matches"][0]["callers"]
    assert [(f["qual"], f["depth"]) for f in llamantes] == [
        ("lib.ayuda", 1), ("app.main", 2),
    ]


def test_nombre_ambiguo_devuelve_todas_las_coincidencias(tmp_path):
    """Ambiguo no es error: es material. Quien pregunta decide cual era."""
    root = _proyecto(tmp_path)
    (tmp_path / "otro.py").write_text("def ayuda():\n    pass\n", encoding="utf-8")

    report = symbols.analyze(root)
    res = symbols.calls(report, "ayuda")
    assert [m["symbol"]["qual"] for m in res["matches"]] == ["lib.ayuda", "otro.ayuda"]


def test_desconocido_es_lista_vacia_no_error(tmp_path):
    report = symbols.analyze(_proyecto(tmp_path))

    assert symbols.calls(report, "no_existe")["matches"] == []


# --- la firma: como se llama, sin abrir el fichero ---------------------------


def test_la_firma_dice_como_se_llama(tmp_path):
    """El hecho que mas ficheros obligaba a abrir: args con defaults, `*`,
    async y los decoradores que cambian la llamada. Todo del AST."""
    (tmp_path / "m.py").write_text(textwrap.dedent('''\
        async def baja(url, timeout=5, *, reintentos=2, **extra):
            pass

        class Cosa(dict):
            @property
            def valor(self):
                return 1
        '''), encoding="utf-8")

    report = symbols.analyze(str(tmp_path))
    nodos = {n["qual"]: n for n in report["nodes"]}
    assert nodos["m.baja"]["sig"] == "async (url, timeout=5, *, reintentos=2, **extra)"
    assert nodos["m.Cosa"]["sig"] == "(dict)"
    assert nodos["m.Cosa.valor"]["sig"] == "@property (self)"


def test_la_firma_viaja_en_la_ficha_del_hook(tmp_path, monkeypatch, capsys):
    _proyecto(tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(
        {"tool_input": {"pattern": "ayuda"}, "cwd": str(tmp_path)}
    )))

    assert cli.main(["calls", "--hook"]) == 0
    assert "lib.ayuda()" in capsys.readouterr().out


def test_las_cuentas_separan_src_de_tests(tmp_path):
    """Los tests son la red, no la onda: 56 llamantes y "5 de src + 51 de
    tests" cuentan historias distintas a quien va a tocar el simbolo."""
    root = _proyecto(tmp_path)
    (tmp_path / "test_cosa.py").write_text(
        "from lib import ayuda\n\ndef test_a():\n    ayuda()\n", encoding="utf-8"
    )

    report = symbols.analyze(root)
    fichas = symbols.relacionados(report, "ayuda")
    assert fichas[0]["callers"] == 2
    assert fichas[0]["callers_tests"] == 1
    assert symbols.es_de_test("test_cosa.test_a")
    assert symbols.es_de_test("tests.test_x.helper")
    assert not symbols.es_de_test("galaxybrain.store.save")


# --- relacionados: lo que alimenta el hook -----------------------------------


def test_relacionados_casa_el_nombre_dentro_de_un_patron(tmp_path):
    """El texto es un patron de Grep, no Python: se tokeniza y se casa por nombre."""
    report = symbols.analyze(_proyecto(tmp_path))

    fichas = symbols.relacionados(report, r"def ayuda\(")
    assert [f["qual"] for f in fichas] == ["lib.ayuda"]
    assert fichas[0]["callers"] == 1
    assert fichas[0]["callees"] == 1
    assert fichas[0]["file"] == "lib.py"


def test_relacionados_calla_sin_coincidencias(tmp_path):
    report = symbols.analyze(_proyecto(tmp_path))

    assert symbols.relacionados(report, "zzz_nada_de_esto") == []


# --- el hook entero, por el CLI ----------------------------------------------


def test_el_hook_calla_cuando_no_hay_nada(tmp_path, monkeypatch, capsys):
    _proyecto(tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(
        {"tool_input": {"pattern": "zzz_nada"}, "cwd": str(tmp_path)}
    )))

    assert cli.main(["calls", "--hook"]) == 0
    assert capsys.readouterr().out == ""


def test_el_hook_devuelve_ficha_con_sitio_y_cuentas(tmp_path, monkeypatch, capsys):
    _proyecto(tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(
        {"tool_input": {"pattern": "ayuda"}, "cwd": str(tmp_path)}
    )))

    assert cli.main(["calls", "--hook"]) == 0
    salida = capsys.readouterr().out
    assert "lib.ayuda" in salida
    assert "lib.py:1" in salida
    assert "1 le llaman" in salida


def test_el_hook_no_revienta_con_stdin_roto(monkeypatch, capsys):
    """Contrato: el hook nunca puede romper la busqueda que lo dispara."""
    monkeypatch.setattr("sys.stdin", io.StringIO("esto no es json"))

    assert cli.main(["calls", "--hook"]) == 0
    assert capsys.readouterr().out == ""


def test_en_linea_da_el_simbolo_que_contiene_la_linea(tmp_path):
    """Contencion por [line, end] del AST, no "el def mas cercano por arriba":
    la linea 1 de app.py es un import y NO pertenece a ningun simbolo."""
    report = symbols.analyze(_proyecto(tmp_path))

    assert symbols.en_linea(report, "lib.py", 3)["qual"] == "lib.ayuda"
    assert symbols.en_linea(report, "app.py", 1) is None


def test_en_linea_prefiere_el_metodo_a_la_clase(tmp_path):
    (tmp_path / "cosa.py").write_text(
        "class Cosa:\n    def metodo(self):\n        return 1\n", encoding="utf-8"
    )

    report = symbols.analyze(str(tmp_path))
    assert symbols.en_linea(report, "cosa.py", 3)["qual"] == "cosa.Cosa.metodo"


# --- el ancla del crash: la consola dice el nodo -----------------------------


def _record(root, fichero, linea):
    return {
        "process": {"project": root},
        "frames": [
            {"file": "/usr/lib/python/x.py", "line": 1, "is_library": True},
            {"file": fichero, "line": linea, "is_library": False},
        ],
    }


def _repo_git(root):
    import subprocess

    for orden in (
        ("init", "-q"),
        ("config", "user.email", "t@t"),
        ("config", "user.name", "t"),
        ("config", "commit.gpgsign", "false"),
        ("add", "-A"),
        ("commit", "-q", "-m", "v1"),
    ):
        subprocess.run(("git",) + orden, cwd=root, check=True, capture_output=True)


def test_el_ancla_apunta_al_nodo_y_sus_llamantes(tmp_path):
    """Criterio 1 de la fase "grafo como columna": el crash con su nodo y su onda."""
    root = _proyecto(tmp_path)

    ancla = cli._ancla_grafo(_record(root, str(tmp_path / "lib.py"), 3))
    assert ancla["nodo"]["qual"] == "lib.ayuda"
    assert ancla["llamantes"] == ["app.main"]
    assert ancla["cambiado"] is None  # sin repo git no consta cambio: sin aviso


def test_el_ancla_avisa_si_el_fichero_cambio_despues_de_la_captura(tmp_path):
    """El ancla resuelve contra el codigo de HOY: si el fichero tiene commits
    posteriores a la captura, apuntar sin avisarlo seria mentir por omision."""
    root = _proyecto(tmp_path)
    _repo_git(root)

    registro = _record(root, str(tmp_path / "lib.py"), 3)
    registro["ts"] = "2020-01-01T00:00:00+00:00"  # muy anterior al commit
    ancla = cli._ancla_grafo(registro)
    assert ancla["nodo"]["qual"] == "lib.ayuda"
    assert ancla["cambiado"]


def test_linea_sin_simbolo_con_fichero_cambiado_no_calla(tmp_path):
    """El caso de la primera prueba de uso real (NameError de hace 3 dias): la
    linea ya no cae en ningun simbolo Y el fichero cambio despues. Callar ahi
    esconde el porque; se dice el hecho y de quien es la limitacion."""
    root = _proyecto(tmp_path)
    _repo_git(root)

    registro = _record(root, str(tmp_path / "app.py"), 1)  # el import: sin simbolo
    registro["ts"] = "2020-01-01T00:00:00+00:00"
    ancla = cli._ancla_grafo(registro)
    assert ancla["nodo"] is None
    assert ancla["cambiado"]


def test_el_ancla_calla_si_no_puede_decir_nada(tmp_path):
    """Regla 9: el ancla es un extra sobre la ficha del crash, nunca un fallo."""
    root = _proyecto(tmp_path)

    assert cli._ancla_grafo(_record(root, "<string>", 1)) is None
    assert cli._ancla_grafo({"process": {}, "frames": []}) is None
    assert cli._ancla_grafo(_record(root, str(tmp_path / "app.py"), 1)) is None


def test_el_hook_tolera_el_bom_de_powershell(tmp_path, monkeypatch, capsys):
    """PowerShell 5.1 pipa con BOM y `json.loads` lo rechaza. El hook callaba
    "cumpliendo el contrato" — un silencio con causa evitable que se midio como
    velocidad (180 ms que eran mudez). El BOM se quita, no se obedece."""
    _proyecto(tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO(_BOM + json.dumps(
        {"tool_input": {"pattern": "ayuda"}, "cwd": str(tmp_path)}
    )))

    assert cli.main(["calls", "--hook"]) == 0
    assert "lib.ayuda" in capsys.readouterr().out
