# galaxy-brain — Project Rules (v2)

Reglas para desarrollar galaxy-brain. La ley de diseño está en [ARCHITECTURE.md](ARCHITECTURE.md);
el alcance y lo que queda fuera, en [SCOPE.md](SCOPE.md); la evidencia, en
[docs/research-report.md](docs/research-report.md).

**Estado, 29 julio 2026.** El proyecto cambió de eje. La ley de **v1** está congelada en
[docs/v1/](docs/v1/) ([SCOPE](docs/v1/SCOPE.md), [ARCHITECTURE](docs/v1/ARCHITECTURE.md),
[README](docs/v1/README.md)): se lee, no se edita, y no gobierna lo que se construya a partir de ahora.
El código de v1 (`skills/`, `agents/`, `hooks/`, `scripts/`, `eval/`) sigue en el repo y sigue
funcionando — está apartado del camino, no borrado.

En una frase, lo que se construye ahora:

> **Cuando algo peta, te dice dónde y con qué estado, sin que tengas que reproducirlo a mano.**

Idioma: español para los documentos de decisión de v2 (coherencia con los tres de los que salen).
Inglés para cualquier cosa que llegue a publicarse. Hoy no se publica nada.

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

1. **Cero modelos en el camino caliente.** Capturar, guardar y mostrar no consultan a ningún modelo.
   La IA entra después del hecho, a mano y visible (ARCHITECTURE-v2, regla 8).
2. **Presupuesto de latencia.** < 1 s por edición, < 10 s por commit. Sobrepasarlo es violación de
   arquitectura, no un problema de rendimiento a optimizar luego.
3. **Un lenguaje, un runtime, un tipo de fallo.** Python · local · excepciones no capturadas. Un
   segundo de cualquiera de los tres se discute en [SCOPE.md](SCOPE.md) antes de tocar código.
4. **Si no cabe en la frase de arriba, no entra.** No hay excepción "pequeña": las excepciones pequeñas
   son exactamente cómo se fabricó el anterior.
5. **El abandono se investiga, no se blinda.** Si dejas de usar la herramienta, prohibido añadir un hook
   que lo impida. Ese dato es el único termómetro honesto que ha dado el proyecto.
6. **Nada project-specific.** Rutas, stacks o comandos cableados son bugs; todo se detecta en ejecución.
7. **No vendoring.** Lo externo se integra por referencia: detección + instalador oficial + verificación.
8. **La fuente canónica es ESTE repo.** Nunca se edita una copia en `~/.claude/`.
9. **Los loops autónomos nunca mergean.** Vigente mientras `skills/` y `agents/` sigan siendo
   ejecutables: ningún loop, skill o agente mergea *por su cuenta*, y `hooks/verify-invariants.js` lo
   bloquea mecánicamente mientras hay marcador de loop activo. Un merge que un humano dirige
   explícitamente en sesión interactiva es decisión humana, no auto-merge — eso sí se permite
   (decisión del owner, 2026-07). Una regla de seguridad no se retira antes que la máquina que vigila.

## Workflow

- Antes de empezar una fase: escribir su criterio de terminado comprobable. Sin criterio, no se empieza.
- Antes de añadir algo: decir qué regla de [ARCHITECTURE.md](ARCHITECTURE.md) lo motiva. Si no
  hay ninguna, la respuesta por defecto es no.
- Antes de tocar `skills/`, `agents/` o `hooks/` (código v1 congelado): decir por qué el cambio no
  puede esperar a que ese código salga del repo. Mantener lo apartado es gasto.
- Antes de commitear, mientras el plugin exista: `claude plugin validate .` limpio.
- El paso a v3 (las gates deterministas de acoplamiento y sobreingeniería) tiene tres condiciones
  escritas en [SCOPE.md](SCOPE.md). No se renegocian: se cumplen o no hay v3.

## Commit discipline

- Formato: `type: descripción corta` (`feat`, `fix`, `refactor`, `docs`, `chore`).
- Un cambio lógico por commit. Cambios de comportamiento y cambios de documentación, por separado.
