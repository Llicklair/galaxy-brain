# almacen — fase 10: movimientos en JSON

Algunos clientes exportan los movimientos en JSON. Si el fichero termina en `.json`, se lee
como JSON en vez de CSV, con todos los comandos:

- Una lista de objetos con las claves de las columnas (`fecha`, `sku`, `tipo`, `cantidad`,
  `precio` y, si hacen falta, `almacen`, `destino`, `ref`). Los valores pueden venir como texto o
  como numero. Las claves que falten valen lo mismo que una columna vacia (`almacen` ausente es
  `central`).
- Las reglas de validacion son las mismas. Donde los mensajes dicen `linea N`, con JSON dicen
  `elemento N` (el primer objeto es el 1); `ref` se refiere tambien al numero de elemento.
- Un fichero que no es JSON valido, o que no es una lista: exit 2, `json invalido`.
