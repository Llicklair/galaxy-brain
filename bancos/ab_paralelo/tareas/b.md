Comando nuevo en `almacen` (lee README.md primero).

    python -m almacen resumen <csv> [--json]

Una fila por sku que tenga stock o ventas, ordenadas por sku, con su stock final (todos los
almacenes), el valor FIFO de ese stock y el margen de toda la historia
(ingresos - coste - mermas). En JSON:

    {"skus": {"A": {"stock": 7, "valor": "14.00", "margen": "29.00"}, ...},
     "total": {"valor": "34.67", "margen": "38.67"}}

En texto, una linea por sku `A stock=7 valor=14.00 margen=29.00` y al final
`total valor=34.67 margen=38.67`. Los importes siguen las reglas del README (redondeo solo al
escribir). Errores del fichero, como en el resto de comandos.

Deja la suite en verde (`python -m pytest -q`) con tests del comando nuevo. Haz commit al
terminar.
