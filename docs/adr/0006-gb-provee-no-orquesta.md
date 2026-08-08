# 6. `gb` provee; no orquesta

**Estado:** aceptada · **Fecha:** 2026-08-08

## Contexto

Sobre el grafo y la actividad derivada se puede montar un orquestador: lanzar agentes en worktrees,
verificar lo que dejan, decidir si se mergea. De hecho el proyecto lo hizo — `bucle/` existe y ha
producido las mediciones más útiles.

La pregunta es dónde vive ese código. Meterlo en `gb` es cómodo (un comando menos que recordar) y es
exactamente cómo una herramienta con un propósito claro se convierte en un framework con varios
difusos.

## Decisión

`gb` **provee hechos**: el grafo, la onda de un cambio, la actividad derivada, el mapa, el estado de
un fallo. Quien decide qué hacer con ellos —lanzar un agente, aceptar un diff, mergear— vive **fuera**:
en `bucle/`, en un hook del usuario, o en la cabeza de quien lee.

Corolario que ya está en las reglas de trabajo: **los bucles autónomos nunca mergean.** Dejan el diff
y el worktree; decide un humano.

## Consecuencias

- Cada familia de comandos de `gb` responde a una pregunta sobre el estado del código. Ninguna
  ejecuta trabajo ajeno.
- `bucle/agente.py` y `bucle/replay.py` **reutilizan** las piezas de `gb` en vez de reimplementarlas:
  dos copias del mismo lanzador divergen y una de las dos acaba mintiendo.
- Si un comando no cae en una familia de [ARCHITECTURE.md](../../ARCHITECTURE.md), no entra. No hay
  excepción "pequeña": las excepciones pequeñas son cómo se fabrica un monstruo.

## Evidencia

- El coste de no tener esto era real y se midió en uso: llegar a ver un agente trabajando exigía
  cinco pasos y un script desechable por tirada («hemos gastado demasiados prompts hasta llegar
  aquí», 8-ago). La cura fue `bucle/agente.py` — **en `bucle/`, no en `gb`**.

## Relacionada

[0005](0005-integracion-por-referencia.md) · [0007](0007-el-abandono-se-investiga.md)
