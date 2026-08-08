# 2. Cero modelos en el camino caliente

**Estado:** aceptada · **Fecha:** 2026-08-08 (registra la regla fundacional del proyecto)

## Contexto

`gb` es una herramienta para hacer mejor a un agente de IA. La conclusión intuitiva sería usar un
modelo dentro: para clasificar capturas, para resumir un fallo, para decidir si un cambio es
arriesgado.

Tres razones lo impiden, y ninguna es ideológica:

1. **Determinismo.** Un veredicto que cambia entre dos ejecuciones sobre el mismo árbol no es un
   gate, es una opinión. Y un gate con opiniones acaba en `--no-verify`.
2. **Latencia.** El presupuesto es < 1 s por edición y < 10 s por commit. Una llamada a un modelo no
   cabe, y "optimizarlo luego" no es una salida: sobrepasarlo es violación de arquitectura.
3. **Coste y disponibilidad.** Una herramienta que necesita cuota deja de funcionar sin red y factura
   por mirar.

## Decisión

**Capturar, guardar, mostrar y analizar no consultan a ningún modelo.** La IA entra después del
hecho, a mano y visible: un humano o un agente lee la salida determinista y decide. Cero
dependencias fuera de la librería estándar refuerza lo mismo por otra vía.

## Consecuencias

- Todo lo que `gb` afirma es reproducible por cualquiera con el mismo árbol.
- Se renuncia a cualquier función que exija juicio semántico (agrupar fallos "parecidos", explicar
  una excepción en prosa). Va fuera, en la capa que sí puede llamar a un modelo.
- Los límites se **declaran** en vez de rellenarse con inferencia — ver [0008](0008-el-grafo-declara-su-techo.md).
- Instalación trivial y ejecución offline.

## Evidencia

- ARCHITECTURE regla 8 y hard rule 1 del proyecto.
- La señal preventiva inyectada en contexto se ignoró **12/12** veces medidas; el que corrige es el
  rechazo determinista, 4/4 ([docs/pruebas-de-uso.md](../pruebas-de-uso.md)). Meter un modelo en el
  camino no habría cambiado esa asimetría: la palanca es la arista que obliga, no el texto.

## Relacionada

[0003](0003-solo-los-hechos-gatean.md)
