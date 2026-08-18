# Una sola convención de almacén

**Fecha:** 2026-08-18 · **Desbloquea:** criterio 3 de la [ADR 0012](adr/0012-consola-multilenguaje.md)
(«`gb last`, `gb show` y `gb list` funcionan sin modificación») · **Medido sobre:** los registros
reales de `~/.galaxy-brain/` y el prototipo de `spike/consola-multilenguaje`, leyendo el código, no
los comentarios.

## Lo que hay hoy, comprobado

Tres convenciones, como dice [CONSOLA-MULTILENGUAJE.md](CONSOLA-MULTILENGUAJE.md). Pero al mirar los
ficheros de verdad salen dos hechos que ese documento no tiene:

**1. El prototipo no lee ni un registro, tampoco los suyos.** Ejecutado contra el almacén real:

```
~/.galaxy-brain/*.crashes.jsonl -> []
existe crashes.jsonl -> True
store_universal.last()          -> None
store_universal._iter_records() -> 0 registros
```

**2. Ningún registro real valida contra el schema v2 — con el validador del propio prototipo.**
`CONSOLA-MULTILENGUAJE.md` dice «23 de 26 validan» y el criterio 2 de la ADR está marcado ✅. Pasando
los registros por `store_universal.validate()`, que es el validador que el spike escribió para eso:

```
  linea  1  rust     INVALIDA: missing required top-level field 'language'
  linea  2  rust     INVALIDA: exception.origin: invalid value 'thread-main'
  linea  3  ruby     INVALIDA: process.argv_forma: expected [<class 'str'>, None], got list
  linea  4  php      INVALIDA: exception.origin: invalid value 'exception'
  linea  6  go       INVALIDA: exception.origin: invalid value 'goroutine-1'
  linea  8  java     INVALIDA: frames[0]: missing required field 'function'
  linea 10  js       INVALIDA: process.argv_forma: expected [<class 'str'>, None], got list
  linea 13  lua      INVALIDA: exception.origin: invalid value 'xpcall'
  linea 14  csharp   INVALIDA: frames[0]: missing required field 'function'

VALIDAN 0 de 24 con el validador del prototipo
```

**El criterio 2 tampoco está pasado.** No son tres convenciones: son ocho dialectos que se parecen.
Rust escribe `error` + `location` + `backtrace`; lua escribe `stack` con `short_src`/`what`; java y
C# escriben `class` + `method` en vez de `function` y el `pid` como **string**; `argv_forma` es lista
en todos y el schema la declara string; `exception.origin` es un enum cerrado que **ningún** hook
respeta.

## 1. Campos: qué falta y qué sobra respecto a `render.py`

`render.render_record` (render.py:115) y `render._render_frame` (render.py:175) leen exactamente
esto. Marco con **PETA** lo que no es «falta un dato» sino un fallo duro.

| Lo que `render` lee | Schema v2 / registro real | Veredicto |
|---|---|---|
| `exception.type`, `exception.message` | sí (rust y lua lo llaman `error`) | renombrar |
| `exception.chain[].kind` | **no existe**; el v2 anida excepciones enteras | **PETA** `KeyError: 'kind'` — render.py:152 lo lee sin `.get` |
| `exception.chain[].type/.message` | sí | ok |
| `frames[].file`, `frames[].line` | sí (lua: `short_src`) | ok |
| `frames[].function` | **falta en java y csharp** (`class` + `method`) | componer |
| `frames[].is_library` | **no existe en el v2** | **falta, y decide el titular** (ver abajo) |
| `frames[].source` | v2 lo declara **string**; gb necesita `[{n, text, is_fail}]` | **PETA** `AttributeError: 'str' object has no attribute 'get'` — render.py:183 |
| `frames[].locals` | opcional, dict — compatible | ok |
| `process.project` | declarado required; **java, lua y rust no lo traen** | derivar de `cwd` |
| `ts` | sí | ok |
| `thread` | no; el v2 tiene `exception.origin` con otro significado | mapear |
| `id` | **no existe** | lo genera `store.write` |
| `frames_trimmed` | no | opcional, 0 |

Y lo que `store._append_index` necesita además: `exception.**origen**` (español, el fichero de un
`SyntaxError` sin frames) — **colisión de nombre** con `exception.**origin**` del v2 (inglés, dónde
afloró). Mismo nombre, cosas distintas. **No se mapean.**

**Sobra** (el v2 lo trae y gb no lo lee nunca): `schema: 2`, `capture_method`, `exception.origin`,
`frames[].column`, `process.runtime`, `process.argv_forma`. Y `language`, que hoy no lee nadie: se
arrastra para un futuro `gb list --lang`, no porque haga falta para el criterio 3.

### El campo que falta y no está en ninguna lista: el ORDEN de los frames

`_headline_index` (render.py:107) busca el frame **más interno que sea tuyo** recorriendo la lista
**hacia atrás**: asume el orden de Python, más interno el **último**. Los hooks de js, java, csharp,
ruby, php, go y rust emiten al revés, más interno **primero**. Sin `is_library` y sin invertir, el
registro js real se pinta así:

```
RangeError: stack overflow in multi-repo JS
hace 1d - node:internal/main/run_main_module:33 - multi
```

**Señala el arranque de Node.** No peta, no avisa, y manda a leer un fichero que no es del usuario.
Es el fallo más caro de los cuatro porque es el único silencioso.

## 2. ¿Hay pérdida?

**Sí, y se declara.** Tres cosas que un hook no-Python no puede dar hoy:

- **`frames[].locals`.** Solo Python y lua las traen (`locals` aparece en **1 de 24** registros
  reales). El fallback stderr no las tendrá nunca. Se guarda `None`, no `{}`: `render` ya distingue
  «no hay locales» de «no se capturaron» (render.py:194).
- **`frames[].source`.** El texto alrededor de la línea. Ningún hook nativo lo manda. Es **derivable
  a posteriori** leyendo el fichero, pero eso es otra decisión: hoy queda vacío.
- **`exception.chain`.** Ningún hook la emite. Las cadenas de java (`Caused by:`) están dentro de
  `traceback` como texto, sin partir.

Lo demás es reversible. Y un hueco propio del prototipo, no del formato: **el hook de lua se mete a sí
mismo en la pila** — su titular apunta a `gb-hook.lua:260`, no al programa. Eso es un bug del hook,
del mismo tipo que el de java (`86c944d`).

## 3. El cambio más pequeño

**Un buzón, una función, una llamada. Y un fichero que se borra.**

1. **`~/.galaxy-brain/crashes.jsonl` es el BUZÓN, no el almacén.** Los hooks nativos ya escriben ahí:
   no se toca ni un hook. El almacén sigue siendo `index.jsonl` + `errors/<proyecto-hash>/<id>.json`,
   que es lo que el usuario ya tiene. Los hechos crudos se quedan en el buzón (regla 6 de
   ARCHITECTURE: los hechos se guardan crudos); lo archivado es derivado.
2. **Una función `normaliza(bruto) -> registro gb`**, ~90 líneas de stdlib, en un módulo nuevo. El
   prototipo (`normaliza.py`, en el directorio de trabajo) está escrito y demostrado.
3. **Una llamada**, al principio de `cli.main()`, envuelta en `try/except BaseException` (regla 9):
   drena las líneas nuevas del buzón con marca de agua de byte en `~/.galaxy-brain/crashes.offset`.
   Idempotente y O(líneas nuevas).
4. **Se borra `store_universal.py` entero.** Su glob no casa su propio fichero, su validador rechaza
   24 de 24 registros suyos, y usa `Path.home()` fijo ignorando `GB_HOME` — por eso el banco de la
   primera vuelta tuvo que inventarse un aislamiento que cuatro runtimes no respetan. Restar antes
   que pulir.

**`gb` no cambia ni una línea de `store.py` ni de `render.py`.** Ese es el punto: el criterio 3 dice
«sin modificación» y así se cumple literalmente.

### Latencia (regla 3: < 1 s)

```
ingesta de 32 registros: 38.4 ms (1.20 ms/registro)
solo normaliza(), 32 registros: 4.66 ms (0.15 ms/registro)
read_index sobre 32 entradas: 8.5 ms
```

En régimen normal el buzón trae 0 o 1 líneas nuevas. El coste es leer un offset y hacer `seek`.

## Demostración

Prototipo y bancos en el directorio de trabajo del agente
(`scratchpad/ag-almacen/`: `normaliza.py`, `demo.py`, `demo_e2e.py`, `valida.py`). Se ingestan los
registros reales con `GB_HOME` apuntando a un temporal — el histórico del usuario no se toca — y se
llama al **CLI de verdad**, sin parchear nada:

```
== Ingesta: 32 registros de hooks nativos -> store.write() de gb ==
   escritos: 32/32  (store.write nunca lanza: regla 9)

--- gb last (exit 0) ---
panic: boom explicito desde go
hace 1min - .../ag-gorust/banco/go/panico.go:6 - hilo goroutine-1

  .../ag-gorust/banco/go/panico.go:6  in main.explotar

  (1 frames mas: gb show 20260818T030835-bb4aac --full)

--- gb list (exit 0) ---
3x  runtime_error           ult. hace 2min    .../gb-hook.lua:260
3x  panic                   ult. hace 1d      src/main.rs:3
2x  panic                   ult. hace 1min    .../banco/go/panico.go:6
2x  TypeError               ult. hace 1d      service.js:3
1x  DivisionByZeroError     ult. hace 2min    .../casos/php/divzero.php:3
1x  ErrorDeBanco            ult. hace 2min    .../casos/php/throw.php:7
```

Y `gb show --full` sobre una captura de **Java**, con la pila ya en el orden que gb espera:

```
java.lang.RuntimeException: Java crash test
hace 1d - CrashTest.java:3

  CrashTest.java:9  in CrashTest.main
  CrashTest.java:6  in CrashTest.outer
  CrashTest.java:3  in CrashTest.inner
```

El titular de js, antes y después de `normaliza()`:

```
antes:   hace 1d - node:internal/main/run_main_module:33
despues: hace 1d - crash_js.js:1
```

## 4. Qué se rompe

**De lo que hay en uso hoy: nada.** El formato del almacén no cambia, `store.py` y `render.py` no se
tocan, y las capturas de Python del usuario siguen escribiéndose igual. Un `index.jsonl` de hoy se
lee mañana.

Lo que sí cambia, y hay que escribirlo antes:

- **Registros multilenguaje entran en `gb list`, `gb graph --gate`, la cola de pendientes y el mapa.**
  `store.es_del_proyecto` y `es_exploracion` deciden por **ruta de fichero**, y eso sigue funcionando
  — pero una captura de `CrashTest.java` trae el fichero **sin ruta** (`CrashTest.java`, no
  `C:\...\CrashTest.java`): `_dentro_de` la resolverá contra el cwd del proceso que ejecuta `gb`.
  **Riesgo real**: una captura de Java puede aparecer o no en la cola según desde dónde se invoque
  gb. Se declara ahora; el arreglo es que el hook de java mande la ruta absoluta, no que gb adivine.
- **`is_library` pasa a ser una tabla declarada a mano** por lenguaje (prefijos `node:`,
  `node_modules/`, `java.`, `System.`, `/vendor/`…). En Python es un hecho derivado
  (`capture.is_library_frame`); aquí es una lista que hay que mantener. Falla hacia «es tuyo»:
  ensucia el titular, nunca lo esconde. **Es la parte más frágil de la propuesta y la que hay que
  vigilar.**
- **Registros con `language: "unknown"` o sin `exception`** (3 de los 24 reales) se archivan con
  `type: "?"` en vez de descartarse. Aparecer feo es mejor que desaparecer callado.
- **Nadie borra el buzón.** Crece append-only, como `index.jsonl`. Si hay que compactarlo, ya existe
  el patrón (`store._compact_usos`).
- **Compatibilidad hacia atrás del buzón:** si un hook cambia de forma, `normaliza` produce campos a
  `None` y `store.write` archiva igual. No hay versión que romper porque el buzón no es contrato: es
  una tolva.

## Criterio de terminado, comprobable

1. `gb last`, `gb show <id> --full` y `gb list` pintan una captura de **js, java, ruby, php, go, rust
   y csharp** con exit 0, **sin un solo cambio en `store.py` ni en `render.py`**. Se comprueba con
   `git diff --stat` sobre esos dos ficheros: cero líneas.
2. El titular (`where` del índice) de una captura de js apunta a un fichero **del usuario**, nunca a
   `node:internal/*`. Test con el registro js real como fixture.
3. Ingestar el buzón dos veces seguidas **no duplica** ni una entrada en `index.jsonl`.
4. Un buzón corrupto —línea truncada, JSON inválido, fichero ilegible— deja `gb last` funcionando
   sobre las capturas de Python. Test con una línea basura por medio.
5. La ingesta de un buzón de 1000 líneas tarda **< 1 s** (regla 3). Medido, no estimado.
6. `store_universal.py` **no existe**.

## Lo que esto NO arregla

El criterio 3 de la ADR 0012, y solo ese. Siguen abiertos el **criterio 4** (`gb status` no existe),
el **criterio 2** de verdad —0 de 24 registros validan, y la propuesta lo esquiva convirtiendo en vez
de validar—, el **fallback stderr** (0 registros en Go) y los 6 lenguajes sin runtime en esta máquina.
La ADR sigue siendo **propuesta**.
