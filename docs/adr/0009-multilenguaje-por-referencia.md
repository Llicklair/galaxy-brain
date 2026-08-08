# 9. El grafo se abre a JS/TS con un parser externo por referencia

**Estado:** aceptada · **Fecha:** 2026-08-08 · **Matiza a:** [0004](0004-un-lenguaje-un-runtime-un-tipo-de-fallo.md)

## Contexto

`gb` era Python de punta a punta ([0004](0004-un-lenguaje-un-runtime-un-tipo-de-fallo.md)). La prueba
que forzó revisarlo fue montar un proyecto JavaScript mínimo y pasarle la herramienta: el suelo
funcionaba, y **todo lo demás o callaba o mentía** — `gb check` devolvía "Sin señales" sobre un
cambio de comportamiento que no había leído.

Un usuario nuevo con un repo JS recibe hoy el 10 % del valor. Y donde más agentes trabajan es
justamente ahí.

Las tres formas de abrirlo, con lo que cuesta cada una:

| Vía | Coste |
|---|---|
| Vendorizar un parser | Prohibido por [0005](0005-integracion-por-referencia.md) |
| Dependencia Python (tree-sitter) | Rompe "cero dependencias", que es lo que hace la instalación trivial |
| **Binario externo detectado** | Dependencia **opcional** del usuario de JS; gb sigue instalándose solo |

## Decisión

**`ast-grep` por referencia** para JS/TS: detección + verificación ejecutándolo + degradación
declarada si no está. La vía Python **no se toca**: `ast` de la stdlib se queda. Dos motores que
conviven, no uno genérico peor que ambos.

La consola queda **fuera**: `sys.excepthook` no tiene equivalente portable, y un usuario de JS tendrá
grafo, onda y suelo, pero no consola. Declarado en [SCOPE.md](../../SCOPE.md).

## Consecuencias

- gb se sigue instalando sin dependencias; quien use JS instala `ast-grep` aparte.
- El 74 % del código —mapa, CLI, almacén, suelo— no se entera: opera sobre el grafo ya derivado.
- Sin `ast-grep`, la capa JS **se degrada diciéndolo**; nunca se cae ni finge un grafo vacío.
- Un tercer lenguaje repite el proceso, y no antes de que JS esté medido en uso real.

## Criterios de aborto, escritos ahora que no duele

1. **Si `ast-grep` no resuelve llamadas con calidad suficiente para que `gb tests` no sub-seleccione,
   la capa JS se queda en grafo de imports y se dice.** Se mide repitiendo el protocolo de las 42
   roturas deliberadas; el listón es **0 falsos verdes**, el mismo que la vía Python.
2. Si la latencia se sale del presupuesto en un repo real, se reduce el alcance antes que el
   presupuesto ([0003](0003-solo-los-hechos-gatean.md): sobrepasarlo es violación de arquitectura).

## Evidencia

- **Spike medido (8-ago):** `ast-grep 0.45` extrae símbolos, imports y llamadas de JS; **365 ms sobre
  1.500 ficheros** (presupuesto < 1 s). Apenas escala con el tamaño.
- **Acoplamiento medido:** `import ast` aparece en 5 de ~19 módulos; ~3.000 de 11.558 LOC (≈26 %). El
  resto opera sobre el grafo derivado.
- **La trampa de la regla 7, reproducida:** en Windows `ast-grep` es un shim `.CMD` de npm y
  `subprocess` da WinError 2 aunque la terminal funcione. *Instalado ≠ funcional*: la detección
  resuelve el ejecutable y lo verifica ejecutándolo.
- **El fallo que lo motivó:** `gb check --staged` respondiendo "Sin señales" sobre un repo JS
  ([docs/pruebas-de-uso.md](../pruebas-de-uso.md), 8-ago).

## Relacionada

[0004](0004-un-lenguaje-un-runtime-un-tipo-de-fallo.md) · [0005](0005-integracion-por-referencia.md) ·
[0008](0008-el-grafo-declara-su-techo.md)
