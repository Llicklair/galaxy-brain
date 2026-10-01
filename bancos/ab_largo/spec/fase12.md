# almacen — fase 12: margen por almacen

`margen` acepta `--por almacen`: agrupa por el almacen donde ocurre cada movimiento (salidas,
bajas, devoluciones y ajustes) en vez de por sku. JSON: `{"almacenes": {"NOMBRE": {"ingresos",
"coste", "mermas", "margen"}, ...}, "total": {...}}` — los mismos campos y reglas que por sku.
Sin `--por`, o con `--por sku`, todo sigue igual. Se combina con `--desde` y `--hasta`.
