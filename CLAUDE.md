# galaxy-brain — Project Rules

Reglas para desarrollar galaxy-brain. La ley de diseño está en [ARCHITECTURE.md](ARCHITECTURE.md);
el alcance y lo que queda fuera, en [SCOPE.md](SCOPE.md); la evidencia, en
[docs/research-report.md](docs/research-report.md) y la libreta de uso en
[docs/pruebas-de-uso.md](docs/pruebas-de-uso.md).

En una frase, lo que hace:

> **Cuando algo peta, te dice dónde y con qué estado, sin que tengas que reproducirlo a mano.**

Esa es la columna: la consola de errores. Alrededor, la misma disciplina aplicada a otros hechos
deterministas sobre tu código — qué forma tiene (`graph`/`symbols`), qué le hizo cada cambio
(`check`), qué le falta de base (`floor`), qué se aprendió entre repos (`memory`). **Una sola
herramienta, `gb`**, un paquete Python, cero modelos en el camino, cero dependencias fuera de la
librería estándar.

Idioma: español para los documentos de decisión (coherencia). Inglés para cualquier cosa que llegue
a publicarse. Hoy no se publica nada.

## Principios

- **Restar antes que pulir.** El coste de mantener no crece con el tamaño, crece peor: cada parte roza
  con todas las demás. Ante un problema, la primera pregunta es qué quitar.
- **Devolver, no dictaminar.** Lo que solo dice que no es un impuesto; lo que devuelve algo se usa
  solo. Una función cuya única salida es un veredicto está mal colocada.
- **Evidencia sobre folklore.** Una decisión cita un hecho medido (H1–H11 u observación propia
  escrita). "Otros frameworks lo hacen" no es una razón.
- **Escribir el criterio de terminado antes de empezar.** La causa número uno de sobreingeniería es no
  saber cuándo parar. La cura cuesta una frase y va escrita antes de la primera línea de código.
- **Preguntar antes de maquinaria pesada.** Detección automática sí; loops, agentes, instalaciones, PRs
  y gasto de cuota solo tras propuesta y sí explícito.

## Hard rules (REJECT en revisión si se violan)

1. **Cero modelos en el camino caliente.** Capturar, guardar, mostrar y analizar no consultan a ningún
   modelo. La IA entra después del hecho, a mano y visible (ARCHITECTURE, regla 8).
2. **Presupuesto de latencia.** < 1 s por edición, < 10 s por commit. Sobrepasarlo es violación de
   arquitectura, no un problema de rendimiento a optimizar luego.
3. **Un lenguaje, un runtime.** Python · local. La consola captura un solo tipo de fallo: excepciones
   no capturadas. Un segundo de cualquiera de los tres se discute en [SCOPE.md](SCOPE.md) antes de
   tocar código.
4. **Si un comando no cae en una de las familias de [ARCHITECTURE.md](ARCHITECTURE.md), no entra.** No
   hay excepción "pequeña": las excepciones pequeñas son exactamente cómo se fabrica un monstruo.
5. **El abandono se investiga, no se blinda.** Si dejas de usar la herramienta, prohibido añadir un
   hook que lo impida. Ese dato es el único termómetro honesto que ha dado el proyecto.
6. **Nada project-specific.** Rutas, stacks o comandos cableados son bugs; todo se detecta en ejecución.
7. **No vendoring.** Lo externo se integra por referencia: detección + instalador oficial + verificación.
8. **La fuente canónica es ESTE repo.** Nunca se edita una copia en `~/.claude/`.
9. **Solo se bloquea sobre hechos, nunca sobre proxies.** `check` y `graph --smells` informan, no
   bloquean; solo un ciclo de imports nuevo o un cruce de frontera declarado detiene un commit. Gatear
   proxies fabrica los falsos positivos que acaban en `--no-verify`.

## Workflow

- Antes de empezar una fase: escribir su criterio de terminado comprobable. Sin criterio, no se empieza.
- Antes de añadir algo: decir qué regla de [ARCHITECTURE.md](ARCHITECTURE.md) lo motiva. Si no hay
  ninguna, la respuesta por defecto es no.
- Antes de commitear: la suite en verde (`python -m pytest tests/ -q`) y el gate limpio
  (`gb graph src --gate`). El pre-commit ([.githooks/pre-commit](.githooks/pre-commit)) corre ambos
  más `gb check --staged`; engánchalo una vez con `git config core.hooksPath .githooks`.
- Cuando falle un **test**: repetir con `pytest -l` (locales de todos los frames) antes de añadir
  ningún `print`. Casi siempre el `-l` ya trae la respuesta, y galaxy-brain **no** cubre este caso —
  pytest atrapa la excepción y no llega a `sys.excepthook`
  ([docs/pruebas-de-uso.md](docs/pruebas-de-uso.md)).
- Cuando muera un **script, CLI o servidor** (excepción no capturada): leer el estado ya capturado —
  `gb show <id>`, que el aviso trae entero, o `gb last --since 5m --json` — **antes** de volver a
  ejecutar con `print`. Es lo que se mide.

## Commit discipline

- Formato: `type: descripción corta` (`feat`, `fix`, `refactor`, `docs`, `chore`).
- Un cambio lógico por commit. Cambios de comportamiento y cambios de documentación, por separado.
