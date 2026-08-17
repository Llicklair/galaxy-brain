# 12. Consola multilenguaje por mecanismo nativo + fallback stderr

**Estado:** propuesta — **medida el 18-ago-2026 y NO pasa sus propios criterios** · **Fecha:** 2026-08-16 · **Supercede (solo el eje lenguaje):** [0004](0004-un-lenguaje-un-runtime-un-tipo-de-fallo.md) · **Extiende:** [0009](0009-multilenguaje-por-referencia.md)

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

| Categoría | Lenguajes | Mecanismo |
|---|---|---|
| **Viables** (hook nativo, install por env-var, cero cambios de código) | JS, TS/TSX, Java, Kotlin, Scala, Ruby, PHP, C# | `NODE_OPTIONS`, `JAVA_TOOL_OPTIONS`, `RUBYOPT`, `auto_prepend_file`, `DOTNET_STARTUP_HOOKS` |
| **Parciales** (hay hook, pero no install transparente) | Dart, Rust, Lua, Elixir, Swift, C | wrapper, `LD_PRELOAD` o configuración a nivel de proyecto |
| **Inviable por hook** (sin mecanismo global) | Go | `recover()` es por goroutine |

- **El fallback universal existe:** todo runtime imprime a stderr cuando muere. Un parser de stderr no da variables locales, pero da tipo de excepción + traza + exit code — suficiente para `gb last` y `gb list`.

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
