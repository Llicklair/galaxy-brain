---
name: construye
description: "Construcción autónoma dirigida por especificación (Spec-Driven Build) — la hermana de /forja que EDIFICA en vez de revisar. Se apoya en GitHub Spec Kit para la mitad delantera (constitution→spec→clarify→plan→tasks) y le injerta el motor verificado de la forja en /speckit-implement: test-first de ACEPTACIÓN, generador≠evaluador (otro modelo), gate de suite COMPLETA (sin regresión), barrido por-clase y entrega en PR o local — NUNCA auto-merge. Fast-path para cambios atómicos (/construye --fast): salta los artefactos de ceremonia pero conserva las 5 gates; auto-escala a ceremonia completa si el cambio crece. Usa /speckit-converge para brownfield (proyectos grandes, feature a feature). Úsalo con /construye (una feature/lote), /construye --fast|--full, o /loop construye (continuo)."
---

# /construye — Spec-Driven Build verificado (la forja que edifica)

El **dual de /forja**. La forja REVISA lo que existe; `/construye` EDIFICA lo que falta **desde una
especificación**. Misma regla de oro: **el loop construye y verifica; NUNCA auto-mergea ni commitea sin
tu OK. Tú decides.** El generador no se auto-aprueba: lo verifica un evaluador independiente (otro modelo).

> No reinventa la rueda. Adopta **GitHub Spec Kit** (estándar de facto, ~116k★, nativo en Claude Code)
> para los artefactos y las fases, y le añade la única parte que no existe como producto en 2026: el
> **motor de verificación cruzada + barrido por-clase + loop continuo bajo nunca-auto-merge** de la forja.

## La costura (por qué encaja)
`/speckit-implement` **genera código pero deliberadamente NO verifica** (su SKILL.md lo dice:
"external verifier handles verification/quality gates"). **Ese hueco es el slot de la forja.** Y Spec Kit
trae un registro de hooks oficial (`.specify/extensions.yml`) donde la verificación se cablea sin parchear
nada. `/speckit-converge` es el bucle brownfield (mapea intención→código, **solo añade** lo que falta).

| Spec Kit aporta (tal cual) | La forja aporta (el motor) |
|---|---|
| constitution / spec / clarify / plan / tasks | loop driver + cadencia (one-shot o continuo) |
| converge (gaps brownfield, append-only) | test-first de **aceptación** (DoD ejecutable) |
| hooks + `[P]` (paralelo) + estructura TDD | **generador≠evaluador** en **otro modelo** |
| | gate de **suite COMPLETA** (sin regresión) + checkpoints |
| | **barrido por-clase** (sin regresión) |
| | worktree · pr/no-pr · **nunca auto-merge** · gitnexus MARCO |

## 0. SETUP (detéctalo, no lo hardcodees)
- **Spec Kit presente**: ¿existe `.specify/` y las skills `/speckit-*`? Si NO →
  `uvx --from git+https://github.com/github/spec-kit.git specify init . --integration claude --script sh`.
  Sin Spec Kit, `/construye` no arranca: lo reporta y para.
- **Sembrar la constitución** (`/speckit-constitution`): puéblala desde `ARCHITECTURE.md` + `CLAUDE.md` +
  las reglas rojas del repo. Si el proyecto quiere blindar áreas sensibles, que las declare aquí como
  principios MUST. La constitución es la LEY que el evaluador hace cumplir (REJECT si se viola).
- **COMPILAR la constitución** (sube la ley de "prompt" a "mecánica"): convención RFC — los principios
  llevan MUST/MUST NOT/NEVER en MAYÚSCULAS. El orquestador corre
  `node "${CLAUDE_PLUGIN_ROOT}/scripts/constitution.js" extract <constitution.md>` + `scaffold law/` y
  después RELLENA cada stub con su gemelo mecánico: regla ast-grep inline, o `command` (import-linter /
  dependency-cruiser / ArchUnit — instálalos por referencia si el principio es de capas). Lo que no se
  deja compilar se marca `judged-only` HONESTAMENTE — el informe de `check` dice cuántas leyes son de
  hierro (mecánicas) y cuántas de papel (solo juicio del evaluador). Una ley que no se puede ejecutar
  no es ley: los ERROR bloquean.
- **Gates reales**: lee `.github/workflows/*`, `package.json` scripts, `pyproject.toml [tool.*]`, `Makefile`
  y anota los comandos exactos de lint/type/test/build por subproyecto.
- **API con esquema** (`openapi.{yaml,json}` / GraphQL): añade `schemathesis` como gate extra si está
  o se instala (`pip install schemathesis`) — el spec del API ya ES un oráculo ejecutable
  (property-tests automáticos desde el esquema). Detectado, nunca impuesto.
- **Modo de entrega** (igual que la forja): `pr` (worktree + PR acumulado) o `no-pr` (working tree local,
  sin commitear). "construye con PR" / "construye sin PR" / por defecto, el último.
- **Seguridad al ejecutar gates** (la allowlist NO es sandbox): repo de confianza → auto-ejecuta; repo
  ajeno sin auditar → sandbox o "verificación no disponible" (a inbox, sin ejecutar).
- **GitNexus**: si hay grafo, da el MARCO (dónde enchufa la feature) sin meterlo en contexto.

## 1. La forma: el sándwich, pero hacia ADELANTE
**MARCO GLOBAL → ÁTOMOS → PUERTA GLOBAL**, sostenidos por el ORQUESTADOR (la sesión principal):
- **MARCO**: dónde enchufa la feature (`gitnexus_impact`), **patrones HERMANOS a imitar** (cómo se
  construyen features parecidas en el repo → consistencia), contratos/tipos, capa correcta.
- **ÁTOMOS**: por tarea, test-first de aceptación + implementer, informados por el marco.
- **PUERTA**: por LOTE — evaluador cross-modelo + suite COMPLETA + barrido por-clase + converge.

## 2. Mitad delantera — Spec Kit con PUERTA HUMANA
1. `/speckit-specify` (desde tu descripción de la feature) → genera `spec.md` con marcadores
   `[NEEDS CLARIFICATION]` donde haya ambigüedad.
2. `/speckit-clarify` — **PUERTA HUMANA**: el loop NO inventa requisitos. Resuelve las ambigüedades
   contigo (o las deja marcadas); **apruebas la spec** antes de planificar. (Paralelo al anti-falso-
   positivo de la forja: ante duda, pregunta, no rellenes a ciegas.)
3. **Criterios de aceptación en EARS** (notación pública, origen Rolls-Royce — adoptada con atribución,
   ver deep-scan del plugin): al cerrar clarify, reescribe cada criterio como
   `WHEN <disparador> THE SYSTEM SHALL <respuesta observable>` (los 5 patrones EARS: ubicuo, por evento,
   por estado, comportamiento-no-deseado, opcional). La regla del injerto: **1 cláusula EARS = 1 test de
   aceptación**. Si un criterio no se deja escribir en EARS, no es testeable → vuelve a clarify, no pasa
   a plan. Esto convierte la spec en la lista exacta de oráculos que vendrán.
   **Compilación mecánica** (`scripts/ears.js` del plugin): el orquestador corre
   `node "${CLAUDE_PLUGIN_ROOT}/scripts/ears.js" extract <spec.md>` — asigna IDs estables (EARS-###) y
   señala como NEEDS-CLARIFY toda línea con SHALL que no encaje en un patrón (esas vuelven a clarify) —
   y luego `scaffold --lang <python|vitest>` → un stub EN ROJO por cláusula, etiquetado con su ID.
4. `/speckit-plan` → arquitectura, stack, touch-points, `Constitution Check`.
5. `/speckit-tasks` → `tasks.md` ordenado, atómico, con `[P]` (paralelo) y estructura **TDD-first**.

## 2·bis — Fast-path: mismas gates, sin ceremonia de artefactos
La crítica nº1 de adopción de Spec Kit es la **ceremonia completa sobre un cambio de una línea**
(destruye el uso; medido en el rig A/B: la disciplina costó +58% tokens sobre un `>`→`>=`). El
fast-path la corta **saltando artefactos, NUNCA gates** — porque un documento que ninguna gate lee es
decoración, pero una gate que no corre es código sin verificar.

- **Disparador (automático por defecto, honesto — no un flag que se olvida)**: el orquestador propone
  fast-path cuando el cambio (a) mapea a **una sola** cláusula EARS *y* (b) el `gitnexus_impact` /
  scope estimado toca **≤2 ficheros de producción**. Override explícito: `/construye --fast` lo fuerza,
  `/construye --full` exige ceremonia. Ante duda → ceremonia (el sesgo seguro).
- **Qué SALTA** (solo papeleo): `spec.md`/`plan.md`/`tasks.md` como ficheros → se colapsan en **una**
  cláusula EARS inline (`WHEN … THE SYSTEM SHALL …`); la ronda formal de `clarify` (solo pregunta si
  hay ambigüedad real, §2.2 sigue siendo puerta si la hay); `converge` (no aplica a un átomo).
- **Qué CONSERVA — idéntico, innegociable**: (1) test-first de aceptación con esa cláusula EARS
  (`ears.js` sigue exigiendo 1 cláusula = 1 test), (2) rojo anclado por `evidence.js` antes del fix,
  (3) **generador≠evaluador en OTRO modelo**, (4) gate de **suite COMPLETA** + `test-guard.js` +
  `constitution.js check` (LAWs), (5) PR con evidencia, **nunca auto-merge**.
- **Auto-escala (apuesta reversible)**: si al ejecutar el cambio resulta mayor de lo previsto —el
  evaluador ve scope creep, aparece un 2º invariante, o toca >2 ficheros— **sube a ceremonia completa
  automáticamente** y lo anota. El fast-path nunca es un compromiso, solo un atajo revocable.
- **Red de seguridad**: como las 5 gates son las mismas, un fast-path mal juzgado **no puede colar
  código sin verificar** — a lo sumo pierde rastro documental, y el evaluador puede exigir la ceremonia.
  El riesgo es de *cobertura de spec*, no de *correctitud*.

## 3. El loop autónomo de construcción (aquí injerta la forja)
Por cada tarea/historia de `tasks.md`:
- **MARCO** (orquestador): `gitnexus_impact` de dónde toca la tarea + grep de hermanas del patrón a imitar.
- **ÁTOMO test-first** (`loop-tester`): rellena el cuerpo de los stubs que `ears.js scaffold` dejó en
  rojo (§2.3) — arrange/act/assert reales contra el criterio, **conservando la etiqueta EARS-###** —
  ciego a la implementación. Es el *Definition of Done* ejecutable.
- **Gate 1:1 cláusula↔test** (mecánica, la corre el orquestador y la exige el evaluador):
  `node "${CLAUDE_PLUGIN_ROOT}/scripts/ears.js" check <manifest> --tests <dir>` — cada cláusula con su
  test, ningún ID huérfano/inventado. ROJA → el lote no cierra.
- **Detector de test-gaming al cerrar lote**: `test-guard.js <base>..<head>` sobre el rango — si el
  implementer tocó tests EXISTENTES (borró, debilitó, saltó), cada señal se justifica ante el
  evaluador o REJECT.
- **Ley de arquitectura al cerrar lote**: `node "${CLAUDE_PLUGIN_ROOT}/scripts/constitution.js" check
  law/ --repo .` — cualquier LAW violada y el lote NO cierra, sin apelación al LLM. Las leyes
  judged-only van al prompt del evaluador junto al diff.
  El evaluador confirma que el test es significativo (no tautológico) y que ejercita el camino de la spec.
- **ÁTOMO build** (`loop-fixer` como *implementer*): construye la tarea hasta poner el test **verde**, en
  el worktree, respetando capas + constitución (lo que ésta declare intocable → inbox).
- **PUERTA — generador≠evaluador** (`loop-evaluator`, **OTRO modelo**, asume roto): verifica
  (a) test de aceptación verde, (b) **suite COMPLETA** verde — **no rompe lo existente** (gate de
  regresión: lo más importante en brownfield), (c) lint/type/build, (d) ¿el código **cumple la spec** de
  verdad? (no un verde tautológico), (e) ¿respeta la **constitución**? REJECT → vuelve al
  implementer (máx 3 rondas). Tras 3 fallos → revierte e item a inbox con `infra-fail`/`needs-human`.
- **Marca `[X]` en `tasks.md` SOLO tras PASS del evaluador** (lo escribe el orquestador, no el worker).
- **Registro rojo→verde por tarea (regla 10)**: el orquestador ancla el test de aceptación EN ROJO con
  `node "${CLAUDE_PLUGIN_ROOT}/scripts/evidence.js" red --id <tarea> --test <fichero> -- <comando>`;
  tras construir, `green` (test hash-idéntico o no cierra) + `suite` + `verdict` + `bundle` → el
  markdown va al PR. Prueba mecánica de que el DoD existía ANTES del código y nadie lo debilitó.
- **Independencia de modelo** (no opcional): el evaluador corre en modelo DISTINTO al implementer; el
  orquestador lo FUERZA al lanzar (`model`). Si solo hay 1 modelo: degrada con rol adversarial y **anótalo**.
- **Barrido por-clase**: si la tarea introduce un patrón repetido, antes de cerrar el lote demuestra
  `nº sitios == construidos + inbox` (grep de TODO el repo). Construir UNA instancia sin esa prueba → REJECT.
- **Fan-out**: las tareas `[P]` que Spec Kit ya marca corren en paralelo (worktree aislado por implementer
  que muta); si comparten ficheros, serializa. Determinista con la herramienta **Workflow**.

## 4. Brownfield — el bucle `converge` (la clave para proyectos grandes)
Tras un lote de implement: `/speckit-converge` evalúa el código vs spec/plan/constitución **atado al
file-scope del plan** (NO barre todo el repo) → añade los gaps como `## Phase N: Convergence`
(missing / partial / contradicts / unrequested), **append-only**, CRITICAL primero. Estilo
**delta-spec** (idea de OpenSpec, con atribución): cada fase de convergencia especifica el CAMBIO
(qué falta / qué contradice), nunca re-describe el sistema entero. Loop:
**implement (con las gates de la forja) → converge → implement … hasta "✅ Converged"**. Por eso ES viable
en repos enormes: se trabaja **feature a feature**, no el repo entero de golpe.

## 5. Entrega + PUERTA HUMANA — NUNCA auto-merge
- **`pr`**: rama `loop/construye/<feature>` + UN PR con **changelog spec→construido** (qué se construyó,
  qué FR/SC cubre, qué riesgo). Créalo la 1ª vez; luego solo push. NUNCA mergees.
- **`no-pr`**: cambios en el working tree **sin commitear**, para revisar en el Source Control del IDE y
  commitear tú por lotes. Sin PR, sin push. Estado del loop FUERA del repo (`~/.claude/construye-state/`).
- En AMBOS: **nunca se mergea ni commitea sin tu OK.**

## 6. Wiring opcional (refuerzo por hook)
El orquestador `/construye` ya verifica por sí mismo. Para que la verificación se aplique **incluso si
alguien corre `/speckit-implement` a mano**, registra un `hooks.after_implement` en
`.specify/extensions.yml` (plantilla en `integrations/speckit-after-implement.yml`). Es refuerzo, no
requisito.

## Honestidad (igual de dura que en la forja)
- `/construye` **sube el suelo**: construye lo verificable y **escala lo dudoso** (decisiones de
  producto, ambigüedad de spec) a clarify/inbox. No es un ingeniero senior; es un loop verificado.
- "**Construido y verificado**" = test de aceptación verde + suite completa verde + cumple la spec. Lo no
  probable con la infra (concurrencia que pide BD real, etc.) → "**correcto por construcción, sin prueba
  empírica**", no "verificado". Dilo así en el PR.
- **Nunca auto-merge ni commit sin tu OK.**

## Mapeo de agentes (reutiliza los de la forja)
`loop-tester` → test de **aceptación** · `loop-fixer` → **implementer** (construye) · `loop-evaluator`
(**otro modelo**) → verifica spec + regresión + constitución. No hace falta `loop-finder`: el papel de
"buscar lo que falta" lo hace `/speckit-converge`.

## Continuación / parada
**Marcador de loop (arma el hook de invariantes — obligatorio).** Al ARRANCAR una construcción autónoma:
`mkdir -p ~/.claude/galaxy-brain && touch ~/.claude/galaxy-brain/loop-active`; al PARAR (para/aborto/cuota):
`rm -f ~/.claude/galaxy-brain/loop-active`. Con el marcador, el hook bloquea todo `gh pr merge` del loop
—entrega PR y para, el merge lo decide el humano—; sin marcador (interactivo), un merge pedido por el
humano sí pasa. No es auto-merge.

`/construye` = una feature o un lote (ceremonia o fast-path según §2·bis). `/construye --fast` fuerza
el atajo (una cláusula EARS, sin artefactos, mismas gates); `/construye --full` fuerza la ceremonia
completa. `/loop construye` = continuo (feature a feature vía converge; cadencia corta ≈ casi continuo).
Para SOLO con "para" explícito; entonces presenta el resumen de la bitácora. Si la cuota se agota,
detente y resume.
