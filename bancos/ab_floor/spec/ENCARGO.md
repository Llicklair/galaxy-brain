# almacen — encargo

Un CLI que lee los movimientos de un almacen desde un CSV y responde tres preguntas:
cuanto stock hay, cuanto vale (FIFO) y que margen han dejado las ventas.

Paquete Python `almacen`, sin dependencias fuera de la libreria estandar, Python >= 3.10.
Se ejecuta como `python -m almacen <comando> ...`.

## El fichero de movimientos

CSV con cabecera exacta `fecha,sku,tipo,cantidad,precio`:

| campo | regla |
|---|---|
| `fecha` | `YYYY-MM-DD` |
| `sku` | texto no vacio, sin espacios |
| `tipo` | `entrada` (compra a proveedor) o `salida` (venta) |
| `cantidad` | entero > 0 |
| `precio` | decimal >= 0 con punto (`12.5`). En `entrada` es el coste unitario; en `salida`, el precio de venta unitario |

**Las filas pueden venir desordenadas.** Se procesan por fecha; a igual fecha, en el orden
del fichero.

## Comandos

Todos aceptan `--json`. Sin `--json` la salida es texto libre pensado para personas; el
contrato estable es el JSON. Los importes van en JSON como **cadenas con 2 decimales**,
redondeados **ROUND_HALF_UP** solo al final (los calculos intermedios no se redondean).

### `stock <csv> [--fecha YYYY-MM-DD] [--json]`
Unidades por sku tras procesar los movimientos con fecha <= `--fecha` (todos, si no se da).
JSON: `{"SKU": cantidad, ...}`; los sku con 0 unidades **no** aparecen.

### `valoracion <csv> [--json]`
Valor del stock restante con coste FIFO: las salidas consumen primero las unidades que
entraron antes. JSON: `{"skus": {"SKU": {"cantidad": n, "valor": "0.00"}, ...}, "total": "0.00"}`.
Los sku sin unidades no aparecen en `skus`.

### `margen <csv> [--json]`
Por sku: `ingresos` = suma de cantidad x precio de las salidas; `coste` = coste FIFO de las
unidades vendidas; `margen` = ingresos - coste. Solo aparecen los sku con alguna salida.
JSON: `{"skus": {"SKU": {"ingresos": "0.00", "coste": "0.00", "margen": "0.00"}, ...},
"total": {"ingresos": "0.00", "coste": "0.00", "margen": "0.00"}}`.

## Rendimiento

Un fichero de **100.000 movimientos** se procesa en **menos de 5 segundos** en un portatil
normal, con cualquiera de los tres comandos. Un almacen real tiene historias largas.

## Errores (contrato)

| situacion | salida | stderr |
|---|---|---|
| fichero inexistente | exit 2 | `no existe: <ruta>` |
| cabecera distinta | exit 2 | `cabecera invalida` |
| fila mal formada | exit 2 | `linea N: <motivo>` (N = linea del fichero, la cabecera es la 1) |
| una salida pide mas unidades de las que hay | exit 3 | `linea N: stock insuficiente de SKU (hay X, se piden Y)` |

**Nunca una traza de Python** ante una entrada mala: el usuario de este CLI no programa.
Comando desconocido o argumentos mal puestos: exit 2 (lo que haga argparse vale).
