# Un corpus que no se puede leer revienta con un traceback

## Problema

`guardia.eventos.cargar(ruta)` deja escapar las excepciones crudas del sistema cuando
el fichero de eventos no se puede leer. Por ejemplo,
`guardia responder --incidente no-existe.jsonl` termina con un traceback de pathlib
(`FileNotFoundError`): un fichero mal tecleado se presenta como un fallo del sistema
en vez de como un error de uso. Lo mismo ocurre si la ruta es un directorio o si el
fichero contiene bytes que no son UTF-8 (el corpus puede escribirlo un atacante, asi
que este caso importa). Todos los subcomandos que cargan un corpus estan afectados.

## Comportamiento esperado

- `cargar` devuelve un `Corpus` o lanza un error de dominio nuevo, `CorpusIlegible`;
  nunca un `OSError` ni un `UnicodeDecodeError` crudos. Casos minimos: ruta
  inexistente, ruta que es un directorio, fichero con bytes no UTF-8. El mensaje debe
  nombrar la ruta y la causa.
- Una linea corrupta dentro de un corpus legible NO es un corpus ilegible: se sigue
  saltando y anotando en `saltadas` como hasta ahora.
- La CLI, ante un corpus ilegible en cualquier subcomando, no imprime traceback:
  escribe en stderr un mensaje que empieza por `CORPUS ILEGIBLE` seguido del motivo y
  termina con codigo de salida `2` (el mismo que una propuesta que no encaja en la
  gramatica).

## Interfaz que debe existir

- `guardia.eventos.CorpusIlegible` — clase de excepcion nueva, importable desde
  `guardia.eventos`.
- `guardia.eventos.cargar(ruta)` y `guardia.eventos.Corpus` — existentes; `len(corpus)`
  y `corpus.saltadas` (una tupla, vacia si no se salto nada) — existentes.
- `guardia.cli.main(argv) -> int` — existente. Con
  `["--control", <dir>, "responder", "--incidente", <ruta inexistente>]` debe devolver
  `2`, escribir `CORPUS ILEGIBLE` en stderr y no escribir `Traceback`.

## Fuera de alcance

- Cambiar como se tratan las lineas invalidas (`EventoInvalido`) dentro de un corpus.
- Otros codigos de salida existentes de la CLI.
- Documentacion.
