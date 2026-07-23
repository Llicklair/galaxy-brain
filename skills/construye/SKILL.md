---
name: construye
description: "Construcción autónoma dirigida por especificación (Spec-Driven Build) — la hermana de /forja que EDIFICA en vez de revisar. Se apoya en GitHub Spec Kit para la mitad delantera (constitution→spec→clarify→plan→tasks) y le injerta el motor verificado de la forja en /speckit-implement: test-first de ACEPTACIÓN, generador≠evaluador (otro modelo), gate de suite COMPLETA (sin regresión), barrido por-clase y entrega en PR o local — NUNCA auto-merge. Usa /speckit-converge para brownfield (proyectos grandes, feature a feature). Úsalo con /construye (una feature/lote) o /loop construye (continuo)."
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
- **Gates reales**: lee `.github/workflows/*`, `package.json` scripts, `pyproject.toml [tool.*]`, `Makefile`
  y anota los comandos exactos de lint/type/test/build por subproyecto.
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
3. `/speckit-plan` → arquitectura, stack, touch-points, `Constitution Check`.
4. `/speckit-tasks` → `tasks.md` ordenado, atómico, con `[P]` (paralelo) y estructura **TDD-first**.

## 3. El loop autónomo de construcción (aquí injerta la forja)
Por cada tarea/historia de `tasks.md`:
- **MARCO** (orquestador): `gitnexus_impact` de dónde toca la tarea + grep de hermanas del patrón a imitar.
- **ÁTOMO test-first** (`loop-tester`): escribe el **test de ACEPTACIÓN** derivado de los
  FR-###/SC-###/acceptance-scenarios **EN ROJO** (aún no construido). Es el *Definition of Done* ejecutable.
  El evaluador confirma que el test es significativo (no tautológico) y que ejercita el camino de la spec.
- **ÁTOMO build** (`loop-fixer` como *implementer*): construye la tarea hasta poner el test **verde**, en
  el worktree, respetando capas + constitución (lo que ésta declare intocable → inbox).
- **PUERTA — generador≠evaluador** (`loop-evaluator`, **OTRO modelo**, asume roto): verifica
  (a) test de aceptación verde, (b) **suite COMPLETA** verde — **no rompe lo existente** (gate de
  regresión: lo más importante en brownfield), (c) lint/type/build, (d) ¿el código **cumple la spec** de
  verdad? (no un verde tautológico), (e) ¿respeta la **constitución**? REJECT → vuelve al
  implementer (máx 3 rondas). Tras 3 fallos → revierte e item a inbox con `infra-fail`/`needs-human`.
- **Marca `[X]` en `tasks.md` SOLO tras PASS del evaluador** (lo escribe el orquestador, no el worker).
- **Independencia de modelo** (no opcional): el evaluador corre en modelo DISTINTO al implementer; el
  orquestador lo FUERZA al lanzar (`model`). Si solo hay 1 modelo: degrada con rol adversarial y **anótalo**.
- **Barrido por-clase**: si la tarea introduce un patrón repetido, antes de cerrar el lote demuestra
  `nº sitios == construidos + inbox` (grep de TODO el repo). Construir UNA instancia sin esa prueba → REJECT.
- **Fan-out**: las tareas `[P]` que Spec Kit ya marca corren en paralelo (worktree aislado por implementer
  que muta); si comparten ficheros, serializa. Determinista con la herramienta **Workflow**.

## 4. Brownfield — el bucle `converge` (la clave para proyectos grandes)
Tras un lote de implement: `/speckit-converge` evalúa el código vs spec/plan/constitución **atado al
file-scope del plan** (NO barre todo el repo) → añade los gaps como `## Phase N: Convergence`
(missing / partial / contradicts / unrequested), **append-only**, CRITICAL primero. Loop:
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
`/construye` = una feature o un lote. `/loop construye` = continuo (feature a feature vía converge;
cadencia corta ≈ casi continuo). Para SOLO con "para" explícito; entonces presenta el resumen de la
bitácora. Si la cuota se agota, detente y resume.
