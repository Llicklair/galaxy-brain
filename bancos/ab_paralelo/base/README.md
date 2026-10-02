# almacen

CLI de inventario con valoracion FIFO. Solo libreria estandar de Python.

    python -m almacen stock      <csv> [--fecha AAAA-MM-DD] [--almacen X] [--json]
    python -m almacen valoracion <csv> [--almacen X] [--json]
    python -m almacen margen     <csv> [--desde F] [--hasta F] [--json]

## El CSV

Cabecera `fecha,sku,tipo,cantidad,precio`, opcionalmente con `,almacen,destino` y `,ref`.
Tipos: `entrada`, `salida` (venta), `baja` (merma), `traspaso` (entre almacenes) y
`devolucion` (de una venta: `ref` es la linea de esa salida). Se procesa por fecha; a igual
fecha, en el orden del fichero.

## Reglas

- FIFO por (sku, almacen): una salida consume primero las unidades mas antiguas.
- Los importes se calculan sin redondear y se redondean SOLO al escribir, a 2 decimales,
  con medio centimo hacia arriba (ROUND_HALF_UP). En JSON van como cadena: `"14.00"`.
- Errores del fichero: exit 2 y `linea N: motivo`. Stock insuficiente: exit 3.

## Estructura

- `lectura.py`: CSV -> movimientos validados y ordenados.
- `fifo.py`: el motor. `procesar(movimientos, hasta=None, periodo=(None, None))` devuelve
  `(colas, ventas)`; `stock(colas)` y `valor(colas)` resumen las colas.
- `informes.py`: resultados -> texto o JSON. No calcula nada.
- `cli.py`: argparse y un comando por funcion en `COMANDOS`.

## Tests

    python -m pytest -q
