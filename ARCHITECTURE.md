# galaxy-brain v2 — Architecture

> La ley de diseño de v2. El *qué* está en [SCOPE.md](SCOPE.md); el diagnóstico del que sale
> todo, en [conclusiones-2026-07-29.md](conclusiones-2026-07-29.md).
> La ley de v1 sigue completa y congelada en [docs/v1/ARCHITECTURE.md](docs/v1/ARCHITECTURE.md) — no se
> borra, no se edita, y no gobierna v2.

**Aviso de honestidad:** v2 no tiene código todavía. Este documento fija **reglas**, no implementación.
Todo lo que aquí no está decidido está listado abajo como pregunta abierta, a propósito. Un documento
de arquitectura escrito antes que el código solo puede legislar; si además diseña, está inventando.

---

## Tesis

v1 apostó a que lo que movía la aguja era **verificación determinista + generador ≠ evaluador**.
La primera mitad era correcta. La segunda metió un modelo en el camino y lo hizo caro, lento y
opcional — y lo opcional se abandona.

v2 invierte la colocación:

> **Ecosistema determinista abajo. La IA como cereza, no como motor.**

Y corrige el eje. v1 estaba construida contra el **error**, que es lo que un evaluador adversarial
detecta bien. Lo que de verdad duele no son errores: la sobreingeniería y el acoplamiento **pasan**
todas las gates en verde. Ese eje es v3, y solo si v2 se gana el derecho ([SCOPE.md](SCOPE.md)).

v2 ataca antes: **el fallo que ya ha ocurrido**. Una excepción es un hecho. El estado en el momento
del fallo es un hecho. No hace falta juicio para reportar hechos.

---

## La plantilla (única cosa de este repo validada por el uso)

context-mode es la sola herramienta que sobrevivió al uso diario. Sus cinco propiedades son la ley
de v2, no una inspiración:

| # | Propiedad | Consecuencia de diseño |
|---|-----------|------------------------|
| 1 | **Determinista** | Cero llamadas a modelo en el camino caliente. Ni una. |
| 2 | **Intercepta, no pregunta** | No existe el momento en que alguien decide usarlo. |
| 3 | **Devuelve en el mismo segundo** | No emite veredictos: entrega material. |
| 4 | **Hace una sola cosa** | Decible en una frase, o no entra. |
| 5 | **Sus falsos positivos son inofensivos** | El coste de equivocarse debe ser asimétrico. |

Regla derivada, y es la que decide la supervivencia a los meses:
**lo que solo dice que no es un impuesto; lo que devuelve algo se usa solo.**

---

## Reglas de diseño (la ley)

1. **Cero modelos en el camino caliente.** Capturar, guardar y mostrar no consultan a nadie. Si una
   función necesita un modelo para funcionar, no es del camino caliente por definición.
2. **Devolver, no dictaminar.** Cada ejecución termina entregando algo que el usuario quería tener.
   Una salida cuyo único contenido es "no" viola esta regla.
3. **Presupuesto de latencia, innegociable.** < 1 s en el camino de cada edición; < 10 s en el de cada
   commit. Sobrepasarlo no es un bug de rendimiento: es una violación de arquitectura.
4. **Presupuesto de overhead sobre el proceso observado.** La instrumentación tiene un techo escrito y
   medido, no estimado. Una consola que ralentiza el programa se apaga el primer día.
5. **Un lenguaje, un runtime, un tipo de fallo.** Python · local · excepciones no capturadas. Añadir
   un segundo de cualquiera de los tres es un cambio de scope, no una mejora, y va a
   [SCOPE.md](SCOPE.md) antes que al código.
6. **Los hechos se guardan crudos.** Excepción, traza y estado se persisten tal cual se capturan.
   Interpretar es un paso posterior, separado y descartable.
7. **Histórico local y append-only.** Fuera del repo observado; el arnés nunca ensucia el proyecto que
   observa (única regla de v1 que sobrevive sin enmienda).
8. **La IA solo después del hecho, explícita y opcional.** Interpretar un fallo capturado o proponer un
   arreglo es una pregunta cara que el usuario lanza a mano. Nunca está en el camino que siempre corre.
   Regla de colocación: si la respuesta se comprueba con una regla, es una gate; si no, es una pregunta
   al modelo, y entonces es cara, ocasional y visible.
9. **Fallar en silencio hacia el lado seguro.** Si la captura falla, el programa observado sigue como si
   la consola no existiera. Nunca al revés (propiedad 5).
10. **El abandono es dato, no un bug a blindar.** Si dejas de usarlo, se investiga por qué; no se
    añade un hook que lo haga inevitable. Blindarlo tapa el motivo y destruye el único termómetro
    honesto que ha dado este proyecto.

---

## Lo que NO está decidido (a propósito)

Esto se decide con código en la mano, no antes:

- **Punto de captura.** `sys.excepthook` es lo obvio, pero no cubre hilos, `asyncio` ni procesos hijos.
  Qué subconjunto entra en v1 se decide midiendo, no discutiendo.
- **Qué es "el estado".** Locales del frame, cadena de frames, argumentos, `self`. Cuánto de cada uno.
  Es la decisión cara del proyecto y la que consume el presupuesto de overhead (regla 4).
- **Serialización de objetos vivos.** Un objeto arbitrario no siempre se puede guardar. Qué se hace con
  lo irrepresentable (truncar, describir, omitir) es una decisión de producto, no técnica.
- **Formato y ubicación del histórico.**
- **La superficie de lectura.** CLI, fichero, o integración con el agente. No antes de que haya algo
  que leer.

---

## Herencia de v1

**Sigue en vigor:**

- **Evidence over folklore** — una decisión cita un hecho medido o trae evidencia nueva a `docs/`.
  "Otros lo hacen" no es una razón.
- **No vendoring** — lo externo se integra por referencia: detección + instalador oficial + verificación.
- **Nada project-specific** — nada de rutas ni stacks cableados; todo se detecta en ejecución.
- **Memoria en ficheros, sin vectores** (H5).
- **El repo es la fuente canónica** — se edita aquí, nunca en copias de `~/.claude/`.

**Derogado como ley central:**

- **Generador ≠ evaluador.** Sigue siendo cierto (H2: 54/56 experimentos) y sigue siendo la ley de
  cualquier cosa que use un modelo para juzgar. Deja de ser el eje del producto porque v2 no juzga:
  reporta hechos. Vuelve si vuelve la Fase 6.
- **El pipeline de siete cajas** de [docs/v1/ARCHITECTURE.md](docs/v1/ARCHITECTURE.md) — finder →
  tester → fixer → gates → evaluator → PR. Cero PRs producidos en su vida (inventario en [SCOPE.md](SCOPE.md)).
- **Companions como parte del diseño.** GitNexus, Spec Kit, Playwright, mutation testing, schemathesis:
  fuera del camino de v2. La tabla y sus verdicts se conservan en la ley v1 congelada.

**Vigente mientras la maquinaria de v1 siga instalada:**

- **Los loops autónomos nunca mergean.** forja/construye y sus agentes siguen en el repo; mientras un
  fichero de `skills/` o `agents/` pueda ejecutarse, la regla y sus hooks siguen puestos. Una regla de
  seguridad no se retira antes que la máquina que vigila.
