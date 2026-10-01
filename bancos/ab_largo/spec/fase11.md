# almacen — fase 11: exportar a CSV

`stock` y `valoracion` aceptan `--csv` (no se combina con `--json`):

- `stock --csv`: cabecera `sku,cantidad` y una fila por sku, ordenadas por sku.
- `valoracion --csv`: cabecera `sku,cantidad,valor`, una fila por sku ordenadas por sku, y una
  ultima fila `TOTAL,,<total>`. Los importes con 2 decimales, como en el JSON.
