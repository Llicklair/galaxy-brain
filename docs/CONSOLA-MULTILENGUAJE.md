# La consola multilenguaje, medida

**Fecha:** 2026-08-18 · **Qué se mide:** el spike de la rama `spike/consola-multilenguaje`
(`cab9e29`), tal cual está · **Para qué:** decidir la [ADR 0012](adr/0012-consola-multilenguaje.md),
que hasta hoy citaba este fichero sin que existiera.

La pregunta no es si los hooks se pueden **escribir** — están escritos, son 21 ficheros. Es si
**capturan**, y si lo hacen sin cambiar el programa que observan.

## Cómo

Tres crashes por lenguaje, de formas distintas (nulo, error del runtime, excepción lanzada a mano),
ejecutados dos veces: sin hook, para tener la verdad de referencia, y con el hook por el runner del
spike (`gb-run.py`). De cada tirada se recogen el registro producido, el exit code y el stderr.

El banco corre con `HOME`/`USERPROFILE` propios por caso, porque `store_universal.py` escribe en
`Path.home()/.galaxy-brain` **fijo, sin respetar `GB_HOME`**: sin aislar, una tirada de pruebas
contamina el histórico real. Eso ya es un hallazgo — hoy el prototipo no sabe convivir con la
instalación de verdad.

Runtimes presentes en la máquina: node 24, ruby 3.3, php 8.4, lua, go, java 21, dotnet 10, rustc
1.95. **No medidos por falta de runtime:** elixir, swift, dart, kotlin, scala, C. **No medidos por
requerir compilación previa:** java (necesita `gb-agent.jar`), C# (necesita `GbHook.dll`), rust.

## Resultado

| Lenguaje | Registros válidos | Mismo exit code | Misma traza | Vía |
|---|---|---|---|---|
| **js** | **3/3** | **no — 1 → 7** → **sí tras `8e7a8f9`** | **no** → **idéntica** | `NODE_OPTIONS --require` |
| **ruby** | **3/3** | sí | idéntica (el ruido era del runner) | `RUBYOPT -r` |
| php | 0/3 por el runner · **1/1 a mano** | sí | sí | `-d auto_prepend_file`, **no automático** |
| lua | 0/3 | sí | **no — hook en la traza** | `LUA_INIT` |
| go | **0/1** | — | — | fallback stderr |
| python | fuera del spike | sí | sí | lo captura el gb ya instalado |

Los 7 registros obtenidos **validan todos** contra el schema v2 (0 inválidos): cuando captura, el
formato es correcto y trae `exception.type` de verdad (`TypeError`, `NoMethodError`,
`ZeroDivisionError`, `ArgumentError`), no un genérico.

## Los cinco criterios de terminado de la ADR

1. **≥3 crashes producen registros correctos** — cumplen **js** y **ruby**. `php` solo si instalas el
   hook a mano; el runner se limita a exportar `GB_PHP_HOOK` y decirte el flag que tienes que
   escribir tú. La ADR lo clasifica entre los «viables, install por env-var, **zero code changes**»:
   eso hoy no es cierto.
2. **Validan contra el schema v2** — ✅ los 7.
3. **`gb last/show/list` funcionan sin modificación** — **no se puede**, y no por poco: los hooks
   nativos escriben `~/.galaxy-brain/crashes.jsonl`, `store_universal.py` lee `*.crashes.jsonl` —un
   glob que **no casa ese nombre**— y el gb real usa `index.jsonl` con otro formato. Tres
   convenciones para un almacén que la ADR describe como «agnóstico».
4. **`gb status` declara el mecanismo activo** — no existe.
5. **El hook no altera el programa observado** — **falla en 3 de 4** lenguajes que capturan algo.

## Lo que mata la propuesta tal como está

**El criterio 5, y no es cosmético.** En js el exit code pasa de **1 a 7**. Cualquier script, CI o
`Makefile` que mire el código de salida se comporta distinto por tener la consola puesta. Una
herramienta de observación que cambia lo observado deja de ser una observación — y el proyecto ya
tiene esa regla escrita (ARCHITECTURE, propiedad 5: si la captura falla, el programa sigue **como si
la consola no existiera**). Aquí no falla la captura: funciona, y aun así cambia el programa.

### Pero en js tiene arreglo, y es una palabra

Segundo banco, sobre el mismo defecto: cinco formas distintas de enganchar un hook en Node, tres
crashes cada una (nulo, lanzado, asíncrono), comparando contra el programa sin hook.

| Variante | Captura el error | Mismo exit code | Misma traza |
|---|---|---|---|
| `uncaughtException` + `throw err` (**lo que hace el spike**) | sí | **no — 1 → 7** | **no** |
| `uncaughtException` + `console.error` + `exit(1)` | sí | sí | **no** |
| `uncaughtException` + quitar el listener y relanzar | sí | **no — 1 → 7** | **no** |
| `diagnostics_channel` | **no** | sí | sí |
| solo el evento `exit` | solo el código | sí | sí |
| **`uncaughtExceptionMonitor`** | **sí, entero** | **sí** | **sí** |

**`process.on('uncaughtExceptionMonitor')` es 3/3 perfecta**: da el error completo —`TypeError`,
mensaje, origen, 10 frames— y el proceso muere exactamente como habría muerto. Es el evento que Node
tiene justo para esto: suscribirse **no cuenta como manejar** la excepción, así que el runtime sigue
su curso por defecto.

El defecto no era un límite de Node. Era elegir el gancho equivocado, y el cambio es
`uncaughtException` → `uncaughtExceptionMonitor`. **Aplicado al spike** (`8e7a8f9`, rama
`spike/consola-multilenguaje`) y vuelto a medir con el banco:

| | antes | después |
|---|---|---|
| registros válidos (js) | 3/3 | 3/3 |
| mismo exit code | **no — 1 → 7** | **sí** |
| traza, con `--require` directo | **no** | **idéntica byte a byte** |

### Y la traza de ruby tampoco era culpa del hook

Al remedir apareció que `ruby` seguía marcando «traza distinta» aun sin tocar nada. Instalado
directamente (`ruby -r gb-hook.rb`) la traza es **idéntica** y el exit code también. Lo que
ensuciaba stderr era **el runner**, `gb-run.py`, que mete una línea en blanco antes de la salida del
programa. Defecto suyo, no de los hooks, y de otro tamaño.

Corregido eso, **js y ruby cumplen el criterio 5 de punta a punta**: capturan el error entero y el
programa muere exactamente como habría muerto.

Queda por comprobar si los demás runtimes tienen su equivalente —un gancho de *observación* frente a
uno de *manejo*—, porque ese es el eje que decide el criterio 5, no la lista de lenguajes. Y sigue
siendo cierto que un hook que se puede escribir no es un hook que captura: `lua` engancha y no
registra nada.

> **Nota de método.** El primer intento de medir esto dio "no escribe el registro" y era **falso**:
> el banco pasaba una ruta POSIX de Git Bash a un binario nativo y Node la resolvía como `C:\tmp\…`
> — la trampa del árbol fantasma, ya escrita en las notas de esta máquina, mordiendo otra vez. Un
> banco que se equivoca hacia "no funciona" es tan peligroso como uno que se equivoca hacia "sí":
> este estuvo a punto de cerrar una ADR por un fallo suyo.

**El fallback stderr no cierra la cola.** La ADR lo presenta como la capa universal —«todo runtime
imprime a stderr cuando muere»— y es lo único que cubre Go, el lenguaje sin hook posible. Medido:
**0 registros**. La cola queda abierta.

Con eso se activa el **criterio de aborto 1** que la propia ADR escribió: *«Si el fallback stderr no
distingue tipo de excepción del mensaje en ≥2 lenguajes, se recorta el alcance a solo los lenguajes
con hook nativo»*. Y el recorte deja **js y ruby**, ambos suspendiendo el criterio 5.

## Segunda vuelta (18-ago): el banco del escritorio, y un fallo de método

`gb-lenguajes/hooks` trae lo que la copia del repo no tenía —`gb-agent.jar` y `GbHook.dll`
compilados—, así que se pudieron medir **Java y C#**, los dos que la ADR pone entre los «viables» y
que se habían quedado sin probar.

Y al medirlos apareció que **el banco de la primera vuelta estaba mal**. Aislaba cada tirada
poniendo `HOME`/`USERPROFILE`, y eso funciona en Node, Ruby, PHP y Lua pero **no** en Java, C#, Go ni
Rust: sus runtimes resuelven el home por otra vía (en la JVM, `user.home` sale del SO, no del
entorno del proceso). Sus registros se escribían en el fichero real mientras el banco miraba el
aislado, así que informaba «SIN REGISTRO» sobre hooks que funcionaban. Segunda vez que este banco se
equivoca hacia «no funciona».

Con el método arreglado —no aislar, sino **marcar**: contar el fichero antes y atribuir solo las
líneas nuevas— y el fichero acumulado revisado, la foto es otra:

| Lenguaje | Registro válido | Mismo exit code | Misma traza |
|---|---|---|---|
| **js** | 3/3 | sí *(tras `8e7a8f9`)* | idéntica *(tras `8e7a8f9`)* |
| **ruby** | 3/3 | sí | idéntica |
| **java** | sí | sí | **no** → **idéntica** *(tras `86c944d`)* |
| **csharp** | sí | sí | idéntica |
| php | sí *(hook a mano)* | sí | idéntica |
| go · rust · lua | registros válidos en el fichero acumulado, **no medidos limpiamente aquí** | — | — |

De los registros acumulados en `~/.galaxy-brain/crashes.jsonl` —mezcla de pruebas previas y de este
banco, 8 lenguajes— **el 91 % trae todos los campos que el schema marca como `required`**.

> **Corrección (18-ago).** Aquí se afirmó que «23 de 26 validan contra el schema v2». **Era
> engañoso**, y lo destapó el agente que estudió el almacén. Yo comprobaba solo que los campos
> `required` estuvieran presentes y no vacíos; pasando los mismos registros por
> `store_universal.validate()` —el validador que el propio spike escribió para esto— pasan **9 de
> 105**. La causa dominante no es un campo que falte: es que `exception.origin` declara un enum que
> **ningún hook respeta** (`goroutine-1`, `thread-main`, `xpcall`, `uncaught_exception`…), más
> divergencias de tipo (`pid` como string, `argv_forma` como lista donde el schema dice string).
>
> **El criterio 2 de la ADR tampoco está pasado.** No son tres convenciones de almacén: son ocho
> dialectos que se parecen lo bastante como para que una comprobación superficial los dé por buenos
> — que es exactamente lo que hizo la mía.

### El fallo más caro no es un campo: es el ORDEN de los frames

Ningún inventario de campos lo habría encontrado. `render._headline_index` recorre la pila hacia
atrás para elegir el frame que sale de titular, porque **Python emite el más interno el último**. js,
java, csharp, ruby, php, go y rust la emiten **al revés**.

Verificado sobre un registro js real de 9 frames: el titular que elige gb es
`node:internal/main/run_main_module:33` —el arranque de Node— en lugar de `crash_js.js:1`, que es la
línea que reventó. No lanza excepción, no avisa, y el usuario ve una captura con pinta de correcta
apuntando al sitio equivocado. El peor modo de fallo de toda la consola, en la única función cuyo
trabajo es decidir dónde mirar primero.

### Java se tragaba la traza entera

El defecto más grave encontrado, y no se parecía a un defecto: con el agente puesto,
`String s = null; s.length()` no imprimía **nada**. Sin él, su `NullPointerException` con fichero y
línea. La consola borraba lo único que el programa seguía diciendo, y el exit code seguía siendo 1,
así que nada delataba la pérdida.

`Thread.setDefaultUncaughtExceptionHandler` **sustituye** al default de la JVM — y ese default no es
un handler: la traza la imprime el `ThreadGroup` justo cuando no hay ninguno instalado. El agente
encadenaba a `previousHandler`, que en el caso normal es `null`.

La solución obvia también es una trampa: delegar en `thread.getThreadGroup().uncaughtException()`
vuelve a consultar el default handler —nosotros— y entra en **bucle infinito**. Se replica el
default a mano. Medido: mismo exit code y traza idéntica (`86c944d`).

**Es el mismo error que en js, en otro lenguaje**: engancharse donde se *maneja* en vez de donde se
*observa*. Dos de dos. Ese es el eje por el que hay que reordenar la tabla de tiers de la ADR, y
ahora hay dos casos que lo sostienen en vez de uno.

## Tercera vuelta (18-ago): tres mediciones en paralelo

Tres agentes sobre territorios disjuntos — php+lua, go+rust, y el almacén. Detalle en
[medicion-php-lua.md](medicion-php-lua.md), [medicion-go-rust.md](medicion-go-rust.md) y
[propuesta-almacen-unificado.md](propuesta-almacen-unificado.md). Lo que sigue está verificado
aparte antes de darlo por bueno.

### El eje observación/manejo va 4 de 4

Ya no es un patrón que se repite: es **el** criterio. Los cuatro hooks que capturaban estaban
enganchados donde se *maneja*, y los cuatro rompían el programa observado de una forma distinta:

| Lenguaje | Qué hacía el hook | Qué le hacía al programa |
|---|---|---|
| js | `uncaughtException` + re-lanzar | exit 1 → **7**, frames del hook en la traza |
| java | `setDefaultUncaughtExceptionHandler` | **borraba la traza entera** |
| **php** | `set_exception_handler` | **exit 255 → 0** y borraba el `Fatal error` |
| lua | wrapper que re-lanza con `error(err,0)` | la traza pasaba a ser la del hook |

**php es el peor de los cuatro**, y verificado a mano: `stdout` de 374 bytes a **0**, exit **255 →
0**. Con la consola puesta, un crash de PHP **pasa en verde en cualquier CI**. Decirle a PHP que la
excepción está atendida es exactamente eso: atenderla.

Y lua enseña por qué «mismo exit code» no basta como control: su hook impedía que el programa
**llegara a ejecutarse** —el runner lo cargaba por `LUA_INIT`, donde el `arg[1]` que espera no
existe, así que imprimía `Usage:` y salía— y la columna del exit code decía «sí», porque el crash de
lua también sale con 1. Una coincidencia numérica tapando la destrucción total.

Los cuatro tienen arreglo y los cuatro son el mismo: buscar el punto de **observación**
(`uncaughtExceptionMonitor`, replicar el default de la JVM, `register_shutdown_function` +
`error_get_last`, el message handler de `xpcall`). En php el arreglo es **restar**: 274 → 152 líneas.

### Go y Rust: el fallback funciona, y aun así no sirve

Mi «0 registros en Go» era **falso** — el tercer fallo de método del mismo banco, y el segundo hacia
el «no». Captura **10 de 11 casos**, incluido el panic en goroutine secundaria, justo donde
`recover()` no llega.

Pero `exception.type` vale **`panic`** en los 40 registros de go y rust. No es un defecto del
parser: **el dato no está en stderr**. `panic(&ErrorDeNegocio{})` imprime `panic: codigo 42` sin el
tipo, y `panic_any(...)` imprime `Box<dyn Any>` con el tipo ya borrado por el runtime.

> Eso activa el **criterio de aborto 1** de la ADR, escrito antes de medir nada: *«Si el fallback
> stderr no distingue tipo de excepción del mensaje en ≥ 2 lenguajes, se recorta el alcance a solo
> los lenguajes con hook nativo»*. Dos lenguajes de dos. Se activa por el motivo correcto, y por eso
> vale.

Y **Rust no es «parcial»**: `std::panic::set_hook` no se instala sin tocar el código del usuario —no
hay variable de entorno, y el propio spike llama a `install()` a mano en su `main.rs`—. Es tan
inviable como Go. Su panic en hilo secundario deja exit 0, stderr completo y **cero registros**: el
fallback solo ve lo que mata al proceso.

Un defecto más, invisible: el tee del parser escribía con `sys.stderr.write` en modo texto, y Windows
traduce `\n` → `\r\n`. **11 de 11 casos** salían con `\r` que el programa nunca escribió.

### La tabla de tiers falla en las dos direcciones

php **baja** (no hay env-var: `auto_prepend_file` es directiva de `.ini`, y el runner solo exporta
una variable y te dice el flag a mano → **0 registros por esa vía**) y lua **sube** (`LUA_INIT` sí
instala transparente). Que se equivoque en ambos sentidos es la prueba de que el eje que la ordena
—«¿hay hook instalable por env-var?»— no predice nada. El que predice es observación vs manejo.

## Cuarta vuelta (18-ago): ruby y csharp, y los casos que un observador aún estropea

Los dos capturaban bien, pero nadie los había mirado por el eje nuevo. Y el crash normal no es
donde se rompe un hook de observación: se rompe en los bordes. Cinco casos por lenguaje —crash,
salida limpia, exit code propio, stdout antes de morir, excepción en hilo secundario—, cada uno con
una tirada de **control** sin hook para separar el ruido del runtime de lo que hace el hook.

| Métrica | Antes | Después |
|---|---|---|
| programa observado intacto | 90 % (9/10) | **100 % (10/10)** |
| exit code preservado | 100 % | **100 %** |
| stdout idéntico | 100 % | **100 %** |
| stderr idéntico | 90 % | **100 %** |
| crashes capturados | 100 % (6/6) | **100 % (6/6)** |
| **registros espurios** (sin crash) | **25 % (1/4)** | **0 % (0/4)** |

Por lenguaje: **csharp 100 % (5/5) sin tocar una línea** — su `AppDomain.UnhandledException` no puede
impedir la terminación, así que es observación por construcción. **ruby 80 % → 100 %**.

### El defecto de ruby: `exit 3` también es una excepción

`at_exit` miraba `$!` sin filtrar, y en Ruby una salida deliberada es un `SystemExit`. Un CLI que
sale con 3, o un script que hace `exit 1` después de informar, dejaba una captura de un fallo que
nunca ocurrió. No es cosmético: un histórico con salidas normales dentro deja de significar nada, y
lo que no significa nada se deja de mirar — que es cómo muere un termómetro.

El arreglo es una condición. El mecanismo ya estaba en el lado bueno del eje; lo que faltaba era el
filtro.

### Y el banco se equivocaba en un 20 %

Acusaba al hook de alterar el stderr del caso `hilo`. Lo que cambia ahí es **la dirección de memoria
del objeto Thread**, distinta en cada ejecución aunque no haya hook. Sin tirada de control, el banco
le cobraba al hook el no determinismo del runtime.

## Quinta vuelta (18-ago): ts y tsx, sin instalar nada

Node 24 ejecuta TypeScript nativo (`--experimental-strip-types`), así que **ts se pudo medir con lo
que ya había**. Mismos 5 casos límite, mismo método con tirada de control:

| Métrica | ts |
|---|---|
| programa observado intacto | **100 % (5/5)** |
| crashes capturados | **100 % (3/3)** |
| registros espurios | **0 % (0/2)** |

Y el hook etiqueta bien: `language: "ts"` cuando algún frame apunta a un `.ts`, `"js"` si no. El
mismo hook de Node, sin un cambio.

### `tsx` no tiene runtime, y eso es la respuesta

Node **no ejecuta `.tsx`**: `--experimental-strip-types` no soporta JSX, y falla en la primera
etiqueta. No es una limitación que haya que rodear — es que **un `.tsx` nunca es lo que corre**.
Siempre pasa antes por un transpilador (esbuild, swc, vite, Next), y lo que el runtime ejecuta es
JavaScript. El crash ocurre en Node, con la pila apuntando al `.tsx` original si hay source maps.

Así que **tsx no necesita hook propio: hereda el de Node**, que ya está verificado. La única
consecuencia es de etiquetado: el hook resuelve `/\.tsx?$/` a `"ts"`, así que una captura de un
`.tsx` se guarda como `ts`. El grafo sí los distingue (son dos entradas de la tabla). Es una
discrepancia menor, y queda declarada aquí en vez de descubrirse mirando un informe raro.

## Qué se puede afirmar, y qué no

**Sí:** el eje está encontrado y el formato aguanta. **6 lenguajes verificados, 6 con gancho de
observación** — js, java, php, lua necesitaron arreglo; csharp y ruby ya estaban en el lado bueno
(ruby con un filtro de menos). Los seis capturan con registro y dejan el programa observado intacto:
**100 % en exit code, stdout y stderr**.

**No:** que esté terminada. Falta el criterio 4 (`gb status`), y 6 de los 16 lenguajes no se han
podido probar en esta máquina por falta de runtime. Pero ya no hay ningún bloqueo estructural: lo
que queda es trabajo acotado, no una incógnita.

### Marcador por criterio

| Criterio de terminado | Estado |
|---|---|
| 1. ≥3 crashes producen registros correctos | **8 de 16 resueltos** (7 medidos + tsx por herencia); 2 fuera por el criterio de aborto; 6 sin runtime en esta máquina |
| 2. Validan contra el schema v2 | **9 % (9/105)** — el enum `exception.origin` no lo respeta ningún hook |
| 3. `gb last/show/list` sin modificación | **cumplido** (`94bcef7`) — buzón + normalización; `store.py` y `render.py` con **cero líneas** de cambio |
| 4. `gb status` declara el mecanismo | **no existe** |
| 5. El hook no altera el programa | **100 %** en los siete medidos, tras cinco arreglos |

**Recomendación:** la [ADR 0012](adr/0012-consola-multilenguaje.md) sigue en **propuesta**, con el
alcance ya recortado por su propio criterio de aborto. Lo que queda, por orden:

1. ~~Cambiar el gancho en js~~ · ~~java~~ · ~~php~~ · ~~lua~~ · ~~ruby~~ — **hechos y medidos**.
2. ~~Una sola convención de almacén~~ — **hecho** (`94bcef7`). `crashes.jsonl` pasa a ser un buzón
   y una función lo traduce al almacén de siempre; `store.py` y `render.py` con cero líneas de
   cambio. Lo caro no era mapear campos: el orden de los frames estaba invertido en siete lenguajes,
   así que la captura se pintaba apuntando al arranque del runtime sin lanzar un error.
3. **`gb status`** (criterio 4).
4. **Los lenguajes sin runtime aquí** — elixir, swift, dart, kotlin, scala, C: primero la pregunta
   del eje, y solo después medir.

Lo que ya **no** procede es cerrarla por el exit code, ni aceptarla con los criterios 3 y 4 a cero.

### Advertencia sobre este documento

Sus números han cambiado **cuatro veces por fallos del banco**, no del código:

| Fallo del método | Dirección del error |
|---|---|
| ruta POSIX pasada a un binario nativo (dos veces) | «no funciona» |
| aislamiento de `HOME` que cuatro runtimes ignoran | «no funciona» |
| validación superficial dada por buena (`required` sin tipos ni enums) | «sí funciona» |
| bancos concurrentes atribuyéndose registros ajenos | ambas |
| sin tirada de control para el ruido no determinista | «no funciona» |

**Cuatro de cinco apuntaban al «no»**, y el primero estuvo a punto de cerrar la ADR. Un banco que se
equivoca hacia el no es más peligroso que uno que se equivoca hacia el sí, porque un resultado
negativo no invita a comprobar nada: se archiva. Cualquier cifra de aquí que vaya a decidir algo se
remide antes, y con tirada de control.

## Reproducirlo

Los bancos son scripts sin dependencias que extraen el spike de su rama con `git archive`, montan
los casos y comparan contra una ejecución sin hook. Viven fuera del repo a propósito (son
experimentos, no código de gb); lo que queda aquí son los números. El material de los lenguajes está
en `Desktop/gb-lenguajes`.
