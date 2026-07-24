# Bug report

El consejo entero se cae a veces cuando el juez sintetiza. En los logs aparece un traceback que
termina así (recortado):

```
  File "...claude_code_driver.py", line ~395, in judge_synthesis
TypeError: list indices must be integers or slices, not str
```

Otras veces es `'str' object does not support item assignment`. Pasa de forma intermitente, más a
menudo cuando el modelo va justo de presupuesto. Investiga la causa raíz y arréglala: un fallo del
modelo no debería tumbar el proceso entero. La suite (97 tests) debe seguir verde.
