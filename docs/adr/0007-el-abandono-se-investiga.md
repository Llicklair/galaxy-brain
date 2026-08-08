# 7. El abandono se investiga; está prohibido blindarlo

**Estado:** aceptada · **Fecha:** 2026-08-08

## Contexto

Toda herramienta interna tiene la misma tentación cuando deja de usarse: **forzar su uso**. Un hook
que la invoca sola, un paso obligatorio en el pre-commit, un recordatorio. Eso convierte la métrica
de adopción en una constante y destruye el único dato honesto que existe.

Este proyecto ya midió lo incómodo: de 55 capturas, 13 leídas. Ese 13/55 fue más informativo que
cualquier test.

## Decisión

**Si dejas de usar la herramienta, está prohibido añadir nada que lo impida.** El abandono se
investiga —por qué no se usó, qué fricción hubo, qué faltaba— y se corrige la causa. Nunca el
síntoma.

## Consecuencias

- La adopción sigue siendo un dato medible y no una consecuencia del andamiaje.
- Cada fricción reportada en uso real se trata como un bug de primera clase, no como falta de
  disciplina del usuario.
- Se acepta el riesgo de que la herramienta simplemente no se use. Es el resultado que hay que poder
  ver.

## Consecuencia práctica: cómo se investiga

El embudo (`gb list`) separa capturadas · leídas · intervenidas · sin reaparecer. Cada tramo que se
estrecha nombra una causa distinta, y esa es la que se ataca.

## Evidencia

- La investigación del 13/55 (6-ago) encontró causas concretas y accionables, no falta de voluntad
  ([docs/pruebas-de-uso.md](../pruebas-de-uso.md)).
- Las tres fricciones del 8-ago —el parpadeo del watch, la leyenda mutable, los cinco pasos para ver
  a un agente— salieron de mirar a alguien usarlo, y las tres se arreglaron en el código.
- El eval `eval/` se **retiró** (708 líneas) al demostrarse que medía la tesis equivocada. Retirar
  también es una forma de no blindar.

## Relacionada

[0006](0006-gb-provee-no-orquesta.md)
