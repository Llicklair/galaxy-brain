"""El buzón de los hooks no-Python: que `gb last/show/list` los vea sin cambiar.

Criterio 3 de la ADR 0012, que es el único que bloqueaba: *«`gb last`, `gb show`
y `gb list` funcionan **sin modificación** sobre esos registros»*. Los hooks
escriben en `~/.galaxy-brain/crashes.jsonl` con schema v2; gb archiva en
`index.jsonl` + `errors/<proyecto>/<id>.json`. Aquí se prueba el puente.

Lo que NO se toca —y por eso esto cumple el criterio literalmente— es `store.py`
y `render.py`: ni una línea.
"""

import json
import os

import pytest

from galaxybrain import buzon, cli, render, store


def _bruto(**cambios):
    """Un registro de hook nativo tal cual lo escribe el de js, con la pila en su
    orden: el frame MAS INTERNO PRIMERO, al revés que Python."""
    base = {
        "schema": 2,
        "ts": "2026-08-18T09:00:00.000Z",
        "language": "js",
        "exception": {"type": "TypeError", "message": "Cannot read properties of null",
                      "origin": "uncaughtException"},
        "frames": [
            {"file": "C:/proy/app.js", "line": 3, "function": "sirve"},
            {"file": "node:internal/main/run_main_module", "line": 33, "function": "?"},
        ],
        "process": {"pid": 123, "cwd": "C:/proy", "command": "node app.js"},
    }
    base.update(cambios)
    return base


def _registro(entrada):
    """El registro entero, leido del fichero que apunta el indice."""
    with open(entrada["path"], encoding="utf-8") as fh:
        return json.load(fh)


def _buzon(gb_home, *registros):
    os.makedirs(str(gb_home), exist_ok=True)
    with open(os.path.join(str(gb_home), "crashes.jsonl"), "a", encoding="utf-8") as fh:
        for r in registros:
            fh.write(json.dumps(r) + "\n")


def test_un_registro_de_hook_acaba_en_el_almacen_de_gb(gb_home):
    _buzon(gb_home, _bruto())
    assert buzon.drena() == 1

    entradas = store.read_index()
    assert entradas, "el registro no llego al indice"


def test_el_titular_apunta_a_TU_codigo_y_no_al_arranque_del_runtime(gb_home):
    """El fallo más caro y el más silencioso: `render._headline_index` recorre la
    pila hacia atrás porque Python emite el frame más interno el ÚLTIMO. js,
    java, csharp, ruby, php, go y rust la emiten al revés, así que sin invertir
    el titular sale siendo `node:internal/...` — el arranque de Node — en vez de
    la línea que reventó. No lanza, no avisa: solo señala mal."""
    _buzon(gb_home, _bruto())
    buzon.drena()

    registro = _registro(store.read_index()[0])
    i = render._headline_index(registro["frames"])
    assert "app.js" in registro["frames"][i]["file"]
    assert "node:internal" not in registro["frames"][i]["file"]


def test_gb_show_pinta_una_captura_de_js_sin_reventar(gb_home):
    """`frames[].source` es un STRING en el schema v2 y una LISTA de
    `{n,text,is_fail}` en gb: sin convertir, `render` itera el string carácter a
    carácter y muere con AttributeError dentro de `gb show`."""
    _buzon(gb_home, _bruto(frames=[{"file": "C:/proy/app.js", "line": 3,
                                    "function": "sirve", "source": "o.metodo()"}]))
    buzon.drena()

    texto = render.render_record(_registro(store.read_index()[0]),
                                 render.Style(False), full=True)
    assert "TypeError" in texto
    assert "app.js" in texto


def test_drenar_dos_veces_no_duplica(gb_home):
    """La marca de agua es el contrato: cada comando de gb llama a esto."""
    _buzon(gb_home, _bruto())
    assert buzon.drena() == 1
    assert buzon.drena() == 0
    assert len(store.read_index()) == 1


def test_una_linea_rota_no_se_lleva_por_delante_las_buenas(gb_home):
    """El buzón lo escriben varios procesos a la vez: una línea a medias es
    normal, no excepcional. Se salta esa y siguen las demás."""
    os.makedirs(str(gb_home), exist_ok=True)
    with open(os.path.join(str(gb_home), "crashes.jsonl"), "w", encoding="utf-8") as fh:
        fh.write('{"schema": 2, "ts": "x", "lang')          # truncada
        fh.write("\n" + json.dumps(_bruto()) + "\n")

    assert buzon.drena() == 1


def test_sin_buzon_no_pasa_nada(gb_home):
    assert buzon.drena() == 0


def test_el_buzon_nunca_tumba_a_gb(gb_home, monkeypatch):
    """Propiedad 5 de ARCHITECTURE: si la captura falla, el programa sigue como
    si la consola no existiera. Aquí el 'programa' es la CLI del usuario."""
    _buzon(gb_home, _bruto())

    def revienta(_registro):
        raise RuntimeError("almacen roto")

    monkeypatch.setattr(store, "write", revienta)
    assert buzon.drena() == 0                     # no lanza
    assert cli.main(["list", "--color", "never"]) == 0


def test_lo_que_no_se_puede_derivar_queda_en_None_no_inventado(gb_home):
    """Regla 9. El fallback stderr no trae locales ni código fuente, y un hook
    puede no traer `cwd`. Nada de eso se rellena a ojo."""
    _buzon(gb_home, _bruto(frames=[{"file": "a.go", "line": 6, "function": "explotar"}],
                           process={"pid": 7}))
    buzon.drena()

    registro = _registro(store.read_index()[0])
    assert registro["frames"][0]["locals"] is None
    assert registro["frames"][0]["source"] == []


@pytest.mark.parametrize("lang", ["js", "java", "csharp", "ruby", "php", "lua"])
def test_los_seis_lenguajes_medidos_entran(gb_home, lang):
    """Los seis con gancho de observación verificado. Si uno deja de entrar, es
    que su hook cambió de forma y el puente no se ha enterado."""
    _buzon(gb_home, _bruto(language=lang))
    assert buzon.drena() == 1
    assert store.read_index()


def test_perder_la_marca_de_agua_no_duplica(gb_home):
    """El fallo que costó 17 capturas duplicadas en un histórico real.

    La idempotencia estaba puesta SOLO en `crashes.offset`, un fichero como
    cualquier otro: se borra al limpiar, se pierde al rotar, y entonces el buzón
    se relee entero y todo entra por segunda vez. Ahora el id se deriva del
    contenido, así que releer es gratis en vez de destructivo.
    """
    _buzon(gb_home, _bruto(), _bruto(ts="2026-08-18T09:00:01.000Z"))
    assert buzon.drena() == 2

    os.remove(os.path.join(str(gb_home), "crashes.offset"))   # se pierde la marca
    assert buzon.drena() == 0, "releer el buzón ha duplicado"
    assert len(store.read_index()) == 2


def test_dos_crashes_distintos_en_el_mismo_segundo_son_dos(gb_home):
    """El control del test de arriba: deduplicar no puede tragarse hechos
    distintos. Mismo instante, mismo tipo, distinto sitio -> dos entradas."""
    _buzon(gb_home,
           _bruto(frames=[{"file": "C:/proy/a.js", "line": 1, "function": "f"}]),
           _bruto(frames=[{"file": "C:/proy/b.js", "line": 2, "function": "g"}]))
    assert buzon.drena() == 2
    assert len(store.read_index()) == 2
