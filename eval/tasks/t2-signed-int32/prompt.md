# Bug report

En Windows, cuando un proceso hijo muere con returncode `2147483648` (0x80000000), el mensaje de
diagnóstico de `DriverProcessError` muestra `signed=2147483648`. Debería mostrar el valor int32
con signo correcto: `signed=-2147483648` (es el borde exacto del rango). Arréglalo y deja un test
que fije el borde. La suite debe seguir verde.
