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

## Qué se puede afirmar, y qué no

**Sí:** el patrón se repite y el formato aguanta. Escribir un hook por lenguaje que produce un
registro v2 correcto es viable — hay dos funcionando y un tercero a un flag de distancia.

**No:** que esto esté cerca de entrar. Ningún lenguaje pasa los cinco criterios; el almacén no habla
consigo mismo; y 6 de los 16 lenguajes ni siquiera se han podido probar en esta máquina.

**Recomendación:** la [ADR 0012](adr/0012-consola-multilenguaje.md) se queda en **propuesta**, y el
siguiente paso no es añadir lenguajes. Por orden:

1. ~~Cambiar el gancho en js~~ — **hecho** (`8e7a8f9`), 3/3 perfecto.
2. **Una sola convención de almacén.** Hoy son tres y no se leen entre sí. Mientras eso siga así,
   `gb last/show/list` no puede ver nada de lo que capturan los hooks (criterio 3), y da igual
   cuántos lenguajes se añadan.
3. **Quitar el ruido del runner** en stderr: una línea en blanco de más basta para suspender el
   criterio 5 de todos los lenguajes a la vez, y no tiene nada que ver con ellos.
4. **Buscar el gancho de observación en cada runtime.** El eje que decide no es «¿hay hook
   instalable por env-var?» sino **«¿hay un gancho de OBSERVACIÓN o solo uno de MANEJO?»**. La tabla
   de tiers de la ADR está ordenada por el eje equivocado, y este banco es la prueba: js estaba en
   la casilla buena por el motivo equivocado.
5. **Decidir qué se hace con Go**, donde no hay hook y el fallback no registró nada.

Lo que ya **no** procede es cerrarla por el exit code. Lo que tampoco procede es aceptarla: **js,
ruby, java y csharp pasan hoy los criterios 1, 2 y 5**, pero el 3 y el 4 no los pasa nadie —el
almacén no habla consigo mismo y `gb status` no existe—, y quedan lenguajes sin probar.

### Advertencia sobre este documento

Sus números han cambiado **dos veces** por fallos del banco, no del código: una ruta POSIX pasada a
un binario nativo, y un aislamiento de `HOME` que cuatro runtimes ignoran. Las dos veces el error
apuntaba en la misma dirección —«no funciona»— y la primera estuvo a punto de cerrar la ADR.

Un banco que se equivoca hacia el no es tan peligroso como uno que se equivoca hacia el sí, y es
más fácil de creerse: un resultado negativo no invita a comprobar nada. Cualquier cifra de aquí que
vaya a decidir algo se remide antes.

## Reproducirlo

El banco es un script sin dependencias que extrae el spike de su rama con `git archive`, monta los
casos y compara. Vive fuera del repo a propósito (es un experimento, no código de gb); lo que queda
aquí son los números.
