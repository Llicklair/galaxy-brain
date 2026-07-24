---
name: setup
description: "Bootstrap de galaxy-brain en el proyecto actual: detecta e instala los companions por REFERENCIA (instalador oficial de cada uno, nunca código replicado) — GitNexus (grafo de código), Spec Kit (pipeline spec-driven, solo si se usará /construye), context-mode (protección de contexto) y los oráculos del stack (Playwright, gh CLI, mutation testing, gates estáticas, schemathesis). Verifica cada instalación y reporta qué quedó activo y qué degradado. Úsalo al aterrizar galaxy-brain en un repo nuevo: /galaxy-brain:setup"
---

# /galaxy-brain:setup — bootstrap de companions por referencia

Prepara el proyecto actual para los loops de galaxy-brain. **Principio innegociable
(ARCHITECTURE.md): los companions se instalan por referencia con su instalador oficial — este
plugin NUNCA replica su código.** Cada companion es opcional: si falta, los loops degradan con
elegancia (menos potencia, nunca un fallo).

## Procedimiento

Para cada companion: **detectar → (si falta) proponer e instalar → verificar**. Pide confirmación
una sola vez con la lista de lo que falta; instala solo lo aceptado.

### 1. GitNexus — grafo de código (recomendado para /forja)

- **Detectar**: `npx gitnexus status` responde con índice fresco, o existe índice previo del repo.
- **Instalar**: `npx gitnexus analyze` (indexa el repo; registra su MCP según indique su propia CLI).
- **Verificar**: `npx gitnexus status` reporta el repo indexado.
- **Sin él**: /forja descubre por árbol de ficheros y grep en vez de flujos de ejecución. Funciona.

### 2. GitHub Spec Kit — pipeline spec-driven (solo si se usará /construye)

- **Detectar**: existe `.specify/` y las skills `/speckit-*`.
- **Instalar**: `uvx --from git+https://github.com/github/spec-kit.git specify init . --integration claude --script sh`
  (requiere `uv`; si falta, indica su instalador oficial: https://docs.astral.sh/uv/).
- **Verificar**: `.specify/` existe y `/speckit-constitution` está disponible.
- **Sin él**: /construye no arranca (lo reporta y para). /forja no lo necesita.

### 3. context-mode — protección de contexto (opcional)

- **Detectar**: sus tools `ctx_*` están disponibles en la sesión.
- **Instalar**: es un plugin de Claude Code — indica al usuario el marketplace correspondiente
  (`/plugin`); no intentes instalarlo por él.
- **Sin él**: los loops funcionan; las sesiones muy largas consumen más contexto.

### 4. Oráculos del stack — las mejores herramientas del mercado, por referencia

Detecta el stack y propone SOLO lo que aplica. Cada uno es opcional: sin él = una gate menos, nunca
un fallo. Evidencia y veredictos completos: `docs/deep-scan-2026-07.md` del repo del plugin.

| Oráculo | Detectar | Instalar (oficial) | Da al loop |
|---|---|---|---|
| **Playwright** (repos web) | `playwright.config.*` o `@playwright/test` en package.json | `npm init playwright@latest` (+ opcional `npx playwright init-agents --loop=claude`) | oráculo E2E durable (`npx playwright test`) + regresión visual local (`toHaveScreenshot`) |
| **gh CLI** | `gh auth status` | https://cli.github.com | veredicto de CI como oráculo (`gh run watch`, `gh run view --log-failed`) |
| **Mutation testing** | `stryker.config.*` · `[tool.mutmut]` · `cargo mutants --version` · pitest en pom/gradle | `npm i -D @stryker-mutator/core` · `pip install mutmut` · `cargo install cargo-mutants` | score de mutación diff-scoped = oráculo de CALIDAD de tests (caza tests "siempre verdes") |
| **Gates estáticas rápidas** | configs de ruff / biome / pyright / semgrep / ast-grep (`sgconfig.yml`) | instalador oficial de cada una, SOLO si el repo ya la configura | gates de segundos antes de la suite |
| **schemathesis** (API con esquema) | `openapi.{yaml,json}` / esquema GraphQL | `pip install schemathesis` | property-tests automáticos DESDE el spec del API — el spec ya ES un oráculo ejecutable |
| **Arch-linters** (ley de capas) | `.importlinter`/`[tool.importlinter]` · `.dependency-cruiser.js` · ArchUnit en tests JVM | instalador oficial de cada uno — al compilar la constitución o si el repo ya los usa | contratos de arquitectura como chequeos de segundos: capas/imports imposibles de violar en silencio |

Reglas de uso (no negociables; las skills de los loops las aplican):
- **Playwright MCP solo dentro del evaluador** (grounding de selectores + ojos de aceptación), nunca
  residente en el loop principal: un run vía MCP ≈114k tokens vs ~27k por CLI. El oráculo durable son
  los specs commiteados; toda sesión MCP termina emitiendo/actualizando un spec commiteado.
- **`--update-snapshots` / `-u` prohibidos para los agentes**: actualizar un baseline es un evento de
  aprobación del evaluador/humano, no un fix (refuerzo mecánico en `hooks/` del plugin).
- **Mutation diff-scoped SOLO al cerrar lote/PR** (minutos), nunca en el bucle interno.
- **mutmut NO corre en Windows nativo** (el paquete instala pero rehúsa ejecutarse): en hosts Windows
  la gate de mutación Python se ejecuta vía WSL o dentro de contenedor — verifica SIEMPRE con una
  ejecución real antes de dar el oráculo por activo; instalado ≠ funcional.
- **CodeQL NO es gate de loop** (builds de 15–45 min); si el repo lo usa, se queda en su CI nocturna.

### 5. Gates del proyecto (siempre, sin instalación)

Detecta y anota los comandos REALES de lint/typecheck/build/test leyendo `.github/workflows/*`,
`package.json` scripts, `pyproject.toml`, `Makefile`, etc. No los inventes ni los hardcodees:
son los oráculos deterministas que usarán los loops (ARCHITECTURE, regla 2). Los oráculos del §4
que estén activos entran en esta cadena de gates (p.ej. `npx playwright test` tras la suite unitaria).

## Reporte final

Tabla con: companion · estado (activo / instalado ahora / omitido / no disponible) · qué pierde el
loop si falta. Cierra indicando el siguiente paso natural: `/forja` (revisar lo que existe) o
`/construye` (edificar desde spec).
