"""Repos MIXTOS: los dos motores conviven en un solo grafo (ADR 0009, enmienda).

Hasta el 15-ago-2026 Python no convivia con nadie: EXCLUIA. El motor
multilenguaje entraba solo donde no habia ni un `.py`, asi que un repo con
backend Python y frontend TypeScript veia media casa — y no lo decia. Medido
sobre este mismo banco antes del cambio: `gb graph` cantaba "2 modulos, 1 arista,
0 ciclos. Sin ciclos de imports." con los dos ficheros TS fuera y cero avisos.

Eso no es una limitacion, es un falso verde: el lector no tiene forma de saber
que la mitad de su repo no se ha mirado. Por eso el criterio de estos tests no
es "ve mas nodos" sino "ve los dos lados Y declara lo que sigue sin ver".
"""

import os

import pytest

from galaxybrain import cli, lenguajes

necesita_astgrep = pytest.mark.skipif(
    not lenguajes.binario(),
    reason="ast-grep no instalado; la capa multilenguaje es opcional (ADR 0009)",
)


def _escribe(root, rel, contenido):
    ruta = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write(contenido)
    return ruta


def _mixto(root):
    """Backend Python + frontend TypeScript, cada uno con su import interno."""
    _escribe(root, "api/server.py", "from api.db import consulta\n\n"
                                    "def arranca():\n    return consulta('select 1')\n")
    _escribe(root, "api/db.py", "def consulta(sql):\n    return []\n")
    _escribe(root, "web/app.ts", "import { fetchUsers } from './cliente';\n\n"
                                 "export function render() {\n  return fetchUsers();\n}\n")
    _escribe(root, "web/cliente.ts", "export function fetchUsers() {\n"
                                     "  return fetch('/users');\n}\n")
    return str(root)


@necesita_astgrep
def test_un_repo_mixto_ensena_los_dos_lados(tmp_path):
    """El agujero exacto que esto cerro: 2 de 4 modulos, sin avisar."""
    informe = cli._analiza_simbolos(_mixto(tmp_path))
    modulos = sorted(n["qual"] for n in informe["nodes"] if n["kind"] == "module")
    assert modulos == ["api.db", "api.server", "web.app", "web.cliente"]


@necesita_astgrep
def test_no_se_inventa_ninguna_arista_entre_familias(tmp_path):
    """Un `fetch('/users')` NO se ata a una vista de Python: nadie puede
    derivarlo sin resolver el runtime, y declararlo seria el grafo declarado que
    ADR 0009 rechaza."""
    informe = cli._analiza_simbolos(_mixto(tmp_path))
    fichero = {n["qual"]: n["file"].replace("\\", "/") for n in informe["nodes"]}
    for origen, destino, _tipo in informe["edges"]:
        de_python = fichero.get(origen, "").endswith(".py")
        a_python = fichero.get(destino, "").endswith(".py")
        assert de_python == a_python, "arista cruzada inventada: %s -> %s" % (origen, destino)


@necesita_astgrep
def test_lo_que_sigue_sin_ver_queda_escrito(tmp_path):
    """La mitad que importa: callar el techo es como se fabrica el falso verde."""
    informe = cli._analiza_simbolos(_mixto(tmp_path))
    assert any("ENTRE familias" in linea for linea in informe["not_covered"])


@necesita_astgrep
def test_dos_modulos_con_el_mismo_nombre_no_se_pisan(tmp_path):
    """`module_name` es identico en los dos motores, asi que `web/app.py` y
    `web/app.ts` aterrizan en `web.app`. Python conserva el nombre; el otro
    lleva su extension pegada. Si uno comiera al otro, el grafo mentiria."""
    root = _mixto(tmp_path)
    _escribe(root, "web/app.py", "def render():\n    return 1\n")
    nodes, _edges, _errores = cli._constructor_fusionado(root)
    assert {"web.app", "web.app:ts"} <= set(nodes)


@necesita_astgrep
def test_un_ciclo_solo_de_typescript_bloquea_el_gate(tmp_path):
    """Antes, un ciclo de imports entre ficheros TS pasaba el pre-commit de un
    repo mixto porque nadie lo miraba. El gate va sobre hechos (regla 9) y un
    ciclo es un hecho en cualquier lenguaje."""
    root = _mixto(tmp_path)
    _escribe(root, "web/cliente.ts", "import { render } from './app';\n\n"
                                     "export function fetchUsers() {\n  return render();\n}\n")
    _nodes, edges, _errores = cli._constructor_fusionado(root)
    assert "web.app" in edges.get("web.cliente", set())
    assert "web.cliente" in edges.get("web.app", set())


@necesita_astgrep
def test_check_ve_el_ciclo_nuevo_de_typescript(tmp_path):
    """Auditoria del 24-sep-2026: `graph --gate --since` bloqueaba el ciclo y
    `check` decia "sin acoplamiento nuevo" sobre el MISMO commit — llamaba al
    grafo sin el extractor de los dos motores."""
    import subprocess

    from galaxybrain import changes

    root = _mixto(tmp_path)

    def git(*args):
        subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)

    git("init", "-q")
    git("-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
    git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base")
    _escribe(root, "web/cliente.ts", "import { render } from './app';\n\n"
                                     "export function fetchUsers() {\n  return render();\n}\n")
    git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qam", "ciclo")

    report = changes.analyze(root, "HEAD~1..HEAD",
                             constructor=cli._constructor_de_grafo(root))
    pares = report["coupling"]["new_pairs"]
    assert any({"web.app", "web.cliente"} <= set(p) for p in pares), pares


def test_sin_el_binario_el_informe_de_python_sigue_entero_y_lo_dice(tmp_path, monkeypatch):
    """`ast-grep` es opcional por diseno (SCOPE). Que falte no puede tumbar un
    informe de Python bueno — pero callarlo repetiria el fallo que esto mato."""
    root = _mixto(tmp_path)
    monkeypatch.setattr(
        lenguajes, "analyze",
        lambda *a, **k: {"root_error": "ast-grep no instalado", "nodes": [], "edges": [],
                         "errors": [], "unresolved": {}, "not_covered": []},
    )
    informe = cli._analiza_simbolos(root)
    modulos = sorted(n["qual"] for n in informe["nodes"] if n["kind"] == "module")
    assert modulos == ["api.db", "api.server"]
    assert any("ast-grep no instalado" in linea for linea in informe["not_covered"])


def test_un_repo_solo_de_python_no_paga_nada(tmp_path, monkeypatch):
    """El presupuesto de latencia es ley (regla 2). Quien no tenga otro lenguaje
    no puede pagar ni una invocacion del binario de mas."""
    _escribe(tmp_path, "api/db.py", "def consulta(sql):\n    return []\n")
    llamadas = []
    monkeypatch.setattr(lenguajes, "analyze", lambda *a, **k: llamadas.append(1))
    cli._analiza_simbolos(str(tmp_path))
    assert llamadas == []


def _swift_y_java(root):
    """Dos hooks, uno por lenguaje, con una funcion del MISMO nombre en cada uno:
    el caso real de `hooks_lang/` en este repo (libreta del 6-sep-2026)."""
    _escribe(root, "hooks_lang/swift/gb_hook.swift",
             "import Foundation\n\n"
             "private func detectProjectRoot() -> String {\n    return \"/\"\n}\n\n"
             "func armar() {\n    let raiz = detectProjectRoot()\n    print(raiz)\n}\n")
    _escribe(root, "hooks_lang/jvm/GbAgent.java",
             "public class GbAgent {\n"
             "    static String detectProjectRoot() {\n        return \"/\";\n    }\n\n"
             "    public static void premain(String args) {\n"
             "        String raiz = detectProjectRoot();\n        System.out.println(raiz);\n"
             "    }\n}\n")
    return str(root)


@necesita_astgrep
def test_una_llamada_suelta_no_cruza_de_lenguaje(tmp_path):
    """El gate del 6-sep cazo `swift.gb_hook -> jvm.GbAgent.detectProjectRoot`:
    Swift no llama a Java. La causa tenia dos mitades — `private func` era
    invisible para los patrones de swift, asi que la unica definicion del arbol
    era la de java, y la llamada suelta se resolvia por nombre sin mirar el
    lenguaje. Aqui se exige que las dos mitades sigan cerradas: cada llamada
    resuelve dentro de su lenguaje, y ninguna se pierde por el camino."""
    informe = lenguajes.analyze(_swift_y_java(tmp_path))
    llamadas = sorted((o, d) for o, d, tipo in informe["edges"] if tipo == "CALLS")
    assert llamadas == [
        ("hooks_lang.jvm.GbAgent.premain", "hooks_lang.jvm.GbAgent.detectProjectRoot"),
        ("hooks_lang.swift.gb_hook.armar", "hooks_lang.swift.gb_hook.detectProjectRoot"),
    ]
    assert "nombre-ambiguo" not in informe["unresolved"]


def _repo_git(root):
    import subprocess

    def git(*args):
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
                       cwd=root, check=True, capture_output=True)
    git("init", "-q")
    return git


@necesita_astgrep
def test_un_ciclo_ts_que_ya_estaba_no_bloquea_el_commit(tmp_path):
    """Auditoria del 24-sep-2026: la base de `--since` solo leia blobs .py, asi
    que en un repo TS con un ciclo YA commiteado cualquier commit salia con
    "NUEVO acoplamiento ciclico" y el pre-commit bloqueaba siempre. Los dos
    caminos: cambia un .ts (se re-analiza la ref con el mismo motor) y cambia
    solo un .py (base barata: lo no Python es el de hoy)."""
    root = _mixto(tmp_path)
    _escribe(root, "web/cliente.ts", "import { render } from './app';\n\n"
                                     "export function fetchUsers() {\n  return render();\n}\n")
    git = _repo_git(root)
    git("add", "-A")
    git("commit", "-qm", "base con ciclo ts")

    _escribe(root, "web/otro.ts", "export const x = 1;\n")
    git("add", "-A")
    git("commit", "-qm", "toca un ts")
    assert cli.main(["graph", root, "--gate", "--since", "HEAD~1"]) == 0

    _escribe(root, "api/db.py", "def consulta(sql):\n    return [sql]\n")
    git("commit", "-qam", "toca solo python")
    assert cli.main(["graph", root, "--gate", "--since", "HEAD~1"]) == 0


@necesita_astgrep
def test_un_ciclo_ts_nuevo_sigue_bloqueando(tmp_path):
    root = _mixto(tmp_path)
    git = _repo_git(root)
    git("add", "-A")
    git("commit", "-qm", "base sin ciclo")
    _escribe(root, "web/cliente.ts", "import { render } from './app';\n\n"
                                     "export function fetchUsers() {\n  return render();\n}\n")
    git("commit", "-qam", "cierra el ciclo")
    assert cli.main(["graph", root, "--gate", "--since", "HEAD~1"]) == 1


@necesita_astgrep
def test_check_calcula_la_onda_de_un_cambio_en_typescript(tmp_path):
    """Auditoria del 24-sep-2026: la onda de `check` (simbolos tocados y sus
    llamantes) salia del motor de Python y un cambio en un .ts la dejaba vacia."""
    root = _mixto(tmp_path)
    git = _repo_git(root)
    git("add", "-A")
    git("commit", "-qm", "base")
    _escribe(root, "web/cliente.ts", "export function fetchUsers() {\n  return [1];\n}\n")
    git("commit", "-qam", "toca ts")

    from galaxybrain import changes

    report = changes.analyze(root, "HEAD~1..HEAD", constructor=cli._constructor_de_grafo(root),
                             informe_simbolos=cli._analiza_simbolos(root))
    assert any("fetchUsers" in (o.get("symbol") or o.get("qual") or str(o)) for o in report["onda"]), \
        report["onda"]


@necesita_astgrep
def test_dead_no_da_por_huerfano_un_modulo_js_importado(tmp_path, capsys):
    """Auditoria del 24-sep-2026: `dead` sacaba el "nadie lo importa" del grafo
    de Python, asi que en express `application`/`request`/`response` (cargados
    con `require`) salian como modulos huerfanos."""
    import json

    root = str(tmp_path / "js")
    # como `application` en express: se carga con require y se mezcla, sin una
    # sola llamada resuelta que la salve por otra via
    _escribe(root, "app.js", "const util = require('./util');\nObject.assign(exports, util);\n")
    _escribe(root, "util.js", "function ayuda() { return 1; }\nmodule.exports = { ayuda };\n")
    cli.main(["dead", root, "--json"])
    informe = json.loads(capsys.readouterr().out)
    assert "util" not in [m.get("module") or m.get("qual") or m for m in informe["modulos_huerfanos"]], \
        informe["modulos_huerfanos"]
