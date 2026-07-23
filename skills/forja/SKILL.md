---
name: forja
description: "Loop Engineering portable (v2): bucle autónomo que REPASA TODO un proyecto en profundidad y mejora el código sin que teclees. Descubre por flujos de ejecución (GitNexus si está) con lente rotativa, ESCRIBE tests/repros (test-first), arregla lo seguro en worktrees aislados, lo verifica con un evaluador adversarial independiente, y abre PR (NUNCA auto-merge). Genérico para cualquier producto. Úsalo con /loop forja (continuo) o /forja (una pasada)."
---

# /forja — Loop Engineering v2 (portable, profundo, nocturno)

Bucle que se diseña para correr SOLO mucho tiempo y dejar valor real: no re-escanea lo mismo,
no infla un inbox de prosa — produce **tests verdes, repros de bugs reproducibles, y PRs
revisables**. Regla de oro intacta: **el loop juzga y propone; NUNCA auto-mergea. Tú decides.**
El generador no se auto-aprueba: lo verifica un evaluador independiente (otro modelo).

> Portabilidad: este skill NO asume ningún stack. Detecta el proyecto y se adapta (ver §0).
> Vive en `~/.claude/` → disponible en cualquier repo. Un proyecto puede tener su propio
> `.claude/skills/forja` que lo especialice (p.ej. con sus propias líneas rojas); ese gana localmente.

## Modos de entrega: con-PR / sin-PR — **el PR es OPCIONAL**
El usuario elige cómo entrega el loop (por defecto recuerda el último modo):
- **`pr`** (aislado): los fixers trabajan en un **worktree** (`loop/forja/auto`) y se acumula **UN PR**
  (créalo la 1ª vez, luego solo push). NUNCA mergea. Para revisar en GitHub. Es el flujo de §3 y §5.
- **`no-pr`** (local): los fixers editan **directamente el working tree principal**, **SIN commitear** —
  para que revises los cambios en el panel Source Control de tu IDE y commitees tú por lotes. **Sin PR, sin
  merge, sin push.** Reglas duras de este modo:
  - Un fix rechazado se revierte **por-fichero** (`git checkout HEAD -- <ficheros>` + borrar los tests
    nuevos). **NUNCA** `git reset --hard`/`clean` en el tree principal (borraría tu trabajo sin commitear).
  - **Fixers en SERIE** (no en paralelo): dos fixers a la vez sobre el mismo working tree se pisarían.
  - El **estado del loop vive FUERA del repo** (p.ej. `~/.claude/forja-state/<repo>/{state,coverage,inbox}.md`)
    para no llenar `tasks/` de markdowns.
- **Disparadores**: "forja sin PR" → `no-pr` · "forja con PR" → `pr` · "forja" / "/loop forja" → el modo
  guardado. Cambia de modo solo si el usuario lo pide.
- En AMBOS modos: el evaluador independiente verifica igual, y **NUNCA se mergea/commitea sin tu OK**.

## La forma: sándwich híbrido (átomos dentro de un marco global)
Los sub-agentes son ATÓMICOS a propósito — caben en contexto, paralelizan, se revierten. Pero lo atómico
CIEGA a lo sistémico: interacciones entre tests, mitigaciones aguas abajo, **implementaciones hermanas**
del mismo bug, herencia de tipos. Por eso el loop NO es solo átomos: es **MARCO GLOBAL → átomos →
PUERTA GLOBAL**, y el marco y la puerta los sostiene el **ORQUESTADOR** (la sesión principal), no los workers.
- **MARCO GLOBAL (antes de tocar)** — construye el mapa con GitNexus (el grafo ES la visión global,
  consultable sin meterla en contexto): `gitnexus_impact` (blast radius), `processes`/`context`; y
  **escanea implementaciones HERMANAS del mismo patrón** (grep/grafo) — casi nunca el defecto está en un
  solo sitio (p.ej. `delete→409` estaba en 5 entidades; la numeración `COUNT(*)` en 2). Anota jerarquías de
  tipos (Response↔Create), recursos compartidos, y **quién YA frena el caso** (guard/constraint/RLS aguas
  abajo) → re-gradúa la severidad del finder. Pasa ese *brief* a los workers.
- **ÁTOMOS (en medio)** — finders/fixers/testers (§1–§4) informados por el brief; cada worker corre
  `gitnexus_impact` ANTES de editar un símbolo, y arregla TODAS las hermanas del patrón, no una.
- **PUERTA GLOBAL (por LOTE, no por fix)** — los fixes atómicos se acumulan; UNA pasada de integración
  cierra el lote: **suite COMPLETA** + dedup entre fixes + un crítico que mira el LOTE como conjunto
  ("¿interactúan? ¿qué quedó sin cubrir o sin verificar?"). Aquí caen las fugas que ningún `-k` ve.
- Principio: **átomos para el trabajo; grafo + orquestador para el marco y la puerta.**

## 0. SETUP del proyecto (primera vez / cada arranque) — detéctalo, no lo hardcodees
- **Raíz y subproyectos**: localiza backend/frontend/paquetes (busca `pyproject.toml`,
  `package.json`, `go.mod`, `Cargo.toml`, `Makefile`).
- **Gates reales** (lo que el proyecto considera "verde"): lee `.github/workflows/*`, `package.json`
  scripts, `pyproject.toml` [tool.*], `Makefile`. Anota los comandos exactos de lint/type/test/build
  por subproyecto en `tasks/forja/state.md` (sección "Gates detectadas").
- **SEGURIDAD al ejecutar gates — la allowlist NO es un sandbox.** Ejecutar las gates corre **código del
  repo objetivo** con TUS privilegios: `pytest` ejecuta `conftest.py`, `npm test` el script de
  `package.json`, `make`/`cargo` (+`build.rs`) su cuerpo arbitrario. Filtrar el NOMBRE del comando NO
  acota el PAYLOAD. Por tanto:
  - **Repo de confianza (tuyo / de tu equipo)**: auto-ejecuta las gates con normalidad.
  - **Repo NO confiable (ajeno, fork, público sin auditar)**: NO auto-ejecutes gates sin **sandbox**
    (contenedor con red cortada + FS limitado al worktree + sin privilegios). Sin sandbox → trátalo como
    "verificación no disponible": el fix va a inbox SIN ejecutar, para revisión humana.
  - La **allowlist** (`pytest`/`ruff`/`mypy`/`npm|pnpm|yarn test|lint|build`/`tsc`/`go test`/`cargo test`/
    `make <target>`) es solo un **primer filtro** contra ejecutables del todo desconocidos — NO una
    garantía. Un script/target fuera de ella nunca se ejecuta a ciegas: inbox + aprobación humana.
- **Entornos de ejecución**: si usa Poetry/venv/nvm, anota cómo invocar las gates DENTRO de un
  worktree (los venv/`node_modules` no se clonan con `git worktree` → ver §6 frontend).
- **GitNexus**: ¿hay grafo indexado? (`gitnexus_list_repos`). Si sí → discovery por FLUJOS (§1A).
  Si no → discovery por directorios + tests (§1B). Si está stale, `npx gitnexus analyze` primero.
- **Reglas del repo**: lee `CLAUDE.md`/`AGENTS.md`/`CONTRIBUTING` y respétalas (líneas rojas,
  límites de capa, disciplina de commits). El loop **no impone ninguna zona prohibida por sí mismo**:
  las únicas líneas rojas son las que declare el repo objetivo en su `CLAUDE.md`. Si un proyecto quiere
  blindar áreas sensibles (p.ej. cálculo de dinero/legal), que lo escriba ahí y el evaluador lo respeta.
- **Arranque seguro / fallos de ENTORNO (no solo de worker).** Antes de reusar el worktree acumulador:
  `git -C <worktree> status --porcelain`; si hay cambios sin commit (run anterior muerto por cuota/crash
  a media edición) → **resetéalo** (`reset --hard` + `clean -fd`) ANTES de seguir, no acumules estado
  sucio. Si la detección de áreas devuelve **0** (denominador=0): NO arranques el bucle (no dividas por
  cero) → reporta y manda `setup-fail` a inbox. Si `gitnexus analyze` falla (sin Node, red, repo enorme):
  **cae a §1B** (por área) y etiqueta esa pasada `gitnexus-stale`, no sigas como si el grafo fuese fiable.

## 1. DISCOVERY — repasa TODO, en profundidad, sin repetir

### 1A. Por FLUJO DE EJECUCIÓN (preferido, si hay GitNexus)
- `gitnexus` → lista de procesos/flujos (resource `…/processes`, o `gitnexus_query`). Cada flujo es
  un proceso real de usuario (login, cobro, exportar, etc.). Recórrelos uno a uno con un **cursor**
  en `tasks/forja/state.md`. Esto cubre el proyecto por COMPORTAMIENTO, no por carpetas.
- Antes de tocar un símbolo: `gitnexus_impact` para el blast radius.

### MAPA DE COBERTURA (sistemático, no por intuición) — `tasks/forja/coverage.md`
La elección de flujo NO es a ojo: se lleva un **registro de cobertura** con un **denominador con sentido**
(las áreas-flujo del proyecto = los route-files / clusters reales; NO los "procesos" autogenerados de
GitNexus, que tienen nombres-basura tipo `X → FakeResult`). Cada turno el orquestador:
1. abre `coverage.md`, **elige un flujo ⬜ PENDIENTE** (o un 🔶 para completarlo) — nunca uno ✅ ya barrido
   con la lente actual (así no se repite ni se reescribe lo hecho);
2. lo barre, lo marca ✅, y **recalcula el % (N barrados / total)**;
3. reporta el progreso ("X/total = Y%", p.ej. "12/65") — barra que sube hacia 100%.
Cuando TODOS están ✅ con una lente → vuelta completa; las siguientes vueltas **rotan la lente (1-6)** sobre
los ✅ (re-pasar con lente nueva ≠ repetir). El mapa garantiza **completitud medible** y elimina el picoteo.
**Sembrar la 1ª vez (denominador = lista de áreas-flujo), sin hardcodear stack.** Si hay GitNexus, usa
sus clusters/route-files. Si no, **detecta el stack** y lista las áreas con el patrón que corresponda:
- **Python/FastAPI/Flask/Django**: `api/*/routes/*.py`, `**/views.py`, `**/urls.py`, `**/endpoints/*.py`.
- **Node/TS (Express/Nest/Next)**: `src/routes/**`, `**/*.controller.ts`, `app/**/route.ts`, `pages/api/**`.
- **Go**: `**/handler*.go`, `**/*_handler.go`, rutas registradas en el router.
- **Rails**: `app/controllers/**/*.rb`, `config/routes.rb`.
- **Rust (axum/actix)**: `src/routes/**`, `src/handlers/**`, registros de router.
- **Frontend SPA**: vistas/páginas/stores como áreas (`src/pages/**`, `src/views/**`, `src/features/**`).
Si nada encaja, cae al fallback por ÁREA (§1B): módulos/carpetas de alto nivel = denominador. Lo importante
es un **denominador estable y con sentido** por proyecto, no el patrón concreto.
- **HONESTIDAD del %**: una ✅ = "barrido 1 flujo del área con 1 lente", NO "área revisada". El % de áreas
  es **AMPLITUD de primer contacto**, no profundidad. Reporta SIEMPRE el matiz: la cobertura real (flujos
  finos × 6 lentes) es mucho menor que el % de áreas. No vendas "40% revisado" si es "40% pisado una vez".
- **RESET / pasadas** (`/clean forja map` o "resetea el mapa", o auto al 100% de amplitud): archiva la
  pasada (lente+fecha), vuelve todas las ✅/🔶 a ⬜, incrementa la pasada y fija la **siguiente lente**
  (1→2→…→6→1). Una revisión seria = 6 pasadas (las 6 lentes) y, en cada área ✅, bajar de "área" a "flujo
  fino" (no basta 1 flujo por área).
- **OPCIÓN: nº de lentes en paralelo por flujo (1-6).** Por defecto el orquestador puede barrer un flujo
  con **N finders en paralelo, uno por lente** (fan-out), cubriendo varias/las 6 lentes en UNA visita →
  la ✅ del mapa pasa a significar "revisado por N lentes" (amplitud≈profundidad). El usuario elige N
  ("6 lentes", "3 lentes", "1 lente"): **N=6** = barrido completo por visita (más coste, más profundidad,
  menos flujos por turno); **N=1** = rápido/superficial (más flujos, menos profundo). CLAVE: **un finder
  por lente** (no un solo finder con 6 lentes — eso diluye el enfoque y baja el recall). Coste libre si la
  calidad importa; el fan-out es paralelo, el reloj apenas cambia.

### 1B. Por ÁREA (fallback sin GitNexus)
- Lista los módulos/carpetas de alto nivel; recórrelos con cursor.

### 1C. Modo DETECTOR (barato — descubrimiento DETERMINISTA, ~0 tokens de escaneo)
Disparador: **"forja detector"** (una vuelta) · **"loop forja detector"** (continuo). Para cuando el valor
está en **detalles atómicos** y NO quieres gastar tokens en pasadas LLM de 6 lentes (lo contrario del loop
nocturno caro). Premisa: el LLM se SALTA detalles atómicos; un **detector estático/AST** los caza en
segundos por ~0 tokens y el LLM solo **remedia los hits**. Barato y FINITO (converge cuando queda limpio).
- **Detector**: usa el del proyecto si existe (p.ej. `tests/_defect_detectors.py` con `scan()` →
  dict `familia → [sitios]`); si no, créalo incremental (UNA familia AST barata por vez: `except: pass`,
  `== None`, `/ len(x)` sin guard, status-write sin guard, SELECT-then-add sin UNIQUE, httpx sin timeout,
  `detail=str(e)` en un 500…). Mucho recall, poca precisión → la MAYORÍA serán **falsos positivos**.
- **Ledger** FUERA del repo (`~/.claude/forja-state/<repo>/detector-inbox.md`): registra
  `fixed + FP-descartados + pendientes`. Cada vuelta **resta el ledger** y tría **solo lo NUEVO** (no re-tría).
- **La vuelta**: (1) `scan()` (~segundos); (2) triar lo nuevo en un **SUBAGENTE** (no inflar contexto);
  (3) arreglar **solo los REALES** con guards mínimos contract-preserving, **inbox** lo arriesgado
  (migraciones, cambios de alto blast-radius) — sin sobre-afirmar concurrencia (son guards de re-entrada
  SECUENCIAL, no de carrera); (4) verificar con **tests AFECTADOS** (segundos), NO la suite completa;
  (5) actualizar el ledger.
- **Checkpoint**: la **suite COMPLETA** se corre **UNA vez por sesión** (de fondo), nunca por vuelta (si no,
  "una eternidad").
- **Ratchet**: familias cuyo fix BORRA el patrón (`detail=str(e)`, `httpx` sin timeout) → test guardrail
  baseline 0; familias tipo "guard añadido" (el patrón persiste) → **allowlist** (solo falla un sitio NUEVO).
- Entrega: pr/no-pr como siempre; **nunca auto-merge ni commit sin tu OK**.

### 1D. Modo MAX (afinado — barrido grande + profundidad máxima al MENOR coste)
Disparador: **"forja max"** (una pasada) · **"loop forja max"** (continuo). Es el **embudo**: une lo barato
(§1C) con lo profundo (§1A) para lograr las cuatro cosas A LA VEZ — barrido grande, soluciones atómicas
grandes, máxima profundidad, mínimo coste. Regla de oro: **la capa gratis barre TODO; el LLM solo
profundiza donde hay valor.** Sin dependencias externas (AST + GitNexus).
1. **BARRIDO BARATO (≈0 tokens, todo el repo)** — corre el detector AST (§1C `scan()`) y, si hay GitNexus,
   mapea flujos + `gitnexus_impact` de cada hit. Salida = lista de candidatos. **Aún NADA de LLM.**
2. **RANK por valor** — ordena por `severidad(familia) × blast-radius(grafo) × confianza`. Resta el ledger
   (§1C): solo lo NUEVO o lo cambiado (prioriza `git log` reciente). El ruido advisory se descarta de entrada.
3. **PRESUPUESTO DURO** — fija un techo de tokens por pasada (p.ej. "forja max 300k"); coge el **top-K** de
   candidatos que entra en el techo. Lo que no entra → vuelta siguiente (el ledger lo recuerda). El coste
   es **acotado y predecible**, no "hasta que se acabe".
4. **PROFUNDIDAD NARROW (LLM caro, SOLO en el top-K)** — por cada flujo candidato, **UN finder lee el
   código UNA vez y aplica las 6 lentes de golpe** (no 6 agentes releyendo lo mismo → ~6× más barato).
   Confirma el bug con repro; descarta el FP.
5. **FIX ATÓMICO GRANDE (por CLASE, no por instancia)** — escaneo de hermanas (§4): si el bug es un patrón,
   el fixer extrae el arreglo común (helper compartido) y lo aplica a TODA la familia en un lote + **1 test
   que cubre la clase**. Una solución grande > N parches sueltos.
6. **PUERTA adversarial** (§4, modelo distinto) — suite COMPLETA + prueba de barrido-por-clase
   (`nº sitios del patrón == saneados + inbox`) + sin sobre-afirmar. REJECT → vuelve al fixer (máx 3 rondas).

**Palancas de coste (todas activas en MAX):**
- **Modelo por etapa**: triaje/rank en modelo **barato** (haiku); finder profundo en sonnet; fix difícil +
  evaluador en el **fuerte**. No pagues opus por un grep.
- **Ratchet/ledger** (§1C): nunca re-analiza lo ya visto; cada vuelta solo lo nuevo/cambiado.
- **Una lectura, 6 lentes**: el coste real es LEER el código — reutiliza esa lectura para las 6 lentes.
- **Presupuesto duro**: el top-K se corta por tokens, no por agotamiento.

Honestidad: MAX **no** hace gratis el análisis profundo de TODO — hace profundo SOLO lo que la capa barata
marcó como valioso; el resto queda en el ledger para vueltas siguientes. El `coverage.md` reporta el % real
cubierto en profundidad (no el barato). Entrega: pr/no-pr como siempre; **nunca auto-merge ni commit sin tu OK**.

### Lente rotativa (profundidad, no repetición)
Cada pasada completa sobre el proyecto usa una LENTE distinta; guarda qué lente toca en el estado:
1 correctitud/bugs · 2 seguridad (authz, tenant/aislamiento, inyección, secretos) · 3 concurrencia/
estado/idempotencia · 4 manejo de errores/casos borde (None, vacío, red, timeout) · 5 **test-gaps**
(cobertura ausente) · 6 rendimiento/recursos (N+1, fugas, sin timeout). Re-pasar con lente nueva ≠ repetir.

### Fuentes de trabajo extra (priorízalas si existen)
inbox de hallazgos previos · **tests rojos** (corre la suite) · gates bloqueantes rojas · TODO/FIXME ·
ficheros cambiados recientemente (git log: más probabilidad de bug) · informes de auditoría del repo.

### JUDGE (pone el techo de calidad — el documento, Secc. III)
Por cada candidato: **¿IMPORTA?** Defecto real con arreglo objetivo → fix. Subjetivo/refactor de
gusto/que cambia comportamiento observable sin que se pida → a inbox como propuesta. Ruido advisory
(formato, type-args triviales) → descártalo. Ya en vuelo (bitácora/ramas) → sáltalo.

### Anti-falso-positivo (verificación adversarial)
Antes de actuar sobre un hallazgo, **un 2º finder (modelo/lente distinta) intenta REFUTARLO**.
Solo sobrevive lo confirmado por ≥2. (En el run v1 colaron 1-2 falsos positivos por no hacer esto.)
Para hallazgos **high-risk**, no uses N refutadores iguales: usa **lentes DISTINTAS** (correctitud /
seguridad / ¿reproduce de verdad? / ¿lo cubre una capa existente?). La diversidad caza fallos que la
redundancia no — y aquí es donde más cuesta un falso positivo (o un falso negativo).
**Antes de etiquetar "ALTA": busca la MITIGACIÓN que ya exista** (guard previo, `UNIQUE`/constraint,
RLS fail-closed, idempotencia ya implementada, default razonable). Muchísimos "ALTA" del finder ya
están cubiertos por una capa existente → degrádalos. Default = "media, a verificar", no "ALTA". El
finder tiene mucho *recall* y poca *precisión*: confía en la verificación, no en su grito.

## 2. TEST-FIRST — el motor del valor nocturno (lente 5 y siempre que se pueda)
Antes (o en vez) de arreglar, **escribe un test** del caso (sub-agente `loop-tester`):
- Si el test **FALLA** → has encontrado un bug REAL con **repro reproducible**. Adjunta el test al
  hallazgo/fix. (Falla = oro: bug + repro, no prosa.)
- Si **PASA** → ganaste cobertura sobre un camino antes sin testear.
Es aditivo (no cambia comportamiento), auto-verificable (se corre), e imparable de noche. El evaluador
confirma que el test es significativo (no tautológico) y que de verdad ejercita el camino.

## 3. HANDOFF — worktree acumulador persistente (paralelizable)
- Worktree persistente `.claude/worktrees/forja-auto` en rama `loop/forja/auto`; reutilízalo (no
  recheckear por turno). Crear si no existe desde la rama base.
- **Fan-out (coste libre)**: por turno, lanza VARIOS finders en paralelo (uno por flujo/área) y, tras
  el JUDGE+verify, varios fixers/testers en paralelo. Para orquestación determinista usa la
  herramienta **Workflow** (parallel()/pipeline(), `isolation:"worktree"` por agente que MUTA en
  paralelo). El documento: "añade paralelismo el último, tras probar los checks" — ya están probados.
- **Colisión de fixers paralelos — el worktree único NO basta.** Finders y testers paralelizan libres
  (no mutan producción / son aditivos). Pero DOS fixers a la vez sobre el worktree compartido
  `loop/forja/auto` pueden editar el MISMO fichero (típico: arreglan la misma **hermana** del patrón) y
  pisarse. Y una partición fijada de antemano NO basta: las hermanas se descubren EN VUELO (el fixer hace
  su propio grep, §1), así que la asignación previa se queda stale. Protocolo:
  - El orquestador **mapea las hermanas ANTES** de repartir (grep/grafo del patrón) y da a cada fixer un
    **conjunto CERRADO de ficheros**. El fixer **no amplía su scope**: si descubre una hermana fuera de su
    conjunto, la **reporta y no la toca** → el orquestador la asigna a una ronda posterior.
  - **GATE DE BARRIDO POR-CLASE (obligatoria, bloquea el lote).** Antes de cerrar el lote, por CADA
    patrón arreglado el orquestador corre el grep del patrón sobre TODO el repo y demuestra cobertura:
    `nº sitios del patrón == nº sitios saneados + nº en inbox`. Si queda un solo sitio sin tratar, el
    lote NO se cierra. El fix de UNA instancia sin el grep que prueba "estas son TODAS las hermanas" se
    REJECT. Ejemplos de clase (no de instancia): `writerow/to_csv/ws.append` con dato de usuario →
    formula-injection; `detail=str(e)`/`detail=f"...{e}"` → info-leak; `await file.read()` sin cap → DoS;
    `SELECT ... status ==` sin `with_for_update`/UNIQUE → carrera; `LIKE` sin escape. **La afirmación
    "lo arreglé" exige adjuntar la lista exhaustiva de sitios del grep, no el sitio tocado.** (Lección
    real: el saneo CSV-Excel olvidó CSV-fiscal; el no-leak connect/disconnect olvidó add_account.)
  - Si no puedes garantizar conjuntos disjuntos: **serializa los fixers**, o da a cada uno su **worktree
    aislado** (`isolation:"worktree"`). El merge secuencial puede CONFLICTUAR (probable justo en patrones
    repetidos): **conflicto → REJECT ambos, descarta y re-encola en serie**; nunca subas markers `<<<<`.
  - **Estado del loop**: SOLO el orquestador escribe `coverage.md`/`state.md` (✅, %, bitácora) y SOLO
    tras recoger los veredictos del lote — los workers reportan, no escriben el mapa (evita races y ✅
    perdidos por crash antes del PASS).

## 4. GENERATE + VERIFY (generador ≠ evaluador, /goal)
- Generador (`loop-fixer`) implementa el arreglo mínimo / `loop-tester` escribe el test, en el worktree.
- Evaluador (`loop-evaluator`, **otro modelo**, asume roto, EJECUTA las gates detectadas) comprueba la
  condición de parada objetiva. REJECT → vuelve al generador (máx 3 rondas). Tras 3 fallos → revierte
  el commit y manda el item a inbox.
- **Independencia de modelo (no opcional, no silenciosa).** El evaluador debe correr en un modelo
  DISTINTO al del generador que juzga, y el 2º finder (anti-falso-positivo) en uno distinto al 1º cuando
  haya. El orquestador lo FUERZA al lanzar (param `model` del Agent/Workflow); no se confía al default del
  frontmatter (hoy finder y evaluator comparten `sonnet` → mismo modelo = puntos ciegos compartidos). Si
  solo hay 1 modelo: degrada con lente/rol adversarial distinto y **anótalo** en la bitácora
  ("verificación same-model") — no celebres un PASS que no es independiente.
- **Fallo de subagente (crash / timeout / output malformado) — no lo trates como PASS.** Si un worker no
  devuelve un veredicto parseable (sin `VEREDICTO`/`PASS|REJECT|BLOCKER`, JSON roto, vacío, o se cae):
  trátalo como **REJECT no concluyente**, NO como verde. Acciones: (1) `git -C <worktree> reset --hard` +
  `git clean -fd` para descartar cualquier cambio a medio escribir antes del siguiente intento; (2)
  reintenta el item **1 vez**; si vuelve a fallar → el item va a inbox con etiqueta `infra-fail` (no
  `bug-fix`), para no confundir "no se pudo verificar" con "no hay bug"; (3) registra el fallo en la
  bitácora de `state.md`. **Corte de cascada**: si fallan **N≥3 subagentes seguidos** (señal de entorno
  roto, cuota, o worktree corrupto), **detén la pasada** y resume — no sigas acumulando estado roto de
  noche. Un worktree que quedó sucio tras un crash se recupera con reset/clean, nunca se reutiliza a medias.
- Si un cambio altera resultados/semántica observable, el evaluador exige evidencia (un test) que lo
  justifique; ante duda, REJECT → inbox. Vale para cualquier código, no para una zona concreta.
- **Gate de suite COMPLETA — el verde por subconjunto engaña**: si el cambio toca `conftest`/fixtures/
  migraciones/estado de test compartido o **añade una fixture**, corre la **suite entera**, no solo
  `-k <área>`: las fugas entre tests (estado compartido) SOLO aparecen ahí. Además **checkpoint
  periódico**: cada ~5–8 fixes acumulados en la rama, una pasada completa para cazar interacciones
  acumuladas. **Verde por turno ≠ verde de la rama** (lección real: una fixture dejó 11 tests rojos que
  ningún `-k` veía).
- **Honestidad sobre lo no probado**: concurrencia que pide BD real (conftest SQLite), RLS, locks → el
  fix es "**correcto por construcción, sin prueba empírica**", NO "verificado". Dilo así en bitácora/PR.
- **NO SOBRE-AFIRMAR EN COMENTARIOS/DOCSTRINGS (gate del evaluador).** Un guard `SELECT ... then check`
  sin `with_for_update()`/UNIQUE/advisory-lock NO es race-safe — protege el caso SECUENCIAL, no el
  concurrente. El comentario del fix DEBE calibrar exactamente lo que da: prohibido escribir "protege
  multi-instancia / deploy rolling / dos procesos a la vez" sobre un check-then-act. El evaluador REJECT
  si el comentario promete garantía concurrente que el mecanismo no respalda; el fixer reescribe el
  comentario a la verdad ("idempotente en secuencial; la carrera real necesita UNIQUE → inbox") o
  implementa el lock de verdad. (Lección real: el catchup scheduler decía proteger "dos instancias
  vivas" siendo TOCTOU; reconcile no tenía `with_for_update`.) Patrón honesto de referencia: `pos.py`,
  que admite en su docstring que la race simultánea sigue sin resolver y remite a inbox.

## 5. PERSISTENCE + PUERTA HUMANA — PR único acumulado, NUNCA merge
- Push de la rama; UN solo PR que crece (créalo la 1ª vez; luego solo push). NUNCA mergees.
- **Changelog por lote (combate la deuda de comprensión)**: antes de empujar al PR, el orquestador redacta
  en lenguaje humano "qué CAMBIA de comportamiento y qué RIESGO" (≤5 líneas por fix) en la descripción del
  PR. Nadie revisa 18 diffs; sí un resumen que los hace revisables → la puerta humana pasa a ser ejercible.
- **Drenar lo difícil como ARTEFACTO**: los hallazgos arriesgados (no auto-fixeables) → el loop
  redacta el fix en una rama aparte + un **test que demuestra el bug**, para que revises un diff+repro,
  no una nota. El inbox pasa de "deberes" a "PRs que apruebas/rechazas".
- Bitácora viva en `tasks/forja/state.md` (1 línea por turno con resultado). Lo no auto-fixeable →
  `tasks/forja/inbox/` con severidad.
- **Medición de coste (para decidir con datos, no a ojo)**: en esa misma línea de bitácora anota lo
  medible del turno — `lente`, `N finders lanzados`, `flujos barridos`, `fixes/tests aceptados`, y
  `tokens aprox` (in/out, si la herramienta los expone). Tras varias pasadas tendrás el coste real por
  finder y por pasada → ahí sí se decide N y caps con evidencia. **No fijes un techo sobre estimaciones.**

## 6. Detalles de portabilidad / gates en worktree
- **Python/venv**: `git worktree` no clona el venv; invoca las gates con el binario del venv principal
  (`<venv>/bin|Scripts/python -m pytest/ruff/mypy`) apuntando a los ficheros del worktree, o crea/cachea
  un venv para el worktree.
- **Frontend (node_modules)**: el worktree no trae `node_modules`. Antes de verificar frontend, enlaza
  o copia `node_modules` del repo principal al worktree (`ln -s`/`cp -r`), o corre las gates frontend
  desde el repo principal. Sin esto, los fixes de frontend NO son verificables → van a inbox.

## Las 4 deudas silenciosas (vigílalas — Secc. VIII)
verificación → evaluador independiente + /goal · comprensión → tú lees una muestra de los PRs ·
rendición → el loop ejecuta, **tú decides el merge** · token blowout → coste libre aquí, pero la
bitácora MIDE tokens/turno (§5) → pon caps **con datos**, no a ojo, si la cuota importa. Si lleva muchos turnos sin que el evaluador rechace nada, sospecha del
evaluador, no lo celebres.

## Continuación / parada
Continuo con `/loop forja` (cadencia corta = casi continuo). Para SOLO con "para" explícito del
usuario; entonces presenta el resumen consolidado de la bitácora. Si la cuota se agota, detente y resume.
