# galaxy-brain — Informe de investigación: qué hace a un agente de código LLM máximamente efectivo

> Fuente: workflow `deep-research` (2026-07-14). 5 ángulos, 119 afirmaciones extraídas, 21 verificadas adversarialmente (3 votos) antes de que el límite de sesión cortara la fase de síntesis. Este documento es la síntesis reconstruida a partir del material salvado en `research-salvage.json`. Confianza marcada por afirmación. Casi todas las fuentes son **primarias** (blog de ingeniería de Anthropic, papers peer-reviewed, repos con tracción).

---

## Resumen ejecutivo

La evidencia converge en una tesis incómoda para el diseño de harnesses: **la mayor parte de la capacidad vive en el modelo, no en el andamiaje**. Un scaffold mínimo (~100 líneas, solo bash) alcanza >74% en SWE-bench Verified; Anthropic logró su SOTA (49%) con "solo un prompt, una tool Bash y una tool Edit". Añadir muchas herramientas especializadas (LSP, AST, etc.) tiene rendimientos marginales decrecientes y **quema contexto**, que es un recurso finito con "context rot" medible.

Pero hay una excepción nítida y es exactamente la tesis de galaxy-brain: **la verificación determinista y la separación generador≠evaluador sí mueven la aguja de forma medible y reproducible.** Los LLMs son malos juzgando su propio trabajo (en 54 de 56 experimentos no discriminan mejor de lo que generan), pero excelentes reparando cuando reciben feedback determinista (tests fallidos, análisis estático). El loop "generar → verificar con herramienta real → reparar" es la palanca de mayor impacto respaldada por benchmarks.

Implicación de diseño para v0.1: galaxy-brain no debe ser una caja de herramientas. Debe ser un **loop de verificación con oráculos deterministas primero (lint/typecheck/build/test), evaluador LLM adversarial de modelo distinto después, y aislamiento de contexto vía subagentes**. Todo lo demás es secundario.

---

## Hallazgos por impacto esperado

### 🟥 IMPACTO ALTO — respaldado por benchmarks, va al núcleo de v0.1

**H1. El feedback determinista es la mejor verificación; los LLMs reparan bien con él aunque juzguen mal sin él.** *(confianza: alta)*
- Loop iterativo que realimenta análisis estático (Bandit/Pylint) a GPT-4o: problemas de seguridad de >40% → 13% en 10 iteraciones; legibilidad >80% → 11%; fiabilidad >50% → 11%. *(paper, PythonSecurityEval)*
- Anthropic: "la mejor forma de verificación es el feedback determinista basado en reglas (linting)"; recomienda generar TypeScript y lintearlo sobre generar JS puro por las capas extra de feedback.
- Los LLMs son malos detectando bugs/vulns de su propio código, pero "muestran capacidad sustancial de reparar" con reportes de tests o análisis estático. *(paper Discover AI 2026, peer-reviewed)*
- **Diseño:** gates deterministas (lint, typecheck, build, test) son obligatorios y van **ANTES** de cualquier revisión LLM.

**H2. Generador ≠ evaluador, y la independencia debe maximizarse — misma familia de modelo contamina.** *(confianza: alta)*
- "Preference leakage": un juez sesga hacia su modelo "estudiante" relacionado. Mismo modelo ~23.6% de sesgo, herencia 19.3–22.3%, misma familia ~8.9%. → **usar modelo de familia/proveedor distinto para el evaluador.**
- En 54/56 experimentos los LLMs NO discriminan mejor de lo que generan → un modelo no puede fiarse de auto-revisarse.
- Modelos más fuertes tienen mejor discriminación relativa (mayor DG-Diff) → **asignar el rol de evaluador al modelo más fuerte disponible.**
- Mitigaciones de prompt ("sé imparcial") NO funcionan (17.8→18.3, peor); solo calibración con set held-out y CoT ayudan.

**H3. Los gates de suite completa contra el gaming del propio agente.** *(confianza: alta)*
- Sin acceso a los tests de evaluación, el modelo "frecuentemente cree que tuvo éxito en tareas que fallaron" (arregla al nivel de abstracción equivocado). *(Anthropic, harnesses largos)*
- Sin prompting explícito, Claude marca features como completas tras solo unit tests o curl que no ven fallos end-to-end. Darle testing como usuario real (Puppeteer MCP) lo mejoró drásticamente.
- Lista de features en JSON, todas inicializadas como *failing*, editables solo vía campo `passes` con instrucciones fuertes de no-editar → previene reclamaciones prematuras de completitud.
- **Diseño:** nunca auto-merge; gate = suite COMPLETA sin regresión; test-first de aceptación escrito por agente que no ve la implementación ("spec-blind validation").

**H4. Subagentes como firewall de contexto.** *(confianza: alta)*
- Cada subagente explora con decenas de miles de tokens y devuelve solo ~1.000–2.000 de resumen destilado. Anthropic reporta "mejora sustancial sobre sistemas de agente único".
- Multi-agente (Opus orquestador + Sonnet subagentes) superó a Opus single-agent en **90.2%** en su eval de investigación (queries breadth-first).
- **Pero:** multi-agente consume ~15x tokens, y Anthropic dice explícitamente que "la mayoría de tareas de coding son mal encaje para multi-agente hoy" (poco paralelizables, mala coordinación en tiempo real).
- **Diseño:** usar subagentes para **aislamiento de contexto** (finder/evaluator con ventanas propias), NO para paralelismo de coding. El evaluador como subagente evita que el hilo principal lea stdout/stderr del runner (un plugin real reporta ahorro de ~12K tokens/ciclo así).

### 🟧 IMPACTO MEDIO — mejora real, decisiones de arquitectura

**H5. Memoria persistente: file-based, no vectorial.** *(confianza: alta)*
- La arquitectura que Anthropic eligió para producción es **file-based y client-side**, no vectorial: Claude crea/lee/actualiza/borra archivos en un directorio de memoria. Recuperación "just-in-time" con identificadores ligeros (rutas, queries guardadas), no pre-carga vía embeddings.
- Claude Code en producción: compaction + dos sistemas file-based — `CLAUDE.md` versionado (estándares, arquitectura) + "auto memory" que Claude escribe. Spec Kit hace lo mismo: `.specify/memory/constitution.md` re-leído en cada fase.
- Memory tool + context editing: **+39%** sobre baseline en búsqueda agéntica (context editing solo: +29%). En eval de 100 turnos, context editing redujo tokens **84%** y completó workflows que si no fallaban por agotamiento.
- **Diseño:** memoria = archivos. Patrón coding: context editing limpia lecturas de archivos y tests viejos; la memoria persiste insights de debugging y decisiones arquitectónicas.

**H6. Context engineering: el contexto es finito con rendimientos decrecientes.** *(confianza: alta)*
- "Context rot": la precisión de recuperación cae según crecen los tokens, **antes** del límite duro → pruning proactivo.
- Compaction de Claude Code: resume preservando decisiones arquitectónicas, bugs no resueltos y detalles de implementación, descartando outputs de tools obsoletos. Trigger por defecto 150K; tool-result clearing 100K (mantiene últimas 3 tool uses).
- Los 3 primitivos (compaction, tool-result clearing, memory tool) **componen, no compiten**: clearing es lossless si la tool es re-invocable; compaction es lossy-controlado; memoria es persistente.
- Claude Code capa respuestas de tools a **25.000 tokens** por defecto; recomienda paginación/filtrado/truncado en toda tool.

**H7. Spec-driven: integrarse con Spec Kit, no reinventar.** *(confianza: alta)*
- Spec Kit: pipeline de fases con slash commands (constitution→specify→clarify→plan→tasks→implement), 121k estrellas, MIT, agnóstico de agente (30+), incluye `/speckit.converge` para brownfield.
- Verificación ANTES de código: checklists que validan la spec ("unit tests for English"). `/speckit.implement` es gate determinista (valida prerequisitos, respeta dependencias).
- **Diseño:** galaxy-brain v0.1 es solo la forja. Spec Kit queda para v0.2 (`construye` ya se apoya en él). No reimplementar la mitad delantera.

**H8. LLM-as-judge tiene sesgos medibles que hay que neutralizar por diseño.** *(confianza: alta)*
- **Sesgo de estilo** (favorecer markdown) es el dominante (0.10–0.76), y es **más fuerte en contenido técnico** (código, math) → normalizar formato antes de juzgar.
- **Sesgo posicional:** rankings se invierten al intercambiar orden; GPT-4 se contradice 46.3% al swapear. Mitigación: Balanced Position Calibration (juzgar en ambos órdenes y agregar) > muestrear más en orden fijo.
- **Sesgo de verbosidad** heterogéneo por familia: Gemini/Llama prefieren respuestas largas, Claude concisas, GPT-4o neutral.
- **Auto-preferencia** por familiaridad (perplexity), no autoría → cambiar de modelo no la elimina del todo si el output es low-perplexity.
- Anthropic advierte: LLM-as-judge "generalmente NO es muy robusto" y tiene coste de latencia; úsalo cuando la ganancia justifique el coste.
- Un juez mid-tier bien debias-eado bate a frontier a 15x menos coste (Gemini 2.5 Flash, 71.0% acuerdo humano, ~$0.001/eval).
- **Diseño:** el evaluador LLM es la **segunda** capa (tras deterministas), con CoT largo, normalización de formato y modelo distinto/fuerte. Techo realista: humanos concuerdan solo 71.7% entre sí.

### 🟨 IMPACTO BAJO / ADVERTENCIAS — evita sobre-ingeniería

**H9. El scaffold elaborado aporta poco sobre el modelo base.** *(confianza: alta — anti-folklore)*
- Scaffold mínimo ~100 líneas >74% SWE-bench Verified, arranca más rápido que Claude Code. mini-swe-agent: solo bash, sin tool-calling API, historial lineal sin compaction — baseline de Meta/NVIDIA/IBM.
- Anthropic SOTA (49%) con prompt + Bash + Edit, sin scaffolding hardcoded. Con scaffold fijo, la capacidad del modelo domina: Sonnet nuevo 49% / viejo 33% / Opus 3 22%.
- **PERO** el scaffold SÍ importa en la interfaz: refinamientos de descripciones de tools bastaron para SOTA en SWE-bench Verified (Sonnet 3.5); IDs semánticos > UUIDs reducen alucinaciones; el ACI (agent-computer interface) es variable testable.
- **Lección para galaxy-brain:** no compitas en scaffold ni en nº de tools. Compite en el **loop de verificación**. Mantén las tools mínimas y bien descritas.

**H10. Pipelines deterministas simples pueden batir a agentes autónomos complejos.** *(confianza: alta)*
- Agentless (localización→reparación→validación, sin que el LLM decida acciones) superó a todos los agentes OSS en SWE-bench Lite (~32%) en su momento. Cuestiona que la autonomía agéntica compleja sea necesaria.
- **Lección:** el loop de la forja debe tener fases deterministas claras, no autonomía abierta.

**H11. Enforcement por hooks > instrucciones de prompt para pipelines multi-paso.** *(confianza: media — fuente blog, sin cita externa)*
- Afirmación: instrucciones de prompt (skills/markdown) son poco fiables en pipelines autónomos porque el fallo por-paso compone (10 pasos a 90% → falla >60% de las veces); hooks deterministas que emiten JSON son más fiables.
- **Verificar antes de adoptar**, pero encaja con H3/H9: mover invariantes críticos de prompt a hooks/gates.

---

## Mapa del ecosistema OSS (para diferenciarse, no reinventar)

| Proyecto | Qué hace | Implicación para galaxy-brain |
|---|---|---|
| **Claude Code `/code-review`** | Review integrado, niveles de esfuerzo, modo cloud "ultra" | Debemos diferenciarnos del comando nativo: verificación adversarial + auto-fix con consenso |
| **ng/adversarial-review** | Optimizer+Skeptic, cada hallazgo sobrevive 2ª pasada escéptica con salida de comandos; deterministas antes de LLM; cost gate por tamaño/riesgo de diff (score≤0 solo reporte, 1–4 dos Sonnet, ≥5 cuatro Sonnet+Opus); diversidad cross-vendor (Claude+Codex) | **Ya existe casi exactamente nuestro patrón.** Diferenciarse: portabilidad, test-first, integración Spec Kit. Estudiar su cost-gate y routing. |
| **autonomous-dev** | Generador/evaluador con reviewer skeptical; "spec-blind validation" (agente escribe tests desde criterios sin ver implementación, gate duro STEP 8.5); budget ~25-35K tokens/feature, `/clear` reset | Adoptar "spec-blind validation" como anti-gaming. Confirma nuestra tesis. |
| **Spec Kit** | Pipeline spec-driven, 121k★, agnóstico | Integrar en v0.2 (`construye`), no reimplementar |
| **SWE-agent** | ACI custom (editor guardado, navegación, ejecución tests) | Reutilizar ideas de ACI; tools bien diseñadas > muchas tools |
| **Aider** | Linta cada archivo tras cada edición, auto-fix loop; usa tree-sitter para AST y mostrar error en su función; linter language-agnostic vía nodos ERROR de tree-sitter | Patrón de post-edit gate ya shipped. tree-sitter para feedback formateado. |

**Diferenciador de galaxy-brain:** portabilidad a cualquier repo + test-first + deterministas-antes-de-LLM + modelo distinto para evaluador + integración futura con Spec Kit. El espacio está poblado pero fragmentado; nadie combina todo con opinión clara.

---

## Advertencias sobre la evidencia

- La fase de síntesis del workflow no llegó a ejecutarse (límite de sesión); solo 21/119 afirmaciones pasaron verificación adversarial formal — todas las 21 sobrevivieron con confianza alta, y todas eran de fuentes primarias de Anthropic. El resto están extraídas con `sourceQuality` marcado pero no re-verificadas voto-a-voto.
- Afirmaciones marcadas `(blog)` (H11, autonomous-dev, aider) tienen menor peso; verificar números concretos (ej. "property-based tests +23-37% pass@1", "85% acuerdo humano") antes de citarlos como hechos.
- SWE-bench Lite tiene problemas defectuosos (issues con el parche en la descripción); citar cifras con cuidado.

---

## Componentes propuestos para v0.1 (derivados de los hallazgos)

Ordenados por impacto/evidencia. v0.1 = **solo la forja** (loop de revisión), como se acordó.

1. **Gates deterministas primero** (H1, H10) — lint + typecheck + build + test como capa obligatoria antes de cualquier LLM. Detección automática de las gates reales del proyecto.
2. **Test-first de aceptación "spec-blind"** (H3) — agente escribe el test/repro sin ver la implementación; un test que falla = bug con repro.
3. **Evaluador adversarial de modelo distinto** (H2, H8) — generador ≠ evaluador, familia/proveedor distinta, modelo fuerte para juzgar, CoT largo, normalización de formato, veredicto machine-parseable (contrato tipo `VERDICT: APPROVED|REVISE`).
4. **Subagentes como firewall de contexto** (H4) — finder/evaluator con ventanas aisladas; el hilo principal solo recibe un JSON de resultado, nunca el stdout crudo.
5. **Gate de suite completa, nunca auto-merge** (H3) — entrega en PR o local; cap de iteraciones de fix (ej. 2) para atrapar regresiones.
6. **Memoria file-based** (H5) — insights de debugging y decisiones persisten en archivos; context editing limpia lecturas/tests viejos. Nada vectorial.
7. **Tools mínimas y bien descritas** (H9) — no añadir LSP/AST salvo que paguen su coste de contexto; descripciones de tools cuidadas; IDs semánticos.
8. **Fases deterministas, no autonomía abierta** (H10, H11) — considerar mover invariantes críticos a hooks en vez de solo prompt.

> Nota de coherencia: galaxy-brain YA implementa gran parte de esto (agentes `loop-finder/tester/fixer/evaluator`, generador≠evaluador, gates, nunca auto-merge). El research **valida el diseño existente** y añade tres refinamientos concretos poco obvios: (a) evaluador de **familia de modelo distinta** por preference-leakage, (b) **normalización de formato** antes de juzgar por style-bias, (c) memoria **file-based explícita** con context editing para coding.
