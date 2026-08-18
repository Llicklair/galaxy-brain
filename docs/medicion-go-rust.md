# El fallback stderr, medido en Go y Rust

**Fecha:** 2026-08-18 · **Qué se mide:** `gb-stderr-parser.py` de la rama `spike/consola-multilenguaje`,
tal cual está · **Para qué:** cerrar la cola que la [ADR 0012](adr/0012-consola-multilenguaje.md) dejó
abierta — Go y Rust son los dos lenguajes donde **no hay hook global instalable**, así que el fallback
universal de stderr es la única vía, y de él depende el criterio de aborto 1.

Go y Rust son el caso difícil por construcción: en Go `recover()` es por goroutine y no hay gancho de
proceso; en Rust `std::panic::set_hook` existe pero es una función de librería que alguien tiene que
llamar. Si el fallback no sirve aquí, no sirve como capa universal en ninguna parte.

**Titular: la cifra anterior era falsa.** [CONSOLA-MULTILENGUAJE.md](CONSOLA-MULTILENGUAJE.md) dice
«**0 registros** en Go» y con eso activa el criterio de aborto 1. Remedido desde cero:
**10 registros de 11 casos**, con fichero, línea y función correctos. Es la **tercera** vez que este
banco se equivoca hacia el «no funciona».

Lo que sí queda en pie del criterio de aborto es otra cosa, y es peor de arreglar: el registro se
produce, pero **el tipo de excepción no existe en ninguno de los dos lenguajes**, y eso no es un
defecto del parser.

## Cómo (método, después de que el banco fallara tres veces)

- **Ni una sola variable `HOME`/`USERPROFILE` tocada.** Go y Rust las ignoran; aislar por ahí es lo
  que produjo el falso «SIN REGISTRO» de la vuelta anterior.
- **MARCA + FIRMA.** Se cuentan las líneas de `~/.galaxy-brain/crashes.jsonl` justo antes y justo
  después de cada tirada, y solo se atribuyen las nuevas. **La marca sola no bastó:** aparecieron
  registros `LuaError` de un banco hermano corriendo a la vez sobre el mismo fichero, atribuidos a
  mis casos. Se añadió una firma — una línea nueva es mía solo si su `process.cwd` es el del banco
  **y** el nombre de mi binario aparece en `argv_forma` o en la traza. Con la marca sola, dos casos
  salían con registros ajenos. **El fichero solo se lee: no se edita ni se borra.**
- **Tres tiradas por caso:** directa A (verdad de referencia), directa B (**control**, para medir el
  ruido no determinista del propio runtime) y envuelta. Sin el control, cualquier comparación byte a
  byte miente: Rust imprime el **id de hilo del SO** en la línea del panic y cambia en cada ejecución.
- **Rutas nativas Windows** en todo momento; ni una ruta POSIX a un binario nativo.
- Programas mínimos compilados con `go build` y `rustc -g` (no hace falta `cargo`; está instalado,
  1.95.0). Go 1.26.5, rustc 1.95.0.
- Validación contra el `schema.json` del prototipo con un validador draft-07 propio
  (subconjunto `type`/`required`/`const`/`enum`/`properties`/`items`): `jsonschema` **no está
  instalado** en esta máquina. Los dos incumplimientos que encontró los confirma por separado
  `store_universal.py`, que valida lo mismo con su propio código.

## Resultado

`reg` = registro producido · `válido` = valida contra schema v2 · `bytes` = stderr idéntico byte a
byte · **o/p** = parser **o**riginal / **p**archeado (el parche está más abajo).

| Lenguaje | Caso | Registro (o/p) | Válido (o/p) | Tipo ≠ mensaje | Mismo exit code | Misma traza (o/p) | Frames |
|---|---|---|---|---|---|---|---|
| go | nil pointer | 1 / 1 | **0 / 1** | **no** | sí (2/2) | **no / sí** (byte a byte) | 2 |
| go | index out of range | 1 / 1 | **0 / 1** | **no** | sí (2/2) | **no / sí** | 2 |
| go | panic explícito | 1 / 1 | **0 / 1** | **no** | sí (2/2) | **no / sí** | 2 |
| go | panic explícito + `GOTRACEBACK=all` | 1 / 1 | **0 / 1** | **no** | sí (2/2) | **no / sí** | 2 |
| go | **panic en goroutine secundaria** | 1 / 1 | **0 / 1** | **no** | sí (2/2) | **no / sí** | 2 |
| go | `fatal error:` deadlock | 1 / 1 | 0 / **0** | — | sí (2/2) | **no / sí** | 0 |
| rust | unwrap sobre `None` | 1 / 1 | **0 / 1** | **no** | sí (101/101) | idéntica salvo id de hilo | 1 |
| rust | index out of bounds | 1 / 1 | **0 / 1** | **no** | sí (101/101) | idéntica salvo id de hilo | 1 |
| rust | `panic!` explícito | 1 / 1 | **0 / 1** | **no** | sí (101/101) | idéntica salvo id de hilo | 1 |
| rust | `panic!` + `RUST_BACKTRACE=1` | 1 / 1 | **0 / 1** | **no** | sí (101/101) | idéntica salvo id de hilo | **5** |
| rust | **panic en hilo secundario** | **0 / 0** | — | — | sí (0/0) | idéntica salvo id de hilo | — |

**Con el parser original: 10 registros producidos, 0 válidos.** Con el parche: **9 de 10 válidos**.

Sobre «misma traza»: en Go el control (dos tiradas directas seguidas) es **byte a byte idéntico**, así
que la comparación estricta es legítima y el parcheado la pasa en los 6 casos. En Rust el control
**no** lo es —`thread 'main' (31640) panicked at…`, el número cambia cada vez—, así que ahí lo máximo
demostrable es «idéntica salvo el id de hilo», y eso es lo medido: normalizando solo ese número, las
11 trazas coinciden con la de referencia, y la longitud en bytes también.

## Las cuatro preguntas

### 1. ¿Produce registro válido para un panic de Go y de Rust?

**Produce registro: sí, 10 de 11 casos.** Y no un registro pobre: en Go salen los frames con fichero,
línea y función reales (`main.leer` línea 10, `main.main` línea 16, correctos); en Rust sale el punto
del panic con **línea y columna**, y con `RUST_BACKTRACE=1` sube a 5 frames con nombres
(`panico::explotar`). El caso más interesante lo cubre entero: **un panic en una goroutine secundaria**
—exactamente donde `recover()` no llega y por lo que la ADR clasifica a Go como «inviable por hook»—
produce registro con sus frames.

**Válido contra el schema: no, 0 de 10**, y por dos defectos que afectan a **todos** los lenguajes que
pase el parser, no solo a estos dos:

- `exception.origin` se escribe como `"goroutine-1"` / `"thread-main"`. El enum del schema solo admite
  `main`, `thread`, `goroutine`, `coroutine`, `task`, `promise`, `signal`, `process`, `unraisable`.
- `process.argv_forma` se escribe como **lista**; el schema pide `string | null`.

No es opinión mía sobre el schema: `store_universal.py` valida lo mismo por su cuenta
(`VALID_ORIGINS`, `_check_type(proc["argv_forma"], [str, None])`) y rechazaría igual. Son dos
autoridades independientes contra el parser. Parcheado, **9 de 10 validan**.

El que sigue sin validar es el `fatal error: all goroutines are asleep - deadlock!` de Go: no lleva la
cabecera `goroutine N [running]:` que busca el detector, así que cae al genérico y sale con
`language: "unknown"` — valor que el enum de `language` tampoco admite. La rama genérica del parser
**no puede producir un registro válido nunca**, en ningún lenguaje.

Y hay un agujero que ningún parche arregla: **el panic en hilo secundario de Rust no produce registro
y es correcto que no lo produzca.** El proceso sale con **0** porque el `Err` del `join()` se ignora, y
el parser solo mira si `exit_code != 0`. stderr trae el panic entero. Es un fallo real, visible, que
el fallback no ve por diseño — y no es un caso raro: es el patrón normal de un worker que revienta sin
tumbar el proceso.

### 2. ¿Distingue el tipo del mensaje?

**No, y no es arreglable.** En los 9 panics reales, `exception.type` vale **`"panic"`, siempre**: un
valor constante, cero información. Toda la discriminación vive en `message` (8 mensajes distintos de
10 registros). Comparado con lo que dan los hooks nativos —`TypeError`, `NoMethodError`,
`ZeroDivisionError`— el fallback devuelve exactamente el «algo petó» que el criterio de aborto 1
describe.

Antes de firmar un negativo, la pregunta obligatoria: ¿es defecto del parser o no está el dato? Se
midió con un panic de tipo propio en cada lenguaje:

- Go, `panic(&ErrorDeNegocio{Codigo: 42})` → stderr dice `panic: codigo 42`. El tipo
  `*main.ErrorDeNegocio` **no aparece por ninguna parte**.
- Rust, `panic_any(ErrorDeNegocio{codigo: 42})` → stderr dice `Box<dyn Any>`. El tipo está
  **borrado por el runtime**, y encima con un texto que no significa nada para quien lee.

**El dato no está en stderr.** Ningún parser lo puede recuperar, porque ningún runtime lo imprime:
en Go el panic es un `interface{}` que se imprime por su valor y en Rust un `Box<dyn Any>` que se
imprime por `Display` si es texto y por nada si no lo es. Lo único derivable de forma determinista es
una **categoría** —Go marca `runtime error:` como prefijo; Rust tiene mensajes canónicos para
`unwrap`/`index out of bounds`—, y eso sería una taxonomía **inventada por gb**, no leída del
programa. Eso hay que decidirlo, no colarlo.

**Son dos lenguajes de dos. El criterio de aborto 1 se activa**, pero por el motivo correcto esta vez:
no porque el fallback no capture —captura—, sino porque el tipo de excepción no existe en el
material de partida.

### 3. ¿Envolver el proceso altera algo?

**Exit code: no, en 11 de 11.** Go sale 2 envuelto y sin envolver; Rust 101; el hilo secundario 0. El
parser devuelve el código del hijo tal cual. Es más limpio que los hooks nativos: en js hubo que
cambiar el gancho para conservarlo.

**stdout: idéntico en 11 de 11.** Pasa sin tocar (`stdout=sys.stdout`).

**stderr: el original lo altera en 11 de 11, y era invisible.** Mismo número de líneas, mismo texto,
y aun así distinto: el parser reemite cada línea con `sys.stderr.write(str)`, y el modo texto de
Python en Windows **traduce `\n` a `\r\n`**. Go y Rust escriben `\n`. Resultado: 7-13 bytes `\r`
inyectados en cada traza, uno por línea. Nada lo delata —ni el exit code, ni leer la salida en una
terminal— y sin embargo cualquier consumidor que compare trazas, haga hash de un log o parsee líneas
ve algo que el programa nunca escribió. Es el mismo tipo de defecto que el «Java se tragaba la traza»
de la vuelta anterior: la consola cambia lo observado y no hay señal de que lo haya hecho.

Arreglado, **Go queda byte a byte idéntico en sus 6 casos** y Rust idéntico salvo el id de hilo, que
también cambia entre dos tiradas directas.

### 4. En Rust, ¿se puede instalar `set_hook` sin tocar el código del usuario?

**No.** `std::panic::set_hook` es una función de librería que alguien tiene que **llamar en tiempo de
ejecución**, y Rust no tiene «vida antes de `main`» estable ni ninguna variable de entorno que
inyecte código:

- **Env vars:** `RUST_BACKTRACE` es la única con efecto sobre el panic, y solo decide **si se imprime
  el backtrace** — no instala nada. No existe un `RUST_PANIC_HOOK`.
- **`RUSTFLAGS`:** `rustc -C help` no ofrece ninguna opción de inyección; lo más cercano es
  `-C panic=abort`, que **cambia el comportamiento del programa** en vez de observarlo. Inyectar un
  `extern crate` requiere `-Z crate-attr`, que es **nightly**. Y en cualquier caso exige recompilar:
  el binario ya construido del usuario no se puede instrumentar.
- **`#[panic_handler]`** es solo `no_std`.
- **`LD_PRELOAD`** no aplica: el panic runtime se enlaza estáticamente, y además esta máquina es
  Windows.
- **Crate con `ctor`** (constructores en secciones del enlazador) funcionaría técnicamente, pero
  implica **añadir una dependencia al `Cargo.toml` del usuario y recompilar**. Eso es tocar el
  proyecto.

**Lo confirma el propio spike:** su hook de Rust (`experimentos/consola-multilenguaje/rust/src/`)
expone `pub fn install()` y su ejemplo lo llama a mano — `gb_hook::install();` como primera línea de
`main()`, con el comentario «do this as early as possible». El prototipo ya asume que hay que editar
el código; solo que la tabla de tiers de la ADR lo llama «parcial» en vez de decirlo.

**Consecuencia para la ADR:** Rust no es «parcial», es **igual de inviable que Go** en el eje que
importa — instalación sin tocar el código. La fila «Parciales · Rust · wrapper» debe leerse como
«fallback stderr», que es lo mismo que Go. Un hook que exige un `install()` en `main()` no es una
consola que se pone: es una librería que se adopta.

## Veredicto: ¿sirve el fallback stderr como capa universal?

**Como red de captura, sí, y mejor de lo que decía el número anterior.** No solo produce registro:
produce frames con fichero y línea, cubre el panic en goroutine secundaria que ningún hook de Go
podría cubrir, no toca el exit code, y con un parche de 4 líneas no toca la traza. Que sea la única
vía en dos lenguajes deja de ser un problema de captura.

**Como sustituto de un hook, no.** Le faltan tres cosas, y solo una tiene arreglo:

1. **El tipo de excepción no existe** (pregunta 2). Insalvable: el dato no está impreso. Un
   `gb last` sobre Go o Rust solo puede decir «panic» y enseñar el mensaje.
2. **Solo ve lo que mata al proceso.** El panic del hilo secundario de Rust —fallo real, stderr
   completo, exit code 0— pasa de largo. Los hooks nativos sí lo verían.
3. **Los defectos de formato** (schema, `\r\n`) tienen arreglo y están arreglados y remedidos aquí.

**Lo que esto propone a la ADR:** el fallback stderr no es «la capa universal que iguala a los hooks»,
es **una capa distinta con otra cobertura**: coge lo que mata al proceso en cualquier lenguaje, sin
tipo. Venderla como equivalente es lo que rompe el criterio de aborto 1; venderla por lo que es
—«murió, aquí está la traza, aquí el fichero y la línea»— es un hecho que hoy no se tiene y que en Go
no se puede tener de otra forma. Recortar el alcance a los lenguajes con hook nativo, como manda el
criterio 1 leído al pie de la letra, tiraría una captura que **sí funciona**, y con ella el único
lenguaje del grafo que no tiene alternativa.

Es una decisión de alcance, no de evidencia, y por eso se deja escrita en vez de tomada. Lo que la
evidencia sí cierra: **el «0 registros en Go» no es cierto** y no puede seguir sosteniendo el aborto.

## El parche

Tres defectos arreglables, todos fuera del repo
(`<scratchpad>/ag-gorust/banco/gb-stderr-parser-parcheado.py`), remedidos con el mismo banco:
**0/10 registros válidos → 9/10**, y **stderr byte a byte idéntico en los 6 casos de Go**.

```diff
--- experimentos/consola-multilenguaje/gb-stderr-parser.py
+++ gb-stderr-parser-parcheado.py
@@ -97,7 +97,7 @@   (build_record)
-            "argv_forma": redact_argv(child_argv),
+            "argv_forma": " ".join(redact_argv(child_argv)),
@@ -193,7 +193,7 @@   (detect_go_crash)
-        "origin": f"goroutine-{goroutine_id}",
+        "origin": "goroutine" if goroutine_id != 1 else "main",
@@ -295,7 +295,7 @@   (detect_rust_crash)
-        "origin": f"thread-{thread}",
+        "origin": "main" if thread == "main" else "thread",
@@ -420,10 +420,11 @@   (main, el tee de stderr)
         for raw_line in proc.stderr:
-            line = raw_line.decode("utf-8", errors="replace")
-            sys.stderr.write(line)
-            sys.stderr.flush()
-            stderr_chunks.append(line)
+            # Se reemite en BYTES: sys.stderr.write() traduce "\n" -> "\r\n"
+            # en Windows y eso cambiaba la traza del programa observado.
+            sys.stderr.buffer.write(raw_line)
+            sys.stderr.buffer.flush()
+            stderr_chunks.append(raw_line.decode("utf-8", errors="replace"))
```

**`gb-run.py` tiene los tres defectos, duplicados** (líneas 234, 273, 352 y 521): el spike copió los
detectores en vez de importarlos, así que arreglar uno no arregla el otro. Cualquier medida hecha con
`gb-run.py` —incluida la vuelta anterior de este banco— arrastra el `\r\n` y los registros inválidos.

## Lo que NO se pudo medir

- **`gb last` / `gb show` / `gb list` sobre estos registros (criterio 3).** No se intentó: el defecto
  ya está documentado y es anterior a Go y Rust — los hooks escriben `crashes.jsonl`,
  `store_universal.py` lee `*.crashes.jsonl` y el gb real usa `index.jsonl`. Mientras eso siga así,
  ningún lenguaje pasa el criterio 3 y estos registros tampoco.
- **`gb status` (criterio 4).** No existe.
- **El hook nativo de Rust funcionando.** Requiere `cargo build` de la librería del spike y un
  programa que llame a `install()`. No se midió porque la pregunta 4 lo saca de la categoría
  «instalable»: medir su captura no cambiaría esa respuesta.
- **`go run` como envoltura** (en vez del binario compilado). Solo se midió sobre binarios. Con
  `go run`, `GOTRACEBACK=all` sí se activa por la heurística del parser y el exit code del `go run`
  es 1, no 2 — hay una capa de proceso más en medio que no está medida.
- **Linux / macOS.** Todo esto es Windows 10. El defecto del `\r\n` es específico de Windows: en
  POSIX el parser original probablemente ya deje la traza intacta. Los otros dos defectos (schema) son
  independientes de la plataforma.
- **Panics con `recover()` parcial, `runtime.Goexit`, stack overflow y OOM.** Fuera del banco.
- **Concurrencia sobre el almacén.** No se midió, pero se observó: dos bancos escribiendo a la vez en
  `~/.galaxy-brain/crashes.jsonl` sin coordinación. Ninguna línea salió corrupta en estas tiradas,
  pero no hay nada en el prototipo que lo garantice, y sí obligó a cambiar el método de atribución.
