# almacen — fase 2 (peticion de cambio)

Dos cambios. El contrato de la fase 1 sigue vigente en todo lo que no se toca aqui.

## 1. Bajas (merma)

Nuevo `tipo`: `baja`. Unidades que salen del almacen sin venderse (roturas, caducidad).

- Consumen stock en FIFO, igual que una `salida`.
- Su `precio` se ignora (puede venir a 0).
- No generan ingresos. Su coste FIFO va a un campo nuevo, `mermas`.
- Una baja que pide mas de lo que hay es el mismo error que una salida (exit 3, mismo mensaje).

En `margen`, cada sku que tenga alguna salida **o alguna baja** lleva ahora tambien
`"mermas": "0.00"`, y el margen pasa a ser `ingresos - coste - mermas`. El `total` lleva
tambien `mermas`. `stock` y `valoracion` no cambian de formato.

## 2. Margen por periodo

`margen <csv> [--desde YYYY-MM-DD] [--hasta YYYY-MM-DD] [--json]`: solo cuentan las salidas
y bajas con fecha dentro del periodo (ambos extremos incluidos). **El coste FIFO se sigue
calculando con toda la historia**: una venta de marzo consume las capas que dejaron las
ventas de enero aunque enero quede fuera del periodo.
