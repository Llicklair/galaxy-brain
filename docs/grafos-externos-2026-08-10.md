# Grafos de terceros, 10-ago-2026 — qué aporta cada uno al hueco medido de gb

Barrido hecho después de que [bancos/oraculo_cobertura.py](../bancos/oraculo_cobertura.py) destapara
**91 falsos verdes de 332 símbolos** con dos causas: la **llamada indirecta**
(`(constructor or build_graph)(...)` no deja arista) y el **despacho implícito** (`Style(...)` ejecuta
`__init__` sin que exista la llamada en el código). La pregunta no era "qué grafos hay" —eso ya está en
[[competencia-tdad-codegraph]]— sino **cuál ataca ESE hueco**.

> **PROBADOS EL MISMO DÍA — los tres caen.** Lo que sigue era la teoría; el veredicto está al final,
> en «Lo que pasó al enchufarlos». Ninguno de los tres llega a producir una sola arista sobre este
> repo. El oráculo que salió de aquí es [bancos/oraculo_aristas.py](../bancos/oraculo_aristas.py), y
> no usa ninguno.

## Lo que ataca el hueco (points-to, no AST plano)

| Herramienta | Qué da | Estado | Veredicto |
|---|---|---|---|
| **Jarvis** ([arXiv 2305.05949](https://arxiv.org/abs/2305.05949), [sitio](https://pythonjarvis.github.io/)) | Grafo de asignación (**points-to** por función) + flow-sensitive + **demand-driven**: le das funciones de entrada y construye al vuelo | Prototipo de investigación | **El único que resuelve la llamada indirecta por diseño.** vs PyCG: **+84% precisión, +20% recall, 67% más rápido**. Demand-driven encaja con gb: el diff YA es el conjunto de entrada |
| **HeaderGen** ([repo](https://github.com/secure-software-engineering/HeaderGen)) | PyCG + flow-sensitivity + **resolución del tipo de retorno de llamadas externas** | Mantenido (Uni Paderborn) | 95,6% precisión / 95,3% recall en micro-benchmark. Orientado a notebooks, pero el motor es general |
| **PyCG** ([repo](https://github.com/vitsalis/PyCG), [ICSE'21](https://arxiv.org/pdf/2103.00587)) | Base de los dos de arriba | **ARCHIVADO**, sin desarrollo | 99,2% precisión pero **69,9% recall** — el recall es justo lo que a gb le falta. No adoptar |

**Regla 7 (no vendoring) + regla 2 (presupuesto):** ninguno entra en el camino caliente. Entran como
**oráculo externo**, igual que `coverage --contexts`.

## Lo que ya es commodity (y por tanto no es dónde invertir)

La categoría "grafo de código por MCP" se llenó en 2026:
[code-graph-mcp](https://github.com/sdsrss/code-graph-mcp) (10 lenguajes, tree-sitter, blast radius),
Codebase-Memory (66 lenguajes, **83% de calidad de respuesta con 10× menos tokens**, 31 repos reales),
CodeGraph ([análisis](https://www.developersdigest.tech/blog/codegraph-local-indexes-ai-coding-agents)).
Reclaman **8×–120% menos tokens** frente a grep.

→ Es exactamente el uso "navegar" de gb (`gb calls`, fichas en Grep). **Está comoditizado.** La ventaja
de gb ahí no es la idea, es *derivado siempre* + *por hooks*. No merece más inversión.

## Lo que sigue libre

La taxonomía de smells de LLM avanzó ([ICSE 2026 NIER, SpecDetect4AI sobre 200 sistemas OSS](https://conf.researchr.org/details/icse-2026/icse-2026-nier/37/),
[taxonomía](https://arxiv.org/html/2605.22976)) — pero **siguen siendo umbrales sobre el estado, no delta
sobre el diff**. Nadie mide "este `except: pass` es NUEVO". El hueco de
[[competencia-tdad-codegraph]] aguanta cinco días después.

## Ideas, por retorno medido

1. **Jarvis/HeaderGen como SEGUNDO ORÁCULO, no como dependencia.** El de cobertura mide recall con
   ejecución real; uno de points-to lo mediría estáticamente y en repos sin suite. Coste: un banco.
   Riesgo de latencia: cero. **Esta es la primera.**
2. **Points-to mínimo propio para dos patrones**, medido contra el oráculo que ya existe: `x = f; x()`
   y `(a or b)()`. No hace falta el análisis completo — hacen falta los dos casos que gb comete en su
   propio núcleo. Criterio de terminado: los 91 falsos verdes bajan, y el banco de JS sigue en 0/7.
3. **Un tercer rechazo.** Lo único medido que mueve al modelo es rechazar (3/3 vs 0/6 avisando). Hoy
   solo rechazan dos cosas: ciclo nuevo y cruce de frontera. Candidato: *tocaste un símbolo opaco y no
   corriste su suite entera* — ya se sabe cuáles son (`usados_como_valor`).
4. **No invertir en navegación.** Ver arriba.

## Lo que pasó al enchufarlos (10-ago, mismo día)

La idea 1 se ejecutó y **murió al contacto**. Vale la pena escribirlo porque el motivo no es opinable:

- **PyCG 0.0.8**: se instala como módulo `PyCG` pero su propio código hace `from pycg import formats`
  → `ModuleNotFoundError` nada más arrancar. Con un shim de `sys.modules` sí importa, y entonces
  revienta en su **propio hook de imports** sobre los 22 módulos de `src/galaxybrain`:
  `ImportManagerError: Can't add edge to a non existing node`. Cero aristas producidas. Archivado
  significa archivado.
- **HeaderGen 2.0.2**: `pip install --dry-run` resuelve **~140 paquetes**, entre ellos **tensorflow,
  keras, jupyter, scikit-learn, xgboost, matplotlib, pytype**. Su caso de uso son notebooks de ML.
  Inaceptable como dependencia de un banco.
- **Jarvis**: sin paquete en PyPI. Sería clonar un prototipo de investigación construido sobre la
  misma maquinaria de PyCG que acaba de reventar.

**El pivote, que además es mejor instrumento:** el objetivo real era un oráculo **no circular** del
recall de aristas. El runtime de Python lo da con `sys.setprofile` — y da el **hecho** («esta llamada
ocurrió») en vez de la estimación de un análisis estático con 69,9% de recall. Cero dependencias, que
es la regla del repo. Coste medido: despreciable sobre la suite.

**Lección de método, que ya tiene precedente en este repo:** *instalado ≠ funcional*, y ahora también
*publicado ≠ instalable*. Los tres candidatos venían con números de paper revisado por pares; ninguno
sobrevivió a `pip install`. El orden correcto es sonda primero, diseño después.

## Descartado con motivo

- **LLM para inferir el grafo** ([arXiv 2410.00603](https://arxiv.org/pdf/2410.00603) mide LLMs en
  análisis de tipos y call graphs): viola la regla 1. No se discute.
- **PyCG directo**: archivado y con el recall justo donde duele.
