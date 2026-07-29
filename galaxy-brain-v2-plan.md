# Galaxy-brain v2 — plan de trabajo

Derivado de `conclusiones-2026-07-29.md`. Ese documento es el diagnóstico; este es qué hacer.

**Decisión de fondo, de la que cuelga todo lo demás:**

> Galaxy-brain v2 se parece a **context-mode**, no a una forja más grande.
> Determinista, intercepta en vez de preguntar, devuelve algo en el mismo segundo,
> hace una sola cosa, y sus falsos positivos son inofensivos.

**Aviso:** esto está escrito sin haber mirado el repo de galaxy-brain. Es el *qué*, no el
*dónde*. El primer paso de la primera sesión sobre ese repo es el inventario (Fase 1).

---

## Estado — 29 julio 2026

> El inventario ya se hizo, y [SCOPE.md](SCOPE.md) reordenó este plan: la **consola de errores**
> (Fase 5) ES v2; las **gates deterministas** (Fases 2–4) pasan a **v3 condicional** (solo si la
> consola sobrevive 14 días de uso). Esta tabla refleja esa decisión, no el orden numérico de abajo.

| Fase | Estado real |
|---|---|
| 0 — La libreta | La automatiza la consola (Fase 5); no arranca hasta instalarla |
| 1 — Restar | ✅ Hecho — [SCOPE.md](SCOPE.md) + v1 archivado en [docs/v1/](docs/v1/) |
| 2 — Declarar invariantes | → v3 (va con las gates) |
| 3 — La capa determinista | → **v3 condicional** — acoplamiento/sobreingeniería, solo si la consola aguanta |
| 4 — Que esté siempre presente | → v3, con las gates |
| 5 — La consola de errores | ✅ Núcleo hecho — `src/galaxybrain/`, 55 tests, `gb list` agrupa por firma · **falta: instalar en máquina real** |
| 6 — La IA, de cereza | Pendiente — `gb why <id>` no existe, gated tras el uso real |
| 7 — Delante de una persona | Pendiente — la única prueba del problema B |

**Lo único que mueve la aguja ahora:** instalar (`pip install -e .` + `gb on`) y usarla. El reloj de
14 días del gate v3 ([SCOPE.md](SCOPE.md)) empieza ahí.

---

## Regla que aplica a todas las fases

Cada fase tiene un **criterio de terminado comprobable** escrito *antes* de empezarla.
Sin eso, se sobreingeniera — es la causa número uno, y la cura es una frase.
Si una fase no tiene criterio, no se empieza.

**Presupuesto de latencia, innegociable:** lo que corre en cada edición, < 1 s. Lo que corre
en cada commit, < 10 s. Lo que se salga de ahí, muere en una semana. Ya pasó.

---

## Fase 0 — La libreta (corre en paralelo, empieza hoy)

No bloquea el diseño, pero es la única fuente de verdad sobre qué falla de verdad.

Durante dos semanas, cada vez que algo se rompa (en cualquier proyecto): **apuntarlo y
seguir**, sin arreglarlo sobre la marcha. Una línea: qué hacías, qué salió, qué esperabas.

- **Terminado:** dos semanas cumplidas, con la lista escrita en un fichero.
- **Para qué sirve:** decide qué gates de la Fase 3 se construyen primero. Sin esto, el
  orden lo elige la intuición, que es justo lo que lleva meses fallando.

---

## Fase 1 — Restar

Antes de construir nada, decidir qué **deja de existir**.

1. Inventario de lo que hay hoy en galaxy-brain: forja, consejo de sabios, integración con
   Spec Kit, setup, agentes del loop, hooks. Para cada pieza, dos datos honestos:
   ¿la he usado en los últimos dos meses? ¿me devolvió algo el mismo día?
2. Todo lo que responda "no" a las dos: fuera de v2. No borrado — fuera del camino.
3. Escribir en una frase qué hace v2. Si no cabe en una frase, aún no está decidido.

- **Terminado:** un `SCOPE.md` con la frase, y la lista explícita de lo que v2 **no** hace.
- **Sospecha de partida:** la forja y el consejo de sabios no sobreviven a este filtro en su
  forma actual. Los dos meten un modelo en el camino, que es lo que los hizo caros.

---

## Fase 2 — Declarar los invariantes

Es la fase aburrida y es la que hace posible todo lo demás. Una gate solo comprueba
propiedades que sepas **enunciar**; esto es enunciarlas.

Un fichero de reglas por proyecto, en texto plano:

- Qué capas existen y quién **no** puede importar a quién.
- Qué módulos son frontera (los que sí pueden cruzar).
- Qué no se toca nunca (secretos, migraciones, ficheros generados).
- Qué significa "hecho" para un cambio en este proyecto.

- **Terminado:** el fichero existe para un proyecto real y describe reglas que hoy se
  incumplen. Si no detecta ninguna infracción existente, las reglas son decorativas.
- **Por qué importa:** lo que más rompe un LLM es una regla que nadie le dijo. Si está en
  tu cabeza, se rompe siempre. No es falta de capacidad: es que no existe para él.

---

## Fase 3 — La capa determinista

Un solo comando, segundos, cero llamadas a modelo.

**Lo estándar, que ya existe y solo hay que pegar:** tipos, lint, formato, tests, y que no
haya regresión respecto a la suite completa. Esto no se escribe, se conecta.

**Lo que aporta galaxy-brain y no tiene nadie** — las dos métricas que atrapan exactamente
lo que hace mal el código escrito por IA, y que ninguna gate normal mide:

*Acoplamiento* (a partir del grafo de imports):
- módulos tocados por un mismo cambio,
- fan-in / fan-out por módulo y su variación,
- ciclos nuevos,
- cruces de frontera prohibidos por el fichero de la Fase 2.

*Sobreingeniería* (proxies, no opiniones):
- ficheros nuevos por feature,
- profundidad de indirección hasta llegar al trabajo real,
- interfaces o abstracciones con una sola implementación,
- líneas añadidas por unidad de comportamiento nuevo.

Ninguna de las dos requiere un modelo. A un modelo no le puedes preguntar de forma fiable
"¿esto está sobrediseñado?"; al grafo sí le puedes contar aristas.

- **Terminado:** un comando que corre en < 10 s sobre un proyecto real y señala al menos
  una infracción verdadera que hoy pasa desapercibida.
- **Condición de calidad:** casi cero falsos positivos. Una gate que chilla sin motivo acaba
  en `--no-verify`, y entonces es peor que no tenerla porque crees que estás cubierto.

---

## Fase 4 — Que esté siempre presente

Sin depender de que nadie se acuerde, incluido tú.

- **Hook del agente** (PostToolUse sobre Edit/Write): corre el subconjunto rápido tras cada
  edición. Presupuesto: < 1 s.
- **Cuello de botella del repo** (pre-commit): corre el conjunto completo. < 10 s.
- **Nada en prosa.** Una instrucción en CLAUDE.md es una sugerencia; un hook es un hecho.

- **Terminado:** dos semanas de uso sin que lo desactives ni una vez.
- **Criterio de fracaso, escrito ahora que no duele:** si te descubres poniendo `--no-verify`
  o desactivando el hook, **no se blinda — se investiga por qué**. El abandono es el único
  termómetro honesto que has tenido nunca. Taparlo es perderlo.

---

## Fase 5 — La consola de errores

La pieza que **devuelve** algo en vez de solo decir que no. Es la que hace que se use por
interés y no por obligación, y la candidata real al "no puedo vivir sin esto".

Alcance de la v1, y es alcance duro: **un lenguaje, un runtime, un tipo de fallo.**
Python, ejecución local, excepciones no capturadas.

- Captura el estado alrededor del fallo, no solo el stack trace.
- Determinista de arriba abajo: la excepción es un hecho, el estado es un hecho.
- Acumula histórico: qué se rompió, cuántas veces, dónde. Es la libreta de la Fase 0,
  automática.

- **Terminado:** ante un fallo real, te dice dónde y con qué estado, sin que tengas que
  reproducirlo a mano.
- **Dónde se muere esto:** en la tentación de soportar todos los lenguajes y todos los
  fallos. Esa tentación es la que fabrica monstruos. Mostrar lo que el runtime ya escupe es
  fácil — eso hace VS Code. Lo caro es capturar el estado, y ahí es donde hay que quedarse.

---

## Fase 6 — La IA, de cereza

Solo donde la pregunta **no cabe en una regla**: interpretar un fallo capturado, proponer un
arreglo, redactar una especificación. Nunca en el camino que tiene que estar siempre puesto.

Regla de colocación: si la respuesta se puede comprobar con una regla, es una gate. Si no,
es una pregunta al modelo, y entonces es cara, ocasional y explícita.

---

## Lo que este plan NO resuelve

Los errores que sobreviven a un arnés perfecto son los de **"he construido correctamente la
cosa equivocada"**. Eso es el problema B, y ninguna verificación lo toca.

Galaxy-brain v2 puede dejar de romperse y seguir sin que nadie lo necesite. La única prueba
para B es la Fase 7, que no es técnica:

**Fase 7 — ponerlo delante de una persona que no seas tú.** Una. Y aguantar lo que pase,
incluido el silencio. Ese silencio también es información, y es la que llevas meses sin
recibir.
