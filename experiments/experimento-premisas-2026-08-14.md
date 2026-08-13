# Experimento — validación de premisas (mapa persistente, dead, who, multi-lenguaje)

**Fecha:** 2026-08-14 · **Banco:** `C:\Users\Marcos\Desktop\gb-lenguajes\exp-premisas\` (creado ad-hoc) + `gb-lenguajes/js` y `gb-lenguajes/go` (preexistentes, sin tocar) · **Herramienta:** `gb` CLI global.

**Nota sobre numeración:** no encontré en el repo una lista numerada de premisas (busqué "Premisa N" en VISION/SCOPE/docs/experiments). Mapeo usado: **premisa 2 = el mapa persistente produce deltas fieles**, **premisa 5 = `gb dead` da candidatos útiles sin ruido**, **premisa 6 = `gb who` coordina agentes paralelos y detecta cruces**. Si la numeración real es otra, los veredictos se remapean sin cambiar su contenido.

---

## Experimento 1 — mapa persistente (fidelidad del delta)

Mini-proyecto Python: `core.py` (suma/resta/multiplica), `servicio.py` (usa core), `app.py` (usa servicio, con `main`). Git init + commit.

| Paso | Esperado | Observado | ✓/✗ |
|---|---|---|---|
| 1ª ejecución `gb symbols .` | "primera mirada" | `[mapa] primera mirada: 9 simbolos guardados` | ✓ |
| 2ª ejecución sin cambios | "sin cambios" | `[mapa] sin cambios desde tu ultima mirada (2026-08-14T01:10:20)` | ✓ |
| Añadir `divide`, borrar `multiplica`, reejecutar | delta exacto +/− | `+1 simbolo(s), -1, +1 arista(s), -1` · `+ core.divide` · `- core.multiplica` | ✓ |

**Falsos positivos: 0. Omitidos: 0.** El delta nombra exactamente la función añadida y la borrada, con módulo cualificado. Fidelidad perfecta en este caso.

---

## Experimento 2 — `gb dead` (precisión/recall con casos etiquetados)

Proyecto con 6 casos etiquetados de antemano (`logica.py`, `principal.py`, `huerfano.py`, `tests/test_logica.py`).

| Caso etiquetado | Esperado | Observado | Resultado |
|---|---|---|---|
| `funcion_muerta_a` (muerta real) | sale | `logica.py:4 logica.funcion_muerta_a` | **TP** |
| `funcion_muerta_b` (muerta real) | sale | `logica.py:8 logica.funcion_muerta_b` | **TP** |
| `huerfano.py` (módulo huérfano) | sale | `huerfano (huerfano.py)` + `huerfano.cosa_huerfana` | **TP** (módulo + su función) |
| `handler_x` (solo valor en dict `TABLA = {"x": handler_x}`) | NO sale | no aparece | **TN** ✓ |
| `solo_test` (usada solo desde `tests/`) | registrar comportamiento | **no aparece** — el llamante desde el test cuenta como llamante; gb NO distingue producción/test en `dead` | TN (comportamiento: test = llamante válido; no existe hoy la señal "solo lo llama un test") |
| `main` | NO sale | no aparece | **TN** ✓ |
| `Motor.arranca` vía `obj.arranca()` | NO sale (métodos excluidos) | no aparece; la salida declara explícitamente que los métodos no se listan | **TN** ✓ |

**Sorpresa / falso positivo:** salió un candidato NO etiquetado — `principal (principal.py)` como "módulo que nadie importa ni llama". Es el **entry point** del proyecto (tiene `if __name__ == "__main__": main()`). gb excluye la *función* `main` pero marca como huérfano el *módulo* que la contiene. Salida literal:

```
Modulos que nadie importa ni llama:
  huerfano  (huerfano.py)
  principal  (principal.py)
```

La salida sí avisa en general ("entry points externos… invisibles para un grafo estatico"), pero el guard `__main__` está en el AST del propio fichero — es detectable estáticamente y podría usarse para no listar (o al menos anotar) el módulo entry-point. Inconsistencia real: `main` exenta, su módulo no.

**Métricas (por candidato emitido, 5 candidatos):**
- TP = 4 (muerta_a, muerta_b, módulo huerfano, cosa_huerfana) · FP = 1 (`principal`) · FN = 0
- **Precisión = 4/5 = 0.80 · Recall = 4/4 = 1.00**

Punto a favor de la honestidad del diseño: la cabecera dice "candidato(s) — proxies, no veredictos" y enumera sus puntos ciegos.

---

## Experimento 3 — `gb who` y cruces (coordinación)

Sobre el repo del exp. 1 (commit limpio `ac6d427`), worktrees `wt-a` (rama exp-a) y `wt-b` (rama exp-b).

| Paso | Esperado | Observado | ✓/✗ |
|---|---|---|---|
| wt-a edita dentro de `core.suma`; wt-b edita dentro de `servicio.calcula_descuento` (disjuntos) | ambos agentes, símbolo exacto, sin cruces | `wt-a … toca core.suma` · `wt-b … toca servicio.calcula_descuento` · sin sección CRUCES | ✓ |
| wt-b edita también `core.suma` | cruce nombrando la función y los dos agentes | ver abajo | ✓ |

Salida literal del cruce:

```
CRUCES — dos o mas agentes sobre el mismo nodo:
  ! core  <- wt-a, wt-b
  ! core.suma  <- wt-a, wt-b
```

Detalles observados:
- Resolución a nivel de **función**, no solo fichero: la edición dentro del cuerpo de `suma` se atribuye a `core.suma` exactamente.
- El cruce se reporta a dos granularidades (módulo `core` y símbolo `core.suma`) — útil, no ruido.
- El repo principal aparece como agente propio con "commiteo hace poco: app, core, servicio" — informativo, sin falsos cruces.
- Muestra frescura ("hace 5s") y base común (`base ac6d427`).

Limpieza hecha: `git worktree remove --force` ambos + `git branch -D exp-a exp-b`.

---

## Experimento 4 — multi-lenguaje spot-check (`gb dead` sobre JS y Go)

Ambos repos preexistentes, sin modificar.

| Repo | `gb dead .` | ¿No-op silencioso o análisis real? |
|---|---|---|
| `gb-lenguajes/js` | `Sin candidatos a codigo muerto (con los limites de abajo).` | **Análisis real**: `gb symbols` reporta `2 function, 3 module / 2 CALLS, 2 DEFINES, 2 IMPORTS` |
| `gb-lenguajes/go` | `Sin candidatos a codigo muerto (con los limites de abajo).` | **Análisis real**: `3 function, 3 module / 2 CALLS, 3 DEFINES, 1 IMPORTS` |

¿Tiene sentido "sin candidatos"? Sí. Fuentes verificadas a mano:
- JS: `src/carrito.js` exporta `total`, `src/iva.js` exporta `iva`; `test/carrito.test.js` usa carrito → todos con llamante/import.
- Go: `carrito.Total` llama a `iva.Iva()` (`return t * (1 + iva.Iva())`); `carrito_test.go` llama a `Total` → todos vivos.

Salvedades honestas:
- Resolución parcial de llamadas fuera de Python: JS 2/4 candidatas resueltas (50%), Go 2/3 (67%), resto "atributo-de-variable" — declarado en la propia salida, no oculto.
- Igual que en Python, **el llamante de test cuenta**: en ambos repos el símbolo principal (`total`/`Total`) vive en parte gracias al test. Si el test fuera el único llamante, `dead` no lo señalaría (mismo comportamiento que `solo_test` en exp. 2).
- Muestra minúscula (2-3 funciones por repo): esto valida "funciona y no dice tonterías", no precisión multi-lenguaje a escala.

---

## Veredictos por premisa

| Premisa | Veredicto | Evidencia |
|---|---|---|
| **2 — mapa persistente / delta fiel** | **VALIDADA** | Primera mirada / sin cambios / delta `+core.divide -core.multiplica` exactos, 0 falsos, 0 omitidos (exp. 1) |
| **5 — dead code útil** | **VALIDADA con una grieta** | Recall 1.00, precisión 0.80. Los 4 excluyentes (dict-value, main, método, test-caller) se comportan como se declara. **Grieta: el módulo entry-point (`principal.py`, con guard `__main__`) sale como huérfano aunque su función `main` esté exenta** — inconsistencia detectable estáticamente. Multi-lenguaje: funciona en JS y Go con candidatos sensatos (exp. 2 y 4) |
| **6 — coordinación who** | **VALIDADA** | Atribución por símbolo exacto en worktrees disjuntos sin cruces falsos; cruce real detectado y nombrado (`core.suma <- wt-a, wt-b`) a las dos granularidades (exp. 3) |

## Fallos y sorpresas (resumen brutal)

1. **FP real en `dead`:** `principal.py` (entry script con `__main__`) listado como módulo huérfano. Bajará la señal/ruido en cualquier proyecto con scripts de entrada. Arreglo barato: si el módulo tiene guard `__main__`, no listarlo (o anotarlo como "entry-point, no huérfano").
2. **`solo_test` no sale en `dead`:** un llamante desde `tests/` mantiene vivo el símbolo. No es un bug (candidatos, no veredictos), pero se pierde la señal valiosa "solo lo llaman los tests" — sería un candidato de primera para código muerto de producción.
3. **Mojibake en la salida:** los separadores se imprimen como `�` en esta consola (cp1252 vs UTF-8). Cosmético pero constante en todos los comandos.
4. Todo lo demás se comportó **exactamente** como promete, incluida la autodeclaración de límites en cada salida — eso es raro de ver y es mérito del diseño.
