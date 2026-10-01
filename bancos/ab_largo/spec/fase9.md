# almacen — fase 9: rotacion

Nuevo comando: `rotacion <csv> [--json]`. Para cada sku con al menos una `salida`:
`vendidas` = unidades de sus salidas menos las de sus devoluciones, y `stock` = su stock final
total. JSON: `{"SKU": {"vendidas": N, "stock": N}, ...}`.
