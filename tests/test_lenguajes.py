"""El motor multilenguaje: mismo informe, otro parser (ADR 0009).

La condicion de calidad NO es cubrir muchos lenguajes — es que lo que devuelva
tenga la MISMA forma que la via Python y declare su techo igual de bien. Un
segundo motor que miente distinto que el primero es peor que no tener segundo
motor.

Los tests que necesitan el binario se saltan si no esta: es dependencia externa
opcional por diseno, y una suite que exige instalarla convertiria en obligatorio
lo que SCOPE declara opcional.
"""

import os

import pytest

from galaxybrain import cli, lenguajes

necesita_astgrep = pytest.mark.skipif(
    not lenguajes.binario(), reason="ast-grep no instalado; la capa multilenguaje es opcional (ADR 0009)"
)


def _escribe(root, rel, contenido):
    ruta = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write(contenido)


@pytest.fixture
def proyecto_js(tmp_path):
    root = str(tmp_path / "app")
    _escribe(root, "src/carrito.js",
             "export function subtotal(xs) { return xs.reduce((a, b) => a + b, 0); }\n"
             "export function total(xs) { return subtotal(xs) * 1.21; }\n")
    _escribe(root, "src/factura.js",
             'import { total } from "./carrito.js";\n'
             "export function emitir(xs) { return total(xs); }\n")
    return root


# --- la forma del informe: el contrato con todo lo que hay debajo -------------


@necesita_astgrep
def test_devuelve_la_misma_forma_que_la_via_python(proyecto_js):
    """Si esto se rompe, el mapa, la CLI y el suelo se enteran del lenguaje —
    que es exactamente lo que el diseno evita."""
    informe = lenguajes.analyze(proyecto_js)

    for clave in ("root", "root_error", "nodes", "edges", "calls_total",
                  "calls_candidates", "calls_resolved", "calls_builtin",
                  "unresolved", "not_covered"):
        assert clave in informe, clave
    assert not informe["root_error"]
    nodo = informe["nodes"][0]
    assert set(nodo) >= {"qual", "kind", "module", "file", "line"}


@necesita_astgrep
def test_encuentra_los_simbolos_una_sola_vez(proyecto_js):
    """`export function f` casa con dos patrones a la vez; contarlo dos veces
    inflaria el grafo con simbolos fantasma."""
    informe = lenguajes.analyze(proyecto_js)

    funciones = [n["qual"] for n in informe["nodes"] if n["kind"] == "function"]
    assert sorted(funciones) == ["carrito.subtotal", "carrito.total", "factura.emitir"]


@necesita_astgrep
def test_la_arista_de_import_solo_cuenta_lo_interno(tmp_path):
    """Un paquete de node_modules no es codigo de este proyecto: su arista no
    dice nada del acoplamiento propio."""
    root = str(tmp_path / "app")
    _escribe(root, "src/a.js", 'import { x } from "./b.js";\nimport React from "react";\n')
    _escribe(root, "src/b.js", "export function x() { return 1; }\n")

    aristas = [(e[0], e[1]) for e in lenguajes.analyze(root)["edges"] if e[2] == "IMPORTS"]

    assert aristas == [("a", "b")], "react es externo: su arista no dice nada del acoplamiento propio"


@necesita_astgrep
def test_resuelve_las_llamadas_que_puede_y_declara_el_resto(proyecto_js):
    informe = lenguajes.analyze(proyecto_js)

    llamadas = {(e[0], e[1]) for e in informe["edges"] if e[2] == "CALLS"}
    # La arista sale de la FUNCION que llama, no de su modulo: si saliera del
    # modulo la cadena transitiva se cortaria (nadie "llama" a un modulo) y la
    # seleccion de tests perderia los impactos indirectos. Medido en el banco de
    # JS: con aristas de modulo, romper el simbolo mas profundo seleccionaba 1
    # test de los 5 que dependian de el.
    assert ("factura.emitir", "carrito.total") in llamadas
    assert ("carrito.total", "carrito.subtotal") in llamadas
    # y el techo, declarado igual que en Python (ADR 0008): `xs.reduce(...)`
    assert informe["unresolved"].get("atributo-de-variable")
    assert any("inventada" in linea for linea in informe["not_covered"])


# --- degradar diciendolo, nunca fingir ---------------------------------------


def test_sin_ast_grep_lo_dice_y_no_revienta(proyecto_js, monkeypatch):
    """Criterio 4 del alcance: sin el binario la capa se degrada DECLARANDO.
    Un informe vacio y mudo aqui seria el mismo fallo que la Fase 0 cerro."""
    monkeypatch.setattr(lenguajes, "binario", lambda: None)

    informe = lenguajes.analyze(proyecto_js)

    assert informe["root_error"] and "ast-grep" in informe["root_error"]
    assert informe["nodes"] == []


def test_una_raiz_sin_js_lo_dice(tmp_path):
    informe = lenguajes.analyze(str(tmp_path))

    assert "ni un fichero de un lenguaje soportado" in informe["root_error"]
    assert not lenguajes.hay_codigo(str(tmp_path))


def test_node_modules_no_es_codigo_del_proyecto(tmp_path):
    root = str(tmp_path / "app")
    _escribe(root, "node_modules/lib/index.js", "export function x() {}\n")

    assert not lenguajes.hay_codigo(root)


# --- nombres de modulo, con el mismo criterio que Python ---------------------


def test_el_nombre_de_modulo_descuenta_src_y_index(tmp_path):
    root = str(tmp_path)
    assert lenguajes.module_name(os.path.join(root, "src", "carrito.js"), root) == "carrito"
    assert lenguajes.module_name(os.path.join(root, "src", "cosas", "index.js"), root) == "cosas"
    assert lenguajes.module_name(os.path.join(root, "lib", "util.ts"), root) == "lib.util"


# --- el despacho: Python manda cuando hay Python -----------------------------


@necesita_astgrep
def test_un_repo_mixto_usa_el_motor_de_python(tmp_path):
    """La via JS entra solo donde no habia nada que analizar; nunca pisa un
    resultado bueno del motor maduro."""
    root = str(tmp_path / "mix")
    _escribe(root, "modulo.py", "def f():\n    return 1\n")
    _escribe(root, "src/a.js", "export function g() { return 2; }\n")

    informe = cli._analiza_simbolos(root)

    assert informe.get("motor") is None            # el de Python no marca motor
    assert any(n["qual"].endswith("f") for n in informe["nodes"])


# --- el grafo: la topologia se reutiliza, no se reimplementa ----------------


@necesita_astgrep
def test_el_ciclo_de_imports_se_detecta_igual_en_js(proyecto_js):
    """El criterio que decide si `build_graph` inyectado sirve: los ciclos los
    calcula el codigo de `graph`, ya probado, con aristas que pone `js`. Si
    hubiera una segunda deteccion de ciclos aqui, tarde o temprano divergiria."""
    from galaxybrain import graph

    limpio = graph.analyze(proyecto_js, constructor=lenguajes.build_graph)
    assert limpio["modules"] == 2 and limpio["cycles"] == []

    # se cierra el ciclo: factura ya importaba carrito
    _escribe(proyecto_js, "src/carrito.js",
             'import { emitir } from "./factura.js";\n'
             "export function total(xs) { return emitir(xs); }\n")

    conciclo = graph.analyze(proyecto_js, constructor=lenguajes.build_graph)
    assert [sorted(c) for c in conciclo["cycles"]] == [["carrito", "factura"]]


@necesita_astgrep
def test_gb_graph_sobre_js_no_da_el_falso_cero(proyecto_js, capsys):
    """Antes del ADR 0009 esto respondia `0 modulos` con su aviso. Ahora
    responde de verdad — el aviso sigue existiendo para los lenguajes sin
    motor, que es lo que fija tests/test_no_leido.py."""
    assert cli.main(["graph", proyecto_js]) == 0

    salida = capsys.readouterr().out
    assert "2 modulos" in salida
    assert "ni un modulo analizado" not in salida


@necesita_astgrep
def test_symbols_declara_su_techo_en_js(proyecto_js, capsys):
    """Criterio 2: no basta con listar; hay que decir cuanto NO se resuelve."""
    assert cli.main(["symbols", proyecto_js]) == 0

    salida = capsys.readouterr().out
    assert "atributo-de-variable" in salida
    assert "una arista inventada es peor" in salida


@necesita_astgrep
def test_el_delta_no_soportado_se_declara_en_vez_de_ignorarse(proyecto_js):
    """Ignorar una bandera en silencio es mentir por omision: quien escribe
    `--since` espera un delta y recibiria el estado absoluto sin enterarse."""
    informe = cli._analiza_simbolos(proyecto_js, since="HEAD~1")

    assert any("--since" in linea for linea in informe["not_covered"])


@necesita_astgrep
def test_la_seleccion_de_tests_sigue_la_cadena_indirecta(tmp_path):
    """Criterio 6, la parte que casi se cuela: el test que NO importa el simbolo
    roto pero llega a el por un tercero.

    En el banco con `node --test` esto da 0 falsos verdes y 52% de ahorro; aqui
    se fija la propiedad estructural que lo hace posible, que es la unica que se
    puede comprobar sin un runner de JS instalado.
    """
    from galaxybrain import impacted

    root = str(tmp_path / "cadena")
    _escribe(root, "src/iva.js", "export function iva() { return 0.21; }\n")
    _escribe(root, "src/carrito.js",
             'import { iva } from "./iva.js";\n'
             "export function total(xs) { return xs * (1 + iva()); }\n")
    _escribe(root, "test/carrito.test.js",
             'import { total } from "../src/carrito.js";\ntest("t", () => total(1));\n')

    informe = lenguajes.analyze(root)
    nodes = {n["qual"]: n for n in informe["nodes"]}
    llamantes = impacted._llamantes(informe["edges"])

    # el test NO menciona `iva`, pero llega por carrito.total
    alcanzan, _truncado = impacted.tests_que_alcanzan(nodes, llamantes, ["iva.iva"])
    assert "carrito.test" in {q.rsplit(".", 1)[0] if "." in q else q for q in alcanzan} \
        or any("carrito.test" in q for q in alcanzan), alcanzan


@necesita_astgrep
def test_gb_calls_nombra_a_los_llamantes_en_js(proyecto_js, capsys):
    codigo = cli.main(["calls", "total", proyecto_js])

    salida = capsys.readouterr().out
    assert codigo == 0
    assert "carrito.total" in salida
    assert "factura" in salida
