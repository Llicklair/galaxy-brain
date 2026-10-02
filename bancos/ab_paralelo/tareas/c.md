Cambio de regla en `almacen` (lee README.md primero).

Contabilidad pide redondeo bancario: a partir de ahora, todos los importes que escribe la
herramienta se redondean a 2 decimales con medio centimo al PAR (ROUND_HALF_EVEN): 0.005 ->
0.00, 0.015 -> 0.02, 0.025 -> 0.02. Sigue siendo redondear solo al escribir, nunca por el
camino. Actualiza el README.

Deja la suite en verde (`python -m pytest -q`) y que quede probado el caso del medio
centimo. Haz commit al terminar.
