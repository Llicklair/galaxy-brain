# A/B P: tres agentes a la vez sobre el mismo repo, con gb y sin gb

**La pregunta.** El unico sitio donde un agente NO puede ver lo que hace otro, por mucho que
lea: el trabajo en paralelo. Cada rama pasa sola sus tests; la union se rompe (el conflicto
SEMANTICO: merge limpio, CI verde por rama, comportamiento roto junto). `converge` lo cazo
10/10 con agentes reales el 13-ago, pero nunca se ha medido contra no tener gb.

## Diseño (decidido antes de construir nada)

**Base.** `almacen` completo (la referencia de la v2, fases 1-4) como proyecto existente, con su
propia suite visible.

**Tres tareas a la vez**, cada una en su worktree y su rama, pensadas para chocar sin conflicto
de texto:
- **A (refactor):** `fifo.procesar` devuelve un objeto `Resultado` (atributos con nombre) en vez
  de una tupla; actualiza a quien lo llama.
- **B (comando nuevo):** `rotacion <csv> --json`: dias medios en almacen por sku. Lo natural es
  llamar a `fifo.procesar` y desempaquetar la tupla — que A acaba de quitar.
- **C (cambio de regla):** los importes pasan a redondeo bancario (ROUND_HALF_EVEN). Los tests
  que B escriba con valores calculados a HALF_UP pueden romper juntos.

Cada tarea tiene su suite oculta, y la suite oculta de la v2 (adaptada a HALF_EVEN) juzga la
union.

**Brazos.** Mismo modelo; los tres agentes arrancan a la vez.
- SIN: al terminar, el orquestador hace merge de las tres ramas y corre la suite visible. Si sale
  roja, un agente integrador recibe la salida de la suite y arregla. (Es lo que haria cualquiera
  sin gb: la linea base no es "no mirar", es "mirar despues".)
- CON: los worktrees estan registrados, asi que `gb sync`/`gb who` ven la deuda entre agentes
  mientras trabajan; al terminar, `gb tests --union --run` (converge) ANTES del merge, y si sale
  rojo el integrador recibe el choque nombrado (que rama rompe a cual y por que).

## Metricas

| metrica | como |
|---|---|
| **union rota al primer intento** | suite visible tras el merge, antes del integrador |
| prevencion | ¿algun agente adapto su trabajo al de otro mientras trabajaba? (transcripcion: `gb sync`/`who` leidos y cambios despues) |
| coste de llegar a verde | $ y minutos de los tres agentes + el integrador |
| correccion final | suites ocultas de A, B, C y de la union |
| conflictos de texto | los que `git merge` no resuelve solo |

**Tamaño.** 2 ejecuciones por brazo para empezar (unos 15-20 $).

**Expectativa escrita antes.** Por lo ya medido (informar 0/6), la prevencion durante el trabajo
probablemente sea nula: un agente no mira `gb sync` si nada le obliga. Donde gb puede ganar es
en la integracion: el choque nombrado frente a una traza cruda. Si sale empate, tambien se
escribe.
