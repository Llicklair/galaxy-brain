# almacen — fase 14: resumen

Nuevo comando: `resumen <csv> [--json]`, el cuadro de mando en una linea. JSON:
`{"skus": N, "unidades": N, "valor": "0.00", "ingresos": "0.00", "margen": "0.00"}`, donde
`skus` son los sku con stock, `unidades` el stock total, `valor` el total de `valoracion`, e
`ingresos` y `margen` los del total de `margen` (toda la historia).
