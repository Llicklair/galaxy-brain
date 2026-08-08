# 4. Un lenguaje, un runtime, un tipo de fallo

**Estado:** aceptada · **Fecha:** 2026-08-08

## Contexto

Cada eje de generalidad multiplica el coste de mantener: soportar dos lenguajes no cuesta el doble,
cuesta peor, porque cada parte roza con todas las demás. Y la generalidad se pide siempre antes de
tener un solo usuario satisfecho del caso concreto.

Los tres ejes tentadores son el lenguaje (¿y TypeScript?), el runtime (¿y remoto, y contenedores?) y
el tipo de fallo capturado (¿y los errores de negocio, y los logs?).

## Decisión

**Python · local · excepciones no capturadas.** Uno de cada. Añadir un segundo de cualquiera de los
tres se discute en [SCOPE.md](../../SCOPE.md) **antes** de tocar código, nunca como consecuencia de
una implementación que ya está a medias.

## Consecuencias

- El grafo es un analizador de Python y lo dice: sobre un repo Node, `gb floor` detecta `npm test` y
  eslint, y **declara** que `gb graph` hoy solo lee Python en vez de callar.
- La consola no ve fallos que `pytest` atrapa (nunca llegan a `sys.excepthook`). Documentado, no
  disimulado.
- Se renuncia a un mercado más grande a cambio de que el caso que se cubre funcione de verdad.

## Evidencia

- `gb floor` sobre un repo Node: cero avisos falsos, y el límite dicho de frente
  ([docs/pruebas-de-uso.md](../pruebas-de-uso.md), 30-jul).
- El límite de pytest está escrito en las reglas de trabajo del propio repo: ante un test rojo se usa
  `pytest -l`, **no** `gb`, porque gb no cubre ese caso.

## Relacionada

[0005](0005-integracion-por-referencia.md)
