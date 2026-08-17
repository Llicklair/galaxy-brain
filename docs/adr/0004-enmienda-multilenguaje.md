# 4. Un lenguaje, un runtime, un tipo de fallo — Enmienda

**Estado:** propuesta (borrador, sin medir) · **Fecha:** 2026-08-16 · **Enmienda a:** [0004](0004-un-lenguaje-un-runtime-un-tipo-de-fallo.md) · **Motivada por:** [0012](0012-consola-multilenguaje.md)

## Naturaleza de la enmienda

Esto **no reemplaza** la ADR 0004 ni la declara errónea. La 0004 estableció tres ejes de contención: lenguaje, runtime y tipo de fallo. Esta enmienda **supercede uno solo de los tres** —el eje lenguaje, y solo para la consola— y deja los otros dos intactos.

Entra en vigor **cuando entre en vigor la [0012](0012-consola-multilenguaje.md)**, que hoy es una propuesta sin medir. Mientras tanto esto documenta qué cambiaría, no qué ha cambiado.

## Lo que cambiaría

| Eje | ADR 0004 (original) | Después de esta enmienda |
|---|---|---|
| **Lenguaje (consola)** | Python. Uno. | 17 lenguajes en tres tiers (hook nativo / hook parcial / fallback stderr). Detalle en [0012](0012-consola-multilenguaje.md). |
| **Lenguaje (grafo)** | Python. Uno. | Ya supercedido por [0009](0009-multilenguaje-por-referencia.md) y [0010](0010-repos-mixtos-los-dos-motores-conviven.md): 17 lenguajes, dos motores. Sin cambio adicional aquí. |

## Lo que NO cambia

| Eje | ADR 0004 (original) | Estado |
|---|---|---|
| **Runtime** | Ejecución local. Uno. | **Sin cambio.** Los hooks corren en el runtime del usuario, no en uno que gb provea. |
| **Tipo de fallo** | Excepciones no capturadas. Uno. | **Sin cambio.** El fallback stderr captura el mismo tipo de fallo (una excepción que mata el proceso); cambia la vía, no lo capturado. |

## Por qué el razonamiento original era correcto

La 0004 decía: *«Cada eje de generalidad multiplica el coste de mantener: soportar dos lenguajes no cuesta el doble, cuesta peor.»* Sigue siendo cierto. Lo que el spike sugiere —**sugiere**, no demuestra— es que el coste real de este eje concreto es menor que el estimado:

1. **El patrón se repite.** 8 de 16 lenguajes tienen un mecanismo equivalente a `sys.excepthook` instalable por variable de entorno: no cambia la arquitectura, solo el fichero del hook y la env-var.
2. **El almacén y la CLI son agnósticos.** `gb last/show/list` operan sobre registros JSON y el campo `language` ya existía. No hay código Python-specific en la capa de presentación.
3. **El fallback cierra la cola.** Los lenguajes sin hook nativo se cubren con un parser de stderr: uno solo, no uno por lenguaje.

Los tres puntos salen de leer el código del spike, no de medirlo. **Que un hook se pueda escribir no es que capture.** La 0004 no se enmienda de verdad hasta que existan los crashes contados que pide el criterio de terminado de la 0012.

La decisión de no generalizar **antes de tener evidencia** fue exactamente correcta, y la que la levante necesita la misma clase de evidencia que la puso.

## Relación con la ADR 0004

La 0004 queda con estado **aceptada; enmienda propuesta en el eje lenguaje**. Su texto original no se modifica: esta enmienda vive junto a ella y la referencia. Quien lea la 0004 verá la decisión original y el enlace aquí; quien lea esta entiende qué cambiaría y qué no.

## Relacionada

[0004](0004-un-lenguaje-un-runtime-un-tipo-de-fallo.md) · [0009](0009-multilenguaje-por-referencia.md) · [0010](0010-repos-mixtos-los-dos-motores-conviven.md) · [0012](0012-consola-multilenguaje.md)
