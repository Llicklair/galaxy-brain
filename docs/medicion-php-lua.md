# PHP y Lua, medidos: dónde se engancha el hook

**Fecha:** 2026-08-18 · **Qué se mide:** los hooks `gb-hook.php` y `gb-hook.lua` del spike
`spike/consola-multilenguaje`, tal cual están · **Para qué:** contestar la pregunta que decide la
[ADR 0012](adr/0012-consola-multilenguaje.md): **¿el hook se engancha donde se OBSERVA el error, o
donde se MANEJA?**

Respuesta corta: **los dos estaban enganchados donde se maneja, y los dos rompían el programa
observado**. En php de la forma más peligrosa que se ha visto hasta ahora en este spike —**el exit
code pasa de 255 a 0**: un crash sale por la puerta como un éxito. En lua de la más burda —**el
programa observado no llegaba a ejecutarse**. Los dos tienen arreglo, medido y byte a byte.

## Método

46 ejecuciones. Cada caso corrido **dos veces**: sin hook (verdad de referencia: exit code, stdout y
stderr) y con hook, y comparados los tres.

- **No se aisló con `HOME`/`USERPROFILE`.** Se marcó: contar las líneas de
  `~/.galaxy-brain/crashes.jsonl` antes de cada tirada y atribuir solo las nuevas. El fichero solo se
  lee (tenía 17 líneas al empezar; ni se editó ni se borró).
- **Marcar no bastó, y es un hallazgo de método nuevo.** El `crashes.jsonl` es **compartido** y otros
  bancos escribían en él a la vez: tres tiradas de lua se atribuyeron registros `rust/panic` y
  `go/panic` que no eran suyos, y una salió como «2 registros» cuando había escrito 1. Corregido
  atribuyendo además por el campo `language`. **Marcar sin atribuir se equivoca hacia el SÍ** — el
  banco anterior solo se había equivocado hacia el no, que es el error fácil de detectar.
- Rutas Windows siempre (`cygpath -w`); nunca POSIX a un binario nativo.
- Validación contra `schema.json` del prototipo: campos `required` de la raíz, de `exception` y de
  `process`, presentes **y no vacíos**.
- Runtimes: **php 8.4.24 (cli, ZTS)**, **Lua 5.4.6**.

**Trampa de método específica de php, que casi me come:** php-cli escribe los fatales en **stdout**
(`display_errors=1` → STDOUT), no en stderr. Una tabla que solo mire stderr da «misma traza: sí» en
los cuatro casos **mientras la traza entera está desapareciendo**. Los dos streams se comparan por
separado en todo lo que sigue.

### Casos

| php (exit sin hook: **255** en los 4) | lua (exit sin hook: **1** en los 3) |
|---|---|
| `null` — método sobre `null` (`Error`) | `nil` — indexar un nil |
| `divzero` — `intdiv(10,0)` (`DivisionByZeroError`) | `arith` — aritmética sobre una tabla |
| `throw` — `throw new ErrorDeBanco` a mano | `error` — `error("...")` a mano |
| `fatal` — `require` de un fichero que no existe | |

## Resultado

| Lenguaje | Caso | Vía | Registro válido | Mismo exit code | Misma traza | Mismo stdout |
|---|---|---|---|---|---|---|
| php | null | runner `gb-run.py` | **0/1** | sí | sí | sí |
| php | divzero | runner `gb-run.py` | **0/1** | sí | sí | sí |
| php | throw | runner `gb-run.py` | **0/1** | sí | sí | sí |
| php | fatal | runner `gb-run.py` | **0/1** | sí | sí | sí |
| php | null | `-d auto_prepend_file` | 1/1 | **NO — 255 → 0** | sí (vacío) | **NO — traza borrada** |
| php | divzero | `-d auto_prepend_file` | 1/1 | **NO — 255 → 0** | sí (vacío) | **NO — traza borrada** |
| php | throw | `-d auto_prepend_file` | 1/1 | **NO — 255 → 0** | sí (vacío) | **NO — traza borrada** |
| php | fatal | `-d auto_prepend_file` | **0/1** (`frames` vacío) | **NO — 255 → 0** | sí (vacío) | **NO — traza borrada** |
| php | los 4 | **`auto_prepend_file` ARREGLADO** | **4/4** | **sí (255)** | **idéntico** | **idéntico** |
| lua | nil | `LUA_INIT=@` (lo que pone el runner) | **0/1** | sí (por coincidencia) | **NO** | **NO — no ejecuta** |
| lua | arith | `LUA_INIT=@` (lo que pone el runner) | **0/1** | sí (por coincidencia) | **NO** | **NO — no ejecuta** |
| lua | error | `LUA_INIT=@` (lo que pone el runner) | **0/1** | sí (por coincidencia) | **NO** | **NO — no ejecuta** |
| lua | nil | wrapper `lua gb-hook.lua caso.lua` | **0/1** (falta `process.project`) | sí | **NO — frames del hook** | sí |
| lua | arith | wrapper `lua gb-hook.lua caso.lua` | **0/1** (falta `process.project`) | sí | **NO — frames del hook** | sí |
| lua | error | wrapper `lua gb-hook.lua caso.lua` | **0/1** (falta `process.project`) | sí | **NO — frames del hook** | sí |
| lua | los 3 | **`LUA_INIT=@` ARREGLADO** | **3/3** | **sí (1)** | **idéntico** | **idéntico** |

Tras los arreglos, comparación **byte a byte** (no normalizada) de exit code + stdout + stderr, y con
dos programas que **no** fallan, con argumentos y `exit(3)` propio, para comprobar que el hook no
altera el camino feliz: **0 fallos de 9 comprobaciones**.

## PHP: `set_exception_handler` es un MANEJADOR, y borra el crash entero

El hook del spike instala tres cosas: `set_exception_handler`, `set_error_handler` y
`register_shutdown_function`. Las dos primeras son **manejadores**. Instalar un
`set_exception_handler` le dice a PHP que la excepción está atendida, y PHP hace lo consecuente:

- **no imprime** el `Fatal error: Uncaught ...` con su `Stack trace:` — stdout pasa de 797 bytes a
  **vacío**;
- **sale con 0**. Medido: 255 → 0 en los cuatro casos.

Es el defecto de java (borrar la traza del programa observado) **y** el de js (cambiar el exit code)
a la vez, y peor que ninguno de los dos: java al menos conservaba el 1, y el 255 → 0 de php pone en
verde cualquier CI, `Makefile` o `&&` que mire el código de salida. Con la consola puesta, un
programa que revienta parece que ha ido bien y no queda ni el rastro en pantalla. Nada lo delata.

**El gancho de observación de php es `register_shutdown_function` + `error_get_last()`, a secas.**
Corre *después* de que PHP ya haya reportado el fatal por su camino normal, no sustituye a nadie, y
`error_get_last()` trae todo lo que hace falta — sonda medida:

```
type: 1 (E_ERROR)
message: "Uncaught Error: Call to a member function longitud() on null in ...\null.php:3
          Stack trace:
          #0 ...\null.php(6): pide_longitud(NULL)
          #1 ...\null.php(8): nivel_medio()
          #2 {main}
            thrown"
file: ...\null.php   line: 3
```

Tipo, mensaje, fichero, línea y la pila entera. Y con solo el shutdown instalado, **exit 255 y los
797 bytes de stdout intactos**.

El arreglo (`arreglo/gb-hook.php`, 152 líneas frente a 274 — el arreglo es **restar**: se caen los
dos manejadores enteros) parsea el `Uncaught <Clase>: <msg> in <fichero>:<línea>` para sacar el tipo
de verdad y las entradas `#N fichero(línea): función()` para los frames. Medido:

| | antes (spike) | después (arreglo) |
|---|---|---|
| registros válidos | 3/4 (`fatal` con `frames` vacío) | **4/4** |
| tipo capturado | `Error`, `DivisionByZeroError`, `ErrorDeBanco` | igual, y `fatal` también |
| exit code | **255 → 0** | **255, igual** |
| stdout | **borrado** | **idéntico byte a byte** |
| stderr | igual (vacío) | **idéntico byte a byte** |

Los frames del caso `throw` salen exactos contra la traza real: `lanza()`@4, `envoltorio()`@7,
`{main}`@9. El caso `fatal` (un `require` inexistente, que en PHP 8 se lanza desde el ámbito
principal y por tanto `getTrace()` devuelve **vacío**) es justo el que el hook original dejaba sin
`frames` — el arreglo sintetiza el frame del sitio del fallo con `file`/`line` de `error_get_last()`.

### Y el runner no instala nada

`gb-run.py` para php **solo exporta `GB_PHP_HOOK` y te imprime el flag para que lo escribas tú**
(líneas 141-149 de `gb-run.py`, en la rama `spike/consola-multilenguaje`). Medido: **0 registros
en 4/4 casos** por esa vía. La ADR clasifica php entre los «viables, install por env-var, **cero
cambios de código**»; **hoy eso no es cierto**, y no hay env-var de PHP que lo arregle:
`auto_prepend_file` es una directiva de `php.ini`, y `PHP_INI_SCAN_DIR` (lo único parecido a una
env-var) apunta a un *directorio* de `.ini`, no a un fichero de código. Es viable — pero desplegando
un `.ini` generado, no exportando una variable.

## Lua: el runner mataba el programa, y el wrapper mentía en la traza

Dos defectos independientes, uno en el runner y otro en el hook.

**1. `LUA_INIT=@gb-hook.lua` impide que el programa se ejecute.** `gb-hook.lua` está escrito como
**wrapper** (`lua gb-hook.lua script.lua`): su `main()` lee `arg[1]` esperando el script. `LUA_INIT`
lo carga *antes* del script, cuando `arg[1]` no existe todavía, así que hace lo que dice su código:
imprime `Usage: lua gb-hook.lua <script.lua> [args...]` en stderr y `os.exit(1)`. **El programa
observado nunca corre.** Medido en 3/3: stdout perdido (`antes del fallo` no sale), stderr sustituido
por el mensaje de uso, 0 registros.

Y **la columna «mismo exit code» dice sí**: el crash de lua sale con 1 y el `os.exit(1)` del hook
también. Coincidencia numérica exacta que tapa una destrucción total del programa observado. Es la
lección de java —«el exit code no delataba la pérdida»— en su versión extrema.

**2. Como wrapper sí captura, pero la traza que imprime es la del hook.** Tras el fallo hace
`error(err, 0)` desde `main()`, así que la traza que compone el intérprete es la de *su* pila:

```
  sin hook                                    con el wrapper
  stack traceback:                            stack traceback:
    ...nil.lua:2: in function <...nil.lua:1>    [C]: in function 'error'
    (...tail calls...)                          ...gb-hook.lua:292: in local 'main'
    ...nil.lua:10: in main chunk                ...gb-hook.lua:296: in main chunk
    [C]: in ?                                   [C]: in ?
```

El programa deja de decir dónde petó y pasa a decir dónde está el hook. Es exactamente
`uncaughtException` + `throw err` de js, en lua. Además los 3 registros son **inválidos**: falta
`process.project`, porque las tablas de Lua no admiten `nil` como valor y `project = nil` hace
desaparecer la clave del JSON.

### El punto de observación de lua, y por qué el arreglo tiene dos mitades

Lua no tiene un evento de «excepción no capturada». Lo que sí tiene es el **message handler de
`lua_pcall`/`xpcall`, que corre ANTES de desenrollar la pila** — ahí siguen vivos el stack y los
locales. **Ese es el punto de observación**, y el spike ya lo usaba: no era el gancho lo que estaba
mal. Lo que estaba mal era **qué se hace después**. Como el intérprete estándar (`lua.c`) ya
instaló su propio `msghandler` y su propio informe, cualquier envoltorio tiene que **replicar el
default a mano** — la misma conclusión que java, por la misma razón.

El arreglo (`arreglo/gb-hook.lua`) hace las dos mitades:

1. **Instalable de verdad por `LUA_INIT`**: en vez de exigir un wrapper, lee `arg[0]` (que `lua.c`
   ya ha rellenado con la ruta del script antes de ejecutar `LUA_INIT`), carga el script él mismo
   bajo `xpcall` con su message handler, y sale con el código correcto. Cero cambios en la línea de
   órdenes del usuario: **la casilla «install por env-var» de la ADR sí se cumple en lua**, al
   contrario que en php.
2. **Replica el informe de `lua.c` byte a byte**: `"lua: " .. debug.traceback(msg, 2) .. "\n"` a
   stderr, `os.exit(1)`, y **recortando la cola del traceback** en el `in main chunk` del script
   observado más un `\t[C]: in ?` — porque por debajo solo quedan `xpcall` y los frames del propio
   hook. Se replican también las reglas de `lua.c` para objetos de error que no son cadena
   (`__tostring` se devuelve **sin** traceback; si no, `(error object is a %s value)`).

| | antes (spike, vía `LUA_INIT`) | después (arreglo, vía `LUA_INIT`) |
|---|---|---|
| el programa llega a ejecutarse | **no** | **sí** |
| registros válidos | 0/3 | **3/3** |
| exit code | 1 «por coincidencia» | **1, el de verdad** |
| stderr | `Usage: ...` | **idéntico byte a byte** |
| stdout | perdido | **idéntico byte a byte** |

Los frames del registro salen limpios y **con locales del sitio del fallo**, que es más de lo que
enseña el intérprete: `nil` → `[('Lua',2,'nil.lua'), ('main',10,'nil.lua')]` con `locals: {t}`;
`arith` → `locals: {a}`; `error` → `[('error',-1,'[C]'), ('lanza',2), ('envoltorio',6),
('main',10)]`.

### Dos fallos de mi propio arreglo, encontrados midiendo

Se dejan escritos porque son del mismo eje:

- **Recorté el traceback por el último `in main chunk` en vez del primero.** El último es el del
  *hook*; el primero es el del *script*. Resultado: tres frames del hook seguían colándose. Un
  `for i = #lineas, 1, -1` cambiado a `for i = 1, #lineas`.
- **`lua -e 'print("hola")'` dejó de funcionar.** Sin script, `createargtable()` de `lua.c` pone
  `arg[0]` = **el propio intérprete** — y `lua.exe` existe como fichero, así que mi guarda «arg[0] es
  un fichero legible» la pasaba y el hook intentaba `loadfile(lua.exe)`: *syntax error*, exit 1, el
  código inline nunca corrió. Mi hook mataba el programa igual que el que estaba arreglando. La
  guarda correcta es `arg[-1] == nil` → no hay script, apartarse: los índices negativos de `arg` solo
  existen cuando `lua.c` ha identificado un script.

## Qué NO se pudo medir

- **php sin `-d`**: no se tocó el `php.ini` de la máquina (es configuración del usuario), así que la
  vía «instalado de verdad para todo el sistema» queda sin medir. Se midió la equivalente por flag.
- **php-fpm / apache / web**: solo cli. El `register_shutdown_function` debería comportarse igual,
  pero eso es una hipótesis, no una medida.
- **lua sin script**: `lua -e '...'` y `lua -` (stdin) **no se capturan** por diseño del arreglo — el
  hook se aparta a propósito. Un crash en `-e` o en stdin no produce registro. Medido: el programa
  sigue perfecto (exit y traza normales), simplemente no hay consola.
- **LuaJIT, Lua 5.1/5.3**: solo Lua 5.4.6. `os.exit(code, true)` y `table.unpack` son 5.2+; en 5.1
  haría falta `unpack`.
- **Corrutinas** en lua y **excepciones en `finally`/destructores** en php: fuera del banco.
- **`gb last`/`show`/`list` sobre estos registros** (criterio 3 de la ADR): sigue sin poder medirse,
  y por lo ya escrito en [CONSOLA-MULTILENGUAJE.md](CONSOLA-MULTILENGUAJE.md) — los hooks escriben
  `crashes.jsonl` y el gb real usa `index.jsonl`. Esto no lo arregla ningún hook.

## Lo que esto aporta a la ADR 0012

**El eje observación/manejo se confirma en dos lenguajes más: van cuatro de cuatro** (js, java, php,
lua). Cada vez que un hook de este spike se ha enganchado donde se *maneja*, ha roto el programa
observado; cada vez que se ha movido a donde se *observa*, ha quedado byte a byte idéntico. Ya no es
un patrón sugerente: es el criterio.

Y la tabla de tiers de la ADR sale de aquí con dos casillas **cambiadas de sitio y por motivos
opuestos**:

- **php baja**: está entre los «viables, install por env-var, cero cambios de código» y **no hay
  env-var** que lo instale. Es viable desplegando un `.ini`, que es otra cosa y hay que escribirla.
- **lua sube**: está entre los «parciales, sin install transparente» y `LUA_INIT` **sí** lo instala
  de forma transparente — solo hacía falta que el hook no estuviera escrito como wrapper. Medido:
  3/3 con `LUA_INIT` y nada más.

Que las dos casillas estuvieran mal **en direcciones contrarias** es la prueba de que el eje por el
que está ordenada la tabla no predice nada. El que predice es el otro.

**Los criterios 1, 2 y 5 los pasan hoy php y lua**, con los arreglos aplicados. El 3 y el 4 siguen
sin pasarlos nadie.

## Reproducirlo

Banco, casos y hooks arreglados viven fuera del repo (es un experimento, no código de gb), en el
directorio de trabajo de esta medición: `banco.py` (tabla principal), `extras.py` (bytes exactos y
camino feliz), `arreglo/gb-hook.php`, `arreglo/gb-hook.lua`. Aquí quedan los números.
