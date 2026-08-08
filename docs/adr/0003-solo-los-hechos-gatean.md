# 3. Solo los hechos gatean; los proxies informan

**Estado:** aceptada · **Fecha:** 2026-08-08

## Contexto

`gb` calcula muchas señales: complejidad, acoplamiento, olores del grafo, pérdida de aserciones,
firmas cambiadas sin llamantes. La tentación es bloquear el commit con todas ellas — al fin y al
cabo, cada una apunta a algo real.

El problema es que la mayoría son **proxies**: correlacionan con un defecto, no lo demuestran. Un
proxy que bloquea produce falsos positivos, los falsos positivos producen `--no-verify`, y una gate
que se salta por costumbre no protege de nada. Peor: enseña a ignorar también las que sí importan.

## Decisión

**Solo bloquea lo que es un hecho comprobable.** Hoy: un ciclo de imports nuevo y un cruce de
frontera declarado en `.gb-boundaries`. Todo lo demás —`check`, `graph --smells`, la onda del
cambio— **informa y devuelve**, nunca detiene.

Corolario operativo: cuando una señal produce ruido, **se afina o se degrada a informativa**; no se
"tolera".

## Consecuencias

- El gate se puede dejar puesto sin que nadie aprenda a saltárselo.
- Se acepta que pasen cosas malas por el gate. Es deliberado: el coste de un falso negativo es un
  bug; el de un falso positivo sistemático es perder la gate entera.
- Cada señal nueva nace informativa y solo asciende a bloqueante si se demuestra que no fabrica ruido
  sobre historia real.

## Evidencia

- `FIRMA_CAMBIADA_SIN_LLAMANTES` disparaba en **todo** cambio de firma: 3/3 ciertos pero
  inaccionables sobre historia real (parámetros con defecto). Afinada a cambios que **rompen**
  llamadas → **0 falsos positivos en 15 commits** ([docs/pruebas-de-uso.md](../pruebas-de-uso.md)).
- El suelo (`gb floor`) enumera lo que falta y **no bloquea**: gatear cosmética fabrica exactamente
  el `--no-verify` que esta decisión persigue.

## Relacionada

[0002](0002-cero-modelos-en-el-camino-caliente.md) · [0008](0008-el-grafo-declara-su-techo.md)
