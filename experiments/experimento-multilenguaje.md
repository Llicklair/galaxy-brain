# Experimento multi-lenguaje — galaxy-brain (gb)

**Fecha:** 2026-08-13
**Objetivo:** Medir qué capacidades de gb son universales (todos los lenguajes) y cuáles son Python-only, inyectando 4 defectos controlados en 5 lenguajes representativos.

**Repos:** `C:\Users\Marcos\Desktop\gb-lenguajes\{go,rust,js,c,ruby}\`
**Estructura de cada repo:** módulo `iva` (núcleo, no debe depender de capas superiores) + módulo `carrito` (importa a `iva`). Regla de frontera: `iva -/-> carrito`.

---

## Defectos inyectados

| # | Defecto | Herramienta | Qué se inyecta |
|---|---------|-------------|----------------|
| D1 | Dependencia circular | `gb graph <src>` | `iva` importa a `carrito` (que ya importa a `iva`) |
| D2 | Violación de frontera | `gb graph <src> --gate` | Importación/llamada que cruza la regla `iva -/-> carrito` |
| D3 | Silencio de errores | `gb delta --worktree .` | `except:` / `rescue` / `catch` vacío que traga excepciones |
| D4 | Cambio de firma | `gb delta --worktree .` | Función `iva()` cambia tipo de retorno (`float` → `int`/`string`) |

---

## Resultados por lenguaje

### Go

Directorio analizado: raíz del repo (módulos `iva/` y `carrito/`).
`.gb-boundaries`: `iva.iva -/-> carrito.carrito` (nivel de símbolo).

| Defecto | Detectado | Exit | Salida clave |
|---------|-----------|------|--------------|
| D1 — Circular (`iva` importa `carrito`) | **SÍ** | 0 | `CICLOS de imports: iva <-> carrito` |
| D2 — Frontera (`iva` llama símbolo en `carrito`) | **SÍ** | 1 (con `--gate`) | `! iva.iva -> carrito.Total [iva.iva -/-> carrito.carrito]` |
| D3 — Silencio errores (`recover()` vacío) | **NO** | 0 | `0 fichero(s) .py mirados` |
| D4 — Cambio firma (`float64` → `int`) | **NO** | 0 | `0 fichero(s) .py mirados` |

**Notas:**
- D1/D2: gb analiza Go con motor regex; detecta imports y llamadas a símbolos cross-módulo.
- D3/D4: `gb delta` solo parsea `.py` con `ast` de Python. Los ficheros `.go` se ignoran completamente.

---

### Rust

Directorio analizado: raíz del repo (`src/iva.rs`, `src/carrito.rs`, `src/lib.rs`).
`.gb-boundaries`: `iva -/-> carrito`.
**Nota de configuración:** el `.gb-boundaries` está en la raíz; al apuntar `gb graph src`, gb lo busca en `src/` y no lo encuentra. Hay que apuntar el análisis a `.` (raíz) para que las reglas se carguen.

| Defecto | Detectado | Exit | Salida clave |
|---------|-----------|------|--------------|
| D1 — Circular (`use crate::carrito::total` en `iva.rs`) | **PARCIAL** | 0 | 0 ciclos — pero detecta llamada cross-frontera: `! iva.iva -> carrito.total [iva -/-> carrito]` |
| D2 — Frontera (llamada desde `iva` a `carrito::total`) | **SÍ** | 1 (con `--gate`) | `CRUCES de frontera por LLAMADA: ! iva.iva_total -> carrito.total` |
| D3 — Silencio errores (`catch_unwind` vacío) | **NO** | 0 | `0 fichero(s) .py mirados` |
| D4 — Cambio firma (`f64` → `i32`) | **NO** | 0 | `0 fichero(s) .py mirados` |

**Notas:**
- D1 (Rust): La sintaxis `use crate::carrito` no es reconocida como arista de grafo por el motor regex de gb (no genera ciclo en el grafo de imports). Sin embargo, la llamada a la función sí se detecta como cruce de frontera por símbolo. Resultado: "circular" en sentido de dependencia de llamada sí se detecta, pero no como ciclo de imports formal.
- D2: La detección de violaciones de frontera vía llamadas de función es la capacidad más robusta de gb para Rust.
- D3/D4: mismo resultado que Go — motor `delta` es Python-only.

---

### JavaScript

Directorio analizado: `src/` (ficheros `iva.js`, `carrito.js`, `suma.js`).
`.gb-boundaries`: en raíz, no en `src/`. Al apuntar `gb graph src`, las reglas no se cargan.

| Defecto | Detectado | Exit | Salida clave |
|---------|-----------|------|--------------|
| D1 — Circular (`require('./carrito')` en `iva.js`) | **SÍ** | 0 | `CICLOS de imports: carrito <-> iva` |
| D2 — Frontera (mismo defecto + `--gate`) | **SÍ*** | 1 | Ciclo detectado → gate falla. Pero: `0 reglas de frontera cargadas` — no valida la regla explícita |
| D3 — Silencio errores (`catch(e) {}` vacío) | **NO** | 0 | `0 fichero(s) .py mirados` |
| D4 — Cambio firma (retorna `string` en lugar de `number`) | **NO** | 0 | `0 fichero(s) .py mirados` |

**Notas:**
- D2*: El gate falla con exit 1, pero por el ciclo detectado en D1, no por la regla de frontera. Las reglas de `.gb-boundaries` no se aplican porque el fichero está en raíz y el análisis apunta a `src/`. Esto es un problema de configuración: el `.gb-boundaries` debe co-ubicarse con la carpeta analizada, o se debe analizar la raíz.
- `require()` es correctamente parseado por gb como arista de grafo.
- D3/D4: Python-only, sin detección.

---

### C

Directorio analizado: `src/` (ficheros `iva.c`, `iva.h`, `carrito.c`).
`.gb-boundaries`: en raíz, no en `src/`. Misma situación que JS.

| Defecto | Detectado | Exit | Salida clave |
|---------|-----------|------|--------------|
| D1 — Circular (`#include "carrito.h"` en `iva.c`) | **SÍ** | 0 | `CICLOS de imports: carrito <-> iva` |
| D2 — Frontera (mismo defecto + `--gate`) | **SÍ*** | 1 | Ciclo → gate falla. Pero: `0 reglas de frontera cargadas` |
| D3 — Silencio errores (ignorar retorno de `fopen`) | **NO** | 0 | `0 fichero(s) .py mirados` |
| D4 — Cambio firma (`double iva()` → `int iva()`) | **NO** | 0 | `0 fichero(s) .py mirados` |

**Notas:**
- `#include "header.h"` es correctamente parseado por gb como arista de grafo — el motor regex de C funciona bien.
- D2*: Misma advertencia que JS. La regla explícita no se aplica; el exit 1 viene del ciclo.
- D3/D4: Python-only. En C no hay mecanismo de excepciones análogo, y los cambios de tipo no son detectados.

---

### Ruby

Directorio analizado: `lib/` (ficheros `iva.rb`, `carrito.rb`).
`.gb-boundaries`: en raíz, no en `lib/`. Misma situación.

| Defecto | Detectado | Exit | Salida clave |
|---------|-----------|------|--------------|
| D1 — Circular (`require_relative 'carrito'` en `iva.rb`) | **SÍ** | 0 | `CICLOS de imports: carrito <-> iva` |
| D2 — Frontera (mismo defecto + `--gate`) | **SÍ*** | 1 | Ciclo → gate falla. Pero: `0 reglas de frontera cargadas` |
| D3 — Silencio errores (`rescue` vacío) | **NO** | 0 | `0 fichero(s) .py mirados` |
| D4 — Cambio firma (retorna `string` en lugar de `float`) | **NO** | 0 | `0 fichero(s) .py mirados` |

**Notas:**
- `require_relative` es correctamente parseado por gb.
- D2*: Misma advertencia que JS/C.
- D3/D4: Python-only, sin detección.

---

## Tabla resumen — 5 lenguajes × 4 defectos

| Lenguaje | D1 Circular | D2 Frontera | D3 Silencio | D4 Firma |
|----------|-------------|-------------|-------------|----------|
| Go       | DETECTADO   | DETECTADO   | NO          | NO       |
| Rust     | PARCIAL*    | DETECTADO   | NO          | NO       |
| JS       | DETECTADO   | DETECTADO** | NO          | NO       |
| C        | DETECTADO   | DETECTADO** | NO          | NO       |
| Ruby     | DETECTADO   | DETECTADO** | NO          | NO       |

\* Rust D1: el ciclo de imports no aparece en el grafo (sintaxis `crate::` no reconocida como import), pero la dependencia de llamada sí se detecta como cruce de frontera.
\** JS/C/Ruby D2: gate sale con exit 1 (útil para CI), pero la causa es el ciclo detectado, no la regla de frontera explícita — porque `.gb-boundaries` está en raíz y el análisis apunta a `src/`/`lib/`. La regla explícita requiere co-ubicar el `.gb-boundaries` con la carpeta analizada.

---

## Hallazgos clave

### 1. `gb graph` es universal — con matices por sintaxis

El motor de análisis de grafos de gb funciona correctamente en todos los lenguajes probados. Detecta dependencias circulares y (cuando las reglas están bien configuradas) violaciones de frontera en Go, Rust, JS, C y Ruby. Las primitivas que reconoce:

| Lenguaje | Sintaxis de import detectada |
|----------|------------------------------|
| Go | `import "paquete"` |
| Rust | `use crate::modulo` (llamadas; el import formal no genera arista, pero las llamadas sí) |
| JS | `require('./modulo')` / `import from` |
| C | `#include "fichero.h"` |
| Ruby | `require_relative 'fichero'` |

### 2. `gb delta` es exclusivamente Python

Los detectores de `gb delta` (`silencios`, `tipos_cambiados`, `guardas_eliminadas`) están implementados sobre el módulo `ast` de Python. Para cualquier fichero no-Python, el motor reporta `0 fichero(s) .py mirados` y sale con exit 0 — no hay error, simplemente no analiza nada. Esto es por diseño actual, no un bug silencioso.

**Capacidades por herramienta:**

| Capacidad | Herramienta | Alcance |
|-----------|-------------|---------|
| Detección de ciclos de imports | `gb graph` | Universal (regex-based) |
| Verificación de fronteras arquitectónicas | `gb graph --gate` | Universal (regex-based) |
| Detección de error swallowing | `gb delta` | **Solo Python** |
| Detección de cambios de firma | `gb delta` | **Solo Python** |
| Detección de guardas eliminadas | `gb delta` | **Solo Python** |

### 3. Problema de configuración: co-ubicación de `.gb-boundaries`

> **CORRECCIÓN (13-ago, verificada a mano):** gb YA se defiende de este caso. Reproducido en
> `gb-lenguajes/js` sin defecto inyectado: `gb graph src --gate` sale con **exit 1** y denuncia
> *"SIN FRONTERAS COMPROBADAS: 0 reglas cargadas... pero SÍ existe `js\.gb-boundaries` — ese
> fichero no se está aplicando"*. No hay falso verde: el gate falla y nombra el fichero sin aplicar
> (`_boundaries_elsewhere` en graph.py). La atribución del exit 1 "solo al ciclo" en las tablas de
> JS/C/Ruby era un registro incompleto del agente. Lo que sigue siendo cierto: las reglas no se
> APLICAN hasta co-ubicar el fichero o apuntar el análisis a su carpeta — pero gb lo dice a gritos.

En Go, el repo tiene módulos `iva/` y `carrito/` directamente en la raíz, y el `.gb-boundaries` también está en la raíz — coincide con el punto de análisis. Resultado: las reglas se cargan y se aplican correctamente.

En Rust, JS, C y Ruby, los módulos están bajo un subdirectorio (`src/`, `lib/`), pero el `.gb-boundaries` está en la raíz del repo. Al apuntar el análisis al subdirectorio, gb busca `.gb-boundaries` ahí y no lo encuentra. Soluciones:
- Mover `.gb-boundaries` al subdirectorio analizado, o
- Apuntar el análisis a la raíz (`.`) en lugar del subdirectorio — funciona cuando los módulos se pueden resolver desde ahí.

En Rust, apuntar a `.` sí carga las reglas y permite la detección completa de violaciones de frontera.

---

## Implicación estratégica

**Para hacer `gb delta` universal, hay que añadir soporte de AST por lenguaje.**

El enfoque actual es correcto en Python porque `ast` da acceso al árbol sintáctico real. Para extender a otros lenguajes la arquitectura necesitaría:

| Lenguaje | AST disponible |
|----------|---------------|
| Python | `ast` (stdlib) — ya implementado |
| JS/TS | `@babel/parser`, `acorn`, `tree-sitter-javascript` |
| Rust | `syn` (crate), `tree-sitter-rust` |
| Go | `go/ast` (stdlib de Go) |
| Ruby | `parser` gem, `tree-sitter-ruby` |
| C/C++ | `tree-sitter-c`, `libclang` |

La alternativa más portable es **tree-sitter** (bindings Python disponibles para todos los lenguajes anteriores), que permitiría un motor unificado sin dependencias por lenguaje.

El análisis de grafo (`gb graph`) ya es universal porque opera con regex sobre el texto fuente — más frágil ante sintaxis inusual, pero no requiere un parser completo del lenguaje.

**Resumen ejecutivo:** gb ya entrega valor en cualquier lenguaje para arquitectura (dependencias, fronteras). Para detección de patrones de código (silencios, firmas, guardas), la inversión necesaria es añadir soporte de AST por lenguaje — tree-sitter como backend unificado sería la ruta más eficiente.

---

## Metodología

Cada defecto fue inyectado editando el fichero fuente (sin commitar), ejecutando el comando de gb correspondiente, registrando salida y exit code, y revirtiendo con `git checkout -- .` antes del siguiente defecto. Los repos tienen un único commit inicial limpio, garantizando que el baseline de `git diff` es el estado original.

**Comandos usados:**
- D1: `gb graph <directorio>` (sin gate)
- D2: `gb graph <directorio> --gate`
- D3/D4: `gb delta --worktree .`
