# almacen — fase 6: ajustes de inventario (recuento fisico)

Nuevo `tipo`: `ajuste`. Alguien ha contado las unidades de un sku en un almacen, y `cantidad`
es lo que conto. Es el unico tipo en que `cantidad` puede ser 0.

- Si lo contado es MAS que el stock de ese sku en ese almacen, la diferencia entra como una capa
  nueva, al final, con coste unitario `precio`.
- Si es MENOS, la diferencia sale en orden FIFO y su coste va a `mermas` (en `margen`, en el
  periodo de la fecha del ajuste), igual que una `baja`.
- Si es igual, no pasa nada.

Un ajuste nunca da "stock insuficiente".
