# A/B B: gb le habla al ORQUESTADOR, no al agente — tres agentes a la vez

**Por que este banco** (diagnostico del 2-oct-2026, `docs/pruebas-de-uso.md`). Cinco A/B en
empate tenian dos cosas en comun: en el brazo SIN gb nunca se rompio nada (techo: un verificador
en un banco sin fallos solo puede medir su coste), y lo que gb le daba al agente era la capa que
INFORMA (contexto, prosa de `floor`, `calls` disponible), la que el propio proyecto ya habia
condenado el 13-ago ("lo que informa, nunca"). Este banco cambia las dos cosas: **fallos
garantizados** y **gb solo en manos del orquestador**; el agente no lo ve en ningun brazo.

## Diseño (decidido antes de lanzar)

**Base.** `almacen` de la v2 (`base/`), con su suite visible y la CLI despachada por funciones.

**Tres tareas a la vez** (`tareas/`), cada una en su worktree, que componen sin conflicto de texto
y chocan de significado:
- **A (refactor):** `fifo.procesar` devuelve un `Resultado` con atributos, no una tupla.
- **B (comando nuevo):** `resumen`. Lo natural, leyendo el README, es desempaquetar la tupla — que
  A acaba de quitar. Choque A x B, garantizado y visible para la suite.
- **C (regla):** redondeo bancario. Componen limpio con B si B usa `informes.importe`; si B
  redondea por su cuenta, la union escapa a la suite visible y solo la caza la oculta.

**Una tanda de agentes por repeticion, tres orquestadores sobre las MISMAS ramas.** Como los
agentes no ven gb en ningun brazo, su trabajo es identico: se corre una vez y se bifurca solo lo
que hace el orquestador. Emparejado, sin varianza entre brazos en la parte cara.
- **ci:** cada rama verde sola -> merge. La practica comun (CI por PR). Sin integrador.
- **sin:** merge -> suite -> si roja, un integrador recibe la salida de pytest (hasta 2 rondas).
- **con:** `gb tests --run --union` ANTES del merge -> merge -> si rojo, el integrador recibe
  la salida de gb (cada rama sola, la union, el choque nombrado) Y la misma de pytest.

**Validacion sin cuota** (`correr.py validar`, con `referencia/` en lugar de agentes): las tres
ramas verdes solas, la union roja, converge dice CHOQUE SEMANTICO, cero conflictos de texto, la
union arreglada pasa la oculta 72/72. VALIDO el 2-oct-2026.

## Metricas

| metrica | brazo | que dice |
|---|---|---|
| main roto tras merge con todas las ramas verdes | ci | cuanto escapa la practica comun |
| la union roja detectada ANTES de tocar main | con | lo que ci no tiene y sin solo ve despues |
| coste y minutos del integrador hasta verde | sin vs con | si el hecho de gb abarata reparar |
| oculta de la union al final | sin vs con | correccion; y escapes (visible verde, oculta roja) |
| conflictos de texto | todos | si el choque fue de texto, no de significado |

**Tamaño.** 3 repeticiones (unos 15-20 $: 3 agentes + 2 integradores por repeticion).

## Expectativa, escrita antes

- **ci** deja pasar main roto en (casi) todas: cada rama esta verde sola, por construccion.
- **sin vs con en el integrador: probablemente empate.** La validacion ya lo enseña: la salida de
  pytest del merge dice `TypeError: cannot unpack non-iterable Resultado object`, que es casi
  todo el diagnostico. Lo que gb añade ("cada rama pasa sola") a un integrador capaz vale poco.
- **Donde gb puede ganar es en el orquestador, no en el integrador:** con converge, main no se
  toca hasta que la union esta verde; ci rompe main y sin lo rompe y lo arregla despues. Si esa
  diferencia de PROCESO es todo lo que hay, la conclusion es que el valor de converge es
  "ejecutar la union antes del merge" — y entonces hay que preguntarse si un script de cinco
  lineas sin gb (merge a una rama temporal + suite) da lo mismo. Si da lo mismo, eso tambien
  se escribe.
