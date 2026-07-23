---
name: setup
description: "Bootstrap de galaxy-brain en el proyecto actual: detecta e instala los companions por REFERENCIA (instalador oficial de cada uno, nunca código replicado) — GitNexus (grafo de código), Spec Kit (pipeline spec-driven, solo si se usará /construye) y context-mode (protección de contexto). Verifica cada instalación y reporta qué quedó activo y qué degradado. Úsalo al aterrizar galaxy-brain en un repo nuevo: /galaxy-brain:setup"
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

### 4. Gates del proyecto (siempre, sin instalación)

Detecta y anota los comandos REALES de lint/typecheck/build/test leyendo `.github/workflows/*`,
`package.json` scripts, `pyproject.toml`, `Makefile`, etc. No los inventes ni los hardcodees:
son los oráculos deterministas que usarán los loops (ARCHITECTURE, regla 2).

## Reporte final

Tabla con: companion · estado (activo / instalado ahora / omitido / no disponible) · qué pierde el
loop si falta. Cierra indicando el siguiente paso natural: `/forja` (revisar lo que existe) o
`/construye` (edificar desde spec).
