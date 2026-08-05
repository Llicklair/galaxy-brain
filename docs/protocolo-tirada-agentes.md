# Protocolo de tirada — agentes en paralelo sobre este repo

> **Fecha:** 5 de agosto de 2026, escrito tras dos tiradas reales (6 agentes Opus, 28 tests
> rescatados, 7 hallazgos en `src/`). Esto NO es maquinaria de `gb`: es el guion del
> **orquestador** (Claude Code, o quien sea). `gb` provee los hechos; quién lanza qué y cuándo
> lo decide quien lee esta página. Si algún día `gb` orquesta, este documento es el bug.

## El ciclo

1. **Mapa vivo antes de lanzar.** `gb symbols . --html mapa.html --watch --fondo --refresco 3`
   y el navegador abierto. Sin el mapa, la tirada es ciega y este protocolo pierde la mitad.
2. **Lanzar** — un worktree por agente, tareas acotadas y disjuntas (salvo cruce a propósito,
   que también se hace: es la prueba del aro blanco). El prompt de cada agente lleva SIEMPRE:
   - leer CLAUDE.md; cero dependencias fuera de la stdlib;
   - **NO tocar `src/`**: un hallazgo se describe, no se arregla — el fix es decisión de quien
     revisa, con su propio commit;
   - NO commitear, NO push; el trabajo queda en el working tree;
   - la instrucción del `.pth` (abajo, aviso 1), con el comando de verificación exacto;
   - qué devolver: ruta del worktree, `git status --porcelain`, última línea de pytest, lista
     de lo cubierto.
3. **Mirar** — el canvas cuenta la tirada solo: panel (quién vive), consola (qué van haciendo),
   sinapsis (hacia dónde irradia cada uno), aro blanco (cruce). Un agente que no aparece en
   ~2 min o no ha escrito nada o murió: se le pregunta, no se supone.
4. **Aterrizar** — `gb tests --run --union` antes de decidir nada. Lo que se lee primero no es
   el verde: es quién NO se sostiene solo (rescate accidental) y qué no viaja en cada diff.
5. **Rescatar** — por diff (`git diff HEAD` del worktree, guardado ANTES de borrar nada),
   aplicado con `git apply --3way`, y solo lo elegido. El verde que reportó el agente no es
   evidencia; el criterio es el del paso 4.
6. **Limpiar** — `git worktree remove --force` + `git branch -D` + `git worktree prune`.
   Un repo con worktrees muertos registrados hace fallar la siguiente tirada.
7. **Apuntar** — hallazgos en `src/` que no se arreglan hoy van a la memoria del proyecto con
   fichero y línea. Un hallazgo que solo vive en la conversación está perdido.

## Los avisos, ya pagados una vez cada uno

1. **El `.pth` del editable install** pre-importa `galaxybrain` desde el checkout principal al
   arrancar CUALQUIER intérprete: un pytest en un worktree testea el código de OTRO árbol y
   pasa en verde. El conftest ya se defiende, pero los worktrees parten de un commit que puede
   no llevarlo. En el prompt del agente, siempre:
   `PYTHONPATH=<worktree>/src` + verificar `python -c "import galaxybrain.cli as c; print(c.__file__)"`.
2. **Los worktrees del Agent tool nacen ANCLADOS a un commit fijo de la sesión** — no «uno por
   detrás», como se creyó primero: tres tandas nacieron en el mismo commit con HEAD ya doce
   commits más allá, y un commit-colchón no cambió nada. Consecuencias: el aviso `parte de otra
   base` es lo esperado, `--union` rehusará mezclar con tu árbol, y **un banco commiteado después
   del ancla no existe para el agente**. Si la tirada necesita bases exactas (experimentos,
   código recién commiteado), la receta es worktrees PROPIOS: `git worktree add --detach
   <ruta> main`, el agente se lanza SIN aislamiento del harness y recibe la ruta en el prompt
   con la orden de trabajar solo ahí. Limpieza manual al terminar (el harness solo autolimpia
   los suyos). Verificar la base del agente ANTES de darle trabajo: la toma 1 del experimento
   del enrutador se gastó entera en descubrir esto.
3. **El checkpoint y los agentes no comparten CPU.** Una suite bajo el pre-commit con 1-3
   agentes Opus corriendo las suyas da rojos falsos por inanición (18 en la medición del
   5-ago). Los commits y el `--union` esperan a que la tirada termine.
4. **Nada de tiradas ni commits desde dentro de un hook de git** sin los escudos: git inyecta
   `GIT_INDEX_FILE`/`GIT_DIR` y un git heredándolas escribe en el índice REAL (pasó: fixtures
   de tests staged en este repo). `conftest.py` y `aislado._git` ya van con entorno limpio.
5. **El verde reportado no es evidencia.** «449 passed» del agente era cierto en su sesión y
   rojo sobre base limpia. Solo cuenta el paso 4.
6. **Cruce a propósito = conflicto de append al coser.** Si dos agentes añaden al final del
   mismo fichero, instruir «añade AL FINAL, bajo un comentario de sección con tu nombre» y
   resolver el conflicto quedándose las dos secciones. Es un minuto, y el aro blanco del mapa
   avisa de dónde va a pasar.

## Presupuesto orientativo (medido en este repo, agentes Opus)

- 3 agentes en paralelo: 3–7 minutos de reloj, ~40–80k tokens por agente.
- Tarea bien acotada = 3–5 tests o un análisis de un módulo. Más grande, partirla: el coste
  de revisar crece más rápido que el de lanzar.

## Lo que este protocolo no hace

No sustituye la decisión de rescate (humana o del orquestador con criterio del paso 4), no
arregla `src/` por delegación, y no corre solo: cada paso que gasta cuota se lanza a mano.
La versión que se dispara sola es exactamente la maquinaria pesada que las reglas de este
repo obligan a proponer antes de ejecutar.
