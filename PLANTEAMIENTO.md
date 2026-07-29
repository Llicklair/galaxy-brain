# galaxy-brain — El planteamiento

Qué es este proyecto ahora que la premisa original está retirada. La ley de diseño sigue en
[ARCHITECTURE.md](ARCHITECTURE.md); el alcance, en [SCOPE.md](SCOPE.md); las reglas de trabajo, en
[CLAUDE.md](CLAUDE.md). Este documento está por encima de los tres: dice **para qué**.

Escrito el 30 de julio de 2026, un día después del giro.

---

## 1. Lo que se retira

La premisa fundacional era:

> Un arnés con el que Claude construya mejor, sin fallos, hasta ser prácticamente infalible.

Se retira. No por decepción con la ejecución — por tres razones, y solo una de ellas era arreglable.

**1. Hay un techo, y no es de ingeniería.** Escrito en
[conclusiones-2026-07-29.md](conclusiones-2026-07-29.md) §5: *una gate solo comprueba propiedades que
sepas enunciar*, y los errores que sobreviven a un arnés perfecto son los de **"he construido
correctamente la cosa equivocada"**. Un arnés verifica contra una especificación; el error caro vive
en la especificación. "Infalible" exigiría un oráculo de *¿es esto lo que había que construir?*, que
es precisamente lo que se intenta producir.

**2. El arnés se construyó en el eje que no dolía.** §6 del mismo documento: la sobreingeniería pasa
todas las gates, el acoplamiento pasa todas las gates, y los tests los escribe el mismo proceso que
escribió el código — el verde no es prueba cuando examinando y corrector comparten el malentendido.
v1 estaba diseñada contra la **equivocación**; lo que degrada un proyecto es otra cosa.

**3. La premisa violaba la regla antisobreingeniería del propio proyecto.** [CLAUDE.md](CLAUDE.md)
exige un criterio de terminado comprobable escrito antes de empezar, porque *la causa número uno de
sobreingeniería es no saber cuándo parar*. **"Infalible" no tiene criterio de terminado.** Es
infinito por construcción: cada fallo que sobrevive justifica una capa más. Eso explica el resultado
medido en [SCOPE.md](SCOPE.md) — `skills+agents+hooks` son 930 líneas, el 5% de la masa; `scripts/`
pesa el doble y `eval/` seis veces más. **El monstruo no fue la forja, fue el andamio.**

### Lo que dice la medición, con sus dos honestidades

`eval/` existía como puerta de credibilidad: *medir si galaxy-brain mejora resultados, o si nos
estamos contando un cuento*. Resultado de las ejecuciones disparadas (t1/t2/t5/t6): **las recompensas
convergen 8/8**. La disciplina ganó en coste y en evidencia, no en pasa/falla.

- **A favor:** el propio [eval/README.md](eval/README.md) avisa de que es un *fix benchmark*, no de
  descubrimiento — los dos brazos reciben el mismo informe de bug, así que la ventaja de
  descubrimiento queda excluida por construcción. Y faltaba una tarea con trampa donde el atajo fuese
  el camino de menor esfuerzo. Sin eso, los brazos no se pueden separar.
- **En contra:** n=1 por tarea y brazo. No demuestra que el arnés estorbe. Pero no demuestra que
  sirva, y demostrarlo era la razón de construirlo.
- **Y una deuda:** ese resultado **no está en el repo**, vive en memoria ([SCOPE.md](SCOPE.md) lo
  registra como el único dato empírico huérfano). Un proyecto sobre evidencia que no guarda la suya.

---

## 2. La tesis que la sustituye

> **Un arnés no puede hacer a Claude infalible. Sí puede hacer que sus fallos sean baratos de
> encontrar, imposibles de esconder y estructuralmente acotados.**

Y con ella, un cambio de forma:

> **Deja de construir un arnés que juzga a Claude. Construye uno que le da de comer.**

v1 era adversarial de arriba abajo: su forma entera era *pillar al modelo*. La medición dice que
pillar no movió pasa/falla. **Alimentar** — darle el hecho que si no tiene que re-derivar — es otra
cosa, no está medida, y encaja con el principio 2 de [CLAUDE.md](CLAUDE.md), *devolver, no
dictaminar*: juzgar cuesta una llamada a modelo por comprobación y produce un veredicto, que es un
impuesto; alimentar cuesta cero y devuelve algo.

---

## 3. El hallazgo: la lista ya estaba escrita

[conclusiones-2026-07-29.md](conclusiones-2026-07-29.md) §10 responde a *qué haría a un Claude
notablemente mejor*, **ordenado por impacto real**. Al cruzarlo con lo construido desde entonces
aparece algo que nadie había conectado: **v3 construyó tres de los siete niveles sin saber que los
estaba construyendo, y dejó sin construir el primero.**

| # | Nivel (§10) | Estado hoy |
|---|---|---|
| 1 | **Bucle de feedback rápido.** *"Con diferencia el primero. Si puedo ejecutar y ver el resultado en dos segundos, convergo. Si tarda diez minutos, adivino."* | **SIN CONSTRUIR.** Es la Fase A. |
| 2 | Gates deterministas en un comando y en segundos | Hecho — `gb graph --gate`, <10 s con la suite |
| 3 | Un mapa, no una lectura: qué existe y qué depende de qué | Hecho — `gb graph` |
| 4 | Los invariantes escritos. *"Lo que más rompo es una regla que nadie me dijo"* | Hecho — `src/.gb-boundaries`, 12 reglas |
| 5 | El porqué de lo ya decidido, para no "arreglar" lo deliberado | Parcial — vive en mensajes de commit y docstrings |
| 6 | Un entorno donde equivocarse salga barato | Parcial — worktrees, heredado de v1 |
| 7 | Un criterio de terminado comprobable | Hecho como regla; este documento la aplica |

Y la frase que cierra §10: **nada de esto es más contexto, más herramientas ni más modelos.**

**El planteamiento, entonces, no es inventar una lista nueva. Es terminar ésta.** Empezando por el
nivel 1, que es el de mayor impacto declarado y el único de los cuatro primeros que sigue vacío.

---

## 4. Las tres propiedades tienen consumidores distintos

Ésa es la razón de que parezcan tres máquinas inconexas. Se ordenan solas en cuanto se nombra quién
consume cada una:

| Propiedad | La consume | Qué le da | Qué existe hoy |
|---|---|---|---|
| **Baratos de encontrar** | **Claude** | El estado del fallo sin re-derivarlo | v2 entera — pero apuntando al humano, no a él |
| **Imposibles de esconder** | **El owner** | Confianza en el verde | `evidence.js`, `test-guard.js`, y el *no silent green* de v3 |
| **Estructuralmente acotados** | **El proyecto** | Que no se degrade sin enterarse | `gb graph` (ciclos, fronteras, smells) |

Un solo objeto por debajo: **el cambio**. Las tres responden *"¿qué hizo realmente este cambio?"*.
Ninguna responde *"¿esto es bueno?"*. Por eso ninguna necesita un modelo, y por eso pueden ser una
sola máquina.

---

## 5. Las fases, en orden, con su criterio de terminado

El orden no es por valor a largo plazo: es por **cuándo devuelve algo**. Ésa fue la lección del giro,
y aquí manda.

### Fase A — Alimentar (nivel 1 de §10)

`gb` deja de ser solo para el humano y entra en el bucle de trabajo de Claude. Cuando algo peta en
sesión, el estado ya está capturado en disco: se consulta, no se re-deriva volviendo a ejecutar el
programa con `print` añadidos.

- **Por qué primero:** devuelve el mismo día; es casi todo código ya construido y probado (`store`,
  `capture`, `render`); es medible sin juez; y no pide escribir aserciones aburridas, que es donde
  §5 dice que la idea se cae.

**Corrección del 2026-07-30, por la primera prueba de uso** ([docs/pruebas-de-uso.md](docs/pruebas-de-uso.md)).
El alcance escrito arriba era más ancho que el real, y se descubrió a los cinco minutos de probarlo:

- **Los tests que fallan NO están cubiertos.** pytest atrapa la excepción, así que nunca llega a
  `sys.excepthook` y no hay captura. Era el caso más común del bucle, y era el que justificaba la fase.
- **Para tests se adopta `pytest -l` por referencia**, no se construye nada: ya muestra los locales de
  todos los frames, que es más de lo que daría la captura. Reimplementarlo sería la sobreingeniería
  exacta que este documento dice combatir.
- **Lo que la Fase A cubre de verdad:** excepciones no capturadas — scripts, CLIs, servidores,
  procesos largos. Real, y hoy sin alternativa, pero una porción del bucle más pequeña de lo que se
  afirmó.

- **Criterio de terminado, corregido.** Por sesión se apunta: (a) cuántos fallos hubo, (b) cuántos
  eran excepciones no capturadas — el territorio real de `gb` —, y (c) de esos, cuántos se resolvieron
  leyendo el estado capturado **sin volver a ejecutar con prints**. Terminado: **(c) ≥ 3 en 5
  sesiones**. Contar (a) y (b) es lo que impide engañarse: mide cobertura × utilidad, no solo utilidad.
- **Qué la mata, en dos formas distintas:**
  - Si (c) se queda corto habiendo (b), el cable no sirve: **se quita**. No se mejora ni se le añade
    una capa.
  - Si (b) es ~0 en 5 sesiones, la Fase A es **correcta pero irrelevante** para este bucle. Eso
    también es un resultado, y la respuesta NO es extender la cobertura a pytest: eso ya lo cubre
    `pytest -l`.

### Fase B — No esconder

Una sola pasada determinista sobre un rango de commits que devuelve: suite completa, `test-guard`
(¿se compró el verde tocando tests que ya existían?), delta de acoplamiento, y **qué cubrió la gate**.
Los cuatro trozos existen sueltos; falta el comando que los junta y el informe único.

- **Criterio de terminado:** sobre **5 cambios reales**, cero falsos positivos, y **al menos un caso
  real detectado** que habría pasado sin ella.
- **Qué la mata:** un solo falso positivo recurrente. Una gate que chilla sin motivo acaba en
  `--no-verify`, y entonces no protege nada.
- **La trampa, dicha de frente:** lo determinista es barato de *usar*, no de *escribir*. Esta fase
  está hecha de aserciones, invariantes y tests aburridos — la materia que históricamente se salta.
  Aquí es donde este planteamiento se cae, si se cae.

### Fase C — Sacar la puerta fuera del agente

`external-gate.js` / branch protection. Un hook lo puede saltar un subagente y los settings los puede
editar el modelo; el invariante solo se sostiene cuando la última puerta vive donde el agente no
llega.

- **Va la última, a propósito.** Blindar antes de que la herramienta se use quita el único termómetro
  honesto que ha dado el proyecto: que la abandones. [CLAUDE.md](CLAUDE.md) regla 5.
- **Criterio de terminado:** un intento real de merge automático bloqueado por GitHub, no por un
  prompt ni por un hook local.

---

## 6. Lo que NO entra

- **Resucitar los cuatro agentes de v1.** La medición no los avala. Si vuelven, primero una tarea con
  trampa donde el atajo sea el camino de menor esfuerzo — sin eso el eval no separa los brazos, y ya
  se comprobó que no los separó.
- **Un modelo dentro de la gate.** El único sitio donde un segundo modelo aporta es el techo — *"he
  construido correctamente la cosa equivocada"* — porque ahí no hay oráculo determinista posible. Va
  **fuera de la gate, a mano y a petición**: [ARCHITECTURE.md](ARCHITECTURE.md) regla 8.
- **Blindar la adopción.** Ningún hook que impida dejar de usar esto.
- **Más contexto, más herramientas, más modelos.** §10 lo cierra explícitamente.

---

## 7. Cómo se sabrá que este planteamiento también falló

Escrito ahora, para no poder discutirlo después:

1. **Si a las 5 sesiones la Fase A no ha ahorrado 3 reproducciones**, la tesis de "alimentar" es
   falsa y hay que decirlo, no ajustar el criterio.
2. **Si la Fase B no llega a escribirse** en un mes, la trampa de §5 ganó: la materia aburrida sigue
   siendo el punto ciego, y el problema nunca fue de diseño.
3. **Si vuelve a crecer el andamio** — si `scripts/` o `eval/` vuelven a pesar más que lo que
   entregan — es la misma enfermedad con otro nombre.
4. **Si nadie que no sea el owner lo usa nunca.** Sigue pendiente desde §11: ponerlo delante de una
   persona que no seas tú. Es lo único que ningún test puede sustituir, y el silencio, si llega,
   también es información.

Y una deuda que se salda o se cierra: **el resultado del A/B no está en el repo.** O se registra, o
se admite que `eval/` es andamio y se retira. Un proyecto sobre evidencia no puede tener la suya en
otro sitio.
