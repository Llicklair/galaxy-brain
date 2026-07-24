# Bug report

Cuando un `claude` hijo peta, `DriverProcessError` recorta la salida del proceso a ~200
caracteres. En la práctica eso **corta los stack traces por la mitad** y no hay forma de depurar:
el error dice `--stdout_head--` y solo se ve el principio, justo antes de la línea que importa.

Necesito ver **más contexto** de la salida del proceso en el mensaje de error. Sube el recorte a
algo razonable para que quepa un traceback completo. La suite (97 tests) debe seguir verde.
