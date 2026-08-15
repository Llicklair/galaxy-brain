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

import json
import os
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

    **Deuda declarada (10-ago-2026): tres licencias son ANTERIORES al criterio
    estricto.** js, ts, go, csharp y rust se remidieron exigiendo que la
    selección CONTENGA todos los tests que se ponen rojos, no que alguno lo esté
    (`bancos/estricto.py`), y las cinco dan cascada exacta. **java, php y lua no
    se han remedido con rojos reales**: sus intérpretes no están en la máquina
    donde se hizo la revisión, y cuatro instalaciones no se deciden de paso. Lo
    que SÍ se comprobó es la mitad que no necesita intérprete —la cascada, que es
    justo la que falló en Rust— y las tres dan 4/4 exacta
    (`python bancos/bench_multi.py java php lua`). No es una licencia; es la
    deuda acotada y con el comando para saldarla.
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
         ("class", "class $NAME { $$$ }")),
        _JS_IMPORTS,
        globales=_JS_GLOBALES, resolucion="ruta", tia=True,
        sufijos_test=(".test", ".spec"), dirs_test=("test", "tests", "__tests__", "spec"),
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
         ("class", "class $NAME { $$$ }")),
        _JS_IMPORTS,
        globales=_JS_GLOBALES, resolucion="ruta", tia=True,
        sufijos_test=(".test", ".spec"), dirs_test=("test", "tests", "__tests__", "spec"),
    ),
    "tsx": _lang(
        "tsx", (".tsx",),
        (("function", "export function $NAME($$$): $RET { $$$ }"),
         ("function", "export function $NAME($$$) { $$$ }"),
         ("function", "function $NAME($$$) { $$$ }"),
         ("function", "export const $NAME = ($$$) => { $$$ }"),
         ("class", "export class $NAME { $$$ }")),
        _JS_IMPORTS,
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
        "java", (".java",),
        (("class", "public class $NAME { $$$ }"),
         ("class", "class $NAME { $$$ }"),
         ("method", "class A { $MOD $RET $NAME($$$) { $$$ } }", "method_declaration")),
        ("import $SRC;",),
        llamada=("$FN($$$)", "$A.$FN($$$)"),
        tia=True, resolucion="paquete",
        sufijos_test=("Test", "Tests"), dirs_test=("test", "tests"),
    ),
    "kotlin": _lang(
        "kotlin", (".kt", ".kts"),
        (("function", "fun $NAME($$$): $RET { $$$ }"),
         ("function", "fun $NAME($$$) { $$$ }"),
         ("class", "class $NAME { $$$ }")),
        ("import $SRC",),
        llamada=("$FN($$$)", "$A.$FN($$$)"),
        resolucion="paquete",
        sufijos_test=("Test",), dirs_test=("test", "tests"),
    ),
    "swift": _lang(
        "swift", (".swift",),
        (("function", "func $NAME($$$) -> $RET { $$$ }"),
         ("function", "func $NAME($$$) { $$$ }"),
         ("class", "class $NAME { $$$ }"),
         ("class", "struct $NAME { $$$ }")),
        # Sin patron de metodo a proposito: en Swift `func` suelto ya caza los de
        # dentro de un struct o una clase, y anadir el contextual solo metia un
        # patron que la deduplicacion descartaba siempre — lo caza su sonda.
        ("import $SRC",),
        resolucion="paquete",
        sufijos_test=("Test", "Tests"), dirs_test=("test", "tests"),
        carencias=("`import` en Swift nombra un MODULO del sistema o del paquete, no un "
                   "fichero: solo deja arista si coincide con un modulo del propio arbol",),
    ),
    "ruby": _lang(
        # `class $NAME\n $$$\nend` daba ERROR de patron, asi que las clases de
        # Ruby NO se extraian — y la sonda no lo veia porque solo exigia "algun
        # simbolo", y los `def` si salian. Sin cuerpo, casa.
        "ruby", (".rb",),
        (("function", "def $NAME($$$)"),
         ("function", "def $NAME"),
         ("method", "def self.$NAME($$$)"),
         ("class", "class $NAME"),
         ("class", "module $NAME")),
        ("require_relative '$SRC'", 'require_relative "$SRC"'),
        resolucion="ruta-local",
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
         ("class", "class $NAME { $$$ }"),
         ("method", "class A { public function $NAME($$$) { $$$ } }", "method_declaration"),
         ("method", "class A { private function $NAME($$$) { $$$ } }", "method_declaration"),
         ("method", "class A { protected function $NAME($$$) { $$$ } }", "method_declaration")),
        # Las cuatro palabras que incluyen fichero en PHP, cada una con y sin
        # paréntesis (`require 'a.php'` y `require('a.php')` son la misma
        # sentencia). La metavariable va suelta y cubre ambas comillas: aquí
        # solo estaban las simples, el espejo exacto del bug de la familia JS
        # — un repo PHP con comillas dobles no dejaba ni una arista.
        ("require_once $SRC", "require $SRC", "include $SRC", "include_once $SRC",
         "require_once($SRC)", "require($SRC)", "include($SRC)", "include_once($SRC)"),
        tia=True, resolucion="ruta-local",
        sufijos_test=("Test",), dirs_test=("test", "tests"),
    ),
    "lua": _lang(
        # `function M.suma(...)` es LA forma de exportar en Lua (tabla-modulo) y
        # no se cubria: solo salian las globales y las locales.
        "lua", (".lua",),
        (("function", "function $NAME($$$) $$$ end"),
         ("function", "local function $NAME($$$) $$$ end"),
         ("method", "function $T.$NAME($$$) $$$ end"),
         ("method", "function $T:$NAME($$$) $$$ end")),
        # En Lua las tres formas son la misma llamada. Aquí la metavariable NO
        # va suelta a propósito: `require $SRC` casa también las versiones con
        # paréntesis y captura `("a")` con ellos dentro, que luego no resuelve
        # — arista perdida en silencio. Explícito es más largo y no miente.
        ('require($SRC)', "require '$SRC'", 'require "$SRC"'),
        tia=True, resolucion="paquete",
        sufijos_test=("_test", "_spec"), dirs_test=("test", "tests", "spec"),
    ),
    "scala": _lang(
        "scala", (".scala",),
        (("function", "def $NAME($$$): $RET = $$$"),
         ("class", "class $NAME { $$$ }"),
         ("class", "object $NAME { $$$ }")),
        ("import $SRC",),
        llamada=("$FN($$$)", "$A.$FN($$$)"),
        resolucion="paquete",
        sufijos_test=("Test", "Spec"), dirs_test=("test", "tests"),
    ),
    "elixir": _lang(
        "elixir", (".ex", ".exs"),
        (("function", "def $NAME($$$), do: $$$"),
         ("function", "def $NAME($$$)"),
         ("function", "defp $NAME($$$)"),
         ("class", "defmodule $NAME do $$$ end")),
        ("alias $SRC", "import $SRC"),
        resolucion="paquete",
        sufijos_test=("_test",), dirs_test=("test", "tests"),
    ),
    "csharp": _lang(
        # Los METODOS necesitan patron CONTEXTUAL: el patron trae el `class A {
        # ... }` que la gramatica exige y el selector extrae el nodo real. Suelto,
        # ast-grep parsea `public $RET $NAME(...)` como funcion local de nivel
        # superior y el `$` produce nodos ERROR — por eso los 5 patrones probados
        # a ciegas el 8-ago dieron cero, y por eso C# entro sin grafo de llamadas.
        "csharp", (".cs",),
        (("class", "class $NAME { $$$ }"),
         ("class", "public class $NAME { $$$ }"),
         ("method", "class A { public $RET $NAME($$$) { $$$ } }", "method_declaration"),
         ("method", "class A { private $RET $NAME($$$) { $$$ } }", "method_declaration"),
         ("method", "class A { protected $RET $NAME($$$) { $$$ } }", "method_declaration"),
         ("method", "class A { public static $RET $NAME($$$) { $$$ } }", "method_declaration")),
        ("using $SRC;",),
        resolucion="paquete", tia=True,
        sufijos_test=("Test", "Tests"), dirs_test=("test", "tests"),
    ),
    "c": _lang(
        "c", (".c", ".h"),
        (("function", "$RET $NAME($$$) { $$$ }"),),
        # Solo la forma LOCAL: `#include <stdio.h>` es una cabecera del sistema y
        # su arista no diria nada del acoplamiento propio.
        ('#include "$SRC"',),
        # En C una llamada suelta es una SENTENCIA, no una expresion, asi que
        # `$FN($$$)` a secas no casa nada — de ahi que el lenguaje entrara sin
        # aristas de llamada. Las dos formas comunes si casan (medido 9-ago).
        llamada=("$FN($$$);", "$T $V = $FN($$$);"),
        resolucion="ruta-local",
        sufijos_test=("_test",), dirs_test=("test", "tests"),
        carencias=("solo se ven las llamadas en sentencia y en asignacion; una anidada "
                   "en otra expresion (`f(g(x))`) no deja arista para `g`",),
    ),
    "dart": _lang(
        "dart", (".dart",),
        (("function", "$RET $NAME($$$) { $$$ }"),
         ("function", "$RET $NAME($$$) => $$$;"),
         ("class", "class $NAME { $$$ }"),
         ("method", "class A { $RET $NAME($$$) { $$$ } }", "method_declaration")),
        ("import '$SRC';",),
        llamada=None, resolucion="ruta",
        sufijos_test=("_test",), dirs_test=("test", "tests"),
        # Se probaron seis formas, incluida una literal (`suma($$$)`) y dos con
        # selector: ninguna casa. La gramatica de dart en ast-grep 0.45 no expone
        # la invocacion. Sin llamadas no hay `gb calls` ni seleccion de tests.
        carencias=("las LLAMADAS no se extraen con ningun patron probado (6 formas, "
                   "9-ago): hay simbolos y modulos, no hay grafo de llamadas",),
    ),
}

#: Lo que NO se declara soportado aunque `ast-grep` lo acepte: sin patrones
#: medidos, incluirlo seria prometer un grafo que no existe.
#:
#: `cpp` estuvo aqui dentro un dia y se SACO (9-ago). Ninguno de los cinco
#: patrones probados extrae una definicion —ni siquiera `class $NAME { $$$ };`—
#: asi que solo producia nodos de modulo, sin simbolos ni imports: cero valor. Y
#: era peor que ausente, porque al figurar su extension como "leida" el aviso de
#: frontera dejaba de saltar y el usuario recibia un grafo vacio sin que nadie le
#: dijera por que. Fuera de la tabla, gb dice "veo C++ y no lo leo", que es la
#: verdad. Vuelve el dia que alguien mida patrones que funcionen.
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


def _corre(ruta, patron, lenguaje, raiz, selector=None):
    """Una pasada de ast-grep, ya parseada. Lista vacía si algo falla: un patrón
    que no casa nada y un patrón mal escrito dan lo mismo aquí, y por eso los
    contadores del informe declaran cuánto se vio — no se infiere.

    `selector` habilita los patrones CONTEXTUALES: el patrón trae el contexto que
    la gramática necesita para parsear (`class A { ... }`) y el selector dice qué
    sub-nodo es el que de verdad se busca (`method_declaration`). Sin esto, un
    método de C# no se puede expresar: suelto, ast-grep lo parsea como función
    local de nivel superior y el `$` de la metavariable produce nodos ERROR —
    que es por lo que C# entró en la tabla sin metodos y sin grafo de llamadas.
    """
    orden = [ruta, "run", "-p", patron, "-l", lenguaje, "--json=compact"]
    if selector:
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
    if partes[-1] in ("index", "mod", "__init__"):
        partes = partes[:-1]
    return ".".join(partes)


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
    return [q for q in posibles if por_modulo.get(q, "").split(".")[-1] == prefijo]


def _resuelve(especificador, fichero, raiz, modulos, modo):
    """El módulo interno al que apunta un import, o None si es externo.

    Solo se devuelve un módulo que EXISTE en el árbol. Un paquete de terceros no
    es código de este proyecto y su arista no dice nada del acoplamiento propio;
    y un destino inventado sería una arista falsa, que es peor que ninguna.
    """
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
    if modo == "paquete":
        # `app/util`, `app.util`, `crate::app::util` -> se casa por SUFIJO contra
        # los modulos reales. Sin coincidencia, no hay arista.
        limpio = especificador.strip('"\'').replace("::", ".").replace("/", ".")
        partes = [p for p in limpio.split(".") if p]
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
        return None
    return None


# --- el analisis ------------------------------------------------------------


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
    definidos = {}          # nombre pelado -> [qual, ...]
    por_modulo = {}         # qual -> modulo que lo define (para llamadas cualificadas)
    vistos = set()
    for lang in presentes:
        cfg = LENGUAJES[lang]
        for entrada_pat in cfg["simbolos"]:
            # (kind, patron) o (kind, patron, selector): el tercero solo lo
            # necesitan las gramaticas que no parsean el nodo suelto.
            kind, patron = entrada_pat[0], entrada_pat[1]
            selector = entrada_pat[2] if len(entrada_pat) > 2 else None
            for m in _corre(ruta_ag, patron, cfg["ag"], root, selector):
                nombre = _meta(m, "NAME")
                fichero = os.path.abspath(os.path.join(root, m.get("file", "")))
                entrada = por_fichero.get(fichero)
                if not nombre or entrada is None or entrada[1] != lang:
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
                    "file": rel, "line": linea, "end": _fin(m), "sig": "",
                    "test": de_test.get(rel, False),
                })
                informe["edges"].append([modulo, qual, "DEFINES"])
                definidos.setdefault(nombre, []).append(qual)
                por_modulo[qual] = modulo

    # --- imports ---
    aristas = set()
    for lang in presentes:
        cfg = LENGUAJES[lang]
        for entrada_imp in cfg["imports"]:
            # (patron) o (patron, selector): el selector hace falta cuando la
            # forma NORMAL del lenguaje agrupa varios imports en un bloque —
            # `import ( "a"\n "b" )` en Go casa una vez como bloque y ninguna por
            # dentro. Sin esto, el gate decia "sin cruces" mientras un modulo
            # importaba al que tiene prohibido (medido en una tirada real, 9-ago:
            # un FALSO VERDE, que es el peor fallo que puede dar una gate).
            patron, selector = (entrada_imp if isinstance(entrada_imp, tuple)
                                else (entrada_imp, None))
            for m in _corre(ruta_ag, patron, cfg["ag"], root, selector):
                especificador = _sin_comillas(_meta(m, "SRC"))
                fichero = os.path.abspath(os.path.join(root, m.get("file", "")))
                entrada = por_fichero.get(fichero)
                if not especificador or entrada is None or entrada[1] != lang:
                    continue
                destino = _resuelve(especificador, fichero, root, modulos, cfg["resolucion"])
                if destino and destino != entrada[0]:
                    aristas.add((entrada[0], destino))
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
        for patron in cfg["llamada"]:
            for m in _corre(ruta_ag, patron, cfg["ag"], root):
                clave = (m.get("file"), _linea(m), _meta(m, "A"), _meta(m, "FN"))
                if clave in vistas:
                    continue
                vistas.add(clave)
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
            if not llamado.isidentifier():
                # Llamada CUALIFICADA (`paquete.Funcion()`): en Go, Java, C#,
                # Kotlin y Scala es la forma normal de llamar a otro modulo, asi
                # que descartarla dejaba su grafo de llamadas practicamente
                # vacio. Se resuelve como los imports: casando contra simbolos
                # que EXISTEN, y solo si hay exactamente uno. Sin coincidencia o
                # con varias, no hay arista — el prefijo puede ser una variable
                # (`obj.metodo()`) y adivinar seria inventarsela (ADR 0008).
                candidatos = _por_cualificado(llamado, definidos, por_modulo)
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
            candidatos = definidos.get(llamado)
            if not candidatos:
                sin_resolver["nombre-desconocido"] = sin_resolver.get("nombre-desconocido", 0) + 1
                continue
            if len(candidatos) > 1:
                sin_resolver["nombre-ambiguo"] = sin_resolver.get("nombre-ambiguo", 0) + 1
                continue
            informe["calls_resolved"] += 1
            origen = _envuelve(os.path.relpath(fichero, root), _linea(m), entrada[0])
            informe["edges"].append([origen, candidatos[0], "CALLS"])

    informe["unresolved"] = sin_resolver
    informe["not_covered"] = [
        "llamadas sobre variables (`obj.metodo()`): exigen inferencia de tipos. Se cuentan, "
        "no se adivinan — una arista inventada es peor que una arista ausente",
        "reexports, carga dinamica y alias: invisibles al patron",
        "homonimos en modulos distintos: se cuentan aparte en vez de elegir uno",
    ] + carencias_de(presentes)
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
