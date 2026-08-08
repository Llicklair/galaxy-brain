# 1. El grafo se deriva del código, nunca se almacena

**Estado:** aceptada · **Fecha:** 2026-08-08 (registra una decisión de 2026-08-04)

## Contexto

El grafo de símbolos y módulos es la columna vertebral: 10 de los 15 comandos de `gb` derivan de él.
La tentación evidente es indexarlo una vez y guardarlo — es lo que hacen las herramientas del
mercado, y es varios órdenes de magnitud más rápido que releer los AST en cada invocación.

El proyecto convivió con una de ellas (GitNexus) y la desinstaló por completo el 4-ago-2026. El
motivo no fue el rendimiento: fue que **un índice almacenado es una segunda fuente de verdad**, y en
cuanto se desincroniza del código miente sin avisar. Una respuesta lenta se nota; una respuesta
puntual y falsa, no.

## Decisión

El grafo se deriva del AST **en cada invocación**. No hay índice, no hay caché en disco, no hay
proceso que lo mantenga. Si el barrido no cabe en el presupuesto de latencia, se reduce el alcance —
nunca se persiste el resultado.

## Consecuencias

- El grafo **no puede estar desincronizado**: es una función pura del árbol de ficheros actual.
- Coste: se paga un barrido completo por comando. Medido en este repo (70 módulos), dentro del
  presupuesto de < 1 s por edición.
- Se renuncia a consultas que exigirían un índice incremental sobre repos muy grandes. Es un límite
  aceptado, no un pendiente.
- Nada que borrar cuando algo va mal: no hay estado corrupto posible.

## Evidencia

- GitNexus desinstalado por completo el 4-ago-2026, con el grafo propio ocupando su sitio
  ([docs/pruebas-de-uso.md](../pruebas-de-uso.md), entrada del 4-ago).
- `gb symbols` contra el índice de GitNexus: 93 % de recall, y **las discrepancias favorecían la
  honestidad** del derivado (entrada del 30-jul).

## Relacionada

[0003](0003-solo-los-hechos-gatean.md) · [0008](0008-el-grafo-declara-su-techo.md)
