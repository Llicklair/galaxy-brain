# almacen — fase 4 (peticion de cambio)

Los clientes devuelven producto. Todo lo que no se toca aqui sigue vigente (fases 1 a 3).

## Formato

Se acepta un tercer formato, con cabecera exacta
`fecha,sku,tipo,cantidad,precio,almacen,destino,ref`. Los formatos de 5 y 7 columnas siguen
siendo validos (sin `ref`). `ref` va vacio en todo lo que no sea una `devolucion`.

## Nuevo tipo: `devolucion`

Un cliente devuelve `cantidad` unidades de una venta anterior. `ref` es el **numero de linea
del fichero** de esa `salida` (la cabecera es la linea 1). `precio` se ignora.

Es valida si, y solo si: `ref` es la linea de una `salida` del **mismo sku**, que se procesa
**antes** que la devolucion (fecha anterior o, a igual fecha, una linea anterior), y lo devuelto de esa venta (sumando todas sus
devoluciones) no supera lo que se vendio en ella. Si no: exit 2, `linea N: devolucion
invalida`, sin traza. Es un error de fichero, como una fila mal formada.

**Coste.** Las unidades vuelven al stock del `almacen` de la fila de devolucion con el coste
de las capas que **esa venta** consumio, empezando por la ultima unidad que consumio (orden
inverso). Entran detras de las capas que ese almacen ya tuviera. Dos devoluciones de la
misma venta siguen tirando hacia atras desde donde lo dejo la anterior.

**Margen.** Una devolucion resta a su sku `cantidad x precio de venta de la salida
original` de `ingresos`, y el coste de las unidades devueltas de `coste`. Cuenta en el
periodo de la **fecha de la devolucion**, no en el de la venta.
