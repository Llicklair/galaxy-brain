# galaxy-brain — La visión

> **Estado: destino, no realidad.** Lo que gb hace HOY está en [SCOPE.md](SCOPE.md); la ley vigente,
> en [ARCHITECTURE.md](ARCHITECTURE.md); la evidencia, en [docs/research-report.md](docs/research-report.md).
> Esta visión se refinó adversarialmente (2-ago-2026): cada "oráculo" propuesto pasó por un evaluador
> independiente que intentó demostrar que era teatro. Cinco de ocho lo eran. Lo que queda abajo es lo
> que **sobrevivió** a esa refutación — por eso la tabla ya no promete la misma cosa en las ocho fases.

---

## La tesis

**La corrección de un proyecto se construye desde su concepción, no se inspecciona al final.**

Para cuando una consola de errores captura un fallo, el error ya se cometió tres fases antes —en una
idea sin acotar, en una decisión sin registrar, en un código escrito sin verificar—. Verificar solo el
resultado llega tarde por diseño. Un código nace correcto o se corrige caro.

De ahí el giro: galaxy-brain no es una consola de errores con herramientas alrededor. Es **el arnés que
acompaña las ocho fases de un proyecto**, con la disciplina de H1 (feedback determinista antes que el
modelo) y H2 (generador ≠ evaluador) aplicada a todo el ciclo, no solo al código.

Pero hay un límite duro, y fingir que no existe fue lo que hizo teatro a la primera versión de esta
visión:

---

## El patrón que decide — dónde hay oráculo y dónde no

> **Un hecho puede GATEAR (bloquear el paso) solo cuando lo produce algo EXTERNO al modelo: git, el
> intérprete, el AST, una ejecución real. Cuando el hecho lo escribe el mismo modelo que se gatea, no
> es verificación — es auto-reporte, y el modelo ajusta la superficie hasta pasar el contador (H2).**

Esa línea parte "oráculo" en tres cosas que no son la misma, y que VISION fundía:

- **GATEA** — un hecho de *retirada, existencia o ejecución* que el modelo no puede fingir. "Esta
  frontera desapareció del diff", "este símbolo no resuelve en el AST", "este proceso corrió y petó",
  "estos ciclos son nuevos". Ungameable, porque la fuente no es el modelo.
- **INFORMA** — un proxy: correlaciona con lo que importa, pero **un cambio legítimo lo levanta**
  (regla 11). Contar cláusulas de una idea, contar asserts de un diff, exigir un test en rojo. Sale
  siempre, delante de quien decide, pero **no bloquea** — gatearlo fabrica los falsos positivos que
  acaban en `--no-verify`.
- **SE PIDE al humano** — el juicio irreducible: ¿es de verdad *un* trabajo? ¿es el criterio correcto?
  ¿la razón del ADR es buena o folklore plausible? ¿este test prueba lo que querías? Ninguna máquina lo
  comprueba. Se pide y se dice que se pide —como ya hace `floor` con el criterio de terminado—.

La corrección emerge de las fases que **gatean**; las que **informan** hacen visible el riesgo sin
bloquear; y las que **piden** son honestas sobre su propio límite. Vender las tres como "la misma idea"
sería el teatro que este proyecto existe para no hacer.

---

## Las ocho fases

Cada fila separa lo que un hecho externo puede **bloquear**, lo que solo **informa**, y lo que se
**pide** al humano. La columna "tipo" dice qué es la fase en su núcleo.

| # | Fase | GATEA (hecho externo, ungameable) | INFORMA (proxy, regla 11) | SE PIDE al humano | Tipo |
|---|------|-----------------------------------|---------------------------|-------------------|------|
| 1 | **Idea** | `idea.lock` = hash congelado; las citas en floor/boundaries/tests deben igualarlo → caza **drift descoordinado** entre artefactos | Contar cláusulas / denylist de scope: un monstruo de una sola frase (*"diagnosticar cualquier fallo del backend en prod"*) pasa; un JOB compuesto legítimo se bloquea | ¿Es de verdad **un** trabajo? ¿El usuario y el problema son reales? ¿Merece hacerse? | detección + juicio |
| 2 | **Acotar** | El criterio de SCOPE cita artefactos que **existen** (nodos que `pytest --collect-only` colecciona, binarios en PATH): cero referencias fantasma | Exigir un test en rojo — burlable con `sys.exit(1)`, y **rechaza criterios verdes legítimos** (la SCOPE.md de este repo fallaría) | ¿Es el criterio **correcto** y **completo**? ¿"Qué NO entra" es honesto o se dejó vacío por miedo? | detección + juicio |
| 3 | **Arquitectura** | **Retirada de frontera**: una regla que estaba en HEAD ya no está en el working tree y no se añadió un ADR sustituto — diferencia de conjuntos sobre blobs de git | El binding ADR↔invariante por igualdad de cabecera (el modelo escribe las dos cadenas → se verifica a sí mismo). "Regla nueva sin ADR" = papeleo | ¿La razón del ADR es buena o folklore? ¿La frontera es la correcta o un espantapájaros? | **gate** + juicio |
| 4 | **Construir** | **El gate de acoplamiento** (`graph --gate`): ciclo de imports o cruce de frontera — hecho AST, el mismo que la fase 7, aquí en absoluto. *El "recibo de ejecución" quedó **descartado** (decisión, 3-ago): es auto-reporte —el modelo elige qué correr— y exigiría un segundo tipo de evento en la consola (regla 5). El "dije listo sin ejecutar" se acepta como **no-gateable** y se pide al humano.* | **Símbolos fantasma**: `symbols` los cuenta con su motivo sin distinguir "no existe" de "no resoluble" — cuentan, no adivinan, así que **no gatean** (verificado, 3-ago). Rojo/verde como prueba de corrección (gameable: verde tautológico `assert x is not None`). No-ablandamiento de tests (`check`, ya PROXY) | ¿Es **este** test el correcto? ¿Prueba lo que querías? ¿La cobertura basta? ¿Se **ejecutó** de verdad? | **gate** + juicio |
| 5 | **Comprobar** | El estado real de un fallo que **ocurrió**: frames, locales, traza que puso el intérprete. Auto-verificado por `bootstrap.coverage` (8 subprocesos reales) | — (la **ausencia** de captura no prueba nada: es indistinguible de "no corrió") | ¿El programa hace lo que querías, más allá de no petar? | **instrumento** (devuelve, no bloquea) |
| 6 | **Entender** | El grafo desde el AST (ciclos por Tarjan, resuelve solo lo resoluble y declara lo que no); `recall` reproducible | La memoria: contenido **auto-escrito por el modelo, sin verificar** — es una libreta, no un oráculo | ¿El modelo entendió el código? ¿La nota de memoria es cierta? | **instrumento** (devuelve, no bloquea) |
| 7 | **Cambiar** | **El gate**: ciclo de imports NUEVO o cruce de frontera NUEVO en `.gb-boundaries`. Se niega al falso verde (reglas ilegibles / 0 módulos → exit 1) | `check` (`TEST_REMOVED`, `ASSERT_WEAKENED`): regex sobre el diff, PROXY que informa | La honestidad del `.gb-boundaries` (opt-in: sin fichero, cero enforce) | **gate** |
| 8 | **¿Se usa?** | Capturas leídas, comandos corridos: contadores deterministas | Tasa de adopción como señal de valor | ¿Por qué se abandonó? (regla 5: se investiga, no se blinda) | contador |

**Solo tres fases gatean de verdad: la 3, la 4 y la 7.** Y no por casualidad —son las tres cuyo hecho
lo produce git, el AST o una ejecución, no el modelo—.

---

## Qué se integra y qué es propio

La primera mitad del ciclo **no se construye desde cero** (H7: integrar Spec Kit, no reinventar). Spec
Kit ya hace `specify → clarify → plan`, que son las fases 1-3 como *conversación guiada*.

**La frontera exacta, en una frase:** gb acaba en el último hecho que git, el AST o el intérprete
producen sobre código Python. Toda decisión de secuencia y todo artefacto que el modelo escribe
—la spec, la prosa de un ADR, el `idea.lock`— queda fuera. gb **provee** los oráculos (exit-code =
gate, JSON = hechos); el arnés que recorre las ocho fases se monta encima, integrando gb + Spec Kit +
la forja con `gb … --gate; if $?` en cada checkpoint (regla 7). **gb nunca sabe que hay ocho fases.**

Lo que galaxy-brain aporta —y nadie más— es **el suelo determinista de cada fase, en la forma que de
verdad tenga**: un **gate** donde el hecho es externo (3, 4, 7), un **instrumento** que devuelve sin
bloquear donde solo hay un mapa (5, 6), y una **detección de drift o de referencias fantasma** donde el
resto es juicio humano (1, 2). gb no reimplementa la guía; le pone el único suelo que un hecho puede
sostener, y **dice cuándo ese suelo se acaba y empieza el humano**. La disciplina, no las tools.

---

## Lo que esto cambia respecto a hoy

- **`floor` deja de detectar pasivamente** y pasa a **guiar por fases** — pero solo bloquea donde hay un
  hecho externo que lo justifique; en el resto, informa y pide.
- **La fase 4 no resucita la forja: la consume.** El motor (generar → verificar → reparar, con modelo
  dentro) sigue **descartado** dentro de gb (regla 1); si algún día existe, vive fuera y consume los
  oráculos por exit-code/JSON. Lo que gb le da, verificado contra el código (interrogatorio, 3-ago): el
  **gate de acoplamiento** (ciclos + cruces, hecho AST — los símbolos fantasma **no** gatean: se cuentan
  con su motivo, no adivinan), la **consola de crashes** y un **mapa fiel al arrancar**. El abaratamiento
  real no está en verificar más barato —gb no tiene oráculo de correctitud: la consola atrapa crashes,
  justo lo que el LLM menos rompe— sino en que el modelo dé **menos vueltas del loop** porque construye
  sobre un mapa cierto: menos errores de nacimiento, que es la premisa. Y las `.gb-boundaries` las
  declara el **humano**: si el loop escribiera sus propias reglas, el gate mediría contra el generador
  (regla 11). El **recibo de ejecución** sigue **descartado** (3-ago) y **"dije listo sin ejecutar" no
  tiene gate** — se pide al humano, no se comprueba.
- **El éxito se mide distinto.** No por latencia ni por número de comandos, sino por la premisa: **¿el
  código nace con menos errores conocidos de LLM?** La métrica que hoy no existe y que esta visión
  obliga a crear.

---

## Nudos resueltos (refinados adversarialmente, 2/3-ago)

- **Retroceso entre fases — resuelto: no se prohíbe, se detecta.** En 3/4/7 sale gratis: `graph --gate`
  re-lee `.gb-boundaries` contra el AST **en vivo** en cada commit, así que retroceder = editar ese
  fichero y el gate recomputa solo, sin nada cacheado que quede obsoleto. En 1/2/6 (prosa) un solo
  `idea.lock` congela los hashes upstream y `floor` emite una línea **INFORMA** de drift que sale
  siempre y nunca bloquea; el re-sello (`gb floor --accept-drift`) es una aserción humana logueada y
  visible en el diff — auto-reporte declarado, no verificación fingida. **Agujero declarado, no tapado:**
  si editas el ADR en prosa pero no `.gb-boundaries`, el gate valida contra la frontera vieja; se deja
  como límite expuesto, porque cualquier binding ADR↔frontera lo escribiría el modelo (auto-reporte).
- **Dónde acaba gb — resuelto: gb PROVEE, no orquesta.** Ver "Qué se integra y qué es propio": gb es el
  proveedor de oráculos, el orquestador vive fuera. Lo único nuevo que gb gana es la *retirada de
  frontera* (diff de git, cae en la familia `graph`).
- **El auto-reporte en 1/2/memoria — resuelto aceptando el límite, no fingiéndolo.** Se sometieron tres
  mecanismos para hacer *inevitable* el juicio humano sin gatear (escasez por delta, firma atribuida,
  juicio a lomos de un gate/crash). **Los tres se ignoran igual**, cada uno por un camino: la escasez es
  constante justo en la fase de edición activa (banner blindness); la firma necesita un revisor que la
  regla 10 admite que no existe; el coat-tailing produce *falso silencio* en la infra-acotación callada
  —el caso exacto que la fase 1 existe para cazar—. **Veredicto: no se puede.** Un mecanismo
  determinista, sin modelo y sin bloquear, solo cambia el *coste* y la *visibilidad* de no juzgar; no
  mueve la mano del humano. La respuesta honesta —y coherente con la regla 10— es: **estas fases dependen
  de la disciplina del humano, y esa dependencia se MIDE, no se blinda.** El mínimo defendible: la línea
  INFORMA sale en el **delta** (no cookie-banner puro); `accept-drift` es una fila atribuida declarada
  como **termómetro, no cura**; y se **loguea la tasa de accept-drift** — si tiende al sello reflejo, esa
  métrica es el aviso honesto de que la casilla "SE PIDE al humano" se degradó, no un fallo a parchear.

## Lo que sigue sin resolver
- **El riesgo de ceremonia.** Un arnés de ocho fases que estorba acaba en `--no-verify`. La regla 11 es
  la que lo vigila: gatear solo sobre hechos externos, nunca sobre proxies.
