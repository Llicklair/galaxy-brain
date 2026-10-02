Refactor en `almacen` (lee README.md primero).

`fifo.procesar` devuelve hoy una tupla `(colas, ventas)`, y quien la usa tiene que acordarse
del orden: ya ha habido un bug por desempaquetarla al reves. Cambiala para que devuelva un
objeto `Resultado` (definido en `fifo.py`) con dos atributos con nombre, `colas` y `ventas`.
Que deje de ser una tupla: nada de `namedtuple`, que se seguiria desempaquetando en silencio
y el bug podria volver. Actualiza a todos los que la llaman.

El comportamiento de la CLI no cambia. Deja la suite en verde (`python -m pytest -q`) y
añade lo que haga falta para que el cambio quede probado. Haz commit al terminar.
