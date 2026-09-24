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
