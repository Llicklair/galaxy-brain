"""JS/TS: los simbolos que no se escriben `function nombre`.

Medido sobre express el 24-sep-2026: `app.use = function use(...)` y los metodos
de clase no eran simbolos, asi que gb no veia ni un metodo de la libreria. La
matriz va por modificador porque la gramatica no deja una metavariable en su
sitio: cada uno es un patron, y probar solo el plano certificaria de mas.
"""

import os

import pytest

from galaxybrain import lenguajes

pytestmark = pytest.mark.skipif(
    not lenguajes.binario(),
    reason="ast-grep no instalado; la capa multilenguaje es opcional (ADR 0009)",
)

JS = """class C {
  plano(a) { return a; }
  static estatico() { return 1; }
  async asincrono() { return 1; }
  get lectura() { return 2; }
  set escritura(v) { this.v = v; }
}
app.usa = function usa(fn) { return fn; };
res.envia = function (body) { return body; };
exports.flecha = (x) => { return x; };
"""

TS = """class C {
  plano(a: number) { return a; }
  tipado(a: number): number { return a; }
  private privado(): number { return 1; }
  public publico(): void { }
  protected protegido() { }
  static estatico(): number { return 1; }
  private async pa(): Promise<void> { }
}
"""


def _nombres(tmp_path, nombre, fuente):
    raiz = os.path.join(str(tmp_path), nombre.split(".")[1])
    os.makedirs(raiz)
    with open(os.path.join(raiz, nombre), "w", encoding="utf-8") as fh:
        fh.write(fuente)
    return {n["qual"].rsplit(".", 1)[-1] for n in lenguajes.analyze(raiz)["nodes"]
            if n["kind"] != "module"}


def test_js_metodos_y_propiedades(tmp_path):
    vistos = _nombres(tmp_path, "a.js", JS)
    for nombre in ("plano", "estatico", "asincrono", "lectura", "escritura",
                   "usa", "envia", "flecha"):
        assert nombre in vistos, "%s no es simbolo; salen %s" % (nombre, sorted(vistos))


def test_ts_metodos_con_visibilidad_y_retorno(tmp_path):
    vistos = _nombres(tmp_path, "a.ts", TS)
    for nombre in ("plano", "tipado", "privado", "publico", "protegido", "estatico", "pa"):
        assert nombre in vistos, "%s no es simbolo; salen %s" % (nombre, sorted(vistos))


def _llamadas(tmp_path, nombre, fuente):
    raiz = os.path.join(str(tmp_path), "ll_" + nombre.split(".")[0])
    os.makedirs(raiz)
    with open(os.path.join(raiz, nombre), "w", encoding="utf-8") as fh:
        fh.write(fuente)
    return {(o.rsplit(".", 1)[-1], d.rsplit(".", 1)[-1])
            for o, d, tipo in lenguajes.analyze(raiz)["edges"] if tipo == "CALLS"}


def test_this_resuelve_por_ambito_de_clase(tmp_path):
    """`this.set()` dentro de un metodo es el `set` de ESA clase — y no el de
    otra clase del mismo fichero con el mismo nombre."""
    fuente = ("class A {\n  set(v) { return v; }\n  configurar() { return this.set(1); }\n}\n"
              "class B {\n  set(v) { return v; }\n  otro() { return this.set(2); }\n}\n")
    aristas = _llamadas(tmp_path, "clases.js", fuente)
    assert ("configurar", "set") in aristas and ("otro", "set") in aristas, aristas


def test_this_resuelve_por_objeto_asignado(tmp_path):
    """El patron de express: `app.handle = function () { this.set() }` es
    `app.set`; `this.nada()` sin dueno conocido no inventa arista."""
    fuente = ("app.set = function set(k, v) { return v; };\n"
              "app.handle = function handle() { return this.set('a', 1); };\n"
              "res.send = function send() { return this.nada(); };\n")
    aristas = _llamadas(tmp_path, "app.js", fuente)
    assert ("handle", "set") in aristas, aristas
    assert not any(d == "nada" for _, d in aristas), aristas
