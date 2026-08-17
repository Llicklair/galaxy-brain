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
| **js** | **3/3** | **no — 1 → 7** | **no — frames del hook** | `NODE_OPTIONS --require` |
| **ruby** | **3/3** | sí | **no — pierde el fragmento** | `RUBYOPT -r` |
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

**El fallback stderr no cierra la cola.** La ADR lo presenta como la capa universal —«todo runtime
imprime a stderr cuando muere»— y es lo único que cubre Go, el lenguaje sin hook posible. Medido:
**0 registros**. La cola queda abierta.

Con eso se activa el **criterio de aborto 1** que la propia ADR escribió: *«Si el fallback stderr no
distingue tipo de excepción del mensaje en ≥2 lenguajes, se recorta el alcance a solo los lenguajes
con hook nativo»*. Y el recorte deja **js y ruby**, ambos suspendiendo el criterio 5.

## Qué se puede afirmar, y qué no

**Sí:** el patrón se repite y el formato aguanta. Escribir un hook por lenguaje que produce un
registro v2 correcto es viable — hay dos funcionando y un tercero a un flag de distancia.

**No:** que esto esté cerca de entrar. Ningún lenguaje pasa los cinco criterios; el almacén no habla
consigo mismo; y 6 de los 16 lenguajes ni siquiera se han podido probar en esta máquina.

**Recomendación:** la [ADR 0012](adr/0012-consola-multilenguaje.md) se queda en **propuesta**, y el
siguiente paso no es añadir lenguajes sino arreglar los dos defectos que hacen inútiles a los que ya
hay: el exit code de js y las tres convenciones de almacén. Si el exit code no tiene arreglo, la
decisión correcta es **cerrar la ADR** — capturar un crash no vale lo que cuesta cambiar cómo muere
el programa.

## Reproducirlo

El banco es un script sin dependencias que extrae el spike de su rama con `git archive`, monta los
casos y compara. Vive fuera del repo a propósito (es un experimento, no código de gb); lo que queda
aquí son los números.
