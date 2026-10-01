# almacen — fase 3 (peticion de cambio)

El negocio abre un segundo almacen. Esto revisa "Lo que NO entra" de SCOPE.md: **varios
almacenes entra**. Todo lo que no se toca aqui sigue vigente (fases 1 y 2).

## Formato

Se acepta un segundo formato de fichero, con cabecera exacta
`fecha,sku,tipo,cantidad,precio,almacen,destino`. El formato de 5 columnas **sigue siendo
valido** y equivale a `almacen` = `central` y `destino` vacio en todas las filas.

| campo | regla |
|---|---|
| `almacen` | texto no vacio, sin espacios. Donde ocurre el movimiento |
| `destino` | solo en `traspaso` (obligatorio, sin espacios, distinto de `almacen`); en cualquier otro tipo, vacio |

Las reglas de las otras columnas no cambian. Una fila que rompa estas: exit 2,
`linea N: <motivo>`, sin traza.

## FIFO por almacen

El stock y las capas FIFO son **por sku y almacen**. Una `salida` o `baja` consume las
capas de SU almacen; si no llega, es el error de siempre (exit 3), con el mismo mensaje
(`hay X` es lo que hay en ese almacen).

## Nuevo tipo: `traspaso`

Mueve `cantidad` unidades de `almacen` a `destino`, en la fecha de la fila. **Las unidades
conservan su coste**: salen del origen en orden FIFO y entran en el destino con su coste
original, en ese mismo orden, detras de las capas que el destino ya tuviera. `precio` se
ignora. No genera ingresos, coste ni mermas. Sin stock suficiente en origen: exit 3.

## Comandos

- `stock` y `valoracion` aceptan `--almacen NOMBRE`: solo ese almacen. Sin la opcion,
  suman todos los almacenes por sku. **El formato de salida no cambia.**
- `margen` no cambia.
