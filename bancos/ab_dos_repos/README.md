# A/B: el mismo proyecto, construido con gb y sin gb

**La pregunta.** Con todo lo demas igual, ¿un agente que construye un proyecto con gb lo
deja mas correcto, con menos deuda de arquitectura o mas barato que sin gb? Hasta hoy solo
hay mediciones por capa (gate 3/3, `converge` 10/10, informar 0/6); el efecto neto nunca se
ha medido, y el README lo admite.

**Criterio de terminado de la preparacion** (escrito antes de empezar, 1-oct-2026):
especificacion + suite oculta + una referencia que la pasa al 100 % + al menos 3 mutantes
que la suite caza + este protocolo. Estado: **cumplido** — 35/35 sobre la referencia, 8/8
mutantes mueren (`python bancos/ab_dos_repos/mutantes.py`), y el gate de
`spec/gb-boundaries` limpio sobre la referencia y en rojo con un cruce sembrado.

## Que hay aqui

| | |
|---|---|
| `spec/SCOPE.md` | lo que recibe el agente al empezar (fase 1). Igual en los dos brazos |
| `spec/fase2.md` | la peticion de cambio a mitad del trabajo: bajas y margen por periodo. Igual en los dos |
| `spec/gb-boundaries` | la "ley" de SCOPE escrita para gb |
| `oculta/aceptacion_oculta.py` | 35 tests de caja negra (`python -m almacen` + JSON). **Ningun agente la ve** |
| `referencia/` | una implementacion correcta: prueba que la suite oculta es pasable |
| `mutantes.py` | 8 errores tipicos sembrados en la referencia; la suite tiene que tumbar los 8 |

## Los dos brazos

Mismo modelo, mismo prompt, mismos ficheros de spec. **Lo unico que cambia es gb.**

| | SIN gb | CON gb |
|---|---|---|
| repo | `git init` + `spec/SCOPE.md` | lo mismo + `gb floor --init` (AGENTS, hooks, .gitattributes) + `.gb-boundaries` |
| pre-commit | ninguno | el de `--init`: gate de fronteras/ciclos + `gb check` |
| consola de crashes | apagada (`GB_DISABLE=1` en el entorno del proceso) | encendida |
| hook de sesion | ninguno | `gb graph --context` |
| instruccion extra | ninguna | ninguna: el agente no sabe que hay un experimento ni que gb existe, salvo por lo que el propio arnes le inyecta |

Cada ejecucion es un proceso aparte, `claude -p ... --output-format json`, con su entorno:
asi el aislamiento no depende de que el agente "se porte bien", y el JSON trae tokens,
coste y duracion. Cada construccion en su carpeta, fuera de este repo.

## El guion de cada construccion

1. **Fase 1.** Prompt: "Construye el proyecto descrito en SCOPE.md. Commitea cuando creas
   que esta terminado." Sin limite de turnos razonable fijado de antemano (p.ej. 80).
2. Foto de la fase 1: commit, suite oculta (solo tests sin marca `fase2`), metricas.
3. **Fase 2.** Prompt: el contenido de `spec/fase2.md`, "implementa este cambio".
4. Foto final: suite oculta entera, metricas.

## Las metricas (decididas antes de correr nada)

| metrica | como se mide | por que |
|---|---|---|
| **correccion** (principal) | % de la suite oculta en verde, fase 1 y final | lo unico que el agente no puede maquillar |
| **regresion** | tests de fase 1 que pasaban y caen tras la fase 2 | la fase 2 toca FIFO: es donde se rompe lo que ya iba |
| **deuda de arquitectura** | cruces y ciclos con `spec/gb-boundaries`, medidos con gb al final en LOS DOS brazos | gb como instrumento, no como tratamiento |
| **trazas** | casos de la suite que acaban en `Traceback` | contrato explicito de SCOPE |
| **coste** | tokens, coste en $ y minutos (del JSON de `claude -p`) | gb puede hacer al agente mas barato o mas caro |
| **ejecuciones de tests** | veces que el agente lanza su suite (de la transcripcion) | ¿la seleccion o el gate cambian como trabaja? |

## Tamaño y lo que puede (y no puede) decir

**4 construcciones por brazo = 8.** Con n = 4 solo se ven efectos GRANDES: una diferencia
de correccion de 1-2 tests entre brazos es ruido, y se dira asi. El resultado se lee por
brazo (media y rango de cada metrica), con las 8 construcciones a la vista, sin un "p".

**Coste estimado:** del orden de 1-2 M de tokens por construccion (dos fases), 8-15 M en
total. Se mide de verdad en la primera construccion y se para a preguntar si se desvia.

**Amenazas conocidas, dichas antes:**
- El brazo CON gb recibe AGENTS.md y hooks: algo de la diferencia puede ser "mas contexto",
  no "gb". Es lo que gb ES en uso real, asi que se acepta y se dice.
- La spec la escribio quien escribio gb. La suite oculta se valido contra una referencia y
  8 mutantes, no contra la intuicion; aun asi, el sesgo de autor existe.
- Un proyecto, un lenguaje (Python), un modelo. No generaliza a otros sin repetirlo.
- Por lo ya medido (informar 0/6), lo esperable es efecto en lo que **bloquea** (gate,
  check) y empate en lo que **informa**. Si sale asi, tambien es un resultado.
