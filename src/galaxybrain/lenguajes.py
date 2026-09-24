"""El grafo de cualquier lenguaje, derivado con `ast-grep` por referencia (ADR 0009).

Devuelve **la misma forma de informe** que el motor de Python (`symbols.analyze`):
`nodes`, `edges`, contadores de llamadas y `unresolved` por causa. Ese es el punto
entero — el 74 % del código de gb (el mapa, la CLI, el almacén, el suelo) opera
sobre el grafo ya derivado y no debe enterarse del lenguaje.

Todo lo específico de un lenguaje vive en `LENGUAJES`, una tabla de datos: sus
extensiones, los patrones que reconocen una definición, un import y una llamada,
su vocabulario de runtime y su convención de ficheros de test. El motor de abajo
no menciona ningún lenguaje. Añadir uno es una entrada en la tabla; si hiciera
falta tocar el motor, la tabla estaría mal diseñada.

**Los patrones no se suponen, se miden.** Cada entrada tiene su sonda en
`sonda()`, que extrae de un fuente mínimo y comprueba qué sale de verdad — así
"soportamos N lenguajes" es una afirmación verificable en cualquier momento y no
una lista de buenas intenciones. Lo que una sonda no consigue se escribe en
`carencias`, se enseña al usuario y no se disimula.

Límites comunes, dichos de frente igual que en la vía Python (ADR 0008): es
análisis ESTÁTICO por patrón. No resuelve llamadas sobre variables
(`obj.metodo()`), no sigue carga dinámica ni reexports, y no distingue dos
símbolos homónimos salvo por el import que los trae. Todo eso **se cuenta y se
declara**; no se adivina.
"""

import copy
import json
import os
import re
import shutil
import subprocess

#: Vocabulario de runtime que no son símbolos del proyecto. Equivale a los
#: builtins de Python: se excluye del denominador para que el porcentaje de
#: resolución signifique algo.
_JS_GLOBALES = frozenset((
    "console", "require", "setTimeout", "setInterval", "clearTimeout", "clearInterval",
    "fetch", "parseInt", "parseFloat", "isNaN", "String", "Number", "Boolean", "Array",
    "Object", "JSON", "Math", "Date", "Promise", "Error", "Symbol", "Map", "Set",
    "RegExp", "encodeURIComponent", "decodeURIComponent", "structuredClone",
    "describe", "it", "test", "expect", "beforeEach", "afterEach", "beforeAll",
    "afterAll", "vi", "jest", "assert",
))

_COMUNES = frozenset(("print", "println", "printf", "len", "append", "make", "new",
                      "panic", "assert", "require", "test", "it", "describe", "expect"))

#: Los imports de la familia JS (js/ts/tsx), en UN solo sitio: son el mismo
#: lenguaje de módulos y tenerlos por triplicado fue justo cómo `require()` se
#: quedó solo en js y `import type` en ninguno.
#:
#: `$SRC` va SUELTA, sin comillas alrededor. Con `"$SRC"` el patrón solo casaba
#: comillas dobles, así que `from './a.js'` —el estilo mayoritario del
#: ecosistema— no dejaba NI UNA arista: el gate de un repo entero podía estar
#: mudo por una comilla. Se midió el 15-ago-2026, y llevaba meses en verde
#: porque la sonda de conformidad también estaba escrita con dobles (por eso
#: ahora la matriz de [[test_variantes_import]] prueba las dos). Suelta, la
#: metavariable casa el literal completo y `_sin_comillas` lo limpia después.
#:
#: Las formas no son un catálogo teórico: el barril (`export * from`) es el
#: patrón de carpeta más común de frontend, `import()` es todo code-splitting,
#: `require()` es backend CommonJS, y `import './x.css'` no importa símbolos
#: pero SÍ es dependencia de módulo — que es lo que mira el gate.
_JS_IMPORTS = (
    "import { $$$ } from $SRC",
    "import $NAME from $SRC",
    "import * as $NAME from $SRC",
    "import type { $$$ } from $SRC",
    "import $SRC",
    "require($SRC)",
    "import($SRC)",
    # El barril necesita las comillas EN el patrón y por duplicado, al revés
    # que el import. Medido: en `export ... from`, la metavariable suelta no
    # casa nada (ni con selector, ni con `;`, ni con `$$$`) — la gramática no
    # deja que ocupe esa posición; dentro de las comillas sí, pero entonces
    # cada tipo de comilla es un patrón. Es fealdad de la técnica, no del
    # lenguaje, y sale más barato duplicar dos líneas que perder los barriles.
    "export * from '$SRC'",
    'export * from "$SRC"',
    "export { $$$ } from '$SRC'",
    'export { $$$ } from "$SRC"',
)

#: Las definiciones que no son `function nombre`: la mitad del JS real. Medido
#: sobre express el 24-sep-2026: `app.use = function use(...)`, `res.send = ...`
#: y compañía (52 en lib/) no eran simbolos, y gb no veia ni un metodo de la
#: libreria ni quien los llama. El nombre es la PROPIEDAD (`use`), no la funcion.
#: Son `method`: pertenecen a un objeto, y la seleccion los trata como tales.
_JS_PROPIEDADES = (
    ("method", "$OBJ.$NAME = function $F($$$) { $$$ }"),
    ("method", "$OBJ.$NAME = function ($$$) { $$$ }"),
    ("method", "$OBJ.$NAME = ($$$) => { $$$ }"),
)


def _metodos_js(retornos):
    """Los metodos de clase, un patron por modificador: la gramatica no deja una
    metavariable en la posicion del modificador, asi que `static`, `async`,
    `get`/`set` y los de visibilidad de TS son patrones aparte (medido: el plano
    no casa ninguno de ellos). Van todos en el mismo `scan` por lotes."""
    modificadores = ("", "static ", "async ", "static async ", "get ", "set ",
                     "private ", "public ", "protected ", "private static ",
                     "private async ", "public static ", "public async ",
                     "protected static ", "protected async ")
    return tuple(("method", "class A { %s$NAME($$$)%s { $$$ } }" % (m, r), "method_definition")
                 for m in modificadores for r in retornos)


def _clases_php():
    """Clases, interfaces, traits y enums. `$$$` tras el nombre cubre
    `extends`/`implements`; los modificadores y los atributos no admiten
    metavariable, asi que cada combinacion es un patron. Medido sobre
    league/container el 24-sep-2026: con `class $NAME { $$$ }` salia 1 clase
    de src/ de 57 — `final`, `readonly`, `implements` y `interface` la tapaban."""
    formas = tuple("%sclass $NAME $$$ { $$$ }" % m
                   for m in ("", "final ", "abstract ", "readonly ", "final readonly ",
                             "readonly final ", "abstract readonly "))
    formas += ("interface $NAME $$$ { $$$ }", "trait $NAME { $$$ }", "enum $NAME $$$ { $$$ }")
    return tuple(("class", a + f) for a in ("", "#[$$$] ") for f in formas)


def _metodos_php():
    """Los metodos, un patron por modificador x tipo de retorno x atributo: ni el
    modificador, ni el `: Tipo`, ni el `#[...]` admiten metavariable, y el patron
    plano no casa ninguno (medido: `public function x(): int` no salia, y en PHP
    moderno es casi todo). Los de cuerpo `;` son los abstractos y los de interfaz."""
    con_cuerpo = ("", "public ", "protected ", "private ", "static ", "public static ",
                  "protected static ", "private static ", "final public ",
                  "final protected ", "final public static ")
    sin_cuerpo = ("", "public ", "abstract public ", "abstract protected ", "public static ")
    formas = ["%sfunction $NAME($$$)%s { $$$ }" % (m, r)
              for m in con_cuerpo for r in ("", ": $R")]
    formas += ["%sfunction $NAME($$$)%s;" % (m, r) for m in sin_cuerpo for r in ("", ": $R")]
    return tuple(("method", "class A { %s%s }" % (a, f), "method_declaration")
                 for a in ("", "#[$$$] ") for f in formas)


#: Las llamadas de PHP son tres nodos distintos y `$FN($$$)` solo ve la primera.
#: La de metodo (`$this->x()`) no parsea suelta: necesita el `<?php` delante y
#: selector. `$A` es el receptor (`$this`, `self`, `Clase`), que el extractor
#: compone como en Java y resuelve por ambito o por nombre de clase.
_LLAMADA_PHP = ("$FN($$$)", "$A::$FN($$$)",
                ("<?php $A->$FN($$$);", "member_call_expression"))

_JS_CARENCIAS = (
    "los generadores de clase (`*gen() {}`) y los metodos con nombre calculado "
    "(`[clave]() {}`) no son simbolos; tampoco las asignaciones dinamicas "
    "(`app[metodo] = function`), que no tienen nombre escrito",
    "de las llamadas a metodo se resuelve `this.x()` por ambito (la clase, o el "
    "objeto al que se asigno la funcion); `obj.x()` y `new C().x()` no, porque "
    "exigen seguir la variable — por eso tocar un metodo corre todos los tests",
)

#: `new X(...)` construye una X: es una llamada a la clase, y sin ella quien usa
#: una subclase no la "llamaba" y la herencia no tenia por donde subir en la
#: seleccion (24-sep-2026). JS, TS, Java y C#; `$FN` es el nombre del tipo.
_NEW = "new $FN($$$)"

#: `$FN($$$)` casa cualquier invocación; decidir cuáles se pueden resolver es
#: trabajo de después, con nombres. Casi todos los lenguajes lo comparten.
LLAMADA = ("$FN($$$)",)

#: Rust necesita más: el cuerpo de un macro es un árbol de TOKENS, no una
#: expresión, así que `$FN($$$)` no ve `iva()` dentro de `assert!(iva() > 0.0)`
#: — y el código de test idiomático en Rust es todo `assert_eq!`. Medido el
#: 9-ago: sin esto, CERO aristas desde los tests y `gb tests` caía a la suite
#: entera en las 7 roturas del banco. Los dos patrones extra son coincidencias
#: de AST de verdad (ast-grep liga `$FN` dentro del macro), no rascado de texto:
#: no pueden fabricar una arista que no exista.
#: El cuarto patron es la llamada que NO es el primer argumento del macro:
#: `format!("TOTAL {:.2}", emitir(xs))`. Sin el, la cascada de Rust moria en
#: `informe.linea -> factura.emitir` y el banco lo tapaba (ver bancos/estricto.py).
#:
#: Se llama `$ARG` y no `$A` por un motivo que costo un intento entero: `$A` es la
#: metavariable del RECEPTOR en `$A.$FN($$$)` (Java, Kotlin, Scala), y el extractor
#: compone `receptor.llamado` cuando la ve. Con `$A` aqui, ast-grep casaba y
#: capturaba `FN` correctamente pero gb emitia `"TOTAL {:.2}".emitir`, que no
#: resuelve contra nada — y el sintoma era «el patron casa y la arista no sale».
LLAMADA_RUST = ("$FN($$$)", "$M!($FN($$$), $$$)", "$M!($FN($$$))",
                "$M!($ARG, $FN($$$))")


class _Regla(str):
    """Una REGLA de ast-grep (kind + relaciones) donde la tabla pone un patron.

    Un patron casa los modificadores exactos que escribe; una gramatica con
    muchos (C#: `public static async override ...`) necesita una combinacion por
    forma. La regla dice "este kind, con este nombre" y casa todas. Es un `str`
    (su JSON, que tambien es YAML valido y cabe en UNA linea) para que viaje
    por la tabla, el lote y las claves de cache sin tocar a quien la lee; el
    motor la reconoce por su tipo y la corre con `scan` en vez de `run`.
    """

    def __new__(cls, regla):
        return super().__new__(cls, json.dumps(regla, sort_keys=True))


def _regla_con_cuerpo(kind):
    """Un simbolo por KIND del arbol: el nodo `kind` con su nombre en `$NAME`.

    Exige CUERPO, como exigian los patrones (`{ $$$ }`): un metodo abstracto o
    de interfaz no tiene codigo que llamar, y como simbolo atraia llamadas
    ajenas por nombre — `fail()` de `org.junit.Assert` caia en el `void fail()
    throws R;` de una interfaz de test de javapoet.
    """
    return _Regla({"all": [{"kind": kind},
                           {"has": {"field": "name", "pattern": "$NAME"}},
                           {"has": {"field": "body", "pattern": "$CUERPO"}}]})


def _regla_con_nombre(kind):
    """Un simbolo por KIND sin exigir cuerpo: para las definiciones que lo son
    sin llaves (`case class C(x: Int)`, `trait Marca` en Scala), donde el
    abstracto es otro kind y no hay nada que filtrar."""
    return _Regla({"all": [{"kind": kind},
                           {"has": {"field": "name", "pattern": "$NAME"}}]})


#: El componente ENVUELTO: `const X = React.memo((p) => ...)`,
#: `forwardRef<El, P>(function X(p, ref) {...})`, `memo(forwardRef(...))`. El
#: nombre es la variable; el envoltorio se nombra EXACTO (memo/forwardRef, con
#: o sin `React.`) porque `const $NAME = $W(($$$) => ...)` tambien casaria
#: `const store = create((set) => ...)`, que no es un componente ni se llama por
#: ese nombre. Regla y no patron: el generico, el `: React.FC<P>` y el
#: anidamiento son cada uno un patron aparte (medido con ast-grep 0.45).
_TSX_ENVUELTOS = _Regla({"all": [
    {"kind": "variable_declarator"},
    {"has": {"field": "name", "pattern": "$NAME"}},
    {"has": {"field": "value", "kind": "call_expression", "all": [
        {"has": {"field": "function", "regex": r"^(React\.)?(memo|forwardRef)$"}},
        {"has": {"field": "arguments", "stopBy": "end",
                 "any": [{"kind": "arrow_function"}, {"kind": "function_expression"}]}},
    ]}},
]})

#: `<Button/>` y `<Card>...</Card>` SON llamadas: React invoca el componente al
#: renderizar, y sin esto un componente no tenia NI UN llamante (`gb calls
#: ToastBar` vacio en react-hot-toast, que lo renderiza desde Toaster). Solo con
#: mayuscula: en JSX la minuscula es un elemento del DOM (`<div>`), por
#: definicion del lenguaje, y contarlo inflaria los no resueltos.
_TSX_JSX = _Regla({"all": [
    {"any": [{"kind": "jsx_self_closing_element"}, {"kind": "jsx_opening_element"}]},
    {"has": {"field": "name", "pattern": "$FN", "regex": r"^[A-Z]"}},
]})


def _lang(ag, extensiones, simbolos, imports=(), llamada=LLAMADA, globales=_COMUNES,
          resolucion=None, sufijos_test=(), dirs_test=("test", "tests"), carencias=(),
          tia=False):
    """Una entrada de la tabla.

    `tia` es una LICENCIA, y por eso su defecto es False: dice que el grafo de
    llamadas de este lenguaje se midió lo bastante completo como para ESTRECHAR
    la selección de tests. Sin ella, `gb tests` corre la suite entera.

    El motivo es que un grafo incompleto no cuesta ahorro, cuesta un verde falso:
    si falta una arista, los tests que llegaban por ahí se caen de la selección y
    la suite reducida pasa con el árbol roto. Se midió en Rust el 9-ago — la
    llamada dentro de `format!("...", emitir(xs))` es invisible, y con ella se
    caía `tests/informe` de los impactados por `iva`. No dio verde falso de puro
    azar (todos los tests recorrían la cadena), y esa clase de suerte no se deja
    suelta (ADR 0009, criterio de aborto 1).

    **Deuda del 10-ago-2026, SALDADA el 15-ago.** js, ts, go, csharp y rust se
    remidieron con el criterio estricto —que la selección CONTENGA todos los
    tests que se ponen rojos, no que alguno lo esté (`bancos/estricto.py`)— y
    las cinco daban cascada exacta. java, php y lua quedaron a medias: se les
    había comprobado la cascada (la mitad que no necesita intérprete, justo la
    que falló en Rust) pero no los rojos reales, porque sus intérpretes no
    estaban en la máquina de la revisión. Ya lo están, así que se remidieron:
    **4 roturas, 0 falsos verdes, cascada exacta y 56 % de ahorro en los tres**
    (`python bancos/bench_multi.py java php lua`). Las nueve licencias no-Python
    descansan hoy sobre el mismo criterio, sin asteriscos.

    **Ruby la ganó el 15-ago-2026** con el procedimiento entero, no con una
    excepción: licencia provisional, `bench_multi.py ruby` con minitest, y el
    criterio estricto de `bancos/estricto.py` — 4 roturas, **0 fugas**, cascada
    exacta en las 3 medibles (la cuarta cae a la suite entera, que es la caída
    segura) y 50 % de ahorro medio. Los que siguen sin licencia —c, dart,
    elixir, kotlin, scala, swift, tsx— no es que hayan fallado: **no tienen
    banco**, y sin banco no hay nada que medir. Esa distinción importa: un
    lenguaje sin licencia corre la suite entera y es seguro, pero decir que
    "falló" cuando nadie lo probó sería la misma cobertura fingida que la
    matriz de variantes vino a matar.
    """
    return {
        "ag": ag, "extensiones": extensiones, "simbolos": simbolos, "imports": imports,
        "llamada": llamada, "globales": globales, "resolucion": resolucion,
        "sufijos_test": sufijos_test, "dirs_test": dirs_test, "carencias": carencias,
        "tia": tia,
    }


#: `resolucion` dice cómo se convierte el especificador de un import en un módulo
#: del proyecto:
#:   "ruta"    -> `./x`, `../x/y`: se resuelve contra el disco (JS, Ruby, PHP, Lua…)
#:   "paquete" -> `app.util`, `proj/pkg`: se casa por sufijo contra los módulos que
#:                EXISTEN en el árbol. No inventa nada: sin módulo real, no hay arista.
#:   None      -> este lenguaje no tiene resolución fiable; se declara y no se finge.

#: La carencia que comparten los lenguajes que resuelven por paquete y además
#: dejan usar un tipo del MISMO paquete sin nombrarlo: no hay import que leer, así
#: que el grafo de módulos sale a 0 aristas en un proyecto que sí está acoplado.
#: Medido el 18-ago-2026 sobre gb-lenguajes: en `java`, `csharp`, `kotlin` y
#: `scala`, `gb graph` decía «3 módulos, 0 aristas internas» mientras `gb symbols`
#: veía 2 llamadas cruzando de módulo a módulo. El acoplamiento está, y la vista
#: de imports no puede verlo — así que se dice (ADR 0008), no se rellena con
#: aristas inventadas ni se deja pasar por un cero.
MISMO_PAQUETE = ("dos ficheros del mismo paquete se usan SIN import en %s, asi que no dejan "
                 "arista de modulo: 0 aristas aqui NO significa 0 acoplamiento. Las llamadas "
                 "entre ellos si se ven — `gb symbols` las cuenta, y el gate las comprueba")

# La MATRIZ de modificadores de `func` que la sonda de conformidad recorre. Fue
# la lista literal de patrones del motor; desde el 24-sep-2026 swift va por
# regla de kind (ver su entrada) y casa cualquier modificador, asi que la lista
# ya no limita nada: queda como matriz de la sonda, con las formas que la lista
# vieja NO cazaba y el codigo real usa (`mutating` en 41 funciones de
# swift-argument-parser, `class func`, atributos, tres modificadores).
_MODIFICADORES_SWIFT = ("", "private ", "public ", "fileprivate ", "internal ", "open ",
                        "static ", "override ", "private static ", "public static ",
                        "mutating ", "public mutating ", "class ", "@objc ",
                        "@discardableResult public ", "public static override ",
                        "nonisolated ", "package ")

#: Elixir define con MACROS, asi que en el arbol todo es un `call` cuyo destino
#: es la palabra (`def`, `defmodule`, `alias`...). Las alternativas son un
#: `any` de patrones y no una regex a proposito: la regla viaja como argumento
#: y el shim .cmd de npm en Windows se come `^` y `|` — la regex daba 0 matches
#: en silencio.
def _llamada_a(*palabras):
    return {"has": {"field": "target", "any": [{"pattern": p} for p in palabras]}}


_CABEZA_EX = {"kind": "call", "has": {"field": "target", "kind": "identifier",
                                      "pattern": "$NAME"}}
#: La cabeza de `def`: `f(x)`, `f` (aridad cero sin parentesis) o cualquiera de
#: las dos con guarda (`f(x) when is_list(x)`, que es un `binary_operator`).
_DEF_EX = _Regla({"all": [
    {"kind": "call"},
    _llamada_a("def", "defp", "defmacro", "defmacrop", "defguard", "defguardp"),
    {"has": {"kind": "arguments", "has": {"any": [
        {"kind": "identifier", "pattern": "$NAME"},
        _CABEZA_EX,
        {"kind": "binary_operator", "has": {"field": "left", "any": [
            {"kind": "identifier", "pattern": "$NAME"}, _CABEZA_EX]}}]}}}]})
_MODULO_EX = _Regla({"all": [
    {"kind": "call"}, _llamada_a("defmodule", "defprotocol"),
    {"has": {"kind": "arguments", "has": {"kind": "alias", "pattern": "$NAME"}}}]})
_USO_EX = _Regla({"all": [
    {"kind": "call"}, _llamada_a("alias", "import", "require", "use"),
    {"has": {"kind": "arguments", "has": {"nthChild": 1, "pattern": "$SRC"}}}]})

# Una llamada SUELTA (`f()`) solo puede resolver contra una definicion de su
# propia familia: js/ts/tsx se importan entre si y java/kotlin/scala comparten
# la JVM; nadie mas llama a otro lenguaje por nombre pelado. Sin este filtro
# una `detectProjectRoot()` de swift resolvia contra la de java (libreta del
# 6-sep-2026): una arista inventada entre lenguajes, la peor (ADR 0008).
_FAMILIAS = {"js": "js", "ts": "js", "tsx": "js",
             "java": "jvm", "kotlin": "jvm", "scala": "jvm"}


def _familia(lang):
    return _FAMILIAS.get(lang, lang)


LENGUAJES = {
    "js": _lang(
        "js", (".js", ".mjs", ".cjs", ".jsx"),
        (("function", "export function $NAME($$$) { $$$ }"),
         ("function", "function $NAME($$$) { $$$ }"),
         ("function", "export default function $NAME($$$) { $$$ }"),
         ("function", "export const $NAME = ($$$) => { $$$ }"),
         ("function", "const $NAME = ($$$) => { $$$ }"),
         ("function", "export async function $NAME($$$) { $$$ }"),
         ("function", "async function $NAME($$$) { $$$ }"),
         ("class", "export class $NAME { $$$ }"),
         ("class", "class $NAME { $$$ }"),
         # con `extends`/`implements`/genericos: `class Sub extends Base {` no
         # casaba el patron de arriba y la subclase no era simbolo (24-sep-2026)
         ("class", "class $NAME $$$ { $$$ }"))
        + _JS_PROPIEDADES + _metodos_js(("",)),
        _JS_IMPORTS, llamada=LLAMADA + (_NEW,),
        globales=_JS_GLOBALES, resolucion="ruta", tia=True,
        sufijos_test=(".test", ".spec"), dirs_test=("test", "tests", "__tests__", "spec"),
        carencias=_JS_CARENCIAS,
    ),
    "ts": _lang(
        # El `: $RET` NO es opcional en TS: sin el, `export function f(): number`
        # no casa y el lenguaje entero salia con cero simbolos. Lo caza la sonda
        # de conformidad, que es justo para lo que existe.
        "ts", (".ts",),
        (("function", "export function $NAME($$$): $RET { $$$ }"),
         ("function", "function $NAME($$$): $RET { $$$ }"),
         ("function", "export function $NAME($$$) { $$$ }"),
         ("function", "function $NAME($$$) { $$$ }"),
         ("function", "export const $NAME = ($$$) => { $$$ }"),
         ("function", "export async function $NAME($$$): $RET { $$$ }"),
         ("class", "export class $NAME { $$$ }"),
         ("class", "class $NAME { $$$ }"),
         # con `extends`/`implements`/genericos: `class Sub extends Base {` no
         # casaba el patron de arriba y la subclase no era simbolo (24-sep-2026)
         ("class", "class $NAME $$$ { $$$ }"))
        + _JS_PROPIEDADES + _metodos_js(("", ": $RET")),
        _JS_IMPORTS, llamada=LLAMADA + (_NEW,),
        globales=_JS_GLOBALES, resolucion="ruta", tia=True,
        sufijos_test=(".test", ".spec"), dirs_test=("test", "tests", "__tests__", "spec"),
        carencias=_JS_CARENCIAS,
    ),
    "tsx": _lang(
        # Medido sobre react-hot-toast el 24-sep-2026: de 9 componentes y
        # helpers de src/components/*.tsx salia CERO simbolos. Un componente
        # React casi nunca es `export function X`: es `const X: React.FC<P> =
        # (...) => {`, `const X = React.memo((...) => ...)` o una arrow con tipo
        # de retorno — formas que ninguno de los patrones de antes casaba.
        "tsx", (".tsx",),
        (("function", "function $NAME($$$): $RET { $$$ }"),
         ("function", "function $NAME($$$) { $$$ }"),
         ("function", "const $NAME = ($$$) => $E"),
         ("function", "const $NAME = ($$$): $RET => $E"),
         ("function", "const $NAME: $T = ($$$) => $E"),
         ("function", _TSX_ENVUELTOS),
         ("class", "class $NAME $$$ { $$$ }"))
        + _JS_PROPIEDADES + _metodos_js(("", ": $RET")),
        _JS_IMPORTS, llamada=LLAMADA + (_TSX_JSX, _NEW),
        globales=_JS_GLOBALES, resolucion="ruta",
        sufijos_test=(".test", ".spec"), dirs_test=("test", "tests", "__tests__"),
    ),
    "go": _lang(
        "go", (".go",),
        (("function", "func $NAME($$$) $RET { $$$ }"),
         ("function", "func $NAME($$$) { $$$ }"),
         ("class", "type $NAME struct { $$$ }")),
        # con selector: la forma normal de Go agrupa los imports en un bloque,
        # y el patron suelto solo casa el bloque entero, no cada spec.
        (('import "$SRC"', "import_spec"),),
        resolucion="paquete", tia=True,
        sufijos_test=("_test",),
    ),
    "rust": _lang(
        "rust", (".rs",),
        (("function", "pub fn $NAME($$$) -> $RET { $$$ }"),
         ("function", "pub fn $NAME($$$) { $$$ }"),
         ("function", "fn $NAME($$$) -> $RET { $$$ }"),
         ("function", "fn $NAME($$$) { $$$ }"),
         ("class", "pub struct $NAME { $$$ }")),
        ("use $SRC;",),
        llamada=LLAMADA_RUST, resolucion="paquete", tia=True,
        dirs_test=("tests",),
        # Licencia GANADA el 10-ago-2026, y con el criterio duro: 0 falsos verdes
        # y **cascada exacta** en las 7 roturas, 52% de ahorro — el mismo 52% que
        # js y go sobre la misma forma de proyecto, que es la señal de que la
        # cascada esta entera y no de que ahorre mas.
        #
        # Lo que la bloqueaba y como se vio. Con `tia=True` el banco ya daba 0/7
        # ANTES del arreglo, con 64% de ahorro: mas ahorro y aun asi peor, porque
        # el extra venia de perder `tests/informe`. La cascada estaba rota en
        # `informe.linea -> factura.emitir` y el veredicto salia verde solo
        # porque OTROS tests ya estaban rojos. Lo destapo el criterio estricto
        # (`bancos/estricto.py`), que exige que la seleccion CONTENGA todos los
        # rojos en vez de conformarse con que alguno lo este.
        carencias=("una llamada dentro de un macro se ve si es el primer argumento "
                   "(`m!(f(..), ..)`) o el segundo (`m!(x, f(..))`), pero no en "
                   "posiciones mas profundas ni anidada en una expresion: el cuerpo de "
                   "un macro es un arbol de tokens, no una expresion, asi que "
                   "`assert!(f() > 0)` sigue siendo invisible",),
    ),
    "java": _lang(
        # El patron CONTEXTUAL con `$MOD` caza cualquier combinacion de
        # modificadores de una vez (`public static`, `private`, ...). Los tres
        # patrones sueltos que habia antes solo cubrian los que alguien habia
        # pensado, y `public static int f()` se les escapaba.
        #
        # Y aun asi no bastaba: un patron exige la FORMA entera, y en javapoet
        # (banco de repos reales, 24-sep-2026) se escapaban 225 de 816 metodos
        # — 199 por `throws`, el resto genericos (`static <T> T f()`) y sin
        # modificador — y 56 de 87 tipos (`extends`/`implements`, `final class`,
        # `static class` anidada, interfaces, enums). Por KIND no hay forma que
        # olvidar: cada nodo del arbol con su campo `name`.
        "java", (".java",),
        (("class", _regla_con_cuerpo("class_declaration")),
         ("class", _regla_con_cuerpo("interface_declaration")),
         ("class", _regla_con_cuerpo("enum_declaration")),
         ("class", _regla_con_cuerpo("record_declaration")),
         ("method", _regla_con_cuerpo("method_declaration"))),
        # `import static` y `import pkg.*` no casan con `import $SRC;`: la
        # dependencia de `import static com.x.Util.checkNotNull` se perdia.
        ("import $SRC;", "import static $SRC;", "import $SRC.*;", "import static $SRC.*;"),
        llamada=("$FN($$$)", "$A.$FN($$$)", _NEW),
        tia=True, resolucion="paquete",
        sufijos_test=("Test", "Tests"), dirs_test=("test", "tests"),
        carencias=(MISMO_PAQUETE % "Java",),
    ),
    "kotlin": _lang(
        # Por KIND, como Java. Los patrones (`fun $NAME($$$) { $$$ }`) solo
        # cazaban la forma de bloque sin nada delante: en colormath (banco de
        # repos reales, 24-sep-2026) quedaban fuera los cuerpos de expresion
        # (`fun f() = ...`), las funciones de extension (`fun Color.toSRGB()`),
        # `override`/`private`/genericos, y todo `data class`, `sealed class`,
        # `object` e `interface` — 10 185 lineas daban 191 simbolos. La
        # gramatica de kotlin no tiene campos (`name`/`body`), asi que el nombre
        # es el hijo DIRECTO de su kind y el cuerpo, un `function_body`.
        "kotlin", (".kt", ".kts"),
        (("function", _Regla({"all": [{"kind": "function_declaration"},
                                      {"has": {"kind": "simple_identifier", "pattern": "$NAME"}},
                                      {"has": {"kind": "function_body"}}]})),
         ("class", _Regla({"all": [{"kind": "class_declaration"},
                                   {"has": {"kind": "type_identifier", "pattern": "$NAME"}}]})),
         ("class", _Regla({"all": [{"kind": "object_declaration"},
                                   {"has": {"kind": "type_identifier", "pattern": "$NAME"}}]}))),
        ("import $SRC",),
        llamada=("$FN($$$)", "$A.$FN($$$)"),
        resolucion="paquete",
        sufijos_test=("Test",), dirs_test=("test", "tests"),
        carencias=(MISMO_PAQUETE % "Kotlin",),
    ),
    "swift": _lang(
        "swift", (".swift",),
        # Por REGLA de kind, como C#. La gramatica rechaza `$MOD func` como
        # patron (18-sep-2026), y la lista literal de modificadores que lo
        # suplia no llegaba al codigo real: en swift-argument-parser (banco de
        # repos reales, 24-sep-2026) no se veia ni una de las 41 `mutating
        # func`, ni las `func` genericas (`container<K>`), ni 62 de 77 `struct`
        # (bastaba `: Protocolo` o `<T>`), ni un `enum` ni un `protocol`. `class_declaration` cubre
        # class/struct/enum/actor; un `extension` NO es una definicion (su
        # nombre es el del tipo ajeno que extiende), pero sus `func` si salen.
        # Con cuerpo obligatorio: un requisito de protocolo no es codigo.
        (("function", _regla_con_cuerpo("function_declaration")),
         ("class", _Regla({"all": [
             {"any": [{"kind": "class_declaration"}, {"kind": "protocol_declaration"}]},
             {"not": {"has": {"field": "declaration_kind", "regex": "^extension$"}}},
             {"has": {"field": "name", "pattern": "$NAME"}},
             {"has": {"field": "body", "pattern": "$CUERPO"}}]}))),
        # Por kind tambien: `import $SRC` no casaba `@testable import X`,
        # `internal import X`, `@preconcurrency import X` ni `import func X.f`
        # — 54 de los 271 imports de swift-argument-parser.
        (_Regla({"all": [{"kind": "import_declaration"},
                         {"has": {"kind": "identifier", "pattern": "$SRC"}}]}),),
        resolucion="paquete",
        sufijos_test=("Test", "Tests"), dirs_test=("test", "tests"),
        carencias=("`import X` nombra un TARGET de SwiftPM (o un modulo del sistema), nunca "
                   "un fichero: solo deja arista si X es un target del Package.swift y ese "
                   "target tiene UN solo fichero; con varios no hay destino unico",
                   MISMO_PAQUETE % "Swift",
                   "`init`, `subscript` y las propiedades calculadas no son simbolos: sus "
                   "llamadas se cuelgan del tipo que las contiene",),
    ),
    "ruby": _lang(
        # `class $NAME\n $$$\nend` daba ERROR de patron, asi que las clases de
        # Ruby NO se extraian — y la sonda no lo veia porque solo exigia "algun
        # simbolo", y los `def` si salian. Sin cuerpo, casa.
        "ruby", (".rb",),
        (("function", "def $NAME($$$)"),
         ("function", "def $NAME"),
         # sin parentesis a proposito: `def self.port_mapping` (sin argumentos)
         # no casaba `def self.$NAME($$$)` y el metodo no existia; y `def $NAME`
         # lo capturaba con NAME=`self` (addressable, 24-sep-2026).
         ("method", "def self.$NAME"),
         ("class", "class $NAME"),
         ("class", "module $NAME")),
        ("require_relative '$SRC'", 'require_relative "$SRC"', "require_relative($SRC)",
         # `require "gema/x"` NO es relativo al fichero: busca en $LOAD_PATH, que
         # en una gema es `lib/`. Es la forma normal de una gema (addressable no
         # usa ni un require_relative) y sin ella el grafo salia a 0 aristas.
         # Va con su propia resolucion ("carga"): por sufijo, `require "set"` o
         # `require "json"` caerian en un `lib/gema/set.rb` propio — la misma
         # arista inventada que Go y Rust dieron con la stdlib.
         ("require '$SRC'", None, "carga"), ('require "$SRC"', None, "carga"),
         ("require($SRC)", None, "carga")),
        resolucion="ruta-local", tia=True,
        carencias=("una llamada SIN parentesis (`total x` o `iva`) no es un nodo de "
                   "llamada en el AST: es indistinguible de una variable, asi que no "
                   "deja arista. Es idioma corriente en Ruby",),
        sufijos_test=("_test", "_spec"), dirs_test=("test", "tests", "spec"),
    ),
    "php": _lang(
        # PHP real es casi todo clases, y el metodo suelto no parsea: necesita
        # contexto, como en C#. Sin esto solo salian las funciones globales.
        "php", (".php",),
        (("function", "function $NAME($$$) { $$$ }"),
         ("function", "function $NAME($$$): $R { $$$ }"))
        + _clases_php() + _metodos_php(),
        # Las cuatro palabras que incluyen fichero en PHP, cada una con y sin
        # paréntesis (`require 'a.php'` y `require('a.php')` son la misma
        # sentencia). La metavariable va suelta y cubre ambas comillas: aquí
        # solo estaban las simples, el espejo exacto del bug de la familia JS
        # — un repo PHP con comillas dobles no dejaba ni una arista.
        ("require_once $SRC", "require $SRC", "include $SRC", "include_once $SRC",
         "require_once($SRC)", "require($SRC)", "include($SRC)", "include_once($SRC)",
         # `use Vendor\Pkg\Clase;`: la dependencia NORMAL del PHP con composer,
         # y no se leia — league/container (PSR-4, 296 `use` internos) salia
         # con 0 aristas y el gate no podia ver ni un cruce (banco de repos
         # reales, 24-sep-2026). Con selector sale cada clausula, tambien las
         # de `use A, B;`. Se resuelve por el PSR-4 de composer.json.
         ("use $SRC;", "namespace_use_clause")),
        llamada=_LLAMADA_PHP,
        tia=True, resolucion="ruta-local",
        sufijos_test=("Test",), dirs_test=("test", "tests"),
        carencias=(MISMO_PAQUETE % "PHP",
                   "un `use` solo deja arista si el `autoload.psr-4` de composer.json lo "
                   "lleva a un fichero que existe: sin composer.json, con PSR-0/classmap, "
                   "o en `use A\\{B, C}` agrupado, no hay arista (no se adivina)",
                   "de las llamadas a metodo se resuelven `$this->x()`, `self::x()` y "
                   "`static::x()` por ambito (la clase que las contiene) y `Clase::x()` "
                   "por nombre; `$obj->x()`, `parent::x()` y los metodos de trait no"),
    ),
    "lua": _lang(
        # `function M.suma(...)` es LA forma de exportar en Lua (tabla-modulo) y
        # no se cubria: solo salian las globales y las locales.
        "lua", (".lua",),
        (("function", "function $NAME($$$) $$$ end"),
         ("function", "local function $NAME($$$) $$$ end"),
         ("method", "function $T.$NAME($$$) $$$ end"),
         ("method", "function $T:$NAME($$$) $$$ end"),
         # Las mismas funciones escritas como valor: `M.x = function`, `local x =
         # function` y el campo de la tabla que el modulo devuelve (`return { x =
         # function ... }`). En busted eran la mitad del codigo: `busted.utils`
         # y los output handlers salian con cero simbolos (24-sep-2026).
         ("method", "$OBJ.$NAME = function($$$) $$$ end"),
         ("function", "local $NAME = function($$$) $$$ end"),
         ("method", "x = { $NAME = function($$$) $$$ end }", "field")),
        # En Lua las tres formas son la misma llamada. Aquí la metavariable NO
        # va suelta a propósito: `require $SRC` casa también las versiones con
        # paréntesis y captura `("a")` con ellos dentro, que luego no resuelve
        # — arista perdida en silencio. Explícito es más largo y no miente.
        ('require($SRC)', "require '$SRC'", 'require "$SRC"'),
        tia=True, resolucion="paquete",
        sufijos_test=("_test", "_spec"), dirs_test=("test", "tests", "spec"),
    ),
    "scala": _lang(
        # Por KIND y no por patron, como Java y C#: en scala-xml (banco de repos
        # reales, 24-sep-2026) los tres patrones veian 311 de 1020 `def` y 74 de
        # 242 tipos. Se escapaban `def f = x` (sin tipo de retorno), `def f(): T
        # = { ... }`, los `override`/`private[x]`/`final`, TODOS los `trait`,
        # las `case class` sin cuerpo y las clases con `extends`. Un `def` sin
        # cuerpo es otro kind (`function_declaration`), asi que el abstracto no
        # entra; una clase o un trait sin cuerpo SI es una definicion (`case
        # class C(x: Int)` construye), por eso a los tipos no se les exige.
        "scala", (".scala",),
        (("class", _regla_con_nombre("class_definition")),
         ("class", _regla_con_nombre("object_definition")),
         ("class", _regla_con_nombre("trait_definition")),
         ("class", _regla_con_nombre("enum_definition")),
         ("function", _regla_con_cuerpo("function_definition"))),
        # `import $SRC` capturaba SOLO el primer identificador: la gramatica
        # pone cada segmento de `a.b.C` como hijo suelto del import, asi que
        # `import scala.xml.parsing.ConstructingParser` llegaba como `scala` y
        # no resolvia nunca — solo casaban por casualidad los relativos de un
        # segmento (`import Utility.x`). Se toma el import ENTERO y se despliega
        # en nombres cualificados (`a.{B, C => D}`, `a._`, `a.*`, `a.B as C`).
        (_Regla({"all": [{"kind": "import_declaration"}, {"pattern": "$SRC"}]}),),
        llamada=("$FN($$$)", "$A.$FN($$$)"),
        resolucion="paquete",
        sufijos_test=("Test", "Spec"), dirs_test=("test", "tests"),
        carencias=(MISMO_PAQUETE % "Scala",
                   "un import solo deja arista si el fichero vive en la ruta de su "
                   "paquete (`a/b/C.scala` para `a.b.C`): Scala no lo exige, y un "
                   "`object` o tipo declarado en un fichero con otro nombre no se "
                   "encuentra (no se adivina)",
                   "una llamada SIN parentesis (`x.size`, `h`) no es un nodo de "
                   "llamada: es idioma corriente en Scala y no deja arista"),
    ),
    "elixir": _lang(
        # Por REGLA y no por patron (banco de repos reales, jason, 24-sep-2026):
        # `def $NAME($$$)` no casaba la definicion con guarda (`def f(x) when
        # ...`), la de aridad cero sin parentesis (`def project do`), ni
        # `defmacro`; y `defmodule Jason.Decoder` salia con un $NAME con punto
        # que se descartaba. Se veian 224 de 328 funciones y 9 de 30 modulos
        # (solo los de un segmento: `Jason` si, `Jason.Decoder` no).
        "elixir", (".ex", ".exs"),
        (("function", _DEF_EX), ("class", _MODULO_EX)),
        # `alias`/`import`/`require`/`use`, con opciones o sin ellas, y la forma
        # multiple `alias A.{B, C}`: el primer argumento, que `_usos_elixir`
        # resuelve contra los modulos que el arbol DECLARA.
        (_USO_EX,),
        resolucion="paquete",
        sufijos_test=("_test",), dirs_test=("test", "tests"),
    ),
    "csharp": _lang(
        # Los METODOS necesitan patron CONTEXTUAL: el patron trae el `class A {
        # ... }` que la gramatica exige y el selector extrae el nodo real. Suelto,
        # ast-grep parsea `public $RET $NAME(...)` como funcion local de nivel
        # superior y el `$` produce nodos ERROR — por eso los 5 patrones probados
        # a ciegas el 8-ago dieron cero, y por eso C# entro sin grafo de llamadas.
        #
        # Y aun asi un patron casa los modificadores EXACTOS: sobre MediatR
        # (banco de repos reales, 24-sep-2026) faltaban `Mediator`, `IMediator`,
        # `ServiceRegistrar`, `Unit`... y los metodos genericos (`Send<T>`),
        # `=> expr`, `override`, `async`, `internal`, `private static`. De 51
        # tipos se veian 2. Por eso C# va por REGLA de kind: cualquier modificador,
        # base, genericos o cuerpo `=>`. Con cuerpo obligatorio, como en los demas
        # lenguajes: un `abstract` o un miembro de interfaz no es una definicion.
        "csharp", (".cs",),
        (("class", _Regla({"all": [
            {"any": [{"kind": k} for k in ("class_declaration", "struct_declaration",
                                           "interface_declaration", "record_declaration",
                                           "enum_declaration")]},
            {"has": {"field": "name", "pattern": "$NAME"}}]})),
         ("method", _Regla({"all": [
             {"kind": "method_declaration"},
             {"has": {"field": "name", "pattern": "$NAME"}},
             {"has": {"field": "returns", "pattern": "$RET"}},
             {"has": {"field": "body", "any": [{"kind": "block"},
                                               {"kind": "arrow_expression_clause"}]}}]}))),
        ("using $SRC;", "using static $SRC;", "using $A = $SRC;"),
        llamada=LLAMADA + (_NEW,),
        resolucion="paquete", tia=True,
        sufijos_test=("Test", "Tests"), dirs_test=("test", "tests"),
        carencias=(MISMO_PAQUETE % "C#",),
    ),
    "c": _lang(
        "c", (".c", ".h"),
        # Una REGLA y no el patron `$RET $NAME($$$) { $$$ }`: el patron solo casa
        # un tipo de retorno de UN nodo, y se dejaba fuera `static int f(...)`,
        # `char *f(...)`, `inline static ...` y la definicion K&R. En libyaml
        # (banco de repos reales, 24-sep-2026) gb veia 90 funciones de ~228:
        # emitter.c daba 1 de 47, porque casi todo lo interno de una libreria C
        # es `static`. El nombre es el identificador del `function_declarator`,
        # directo o bajo punteros/parentesis (`int (*f(int))(int)`).
        (("function", _Regla({"all": [
            {"kind": "function_definition"},
            {"has": {"field": "declarator", "any": [
                {"kind": "function_declarator",
                 "has": {"field": "declarator", "kind": "identifier", "pattern": "$NAME"}},
                {"has": {"stopBy": "end", "kind": "function_declarator",
                         "has": {"field": "declarator", "kind": "identifier",
                                 "pattern": "$NAME"}}}]}}]})),),
        # Solo la forma LOCAL: `#include <stdio.h>` es una cabecera del sistema y
        # su arista no diria nada del acoplamiento propio.
        ('#include "$SRC"',),
        # En C una llamada suelta es una SENTENCIA, no una expresion, asi que
        # `$FN($$$)` a secas no casa nada (medido 9-ago). Los patrones de
        # sentencia (`$FN($$$);`, `$T $V = $FN($$$);`) dejaban fuera
        # `return f(x);` e `if (!f(x))`, que es COMO se encadena C: en libyaml
        # la maquina de estados entera (`return yaml_parser_parse_stream_start
        # (...)`) no tenia ni un llamante (banco de repos reales, 24-sep-2026).
        # La regla casa el nodo `call_expression` donde este, anidado o no. Solo
        # con un identificador como funcion: `p->handler(x)` es un puntero a
        # funcion y su destino no es un hecho lexico.
        llamada=(_Regla({"kind": "call_expression",
                         "has": {"field": "function", "kind": "identifier",
                                 "pattern": "$FN"}}),),
        resolucion="ruta-local",
        sufijos_test=("_test",), dirs_test=("test", "tests"),
        carencias=("`#include` solo se resuelve junto al fichero: `<yaml.h>` o un "
                   "`\"x.h\"` que el compilador encuentra por `-I` no dejan arista "
                   "(ausente, nunca inventada)",
                   "el preprocesador no se ejecuta: una llamada escrita dentro de una "
                   "macro (`PUSH(...)`) no deja arista, y una macro que el parser no "
                   "entiende puede ocultar la funcion que la sigue (libyaml: "
                   "`yaml_parser_scan`)"),
    ),
    "dart": _lang(
        "dart", (".dart",),
        # REGLAS por kind y no patrones (repos reales, 24-sep-2026): sobre
        # petitparser (7,8k lineas de lib/) salian 10 clases de mas de 100 —
        # `class $NAME { $$$ }` no casa `abstract class P<R> extends B`, ni
        # mixin, ni extension, ni enum — y 13 metodos: ni getters, ni `=>`,
        # ni `static`, ni constructores con cuerpo.
        (("function", _Regla({"all": [
            {"kind": "function_declaration"},
            {"has": {"field": "signature", "has": {"field": "name", "pattern": "$NAME"}}},
            {"has": {"field": "body", "pattern": "$CUERPO"}}]})),
         ("class", _Regla({"all": [
             {"any": [{"kind": k} for k in ("class_declaration", "mixin_declaration",
                                            "extension_declaration", "enum_declaration",
                                            "extension_type_declaration")]},
             {"has": {"field": "name", "pattern": "$NAME"}}]})),
         # metodo, getter, setter; con cuerpo (`{}` o `=>`): el abstracto es
         # un `declaration` sin cuerpo y no se promete, como en Java
         ("method", _Regla({"all": [
             {"kind": "method_declaration"},
             {"has": {"field": "signature", "has": {
                 "any": [{"kind": k} for k in ("function_signature", "getter_signature",
                                               "setter_signature")],
                 "has": {"field": "name", "pattern": "$NAME"}}}},
             {"has": {"field": "body", "pattern": "$CUERPO"}}]})),
         # constructor NOMBRADO con cuerpo (`factory P.of(..) => ..`,
         # `P.named() { .. }`): el nombre es el identificador que sigue al
         # punto (`nthChild` no lo alcanza: medido, 0 casos). El constructor
         # sin nombre se llama como la clase y ya es la clase.
         ("method", _Regla({"all": [
             {"kind": "method_declaration"},
             {"has": {"field": "signature", "has": {
                 "any": [{"kind": "constructor_signature"},
                         {"kind": "factory_constructor_signature"}],
                 "has": {"kind": "identifier", "pattern": "$NAME",
                         "follows": {"pattern": "."}}}}},
             {"has": {"field": "body", "pattern": "$CUERPO"}}]}))),
        # El literal de `import`, `export` y `part` —con `as`/`show`/`hide`
        # detras o sin ellos, comillas simples o dobles—. `import '$SRC';` solo
        # casaba la forma desnuda con comillas simples: en petitparser se
        # perdian los 92 `export` de sus barriles y todo `import ... as x`.
        # `part of` NO: es la vuelta del mismo `part`, y contarla fabricaria un
        # ciclo de dos ficheros que son una sola biblioteca.
        (_Regla({"all": [
            {"kind": "string_literal"}, {"pattern": "$SRC"},
            {"inside": {"kind": "uri", "inside": {"any": [{"kind": "configurable_uri"},
                                                          {"kind": "part_directive"}]}}}]}),),
        # "ruta-local" y no "ruta": en Dart el import relativo se escribe SIN
        # `./` (`import 'a.dart';` es el fichero de al lado), y exigir el punto
        # inicial dejaba a dart con CERO aristas de modulo sobre codigo
        # idiomatico — medido el 11-sep-2026: `'a.dart'` daba 0 y `'./a.dart'`
        # daba 1. Lo que lleva esquema lo decide `_dart_modulo`: `dart:` es el
        # SDK y `package:x/` es interno solo si un pubspec.yaml del arbol se
        # llama `x`.
        llamada=None, resolucion="ruta-local",
        sufijos_test=("_test",), dirs_test=("test", "tests"),
        # Remedido el 24-sep-2026 (ast-grep 0.45.2): el arbol SI expone la
        # invocacion (`call_expression` con su campo `function`); lo que no
        # casaba el 9-ago eran los PATRONES, porque `f(x)` suelto no parsea
        # como llamada en dart. Una regla por kind saca 6119 llamadas en
        # petitparser y resuelve 2951. NO se enciende porque inventa: un
        # parametro de tipo funcion (`predicate(parser)` con `Predicate<Parser>?
        # predicate`) resolvia contra la funcion `predicate` de otro modulo —
        # 7 aristas asi en su lib/, leidas una a una—, y una arista de LLAMADA
        # que cruza una frontera BLOQUEA el gate: seria bloquear sobre algo que
        # no es un hecho. Propuesta medida, fuera de esta tabla: solo `f()`.
        carencias=("las LLAMADAS no se extraen: el arbol las tiene, pero sin ambito "
                   "lexico un parametro de tipo funcion (`predicate(x)`) se confunde con la "
                   "funcion homonima de otro modulo. Hay simbolos y modulos, no grafo de "
                   "llamadas",
                   "`class X;` (clase sin cuerpo, Dart 3.10) no la parsea la gramatica de "
                   "ast-grep 0.45: esa clase no es simbolo",
                   "`part of` no deja arista (es la misma biblioteca que su `part`); el "
                   "import CONDICIONAL (`if (dart.library.io) 'b.dart'`) solo deja la del "
                   "primero",),
    ),
}

#: Lo que NO se declara soportado aunque `ast-grep` lo acepte: sin patrones
#: medidos, incluirlo seria prometer un grafo que no existe.
#:
#: `cpp` estuvo aqui dentro un dia y se SACO (9-ago). Sigue fuera, pero el MOTIVO
#: que decia esta nota era falso y se corrige (remedido el 11-sep-2026 con
#: ast-grep 0.45.2): no es que ningun patron extraiga nada. `class $NAME { $$$ };`
#: con selector `class_specifier` saca la clase con su tramo entero,
#: `#include "$SRC"` deja la arista de modulo e ignora `<vector>`, y
#: `$RET $NAME($$$) { $$$ }` con selector `function_declarator` saca las 6
#: funciones de 6 — metodo, definicion cualificada y plantilla incluidas.
#:
#: Lo que lo deja fuera es mas fino, y es de la TECNICA de patron+selector, no del
#: lenguaje. En C++ un cuerpo `{ $$$ }` es ambiguo con la inicializacion por
#: llaves, asi que el patron entero parsea como declaracion y NUNCA casa un
#: `function_definition` (probadas 5 formas de cuerpo: las que si parsean como
#: definicion —`{ $$$; }`, `{ $$$ $LAST; }`, `{ $$$ return $X; }`— casan 0 de 6
#: sobre codigo multilinea real). Queda `function_declarator`, y arrastra dos
#: defectos MEDIDOS que ningun `carencias` arregla:
#:   1. el tramo acaba en la FIRMA, no en la funcion: `1-1` y `4-4` donde C da
#:      `1-3` y `4-7`. Como `_envuelve` atribuye cada llamada por tramo, el origen
#:      de la arista cae al modulo en vez de a la funcion — `gb calls` se queda
#:      sin llamantes, que es el producto del motor.
#:   2. casa tambien el PROTOTIPO, y en C++ toda cabecera los tiene: `suma`
#:      definido en `util.hpp` y en `a.cpp` son dos candidatos, asi que las 3
#:      llamadas del corpus murieron en `nombre-ambiguo`. En C no pasa porque su
#:      patron si parsea como `function_definition` y el prototipo no casa.
#:
#: Se midio la salida: una regla COMPUESTA (`kind: function_definition` + `has`
#: sobre el declarador) arregla las dos — 6 de 6 con tramo entero y sin
#: prototipos. Pero eso ya no es "una entrada en la tabla": pide que el motor
#: acepte reglas y no solo patron+selector, y `run -p` no sabe expresarlas, con lo
#: que el camino de respaldo divergiria del lote. Es decision de arquitectura, no
#: de catalogo. Hasta entonces, fuera de la tabla gb dice "veo C++ y no lo leo",
#: que sigue siendo la verdad — y entrar con el tramo roto seria peor que ausente:
#: el aviso de frontera dejaria de saltar y el usuario veria un grafo mutilado sin
#: que nadie le dijera por que.
SIN_SOPORTE = ("html", "css", "json", "yaml", "bash", "haskell", "nix", "solidity", "cpp")

#: Directorios que nunca son código del proyecto, en ningún lenguaje.
SKIP = frozenset(("node_modules", "dist", "build", "coverage", ".next", "out", "vendor",
                  "target", "bin", "obj", "_build", "deps", "Pods", "__pycache__"))

#: Extensión -> id de lenguaje. Derivado de la tabla: una sola fuente.
POR_EXTENSION = {ext: nombre for nombre, cfg in LENGUAJES.items() for ext in cfg["extensiones"]}


def lenguaje_de(ruta):
    return POR_EXTENSION.get(os.path.splitext(ruta)[1].lower())


def carencias_de(ids):
    """Lo que los lenguajes presentes NO pueden hacer, para poder decirlo."""
    fuera = []
    for i in sorted(set(ids)):
        for texto in LENGUAJES[i]["carencias"]:
            fuera.append("%s: %s" % (i, texto))
    return fuera


# --- el binario: detectar, y verificar EJECUTANDO (regla 7) ------------------


def binario():
    """Ruta del ejecutable de ast-grep, o None.

    `shutil.which` y no confiar en el PATH del shell: en Windows ast-grep es un
    shim `.CMD` de npm y `subprocess(["ast-grep", ...])` da WinError 2 aunque en
    la terminal funcione. Es el 'instalado != funcional' de la regla 7, y se
    reprodujo el 8-ago montando el primer proyecto JS.

    Y lo encontrado se VERIFICA ejecutandolo, se llame como se llame. El
    primer CI en ubuntu (15-ago) cazo DOS impostores el mismo dia: el `sg`
    de Debian que es setgroups (shadow-utils), y en WSL el shim npm de
    Windows llamado `ast-grep` que hereda el PATH y muere en `exec: node:
    not found`. En ambos la deteccion por nombre decia si, la extraccion
    devolvia vacio y las sondas de conformidad se ponian rojas — su trabajo
    exacto. Un nombre en el PATH no es una herramienta.
    """
    for nombre in ("ast-grep", "sg"):
        ruta = shutil.which(nombre)
        if ruta and _es_astgrep(ruta):
            return ruta
    return None


#: memo por ruta: la verificacion es un subprocess y binario() esta en guards.
_ES_ASTGREP = {}


def _es_astgrep(ruta):
    """True si `ruta` responde a --version como un ast-grep de verdad."""
    if ruta not in _ES_ASTGREP:
        try:
            p = subprocess.run([ruta, "--version"], capture_output=True, timeout=20)
            _ES_ASTGREP[ruta] = (p.returncode == 0
                                 and b"ast-grep" in p.stdout.lower())
        except (OSError, subprocess.SubprocessError):
            _ES_ASTGREP[ruta] = False
    return _ES_ASTGREP[ruta]


def disponible():
    """(ruta, version) si el binario responde de verdad, o (None, motivo).

    Detectarlo no basta: se ejecuta. Un shim roto o un binario de otra
    arquitectura existen en el PATH y no sirven.
    """
    ruta = binario()
    if not ruta:
        return None, "ast-grep no esta instalado (https://ast-grep.github.io)"
    try:
        p = subprocess.run([ruta, "--version"], capture_output=True, timeout=20)
    except (OSError, subprocess.SubprocessError) as error:
        return None, "ast-grep esta en el PATH pero no ejecuta: %s" % error
    if p.returncode != 0:
        return None, "ast-grep responde con error al invocarlo"
    return ruta, p.stdout.decode("utf-8", "replace").strip()


#: Patrones que el modo regla de ast-grep RECHAZA aunque `run` los trague: los
#: snippets de ruby sin cuerpo (`def $NAME`) no dejan inferir un kind — medido
#: el 8-sep-2026, 3 rechazos de 47. Van por `run` como siempre; UNO de estos
#: colandose en el lote lo envenenaria ENTERO (el scan no dice que regla fallo
#: y todo caeria al fallback lento). La sonda del lote vigila esa regresion.
_SOLO_RUN = frozenset(("def $NAME", "def self.$NAME", "class $NAME", "module $NAME"))


def _regla_yaml(rid, lenguaje, patron, selector):
    """Un patrón de la tabla como documento de regla para `scan`. Bloque
    literal (`|-`) para que comillas y llaves del patrón no peleen con YAML."""
    if isinstance(patron, _Regla):
        return '{"id": %s, "language": %s, "rule": %s}' % (
            json.dumps(rid), json.dumps(lenguaje), patron)
    sangrado = "\n".join("      " + l for l in patron.splitlines())
    if selector:
        return ("id: %s\nlanguage: %s\nrule:\n  pattern:\n    context: |-\n%s\n"
                "    selector: %s" % (rid, lenguaje, sangrado, selector))
    return "id: %s\nlanguage: %s\nrule:\n  pattern: |-\n%s" % (
        rid, lenguaje, "\n".join("    " + l for l in patron.splitlines()))


def _lote_estructural(ruta, presentes, root):
    """UN proceso de ast-grep para TODOS los patrones estructurales (símbolos y
    llamadas) de todos los lenguajes presentes: {(lang_ag, patron, selector):
    [matches]}, o None si el scan no pudo — y entonces todo cae a la vía de
    siempre, un `run` por patrón, sin perder nada.

    Por qué existe: el barrido eran ~75 arranques de proceso por pasada a
    ~110 ms de arranque cada uno en Windows — 8 de los 10,7 s del gate eran
    CPU arrancando procesos, no analizando (perfilado el 6-sep-2026, deuda de
    la regla 2). `scan --inline-rules` emite la MISMA forma JSON que `run`
    (metaVariables, range, file — verificado con ast-grep 0.45) más el ruleId
    que ata cada match a su patrón.

    Los IMPORTS no entran a propósito: sus patrones están certificados por la
    matriz de variantes en modo `run` y el modo regla ni siquiera los parsea
    (`from $SRC` con la metavariable en posición de string). Migrar el patrón
    certificado a otro modo de parseo es exactamente donde un falso verde
    vivió meses; se quedan donde se midieron.
    """
    trabajos = {}
    docs = []
    for lang in presentes:
        cfg = LENGUAJES[lang]
        # `or ()`: hay lenguajes con la familia entera a None (dart no tiene
        # patron de llamada — carencia declarada) y el bucle consumidor ya lo
        # guarda; el lote tiene que guardarlo igual.
        entradas = [(e[1], e[2] if len(e) > 2 else None) for e in (cfg["simbolos"] or ())]
        # una llamada es `patron` o `(patron, selector)`: la de metodo de PHP
        # solo parsea con contexto, como los metodos de C#
        entradas += [p if isinstance(p, tuple) else (p, None) for p in (cfg["llamada"] or ())]
        for patron, selector in entradas:
            if patron in _SOLO_RUN:
                continue
            clave = (cfg["ag"], patron, selector)
            if clave in trabajos:
                continue
            rid = "r%d" % len(trabajos)
            trabajos[clave] = rid
            docs.append(_regla_yaml(rid, cfg["ag"], patron, selector))
    if not trabajos:
        return {}
    # Por FICHERO y no por --inline-rules, a proposito: en Windows ast-grep
    # llega como shim .cmd de npm, y ese shim destroza un argumento con saltos
    # de linea — a ast-grep le llegaba solo la primera linea del YAML y el lote
    # entero moria con "missing field language" (medido el 8-sep-2026). Los
    # argumentos de `run` sobreviven porque son de una linea.
    import tempfile

    try:
        fd, tmp = tempfile.mkstemp(suffix=".yml", prefix="gb-lote-", text=True)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write("\n---\n".join(docs))
    except OSError:
        return None
    try:
        p = subprocess.run(
            [ruta, "scan", "--rule", tmp, "--json=compact", root],
            capture_output=True, timeout=300,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
    if p.returncode != 0:
        # Una regla que el scan no traga envenena el lote entero y no dice
        # cual: no se adivina, se vuelve a la via medida.
        return None
    try:
        datos = json.loads(p.stdout.decode("utf-8", "replace").strip() or "[]")
    except ValueError:
        return None
    if not isinstance(datos, list):
        return None
    por_rid = {}
    for m in datos:
        por_rid.setdefault(m.get("ruleId"), []).append(m)
    # TODAS las claves presentes, con [] para las que no casaron nada: "sin
    # matches" y "no estaba en el lote" no pueden confundirse, o cada patron
    # sin resultados pagaria un proceso de respaldo que no compra nada.
    return {clave: por_rid.get(rid, []) for clave, rid in trabajos.items()}


def _corre(ruta, patron, lenguaje, raiz, selector=None, lote=None):
    """Una pasada de ast-grep, ya parseada. Lista vacía si algo falla: un patrón
    que no casa nada y un patrón mal escrito dan lo mismo aquí, y por eso los
    contadores del informe declaran cuánto se vio — no se infiere.

    `selector` habilita los patrones CONTEXTUALES: el patrón trae el contexto que
    la gramática necesita para parsear (`class A { ... }`) y el selector dice qué
    sub-nodo es el que de verdad se busca (`method_declaration`). Sin esto, un
    método de C# no se puede expresar: suelto, ast-grep lo parsea como función
    local de nivel superior y el `$` de la metavariable produce nodos ERROR —
    que es por lo que C# entró en la tabla sin metodos y sin grafo de llamadas.

    `lote` es el prefetch de `_lote_estructural`: si el patrón está ahí, ya no
    hay proceso que arrancar. Si no está (imports, o un scan que fallo), la vía
    de siempre.
    """
    if lote is not None:
        precalculado = lote.get((lenguaje, patron, selector))
        if precalculado is not None:
            return precalculado
    orden = [ruta, "run", "-p", patron, "-l", lenguaje, "--json=compact"]
    if isinstance(patron, _Regla):
        # una linea de JSON: el shim .cmd de Windows solo rompe los saltos
        orden = [ruta, "scan", "--inline-rules", _regla_yaml("r", lenguaje, patron, None),
                 "--json=compact"]
    elif selector:
        orden += ["--selector", selector]
    try:
        p = subprocess.run(
            orden + [raiz], capture_output=True, timeout=180,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    salida = p.stdout.decode("utf-8", "replace").strip()
    if not salida:
        return []
    try:
        datos = json.loads(salida)
    except ValueError:
        return []
    return datos if isinstance(datos, list) else []


def _meta(match, nombre):
    return (match.get("metaVariables", {}).get("single", {}).get(nombre, {}) or {}).get("text")


def _sin_comillas(texto):
    """El literal de un import sin sus comillas, o el texto tal cual.

    Cuando la metavariable va SUELTA en el patrón (`from $SRC` en vez de
    `from "$SRC"`) casa las dos comillas del ecosistema, pero captura el
    literal entero — comillas incluidas. Aquí se quitan una sola vez y solo
    si abren y cierran igual: un import que de verdad se llame `'raro` (no
    existe, pero adivinar es peor) se queda como está.
    """
    if texto and len(texto) >= 2 and texto[0] == texto[-1] and texto[0] in "\"'`":
        return texto[1:-1]
    return texto


def _linea(match):
    return match.get("range", {}).get("start", {}).get("line", 0) + 1


def _fin(match):
    """Última línea del símbolo. NO es cosmética: sin ella la selección de tests
    no puede decidir si un hunk del diff cae DENTRO de una función, se queda sin
    semillas y cae a "corre la suite entera" — seguro, pero con 0 % de ahorro.
    Medido en el banco de JS antes de ponerla: 7 de 7 roturas caían a todo."""
    return match.get("range", {}).get("end", {}).get("line", 0) + 1


# --- ficheros, módulos y tests ----------------------------------------------


def es_fichero_de_test(ruta, raiz, cfg):
    """¿Este fichero lo colecciona el runner del lenguaje?

    Mismo criterio que la vía Python y por el mismo motivo: seleccionar algo que
    el runner NO colecciona devuelve "no tests ran", que en un gate se lee igual
    de verde que "todo pasó".
    """
    rel = os.path.relpath(ruta, raiz).replace("\\", "/")
    base = os.path.splitext(os.path.basename(rel))[0]
    if cfg["sufijos_test"] and base.endswith(tuple(cfg["sufijos_test"])):
        return True
    partes = os.path.dirname(rel).split("/")
    return any(p in cfg["dirs_test"] for p in partes)


def module_name(ruta, raiz):
    """Nombre punteado de un fichero, con el mismo criterio que la vía Python:
    relativo a la raíz, sin extensión, descontando `src/` para que
    `src/carrito.js` sea `carrito` y no `src.carrito`."""
    rel = os.path.relpath(ruta, raiz).replace("\\", "/")
    partes = [p for p in rel.split("/") if p and p != "."]
    if partes and partes[0] == "src":
        partes = partes[1:]
    if not partes:
        return ""
    partes[-1] = os.path.splitext(partes[-1])[0]
    if partes[-1] in ("index", "mod", "__init__") and len(partes) > 1:
        # `src/index.tsx` se queda como `index`: quitarle el nombre lo dejaba en
        # "" y el fichero ENTERO desaparecia del grafo — en vaul, el Drawer
        # (1148 lineas, todo el componente); en react-hot-toast, el barril al
        # que apuntan los tests con `from '../src'` (medido el 24-sep-2026).
        partes = partes[:-1]
    return ".".join(partes)


def _via(ruta):
    return os.path.normcase(os.path.normpath(os.path.realpath(ruta)))


def _raiz_ignorada(raiz):
    """¿La raíz es código AJENO para el único repo que la gobierna?

    Dos preguntas, en este orden, porque la segunda sin la primera se equivoca:

    1. ¿De quién es la raíz? Si tiene repo propio (el toplevel es ella misma o
       algo dentro), sus reglas mandan y aquí no se toca nada — que un repo de
       más arriba la ignore no es asunto suyo.
    2. Solo si manda un repo de MÁS ARRIBA: ¿ese repo la ignora? Entonces sus
       reglas no describen este proyecto, y aplicarlas hacia dentro borra el
       grafo entero.

    Se pregunta desde el padre: dentro de la raíz, git resolvería la ruta contra
    el mismo directorio y la respuesta no querría decir lo mismo. Sin git, o si
    algo falla, se responde que no: el filtro sigue como estaba y a lo sumo se
    informa de más.
    """
    raiz_abs = os.path.abspath(raiz)
    padre = os.path.dirname(raiz_abs)
    if not padre or padre == raiz_abs:
        return False
    try:
        p = subprocess.run(
            ["git", "-C", raiz_abs, "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=20,
        )
        if p.returncode != 0:
            return False
        toplevel = _via(p.stdout.strip())
        # Repo propio (o anidado dentro): las reglas de la raíz son las suyas.
        if toplevel == _via(raiz_abs) or toplevel.startswith(_via(raiz_abs) + os.sep):
            return False
        q = subprocess.run(
            ["git", "-C", padre, "check-ignore", "-q", raiz_abs],
            capture_output=True, text=True, timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return q.returncode == 0


def _ignorados_por_git(raiz, rutas):
    """Los de `rutas` que el repo ya ignora, preguntándoselo a git UNA vez.

    `SKIP` es una lista fija y por tanto siempre incompleta: acierta con
    `node_modules` y falla con lo que cada repo decida (`target/`, `_build/`, un
    directorio de temporales). Lo que un proyecto considera "no es mi código" ya
    está escrito en su `.gitignore`, así que se lee de ahí en vez de adivinarlo —
    y así no hay que cablear ningún nombre concreto (regla 6).

    Un solo proceso con `--stdin`: preguntar fichero a fichero convertiría un
    barrido barato en cientos de procesos, contra el presupuesto de la regla 2.
    Si no hay git, o falla, no se filtra nada: quedarse corto es informar de más,
    que es recuperable; pasarse sería esconder código sin decirlo.

    Y si la RAÍZ está ella misma ignorada, no se filtra nada: `git -C` escala
    hasta el repo que la contenga, así que analizar un proyecto dentro de un
    directorio que el repo padre ignora (`tmp*/`, `vendor/`, el `pytest-of-*/`
    de la suite) borraba el grafo entero y lo devolvía VACÍO Y EN VERDE — el
    falso verde de la ADR 0010 otra vez, y con él 124 tests mudos. Si el repo
    padre dice "esto no es mi código", sus reglas tampoco son la ley dentro.
    """
    if not rutas:
        return set()
    if _raiz_ignorada(raiz):
        return set()
    # `-z` en las DOS direcciones. Sin el, git aplica `core.quotepath` y en
    # Windows devuelve `"generado\generado.ts"` —con comillas literales y \r—
    # porque la barra invertida le parece un caracter especial. Ninguna ruta
    # casaba y el filtro no quitaba nada... sin fallar: el peor modo de fallo.
    entrada = "\0".join(
        os.path.relpath(r, raiz).replace(os.sep, "/") for r in rutas)
    try:
        p = subprocess.run(
            ["git", "-C", raiz, "check-ignore", "-z", "--stdin"],
            input=entrada, capture_output=True, text=True, timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return set()
    if p.returncode not in (0, 1):   # 1 = ninguno ignorado; >1 = no es repo git
        return set()
    return {os.path.normpath(os.path.join(raiz, trozo))
            for trozo in p.stdout.split("\0") if trozo.strip()}


def _ficheros(raiz):
    """[(ruta, id_de_lenguaje)] del código que este motor sabe mirar."""
    fuera = []
    for dirpath, dirnames, filenames in os.walk(raiz):
        dirnames[:] = [d for d in dirnames if d not in SKIP and not d.startswith(".")]
        for name in filenames:
            if name.endswith(".d.ts"):
                continue
            lang = lenguaje_de(name)
            if lang:
                fuera.append((os.path.join(dirpath, name), lang))
    ignorados = _ignorados_por_git(raiz, [r for r, _ in fuera])
    if ignorados:
        fuera = [(r, l) for r, l in fuera if os.path.normpath(r) not in ignorados]
    return fuera


def hay_codigo(raiz):
    """¿Hay algo que este motor pueda mirar? Barato, sin invocar el binario."""
    return bool(_ficheros(raiz))


def _por_cualificado(llamado, definidos, por_modulo):
    """Los símbolos que pueden ser el destino de `prefijo.Nombre()`, o None.

    `None` significa "esto no es una llamada cualificada que yo pueda tratar" —
    `obj.metodo()`, `f()()`, `a[b]()`— y se cuenta como techo. Una lista vacía
    significa que sí lo parecía y no casó con nada real, que también es techo.

    La regla es la misma que la de los imports: el prefijo tiene que coincidir
    con el ÚLTIMO segmento de un módulo que existe. `iva.Iva()` resuelve a
    `iva.Iva` si hay un módulo `iva` (o `a.b.iva`) que define `Iva`. En Go, Java,
    C#, Kotlin y Scala esa es la forma normal de llamar fuera del módulo propio;
    en JS o Python el mismo texto suele ser una variable, y por eso no casa con
    ningún módulo y se queda en el techo, que es donde debe quedarse.
    """
    # `::` de Rust/C++ y `.` de Go/Java/C# son la misma idea: una ruta hasta el
    # simbolo. Se normaliza y se toman los DOS ultimos segmentos — el ultimo es
    # el simbolo y el anterior su modulo. Antes se exigia exactamente un punto,
    # asi que `crate::carrito::total(x)` no se resolvia y la llamada quedaba
    # invisible: ni import ni arista, y la frontera `iva -/-> carrito` no la veia
    # NADIE. Medido en una tirada real (9-ago), donde un agente la escribio asi.
    partes = [p for p in llamado.replace("::", ".").split(".") if p]
    if len(partes) < 2:
        return None
    prefijo, nombre = partes[-2], partes[-1]
    if not prefijo.isidentifier() or not nombre.isidentifier():
        return None
    posibles = definidos.get(nombre)
    if not posibles:
        return None
    exactos = [q for q in posibles if por_modulo.get(q, "").split(".")[-1] == prefijo]
    if exactos:
        return exactos
    # El prefijo puede ser el PAQUETE y no el fichero. En Go un paquete es un
    # DIRECTORIO: `nucleo/a.go` da el modulo `nucleo.a`, y la llamada normal
    # entre paquetes se escribe `nucleo.Suma(x)` — el prefijo casa con el
    # directorio, nunca con el ultimo segmento, asi que la regla estricta la
    # dejaba sin resolver (medido el 11-sep-2026: el import SI salia y la
    # llamada NO, con lo que el grafo decia que b depende de nucleo sin poder
    # decir en que). Es el mismo criterio que usan los imports para lo mismo
    # (`_resuelve`, modo paquete): se acepta el prefijo como segmento del
    # camino del modulo, y si sale mas de un candidato quien llama lo cuenta
    # como `nombre-ambiguo` y no inventa ninguna arista.
    por_paquete = [q for q in posibles if prefijo in por_modulo.get(q, "").split(".")]
    if por_paquete:
        return por_paquete
    # Ultimo recurso, sin distinguir mayusculas — el MISMO que ya hacen los
    # imports (`_resuelve`, modo paquete) y por la misma razon: en Elixir el
    # modulo es `A` y su fichero `a.ex`, asi que `A.suma(x)` nunca casaba contra
    # el modulo `a` y la unica llamada entre modulos de Elixir se contaba como
    # `atributo-de-variable`. Que las dos vias resuelvan igual no es simetria
    # cosmetica: un import que sale y una llamada que no deja un grafo que dice
    # "b depende de a" sin poder decir en que.
    bajo = prefijo.lower()
    return [q for q in posibles
            if bajo in [p.lower() for p in por_modulo.get(q, "").split(".")]]


def _firma_de(texto, nombre):
    """Los parametros tal como se escriben: el primer parentesis equilibrado que
    sigue al nombre, con el espacio normalizado. "" si no hay (Ruby sin
    parentesis, una clase). Sintaxis, no semantica: basta para comparar la
    firma vieja con la nueva, que es para lo que existe (`check`)."""
    i = texto.find(nombre)
    if i < 0:
        return ""
    j = texto.find("(", i + len(nombre))
    if j < 0 or "{" in texto[i:j] or "\n" in texto[i + len(nombre):j].strip("\n "):
        return ""
    nivel = 0
    for k in range(j, min(len(texto), j + 2000)):
        c = texto[k]
        if c in "([":
            nivel += 1
        elif c in ")]":
            nivel -= 1
            if nivel == 0:
                return re.sub(r"\s+", " ", texto[j:k + 1])
    return ""


_CLAVES_HERENCIA = ("extends", "implements", "with", "where")


def _bases_de(cabecera, lang):
    """Los nombres de las BASES que escribe la cabecera de una clase.

    Sintaxis, no semantica: `extends`/`implements`/`with` (Java, TS, JS, PHP,
    Dart, Scala), `:` (Kotlin, C#, Swift), `<` (Ruby). Antes se quitan los
    genericos y los parentesis (`class A(val x: Int) : B()` en Kotlin). Solo el
    ultimo segmento de un nombre cualificado: se resuelve por nombre de clase.
    """
    h = cabecera.split("{", 1)[0]
    if lang == "ruby":
        m = re.search(r"\bclass\s+[\w:]+\s*<\s*([\w:.]+)", h.split("\n", 1)[0])
        return [m.group(1)] if m else []
    previo = None
    while previo != h:
        previo = h
        h = re.sub(r"<[^<>]*>", "", h)
        h = re.sub(r"\([^()]*\)", "", h)
    kw = re.search(r"\b(extends|implements|with)\b", h)
    if kw:
        cola = h[kw.start():]
    elif ":" in h and lang in ("kotlin", "csharp", "swift"):
        cola = h.split(":", 1)[1]
    else:
        return []
    cola = re.split(r"\bwhere\b", cola)[0]
    return [n for n in re.findall(r"[A-Za-z_][\w.$]*", cola) if n not in _CLAVES_HERENCIA]


def _dueno_y_herencia(informe, cabeceras, definidos, por_modulo, lengua_de):
    """`owner` de cada metodo y aristas EXTENDS, con los hechos del arbol.

    Solo Python los tenia, y con ellos la seleccion sube de un metodo de la
    base a quien usa la subclase (`impacted._enlaza_herencia`). Aqui: el dueño
    es la clase MAS PEQUEÑA que contiene al metodo en su fichero; una base es
    arista solo si casa con UNA clase del arbol de la misma familia (la del
    propio modulo primero). Una base de fuera (`extends Exception`) o ambigua no
    inventa nada: se cuenta en `unresolved["base-sin-resolver"]`.
    """
    nodos = informe["nodes"]
    clases_por_fichero = {}
    es_clase = set()
    for n in nodos:
        if n["kind"] == "class" and n.get("end"):
            clases_por_fichero.setdefault(n["file"], []).append(n)
            es_clase.add(n["qual"])
    for n in nodos:
        if n["kind"] not in ("method", "function") or n.get("owner"):
            continue
        dentro = [c for c in clases_por_fichero.get(n["file"], ())
                  if c["line"] <= n["line"] <= c["end"] and c["qual"] != n["qual"]]
        if dentro:
            n["owner"] = min(dentro, key=lambda c: c["end"] - c["line"])["qual"]
            # En Kotlin, Swift, Scala o Ruby la regla es `fun`/`func`/`def` sin
            # distinguir: dentro de una clase ES un metodo (como en Python).
            n["kind"] = "method"
    sin = 0
    for qual, cabecera in cabeceras.items():
        lang = lengua_de.get(qual)
        for escrita in _bases_de(cabecera, lang):
            partes = [p for p in re.split(r"[.:]+", escrita) if p]
            if not partes:
                continue
            base = partes[-1]
            candidatos = [q for q in definidos.get(base, ()) if q in es_clase and q != qual]
            candidatos = _misma_familia(candidatos, lang, lengua_de)
            propios = [q for q in candidatos if por_modulo.get(q) == por_modulo.get(qual)]
            # Una base CUALIFICADA (`Addressable::URI`, `a.b.C`) dice que no es
            # la del propio modulo: en addressable, preferir la local casaba
            # `CustomURIClass < Addressable::URI` con el `Fake::URI` del spec,
            # una arista inventada (24-sep-2026). Entonces solo vale si es unica.
            if len(propios) == 1 and len(partes) == 1:
                candidatos = propios
            if len(candidatos) != 1:
                sin += 1
                continue
            informe["edges"].append([qual, candidatos[0], "EXTENDS"])
    if sin:
        informe.setdefault("unresolved", {})["base-sin-resolver"] = sin


def _misma_familia(candidatos, lang, lengua_de):
    """Deja solo los candidatos que un fichero de `lang` puede llamar por nombre."""
    mia = _familia(lang)
    return [q for q in candidatos if _familia(lengua_de.get(q, lang)) == mia]


_GO_MOD = {}
_PUBSPEC = {}


def _pubspec_nombre(carpeta):
    """El `name:` del pubspec.yaml de `carpeta`, o None. Cacheado por carpeta
    y mtime: el watch re-lee solo si el fichero cambia."""
    ruta = os.path.join(carpeta, "pubspec.yaml")
    try:
        firma = (ruta, os.path.getmtime(ruta))
    except OSError:
        return None
    if firma not in _PUBSPEC:
        try:
            with open(ruta, encoding="utf-8", errors="replace") as fh:
                m = re.search(r"^name:\s*['\"]?([\w.]+)", fh.read(), re.M)
        except OSError:
            m = None
        _PUBSPEC[firma] = m.group(1) if m else None
    return _PUBSPEC[firma]


def _dart_modulo(especificador, fichero, raiz, modulos):
    """El modulo interno de un `import`/`export`/`part` de Dart, o None.

    La regla EXACTA, como go.mod en Go: `dart:x` es el SDK; `package:x/r.dart`
    es `<paquete x>/lib/r.dart`, y el paquete `x` es el que DECLARA un
    pubspec.yaml con `name: x` — si ninguno del arbol lo declara, es de pub y
    no hay arista. Lo que no lleva esquema es una ruta relativa al fichero.

    El `package:` PROPIO es la forma idiomatica de los tests y de los ejemplos
    (`import 'package:petitparser/petitparser.dart'`) y de mucho `lib/`; con la
    resolucion por ruta no dejaba NINGUNA arista — en petitparser 54 de 646
    (banco de repos reales, 24-sep-2026). Un pubspec por paquete, asi que un
    monorepo (o un `example/` con su pubspec) resuelve cada nombre al suyo.
    """
    if especificador.startswith("package:"):
        nombre, _, resto = especificador[len("package:"):].partition("/")
        if not resto:
            return None
        cola = os.path.normcase(os.path.join("lib", *resto.split("/")))
        candidatos = []
        for modulo, ruta in modulos.items():
            ruta = os.path.abspath(ruta)
            if not os.path.normcase(ruta).endswith(os.sep + cola):
                continue
            paquete = ruta[:len(ruta) - len(cola)].rstrip("\\/")
            if _pubspec_nombre(paquete) == nombre:
                candidatos.append(modulo)
        return candidatos[0] if len(candidatos) == 1 else None
    if ":" in especificador or especificador.startswith("/"):
        return None          # `dart:`, `file:`, `http:`... o absoluta: no es del arbol
    destino = os.path.normpath(os.path.join(os.path.dirname(fichero), especificador))
    modulo = module_name(destino, raiz)
    if modulo in modulos and (os.path.normcase(os.path.abspath(modulos[modulo]))
                              == os.path.normcase(destino)):
        return modulo
    return None

#: Un `use` de PHP: `[function|const ]Nombre\De\Clase[ as Alias]`. Sin `/` ni
#: `.`, que es lo que distingue un nombre de clase de la ruta de un `require`.
_PHP_NOMBRE = re.compile(r"^(?:(?:function|const)\s+)?\\?[A-Za-z_]\w*(?:\\\w+)*(?:\s+as\s+\w+)?$")
_COMPOSER = {}


def _php_autoload(fichero, raiz):
    """[(prefijo, carpeta_abs)] del `autoload(-dev).psr-4` del composer.json que
    gobierna `fichero` (subiendo hasta `raiz`), del prefijo mas largo al mas
    corto; [] si no hay."""
    carpeta = os.path.dirname(os.path.abspath(fichero))
    tope = os.path.abspath(raiz)
    while True:
        if carpeta in _COMPOSER:
            return _COMPOSER[carpeta]
        ruta = os.path.join(carpeta, "composer.json")
        if os.path.isfile(ruta):
            mapa = []
            try:
                with open(ruta, encoding="utf-8", errors="replace") as fh:
                    datos = json.load(fh)
            except (OSError, ValueError):
                datos = {}
            for seccion in ("autoload", "autoload-dev"):
                psr4 = (datos.get(seccion) or {}).get("psr-4") or {}
                for prefijo, dirs in psr4.items():
                    for d in ([dirs] if isinstance(dirs, str) else dirs or []):
                        mapa.append((prefijo, os.path.normpath(os.path.join(carpeta, d))))
            _COMPOSER[carpeta] = sorted(mapa, key=lambda x: -len(x[0]))
            return _COMPOSER[carpeta]
        padre = os.path.dirname(carpeta)
        if carpeta == tope or padre == carpeta:
            return []
        carpeta = padre


def _php_psr4(especificador, fichero, raiz, modulos):
    """El modulo de la clase que nombra un `use`, por PSR-4, o None (externa,
    funcion/constante, o sin composer.json: no se adivina)."""
    nombre = re.sub(r"\s+as\s+\w+$", "", especificador.strip())
    if nombre.startswith(("function ", "const ")):
        return None                # viven en ficheros `files`, no en PSR-4
    nombre = nombre.lstrip("\\")
    for prefijo, carpeta in _php_autoload(fichero, raiz):
        if not nombre.startswith(prefijo):
            continue
        cand = os.path.join(carpeta, *nombre[len(prefijo):].split("\\")) + ".php"
        modulo = module_name(cand, raiz)
        if os.path.isfile(cand) and modulo in modulos:
            return modulo
    return None


def _go_modulo(fichero, raiz):
    """El `module` del go.mod que gobierna `fichero` (subiendo hasta `raiz`), o
    None si no hay: entonces se resuelve como siempre."""
    carpeta = os.path.dirname(os.path.abspath(fichero))
    tope = os.path.abspath(raiz)
    while True:
        if carpeta in _GO_MOD:
            return _GO_MOD[carpeta]
        gomod = os.path.join(carpeta, "go.mod")
        if os.path.isfile(gomod):
            try:
                with open(gomod, encoding="utf-8", errors="replace") as fh:
                    m = re.search(r"^module\s+(\S+)", fh.read(), re.M)
            except OSError:
                m = None
            _GO_MOD[carpeta] = m.group(1).strip('"') if m else None
            return _GO_MOD[carpeta]
        padre = os.path.dirname(carpeta)
        if carpeta == tope or padre == carpeta:
            return None
        carpeta = padre


_LUA_ROCAS = {}
_LUA_NOMBRE = re.compile(r"[\w\-]+(?:\.[\w\-]+)*$")
_LUA_ENTRADA = re.compile(r"""\[\s*["']([\w.\-]+)["']\s*\]\s*=\s*["']([^"']+\.lua)["']""")


def _lua_rocas(raiz):
    """{nombre de require -> modulo} que declaran los `.rockspec` del arbol
    (`build.modules`). Es la regla exacta de Lua, como go.mod en Go: luarocks
    instala `src/util.lua` como `luassert.util`, y ningun sufijo lo adivina.
    Cacheado por la firma (nombre, mtime) de los rockspecs: el watch re-lee solo."""
    base = os.path.abspath(raiz)
    rocas = []
    for carpeta in (base, os.path.join(base, "rockspecs")):
        try:
            rocas += sorted(os.path.join(carpeta, n) for n in os.listdir(carpeta)
                            if n.endswith(".rockspec"))
        except OSError:
            continue
    firma = (base, tuple((r, os.path.getmtime(r)) for r in rocas))
    if firma not in _LUA_ROCAS:
        mapa = {}
        for r in rocas:
            try:
                with open(r, encoding="utf-8", errors="replace") as fh:
                    texto = fh.read()
            except OSError:
                continue
            for req, rel in _LUA_ENTRADA.findall(texto):
                mapa[req] = module_name(os.path.join(base, rel), base)
        _LUA_ROCAS.clear()
        _LUA_ROCAS[firma] = mapa
    return _LUA_ROCAS[firma]


def _lua_modulo(especificador, raiz, modulos):
    """El modulo interno de un `require` de Lua, o None si es externo.

    En Lua el nombre ENTERO es la ruta desde una raiz de `package.path`
    (`?.lua`, `?/init.lua`): `require 'pl.utils'` es Penlight, no
    `busted/utils.lua`. Casar por un trozo del nombre, como el sufijo generico,
    inventaba aristas: en busted `pl.utils` caia en `busted.utils` y
    `cliargs.core` en `busted.core` (banco de repos reales, 24-sep-2026). Y un
    `require('busted.languages.' .. x)` no nombra ningun modulo: caia en `busted`.
    """
    if not _LUA_NOMBRE.match(especificador):
        return None          # concatenacion o variable: no hay nombre escrito
    declarado = _lua_rocas(raiz).get(especificador)
    if declarado in modulos:
        return declarado
    for exacto in (especificador, especificador + ".init"):
        if exacto in modulos:
            return exacto
    # Una raiz de package.path puede ser un subdirectorio (`lua/`, `lib/`): vale
    # el nombre entero como sufijo por segmentos, y solo si hay UN candidato.
    cola = ("." + especificador, "." + especificador + ".init")
    candidatos = [m for m in modulos if m.endswith(cola)]
    return candidatos[0] if len(candidatos) == 1 else None


def _rust_interno(primero, modulos):
    """¿El primer segmento de un `use` de Rust nombra algo de ESTE crate?

    Lo son `crate`/`self`/`super` y los modulos de PRIMER NIVEL de un crate: los
    que cuelgan del directorio de su `lib.rs`/`main.rs`. Casar por sufijo en
    cualquier profundidad no vale: el crate `glob` (muy usado) volveria a caer en
    `resolvers.glob`.
    """
    if primero in ("crate", "self", "super"):
        return True
    raices = {m.rsplit(".", 1)[0] if "." in m else "" for m in modulos
              if m.rsplit(".", 1)[-1] in ("lib", "main")}
    return any((raiz + "." if raiz else "") + primero in modulos
               or any(m.startswith((raiz + "." if raiz else "") + primero + ".") for m in modulos)
               for raiz in raices)


_SWIFT_PKG = {}
_RE_TARGET_SWIFT = re.compile(r"\.(target|executableTarget|testTarget|macro)\s*\(\s*name:\s*"
                              r"\"([^\"]+)\"")
_RE_PATH_SWIFT = re.compile(r"\bpath:\s*\"([^\"]+)\"")


def _swift_targets(fichero, raiz):
    """{target: carpeta} del Package.swift que gobierna `fichero` (subiendo
    hasta `raiz`), o {} si no hay: sin manifiesto, ningun import es propio.

    SwiftPM pone cada target en `Sources/<nombre>` (`Tests/<nombre>` los de
    test) salvo que declare `path:`; eso es todo lo que se lee."""
    carpeta = os.path.dirname(os.path.abspath(fichero))
    tope = os.path.abspath(raiz)
    while True:
        if carpeta in _SWIFT_PKG:
            return _SWIFT_PKG[carpeta]
        manifiesto = os.path.join(carpeta, "Package.swift")
        if os.path.isfile(manifiesto):
            try:
                with open(manifiesto, encoding="utf-8", errors="replace") as fh:
                    texto = fh.read()
            except OSError:
                texto = ""
            targets = {}
            decl = list(_RE_TARGET_SWIFT.finditer(texto))
            for i, m in enumerate(decl):
                tramo = texto[m.end():decl[i + 1].start() if i + 1 < len(decl) else len(texto)]
                ruta = _RE_PATH_SWIFT.search(tramo)
                rel = (ruta.group(1) if ruta else
                       os.path.join("Tests" if m.group(1) == "testTarget" else "Sources", m.group(2)))
                targets[m.group(2)] = os.path.normpath(os.path.join(carpeta, rel))
            _SWIFT_PKG[carpeta] = targets
            return targets
        padre = os.path.dirname(carpeta)
        if carpeta == tope or padre == carpeta:
            return {}
        carpeta = padre


def _resuelve_swift(especificador, fichero, raiz, modulos):
    """`import X` (o `import func X.f`, `import X.Sub`) nombra el MODULO X: es
    interno solo si X es un target del Package.swift, y apunta a su fichero si
    el target tiene uno solo. Nunca por nombre de fichero: `import Foundation`
    casaba por sufijo con `Utilities/Foundation.swift` de swift-argument-parser
    y las 22 aristas del grafo eran esa (banco de repos reales, 24-sep-2026)."""
    carpeta = _swift_targets(fichero, raiz).get(especificador.split(".")[0])
    if not carpeta:
        return None
    dentro = [m for m, ruta in modulos.items() if ruta.endswith(".swift")
              and os.path.abspath(ruta).startswith(carpeta + os.sep)]
    return dentro[0] if len(dentro) == 1 else None


_NS_CS = {"modulos": None, "mapa": {}}
_RE_NAMESPACE = re.compile(r"^\s*namespace\s+([A-Za-z_][\w.]*)", re.M)


def _namespaces_cs(modulos):
    """{namespace: [modulo, ...]} de los .cs del arbol: lo que el proyecto
    DECLARA. Una plaza, atada a la identidad de `modulos` (uno por analyze)."""
    if _NS_CS["modulos"] is not modulos:
        mapa = {}
        for nombre, ruta in modulos.items():
            if not ruta.endswith(".cs"):
                continue
            try:
                with open(ruta, encoding="utf-8-sig", errors="replace") as fh:
                    declarados = set(_RE_NAMESPACE.findall(fh.read()))
            except OSError:
                continue
            for ns in declarados:
                mapa.setdefault(ns, []).append(nombre)
        _NS_CS["modulos"], _NS_CS["mapa"] = modulos, mapa
    return _NS_CS["mapa"]


def _resuelve_cs(especificador, modulos):
    """`using X.Y;` nombra un NAMESPACE, no un fichero: es interno solo si algun
    fichero del arbol lo declara, y apunta a ESE fichero si es uno solo (con
    varios no hay destino unico: la carencia MISMO_PAQUETE). `using static` y el
    alias nombran un TIPO: su namespace declarado y el fichero con su nombre.

    Sin esto el sufijo sin mayusculas casaba por el ultimo segmento: en MediatR
    `global using MediatR.DependencyInjectionTests.Contracts.Requests;` (una
    carpeta de 6 ficheros) caia en `samples/.../ExceptionHandler/Requests.cs`
    de OTRO proyecto, y `...Contracts.Responses` (un solo fichero, `Pong.cs`)
    no dejaba arista porque el prefijo exigia el namespace desde la raiz del
    repo (banco de repos reales, 24-sep-2026). Misma clase que Go y Rust.
    """
    mapa = _namespaces_cs(modulos)
    declarados = mapa.get(especificador)
    if declarados:
        return declarados[0] if len(declarados) == 1 else None
    padre, _, tipo = especificador.rpartition(".")
    candidatos = [m for m in mapa.get(padre, ()) if m.rsplit(".", 1)[-1] == tipo]
    return candidatos[0] if len(candidatos) == 1 else None


def _java_interno(partes, modulos, minimo=2):
    """El modulo al que apunta un import de Java, o None si es externo.

    Un import de Java es un nombre CUALIFICADO ENTERO (`org.jsoup.nodes.Element`),
    asi que solo es interno si un modulo termina en ese nombre, segmento a
    segmento y con sus mayusculas. Los atajos de `_resuelve` (sufijo suelto,
    sin mayusculas, quitar el ultimo segmento y volver a probar) inventaban
    aristas: `java.util.List` -> `java.util` -> `Util.java` en javapoet (17 de
    32 aristas falsas), `org.w3c.dom.Element` -> `nodes/Element.java` y
    `java.util.regex.Pattern` -> `helper/Regex.java` en jsoup (banco de repos
    reales, 24-sep-2026).

    Se prueba el nombre entero y luego quitando segmentos por la derecha, que
    es lo que pide `import static a.b.C.metodo` o una clase anidada
    `a.b.C.Interna` -> `a.b.C`; nunca por debajo de dos segmentos (un tipo en
    un paquete). `import a.b.*` nombra el paquete: vale si tiene un solo modulo.
    `minimo` sube ese suelo cuando `partes` trae delante un paquete que no es
    del import (el relativo de Scala): quitar segmentos no puede comerselo.
    """
    for fin in range(len(partes), max(minimo, 2) - 1, -1):
        nombre = ".".join(partes[:fin])
        hits = [m for m in modulos if m == nombre or m.endswith("." + nombre)]
        if hits:
            return hits[0] if len(hits) == 1 else None
    paquete = "." + ".".join(partes) + "."
    hijos = [m for m in modulos if paquete in "." + m
             and "." not in ("." + m).split(paquete, 1)[1]]
    return hijos[0] if len(hijos) == 1 else None


#: Una declaracion de NIVEL SUPERIOR de Kotlin: en columna 0, con sus
#: modificadores/anotaciones delante y, si es de extension, su receptor
#: (`fun Color.toSRGB()`, `val <T> List<T>.x`). Lo que va sangrado no es de
#: nivel superior y no se importa por el nombre del paquete.
_KT_DECLARACION = re.compile(
    r"^(?:[@\w][\w.@()\",= ]*\s)?(?:fun|val|var|class|interface|object|typealias)\s+"
    r"(?:<[^>\n]*>\s*)?(?:[\w.<>?,* ]+\.)?`?(\w+)`?", re.M)
_KT_DECLARA = {}            # ruta -> (mtime_ns, {nombres de nivel superior})


def _kotlin_declara(modulo, nombre, raiz):
    """¿El fichero del modulo declara `nombre` en su nivel superior?"""
    base = modulo.split(".")
    for pre in ((), ("src",)):
        for ext in (".kt", ".kts"):
            ruta = os.path.join(raiz, *pre, *base) + ext
            try:
                mt = os.stat(ruta).st_mtime_ns
            except OSError:
                continue
            memo = _KT_DECLARA.get(ruta)
            if memo is None or memo[0] != mt:
                with open(ruta, encoding="utf-8", errors="replace") as f:
                    memo = (mt, set(_KT_DECLARACION.findall(f.read())))
                _KT_DECLARA[ruta] = memo
            return nombre in memo[1]
    return False


def _kotlin_interno(partes, raiz, modulos):
    """El modulo al que apunta un import de Kotlin, o None si es externo.

    Como en Java el import es un nombre CUALIFICADO entero, y los atajos de
    `_resuelve` inventaban lo mismo: `android.graphics.Color` y
    `androidx.compose.ui.graphics.Color` caian en el `Color.kt` propio, y
    `org.jetbrains.skia.ColorSpace` en `ColorSpace.kt` (colormath, banco de
    repos reales, 24-sep-2026). Pero Kotlin importa ademas lo que Java no:
    funciones, propiedades y objetos de NIVEL SUPERIOR, en un fichero cuyo nombre
    no dice nada (`import ...internal.doCreate` vive en `ColorSpaceUtils.kt`;
    `import ...model.LABColorSpaces.LAB50`, en `LAB.kt`). Si el nombre entero no
    es un fichero, se busca en el paquete el fichero que DECLARA ese nombre, y
    solo vale si es exactamente uno.
    """
    hit = _java_interno(partes, modulos)
    if hit:
        return hit
    for fin in range(len(partes), 1, -1):
        paquete, nombre = partes[:fin - 1], partes[fin - 1]
        n = len(paquete)
        candidatos = [m for m in modulos if m.split(".")[-n - 1:-1] == paquete]
        declaran = [m for m in candidatos if _kotlin_declara(m, nombre, raiz)]
        if declaran:
            return declaran[0] if len(declaran) == 1 else None
    return None


_COMODIN_SCALA = ("_", "*", "given")


def _scala_nombres(texto):
    """Los nombres cualificados de UN `import` de Scala, entero como lo da el AST.

    `import a.b.C, x.Y`       -> a.b.C, x.Y
    `import a.b.{C, D => E}`  -> a.b.C, a.b.D   (el renombre no cambia el origen)
    `import a.b._` / `a.b.*`  -> a.b            (el paquete: `_java_interno` lo trata)
    `import a.b.C as D`       -> a.b.C          (Scala 3)

    Cada nombre va con el nombre LOCAL que deja en el fichero (`D` en los dos
    renombres, None en el comodin): lo usa la resolucion de llamadas.
    """
    cuerpo = re.sub(r"\s+", " ", texto.strip())
    if cuerpo.startswith("import "):
        cuerpo = cuerpo[len("import "):]
    clausulas, nivel, actual = [], 0, ""
    for c in cuerpo:
        nivel += (c == "{") - (c == "}")
        if c == "," and nivel == 0:
            clausulas.append(actual)
            actual = ""
        else:
            actual += c
    clausulas.append(actual)
    nombres = []
    for clausula in (c.strip() for c in clausulas):
        if "{" in clausula:
            base = clausula.split("{", 1)[0].strip().rstrip(".").strip()
            selectores = clausula.split("{", 1)[1].rsplit("}", 1)[0].split(",")
        else:
            base, _, ultimo = clausula.rpartition(".")
            selectores = [ultimo]
        for sel in selectores:
            trozos = re.split(r"=>| as ", sel)
            origen, local = trozos[0].strip(), trozos[-1].strip()
            if not origen or not base:
                continue
            if origen in _COMODIN_SCALA or origen.startswith("given "):
                nombres.append((base.replace(" ", ""), None))
            else:
                nombres.append(((base + "." + origen).replace(" ", ""),
                                None if local in _COMODIN_SCALA else local))
    return nombres


def _scala_de_fuera(nombre, modulos):
    """¿Un import de Scala nombra algo que NO puede estar en este arbol? Solo si
    su primer segmento no es ningun directorio del proyecto: `org.junit...` en
    un repo sin `org/`. Si lo es (`scala.xml.dtd.PublicID`, declarado en un
    fichero con otro nombre) no se sabe, y no se afirma."""
    raiz = "." + nombre.split(".", 1)[0] + "."
    return not any(raiz in "." + m for m in modulos)


_RE_PAQUETE_SCALA = re.compile(r"^\s*package\s+(?!object\b)([A-Za-z_][\w.]*)", re.M)
_PAQUETES_SCALA = {"modulos": None, "mapa": {}}


def _scala_interno(nombre, fichero, modulos):
    """El modulo al que apunta un nombre importado en Scala, o None si es externo.

    Un import de Scala es RELATIVO al paquete en el que esta el fichero (`import
    Utility.sbToString` dentro de `package scala.xml`, o `import parsing._`), y
    si no, absoluto. Las dos vias exigen el nombre cualificado ENTERO, como en
    Java: `import scala.collection.Seq` no puede caer en un `Seq.scala` propio
    por sufijo — la misma arista inventada que dieron Go, Rust y Java.
    Los paquetes visibles son los de las clausulas `package` apiladas del
    fichero (`package a` + `package b` ve `a.b` y `a`), del mas interno afuera.
    """
    partes = [p for p in nombre.split(".") if p]
    if not partes:
        return None
    if _PAQUETES_SCALA["modulos"] is not modulos:     # una plaza por analyze
        _PAQUETES_SCALA["modulos"], _PAQUETES_SCALA["mapa"] = modulos, {}
    clausulas = _PAQUETES_SCALA["mapa"].get(fichero)
    if clausulas is None:
        try:
            with open(fichero, encoding="utf-8", errors="replace") as fh:
                clausulas = _RE_PAQUETE_SCALA.findall(fh.read())
        except OSError:
            clausulas = []
        _PAQUETES_SCALA["mapa"][fichero] = clausulas
    contextos, acumulado = [], []
    for clausula in clausulas:
        acumulado = acumulado + clausula.split(".")
        contextos.insert(0, list(acumulado))
    for ctx in contextos:
        destino = _java_interno(ctx + partes, modulos, minimo=len(ctx) + 1)
        if destino:
            return destino
    return _java_interno(partes, modulos)


def _declarados_elixir(defs):
    """Lo que un arbol Elixir DECLARA, a partir de sus `defmodule`/`defprotocol`.

    `defs` es [(fichero, ini, fin, nombre_escrito, modulo)]. Devuelve el
    contexto que usan imports y llamadas: `declarados` {Nombre.Completo:
    {modulo}}, `ambitos` {fichero: [(ini, fin, Nombre.Completo)]} y `alias`
    {fichero: {Corto: Completo}} sembrado con los anidados — `defmodule
    Unescape` dentro de `Jason.Decoder` es `Jason.Decoder.Unescape` y dentro de
    su padre se le llama `Unescape`.

    En Elixir el nombre de un modulo lo pone `defmodule`, no el fichero: casar
    `Jason.Codegen` contra `codegen.ex` por sufijo sin mayusculas era adivinar,
    y la adivinanza fallaba justo en lo que importa — `alias Jason.DecodeError`
    (declarado en `decoder.ex`) no casaba con ningun fichero y caia, quitando
    el ultimo segmento, en `jason.ex`: una arista inventada por cada test.
    """
    ctx = {"declarados": {}, "ambitos": {}, "alias": {}, "importa": {}}
    for fichero, ini, fin, nombre, modulo in sorted(defs, key=lambda d: (d[0], d[1], -d[2])):
        padres = [a for a in ctx["ambitos"].get(fichero, ()) if a[0] <= ini and fin <= a[1]]
        completo = nombre
        if padres:
            padre = max(padres, key=lambda a: a[0])[2]
            completo = "%s.%s" % (padre, nombre)
            ctx["alias"].setdefault(fichero, {})[nombre.split(".")[0]] = \
                "%s.%s" % (padre, nombre.split(".")[0])
        ctx["ambitos"].setdefault(fichero, []).append((ini, fin, completo))
        ctx["declarados"].setdefault(completo, set()).add(modulo)
    return ctx


def _nombre_elixir(nombre, fichero, linea, ctx):
    """El modulo DECLARADO en el arbol al que `nombre` se refiere desde esa
    linea, o None si no es de este proyecto (`Enum`, `Logger`, `Ecto.Repo`).

    Primero el alias del fichero (`alias Jason.{Codegen}` hace de `Codegen`
    `Jason.Codegen`), luego el nombre tal cual. Nunca por sufijo ni sin
    mayusculas: `Logger` solo es propio si alguien declara `defmodule Logger`.
    """
    if nombre.startswith("__MODULE__"):
        dentro = [a for a in ctx["ambitos"].get(fichero, ()) if a[0] <= linea <= a[1]]
        if not dentro:
            return None
        nombre = max(dentro, key=lambda a: a[0])[2] + nombre[len("__MODULE__"):]
    primero, punto, resto = nombre.partition(".")
    candidatos = [nombre]
    alias = ctx["alias"].get(fichero, {}).get(primero)
    if alias:
        candidatos.insert(0, alias + punto + resto)
    return next((c for c in candidatos if c in ctx["declarados"]), None)


def _usos_elixir(usos, ctx):
    """[(origen, destino)] de los `alias`/`import`/`require`/`use` de Elixir.

    `usos` es [(fichero, linea, verbo, especificador, texto, modulo)]. Dos
    pasadas: los `alias` de cada fichero, en orden, llenan su tabla de nombres
    cortos; despues se resuelve cada uso contra lo DECLARADO. De paso, los
    `import` quedan en `ctx["importa"]`: son lo unico, ademas del propio
    modulo, contra lo que una llamada suelta puede resolver.
    """
    def _objetivos(esp):
        base, llave, dentro = esp.partition(".{")
        if not llave:
            return [esp]
        return ["%s.%s" % (base, x.strip()) for x in dentro.rstrip("}").split(",") if x.strip()]

    for fichero, _linea, verbo, esp, texto, _mod in sorted(usos):
        if verbo != "alias":
            continue
        tabla = ctx["alias"].setdefault(fichero, {})
        objetivos = _objetivos(esp)
        como = re.search(r"\bas:\s*([A-Z]\w*)", texto)
        for obj in objetivos:
            primero, punto, resto = obj.partition(".")
            completo = tabla[primero] + punto + resto if primero in tabla else obj
            corto = como.group(1) if como and len(objetivos) == 1 else completo.rsplit(".", 1)[-1]
            tabla[corto] = completo
    aristas = set()
    for fichero, linea, verbo, esp, _texto, modulo in usos:
        for obj in _objetivos(esp):
            completo = _nombre_elixir(obj, fichero, linea, ctx)
            destinos = ctx["declarados"].get(completo) or ()
            if len(destinos) != 1:
                continue
            destino = next(iter(destinos))
            if verbo == "import":
                ctx["importa"].setdefault(fichero, set()).add(destino)
            if destino != modulo:
                aristas.add((modulo, destino))
    return aristas


def _llamada_elixir(llamado, fichero, linea, propio, ctx, definidos, por_modulo):
    """(candidatos, motivo) de una llamada de Elixir.

    `Mod.f()` resuelve contra el modulo que `Mod` NOMBRA (alias, anidado o
    nombre completo), y si ese modulo no es de este arbol es una llamada a
    una libreria: `Enum.map` no puede caer en un `map` propio porque algun
    fichero se llame `enum.ex`. `f()` suelta, contra el propio fichero y los
    modulos que este `import`a — en Elixir no hay funciones globales, y
    casarla por nombre en todo el arbol colgaba el `atom()` de StreamData en
    `property_test.exs` del `Jason.Encode.atom` (banco de repos reales).
    """
    prefijo, _, fun = llamado.rpartition(".")
    if not fun:
        return [], "atributo-de-variable"          # `f.(x)`: una variable
    if not prefijo:
        visibles = {propio} | ctx["importa"].get(fichero, set())
        return [q for q in definidos.get(fun, ()) if por_modulo.get(q) in visibles], \
            "nombre-desconocido"
    if not (prefijo[:1].isupper() or prefijo.startswith("__MODULE__")):
        return [], "atributo-de-variable"          # `mod.f()`, `:erlang.f()`
    completo = _nombre_elixir(prefijo, fichero, linea, ctx)
    destinos = ctx["declarados"].get(completo) or ()
    return [q for q in definidos.get(fun, ()) if por_modulo.get(q) in destinos], \
        "nombre-desconocido"


def _resuelve(especificador, fichero, raiz, modulos, modo):
    """El módulo interno al que apunta un import, o None si es externo.

    Solo se devuelve un módulo que EXISTE en el árbol. Un paquete de terceros no
    es código de este proyecto y su arista no dice nada del acoplamiento propio;
    y un destino inventado sería una arista falsa, que es peor que ninguna.
    """
    if modo == "carga":
        # Ruby `require "gema/x"`: se busca en $LOAD_PATH, que en una gema es su
        # `lib/`. Se casa la ruta ENTERA bajo un directorio `lib`, nunca por
        # sufijo: `require "set"` solo es propio si existe `lib/set.rb`. Con
        # varias `lib/` que casen, gana la de la gema del fichero; si no hay una
        # sola, no se adivina.
        if especificador.startswith((".", "/")):
            return None
        ruta_imp = especificador[:-3] if especificador.endswith(".rb") else especificador
        cola = "lib." + ".".join(p for p in ruta_imp.split("/") if p)
        iguales = [m for m in modulos if m == cola or m.endswith("." + cola)]
        if len(iguales) > 1:
            propio = module_name(fichero, raiz)
            iguales = [m for m in iguales
                       if propio.startswith(m[:len(m) - len(cola)] + "lib.")]
        return iguales[0] if len(iguales) == 1 else None
    if fichero.endswith(".php") and _PHP_NOMBRE.match(especificador):
        # `use Vendor\Pkg\Clase` es un NOMBRE de clase, no una ruta: solo el
        # PSR-4 de composer.json dice donde vive. Nunca se cae a la ruta ni al
        # sufijo: `use Psr\Container\ContainerInterface` casaba asi con el
        # `Container.php` propio — el bug de Rust y Go, en PHP.
        return _php_psr4(especificador, fichero, raiz, modulos)
    if fichero.endswith(".dart"):
        return _dart_modulo(especificador, fichero, raiz, modulos)
    if modo in ("ruta", "ruta-local"):
        # "ruta" exige el punto inicial porque en JS/TS un especificador pelado
        # es un PAQUETE (`react`), no un fichero. "ruta-local" no lo exige porque
        # en Ruby y PHP `require_relative 'a'` si es el fichero de al lado — y
        # tratarlos igual dejaba a los dos sin una sola arista (medido por la
        # sonda de conformidad, 8-ago).
        if modo == "ruta" and not especificador.startswith("."):
            return None
        destino = os.path.normpath(os.path.join(os.path.dirname(fichero), especificador))
        candidatos = [destino] + [destino + ext for ext in POR_EXTENSION]
        candidatos += [os.path.join(destino, base + ext)
                       for base in ("index", "mod") for ext in POR_EXTENSION]
        for cand in candidatos:
            nombre = module_name(cand, raiz)
            if nombre in modulos:
                return nombre
        return None
    if modo == "paquete" and fichero.endswith(".lua"):
        return _lua_modulo(especificador, raiz, modulos)
    if modo == "paquete":
        # `app/util`, `app.util`, `crate::app::util` -> se casa por SUFIJO contra
        # los modulos reales. Sin coincidencia, no hay arista.
        if fichero.endswith(".cs"):
            return _resuelve_cs(especificador.strip(), modulos)
        if fichero.endswith(".swift"):
            return _resuelve_swift(especificador.strip(), fichero, raiz, modulos)
        limpio = especificador.strip('"\'').replace("::", ".").replace("/", ".")
        partes = [p for p in limpio.split(".") if p]
        if fichero.endswith(".go"):
            # Go tiene la regla EXACTA en go.mod: es interno lo que empieza por
            # el `module` declarado; lo demas es stdlib o de terceros. Sin esto,
            # `import "time"` y `"database/sql/driver"` casaban con `time.go` y
            # `sql.go` del propio paquete — en google/uuid las 6 aristas del
            # grafo eran inventadas (banco de repos reales, 24-sep-2026).
            modulo_go = _go_modulo(fichero, raiz)
            if modulo_go is not None:
                ruta_imp = especificador.strip('"\'`')
                if ruta_imp != modulo_go and not ruta_imp.startswith(modulo_go + "/"):
                    return None
                resto = ruta_imp[len(modulo_go):].strip("/")
                if not resto:
                    return None
                partes = [p for p in resto.replace("/", ".").split(".") if p]
        if fichero.endswith(".rs") and partes and not _rust_interno(partes[0], modulos):
            # En Rust el PRIMER segmento decide: `crate`/`self`/`super` o un
            # modulo del propio crate es interno; cualquier otro es un crate
            # externo (`std`, `serde`, `globset`). Sin esto, el sufijo sin
            # mayusculas casaba `use globset::Glob` con `resolvers.glob` y
            # fabricaba un ciclo `filesystem <-> resolvers.glob` que el gate
            # bloquearia — medido sobre tach el 24-sep-2026.
            return None
        if fichero.endswith(".java"):
            return _java_interno(partes, modulos)
        if fichero.endswith((".kt", ".kts")):
            return _kotlin_interno([p.strip("`") for p in partes], raiz, modulos)
        if fichero.endswith(".scala"):
            return _scala_interno(".".join(partes), fichero, modulos)
        for i in range(len(partes)):
            cand = ".".join(partes[i:])
            if cand in modulos:
                return cand
        # Un import de paquete nombra el DIRECTORIO (`import "ejemplo/iva"`), y el
        # nombre de modulo aqui es `directorio.fichero` (`iva.iva`): no casan
        # nunca por sufijo. Se busca el modulo cuyo PREFIJO sea ese paquete, y
        # solo si hay exactamente uno — con varios ficheros en el paquete, elegir
        # seria adivinar. Sin esto, Go, Java, Kotlin, Scala, C#, Swift y Elixir
        # salian con CERO aristas de import y su mapa se veia vacio (9-ago).
        for i in range(len(partes)):
            prefijo = ".".join(partes[i:])
            hijos = [m for m in modulos if m.split(".")[:len(partes) - i] == partes[i:]]
            if len(hijos) == 1 and prefijo:
                return hijos[0]
        # Ultimo recurso, sin distinguir mayusculas: en Elixir el modulo es
        # `Iva` y su fichero `iva.ex`, y en Java/Kotlin la clase `Carrito` vive
        # en `carrito.kt`. Es una convencion del lenguaje, no una adivinanza — y
        # aun asi solo vale si hay EXACTAMENTE un modulo que case.
        bajas = {}
        for m in modulos:
            bajas.setdefault(m.lower(), []).append(m)
        for i in range(len(partes)):
            cand = ".".join(partes[i:]).lower()
            iguales = bajas.get(cand) or []
            if len(iguales) == 1:
                return iguales[0]
            sufijo = [m for k, v in bajas.items() if k.endswith("." + cand) for m in v]
            if len(sufijo) == 1:
                return sufijo[0]
        # El ultimo segmento puede ser un SIMBOLO y no un modulo. Kotlin importa
        # funciones de nivel superior (`import nucleo.suma`), que es su forma
        # idiomatica, y ahi `suma` no es ningun fichero: el especificador entero
        # no casaba con nada y kotlin se quedaba sin arista de modulo mientras
        # `gb symbols` SI veia la llamada cruzar (medido el 11-sep-2026). Se
        # reintenta sin el ultimo segmento, y como la vuelta pasa por las mismas
        # reglas de arriba, sigue exigiendo que haya EXACTAMENTE un modulo que
        # case: no se inventa destino, se deja de perder el que existe.
        if len(partes) >= 2:
            return _resuelve(".".join(partes[:-1]), fichero, raiz, modulos, modo)
        return None
    return None


# --- el analisis ------------------------------------------------------------


# Una plaza, no un diccionario: el caso que sangraba es UNA invocacion que analiza
# el MISMO arbol dos veces (`gb graph` monta el grafo fusionado y luego los
# simbolos: 150 subprocesos de ast-grep, 15 de los 20 s medidos el 6-sep-2026).
# La clave lleva la firma completa del arbol (ruta, mtime_ns, tamano por fichero),
# asi que el watch y los tests que SI cambian ficheros fallan la clave y re-derivan
# solos; una plaza acota la memoria y basta para ese patron. Copia profunda en los
# dos sentidos: los consumidores mutan el informe (not_covered, fusion) y un cache
# que devuelve su unico original se envenena con el primero que escribe.
_MEMO_ANALYZE = {"clave": None, "informe": None}


def _firma_arbol(ficheros):
    """(ruta, mtime_ns, tamano) de cada fichero soportado: cambia si algo cambia."""
    filas = []
    for fichero, _lang in ficheros:
        try:
            st = os.stat(fichero)
            filas.append((fichero, st.st_mtime_ns, st.st_size))
        except OSError:
            filas.append((fichero, 0, -1))
    return tuple(filas)


def analyze(root):
    """El informe, con la MISMA forma que `symbols.analyze` de la vía Python.

    `root_error` no vacío significa "no he podido mirar" y ningún consumidor debe
    leerlo como "no hay nada": es la distinción que la Fase 0 dejó fijada.
    """
    root = os.path.abspath(root)
    informe = {
        "root": root, "root_error": "", "nodes": [], "edges": [], "errors": [],
        "calls_total": 0, "calls_candidates": 0, "calls_resolved": 0, "calls_builtin": 0,
        "unresolved": {}, "not_covered": [], "since": None, "baseline_ok": None,
        "new_nodes": [], "gone_nodes": [], "new_calls": [], "motor": "ast-grep",
        "lenguajes": [],
    }
    if not os.path.isdir(root):
        informe["root_error"] = "no existe: %s" % root
        return informe

    ficheros = _ficheros(root)
    if not ficheros:
        informe["root_error"] = "ni un fichero de un lenguaje soportado bajo %s" % root
        return informe

    ruta_ag, detalle = disponible()
    if not ruta_ag:
        informe["root_error"] = detalle
        return informe
    # `clave_memo` y no `clave`: mas abajo el dedupe de simbolos rebinda `clave`
    # y el memo guardaria la del ultimo match (paso el 6-sep, cache que nunca daba).
    clave_memo = (root, ruta_ag, _firma_arbol(ficheros))
    if _MEMO_ANALYZE["clave"] == clave_memo:
        return copy.deepcopy(_MEMO_ANALYZE["informe"])
    informe["motor"] = detalle
    presentes = sorted({lang for _f, lang in ficheros})
    informe["lenguajes"] = presentes

    modulos = {}
    por_fichero = {}
    for fichero, lang in ficheros:
        nombre = module_name(fichero, root)
        if not nombre:
            continue
        modulos[nombre] = fichero
        por_fichero[os.path.abspath(fichero)] = (nombre, lang)

    # La marca que lee la seleccion de tests, por FICHERO: significa "este nodo
    # vive en algo que el runner colecciona". Va en el modulo Y en sus simbolos,
    # y las dos mitades hacen falta: en JS el caso es una lambda anonima dentro
    # de `test(...)` y la arista sale del modulo, pero en Rust `#[test] fn t()`
    # es un simbolo con nombre y la arista sale de EL — marcando solo el modulo,
    # la cadena llegaba a `tests.carrito.t`, no lo reconocia como test y el
    # fichero se caia de la seleccion (medido montando el banco de Rust, 9-ago).
    de_test = {}
    for nombre, fichero in sorted(modulos.items()):
        cfg = LENGUAJES[lenguaje_de(fichero)]
        rel = os.path.relpath(fichero, root)
        de_test[rel] = es_fichero_de_test(fichero, root, cfg)
        informe["nodes"].append({
            "qual": nombre, "kind": "module", "module": nombre, "doc": "",
            "file": rel, "line": 1, "end": None, "sig": "",
            "test": de_test[rel],
        })

    # --- simbolos ---
    # El prefetch: un solo proceso para todo lo estructural. None = el scan no
    # pudo y cada _corre de abajo arranca su proceso como siempre.
    lote = _lote_estructural(ruta_ag, presentes, root)
    definidos = {}          # nombre pelado -> [qual, ...]
    por_modulo = {}         # qual -> modulo que lo define (para llamadas cualificadas)
    lengua_de = {}          # qual -> lenguaje del fichero que lo define
    dueno_de = {}           # qual -> objeto al que se asigno (`app` en `app.use = ...`)
    cabeceras = {}          # qual de clase -> su texto, para leer sus bases
    defs_ex = []            # los `defmodule` de Elixir, para `_declarados_elixir`
    vistos = set()
    for lang in presentes:
        cfg = LENGUAJES[lang]
        for entrada_pat in cfg["simbolos"]:
            # (kind, patron) o (kind, patron, selector): el tercero solo lo
            # necesitan las gramaticas que no parsean el nodo suelto.
            kind, patron = entrada_pat[0], entrada_pat[1]
            selector = entrada_pat[2] if len(entrada_pat) > 2 else None
            for m in _corre(ruta_ag, patron, cfg["ag"], root, selector, lote=lote):
                nombre = _meta(m, "NAME")
                fichero = os.path.abspath(os.path.join(root, m.get("file", "")))
                entrada = por_fichero.get(fichero)
                if not nombre or entrada is None or entrada[1] != lang:
                    continue
                if lang == "elixir" and kind == "class":
                    # `defmodule Jason.Decoder`: el nombre escrito va al
                    # contexto de resolucion y el simbolo es su ultimo segmento
                    defs_ex.append((fichero, _linea(m), _fin(m), nombre, entrada[0]))
                    nombre = nombre.rsplit(".", 1)[-1]
                if "." in nombre or ":" in nombre:
                    # `$NAME` no es un identificador: en Lua `function $NAME()`
                    # casa tambien `function M.x()` y `function M:x()`, que ya
                    # recogen los patrones de metodo. Aceptarlo duplicaba cada
                    # metodo con un qual inventado (`busted.core.busted.getTrace`)
                    # que ademas se quedaba las llamadas de dentro (mismo tramo).
                    continue
                if re.match(r"def\s+%s\s*\." % re.escape(nombre), m.get("text", "")):
                    # `def self.x` / `def Obj.x` casando `def $NAME`: NAME es el
                    # RECEPTOR, no el metodo. Salian decenas de simbolos `self` y
                    # las llamadas de dentro se colgaban de ellos.
                    continue
                modulo = entrada[0]
                linea = _linea(m)
                clave = (fichero, linea, nombre)
                if clave in vistos:
                    continue          # una definicion casa con varios patrones
                vistos.add(clave)
                qual = "%s.%s" % (modulo, nombre) if modulo else nombre
                rel = os.path.relpath(fichero, root)
                informe["nodes"].append({
                    "qual": qual, "kind": kind, "module": modulo, "doc": "",
                    "file": rel, "line": linea, "end": _fin(m),
                    "sig": _firma_de(m.get("text") or "", nombre) if kind in ("function", "method") else "",
                    "test": de_test.get(rel, False),
                })
                if _meta(m, "OBJ"):
                    # `app.handle = function`: el objeto al que se asigna, para
                    # resolver `this.set()` dentro contra `app.set` (ver abajo).
                    dueno_de[qual] = _meta(m, "OBJ").strip()
                informe["edges"].append([modulo, qual, "DEFINES"])
                # Una SOBRECARGA (Java, C#, Kotlin) da el mismo qual dos veces, y
                # con el repetido la llamada salia `nombre-ambiguo` entre un
                # simbolo y el mismo: `writeTo -> writeToPath` en javapoet.
                if qual not in definidos.setdefault(nombre, []):
                    definidos[nombre].append(qual)
                por_modulo[qual] = modulo
                lengua_de[qual] = lang
                if kind == "class" and qual not in cabeceras:
                    cabeceras[qual] = (m.get("text") or "")[:800]

    _dueno_y_herencia(informe, cabeceras, definidos, por_modulo, lengua_de)

    # --- imports ---
    aristas = set()
    # {fichero: {nombre}} que el fichero trae de FUERA del arbol por import
    # explicito (Scala): ahi `f()` es ese `f`, no un homonimo del proyecto.
    importados_de_fuera = {}
    ctx_ex = _declarados_elixir(defs_ex)
    usos_ex = []
    for lang in presentes:
        cfg = LENGUAJES[lang]
        for entrada_imp in cfg["imports"]:
            # (patron) o (patron, selector): el selector hace falta cuando la
            # forma NORMAL del lenguaje agrupa varios imports en un bloque —
            # `import ( "a"\n "b" )` en Go casa una vez como bloque y ninguna por
            # dentro. Sin esto, el gate decia "sin cruces" mientras un modulo
            # importaba al que tiene prohibido (medido en una tirada real, 9-ago:
            # un FALSO VERDE, que es el peor fallo que puede dar una gate).
            # Un tercero, si esta, es la resolucion de ESE patron cuando no es la
            # del lenguaje (Ruby: `require` va por $LOAD_PATH, no por ruta).
            patron, selector, modo = ((tuple(entrada_imp) + (None,))[:3]
                                      if isinstance(entrada_imp, tuple)
                                      else (entrada_imp, None, None))
            for m in _corre(ruta_ag, patron, cfg["ag"], root, selector):
                especificador = _sin_comillas(_meta(m, "SRC"))
                fichero = os.path.abspath(os.path.join(root, m.get("file", "")))
                entrada = por_fichero.get(fichero)
                if not especificador or entrada is None or entrada[1] != lang:
                    continue
                if lang == "elixir":
                    # necesita los `alias` del fichero antes de resolver nada
                    texto = m.get("text", "")
                    usos_ex.append((fichero, _linea(m), texto.split(None, 1)[0],
                                    especificador, texto, entrada[0]))
                    continue
                # Un `import` de Scala nombra VARIOS (`a.{B, C}`, `a.B, c.D`):
                # llega entero y se despliega aqui, uno por nombre.
                for nombre, local in (_scala_nombres(especificador) if lang == "scala"
                                      else ((especificador, None),)):
                    destino = _resuelve(nombre, fichero, root, modulos,
                                        modo or cfg["resolucion"])
                    if destino and destino != entrada[0]:
                        aristas.add((entrada[0], destino))
                    if local and not destino and _scala_de_fuera(nombre, modulos):
                        importados_de_fuera.setdefault(fichero, set()).add(local)
    aristas |= _usos_elixir(usos_ex, ctx_ex)
    for origen, destino in sorted(aristas):
        informe["edges"].append([origen, destino, "IMPORTS"])

    # --- llamadas ---
    # Los tramos de cada fichero, para saber DENTRO DE QUE simbolo cae una
    # llamada. Sin esto la arista sale del modulo y la cadena transitiva se
    # corta: nadie "llama" a un modulo. Medido en el banco de JS: con aristas de
    # modulo, romper el simbolo mas profundo seleccionaba 1 test de los 5 que
    # dependian de el — y no daba falso verde solo porque la rotura era dura.
    tramos = {}
    for n in informe["nodes"]:
        if n["kind"] != "module" and n.get("end"):
            tramos.setdefault(n["file"], []).append((n["line"], n["end"], n["qual"]))

    def _envuelve(rel, linea, modulo):
        dentro = [t for t in tramos.get(rel, []) if t[0] <= linea <= t[1]]
        return min(dentro, key=lambda t: t[1] - t[0])[2] if dentro else modulo

    por_fichero_nodos = {}
    for n in informe["nodes"]:
        if n["kind"] != "module" and n.get("end"):
            por_fichero_nodos.setdefault(n["file"], []).append(n)

    def _this_metodo(rel, linea, nombre):
        """A quien apunta `this.nombre()` en JS/TS, por AMBITO LEXICO — un hecho,
        no una inferencia de tipos. Dentro de un metodo de clase: el metodo
        `nombre` de ESA clase (mismo fichero, dentro de su tramo). Dentro de
        `app.handle = function`: la propiedad `nombre` asignada al mismo `app`
        en el mismo modulo (el patron de express). Si no, nada: se cuenta."""
        propios = por_fichero_nodos.get(rel, [])
        envolventes = sorted((n for n in propios if n["line"] <= linea <= n["end"]),
                             key=lambda n: n["end"] - n["line"])
        for n in envolventes:
            if n["qual"] in dueno_de:
                obj, mod = dueno_de[n["qual"]], por_modulo.get(n["qual"])
                return [q for q, o in dueno_de.items() if o == obj
                        and por_modulo.get(q) == mod and q.rsplit(".", 1)[-1] == nombre]
            if n["kind"] == "method":
                clases = [c for c in propios if c["kind"] == "class"
                          and c["line"] <= n["line"] <= c["end"]]
                if not clases:
                    return []
                c = min(clases, key=lambda c: c["end"] - c["line"])
                return [x["qual"] for x in propios if x["kind"] == "method"
                        and x["qual"] not in dueno_de
                        and x["qual"].rsplit(".", 1)[-1] == nombre
                        and c["line"] <= x["line"] <= c["end"]]
        return []

    sin_resolver = {}
    for lang in presentes:
        cfg = LENGUAJES[lang]
        if not cfg["llamada"]:
            continue                    # declarado en `carencias`, no disimulado
        # Varios patrones por lenguaje, deduplicando por (fichero, linea, nombre):
        # una misma llamada puede casar con dos formas y contarla dos veces
        # inflaria el denominador de resolucion.
        vistas = set()
        candidatas = []
        for entrada_ll in cfg["llamada"]:
            patron, selector = (entrada_ll if isinstance(entrada_ll, tuple)
                                else (entrada_ll, None))
            for m in _corre(ruta_ag, patron, cfg["ag"], root, selector, lote=lote):
                clave = (m.get("file"), _linea(m), _meta(m, "A"), _meta(m, "FN"))
                if clave in vistas:
                    continue
                vistas.add(clave)
                # La CABECERA de la definicion no es una llamada. En Elixir
                # `def suma(a, b)` es un nodo `call` de verdad, asi que
                # `$FN($$$)` casaba el propio `def` y gb emitia `a.suma ->
                # a.suma`: una arista INVENTADA, que es peor que una ausente
                # (ADR 0008). Medido el 11-sep-2026 sobre un modulo con dos
                # funciones: 3 aristas CALLS de las que 2 eran auto-aristas del
                # encabezado. La sonda de conformidad no lo vio porque solo
                # exige "alguna arista" y una auto-arista la satisface.
                #
                # Se descarta por POSICION, no por lenguaje: mismo fichero,
                # misma linea y mismo nombre que una definicion ya extraida es
                # el encabezado de esa definicion. El precio va declarado en
                # `carencias`: una recursion escrita en la MISMA linea que su
                # def (`def f(x), do: f(x - 1)`) se pierde — y ya se perdia,
                # porque la deduplicacion de arriba deja un solo match para esa
                # linea y ese nombre.
                fichero_m = os.path.abspath(os.path.join(root, m.get("file", "")))
                if (fichero_m, _linea(m), _meta(m, "FN")) in vistos:
                    continue
                candidatas.append(m)
        for m in candidatas:
            llamado = (_meta(m, "FN") or "").strip()
            # Patron `$A.$FN($$$)`: en Java, Kotlin y Scala TODA invocacion es
            # `receptor.metodo(...)` en el AST y `$FN($$$)` no casa nada — el
            # banco de Java salio con CERO llamadas hasta ver esto. Las dos
            # metavariables se recomponen en el nombre cualificado, que es lo que
            # sabe resolver `_por_cualificado`.
            receptor = (_meta(m, "A") or "").strip()
            if receptor and "." not in llamado:
                llamado = "%s.%s" % (receptor, llamado)
            fichero = os.path.abspath(os.path.join(root, m.get("file", "")))
            entrada = por_fichero.get(fichero)
            if not llamado or entrada is None or entrada[1] != lang:
                continue
            informe["calls_total"] += 1
            if llamado in cfg["globales"]:
                informe["calls_builtin"] += 1
                continue
            informe["calls_candidates"] += 1
            if lang == "php" and receptor == "parent":
                # `parent::x()` es el metodo del PADRE: por ambito saldria el
                # override de esta misma clase, una auto-arista inventada.
                sin_resolver["parent"] = sin_resolver.get("parent", 0) + 1
                continue
            propio = None
            if (lang in ("js", "ts", "tsx") and llamado.startswith("this.")
                    and llamado.count(".") == 1):
                propio = llamado[5:]
            elif lang == "php" and receptor in ("$this", "self", "static"):
                # el mismo hecho lexico que `this.x()` en JS: la clase que
                # contiene la llamada
                propio = (_meta(m, "FN") or "").strip()
            if propio:
                rel = os.path.relpath(fichero, root)
                candidatos = sorted(set(_this_metodo(rel, _linea(m), propio)))
                if len(candidatos) != 1:
                    sin_resolver["this-sin-dueno"] = sin_resolver.get("this-sin-dueno", 0) + 1
                    continue
                informe["calls_resolved"] += 1
                origen = _envuelve(rel, _linea(m), entrada[0])
                informe["edges"].append([origen, candidatos[0], "CALLS"])
                continue
            if lang == "elixir":
                candidatos, motivo = _llamada_elixir(llamado, fichero, _linea(m), entrada[0],
                                                     ctx_ex, definidos, por_modulo)
                if len(candidatos) > 1:
                    propios = [q for q in candidatos if por_modulo.get(q) == entrada[0]]
                    candidatos = propios if len(propios) == 1 else candidatos
                if len(candidatos) != 1:
                    motivo = motivo if not candidatos else "nombre-ambiguo"
                    sin_resolver[motivo] = sin_resolver.get(motivo, 0) + 1
                    continue
                informe["calls_resolved"] += 1
                origen = _envuelve(os.path.relpath(fichero, root), _linea(m), entrada[0])
                informe["edges"].append([origen, candidatos[0], "CALLS"])
                continue
            if not llamado.isidentifier():
                # Llamada CUALIFICADA (`paquete.Funcion()`): en Go, Java, C#,
                # Kotlin y Scala es la forma normal de llamar a otro modulo, asi
                # que descartarla dejaba su grafo de llamadas practicamente
                # vacio. Se resuelve como los imports: casando contra simbolos
                # que EXISTEN, y solo si hay exactamente uno. Sin coincidencia o
                # con varias, no hay arista — el prefijo puede ser una variable
                # (`obj.metodo()`) y adivinar seria inventarsela (ADR 0008).
                candidatos = _por_cualificado(llamado, definidos, por_modulo)
                if candidatos:
                    candidatos = _misma_familia(candidatos, lang, lengua_de)
                if not candidatos:
                    # None: no era una llamada cualificada tratable.
                    # []:   lo parecia y no caso con ningun simbolo real — el
                    #       prefijo era una variable (`xs.reduce(...)`).
                    # Las dos son techo, y las dos se cuentan; indexar aqui una
                    # lista vacia reventaba con IndexError (cazado por su test).
                    sin_resolver["atributo-de-variable"] = \
                        sin_resolver.get("atributo-de-variable", 0) + 1
                    continue
                if len(candidatos) > 1:
                    sin_resolver["nombre-ambiguo"] = sin_resolver.get("nombre-ambiguo", 0) + 1
                    continue
                informe["calls_resolved"] += 1
                origen = _envuelve(os.path.relpath(fichero, root), _linea(m), entrada[0])
                informe["edges"].append([origen, candidatos[0], "CALLS"])
                continue
            if llamado in importados_de_fuera.get(fichero, ()):
                # `import org.junit.Assert.assertEquals` y luego `assertEquals(...)`:
                # la llamada es la de JUnit, y por nombre caia en el
                # `assertEquals` de un helper de test propio — 250 aristas
                # inventadas en scala-xml (banco de repos reales, 24-sep-2026).
                sin_resolver["importado-de-fuera"] = sin_resolver.get("importado-de-fuera", 0) + 1
                continue
            candidatos = _misma_familia(definidos.get(llamado) or [], lang, lengua_de)
            if not candidatos:
                sin_resolver["nombre-desconocido"] = sin_resolver.get("nombre-desconocido", 0) + 1
                continue
            if len(candidatos) > 1:
                # Homonimos en modulos distintos, y uno de ellos es el PROPIO
                # modulo del llamante: `f()` en el fichero que define `f` es
                # ese `f` en todos los lenguajes de la tabla — el ambito lexico
                # es un hecho, no una adivinanza. Con dos homonimos en otros
                # modulos sigue siendo ambiguo y no se elige.
                propios = [q for q in candidatos if por_modulo.get(q) == entrada[0]]
                if len(propios) == 1:
                    candidatos = propios
            if len(candidatos) > 1:
                sin_resolver["nombre-ambiguo"] = sin_resolver.get("nombre-ambiguo", 0) + 1
                continue
            informe["calls_resolved"] += 1
            origen = _envuelve(os.path.relpath(fichero, root), _linea(m), entrada[0])
            informe["edges"].append([origen, candidatos[0], "CALLS"])

    informe["unresolved"] = {**(informe.get("unresolved") or {}), **sin_resolver}
    informe["not_covered"] = [
        "llamadas sobre variables (`obj.metodo()`): exigen inferencia de tipos. Se cuentan, "
        "no se adivinan — una arista inventada es peor que una arista ausente",
        "reexports, carga dinamica y alias: invisibles al patron",
        "homonimos en modulos distintos: se cuentan aparte en vez de elegir uno",
    ] + carencias_de(presentes)
    _MEMO_ANALYZE["clave"] = clave_memo
    _MEMO_ANALYZE["informe"] = copy.deepcopy(informe)
    return informe


def build_graph(root, skip=None, include_nested=False, skipped=None):
    """(nodes, edges, errors) de imports, con la MISMA firma que `graph.build_graph`.

    Existe para inyectarse en `graph.analyze(constructor=...)`: así los ciclos, las
    fronteras y el fan-in/out se calculan con el código que ya estaba probado, en
    vez de con una segunda copia peor. Un `.gb-boundaries` funciona igual sobre un
    proyecto Go o Ruby, que es justo lo que se busca.
    """
    informe = analyze(root)
    if informe["root_error"]:
        return set(), {}, {"": informe["root_error"]}
    nodes = {n["qual"] for n in informe["nodes"] if n["kind"] == "module"}
    edges = {}
    for origen, destino, tipo in informe["edges"]:
        if tipo == "IMPORTS":
            edges.setdefault(origen, set()).add(destino)
    return nodes, edges, {}
