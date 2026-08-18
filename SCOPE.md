# galaxy-brain — Scope

El *qué* y, sobre todo, el *qué no*. La ley de diseño está en [ARCHITECTURE.md](ARCHITECTURE.md);
la evidencia, en [docs/research-report.md](docs/research-report.md) y [docs/pruebas-de-uso.md](docs/pruebas-de-uso.md).

---

## La frase

> **Cuando agentes escriben código —uno o varios a la vez—, gb dice la verdad: qué se rompe solo,
> qué se rompe junto, qué tests lo prueban y con qué estado murió. Hechos deterministas, cero
> modelos, en el segundo.**

Esa es la columna vertebral: **la verificación del trabajo de agentes** — la rama sola y la unión
(`tests --isolated/--union`, con el choque semántico nombrado), la selección derivada de qué correr
(`tests`), el gate sobre hechos (`graph --gate`) y la consola que guarda el estado del proceso que
murió (`last`/`show`). Debajo de todas está **el grafo** (`graph`/`symbols`/`calls`), siempre
derivado, nunca declarado ni mantenido a mano: es el **motor** — la selección sube por sus aristas,
el rechazo del bucle cruza sus firmas, cada captura se ancla a su nodo — y se mide por lo que sus
consumidores detectan, no por lo que enseña. Ninguno emite veredictos sobre proxies; todos
devuelven material en el mismo segundo.

### La refocalización (2026-08-13), con su evidencia

La columna anterior («el grafo, y capas que aterrizan sobre sus nodos») describía el motor, no el
producto. El uso real lo dijo primero — de 6.015 invocaciones en 7 días, casi todo era la
maquinaria invocándose a sí misma; `last` tecleado a mano: 5 — y la libreta lo confirmó midiendo:
**lo que bloquea o produce un hecho único funciona siempre; lo que informa, nunca.**

| Capa | Evidencia (libreta/memoria) | Sentencia |
|---|---|---|
| `converge` (rama sola + unión) | 10/10 choques con agentes reales (13-ago); 2 falsos verdes estructurales cazados y fijados | **columna** |
| rechazo por adopción (bucle, fuera de gb) | corrige 4/4, siempre; la señal preventiva se ignora 4/4 | **columna** (consume gb) |
| `tests` (selección TIA) | 5/5 mismo veredicto, 20–97 % de ahorro; blindada el 13-ago | queda |
| consola (`last/list/show/on/off/status`) | criterio 3/3; el estado irreproducible solo existe aquí | queda |
| `graph --gate` (ciclos/fronteras) | bloquear corrige 3/3 (9-ago); 0 bloqueos espurios | queda |
| grafo (`graph/symbols/calls`) | motor de todo lo anterior | queda como **motor** |
| `floor` / `memory` | 0 avisos falsos / uso diario real | quedan |
| `check` / `delta` | check: 2 señales, 0 FP sobre 67 commits ajenos | quedan como comandos |
| hooks informativos por acción (`calls --hook`, `delta` por edición) | informar no cambia nada: 0/6 (9-ago); el modelo paga por donde no hay medida | **se cortan del defecto** |
| canvas/watch (`viz`, `symbols --html --watch --fondo`) | dos A/B en empate (3/3 y 3/3); `grep` daba los mismos llamantes; procesos colgados (10-ago) | **se corta** — enmendado 14-ago: vuelve SOLO el renderer como salida de `who --html` (el A/B no midió el uso diario del mapa; libreta 14-ago); la maquinaria del watch propio sigue cortada |
| `graph --context` (mapa de sesión, una vez) | outcome plano en los mismos A/B; coste una-vez-por-sesión | en observación: si en 5 sesiones reales no cambia ninguna decisión (anotado en libreta), se corta |
| `actividad` (presencia derivada) | consumidor real: el bucle | queda como motor del orquestador |

El recorte se ejecuta por fases, cada una con la suite en verde: (1) los hooks informativos fuera
del defecto — la norma va en el defecto, y un defecto que no cambia resultados es ruido pagado;
(2) `viz.py` y su superficie fuera del árbol, con sus tests. Nada de esto toca el alcance duro.
(Enmienda 14-ago: `viz.py` volvió verbatim como renderer de `gb who --html` — el fósil de
`mapa.html` demostró que el mapa se consultaba a diario, el dato que el A/B no miraba; la
maquinaria del watch propio, que era la culpable medida, sigue fuera. Libreta 14-ago.)

### Alcance duro

| | |
|---|---|
| **Lenguaje (grafo)** | Python, con `ast` de la stdlib · 16 más, con `ast-grep` **por referencia** ([0009](docs/adr/0009-multilenguaje-por-referencia.md), [0010](docs/adr/0010-repos-mixtos-los-dos-motores-conviven.md)). Dos motores, 17 lenguajes, y en un repo mixto **conviven**. |
| **Lenguaje (consola)** | Python. Uno. |
| **Runtime** | Ejecución local. Uno. |
| **Fallo (consola)** | Excepciones no capturadas. Uno. |

Cualquier elemento nuevo en esa tabla es scope creep, no una mejora.

#### Lo único que se declara a mano: las aristas que el código no confiesa

El grafo se deriva. La excepción, acotada y escrita: una dependencia que **ningún** analizador
estático puede ver —HTTP, `subprocess`, CLI, IPC, el otro lado en un lenguaje que este repo no
analiza— se declara en `.gb-boundaries` como `A => B` y entra como arista de primera clase (ciclos,
fan-in/out, selección de tests, mapa), gobernada por las fronteras como cualquier otra.

**Qué NO es esto:** no es declarar lo que el análisis ya deriva (eso es un grafo mantenido a mano,
que es justo lo que la ADR 0001 mató: se desincroniza y miente); no es un peso, una etiqueta ni un
tipo de arista; no es una vía para exceptuarse de un `-/->`; y no es un lenguaje de descripción de
arquitectura. Una línea, dos módulos, una dirección. Si alguna vez hace falta un tercer campo, la
respuesta por defecto es no.

#### Por qué el grafo lleva dos lenguajes y la consola uno

No es una inconsistencia, son dos costes distintos. El grafo necesita **un parser**, y eso se integra
por referencia sin tocar el resto ([regla 7](ARCHITECTURE.md)): el 74 % del código —el mapa, la CLI,
el almacén, el suelo— opera sobre el grafo ya derivado y no se entera del lenguaje. La consola
necesita **un enganche al runtime**, y `sys.excepthook` no tiene equivalente portable: capturar
crashes de Node es otro proyecto, no una extensión de este.

Consecuencia declarada, para que nadie la descubra usándolo: **un usuario de JS tiene grafo, onda y
suelo; no tiene consola.** Y necesita instalar `ast-grep` — gb se sigue instalando sin dependencias,
pero la capa JS depende de un binario externo detectado y verificado, nunca vendorizado.

El razonamiento completo y sus criterios de aborto, en
[ADR 0009](docs/adr/0009-multilenguaje-por-referencia.md). Un **tercer** lenguaje repite el mismo
proceso: se discute aquí antes de tocar código, y no antes de que el segundo esté medido en uso real.

#### La conducta en la frontera, que es permanente

Siempre habrá un lenguaje que gb no parsea, así que esto no es andamiaje temporal: **sobre código que
no ha leído, gb no da veredictos.** Ni "sin señales", ni "no encontrado". Dice qué lenguaje ve y que
no lo ha mirado. Se aplica igual el día que se soporten diez lenguajes.

Los catorce comandos, por familia — si uno nuevo no cae en ninguna, no entra
([ARCHITECTURE.md](ARCHITECTURE.md) regla 4):

| Familia | Comandos |
|---|---|
| **Qué forma tiene** (el motor) | `graph` · `symbols` · `calls` |
| Dónde petó y con qué estado | `last` · `list` · `show` · `on` · `off` · `status` |
| Qué le hizo cada cambio | `check` · `tests` · `delta` |
| Qué le falta de base | `floor` |
| Qué se aprendió, cross-repo | `memory` |

#### Un tipo de fallo, tres puertas de salida

"Excepción no capturada" no es sinónimo de `sys.excepthook`. Es un solo tipo de fallo que el
intérprete deja salir por tres sitios distintos, y cubrir los tres **no** amplía la tabla de arriba:

| Puerta | Cuándo | Estado |
|---|---|---|
| `sys.excepthook` | La excepción mata el hilo principal y el proceso | cubierto |
| `threading.excepthook` | Mata un hilo de `threading`, el proceso sigue | cubierto (`GB_NO_THREADS=1` lo quita) |
| `sys.unraisablehook` | Python **no pudo** propagarla: `__del__`, callbacks de weakref, GC | cubierto desde 2026-07-31 |

La tercera se añadió porque era la única que desaparecía **sin dejar rastro**: el intérprete la
imprime, el proceso no muere, y `gb last` no tenía nada que enseñar. Cumple las dos condiciones que
hacen que algo quepa aquí — es el mismo hecho (una excepción que nadie capturó) y conserva el coste
cero, porque el hook solo se ejecuta cuando algo ya ha fallado.

**Criterio de terminado, escrito antes de implementarla:** (1) un `raise` dentro de `__del__` deja un
registro recuperable con `gb show`; (2) el programa observado sigue exactamente igual, incluida la
traza que Python ya imprimía; (3) `SystemExit` y `KeyboardInterrupt` se siguen ignorando por esta
puerta también; (4) el coste de arranque no sube — no se importa nada nuevo; (5) un finalizador que
revienta en bucle no puede inundar el histórico ni frenar el programa.

**Lo que NO se hizo y por qué.** Las tareas sueltas de `asyncio` (una `Task` que revienta y nadie
`await`ea) siguen fuera: exigen tocar el manejador del bucle de eventos, que es otra superficie y
otro coste. Si la excepción propaga fuera de `asyncio.run()`, ya se captura por la primera puerta.

---

## Lo que NO hace

- **No mete un modelo en el camino que siempre corre.** La IA entra después del hecho, a mano y
  visible (ARCHITECTURE, regla 8). Nada que captura, guarda, muestra o analiza consulta a un modelo.
- **No juzga ni bloquea sobre proxies.** Las señales de `check` y de `graph --smells` informan; solo
  se bloquea sobre hechos (un ciclo de imports nuevo, un cruce de frontera declarado). Gatear proxies
  fue el error que hundió el enfoque anterior (ARCHITECTURE, regla 11).
- **No es multi-lenguaje ni multi-runtime.** Ni CI, ni UI, ni servidor. No "más adelante" como coartada:
  no antes de que haya una razón medida escrita aquí.
- **No cubre `asyncio` ni `multiprocessing`** en la consola: hilo principal e hilos de `threading`.
- **No reproduce el pasado paso a paso.** El estado es el del momento en que muere el proceso, no un
  depurador con viaje en el tiempo.
- **Sí enseña un canvas — desde el 14-ago-2026, y por un dato, no por bonito.** El A/B del 13-ago
  midió empate en decisiones de agente y retiró canvas y maquinaria; al día siguiente el fósil de
  `mapa.html` demostró lo que ese A/B no miraba: el mapa se consultaba a diario incluso congelado
  (libreta 14-ago). Vuelve solo el renderer (`viz.py`, salida de `gb who --html`, persistente en el
  `mapa.html` de la raíz); el vivo es `gb who --watch --html`, un comando en primer plano que muere
  contigo. La maquinaria de watch propio (candado, relanzamientos, procesos colgados) sigue retirada
  y su sentencia intacta.
- **No es un servidor MCP** (decidido 2026-07-31, tras plantearlo para ganar persistencia y tener el
  grafo siempre delante). Ninguna de las dos cosas la da MCP: la persistencia ya está resuelta en
  ficheros (`~/.galaxy-brain`, el vault de `memory`) y MCP es transporte, no almacenamiento; y un
  servidor MCP mete en contexto los *esquemas* de sus herramientas, no sus *resultados* — o sea,
  disponibilidad bajo demanda, que es lo que ya da el CLI. Lo que hace que algo esté siempre delante
  es un **hook**, y por eso la respuesta fue `gb graph --context` (regla 11: que salga sin que haya
  que pedirlo). Coste de haberlo hecho al revés: el SDK rompe `dependencies = []`, y los esquemas de
  once subcomandos ocuparían contexto en cada sesión — justo lo que H6 manda cuidar. **Se reabre solo
  si** aparece una necesidad que el hook no cubra, y entonces sería la rebanada de lectura
  post-mortem (`last · show · list`), no la superficie entera.

---

## Terminado (criterios comprobables, por familia)

Cada familia trae su criterio de *hecho* y su criterio de *muerte*. La regla común: **un falso
positivo recurrente la mata** — una herramienta que chilla sin motivo acaba en `--no-verify`, y ese
fue el error que no se repite.

- **Consola** (`last`/`list`/`show`) — ante un fallo real en un proyecto tuyo, te da el punto y el
  estado alrededor sin que abras el depurador ni vuelvas a lanzar nada a mano. Bar: resolver ≥ 3
  fallos así en 5 sesiones.
- **`check`** — sobre cambios reales, **cero falsos positivos** y **≥ 1 amaño real detectado** que
  habría pasado desapercibido leyendo el diff por encima.
- **`floor`** — sobre stacks distintos, **cero avisos falsos** y **≥ 1 nivel señalado** que acabes
  arreglando.
- **`graph --gate`** — cero bloqueos espurios: solo bloquea sobre ciclos nuevos o cruces declarados.
- **`tests`** — sobre un cambio real, la selección derivada del grafo da **el mismo veredicto** que
  la suite entera (mismo exit code) y **tarda menos**. Criterio de muerte: **un solo falso verde** —
  la selección pasa y la suite entera falla por algo que el cambio rompió. Eso no es "menos
  cobertura", es una mentira, y mata el comando. Por eso el fallback ante la duda es correrlo todo:
  si el diff toca algo que no se resuelve a símbolos (un `conftest.py`, un fichero de datos, un
  fichero fuera del grafo), la respuesta correcta es la suite completa, dicha en voz alta.
  Medición previa a la implementación (5-ago-2026, este repo): 5 símbolos, 5/5 mismo exit code,
  ahorro entre 20% y 97% — y el ahorro cae justo donde el símbolo está muy acoplado, que es
  información honesta sobre el diseño, no un fallo del método.

---

## Criterios de fracaso, escritos ahora que no duele

- **Si te descubres desactivándolo o saltándotelo: no se blinda, se investiga por qué.** El abandono
  es el único termómetro honesto que ha dado este proyecto. Taparlo es perderlo (ARCHITECTURE, regla 10).
- **Presupuesto de latencia, innegociable:** lo que corre en cada edición, < 1 s; en cada commit,
  < 10 s. Lo que se salga de ahí muere en una semana. Ya pasó una vez.
- **Si un comando no cabe en la frase de su familia, no está terminado: está creciendo.**

---

## Lo que este scope no resuelve

Que nadie lo necesite. La herramienta puede funcionar perfectamente y no producir un solo *"ahora no
puedo vivir sin esto"*. Esa es la única prueba que falta, y no es técnica: usarla a diario y aguantar
lo que pase, incluido el silencio. La correctitud está medida (ver [docs/pruebas-de-uso.md](docs/pruebas-de-uso.md));
la **adopción**, no.
