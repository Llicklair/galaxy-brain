# 10. Un tercer rechazo tiene que ganárselo: la barra, escrita antes del candidato

**Estado:** aceptada · **Fecha:** 2026-08-10 · **Matiza a:** [0003](0003-solo-los-hechos-gatean.md)

## Contexto

Rechazar es lo único medido que cambia el comportamiento del modelo. Las dos tandas del 9-ago lo
dejaron claro y en direcciones opuestas:

| señal | efecto medido |
|---|---|
| **Rechazar** (cruce de frontera por llamada) | paró a Rust **3/3**, y en 2 el agente se corrigió al peldaño siguiente |
| **Informar** (`simbolos_preexistentes` al peldaño siguiente) | **0 de 6** — ninguna tirada cambió de comportamiento |

De ahí sale una tentación obvia: si rechazar funciona y informar no, conviértase en rechazo todo lo
que hoy informa. Hoy solo bloquean **dos** hechos —un ciclo de imports nuevo y un cruce de frontera
declarado— y el grafo sabe muchas más cosas.

La tentación es un error, y el propio repo tiene la medición que lo demuestra: si `SKIP_ADDED`
bloqueara, este proyecto habría comido **dos `--no-verify`** en su historia. A partir del segundo, la
gate entera deja de leerse. Un rechazo malo no cuesta un falso positivo: cuesta **todos los rechazos
buenos que vinieran después**.

El 10-ago se revisaron cuatro candidatos y ninguno pasó, así que en vez de repetir el debate cada vez
se escribe la barra.

## Decisión

Un hecho merece **bloquear** solo si cumple las tres:

1. **Es un hecho derivado, no un proxy.** Ya lo exige [0003](0003-solo-los-hechos-gatean.md); aquí se
   mantiene sin excepción.
2. **Su presencia es SIEMPRE un defecto.** No "suele serlo", no "conviene mirarlo". Si existe un caso
   legítimo, informa.
3. **Quien lo recibe puede arreglarlo AHORA**, con la información que el propio mensaje le da. Un
   rechazo que exige investigar antes de saber qué hacer se salta.

Lo que no cumple las tres, **informa y devuelve** — que es la regla 2 de ARCHITECTURE, no un premio
de consolación.

## Los cuatro candidatos de hoy, y por qué ninguno pasa

| candidato | falla en |
|---|---|
| Símbolo **pasado como valor** tocado sin correr su suite | (2) no es un defecto: es un patrón normal —callbacks, inyección, registros— y además dejó de hacer falta cuando la selección aprendió a subir por el cuerpo que lo nombra |
| **`SKIP_ADDED`** (skip/xfail nuevo) | (2) medido: dos casos legítimos en este repo, y bloquear habría fabricado dos `--no-verify` |
| **Símbolo público sin llamantes** tras el cambio | (2) código recién escrito, API pública y puntos de extensión lo producen a diario |
| **Módulo nuevo sin regla de frontera** | (2) y (3): bloquea sobre una **ausencia**, saltaría en cada módulo nuevo, y el autor no sabe qué frontera declarar hasta que el módulo se asienta |

## Consecuencias

- El grafo se queda en **dos rechazos**, y eso es un techo declarado, no un olvido.
- Lo que sabe y no bloquea (smells, señales del delta, la onda) sigue en `check` **informando**.
- El siguiente candidato se juzga contra las tres condiciones, no se debate desde cero.
- Se asume el coste: mientras informar mida 0/6, todo lo que no bloquea vale poco para un agente. Es
  el precio de no romper los dos rechazos que sí funcionan.
- Si alguna vez se mide una señal informativa que **sí** cambie el comportamiento, esta ADR se
  sustituye — el 0/6 es de seis tiradas, no de una ley.

## Evidencia

- **3/3 con rechazo, 0/6 con aviso** ([docs/pruebas-de-uso.md](../pruebas-de-uso.md), 9-ago-2026).
- **`SKIP_ADDED`**: dos casos legítimos en la historia de este repo; bloquear habría dado dos
  `--no-verify` (misma libreta).
- **El caso del pasado-como-valor** dejó de necesitar rechazo al arreglarse la selección: 93 → 0
  falsos verdes con la puerta en la capa correcta (10-ago-2026).

## Relacionada

[0003](0003-solo-los-hechos-gatean.md) · [0006](0006-gb-provee-no-orquesta.md) ·
[0008](0008-el-grafo-declara-su-techo.md)
