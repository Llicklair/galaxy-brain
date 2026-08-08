# 8. El grafo declara su techo en vez de rellenarlo

**Estado:** aceptada · **Fecha:** 2026-08-08

## Contexto

El análisis estático de Python sin anotaciones tiene un techo duro: las llamadas por atributo
(`obj.metodo()`) exigen inferencia de tipos. Medido, el grafo resuelve el **38 %** de las llamadas
candidatas en este repo y el **40 %** en un repo ajeno. Que el número se repita en código que no es
nuestro dice que es una propiedad de la técnica, no un defecto de la implementación.

Hay dos maneras de que ese número suba, y las dos están descartadas con datos:

- **Inferencia de tipos:** pyrefly da 37/37 falsos positivos sobre código sin anotar (medido 6-ago).
- **Heurística por nombre de método:** subiría el porcentaje **inventando aristas**, que acabarían
  alimentando una gate. Prohibido por [0003](0003-solo-los-hechos-gatean.md).

La tercera opción —presentar el grafo parcial como si fuera completo— es la que toma la mayoría de
herramientas del sector, y es la peor: quien lo lee no puede saber sobre qué está pisando.

## Decisión

El grafo **cuenta y publica lo que no resuelve**, en cada salida, desglosado por causa
(`atributo-de-variable`, `expresion-dinamica`, builtins excluidos). Y **todo consumidor degrada hacia
el silencio**: ante un símbolo que no ve, ninguno concluye "no hay nada" — o cae al comportamiento
seguro, o no acusa.

- `gb tests`: si no ve llamantes, selecciona **la suite entera**.
- `FIRMA_CAMBIADA_SIN_LLAMANTES` y la verificación de adopción: fallan hacia el **falso negativo**,
  nunca hacia la acusación falsa.
- `graph --gate`: usa imports, que sí son un hecho completo — no depende del techo.

## Consecuencias

- Un grafo al 40 % **que declara su 40 %** es utilizable; uno al 60 % que se presenta completo, no.
- Se renuncia a precisión en la selección de tests a cambio de no dar nunca un verde falso.
- Levantar el techo con evidencia de runtime (`coverage --contexts`) queda como **capa aparte y
  offline**, y su disparador es un caso medido donde el techo cueste algo. Hoy no existe.

## Evidencia

- **42/42 sin un solo falso verde** sobre código ajeno: 22 roturas duras y 20 mutaciones semánticas,
  comparando la selección de `gb tests` contra la suite entera. Los 14 símbolos **invisibles** al
  grafo seleccionaron los 20 de 20 ficheros; los bien conectados, 2–9 (en el extremo, 1 test de 235,
  y era el que fallaba) — o sea que discrimina, y aun así nunca seleccionó de menos.
  ([docs/pruebas-de-uso.md](../pruebas-de-uso.md), 8-ago.)

## Relacionada

[0001](0001-el-grafo-se-deriva-nunca-se-almacena.md) · [0003](0003-solo-los-hechos-gatean.md)
