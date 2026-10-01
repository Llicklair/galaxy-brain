# almacen — fase 7: alertas de stock minimo

`stock` acepta `--minimo N` (entero >= 0): solo lista los sku cuyo stock es menor o igual que N.
Con `--minimo`, los sku que han tenido algun movimiento y estan a 0 **si** aparecen (con 0): son
justo los que hay que reponer. Se combina con `--fecha` y `--almacen`. El formato no cambia.
