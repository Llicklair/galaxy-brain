# galaxy-brain — Scope

El *qué* y, sobre todo, el *qué no*. La ley de diseño está en [ARCHITECTURE.md](ARCHITECTURE.md);
la evidencia, en [docs/research-report.md](docs/research-report.md) y [docs/pruebas-de-uso.md](docs/pruebas-de-uso.md).

---

## La frase

> **Cuando algo peta, te dice dónde y con qué estado, sin que tengas que reproducirlo a mano.**

Esa es la columna: la consola de errores. El resto de la herramienta son **hechos deterministas
sobre tu código en el mismo espíritu** — qué forma tiene, qué le hizo cada cambio, qué le falta de
base, qué se aprendió entre repos. Ninguno emite veredictos; todos devuelven material en el mismo
segundo.

### Alcance duro

| | |
|---|---|
| **Lenguaje** | Python. Uno. |
| **Runtime** | Ejecución local. Uno. |
| **Fallo (consola)** | Excepciones no capturadas. Uno. |

Cualquier cuarto elemento en esa tabla es scope creep, no una mejora. La consola captura excepciones
no capturadas; las familias de análisis (`graph`, `symbols`, `check`, `floor`) leen fuente Python.
Un solo lenguaje de punta a punta.

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
