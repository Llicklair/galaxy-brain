# 5. Integración por referencia, nunca vendoring

**Estado:** aceptada · **Fecha:** 2026-08-08

## Contexto

La misión del proyecto es dual: **adoptar las mejores herramientas del mercado** y construir solo lo
que falta. Eso obliga a decidir cómo entra lo externo.

Copiar código ajeno dentro del repo (vendoring) da control inmediato y una deuda que crece sola: la
copia no recibe los arreglos de seguridad del original, diverge en silencio, y con el tiempo nadie
recuerda qué se tocó ni por qué.

## Decisión

Lo externo se integra por **detección + instalador oficial + verificación de que funciona**. Nunca se
copia su código dentro. Y lo que otra herramienta ya hace bien **no se reimplementa**: se delega y se
dice a quién.

Corolario: *instalado ≠ funcional*. Un oráculo se verifica ejecutándolo, no comprobando que el
binario existe.

## Consecuencias

- `gb floor` **delega** la higiene de proceso (branch protection, deps pinneadas, releases firmadas)
  a OpenSSF Scorecard y lo declara en su salida, en vez de fabricar una versión peor.
- Detecta `pytest`, `ruff`, `eslint`, `npm test`, `go test`, `pyrefly`… sin cablear ninguno: todo se
  lee del proyecto en ejecución (hard rule 6).
- Si una herramienta externa no está, se dice; no se sustituye por un apaño interno.

## Evidencia

- **pyrefly, medido antes de adoptarlo (6-ago):** 37/37 falsos positivos sobre código sin tipos, y
  sin configuración devuelve exit 0 mudo. Se detecta como gate de tipos si el proyecto ya lo usa,
  pero no se recomienda a ciegas. Verificar ejecutando cambió la decisión.
- **GitNexus, desinstalado (4-ago):** la alternativa a integrarlo era construir el grafo propio, y se
  midió antes de decidir (93 % de recall del derivado).

## Relacionada

[0004](0004-un-lenguaje-un-runtime-un-tipo-de-fallo.md) · [0006](0006-gb-provee-no-orquesta.md)
