# Decisiones de arquitectura (ADR)

Una decisión por fichero, en el formato de [MADR](https://adr.github.io/): contexto, decisión,
consecuencias. Aquí va **el porqué**; la ley vigente vive en [ARCHITECTURE.md](../../ARCHITECTURE.md)
y el alcance en [SCOPE.md](../../SCOPE.md).

Estos ocho no inauguran nada: **registran decisiones ya tomadas y ya aplicadas**, que hasta hoy
vivían repartidas entre esos dos documentos, los mensajes de commit y la libreta. El problema no era
que faltara el razonamiento —sobraba— sino que no era **citable**: sin una dirección estable, el
porqué se vuelve folklore y lo deliberado se "arregla".

Regla de este directorio: **una decisión cita un hecho medido**, propio o de la literatura. "Otros
frameworks lo hacen" no es una razón. Cada ADR lleva su sección de evidencia con el enlace a la
[libreta de pruebas de uso](../pruebas-de-uso.md).

| # | Decisión |
|---|---|
| [0001](0001-el-grafo-se-deriva-nunca-se-almacena.md) | El grafo se deriva del código, nunca se almacena |
| [0002](0002-cero-modelos-en-el-camino-caliente.md) | Cero modelos en el camino caliente |
| [0003](0003-solo-los-hechos-gatean.md) | Solo los hechos gatean; los proxies informan |
| [0004](0004-un-lenguaje-un-runtime-un-tipo-de-fallo.md) | Un lenguaje, un runtime, un tipo de fallo |
| [0005](0005-integracion-por-referencia.md) | Integración por referencia, nunca vendoring |
| [0006](0006-gb-provee-no-orquesta.md) | `gb` provee; no orquesta |
| [0007](0007-el-abandono-se-investiga.md) | El abandono se investiga; está prohibido blindarlo |
| [0008](0008-el-grafo-declara-su-techo.md) | El grafo declara su techo en vez de rellenarlo |

Una decisión que se revierte **no se borra**: se marca `Estado: sustituida por NNNN` y se escribe la
nueva. El registro de lo que se probó y no funcionó vale tanto como el de lo que quedó.
