# 12. Consola multilenguaje por mecanismo nativo + fallback stderr

**Estado:** propuesta **decidible** — alcance recortado por su propio criterio de aborto; **4 de 5 criterios cumplidos y demostrados**, solo falta `gb status` · **Fecha:** 2026-08-16 · **Supercede (solo el eje lenguaje):** [0004](0004-un-lenguaje-un-runtime-un-tipo-de-fallo.md) · **Extiende:** [0009](0009-multilenguaje-por-referencia.md)

> **La medición está hecha: [CONSOLA-MULTILENGUAJE.md](../CONSOLA-MULTILENGUAJE.md).** De 6 lenguajes
> probados, capturan 2 por el camino que este ADR describe (js y ruby, 3/3 cada uno, registros
> válidos contra el schema). Los dos **suspenden el criterio 5**: js cambia el exit code de 1 a 7 y
> mete sus frames en la traza. El fallback stderr, que aquí se presenta como la capa universal, dio
> **0 registros** en Go — el único lenguaje donde es la única vía. Eso activa el criterio de aborto 1
> escrito más abajo. Y el almacén tiene tres convenciones de fichero incompatibles entre sí.
>
> **El exit code tenía arreglo, y era una palabra:** `uncaughtException` →
> `uncaughtExceptionMonitor`, el evento que Node tiene para observar sin manejar. **Aplicado**
> (`8e7a8f9`) y remedido: 3/3, captura el error entero y el proceso muere exactamente igual. Con eso,
> **js y ruby pasan los criterios 1, 2 y 5**.
>
> **QUINTA vuelta (18-ago) — el criterio 3 está CUMPLIDO** (`94bcef7`, rama del spike).
> `crashes.jsonl` pasa a ser un **buzón**, no un almacén: `buzon.normaliza()` traduce y
> `buzon.drena()` pasa las líneas nuevas al almacén de siempre con marca de agua por bytes.
> **`store.py` y `render.py` no cambian ni una línea** —comprobado con `git diff` contra
> `main`— que es lo que el criterio pedía literalmente. Demostrado con el CLI de verdad:
> 17 registros reales de 8 lenguajes, `gb list` rc=0, y `gb show` pintando una captura de
> Java en `CrashTest.java:3`. 14 tests nuevos; 900 en verde.
>
> Y con él se cae `store_universal.py` entero: su glob no casaba su propio fichero, su
> validador rechazaba 24 de 24 registros suyos, y usaba `Path.home()` fijo ignorando
> `GB_HOME`.
>
> **Queda el criterio 4** (`gb status` declarando el mecanismo activo) y los seis lenguajes
> sin runtime en esta máquina. Nada más.
>
> **CUARTA vuelta (18-ago) — el eje va 6 de 6.** csharp y ruby, verificados por el eje nuevo sobre 5 casos límite cada uno (crash, salida limpia, exit code propio, stdout antes de morir, excepción en hilo): **programa observado intacto 100 % (10/10)** en exit code, stdout y stderr, y **registros espurios 25 % → 0 %**. csharp pasó los cinco sin tocar una línea. A ruby le faltaba un filtro: `exit 3` es un `SystemExit`, así que capturaba salidas normales como si fueran fallos.
>
> **Lo que queda es el criterio 3, y solo ese.** Nadie lo pasa, y no es mapear campos: el
> orden de los frames está invertido en siete lenguajes, así que la captura se pinta
> apuntando al arranque del runtime en vez de a la línea que reventó, sin lanzar un error.
> El criterio 4 (`gb status`) tampoco existe.
>
> **TERCERA vuelta (18-ago) — el criterio de aborto 1 de este mismo ADR se activa.** El fallback
> stderr no distingue el tipo de excepción del mensaje en **go ni en rust**: `exception.type` vale
> `panic` en los 40 registros, y el dato **no está en stderr** (`panic_any` borra el tipo en el
> runtime). Dos lenguajes de dos. Así que el alcance se recorta a los lenguajes con gancho nativo, y
> **go y rust quedan fuera** — rust incluido, porque `set_hook` no se instala sin tocar el código del
> usuario: no es «parcial», es inviable.
>
> **El eje correcto va 4 de 4** (js, java, php, lua): lo que decide no es «¿hay hook instalable por
> env-var?» sino **«¿el gancho OBSERVA o MANEJA?»**. Los cuatro que capturaban manejaban, y los
> cuatro rompían el programa. El peor, php: `set_exception_handler` borra el `Fatal error` y cambia
> el exit code de **255 a 0** — con la consola puesta, un crash pasa en verde en cualquier CI.
> La tabla de tiers de más abajo se equivoca en **las dos direcciones** (php sobra de «viables», lua
> falta), que es la prueba de que ordena por el eje que no predice.
>
> **Segunda vuelta (18-ago), con los hooks compilados del banco `gb-lenguajes`:** java y csharp
> también capturan con registro válido. Java tenía el defecto más grave de todos — el agente
> **borraba la traza entera** del programa observado, sin que el exit code lo delatara — y es el
> mismo error que js en otro lenguaje: engancharse donde se *maneja* en vez de donde se *observa*.
> Arreglado y medido (`86c944d`). **Reordenar la tabla de tiers por ese eje ya no es una hipótesis:
> hay dos casos.**
>
> Lo que bloquea ahora no son los lenguajes: es el **criterio 3**. Los hooks escriben
> `crashes.jsonl`, `store_universal.py` lee `*.crashes.jsonl` —un glob que no casa ese nombre— y el
> gb real usa `index.jsonl`. Mientras el almacén no hable consigo mismo, `gb last/show/list` no ve
> nada de lo capturado y da igual cuántos lenguajes se añadan. El criterio 4 (`gb status`) tampoco
> existe.
>
> Y la tabla de tiers de más abajo está ordenada por el eje equivocado. Lo que decide no es «¿hay
> hook instalable por env-var?» sino **«¿hay un gancho de OBSERVACIÓN o solo uno de MANEJO?»** — el
> primero respeta el criterio 5, el segundo lo suspende por construcción. Reordenarla por ese eje es
> trabajo pendiente de este ADR.

> **Numeración:** este ADR es el 12 y no el 11 porque el 0010 está usado dos veces
> ([el tercer rechazo](0010-el-tercer-rechazo-tiene-que-ganarselo.md) y [repos
> mixtos](0010-repos-mixtos-los-dos-motores-conviven.md), que de facto es el 11). No se
> renumera lo ya commiteado y citado; se gasta el número y se deja escrito.

## Contexto

La consola de errores era exclusivamente Python ([ADR 0004](0004-un-lenguaje-un-runtime-un-tipo-de-fallo.md)). El razonamiento era sólido: cada eje de generalidad multiplica coste, y `sys.excepthook` no tiene equivalente portable. El grafo, en cambio, ya lee **17 lenguajes** (Python con `ast`; los otros 16 con `ast-grep` por referencia, [ADR 0009](0009-multilenguaje-por-referencia.md) y [ADR 0010](0010-repos-mixtos-los-dos-motores-conviven.md)).

**Lo que cambió desde entonces:**

- Un usuario de un repo multi-lenguaje obtiene grafo + selección de tests pero **cero captura de crashes** para todo lo que no sea Python. El valor de la consola desaparece en el lenguaje mayoritario del ecosistema de agentes (JS/TS).
- Un **spike** barrió los 16 lenguajes no-Python del grafo y escribió un hook por lenguaje para ver si el patrón se repetía. Vive en la rama `spike/consola-multilenguaje` (commit `cab9e29`), fuera de `main` y fuera del paquete:

La tabla original clasificaba por «¿se instala por variable de entorno?». **Ese eje no predice
nada** — se equivocó en las dos direcciones a la vez (PHP estaba entre los viables y no lo es; Lua
estaba entre los parciales y sí instala transparente). El eje que decide, medido 4 de 4, es otro:

| Categoría | Lenguajes | Estado |
|---|---|---|
| **Gancho de OBSERVACIÓN** — el runtime sigue su curso; capturar no cambia el programa | **js · java · php · lua · csharp · ruby** | **6 verificados, 6 en el lado bueno.** Cuatro necesitaron arreglo (`uncaughtExceptionMonitor`, replicar el default de la JVM, `register_shutdown_function`+`error_get_last`, message handler de `xpcall`); csharp y ruby ya estaban — `AppDomain.UnhandledException` no puede impedir la terminación, y `at_exit` solo mira. A ruby le faltaba filtrar `SystemExit`, que es un filtro, no el mecanismo |
| **Sin medir** — falta el runtime en la máquina | kotlin, scala, elixir, swift, dart, C | primero la pregunta del eje (¿observa o maneja?), y solo después medir. Kotlin y Scala corren sobre la JVM, así que heredarían el agente ya arreglado |
| **Sin gancho instalable** | **go**, **rust** | **fuera** (ver abajo): `recover()` es por goroutine; `set_hook` exige tocar el código del usuario |

Lo que cuesta equivocarse de eje, medido: los cuatro hooks del primer grupo **rompían el programa
observado** antes de arreglarlos — js cambiaba el exit code, java borraba la traza, lua impedía que
el programa se ejecutara, y php hacía las dos cosas a la vez (255 → 0, `Fatal error` borrado).

- ~~**El fallback universal existe:** todo runtime imprime a stderr cuando muere.~~ **Descartado el
  18-ago por el criterio de aborto 1 de este mismo documento.** Sí produce registros (10 de 11 casos
  en Go, incluido el panic en goroutine secundaria), pero **no distingue el tipo del mensaje**:
  `exception.type` vale `panic` en los 40 registros de go y rust, y el dato **no está en stderr** —
  `panic_any` lo borra en el runtime. Con go y rust sin otra vía, quedan fuera del alcance.

> **Lo que este ADR NO tiene todavía:** el spike demuestra que los hooks se pueden
> **escribir**, no que **capturen**. No hay una sola medida de crashes reales por
> lenguaje. Mientras no exista, esto es una propuesta, no una decisión — y la regla
> de evidencia del proyecto la rechaza como está.

## Decisión (propuesta)

**Extender la consola a los 16 lenguajes no-Python** usando dos capas:

1. **Hook nativo** donde es viable: un fichero por lenguaje (`hooks/{lang}/`) instalado vía variable de entorno, sin tocar código del usuario. Captura la excepción, serializa un **registro JSON schema v2** (el mismo que ya produce el hook Python) y lo escribe al almacén de gb.

2. **Fallback stderr** como capa universal: para los lenguajes sin hook viable (Go) y como degradación cuando el hook no está instalado. Parsea la salida de error, extrae tipo + mensaje + traza, y produce el mismo registro schema v2 con los campos que faltan marcados como `null`.

**Principios de diseño:**

- **El almacén y la CLI son agnósticos al lenguaje.** `gb last`, `gb show` y `gb list` ya operan sobre registros JSON; lo único que cambia es que `language` deja de ser siempre `"python"`.
- **Cada hook se instala por variable de entorno.** `gb on` la configura; `gb off` la quita. Mismo mecanismo que `sys.excepthook` hoy, cambiando el fichero y la env-var.
- **El hook no se activa si el lenguaje no se detecta.** `gb on` en un repo sin `package.json` no instala el hook de Node. La detección reutiliza la del grafo.
- **`gb status` declara qué capas están activas**, incluyendo si un lenguaje usa hook nativo o fallback.

## Consecuencias

- La restricción «un lenguaje» de [ADR 0004](0004-un-lenguaje-un-runtime-un-tipo-de-fallo.md) queda supercedida **solo en el eje lenguaje** ([enmienda](0004-enmienda-multilenguaje.md)). Los otros dos — un runtime (local) y un tipo de fallo (excepciones no capturadas) — **no cambian**.
- [SCOPE.md](../../SCOPE.md) tendría que cambiar la fila «Lenguaje (consola)» de «Python. Uno.» a los tres tiers, y la **regla 3 de [CLAUDE.md](../../CLAUDE.md)** está escrita hoy como «un runtime, un tipo de fallo — y el grafo con dos motores»: aceptar esto obliga a reescribirla. No es una nota al pie, es la decisión.
- La sección «No es multi-lenguaje» de SCOPE.md se matiza: **sí** lo es (grafo y consola), pero **no es multi-runtime** en el sentido de ejecutar otros runtimes dentro de gb.
- El front-end del grafo (`viz`, mapa, `who --html`) **no se toca**.
- El schema v2 añade `language` obligatorio, y los campos de estado (`locals`, `globals`) pasan a opcionales: el fallback stderr no los tiene.

## Criterio de terminado, por lenguaje

Un lenguaje se considera «cubierto» cuando:

1. **≥ 3 crashes provocados** deliberadamente en ese lenguaje producen registros correctos.
2. Cada registro **valida contra el schema v2**.
3. `gb last`, `gb show` y `gb list` **funcionan sin modificación** sobre ellos.
4. `gb status` **declara el mecanismo activo** (hook nativo / fallback stderr / desactivado).
5. El hook **no altera el comportamiento del programa observado**: misma traza, mismo exit code, mismo output.

## Criterios de aborto, escritos ahora que no duele

1. **Si el fallback stderr no distingue tipo de excepción del mensaje en ≥ 2 lenguajes**, se recorta a los lenguajes con hook nativo. Un `gb last` que dice «algo petó» sin decir qué es peor que no tener consola.
2. **Si mantener los hooks de 3+ lenguajes genera más bugs que los que captura**, se congela en los que funcionen y el resto queda en fallback-only.
3. **Si `gb on` tarda > 1 s** en configurar las variables, se paraleliza o se acepta la lista explícita.

## Lo que NO cambia

- **El front-end del grafo** — `viz.py`, `mapa.html`, `who --html`.
- **El tipo de fallo** — excepciones no capturadas. Ni logs, ni errores de negocio, ni señales.
- **El modelo de runtime** — ejecución local. No CI, no contenedores, no remoto.
- **El presupuesto de latencia** — los hooks son dormant (coste cero hasta que algo falla); el parser de stderr corre después de que el proceso muera.
- **La instalación** — cero dependencias. Los hooks son ficheros que gb despliega; los runtimes los pone el usuario.

## Siguiente paso, antes de aceptar esto

Medir el spike: provocar crashes reales en cada lenguaje y contar cuáles producen un registro válido y qué campos sobreviven al parser de stderr. Ese informe es lo que convierte esta propuesta en decisión, o lo que la mata.

## Relacionada

[0004](0004-un-lenguaje-un-runtime-un-tipo-de-fallo.md) · [enmienda al 0004](0004-enmienda-multilenguaje.md) · [0009](0009-multilenguaje-por-referencia.md) · [0010](0010-repos-mixtos-los-dos-motores-conviven.md) · rama `spike/consola-multilenguaje` (`cab9e29`)
