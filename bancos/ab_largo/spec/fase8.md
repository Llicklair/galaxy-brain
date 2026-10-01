# almacen — fase 8: el kardex de un sku

Nuevo comando: `movimientos <csv> --sku SKU [--json]`. La historia de un sku en el orden en que
se procesa (el de siempre: por fecha y, a igual fecha, por linea), con el saldo tras cada
movimiento. El saldo es el stock total del sku sumando todos los almacenes.

JSON: una lista de objetos `{"linea": N, "fecha": "...", "tipo": "...", "cantidad": N,
"saldo": N}`, donde `linea` es la del fichero y `cantidad` la de la fila. Un sku sin
movimientos da una lista vacia.
