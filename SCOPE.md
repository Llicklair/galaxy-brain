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
