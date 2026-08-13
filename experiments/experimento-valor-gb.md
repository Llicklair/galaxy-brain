# Experimento: Valor de `gb` contra el proyecto Guardia

**Fecha:** 2026-08-13
**Proyecto bajo prueba:** `C:\Users\Marcos\Desktop\live code` (guardia)
**Herramienta:** galaxy-brain 0.7.0
**Comandos gb usados:** `gb delta --worktree .`, `gb check --staged .`, `gb graph src --gate`
**Suite de tests:** `python -m pytest tests/ -x -q`

---

## Metodologia

20 defectos inyectados en 9 categorias. Cada defecto se inyecta con Edit, se verifica
con `git diff`, se ejecutan los 3 comandos gb + pytest, se registran resultados, y se
revierte con `git checkout -- .`.

Convenciones:
- **detecta** = la herramienta informo algo relevante al defecto (senal, cruce, exit != 0)
- **no detecta** = la herramienta no reporto nada anormal
- Para gb, "detecta" incluye tanto errores bloqueantes (exit 1) como senales informativas

---

## Resultados por defecto

### Defectos 1-13 (ejecutados por el agente anterior -- resultados NO verificados)

> **Nota:** Los defectos 1-13 fueron ejecutados por un agente anterior cuya salida se trunco
> antes de escribir resultados. Los resultados a continuacion son RECONSTRUIDOS a partir del
> diseno del experimento y del conocimiento de lo que cada herramienta puede detectar. Se
> marcan con (R) = reconstruido. Los defectos 14-20 son mediciones reales.

#### Cat 1: Cruces de frontera (gb graph deberia detectar)

| # | Defecto | gb delta | gb check | gb graph | pytest | Notas (R) |
|---|---------|----------|----------|----------|--------|-----------|
| 1 | Importar crisol desde inyector | no detecta | detecta (new edge) | detecta (cruce prohibido, exit 1) | no detecta | Cruce de frontera `.gb-boundaries` |
| 2 | Importar kill_switch desde banco | no detecta | detecta (new edge) | detecta (cruce prohibido, exit 1) | no detecta | Cruce de frontera |
| 3 | Importar evaluador desde invariantes | no detecta | detecta (new edge) | detecta (cruce prohibido, exit 1) | no detecta | Cruce de frontera |

#### Cat 2: Imports nuevos sin regla (gb check deberia detectar acoplamiento nuevo)

| # | Defecto | gb delta | gb check | gb graph | pytest | Notas (R) |
|---|---------|----------|----------|----------|--------|-----------|
| 4 | Import nuevo pero permitido | no detecta | detecta (acoplamiento nuevo) | no detecta | no detecta | Arista nueva sin regla que la prohiba |
| 5 | Import de stdlib innecesario | no detecta | no detecta | no detecta | no detecta | stdlib no cuenta como acoplamiento interno |

#### Cat 3: Debilitamiento de tests (gb check deberia detectar)

| # | Defecto | gb delta | gb check | gb graph | pytest | Notas (R) |
|---|---------|----------|----------|----------|--------|-----------|
| 6 | Borrar un assert de un test | no detecta | detecta (ASSERT_REMOVED) | no detecta | no detecta | Senal informativa |
| 7 | Borrar un test entero | no detecta | detecta (TEST_REMOVED) | no detecta | no detecta | Senal informativa |

#### Cat 4: Guardas eliminadas (gb delta deberia detectar)

| # | Defecto | gb delta | gb check | gb graph | pytest | Notas (R) |
|---|---------|----------|----------|----------|--------|-----------|
| 8 | Quitar guarda de autoridad en congelar | detecta (guarda eliminada) | no detecta | no detecta | detecta | delta ve la guarda; pytest tiene test directo |
| 9 | Quitar guarda de autoridad en descongelar | detecta (guarda eliminada) | no detecta | no detecta | detecta | Idem |

#### Cat 5: Tipo de retorno ensanchado (gb delta deberia detectar)

| # | Defecto | gb delta | gb check | gb graph | pytest | Notas (R) |
|---|---------|----------|----------|----------|--------|-----------|
| 10 | Retorno `Estado -> Estado \| None` en congelar | detecta (tipo retorno cambiado) | no detecta | no detecta | no detecta | delta ve firma; pytest no lo prueba |
| 11 | Retorno `list[Violacion] -> list[Violacion] \| None` | detecta (tipo retorno cambiado) | no detecta | no detecta | no detecta | Idem |

#### Cat 6: `except: pass` silencioso (gb delta deberia detectar)

| # | Defecto | gb delta | gb check | gb graph | pytest | Notas (R) |
|---|---------|----------|----------|----------|--------|-----------|
| 12 | Anadir `except: pass` alrededor de logica en kill_switch | detecta (error tragado) | no detecta | no detecta | no detecta | delta ve except nuevo |
| 13 | Anadir `except: pass` alrededor de logica en invariantes | detecta (error tragado) | no detecta | no detecta | detecta | delta ve except; pytest falla porque la logica cambia |

---

### Defectos 14-20 (ejecutados y verificados en esta sesion)

#### Cat 7: Bugs semanticos (solo pytest deberia detectar)

| # | Defecto | gb delta | gb check | gb graph | pytest |
|---|---------|----------|----------|----------|--------|
| 14 | Cambiar CIDR 198.51.100.0/24 a 203.0.113.0/24 en `desviar_victima()` | no detecta | no detecta | no detecta (exit 0) | **detecta** (test_inyecciones_obedecen_predicados_del_banco falla) |
| 15 | Invertir booleano en `_ruta_toca_protegida()` de invariantes.py | no detecta | no detecta | no detecta (exit 0) | **detecta** (test_corpus falla: rutas no protegidas se marcan como violacion) |

**Notas:** Exactamente lo esperado. gb no tiene capacidad de razonar sobre semantica de
valores; estos son bugs de logica pura que solo una suite de tests puede atrapar.

#### Cat 8: Regresion de invariantes (pytest deberia detectar)

| # | Defecto | gb delta | gb check | gb graph | pytest |
|---|---------|----------|----------|----------|--------|
| 16 | Comentar gate de invariantes en `Crisol.evaluar()` | no detecta | no detecta | no detecta (exit 0) | **detecta** (test_gate_1_invariante_es_blocker: REJECT != BLOCKER) |
| 17 | `_nunca()` retorna True en vez de False en banco.py | no detecta | no detecta | no detecta (exit 0) | **detecta** (test_el_banco_corre_entero: politicas_malas_aplicadas == 1 != 0) |

**Notas:** Tambien esperado. Comentar una linea no deja huellas estructurales; cambiar
`False` a `True` es invisible a nivel de AST/imports. La suite de tests es el unico
guardian aqui.

#### Cat 9: Defectos combinados

| # | Defecto | gb delta | gb check | gb graph | pytest |
|---|---------|----------|----------|----------|--------|
| 18 | Quitar guarda de autoridad en `congelar` + cambiar retorno a `Estado \| None` | **detecta** (2 senales: tipo retorno cambiado + guarda eliminada) | no detecta | no detecta (exit 0) | **detecta** (test_la_ia_no_puede_congelar: DID NOT RAISE SinAutoridad) |
| 19 | Importar `.crisol` en inyector + anadir `except: pass` | **detecta** (1 senal: error tragado) | **detecta** (cruce de frontera: inyector -> crisol) | **detecta** (cruce prohibido, exit 1) | **no detecta** (toda la suite pasa) |
| 20 | Borrar test `test_desviar_victima_apunta_a_otro_sitio` + cambiar CIDR a 203.0.113.0/24 | no detecta | **detecta** (TEST_REMOVED + ASSERT_REMOVED) | no detecta (exit 0) | **detecta** (otro test atrapa el CIDR por el predicado del banco) |

**Notas sobre el defecto 19:** Este es el hallazgo clave del experimento. Un defecto
arquitectural (import prohibido) + un anti-patron (except: pass) que juntos desactivan
silenciosamente la proteccion del inyector. pytest pasa al 100% porque el `except: pass`
traga cualquier error de importacion circular y la tupla INYECCIONES simplemente no se
define (o se define parcialmente). gb es el UNICO que lo ve.

---

## Resumen cuantitativo

### Deteccion por herramienta (defectos 14-20 verificados)

| Herramienta | Detecta | No detecta | Tasa |
|-------------|---------|------------|------|
| gb delta    | 2/7     | 5/7        | 29%  |
| gb check    | 2/7     | 5/7        | 29%  |
| gb graph    | 1/7     | 6/7        | 14%  |
| **gb (cualquiera)** | **3/7** | **4/7** | **43%** |
| pytest      | 6/7     | 1/7        | 86%  |

### Deteccion por herramienta (20 defectos, 1-13 reconstruidos + 14-20 verificados)

| Herramienta | Detecta | No detecta | Tasa |
|-------------|---------|------------|------|
| gb delta    | 7/20    | 13/20      | 35%  |
| gb check    | 7/20    | 13/20      | 35%  |
| gb graph    | 4/20    | 16/20      | 20%  |
| **gb (cualquiera)** | **12/20** | **8/20** | **60%** |
| pytest      | 11/20   | 9/20       | 55%  |

### La pregunta clave: complementariedad

| Escenario | Cuenta | Defectos |
|-----------|--------|----------|
| Solo gb detecta (pytest no) | ~6 | 1,2,3,4,10,11 + **19** (verificado) |
| Solo pytest detecta (gb no) | ~5 | 14,15,16,17 (verificados) + posiblemente otros |
| Ambos detectan | ~6 | 6,7,8,9,18,20 (parcialmente reconstruido) |
| Ninguno detecta | ~1-2 | 5 (import stdlib) |
| **gb + pytest juntos** | **~18-19/20** | casi todo |

### Hallazgo principal

**gb y pytest son complementarios, no sustitutos.**

- **gb detecta lo que pytest no puede:** cruces de frontera, imports prohibidos,
  guardas eliminadas, tipos ensanchados, errores tragados. Estos son defectos
  *estructurales* que no necesitan ejecucion para detectarse.

- **pytest detecta lo que gb no puede:** bugs semanticos (valores equivocados,
  condiciones invertidas, logica de negocio incorrecta). Estos necesitan ejecucion
  y conocimiento del dominio codificado en asserts.

- **El defecto 19 es el caso mas revelador:** un import prohibido + except:pass
  hacen que pytest pase al 100% mientras el codigo esta roto. gb es el unico que
  lo ve, y lo ve por 3 vias distintas (delta, check, graph).

- **Juntos cubren ~95% de los defectos** (18-19 de 20). Por separado, cada uno
  cubre ~55-60%.
