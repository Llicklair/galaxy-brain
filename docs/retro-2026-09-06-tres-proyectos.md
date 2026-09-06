# Retro · gb en tres proyectos reales (AI Mate, TTS pro, bank-assistant-eval)

Fecha: 2026-09-06. Fuente: `gb status` (uso 7 días), `~/.galaxy-brain/index.jsonl` y `leidas.jsonl`
(26-ago → 6-sep), y el transcript completo de la sesión de bank-assistant-eval (280 comandos de shell,
13 commits). Escrito por el agente que usó gb en la tercera, revisado contra los datos, no contra la
impresión.

## Los tres proyectos

| Proyecto | Commits con hook | Entradas en `docs/evidencia.md` | Fronteras declaradas |
|---|---|---|---|
| ai-mate-prueba/entrega (prueba técnica, 28-ago) | 38 | 13 | DETERMINISTA -/-> MODELO -/-> ORQUESTACION, PRUEBAS |
| TTS pro | 62 | 34 | INFERENCIA -/-> ENTRENAMIENTO, frontend -/-> model/export |
| bank-assistant-eval (prueba técnica, 4 a 6-sep) | 16 | 16 | DETERMINISTA -/-> MODELO -/-> ORQUESTACION, HERRAMIENTAS |

Los tres siguieron la misma receta: `gb floor --init`, criterio de terminado en SCOPE.md antes del
código, `.gb-boundaries`, hook de pre-commit con ruff + pytest + `graph --gate` + `check --staged`.

## Uso real, 7 días (`gb status`)

| Comando | Invocaciones | Quién lo lanza |
|---|---|---|
| `graph --gate` | 132 | hook (cada commit) y el agente a mano (18 veces en una sesión de bank-assistant) |
| `who` | 92 | hook / sesión |
| `check` | 86 | hook |
| `floor` | 21 | agente a mano |
| `graph`, `list`, `last`, `show`, `status` | 7, 5, 4, 4, 3 | agente a mano |

Total 361. Las tres primeras filas son las que bloquean o producen un hecho único. Las cinco últimas,
las que informan, suman 23.

## La consola, medida contra su propia ley

SCOPE.md dice: *lo que bloquea o produce un hecho único funciona siempre; lo que informa, nunca.*
La consola quedó como "queda" con criterio 3/3. Estos son los datos de consumo en tres proyectos:

| Proyecto | Capturas | Leídas (`gb show`/`last`) | Tasa |
|---|---|---|---|
| TTS pro | 47 | 7 | 15 % |
| ai-mate-prueba/entrega | 10 | 1 | 10 % |
| bank-assistant-eval | 10 | 0 | 0 % |
| scratchpad / efímeros (`python -c`, stdin) | 27 | 1 | 4 % |
| Total (`gb status`) | 101 | 14 | 14 %, y 7/48 en código de proyecto |

En bank-assistant-eval, además, el anuncio "estado capturado → gb show …" salió 14 veces sobre 280
comandos. Corrección sobre la primera versión de esta retro: la captura NO viene del shell, viene del
`excepthook` de Python (`.pth`), así que un `grep` sin coincidencias no captura nada. Las 14 eran
excepciones reales de Python; 10 de ellas en scripts por stdin (`python - <<EOF`) del agente, es
decir, efímeros que `gb list` ya oculta y que el termómetro cuenta como exploración. El anuncio era la
única pieza sin ese filtro.

**Lectura.** La consola no está rota; la captura de excepciones en código de proyecto se leyó 7 de 48
veces, y esas 7 (TTS pro: `tts.py`, `piper.py`, `speaker_encoder.py`) son el caso para el que existe:
un proceso largo que muere con estado irreproducible. Lo que sobra es el anuncio en las capturas
efímeras, que es informativo y, según la ley de SCOPE, no cambia nada. Los 27 efímeros ya se ocultan
en `list`; el anuncio no aplicaba el mismo filtro.

## El aviso que se ignoró diez veces

`graph --gate` imprime en cada commit "Sin ninguna regla que los mencione: 4 de 24 módulo(s) —
evaluador, tools, tools.kb_apply, tools.lab_compare". En bank-assistant-eval salió 10 veces. El agente
actuó 0. Los dos módulos nuevos de `tools/` nunca entraron en `HERRAMIENTAS`.

No es una excepción a la ley, es la ley: informar no cambia nada (0/6 el 9-ago; 0/10 aquí). El aviso
tiene dos salidas coherentes con SCOPE: bloquear (`--strict`: módulo sin regla = gate en rojo) o
proponer la acción exacta (`añade "tools.kb_apply" a HERRAMIENTAS en .gb-boundaries`), que convierte
el aviso en un hecho único con coste cero de decisión. Lo que no tiene sentido es repetirlo.

## Lo que sí cambió decisiones (sin medir, contado por el agente)

- **El suelo antes del código.** En bank-assistant, `tests/test_mvp.py` existía antes que el evaluador
  porque SCOPE.md exigía un criterio de terminado ejecutable. Sin el andamiaje se habría escrito
  después y peor.
- **La frontera como hecho.** `checks -/-> juez` se decidió el primer día porque había que escribir
  `.gb-boundaries`. En la presentación se pudo afirmar "se comprueba en cada commit" y enseñarlo.
  Es la clase de frase que un revisor puede verificar; sin gb no existía.
- **`gb who --html`.** El mapa se pidió a mano para mirar el acoplamiento antes de entregar (2 usos).
  Coherente con la enmienda del 14-ago: el mapa se consulta cuando se busca, no cuando se empuja.

## Propuestas, por rendimiento esperado

1. **Aviso accionable o estricto en `graph --gate`.** Texto con la línea exacta a añadir a
   `.gb-boundaries`, y `--strict` para que un módulo sin regla falle. Medida de éxito: en el próximo
   proyecto, veces que sale el aviso antes de que alguien actúe ≤ 1.
2. **El anuncio de captura en el shell aplica el filtro de efímeros y de código de proyecto.** Un
   `grep` sin resultado o un `python -c` no anuncian nada. Medida: tasa de lectura de capturas
   anunciadas ≥ 50 % (hoy 14 %).
3. **Modo breve del hook.** Una línea si todo pasa ("gate ok · 24 módulos · 0 cruces"); salida
   completa solo si algo falla o hay señal. Fan-in y fan-out se quedan en `gb who`/`gb graph`.
4. **UTF-8 en Windows.** Los guiones largos y las tildes del hook salen como "�" en la consola de
   cp1252. Un `reconfigure(encoding="utf-8")` en la salida del CLI.
5. **`gb floor` cierra la sesión con su propio dato.** Ya tiene todo lo de esta retro (invocaciones,
   capturas leídas, avisos repetidos). Enseñarlo al final de una sesión es más barato que sacarlo del
   transcript, y es la medida que decide si 1 y 2 funcionaron.

## Lo que no propongo

Quitar la consola. Los 7 de 48 en código de proyecto son el estado irreproducible que solo existe
ahí, y en TTS pro (procesos de exportación largos) fue donde se leyó. El problema es el anuncio,
no la captura.

## Hecho el mismo día (commit en este repo)

| Propuesta | Cambio | Test |
|---|---|---|
| 1 · aviso accionable | `render_sin_regla`: el aviso lleva la línea a pegar (`GRUPO = ..., mod`) y apunta a `--proponer-fronteras`. Sin `--strict`: bloquear ahí sería gatear una declaración incompleta, no un hecho del código (regla 9). | `test_los_modulos_sin_regla_traen_la_linea_a_pegar` |
| 2 · anuncio sin efímeros | `hooks._capture`: se guarda igual, no se anuncia si `where` es `<stdin>`/`<string>`. | `test_una_captura_efimera_se_guarda_pero_no_avisa`; los dos tests del aviso pasan a fichero real |
| 3 · hook breve | `gb graph --brief`: una línea si el gate está limpio, más el bloque de sin-regla; informe entero si hay algo que decir. La plantilla de `floor` lo usa. | `test_brief_es_una_linea_cuando_el_gate_esta_limpio`, `test_brief_no_resume_un_fallo` |
| 4 · UTF-8 en Windows | La plantilla del pre-commit exporta `PYTHONUTF8=1`. El "�" era el hook escribiendo cp1252 por la tubería del commit; en consola directa salía bien. | `test_primer_dia` sigue fijando la línea del gate |
| 5 · resumen de sesión | No hecho. `gb status` ya da uso, capturas y lecturas; lo que faltaba (avisos repetidos e ignorados) deja de existir con 1. Se remide en el próximo proyecto. | — |

Medida de éxito, en el próximo proyecto con `gb floor --init`: el aviso de módulos sin regla no sale
más de una vez antes de que alguien actúe; la tasa de lectura de anuncios de captura sube del 14 %.
Suite: 988 en verde; gate limpio; ruff limpio.

