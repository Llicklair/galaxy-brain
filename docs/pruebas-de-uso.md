# Pruebas de uso — la libreta del arnés

Registro de cada prueba de uso real: qué se probó, qué salió y qué cambió por ello.
Existe porque [SCOPE.md](../SCOPE.md) arrastra una deuda concreta — el único dato empírico del
proyecto (el A/B de la báscula) vive en memoria y no en el repo. Un proyecto sobre evidencia no puede
tener la suya fuera, así que aquí se queda, incluida la que va en contra.

Formato: fecha, qué se probó, resultado, consecuencia. Los resultados negativos se escriben con el
mismo detalle que los positivos, o más.

---

## 2026-08-14 · El mapa muerto que se leía como vivo — el dato que el A/B del canvas no miraba

**Lo observado, en uso real:** el recorte del 13-ago se llevó el canvas, pero `mapa.html` quedó en
la raíz como fósil (generado 05:01 del 13-ago) y **siguió siendo la referencia diaria del owner un
día entero** — enseñando "sin actividad" en presente mientras había trabajo en marcha. Tercera
mordida del mismo modo de fallo (aro cocido 10-ago, arreglo 9f3520e dentro del generador… que el
recorte se llevó con el generador). La mentira no está en el dato ni en la fecha del pie: está en
el **tiempo verbal** con que se lee una foto.

**Lo que el A/B midió y lo que no:** el empate (3/3 y 3/3) midió *decisiones de agente* con y sin
canvas — y esa sentencia sigue siendo válida para la maquinaria. Lo que no midió es que el mapa
**se consultaba a diario aunque estuviera congelado**: uso humano sostenido, la señal que la regla
del abandono pide investigar, en la dirección contraria — no abandono, apego.

**Consecuencia (5 commits):** vuelve SOLO el renderer (`viz.py` verbatim de `3229ddd^`, con el
envejecido GEN_TS de 9f3520e dentro) como salida de `gb who --html`; el vivo es `gb who --watch
--html` — un comando en primer plano, sondeo + escritura atómica + meta-refresh, cámara en
sessionStorage; **cero candados, cero relanzamientos**. El destino por defecto es el `mapa.html`
de la raíz si ya existe (la costumbre declarada en disco; escribir donde nadie mira fue la causa
raíz de la foto podrida). La página fina de presencia (`mapa_html.py`) nació y se recortó la misma
noche al confirmarse que el mapa principal es el canvas — sus lecciones quedan en el canvas y en
el default. La sentencia de SCOPE se enmienda, no se borra.

---

## 2026-08-13 · La letra pequeña del verde, medida ANTES de construirla: sobre este repo, humo — y el porqué es el mejor dato del día

La candidata a "gran diferencia": que cada verde diga qué símbolos tocados NO ejecutó ningún test
(grafo + selección + oráculo runtime, todo ya construido). Criterio escrito antes: 20 commits
reales; si ~0 llevaban hueco, la feature es humo y se escribe.

**Resultado: 16 commits medibles, 0 con símbolos de `src` tocados sin pisar, 0 huecos de
selección.** Los 5 "con letra" eran todos de `bancos/` — instrumentos que se corren a mano y no
llevan tests a propósito: señalarlos cada commit sería el falso positivo recurrente que mata
familias (regla 9). Humo, dicho sin anestesia.

**La lectura que importa más que el número:** este repo es el peor sitio del mundo para medir esa
feature — 764 tests para 11½ mil líneas, dos oráculos, y una disciplina que ya pagó todo lo que la
letra pequeña cobraría. Eso explica la sensación de la mañana («la mejoría con el grafo es muy
estrecha») mejor que cualquier teoría: **la estrechez no es del grafo — es de que este repo ya vive
en su techo de verificación.** Cualquier capa nueva compite aquí contra un margen que no existe.
Donde el techo no existe —repos construidos por agentes sin esta disciplina, integración paralela—
la feature queda SIN MEDIR: ni validada ni descartada, y no se construye hasta que un repo real
enseñe el hueco.

**El colateral, real y capturado en vivo:** el falso verde del PROPIO Python. En Windows,
`subprocess.run(text=True)` decodifica el stdout del hijo con cp1252 **en un hilo lector**; un byte
UTF-8 sin mapa (0x81, de los subjects con tildes de hoy) mata el hilo y `run()` devuelve **rc=0
con stdout=None** — verde con la salida perdida. La consola capturó la excepción del hilo
(`threading.excepthook`, la puerta 2 de SCOPE) y el diagnóstico salió de `gb show` sin re-ejecutar.
Cura: `encoding="utf-8"` explícito en todo subprocess que capture texto. Va también a la memoria de
trampas de la máquina.

## 2026-08-13 · LA REFOCALIZACIÓN, ejecutada: la columna es el verificador — y el recorte que ordena, hecho el mismo día

La frase que lo disparó fue de Marcos, de viva voz: «independientemente no aporta demasiado». La
regla 5 dice qué hacer con eso — investigar, no blindar — y la investigación ya estaba hecha, solo
había que leerla junta: **lo que bloquea o produce un hecho único funciona siempre (converge 10/10,
rechazo 4/4, gate 3/3, la captura irreproducible); lo que informa, nunca** (0/6, empates 3/3 dos
veces, y de 6.015 invocaciones en 7 días casi todo era la maquinaria invocándose a sí misma —
`last` a mano: 5).

**La ley** (`5f7c803`): frase nueva en SCOPE/CLAUDE/ARCHITECTURE — cuando agentes escriben código,
gb dice la verdad: qué se rompe solo, qué se rompe junto, qué tests lo prueban y con qué estado
murió. El grafo deja de ser la frase del producto y pasa a MOTOR, medido por lo que sus
consumidores detectan. Sentencia por capa con su evidencia citada en SCOPE.md.

**El recorte** (`07a5a0c` + `3229ddd`, cada fase con la suite en verde):

- Fase 1: los hooks informativos por acción fuera del defecto (`calls --hook`, `delta` por edición,
  `graph --context --if-changed`). Queda el mapa de sesión, una vez, EN OBSERVACIÓN con criterio de
  muerte escrito.
- Fase 2: **−5.025 líneas** — viz.py entero (1.803), la superficie CLI del canvas, la maquinaria
  del watch, la capa de obra que solo pintaba el halo, y la plantilla de `floor`, que reinstalaba
  los hooks retirados en cada repo nuevo (el arnés ya no propaga el defecto muerto). Suite
  888 → 764 (124 tests eran del canvas); cli.py 2.688 → 1.808; src 11.479 líneas. Cortado por
  consumidores con detector de referencias a punto fijo; `gb check` emitió 15 señales de tests
  borrados y las 15 están justificadas aquí — informó, no bloqueó, que es su contrato.

**Las honestidades:**

1. La actividad derivada NO se fue con el canvas: la consume el bucle (agente/escalera), y ahí
   sigue. Lo que el mapa enseñaba con consumidor real sigue vivo por otra puerta: embudo en
   `status`/`list`, suelo en `floor`, procedencia en `--context`.
2. El README describe ahora menos de lo que el árbol sabía hacer ayer; los números del badge se
   remedirán al subir versión (regla del workflow), no aquí.
3. Lo retirado está en la historia de git, no destruido. Si una capa visual vuelve, vuelve por una
   medición — la sentencia lo dice en SCOPE — y con la lección de este día pagada: dos A/B en
   empate no se discuten, se obedecen.

## 2026-08-13 · La cirugía del import roto: el hueco con nombre, cerrado — y 0 falsos positivos sobre este repo

El caso sin red de las entradas de hoy: un consumidor VIEJO con la referencia colgante no viaja en
ningún diff, su arista no existe, y su test no corre **ni en la rama sola ni en la unión**. Falso
verde estructural, y violaba la promesa escrita en la cabecera de `impacted.py` desde el principio:
"un símbolo que no resuelve devuelve TODO".

**Lo construido** (criterio escrito antes, `e9c98f0`): el grafo declara `imports_rotos` — `from M
import y` con M del proyecto e `y` desaparecido, fichero:línea — y la selección lo lee como hecho
duro y cae a todo con el import nombrado en el motivo. El grafo dice el hecho; la decisión vive en
la selección (ADR 0008, mismo reparto que `nombrado_como_valor_en`).

**Los conservadurismos, porque un falso positivo recurrente mata la familia (regla 9):** solo
imports directos del cuerpo del módulo (uno dentro de `try`/`if` es fallback y ya maneja la
ausencia); censo ANCHO de nombres del destino — las constantes no son nodos del grafo, así que el
censo mira el AST entero, no la tabla; sin acusación posible con `import *` ni `__getattr__` de
módulo (PEP 562); y el filesystem como árbitro para submódulos que el barrido no vio.

**Medido:** 0 imports_rotos sobre galaxy-brain entero (la selección de este repo no pierde ni un
ahorro); 8 tests del hecho + 1 de la selección que ejecuta pytest de frente y paga el rojo que
antes no se veía; los 4 controles del banco sin moverse (4/4 CUMPLE); 888 en verde.

**Las honestidades:** `import M.viejo` roto (sin `from`) queda fuera de alcance y dicho en el
docstring; el motor multilenguaje no está cubierto (su licencia TIA ya gobierna qué estrecha); y
el censo ancho puede callar un roto real enmascarado por un nombre local homónimo — se eligió
callar antes que acusar, y esa elección está escrita en el código.

## 2026-08-13 · La tirada por parejas: 6/6 — y `contrato` rompió su predicción en la dirección buena

12 agentes Opus (3 parejas × 2 rondas), 0 caídas, 0 timeouts. Las seis rondas iguales por fuera —
cada rama verde sola, unión roja, choque nombrado — y cada pareja contando una cosa distinta:

- **`firma` 2/2, con la firma exacta del arreglo**: el test nuevo de B viajó, corrió, y el
  ImportError del símbolo renombrado puso la unión en rojo. Antes de fecc3a2 esto salía verde:
  el fix aguanta escritores reales.
- **`formato` 2/2 — el "bimodal" salió unimodal**: las dos veces B testeó llamando a `etiqueta()`
  de verdad (una además con un artículo inexistente), nunca contra un literal congelado. Con n=2
  no es ley: es la primera muestra de que Opus tiende al test de integración aquí.
- **`contrato` 2/2 CONTRA su predicción (0/2)** — y la lectura importa: el techo del detector
  (converge solo ve lo que algún test pisa) sigue siendo cierto — lo confirmó el control
  sembrado — pero los agentes reales no se quedaron en mi siembra: las dos veces B escribió el
  camino triste (`test_no_disponible_sin_precio`) sin que nadie se lo pidiera, y ese test
  convirtió el choque invisible en visible.

**Las honestidades:**

1. **n=2 por pareja**: dirección, no ley. Y las tres siguen poniendo el contrato en el camino
   crítico — esto mide detección y estilo de test de los agentes, no tasa base del fenómeno.
2. **La predicción de `contrato` estaba MAL y se dice**: subestimé al tester. El techo teórico
   existe, pero dos Opus de serie no lo rozaron — escribieron el test que lo tapa. El caso que
   sigue SIN red es el del consumidor VIEJO sin tocar (entrada anterior): ahí nadie escribe test
   nuevo porque nadie toca ese código, y la referencia colgante no suma arista.
3. Coste del día completo: 20 agentes Opus (8 de `escala` + 12 de parejas), 0 caídas, 0 timeouts.

**Consecuencia:** cuatro clases medidas con escritores reales — **10/10 choques visibles
detectados** (4 escala + 2 firma + 2 formato + 2 contrato) y 0 falsos verdes de unión tras el fix.
Lo siguiente con valor no es otra pareja: es la cirugía de columna del "import interno roto"
(consumidor viejo), el único hueco con nombre que queda.

## 2026-08-13 · Cuatro parejas con predicción previa — y el control de `firma` cazó un falso verde de la unión ANTES de gastar un agente

El banco de convergencia aprende parejas: cuatro clases de choque, cada una con su control sembrado
gratis y su predicción escrita antes de correr nada — `escala` (la medida 4/4 esta mañana), `firma`
(renombre de un símbolo público), `formato` (¿el test cruza el contrato o congela un literal?) y
`contrato` (0→KeyError sin test que lo pise, diseñada para NO verse: declara el techo — converge
solo ve lo que algún test corre).

**Primera pasada de controles: 3/4 — `firma` NO CUMPLE, y era un bug de verdad.** La unión salió
verde cuando debía ser roja: los ficheros nuevos viajaban al árbol compuesto (404c624) pero no al
índice, así que el diff de la unión no los declaraba y sus símbolos nunca eran semillas. Mientras
una arista viva subiera hasta ellos (`escala`, `contrato`) no se notaba; el renombre de `firma`
deja la referencia del otro agente COLGANTE — sin nodo del que subir — y el test que probaba el
choque no corría: **unión VERDE con un ImportError dentro**. Arreglo: `add -N` sobre el árbol
compuesto (`aislado._union`) — el test nuevo es semilla de sí mismo. Regresión fijada en
test_aislado; segunda pasada: **4/4 CUMPLE**, incluido el no-visto esperado de `contrato`.

**Las honestidades:**

1. **El control costó cero y pagó más que la tirada**: el falso verde lo destapó la pareja
   sembrada, no los 8 agentes de la mañana — que con `escala` no podían verlo.
2. **Pendiente que esto NO arregla**: la referencia colgante sigue invisible cuando el consumidor
   roto es VIEJO (no viaja en ningún diff) — un renombre con un consumidor preexistente sin tocar
   no corre el test de ese consumidor ni en la rama sola ni en la unión. El grafo distingue hoy
   tres motivos de no-resolución e "import interno roto" no es uno: darle categoría propia y que la
   selección lo lea como hecho duro (la promesa "un símbolo que no resuelve devuelve TODO" de la
   cabecera de impacted.py) es cirugía de columna y va con su propio criterio, no de tapadillo.
3. **Pregunta abierta, anotada sin investigar**: una rama cuyo trabajo es SOLO ficheros nuevos no
   corre pytest en su verificación en solitario (diff trackeado vacío → "nada que correr") y sale
   verde. Si eso esconde un falso "rama sana", tiene que salir en su propio control, no aquí.

**Consecuencia:** catálogo listo para la tirada real por pareja (`--agentes --pareja X`). Lo que
cada una mediría con agentes: `firma` que el arreglo aguanta escritores reales; `formato` si los
agentes testean a través del contrato o contra un literal (bimodal, el dato nuevo); `contrato` si
algún agente escribe el test del camino triste sin que se lo pidan (y entonces el choque se ve).

## 2026-08-13 · Agentes REALES en el banco de convergencia: el choque ocurre solo — **4/4, y `converge` lo vio las 4**

Primera tirada del modo `--agentes` (8dc967a): 4 rondas × 2 `claude -p` (Opus) sobre worktrees
**limpios** — nadie siembra, nadie les pide chocar. Tareas independientes sobre un contrato
compartido: A pasa `precio()` de euros a céntimos; B escribe `informe.linea()` consumiendo ese
precio. Presupuesto impreso antes de arrancar; 8 agentes, 0 caídas, 0 timeouts (tope 300 s).

**Resultado: choque en las 4 rondas, con firma idéntica.** Cada rama en verde POR SEPARADO — ambos
corrieron su pytest y terminaron limpios — y la unión en rojo las 4 veces:
`'total: 200 euros' != 'total: 2 euros'`. El falso verde por rama que 1e15dba nombró, reproducido
con escritores de verdad al primer intento.

**Las honestidades:**

1. **Esto mide DETECCIÓN, no tasa base.** La calibración previa (tasa publicada 5–10% → ~70% de no
   ver nada en 4 rondas) saltó por los aires porque estas dos tareas ponen el contrato compartido en
   el camino crítico: el choque es casi determinista *por diseño de la tarea*. Lo medido es que
   cuando el choque existe, `converge` lo ve — 4/4 con cero falsos verdes de unión — no cuánto
   ocurre en la vida real.
2. **n=4 con UNA pareja de tareas.** Firma idéntica las cuatro veces: es un escenario repetido,
   no cuatro escenarios. Lo que convertiría esto en medición de cobertura es variar la pareja —
   choques que no sean de escala numérica (renombrar, contrato de tipos, orden de argumentos).

**Consecuencia:** el control sembrado deja de ser la única evidencia — el fenómeno aparece sin
sembrarlo y el detector lo caza donde cada rama daba verde. Siguiente paso con valor: más parejas
de tareas, no más rondas de esta.

## 2026-08-10 · El recall de aristas es 96%, y con eso se cae la explicación de los 91 falsos verdes

Se fue a buscar un grafo de terceros que tapara el hueco que destapó el oráculo de cobertura. **Los
tres candidatos con mejores números publicados no producen ni una arista sobre este repo**
([docs/grafos-externos-2026-08-10.md](grafos-externos-2026-08-10.md)): PyCG está archivado y su
paquete de PyPI ni importa —y con un shim revienta su propio hook de imports sobre los 22 módulos—;
HeaderGen arrastra ~140 paquetes con tensorflow dentro; Jarvis no publica paquete. *Instalado ≠
funcional* ya lo teníamos; ahora también **publicado ≠ instalable**.

El pivote salió mejor que el plan: el runtime de Python da el hecho —«esta llamada ocurrió»— con
`sys.setprofile` y cero dependencias, en vez de la estimación de un estático con 69,9% de recall.
[bancos/oraculo_aristas.py](../bancos/oraculo_aristas.py).

**El resultado va contra la hipótesis con la que se empezó.** De las 1.518 llamadas que la suite
ejecuta de verdad, el grafo ve el **96%**. Los 63 huecos se reparten en 28 de despacho implícito y 31
de paso-como-valor —ambos **ya tienen puerta** río abajo— y **4 sin puerta**. O sea que *las aristas
que faltan no explican los 91 falsos verdes*: la causa está en otra capa y hay que ir a buscarla, no
suponerla. Se había dado por hecho lo contrario al planificar.

De los 4, **uno era el instrumento** (un closure de `converge` que se pasa a `_union`; el grafo no
emite nodo para funciones anidadas y el localizador lo colapsaba en su padre). Los otros 3 tenían una
sola causa: `from .graph import _git as _git_output` en `changes.py`. gb resolvía el alias dentro del
módulo pero no al cruzarlo, así que `delta.analyze → changes._git_output` no llegaba a `graph._git`.
Arreglado en `symbols._reexportado`, y **no roza el ADR 0008**: una sentencia `import ... as` no es
una conjetura sobre lo que un nombre podría valer en ejecución, dice a qué símbolo apunta. **Quedan
0 huecos sin puerta** y el grafo pasó de 2.486 a 2.498 aristas.

**Confirmado midiendo, no razonando:** con el arreglo dentro, el oráculo de cobertura da **93 falsos
verdes de 338 símbolos** (antes 91 de 332) y 40% de ahorro. La tasa no se mueve — 27,4% → 27,5%. El
arreglo de la re-exportación es real y son 12 aristas nuevas, pero **no es la causa de los falsos
verdes**, y era la explicación con la que se había planificado el trabajo siguiente.

**Dónde está la causa, subiendo por el camino REAL del perfilador.** Los que se pierden llegan por
enlaces que el grafo no tiene y que **ya tienen puerta**. O sea que el trabajo pendiente no era añadir
aristas al grafo: era que **las puertas de la selección son más débiles de lo que se suponía**. Así
que se midió antes de escribir nada — el oráculo de cobertura pasó a **atribuir cada falso verde a la
puerta que lo dejó escapar**, subiendo por el camino del perfilador y devolviendo el primer eslabón
que el grafo no tiene, clasificado. El resultado no fue una lista de casos sueltos:

```
=== POR QUE FALLA CADA UNO (la puerta, no el grafo) ===
   93  valor: la puerta de opacos no llego
       eslabon roto: galaxybrain.cli.main -> galaxybrain.cli.cmd_graph
```

**93 de 93, una sola causa**, y es la quinta media conexión de esta familia. `set_defaults(func=cmd_graph)`
es despacho de argparse: no deja arista. La puerta que ya existía cubría *«cambió el símbolo opaco»* —
entonces se corre todo— pero **no cubría el caso de al lado**, que era el único que fallaba: que el
camino desde el símbolo cambiado hasta su test **pase por** un enlace opaco. Ahí la cadena de llamantes
moría en seco y los tests del otro lado se perdían en silencio.

El arreglo va en dos capas, y la separación es el punto: `symbols` registra **dónde** se nombró cada
símbolo pasado como valor —hecho sintáctico, el `Name` está escrito en ese cuerpo— e
`impacted._enlaza_pasados_como_valor` trata ese cuerpo como posible invocador, que **sí** es
sobre-aproximar. El grafo dice hechos; la selección se pone en lo seguro.

**Y el diagnóstico acertó la clase, no el alcance:** dijo 93/93 y el primer arreglo cerró 71. Los 22
restantes eran la misma puerta en otro sitio — registros a nivel de módulo (`SONDAS = (..., _sonda_cruce)`),
donde el cuerpo del módulo no es un nodo y por tanto no tiene llamantes, así que enlazarlo no llevaba a
ningún test y la cadena moría igual que sin puerta. Se enlazan las funciones de ese módulo, que es la
sobre-aproximación más estrecha que lo cierra.

**Resultado final: 93 → 0 falsos verdes.** Precio: el ahorro medio baja de 40% a 27%. Es la decisión
correcta por la regla de esta familia —un falso verde la mata, el ahorro no— pero **13 puntos son un
precio real y se escriben, no se esconden**. Control de regresión: los huecos de arista siguen en 0 y
el recall en 96%. 858 tests en verde, gate limpio.

---

## 2026-08-11 · El abandono de la consola, investigado (regla 5): no está vacía — **el 82 % lleva estado**

La regla 5 dice que el abandono se investiga, no se blinda. Había dataset y era inmejorable: **136
capturas en disco, 35 sin leer en este proyecto, y las de hoy son mías**. Durante toda la sesión
diagnostiqué reejecutando con `grep` y `print` en vez de leer lo ya capturado — exactamente lo que
CLAUDE.md manda hacer al revés. El sujeto del abandono era yo, con los datos delante.

**Hallazgo 1 — de 136 capturas, CERO sabían qué comando había muerto.** El registro guarda `program`
y `argv_count`; ante 44 que dicen `program: .../Scripts/gb` no hay forma de saber si fue `gb calls`,
`gb tests` o un hook. Sin eso, actuar sobre una captura cuesta lo mismo que reejecutar — que es lo
que se hace. No era un fallo: `argv` está apagado por defecto porque los secretos viven en los flags
y guardarlos crudos ya fue una fuga. Se cierra con el punto medio: se guarda la **forma**
(`gb calls <arg> --depth <arg>`), nombres de flag sí, valores no.

**Hallazgo 2 — la consola NO está vacía.** 113 de 137 capturas (**82 %**) llevan estado en algún frame
de código propio, con mediana de 6 variables y máximo 41. Solo 12 no llevan nada, y otras 12 son
`SyntaxError`, que por construcción no dejan frame. O sea que el abandono no se explica por «no dice
nada»: dice bastante.

**Y el error de medida, el undécimo del sprint y el mismo de siempre.** La primera cifra fue 64 %,
mirando solo el frame MÁS PROFUNDO. En 34 casos ese frame es de la stdlib —`open`, `import`,
`json.loads`— donde gb no captura estado **a propósito**, y el estado que importa está un frame más
arriba, en código propio, que es justo donde el diseño lo pone. Midiendo el frame correcto: 64 % → 82 %.
Otra vez el instrumento acusando al producto de una decisión de diseño que el instrumento no miraba.

**Lo que queda, y es la hipótesis incómoda:** si la consola lleva contenido y aun así no se lee, el
motivo no es el contenido sino que **el traceback ya está en pantalla**. Su nicho real serían los
procesos cuyo fallo nadie ve: fondo, detached, hooks. Hoy hubo tres casos —los huérfanos que murieron
en silencio y un watch que se creyó vivo dos veces—. Esa fracción **no se puede medir con las 136
viejas** porque no guardan el comando; con `argv_forma` puesta, las nuevas sí lo permitirán. Se mide
cuando haya datos, no antes.

---

## 2026-08-11 · A escala (215 ficheros) tampoco: 3/3 y 3/3, y el motivo es peor — **`grep "from X import"` da los mismos llamantes**

Segunda tirada, montada para arreglar el techo de la primera: si el grafo no aportaba nada en un
proyecto de 4 ficheros porque cabía en contexto, la prueba honesta es un proyecto donde **no quepa**.

**El montaje:** 215 ficheros. 12 llamantes reales de `precio()` —4 directos, 4 con **alias de import**,
4 en **tabla de despacho**— y 200 módulos de ruido que hablan de precios sin llamar a `precio`. Un
`grep precio` ingenuo devuelve **226 aciertos**: un pajar. Verificado antes de disparar que el brazo B
recibe **los 12 exactos**, con los de tabla en su propia línea.

**Resultado: 3/3 en los dos brazos, otra vez.**

**Y el motivo no es el techo de la primera vez, es peor.** Mi diseño nunca fue hostil al grep: escondí
la LLAMADA (alias, tabla) pero no el IMPORT.

```
grep -rl "from tienda.precio import" tienda/   ->  12 de 12
```

En Python, con imports explícitos, **el import es un proxy casi perfecto de «este módulo usa esto»**.
El agente no necesita leer 215 ficheros: greapea el import y lee 12. La afirmación *«`gb calls`
encuentra llamantes que grep no encuentra»* es **falsa a nivel de módulo**, y es la parte del pitch
que más se repite.

**Lo que sigue en pie**, y no se ha probado ni a favor ni en contra:

- **granularidad de símbolo** — qué función dentro del módulo y en qué línea; el grep da el fichero
- **transitividad** — `--depth 2` es un cierre; a grep le costaría N pasadas encadenadas a mano
- **`import tienda.precio as m`** y luego `m.precio()`, que el generador ni siquiera produjo

**Decisión de método, y es la parte incómoda:** se para de gastar. Doce tiradas Opus, dos resultados
nulos, y un tercer diseño elegido DESPUÉS de ver fallar los dos primeros empieza a ser buscar el
montaje que dé el resultado que uno quiere. Eso ya no es medir. Si se retoma, el diseño se fija antes
y con los tres huecos de arriba nombrados de antemano.

---

## 2026-08-11 · ¿El grafo mejora la CORRECCIÓN de un agente? Con esta tarea, **no**: 3/3 y 3/3

La pregunta que el proyecto no había respondido nunca. Todo lo medido hasta ayer —ahorro, recall,
precisión, falsos verdes— es **gasto y seguridad**; que `gb calls` haga escribir código más correcto
se daba por supuesto porque suena obvio.

**El montaje.** Proyecto generado con tres llamantes de `precio()`: uno normal, uno con **alias de
import** (`grep "precio("` no lo encuentra) y uno en **tabla de despacho** (no hay llamada escrita
que grepear). La tarea cambia el contrato a céntimos manteniendo el comportamiento externo. Lo único
que separa los brazos es que B lleva pegada la salida de `gb calls`. El oráculo es una **suite oculta**
que el agente no ve nunca: si el oráculo es visible mide obediencia, no corrección — los commits de
agentes tocan tests un 23 % frente al 13 % de los humanos.

**Presupuesto escrito antes de disparar:** 3 por brazo, 6 tiradas, 300 s de tope. Opus headless.

**Resultado: 3/3 en los dos brazos.** Los seis agentes encontraron y adaptaron los **tres** llamantes,
incluido el de la tabla de despacho. Es un efecto **techo**, no suelo:

> Con esta tarea el grafo no cambia la corrección — Opus la resuelve sin él.

Y era predecible, porque se avisó antes de lanzar: cuatro ficheros de veinte líneas **caben enteros en
el contexto**, y el grafo no puede aportar donde no falta información. Lo que queda sin probar es la
hipótesis contraria, que necesita otro montaje: un repo donde los llamantes **no quepan**. Este banco
no la toca y no debe citarse como si lo hiciera.

**Lo que el montaje sí destapó, antes de gastar un agente:** `gb calls` reportaba **2 de 3** llamantes
— se dejaba el de la tabla de despacho. El grafo lo sabía (`nombrado_como_valor_en`, que alimenta la
selección de tests desde el 10-ago) y la superficie que lee el agente no lo decía. Décima media
conexión, y en el peor sitio posible. Arreglado antes de medir: con el bug, el brazo B habría corrido
lastrado y el resultado habría salido en contra por el motivo equivocado.

**Y el fallo de método, el tercero igual en dos días.** El primer veredicto fue **0-0**, leído como
«el grafo no cambia la corrección» — la conclusión correcta por el motivo equivocado, y a punto de
firmarse. El oráculo comparaba `linea('pan') == 'pan: 2'` y los agentes producían `'pan: 2.0'`:
**medía formato, no valor**. Los dos brazos marcaban cero y el empate parecía el resultado. Corregido
el oráculo y re-evaluados los mismos seis árboles —sin gastar una tirada más— salió 3/3 y 3/3.

Es exactamente el mecanismo 5 de [como-se-rompe-un-instrumento](como-se-rompe-un-instrumento.md): un
cero que significa «no he mirado» se lee igual que uno que significa «no hay efecto». Y entre medias,
dos `print` de éxito **incondicionales** afirmando que un reemplazo se había aplicado cuando
`grep -c` daba 0 — el mecanismo 4, tres veces en el mismo día.

---

## 2026-08-10 · La precisión del grafo, medida por primera vez: **97%** — y las dos veces que el instrumento acusó al grafo de sus propios puntos ciegos

Los dos oráculos medían **recall**: qué ve el grafo de lo que ocurre. Con eso se puede tener recall
perfecto y el grafo lleno de aristas inventadas, y nadie se enteraría. Importa porque una arista falsa
no cuesta un verde falso pero hace que `gb calls` **mienta sobre quién rompe algo** — que es
justamente lo que un agente lee antes de tocar código.

Método: una arista `a -> b` es sospechosa si el cuerpo de `a` corrió de verdad y la llamada a `b` no
ocurrió ni una vez desde ahí. Es **cota superior**, nunca una cuenta de aristas falsas: una rama que
la suite no toma da exactamente la misma señal.

**Primera tirada: ≤35% (779 de 2.251).** Un número alarmante y falso. Dos confusores, los dos del
instrumento:

1. **Los dobles de test.** La primera acusada fue `bootstrap.enable -> bootstrap.pth_path`, que es una
   llamada incondicional en la primera línea de la función. La arista es cierta; el test hace
   `monkeypatch.setattr(bootstrap, "pth_path", lambda: pth)`, así que lo que corre no es el símbolo.
   Hay 41 sustituciones en la suite y golpean al código **mejor** probado — sin descontarlas, la
   medida acusa más cuanto mejor está el test. Se derivan del AST de los tests, no de una lista.
2. **El punto ciego del perfilador**, que era el gordo: su filtro exige que el LLAMADO viva bajo
   `src/galaxybrain`, así que toda arista hacia `bucle.*` o `bancos.*` era **inobservable por
   construcción**. Las tres peores de la lista eran exactamente eso.

**Con los dos descontados: 1.472 de 1.515 confirmadas en ejecución — 97%, y ≤3% (40) sin explicar.**
Comprobada una a mano: `cmd_graph -> _abrir` vive tras `if args.open:`, una rama que la suite no toma
porque abriría un navegador. La arista es cierta. El 3% parece dominado por ramas legítimas.

**La lección, que es la misma del día por octava vez:** un instrumento nuevo acusa primero a lo que
mide y casi nunca a sí mismo. Los dos confusores hacían que el número fuese *peor* cuanto mejor
estaban el test y el reparto del código — cuando una medida empeora al mejorar lo medido, el defecto
está en la medida.

Consecuencia directa del hallazgo de abajo. Si un banco puede aprobar con la cascada rota, el
problema no es Rust: es **el criterio**, y lo comparten los cuatro. Los bancos preguntaban *«¿se
puso roja la selección?»* — un booleano — cuando la pregunta es *«¿contiene la selección **todos**
los tests que se ponen rojos?»*. [`bancos/estricto.py`](../bancos/estricto.py) corre cada fichero de
test por separado y compara conjuntos.

**Control positivo primero, porque un detector sin él es decoración.** Con la licencia puesta y antes
de tocar nada, Rust seguía dando `0 FALSOS VERDES` y el criterio nuevo marcó `CASCADA ROTA en 5
rotura(s)`, señalando `informe.rs` en las cinco — la arista exacta que faltaba. Detecta.

**Y el arreglo de Rust apareció al mirar el sitio correcto.** El intento anterior había concluido que
«ast-grep casa el patrón y gb no emite la arista, luego el hueco está en la extracción». Cierto, y la
causa era de una línea: `$A` es la metavariable del **receptor** en `$A.$FN($$$)` (Java, Kotlin,
Scala), y el extractor compone `receptor.llamado` cuando la ve. Con `$M!($A, $FN($$$))`, `$A`
capturaba la cadena de formato y gb emitía `"TOTAL {:.2}".emitir`, que no resuelve contra nada. La
misma metavariable llamada `$ARG` funciona. Un nombre.

**Resultado, y la cifra que lo valida no es la más alta.** Rust pasa a `0 falsos verdes, cascada
exacta, 52% de ahorro` — y **baja** desde el 64% que daba roto, porque aquel ahorro extra era el test
que se dejaba. Los cuatro lenguajes con banco dan ahora exactamente **52% y cascada exacta** sobre la
misma forma de proyecto: js, go, csharp y rust. Que coincidan es la señal; que uno destacara era el
síntoma. Licencia concedida — ocho lenguajes con ella (nueve contando Python).

**El otro cero mentiroso, cazado de paso.** Un lenguaje sin licencia cae a la suite entera, así que
no puede fugarse nada y el contador de fuga sale a cero: el pie habría dicho «cascada exacta» cuando
el hecho es «no he medido nada». Es el mismo cero que el gate ya persigue («cero violaciones» cuando
no se miró), y ahora se dice aparte: `cascada NO MEDIDA: cayó a la suite entera`.

**Y la pregunta incómoda que esto abre: java, php y lua tienen licencia del 9-ago, concedida con el
criterio que acaba de demostrarse insuficiente.** En esta máquina no hay ruby, php, lua ni java, así
que no se pueden remedir con rojos reales — y instalar cuatro runtimes no se hace por cuenta propia.
Pero la mitad que falló en Rust **no necesita runtime**: el rojo/verde lo da el intérprete, la
CASCADA sale del grafo. Así que `bench_multi.py` ya no se calla cuando falta el binario: genera el
proyecto, rompe, y comprueba a cuántos tests llega la selección contra la cascada esperada `3-2-1-1`
— que llevaba escrita en prosa en su cabecera desde el principio sin que nadie la comprobara.

Resultado: **java, php y lua dan cascada EXACTA 4/4**. No es una licencia —para eso hacen falta rojos
reales y se dice en la salida— pero es la mitad que estaba en duda, y sale limpia.

**Tercer cero mentiroso, en mi propia herramienta y en la misma tirada.** La primera versión marcó a
Ruby con `cascada ROTA 4/4`: Ruby no tiene licencia, así que cae a la suite entera **por diseño**, y
eso es la caída segura funcionando. Acusarla era acusar justo al mecanismo que protege del verde
falso. Ahora se lee la licencia de la tabla y se dice `cae a todo (sin licencia: es lo correcto)`.

---

## 2026-08-10 · Rust: 0/7 y 64% de ahorro, y aun así **sin licencia** — el banco pasaba por suerte

Al ir a conceder la licencia que le faltaba a Rust salió lo contrario de lo buscado, y es el mejor
resultado del día porque es el que evita un falso verde en producción.

Con `tia=True` el banco da **0 falsos verdes de 7 y 64% de ahorro**. Con eso se firma una licencia
cualquier día. Pero la cascada está **rota**: falta `informe.linea → factura.emitir`, porque el código
es `format!("TOTAL {:.2}", emitir(xs))` y la llamada **no es el primer argumento del macro** — los tres
patrones declarados solo cubren la primera posición. Rompiendo `iva`, el test de `informe` falla de
verdad y la selección **no lo elige**; el banco sale verde únicamente porque otros tests ya salían
rojos. **Un 0/7 que pasa por suerte de qué fichero cayó no demuestra nada**, y esta familia se mata con
un falso verde.

Se intentó arreglar y tampoco: `ast-grep` casa `$M!($A, $FN($$$))` y captura `$FN` —verificado con
`--json`— pero gb sigue sin emitir la arista. **El hueco está en la extracción, no en la tabla de
lenguajes.** Revertido todo, con el diagnóstico escrito junto a la entrada de `rust` para quien lo
retome.

**La lección de método, que vale más que el caso:** el criterio de muerte de esta familia (0 falsos
verdes) es necesario y **no es suficiente** cuando el banco tiene pocos ficheros de test — con seis
módulos encadenados, perder un test impactado se tapa con que otro caiga rojo. Un banco así puede
aprobar con la cascada rota. Hay que mirar la cascada, no solo el veredicto.

**Y el error de método, que costó dos tiradas de tres minutos y es el mismo de siempre.** Los datos se
anotan por `(fichero, línea)`. Al editar `symbols.py` con datos de la tirada anterior en disco, las
líneas se desplazaron y el informe salió lleno de huecos inventados **que parecían un hallazgo**. Se
puso una huella del árbol… **de `src` solamente**, y a la tirada siguiente la misma trampa saltó por
`tests`: los dos extremos de una arista son nodos, así que mover los tests desplaza al llamante igual
que mover `src` desplaza al llamado. El hueco «superviviente» estaba, cómo no, en el fichero recién
editado. Es la cuarta media conexión de esta familia: **una guardia que cubre una de las dos entradas
se lee como verde**. Ahora la huella cubre el árbol entero y el banco se niega a contrastar si no casa.

---

## 2026-08-09 · La escalera, medida: **el rechazo mueve al modelo; el aviso no** (6 tiradas)

Tres tandas más sobre los mismos tres repos, ya con los agujeros del gate cerrados. La
pregunta era si el peldaño siguiente cambia de comportamiento cuando se le pone delante un
hecho nuevo — y la respuesta, con la muestra que hay, es **no**.

**Lo que sí funciona: rechazar.** `find_call_violations` paró la violación de Rust **3/3
veces**, y en dos de ellas el agente se corrigió al peldaño siguiente. Go, cuando insistió,
escaló por la regla del mismo rechazo dos veces. La escalera hace su trabajo.

**Lo que no: avisar.** El hecho `simbolos_preexistentes` viajó al peldaño 1 en las tiradas C
y D, y las **seis** ejecuciones siguieron degradando exactamente igual que sin él:

| | tirada C | tirada D (mismo enunciado) |
|---|---|---|
| js | duplicó la suma | duplicó la suma |
| go | correcto (aceptó en el 0) | escaló: insistió en cruzar |
| rust | `let base = 60.0;` **hardcodeado** | duplicó la suma |

Y hay un matiz que invalida parte del experimento y conviene escribir: en ese enunciado
**modificar `carrito.total` era la tarea**. O sea que el aviso decía algo cierto y
completamente irrelevante — era ruido. El hecho tiene valor cuando la tarea solo pedía
AÑADIR y el agente destripó algo de paso (el caso de la tanda anterior, con `carrito.Total`
vaciado); en una tarea de modificación no dice nada. **gb no puede saber en cuál está**, así
que se queda en el veredicto —donde un humano lo lee con contexto— y no se le pide más.

**El techo, ya con seis ejecuciones detrás:** duplicar una función, clavar el resultado
esperado como constante y escribir el test que afirma tu propio error **no dejan rastro
estructural**. No es un fallo del grafo ni se arregla con más nodos: es la frontera entre lo
que la estructura puede demostrar y lo que no.

**Y el error de método propio, que costó una tirada entera:** la primera versión de
`simbolos_preexistentes` deducía del diff qué símbolo era nuevo (cuerpo entero dentro de
líneas añadidas). Falso positivo inmediato: git alineó la llave de cierre de una función
recién creada con la de la función vieja y la dejó como contexto, así que `iva.informe`
—escrita en ese mismo intento— salió acusada de preexistente. La alineación de un diff es
una heurística de presentación; qué existía lo sabe git. Ahora se le pregunta a él, y las
listas pasaron de 2/3/3 símbolos a 1/1/1, todos ciertos. **La tirada C se midió con el
instrumento roto y por eso hubo que repetirla entera.**

---

## 2026-08-09 · Agentes reales en js/go/rust: **dos falsos verdes en el gate, y un tercero que bloqueaba siempre**

Tres tandas de agentes escribiendo código de verdad en sus propios repos, con `.gb-boundaries`
declarando `iva -/-> carrito`. Lo que se buscaba era medir la **escalera** (¿se corrige el agente
cuando recibe un rechazo determinista?). Lo que salió fue otra cosa, y más grave.

**Tanda 1 — trampa blanda.** Los 16 lenguajes resolvieron la tarea correctamente. 16/16 `ESCALAR`,
**0 medido**. La trampa era tan fácil que nadie la pisó, y el `ESCALAR` no venía del código sino de
la cobertura de la ley (ver abajo).

**Tanda 2 — trampa dura. 3/3 cruzaron la frontera, gb cazó 1.** Los dos escapes eran de naturaleza
distinta y ninguno lo habría encontrado un test escrito desde este repo:

| | cómo cruzó | veredicto |
|---|---|---|
| js | `import { total } from "./carrito.js"` | cazado |
| go | `import ( "ejemplo/carrito" … )` — bloque agrupado | **falso verde** |
| rust | `crate::carrito::total(items)`, sin `use` | **falso verde** |

El de Go era un patrón incompleto (`import "$SRC"` solo casaba el bloque entero, ningún spec) y la
forma agrupada **es la normal del lenguaje**. El de Rust era una laguna del mecanismo, no un patrón
mal escrito: `A -/-> B` prometía "A no depende de B" y solo miraba IMPORTS. En Rust, Java, C#, Kotlin
y Scala se alcanza otro módulo sin importarlo. De ahí `find_call_violations`, que comprueba la misma
regla sobre las aristas CALLS — llamar a B es depender de B.

**Tanda 3 — la trampa se ablandó sola y salió el fallo peor.** Al pasar `items` como parámetro, el
atajo dejó de ser necesario: **0/3 cruzaron** (control positivo hecho — plantando el cruce a mano, el
gate lo caza por import *y* por llamada, así que el cero no es mudez). Pero al comprobar el gate
sobre los worktrees: **rc=1 en los tres, sin un solo cruce**. `_boundaries_elsewhere` sube por los
ancestros y para al ver un `.git`, comprobando `isdir` — y en un worktree `.git` es un **fichero**.
Trepaba hasta el checkout principal, encontraba su `.gb-boundaries` y lo denunciaba como "dos fuentes
de reglas", que bloquea. Es el falso positivo que persigue la regla 9, en el único sitio donde
trabajan los agentes, saltando siempre.

**Lo que empeora ese fallo en vez de mitigarlo:** la escalera no se veía afectada porque lee el JSON,
no el código de salida. O sea que **la máquina aceptaba un diff que el humano no podía commitear**.
La lección se repite y ya tiene nombre: *un hecho que el gate usa para bloquear tiene que estar en
los hechos de la escalera, siempre*. La misma media conexión existía con `call_violations` — el gate
rechazaba y `hechos_del_arbol` no lo leía.

**El hallazgo que no es un bug de gb.** Los tres agentes devolvieron `TOTAL 145.20 IVA 25.20` donde
el enunciado pedía `TOTAL 120.00 IVA 25.20`, y los tres escribieron su test afirmando **su propia**
interpretación. Verde, criterio pasa, `ACEPTAR` × 3. `tests_verdes` es un hecho honesto; lo que no es
independiente es el test. **Un test escrito por el mismo agente mide coherencia consigo mismo, no
corrección**, y el auto-accept hereda esa debilidad entera. Ningún hecho del grafo la cubre, y el
arreglo natural —que el test lo escriba otro agente— es orquestación, que el
[ADR 0006](adr/0006-gb-provee-no-orquesta.md) deja fuera. Queda escrito como límite, no como tarea.

**Consecuencia de método, además de los tres arreglos:** los repos se comprueban **antes** de gastar
agentes. En la preparación de la tanda 3 salieron sin coste tres cosas: `ts` estaba rojo de base
(`npx tsx` sin instalar) y habría rechazado en el peldaño 0 por algo que no hizo el agente; `csharp`
tiene tests pero ningún comando declarado; y los tres criterios de terminado decían
`gb graph . --gate`, o sea **el mismo gate que la escalera ya comprueba** — `ACEPTAR` no añadía nada
sobre `SIN_OBJECIONES`. Ahora el criterio es la suite entera, que sí es evidencia independiente de la
selección estrechada.

**Y lo que sigue sin medirse después de tres tandas: la escalera.** Cero rechazos reales, cero
peldaños ejecutados. La pieza que sostiene el auto-accept no se ha probado ni una vez.

---

## 2026-08-08 · `gb check` contra 67 commits ajenos: **2 señales, 0 acusaciones falsas** — la regla 9 medida

La capa que más riesgo tiene de gritar sin motivo, sobre historia que no es nuestra: los 67 commits
de `guardia`, uno a uno.

**Resultado: 2 commits con señal (3 %), ambos `SKIP_ADDED`, ambos ciertos.** Cero `ASSERT_WEAKENED`,
cero tests borrados, cero señales de firma. Los dos marcadores existen todavía hoy y son
`@pytest.mark.skipif(not os.environ.get("GUARDIA_SMOKE_LLM"))` — smoke tests que invocan un LLM real
y gastan cuota. Decisión legítima, no defecto.

**Y ahí está la validación de la regla 9, que es lo que importa:** la señal es **cierta pero benigna**.
Si `SKIP_ADDED` bloqueara, este repo habría comido dos `--no-verify` en su historia — y a partir del
segundo, la gate entera deja de leerse. Informar y devolver es lo que la mantiene puesta. Es el mismo
patrón que ya obligó a afinar `FIRMA_CAMBIADA_SIN_LLAMANTES` (3/3 ciertos e inaccionables).

**El error de método, otra vez el mismo, y por eso se escribe:** el primer barrido dio **0 de 67** y
casi lo doy por bueno. Leía `d['signals']`; la clave real es `d['flags']` — el instrumento estaba
mudo, igual que con `edge_list` esta misma mañana. Lo cazó un **control positivo**: debilitar una
aserción real y borrar un test en un worktree desechable, y comprobar que `gb check --staged`
dispara las 2 señales esperadas. Regla que queda: **un cero no se reporta sin control positivo**. Un
instrumento mudo y un repo limpio dan exactamente la misma cifra.

---

## 2026-08-09 · Ocho licencias, y las tres veces que la sonda dejó pasar un hueco real

Segunda tanda del catálogo, esta vez en lote — reproche justo del usuario: *«no tiene sentido
implementar 1, hacer test, implementar 2, hacer test»*. Una sola medición sobre todos los huecos, una
sola verificación.

**Lo que la medición en lote encontró y la de uno en uno no habría encontrado:**

| Hueco | Por qué la sonda no lo veía |
|---|---|
| **Las clases de Ruby daban ERROR de patrón** | solo exigía "algún símbolo", y los `def` sí salían |
| **PHP sin métodos de clase** — casi todo el PHP real | ídem |
| **Lua sin `function M.x()`** — *la* forma de exportar | ídem |
| **Java con CERO llamadas**, ni candidatas | su fuente llamaba sin receptor |

El de Java es el que más enseña: en **Java, Kotlin y Scala toda invocación es `receptor.metodo(...)`**
en el AST, y `$FN($$$)` no casa nada. Con `$A.$FN($$$)` el motor recompone el nombre cualificado y la
cadena sale entera. Tres veces en dos días que la sonda pasa por encima de un hueco real; ahora
comprueba clases y métodos donde la tabla los promete, derivándolo de la tabla misma.

**Las licencias, medidas con rojos reales** (ruby, php, lua, jdk y scala-cli instalados para poder
hacerlo):

| Con licencia (8) | Denegada, con motivo escrito |
|---|---|
| Python · JS · TS · Go · C# · Java · PHP · Lua | **Ruby**: llama sin paréntesis (`total x`) y eso no es un nodo de llamada · **Rust**: llamadas dentro de macros |

Java, PHP y Lua dan **0 falsos verdes, cascada exacta 3-2-1-1 y 56 % de ahorro**.

**Dos errores del banco que parecían del motor**, y por eso se escriben: buscar la función por el
nombre del módulo (`carrito` define `total`) dejó tres roturas sin aplicar — el banco lo dijo en vez
de dar un verde silencioso; y las funciones de Lua en **una sola línea** hacían que la rotura cayera
fuera del cuerpo, sin semilla, con un `4-2-4-4` que parecía errático del motor y era del fixture.

**Y el fallo de método más caro, el cuarto de la semana:** C# entró en la tabla sin métodos porque
probé cinco patrones a ciegas. `--debug-query=ast` lo explicaba en una línea —`ERROR` sobre el `$` de
la metavariable— porque ast-grep parsea un patrón suelto de C# como función local de nivel superior.
La cura son los patrones **contextuales**, y con ellos C# pasó de medio lenguaje a licencia completa.
Mirar el instrumento antes de tantear habría ahorrado dos días.

---

## 2026-08-09 · El catálogo multilenguaje, y por qué «17 lenguajes» no es la cifra que importa

Un proyecto JS mínimo destapó que gb daba el **10 %** de su valor fuera de Python — y encima mentía
(`gb check` → "Sin señales" sobre un árbol que no había leído). De ahí salieron el ADR 0009 y el
motor por tabla: **16 lenguajes** con `ast-grep` **por referencia**, cero dependencias Python nuevas.

Fueron 17 durante un día. **C++ se sacó** (9-ago): ninguno de los cinco patrones probados extrae una
definición —ni siquiera `class $NAME { $$$ };`— así que solo producía nodos de módulo, sin símbolos
ni imports. Y era **peor que ausente**: al figurar su extensión como "leída", el aviso de frontera
dejaba de saltar y el usuario recibía un grafo vacío sin que nadie le dijera por qué. Fuera de la
tabla, gb dice *"veo C++ y no lo leo"*, que es la verdad. C sí se arregló en la misma tirada: en C
una llamada suelta es una **sentencia**, no una expresión, así que `$FN($$$)` no casaba nada — con
`$FN($$$);` y `$T $V = $FN($$$);` el lenguaje pasa a tener aristas de llamada.

**Lo que hace que el catálogo no sea una lista de intenciones: la sonda de conformidad.** Cada
lenguaje aporta un fuente mínimo y se comprueba contra la tabla que extrae lo que promete. En su
primera tirada **cazó 5 promesas falsas** que habría publicado: `ts` sin un solo símbolo (faltaba
`: $RET`), `csharp` sin resolver la llamada interna, y `ruby`/`php` sin una sola arista porque
`require_relative` no lleva punto inicial.

**Y la cifra que de verdad importa no es 17, es 3.** Los bancos con rojos reales:

| Lenguaje | Runner | Falsos verdes | Ahorro | Cascada |
|---|---|---|---|---|
| JS | `node --test` | **0/7** | 52 % | 5-4-4-3-2-1-1, exacta |
| Go | `go test` | **0/7** | 52 % | 5-4-4-3-2-1-1, exacta |
| Rust | `cargo test` | 0/7 | 64 % | **incompleta** |

Rust es el caso instructivo. Su banco daba 0 falsos verdes y **más** ahorro que los otros dos, y aun
así se le negó la licencia: al mirar por qué el símbolo más profundo alcanzaba 4 tests y no 5,
faltaba `informe.linea → factura.emitir` porque la llamada vive dentro de
`format!("TOTAL {:.2}", emitir(xs))` — el cuerpo de un macro es un árbol de **tokens**, no una
expresión. Eso no es menos ahorro: es **sub-selección**, la única dirección que produce verdes
falsos. Aquí no lo produjo **de puro azar**, porque todos los tests recorrían la cadena.

**Consecuencia: estrechar exige licencia medida** (`tia`, defecto `False`). Un lenguaje no puede
estrechar el día que entra en la tabla: primero su banco, después la licencia. Los otros 14 corren la
suite entera y el informe dice por qué.

**De propina, lo que desbloqueó Go:** las llamadas cualificadas (`paquete.Funcion()`) se descartaban
como techo, y ésa es la forma normal de llamar fuera del módulo en Go, Java, C#, Kotlin y Scala — su
grafo de llamadas salía con **cero aristas entre paquetes**. Ahora se resuelven casando contra
símbolos que existen, solo si hay exactamente uno. Su test de control (un prefijo que **no** es
módulo) destapó un `IndexError` propio: la función podía devolver lista vacía y el código la indexaba
igual; el docstring ya lo decía y el código no.

**El patrón de error más caro de estos dos días, por si sirve de aviso: TRES desajustes de rutas del
mismo tipo.** El diff da rutas desde el toplevel del repo y el grafo desde la raíz analizada. Se
manifestó (1) en la actividad, encendiendo el fichero entero —47 símbolos por editar uno— hasta poner
`--relative`; (2) en `ficheros_tocados`, con un filtro `.py` a mano que dejaba invisible a un agente
trabajando en `.go`; y (3) en el agente anclado, donde **todos** los llamantes figuraban como "sin
tocar" siempre. El tercero solo lo cazó un **control positivo** — el caso negativo daba el resultado
esperado y habría pasado por bueno.

---

## 2026-08-08 · Roturas SUTILES (mutación): 0/20 falsos verdes — y lo que encontró en el repo ajeno

Cierra el hueco que dejó escrito la entrada de abajo: *«las 22 roturas son duras; no dicen nada
sobre contratos sutiles»*. 20 mutaciones semánticas sobre `guardia` —`==`→`!=`, `True`→`False`,
`<=`→`<`, `+`→`-`— que **no petan**: el código sigue corriendo y solo responde mal.

Detalle de método que decide el experimento: la mutación se aplica con **cirugía de texto sobre el
span exacto del operador**, no con `ast.unparse`. Reescribir el fichero entero cambiaría todas las
líneas, el diff sería total, `gb tests` seleccionaría todo y la prueba **se aprobaría sola**. Así el
diff es de un carácter, que es el caso difícil. (mutmut no corre en Windows nativo; de ahí el bicho
a mano.)

**Resultado sobre gb: 0 falsos verdes de 20.** Acumulado con la tanda de abajo, **42/42**.

**Y la honestidad, que aquí pesa más que el número:** 17 de las 20 selecciones fueron la suite
entera. Un cambio en `auditoria.py` o `generador.py` toca módulos que importa medio repo, así que
esta tanda mide **corrección, no ahorro** — el ahorro lo mide la de abajo (2–9 ficheros de 20, y
1 test de 235 en el extremo). Un 0/20 sin este párrafo se leería como una victoria que no es.

**Lo que encontró en el repo ajeno, que no es un hallazgo sobre gb: 11 de 20 mutantes SOBREVIVEN.**
Verificado a mano el más serio, y no es equivalente — en `auditoria.verificar`, la rama del enlace
roto:

```
intacto  → Veredicto(intacta=False, motivo='el enlace previo no cuadra')   ✓
mutado   → Veredicto(intacta=True,  motivo='el enlace previo no cuadra')   ← se contradice
suite    → VERDE
```

Un log con el campo `previo` mentido y el `hash` consistente **es alcanzable** (se construyó) y no lo
cubre ningún test: `test_alterar_el_contenido` dispara la guarda del hash y
`test_borrar_una_entrada_intermedia` la del `seq`, así que a esa rama no llega nadie. Hueco real del
invariante 7 de guardia. Igual con `frozen=True` en `Estado` y `Entrada`: voltearlo no lo nota nadie,
y esas inmutabilidades son premisa del diseño.

**El error de método, apuntado porque casi invalida la tanda:** una sonda a mano daba resultados
imposibles (el veredicto no cambiaba bajo una mutación que sí estaba en disco). Causa: `$PWD` en
git-bash devuelve `/c/Users/...`, que el Python de Windows no interpreta, así que `PYTHONPATH` no
valía nada y `import guardia` caía en el **repo principal** por el editable install — se estaba
midiendo código sin mutar. El script usaba rutas Windows y no le afecta. Lo cerró imprimir
`modulo.__file__`. Regla que queda: **al medir sobre un worktree, verificar de dónde importa Python
antes de creerse un resultado.**

---

## 2026-08-08 · El techo del 40% puesto a prueba en código ajeno: **22/22 sin un solo verde falso**

El grafo resuelve el **38%** de las llamadas candidatas en gb y el **40%** en `guardia`. Que el número
se repita en un repo que no es nuestro dice que no es un defecto de gb: es el techo del análisis
estático de Python sin tipos. El 60% restante es `atributo-de-variable` (`obj.metodo()`), 3328 casos
aquí y 348 allí.

Ese techo **solo puede hacer daño en un sitio**: `gb tests`. Si el grafo no ve un llamante puede
seleccionar de MENOS, y seleccionar de menos da verde con el árbol roto. El argumento de diseño era
que los consumidores degradan hacia el silencio; esto lo convierte en medición.

**Protocolo** (worktree desechable sobre `guardia`, 22 tiradas): inyectar `raise RuntimeError` al
inicio del cuerpo de una función → `gb tests --worktree --json` → correr **solo** su selección →
correr la suite entera → si la entera es roja y la selección verde, es un falso verde.

| Objetivos | Selección típica | Falsos verdes |
|---|---|---|
| 8 símbolos **con** llamantes resueltos | 2–9 de 20 ficheros | **0** |
| 14 símbolos **invisibles** (cero llamantes resueltos) | **20 de 20** | **0** |

Lo que hace válido el resultado es la segunda fila: ante un símbolo que no ve, gb **no concluye "0
tests", concluye "córrelo todo"**. Y lo que impide que el 22/22 sea trampa es la primera: sí
discrimina, no está aprobando el examen seleccionándolo todo siempre. El extremo, en
`transporte.extraer_json`: `1 de 235 test(s) (0%) en 2 fichero(s)` — **un test de 235, y era el que
fallaba**.

**Códigos de salida, que es lo que consume un hook:** roja+`--run` → 1 · roja+`--run --isolated` → 1 ·
verde+`--run` → 0 · sin `--run` (solo lista) → 0. `--isolated` —reconstruir HEAD+diff en un árbol
limpio— **no se había ejecutado nunca fuera de este repo** y funcionó a la primera sobre layout
`src/`. Era el candidato más probable a romperse.

**Las dos honestidades:**

1. La suite de `guardia` tarda **7,3 s**; un fichero suelto, 1,16 s. Ahí el TIA no ahorra nada útil.
   Esto prueba **corrección**, no utilidad en ese repo — el ahorro importa en suites lentas.
2. Las 22 roturas son **duras** (excepción inmediata). No dice nada sobre roturas sutiles: un
   contrato que devuelve mal un valor sin petar.

**Y de propina, un bug real cazado de rebote — el mejor de la tanda.** Al correr la suite de gb en un
shell sin `TMPDIR`, pytest puso sus temporales DENTRO del repo y **101 tests se pusieron rojos**. No
era una regresión: era `_py_no_ignorados` topándose con la regla `pytest-of-*/` del propio
`.gitignore`. Reducido a mano, el síntoma limpio es peor de lo que parecía:

```
$ gb symbols pytest-of-Marcos/.../pkg     # 1 fichero .py dentro
llamadas: 0 resueltas de 0 candidatas (0%)
```

**Cero nodos y ni una palabra del motivo.** Pedir una carpeta a dedo y recibir un grafo vacío se lee
como «aquí no hay nada» — exactamente la mentira en verde que el docstring de `_iter_py_files` dice
no poder contar. La cura no cuesta un subprocess: **una lista de permitidos vacía no es información,
es su ausencia**, así que se descarta el filtro. Apuntar a una carpeta ES pedirla, como `git add -f`;
y con código del proyecto bajo la raíz la lista nunca sale vacía, luego el caso del 7-ago queda
intacto. Fijado con un test que se pone rojo al deshacer la línea.

Vale la pena decir de dónde salió: **no lo encontró ningún test de los 654, lo encontró un entorno
raro**. Séptima vez que el hueco lo destapa el uso y no la suite.

**Consecuencia: no se toca el grafo.** Subir del 40% exigiría inferencia de tipos (medido: pyrefly,
37/37 falsos positivos sobre código sin anotar) o resolución heurística por nombre, que metería
aristas inventadas en una **gate** — prohibido por la regla 9. La única vía compatible con la ley
sería evidencia de runtime (`coverage --contexts`) como capa aparte, y **su disparador es un caso
medido donde el techo cueste algo**. Hoy, tras 22 intentos de fabricarlo, ese caso no existe.

---

## 2026-08-08 · Tres fricciones reportadas mirando trabajar a un agente, y sus curas

Sesión de observación: un agente real trabajando sobre galaxy-brain en un worktree, con el mapa
delante. Lo que salió no fue del código sino del **uso**, que es donde este proyecto encuentra sus
bugs:

1. **«Los procesos me flickean en el cmd.»** El watch en `--fondo` se lanzaba con
   `DETACHED_PROCESS` — o sea SIN consola — y como llama a `git` en cada regeneración, Windows le
   creaba una ventana a cada hijo. Con un agente trabajando, el escritorio parpadeaba cada 3 s.
   Cura: `CREATE_NO_WINDOW`, que da una consola oculta que los hijos heredan.

2. **«Se añadió a la leyenda de símbolos el nombre del agente, y debería ser inmutable.»** Tiene
   razón: la leyenda es el **vocabulario del mapa** (módulo, clase, función, método, import,
   llamada, ciclo) y un vocabulario que se reescribe según quién esté trabajando deja de serlo —
   cada agente que entraba o salía movía de sitio lo estable. Cura: la marca se explica una vez y
   los nombres se quedan en su tarjeta, que es donde significan algo, detrás de un separador que
   marca dónde acaba lo estable y empieza lo efímero. Nota de seguridad: al sacar el nombre del
   HTML, el escape ya no lo hace `html.escape` sino `_en_script` (viaja en el payload JSON de la
   tarjeta) — la protección sigue, cambia la vía, y el test lo fija por la vía nueva.

3. **«Hemos gastado demasiados prompts hasta llegar aquí; esto debería ser más ágil.»** La crítica
   más profunda de la sesión. Ver a un agente trabajar sobre el mapa exigía cinco pasos y un script
   desechable: crear el worktree, escribir un lanzador que teee el stdout a `<worktree>.consola.log`,
   arrancar el watch, encontrar la ruta del mapa, lanzar. Cura: **`python bucle/agente.py "la tarea"`**
   — crea el worktree con nombre derivado de la tarea, asegura el watch, imprime la ruta del mapa,
   teea la consola en vivo y al terminar deja el diff **sin commitear y sin mergear**. Vive en
   `bucle/` porque gb provee y no orquesta (regla 4).

De propina, un falso positivo mío: di por «colgado» al agente tras 3 minutos sin línea nueva en la
consola. No lo estaba — estuvo 5 min 45 s pensando tras leer tres ficheros grandes. Mi lanzador no
guardaba transcript crudo, así que no podía distinguir «pensando» de «tee atascado»; el de `bucle/`
sí imprime en vivo.

## 2026-08-08 · Sonda v2 (el fallo a profundidad 2): la información estaba delante las 3 veces y se usó 1

La v1 salió plana con una crítica válida: el fallo estaba a profundidad 1 y un `grep` lo resolvía, así
que el grafo no podía ganar. La v2 mueve el fallo a **profundidad 2**, donde grep se acaba: `total()`
pasa a incluir IVA y hay **4 consumidores de segundo nivel** que ya lo aplicaban por su cuenta — si
nadie los toca, cobran el IVA dos veces. Validado antes de tirar: el camino perezoso deja `pytest`
**VERDE** y los cuatro cobrando 36,60 € en vez de 30,25. `grep "total"` da 112 líneas;
`gb calls total --depth 2` da los 4 consumidores exactos.

**Ronda 1, espectacular y engañosa:** con grafo → 4/4 correctos y suite verde; sin grafo → los 4
rotos y suite roja. Con cadena causal en el transcript (evento 8: el hook de SessionStart nombra
`contabilidad`, `facturas.envio`, `informes.anual` antes de que el agente tocara nada). **Rondas 2 y
3: no replica.** Ambos brazos fallan. Marcador final **CON 1/3 · SIN 0/3** — no discrimina.

**Y la medida que sí dice algo, porque es intra-brazo y no depende de la comparación:**

| ronda | ¿el mapa le nombró el nivel 2? | ¿lo leyó? | ¿lo arregló? |
|---|---|---|---|
| 1 CON | sí | 4/4 | 4/4 |
| 2 CON | **sí** | 0/4 | 0/4 |
| 3 CON | **sí** | 0/4 | 0/4 |

**El hecho estuvo en su contexto las tres veces y actuó sobre él una.** Eso no es un dato sobre el
grafo: es el mismo dato que el bucle ya había medido desde otro ángulo — **la señal preventiva en
contexto se ignora** (allí 12/12; aquí 2/3) **y lo que corrige es la arista determinista** (allí el
rechazo, 4/4). Dos instrumentos independientes midiendo la misma ley.

**Lo que se lleva el proyecto, y es accionable:** el valor del grafo no se entrega **inyectando
contexto**, se entrega **gateando y rechazando**. `graph --gate` bloquea, `tests` selecciona, el
verificador de adopción rechaza — los tres actúan. `graph --context` sugiere, y sugerir es un lever
débil aunque el hecho sea exacto y esté delante. La forma correcta para el hallazgo de esta sonda no
es "que el mapa lo nombre" sino **"cambiaste la firma de un símbolo con N llamantes transitivos sin
tocarlos" como hecho en el pre-commit**. Eso ya no es un póster: es la regla 11 del proyecto
confirmada por experimento.

**Defecto de método, declarado:** la v1 fue demasiado fácil (los dos brazos aciertan, techo) y la v2
demasiado difícil (los dos fallan 2/3, suelo). Ninguna de las dos cae en la zona que discrimina. La
sonda que lo haría necesita una tarea que el brazo sin ayuda resuelva ~la mitad de las veces, y no
se ha encontrado. n=3 por brazo y por versión.

## 2026-08-08 · La capa ambiental del grafo, medida por fin — **PLANO, y es el negativo más caro del proyecto**

El 71% de gb no lo teclea nadie: 869 `graph --context` + 93 `calls --hook` en 7 días, inyectados por
hooks. Nunca se había medido si eso cambia **lo que el agente escribe**. Sonda A/B de una sola
variable (el grafo entra en contexto o no; `GB_DISABLE=1` en ambos brazos para que la consola no
contamine), 3 rondas por brazo, criterio escrito antes.

**La trampa, validada antes de gastar cuota** (la lección de la báscula, esta vez cumplida): símbolo
objetivo llamado `total` → grep da **92 líneas** de ruido y el grafo **3 llamantes exactos**,
distinguiendo el método homónimo de otra clase; los tests visibles solo cubren el módulo objetivo,
así que el camino perezoso deja **`pytest` VERDE con los 3 llamantes rotos** (medido). Hooks
verificados con centinela en `claude -p` headless: disparan.

**Resultado: 3/3 llamantes actualizados en los SEIS casos. Cero rotos en ambos brazos.**

| brazo | ≥2 llamantes actualizados | media | rotos | búsquedas |
|---|---|---|---|---|
| CON grafo | 3/3 rondas | 3,00 | 0 | 1–2 |
| SIN grafo | 3/3 rondas | 3,00 | 0 | 1–2 |

Los transcripts son casi idénticos: un grep, leer los 3 llamantes, editarlos. **El agente sin grafo
no cayó en la trampa porque no la necesitó** — a esta escala, un grep le basta. La manipulación fue
real (el mapa aparece en el contexto del brazo CON, verificado en el transcript); simplemente no
cambió nada. Nota honesta: `calls --hook` no llegó a inyectar ficha en ninguna ronda — el patrón que
grepeó el agente no parecía un símbolo, así que el hook corrió mudo.

**Lo que esto dice, sin adornarlo:** en una tarea de contrato roto sobre ~20 módulos, la capa
ambiental del grafo **no cambia el resultado ni el coste de descubrimiento**. Es un negativo caro:
es la pieza de mayor volumen de uso del proyecto.

**Lo que NO dice:** que el grafo no sirva. Dice que a esta escala el agente ya es diligente. La
hipótesis que sobrevive es de escala y ambigüedad — repos donde grep deja de escalar (cientos de
módulos, nombres comunes, llamadas por atributo). Con un matiz que hay que decir en contra propia:
gb declara **3.218 `atributo-de-variable` sin resolver** en su propio repo, así que en el caso
dinámico el grafo tampoco ayudaría. Medirlo es la siguiente sonda, no una excusa para esta.

**Y el patrón que ya son tres medidas apuntando al mismo sitio:** el valor demostrado de gb está en
**verificación y contención** (rechazo determinista 4/4, consola 3/3 sobre crashes irreproducibles,
TIA 20–97%, gates de ciclos y fronteras), no en **autoría**. Coincide con el reporte de uso real
—«no es detector primario: red de seguridad + verificación de cierre»— y con la propia filosofía del
póster: *no hacemos al modelo más inteligente*. La sonda de hoy es el dato que faltaba para decirlo
sin fe: **gb no hace que el agente escriba mejor; hace que lo que escriba mal salga caro de colar.**

Límites: n=3 por brazo, un escenario, repo sintético de 20 módulos, un modelo. Mide un mecanismo, no
una media.

## 2026-08-07 · El banco de replay: 13/13 — y el aprendizaje adaptativo, acotado con datos

El póster de arquitectura dibuja un ciclo de *aprendizaje adaptativo* (recolectar → agrupar →
hipótesis → replay → comparar generaciones → consolidar o revertir). Antes de construirlo se miró
qué materia prima existe: **14 actas con sus diffs guardados, 67 infracciones registradas… de 2
escenarios**, y **cero violaciones de frontera vivas** en el repo. Veredicto escrito antes de
teclear: sólo una de las cinco cajas es viable hoy.

- **Viable y construido: el banco de replay** (paso 4). `bucle/replay.py` rehace el árbol que vio
  el verificador desde los diffs grabados y corre **la misma función** de verificación —
  refactorizada para compartir parser (`lineas_de_diff`) e inyectar el mapa de líneas. Cero cuota,
  cero agentes, milisegundos.
- **Aún no: clustering → hipótesis** (pasos 1-3). Con un solo patrón repetido 67 veces, la máquina
  propondría exactamente lo que ya se descubrió a mano el 5-ago. Se abre cuando el corpus tenga
  variedad, y la variedad la trae el uso.
- **Nunca así: generaciones del grafo con rollback** (pasos 5-6). Versionar Gn/Gn+1 implica
  persistir el grafo como fuente de verdad — lo que VISION.md prohíbe desde que se borró GitNexus.
  La corrección que sale de la propia ley: **lo aprendible no es el grafo, es el ruleset** (las
  fronteras y los checks son declarados, y eso sí se versiona). El grafo se sigue derivando.

**Criterio, escrito antes: reproducir el veredicto grabado en ≥13 de 14, y que un verificador roto
falle ruidosamente. Resultado: 13/13 de los casos con verdad de campo** (2 de ellos controles
positivos con final sucio: cazarlos de menos sería falso negativo; los 11 limpios, falso positivo),
**+ prueba de mutación en verde** — cegar `firma_admite` pone el banco rojo. Un banco que no puede
fallar no mide nada.

Tres cosas que el banco descubrió sobre sí mismo mientras se construía, todas reales: (1) la verdad
de campo **no** son las infracciones del acta — el acta anota las del primer intento y el diff
guardado es el estado final tras el rechazo; se deriva de los pasos; (2) el acta v0 del 5-ago no
tiene verdad de campo, y forzarla sería inventar un veredicto: se clasifica aparte, y ahí el replay
demuestra algo mejor — **el verificador de hoy habría cazado las 4 llamadas que aquella tirada dejó
pasar**; (3) reconstruir desde el blob post-imagen es una lotería (`git add -N` no escribe el
objeto): se rehace desde el pre-blob commiteado + `git apply`. Y una trampa de entorno: `bucle/` no
es paquete, así que bajo pytest `import bucle` cae en un namespace package y el módulo real nunca
llega — carga por ruta, y el test comparte instancia para que la mutación alcance al código que
corre.

## 2026-08-07 · El sello «+sin-commitear» con árbol limpio, RESUELTO — y no era el EOL: era Heisenberg

El reporte confirmó la reproducción con datos de campaña (`git ls-files --eol`: 91 ficheros i/lf
w/crlf, porcelain vacío) e hipotetizó EOL. La pista era real como estado del repo pero **no era la
causa**: `_procedencia` ya pregunta a `git status --porcelain` — el camino correcto — y el sucio
era NUESTRO. El `with open(destino + .tmp)` se abría ANTES de evaluar el render que computa el
sello, así que cuando el sello preguntaba a git, el propio temporal del mapa ya existía como
untracked (y `mapa.html.tmp-<pid>` no casa con la línea `mapa.html` del ignore). **El sello se
ensuciaba a sí mismo al medir.** Explica las tres reproducciones: todas durante una regeneración.

Cura: renderizar ANTES de abrir el temporal, en los tres sitios que escriben el mapa. Verificado en
limpio con espía sobre `_git` (porcelain vacío en las tres sondas, sello sin `+`). Doble ración de
Heisenberg durante la caza: el primer espía se metió DENTRO del repo y se delató a sí mismo como
`?? espia.py`; y el primer test acusaba a un mapa limpio porque `sin-commitear` (sin el `+`)
también vive en un comentario JS del template.

Y la segunda mitad del reporte, curada aparte: `floor --init` añadía líneas LF a un `.gitignore`
CRLF (w/mixed) — el olfato del EOL va ahora en bytes (leer en texto traduce los `\r\n` antes de
poder verlos, la trampa dentro de la trampa) y `newline=""` al escribir: el EOL lo decide el
fichero, no la plataforma.

## 2026-08-07 · El balance de una sesión real completa — qué es gb cuando se usa de verdad

Reporte íntegro de la sesión del otro repo (sin tocar gb). **Dónde ayudó, medido:** (1) el mapa
señaló el problema que abrió la sesión (los módulos sueltos destaparon los artefactos de pytest y,
de rebote, el bug del .gitignore del propio gb); (2) el embudo de `gb list` fue el plan de trabajo
— el aviso de arranque dio la primera tarea y cada firma (fichero:línea, conteo, antigüedad) fue un
repro concreto para verificar el cierre de 5 barridos: «está arreglado, medido» en vez de «creo»;
(3) `gb show` con locales diagnosticó el OSError del pipe sin repro manual; (4) las fronteras
hicieron VERIFICABLE un diseño (19 reglas nuevas, 203→222, vigiladas por el gate en cada commit);
(5) el pre-commit compuesto bloqueó de facto commitear roto un refactor de 16 ficheros, y la onda
(«14 símbolos, max 14 llamantes») dio un resumen de blast-radius que antes no existía.

**Dónde NO ayudó, y es identidad, no fallo:** los bugs nuevos del día no los encontró gb — salieron
de barrido activo. gb documenta crashes que ocurren y verifica cierres; no encuentra lo que aún no
ha ocurrido. Es la regla 2 (reporta hechos, no juzga): el detector proactivo de clases de error es
otra herramienta y se integra por referencia (ast-grep/semgrep, capas ortogonales). La frase del
reporte que resume el producto: **«yo barro, él captura y los gates sellan — commits con evidencia
en vez de commits con fe».**

**Fricción reportada y curada en el acto:** «mapa.html baila en el worktree cada 3 segundos» — gb
escribía el artefacto derivado sin excluirlo de git. `floor --init` garantiza ahora la línea
`mapa.html` en el `.gitignore` (aditiva, idempotente, jamás pisa; una ruta distinta que contiene el
nombre no cuenta como cubierta). En repos donde ya está trackeado hace falta además el
`git rm --cached mapa.html` — decisión de cada repo. **Pendiente anotado:** el sello
`+sin-commitear` con árbol limpio (hipótesis EOL/autocrlf; ese repo no tiene `.gitattributes`) — se
verifica allí antes de tocar nada aquí.

## 2026-08-07 · La consola se capturó a sí misma — y el criterio de la familia se completa: 3/3

`emit()` reventaba con `OSError [Errno 22]` cuando el consumidor del pipe cerraba antes
(`gb ... | head`): en Windows la tubería rota no es `BrokenPipeError` sino `OSError(EINVAL)`, y el
except solo cubría Unicode. **gb capturó su propio crash** en el otro repo, el aviso viajó en el
feedback, y el fix salió de `gb show 20260807T024900-efcedd`: los locales traían el stream, el
`text=''` y el errno exactos — **cero reproducciones, causa a la vista**. Es el tercer fallo real
resuelto leyendo el estado sin re-ejecutar: el criterio «resolver ≥3 fallos leyendo el estado» pasa
de 2/3 a **3/3**, y este ni siquiera fue dirigido — fue la herramienta pagándose a sí misma.

Cura con la lección de frontera del propio feedback («cargar tenía diez llamantes»): la clase
entera, no la ruta — `emit()` y `emit_utf8()` comparten `_es_tuberia_rota` (EPIPE + EINVAL) y
`_apagar_stdout` (devnull, que además evita el «Exception ignored» del flush al salir). Un OSError
que NO sea tubería (disco lleno) se sigue viendo: tragárselo sería mentir en verde. Test de ambos
lados.

De propina, la captura destapó un roce más: `gb show <id>` desde otro cwd decía «no encuentro» —
el scope por proyecto negaba un id **globalmente único** a quien lo tenía en la mano. Ahora, si no
está en el proyecto actual, se entrega global (la ficha ya dice de quién es).

## 2026-08-07 · Feedback de uso real (3ª ronda): el grafo indexaba lo que el .gitignore excluye

El otro repo tenía `pytest-of-*/` y `tmp*/` en su `.gitignore` (git los marcaba `!!` correctamente)
y el grafo los indexó igual: módulos sueltos «sin describir, sin llamadas ni imports», conteo
inflado (56) y mapa desincronizado en cuanto pytest rotaba sus temporales. Es la regla 6 aplicada al
propio escáner: la lista de ruido cableada (`__pycache__`, `.venv`…) es folklore; el `.gitignore`
del proyecto es el **hecho declarado**, y gb no lo leía.

Cura en el único walker (`_iter_py_files`, que alimenta a graph Y symbols): `git ls-files -co
--exclude-standard -z` — trackeados + nuevos sin trackear, MENOS lo ignorado. El matiz que hace mal
el `git ls-files` a secas que proponía el reporte: **lo nuevo sin trackear DEBE verse** (la capa de
obra y la actividad viven de ello); lo que sobra es solo lo ignorado. `-z` para que el quoting de
git no esconda rutas con acentos (la trampa cp1252, prima de la del 5-ago). Sin git no hay hecho que
leer: cinturón cableado como siempre, y se indexa todo. Un subprocess por analyze (~30 ms, en
presupuesto); el tick del watch no pasa por aquí.

## 2026-08-07 · «Fracaso absoluto»: el grafo desplegado y CERO actividad visible — el mapa no tenía pulso

Feedback de uso real, segunda ronda del otro repo: una sesión entera de trabajo de verdad (barrido
de CLI, 3 bugs reales, 6 commits) con el mapa abierto — y la capa de actividad a cero todo el rato.
El panel encima mentía: «aparecerán en cuanto un agente toque el árbol», y el agente tocó el árbol
toda la noche.

Diagnóstico, y no es el de anoche: la actividad **ya sabía** pintar la sesión directa (el árbol
principal con cambios sin commitear cuenta como agente en `instantanea`), y los eventos se derivan
comparando instantáneas entre recargas. Lo que no hubo fue **pulso**: nadie lanzó un watch en ese
repo, el mapa se regeneró UNA vez al final (todo ya commiteado → 0 obra, 0 agentes, 0 eventos, por
definición), y el HTML abierto recargaba un fichero que nadie refrescaba. La ironía: `--fondo`
existía exactamente para esto — su docstring dice «para el hook de SessionStart» — y nunca se
cableó en la plantilla del arnés.

Cura: (1) `floor --init` añade al arnés de proyecto el hook de SessionStart
`gb symbols --html --watch --fondo --refresco 3` — vuelve al instante, el candado evita duplicados
entre sesiones, borrar el mapa lo apaga, y con la convención nueva escribe LA referencia de la
raíz: **mapa vivo de serie en cualquier repo con arnés, sin acordarse de nada**; (2) el texto del
panel vacío deja de mentir: dice que hacen falta DOS cosas — trabajo en el árbol Y el mapa
latiendo. Límite honesto: `--init` nunca pisa un settings existente, así que los repos ya
scaffoldeados (el del feedback) tienen que añadir el hook a mano o re-init sin settings.

## 2026-08-07 · Feedback de uso real (otro repo): dos puertas al mismo mapa fabrican dos mapas

En el arranque en frío sobre otro proyecto, la sesión de allí generó `grafo-modulos.html` con
`gb graph --html` y `grafo-simbolos.html` con `gb symbols --html` — 153.957 y 153.958 bytes: **el
mismo lienzo unificado, un byte de diferencia (el sello GEN_TS)**. Desde la unificación, los dos
comandos renderizan EL mapa; dos destinos son dos copias que envejecen por separado. El agente de
allí mordió el anzuelo entero («regenero el de símbolos con el comando correcto») pese a que ambos
títulos decían `mapa · src`. Tercer fichero en escena: un `mapa.html` del 2-ago, obsoleto,
confundiendo — el pie con procedencia existe justo para eso, pero solo si alguien lo abre.

Lo positivo del mismo episodio: el frío funcionó — gb pintó 20 módulos de un repo ajeno sin
configurar nada, rápido y sin errores.

**Propuesta (pendiente de decisión):** al escribir `--html`, decir en la salida que es EL mapa
unificado (p. ej. «el mismo lienzo que produce gb graph/symbols --html: un fichero por proyecto
evita copias que envejecen»), y valorar si `graph --html` y `symbols --html` deben seguir siendo
dos puertas. No se cablea nada por repo (regla 6): es cuestión de qué dice la herramienta, no de
adivinar rutas.

## 2026-08-07 · La sonda del caso caro: la consola CUMPLE su promesa — y el aviso se adopta solo

La mitad no demostrada del proyecto era la promesa fundacional: «te dice dónde y con qué estado,
sin reproducir». Sonda A/B dirigida, con el caso construido para ser IMPOSIBLE de reproducir, no
solo caro: un consolidador muere procesando un stream efímero (el productor ya no existe, los
eventos no se persisten); la causa es un evento de esquema v2 (`importe_eur` en vez de `importe`)
que mete `None` en el saldo; el `TypeError` estalla lejos de la causa y **no contiene el valor** —
el evento culpable solo vive en los locales capturados. Dos brazos idénticos; en B el crash ocurrió
con la captura apagada (queda el traceback en un log), en G capturado. El prompt NO menciona gb en
ninguno: la única diferencia del mundo de G es la línea del aviso al final del crash.log. Corrector
oculto fuera del alcance; criterio escrito antes.

**Primer intento INVALIDADO, y se cuenta:** dejé la clave de corrección en un directorio hermano y
el primer agente-B se salió del «trabaja SOLO aquí», la encontró y entregó el asesino exacto que no
podía conocer. Doble lección: la trampa se sella antes de fiarse de la lectura (la báscula, otra
vez), y **el agente desobedece el límite de directorio a la primera** — dato de harness por sí
solo. Reconstruida estanca: semilla solo en conversación, respuesta fuera de todo disco,
transcript stream-json para auditar lecturas.

**Resultado (n=1 por brazo, se dice):**

| | B2 (sin estado) | G (con la captura) |
|---|---|---|
| siguió el aviso del crash | — | **sí, espontáneo** (`gb show <id>`, sin que nadie le hablara de gb) |
| fix mínimo (no peta) | sí | sí |
| fix COMPLETO (v2 se suma, el requisito) | **no** — descartó los v2 con un WARN, justo lo prohibido | **sí** |
| diagnóstico del evento asesino | «usuario: valor desconocido» | **exacto: id 149, fede, ajuste, v2, 62,50 €** (verificado contra la semilla) |
| reproducciones | 1 (el crash original; nada que reproducir) | **0** |

Auditoría de transcripts: los dos agentes trabajaron estancos; B2 dedujo todo lo deducible del
traceback y no pudo más — la información no existía en su mundo. G convirtió el estado en el fix
que el requisito pedía y en la identidad exacta del evento, sin ejecutar nada.

**Lectura:** el mecanismo completo de la consola queda demostrado en su caso de valor — captura →
aviso → adopción espontánea → estado → fix imposible de otro modo. El criterio de la familia
(«resolver ≥3 fallos leyendo el estado sin re-ejecutar») pasa de 1/3 a **2/3**, con la honestidad
de siempre: esto es dirigido (el escenario lo construimos), n=1, y la adopción espontánea *en la
vida real* sigue midiéndose con el termómetro, no con sondas. Lo que la sonda cierra es la duda de
mecanismo: cuando el caso caro llegue, la consola paga.

## 2026-08-06 · «No veo la actividad de los bucles» — el watch era ciego a los agentes

Reportado por Marcos mirando el mapa en vivo durante las tandas: tres tandas enteras del bucle (8
tiradas) y el lienzo mudo. Dos causas apiladas: la sonda del watch solo vigilaba los `.py` del
proyecto — y los agentes trabajan en OTRO árbol (`.claude/worktrees/`), así que ni sus worktrees ni
sus consolas disparaban regeneración — y aunque hubiera disparado, el guard de forma-igual se comía
la escritura porque **la actividad no es forma**. Doble lección del mismo tipo que los anillos
viejos del 4-ago: cada capa nueva del mapa necesita su fuente en la sonda, o el watch la sirve
congelada.

Cura: `_firma_actividad` (stat de las entradas de `.claude/worktrees/`: worktrees y consolas que
crecen línea a línea — el tick sigue sin pagar subprocesos) en la sonda, y el cambio de actividad
fuerza la escritura aunque la forma no haya cambiado. Verificado en vivo con una tirada real antes
de la cura vía regenerador puente (la actividad se pintó) y con test de la firma después.

## 2026-08-06 · La 5ª rebanada: lo que prima es el MARCO, no los hechos — 4/4 con una frase fija

La 4ª dejó un confundido: `--sin-senal` quitó a la vez los hechos derivados Y el marco del desfase
(«tu árbol puede estar desfasado»), así que no se sabía cuál de los dos hacía obedecible el rechazo.
Este brazo (`--aviso-desfase`) despacha SOLO el marco — una frase fija, sin derivar nada: «hay otros
worktrees en vuelo que pueden cambiar contratos que tu árbol todavía no ve; que tu pytest local
salga verde no lo descarta» — y reserva los hechos al rechazo. Criterio pre-escrito: ≥3/4 corrige →
prima el marco; ≤2/4 → priman los hechos.

**Resultado: 4/4 corrigió, 4/4 uniones verdes.** La tabla de los tres brazos (12 tiradas con dato):

| brazo del despacho              | B infringe | rechazo corrige |
|---------------------------------|-----------|-----------------|
| señal completa (hechos + marco) | 4/4       | 4/4             |
| nada (4ª rebanada)              | 4/4       | 2/4             |
| solo el marco (5ª)              | 4/4       | **4/4**         |

Tres cosas quedan medidas de una vez:

1. **Nada previene la infracción** (12/12): B escribe contra lo que ve en su árbol, reciba lo que
   reciba. La prevención por despacho es una ilusión en los tres brazos.
2. **El marco compra la autoridad del rechazo** — y los hechos derivados en el despacho no añaden
   nada medible sobre el marco solo (4/4 = 4/4). El mecanismo entendido en la 4ª se confirma: el
   rechazo corrige cuando no contradice de primeras lo que el agente observa.
3. **Los hechos son insustituibles donde siempre lo fueron: en el rechazo** (las llamadas exactas
   con fichero:línea). Derivar sigue siendo obligatorio — para verificar y rechazar — pero no hace
   falta gastarlo en el despacho.

Honestidad estadística: n=4 por brazo; marco+señal juntos 8/8 contra 2/4 del brazo desnudo sigue
sin cruzar significancia clásica (~0,09 una cola). Es coherente, replicado en dos brazos y con
mecanismo — pero si algún día importa de verdad, se compra con n, no con prosa.

Consecuencia — DECIDIDA por Marcos la misma noche («gíralo si lo ves necesario») y girada: el
despacho por defecto lleva el AVISO fijo y reserva los hechos al rechazo — mismo efecto medido y un
prompt más corto; la derivación sigue igual (la necesita la verificación). La señal completa queda
tras `--senal-completa`, el brazo desnudo tras `--sin-senal`, y los tres modos son excluyentes: la
norma va en el defecto, desviarse cuesta una bandera.

## 2026-08-06 · La 4ª rebanada: ¿sobra la señal preventiva? — NO, y el porqué es mejor que la pregunta

Hipótesis (del dataset de 5 tiradas): la señal preventiva va ignorada 4/4 y el rechazo corrige 4/4 —
si el rechazo basta, la señal es coste sin efecto. Criterio escrito ANTES de la primera tirada:
4 tiradas reales con `--sin-senal` (derivar y verificar igual, despachar sin señal; los hechos van
solo en el rechazo); si el rechazo corrige ≥3/4, la señal sale del despacho por defecto.

Resultado (actas 20:21–20:47): infracción 4/4 —como con señal— pero **el rechazo solo corrigió
2/4**. En las dos tiradas fallidas, B mantuvo sus llamadas contra la firma vieja **después** de un
rechazo que traía los hechos retenidos Y las llamadas exactas; la unión salió roja y la red aguantó
(nunca se mergea). Con señal: corrección 4/4 (4 con dato).

**Lectura, y es el hallazgo:** la señal no se obedece al escribir (4/4 ignorada en los dos brazos),
pero **prima la corrección** — un rechazo que confirma algo ya visto corrige siempre; un rechazo que
es la primera noticia corrige la mitad de las veces. La señal no es una orden que fracasa: es el
contexto que hace obedecible el rechazo. Se queda en el despacho por defecto.

Honestidad estadística: n=4 por brazo; 4/4 contra 2/4 no separa con significancia (Fisher ~0,43).
El criterio pre-escrito decide igual —2/4 < 3/4— y decide en la dirección conservadora. Si algún
día se reabre, hacen falta más tiradas, no más opinión.

De propina, el dato que faltaba del punto 3 de la lista de refinado: **los dos primeros B que
ignoran también el rechazo** (antes 1/1 corregía). La contención funcionó las dos veces: unión roja,
sin merge, acta con las infracciones exactas.

## 2026-08-06 · Por qué no se lee la consola — la investigación del 13/55 (regla 10)

El termómetro decía «capturas leídas: 13 de 55» y la obligación era investigar, no blindar. Cruzado
el histórico completo (`index.jsonl`) con la libreta de lecturas (`leidas.jsonl`) y los commits de
intervención:

- **El 78% del histórico no es código de ningún proyecto**: 30 efímeras (`python -c`/stdin de
  exploración de agentes) + 13 de scripts de scratchpad + 2 sueltas. No leerlas es correcto — no hay
  nada que leer. El denominador 55 infla la sensación de abandono.
- **Las 6 capturas de código propio de gb: 6/6 arregladas SIN leerlas.** Las seis se leyeron por
  primera vez el 6-ago a las 17:51 — un triaje post-hoc, días después de que los commits ya las
  hubieran curado. El patrón es idéntico en las seis: crash delante del que lo provocó (sesión de
  desarrollo en vivo), traceback ya impreso en el terminal, causa obvia (`NameError` de función aún
  no escrita), reproducir gratis. **El valor diferencial de la consola —los locales, el estado— no
  compite contra un traceback que ya tienes delante.**
- **Las 4 de guardia (otro repo): 0 leídas.** Este sí es el caso con pinta de valor (el crash lejos
  de la sesión que lo mira) y también quedó sin leer — pero desde aquí no se opera ese repo; queda
  como dato para cuando se abra.

**Diagnóstico:** no es abandono de la herramienta; es que en 7 días no ocurrió ni una vez el caso
para el que la consola existe — un crash **caro de reproducir** (watch nocturno, servidor, estado
complejo, otra sesión). Los crashes del flujo real (desarrollo interactivo con agentes) son baratos:
el terminal ya da el traceback y el fix es inmediato. La promesa «sin reproducir a mano» solo paga
cuando reproducir cuesta.

**Consecuencia (devolver, no blindar):** el termómetro mezclaba exploración con producto — `gb
status` pasa a separar el denominador (leídas en código de proyecto vs exploración), para que la
métrica lea señal y no ruido. Ningún aviso nuevo, ningún hook: si el caso caro no ocurre, la
consola no se empuja — se espera, y esta entrada es el registro de la espera.

## 2026-08-04 · La consciencia del LLM deja de ser artesanía — **el arnés viaja con el repo**

Pregunta de Marcos: ¿es el LLM consciente de gb frente a un usuario nuevo? Auditados los canales:
el aviso de captura (gratis, en el stderr del crash) y el AGENTS.md de `--init` funcionaban para
cualquiera; **los tres hooks del grafo** (mapa de sesión, delta por edición, fichas en búsqueda)
eran artesanía del settings global de UNA máquina — el usuario nuevo instalaba, capturaba… y su
agente nunca veía el mapa. El modelo no sabe que gb existe; lo sabe su contexto, y el contexto no
se cableaba solo.

Arreglado: `floor --init` deja también `.claude/settings.json` **a nivel de proyecto** — viaja con
el repo, mergea con lo global de cada máquina, nunca pisa uno existente. Verificado en sandbox
limpio: las 7 piezas creadas y los tres comandos del arnés respondiendo en frío (el mapa, el delta
y `motor.suma(a, b=0)` con firma desde el hook piped). **Pendiente, y es el criterio:** la primera
sesión fresca de agente en un repo scaffoldeado donde los hooks disparen solos — se apunta aquí
cuando ocurra.

## 2026-08-04 · El agente usa el grafo sobre este repo — **la primera prueba de uso dirigida, con su negativo afinado en caliente**

Sesión real con Claude usando el grafo como manda CLAUDE.md, a petición de Marcos. Aviso previo de
honestidad: uso **dirigido**, no espontáneo — así que la pista fuerte no es "lo usó" sino si ahorró
pasos y si mintió. Tres pruebas:

- **Consulta elegida con pregunta desconocida** ("¿quién usa `store.read_index`?"): `gb calls
  read_index --depth 2` → 56 llamantes (5 de src, 51 de tests) con fichero:línea, onda de nivel 2 y
  los 3 llamados, en un comando. **Verificado contra grep en vivo: 5/5 llamantes de src exactos —
  el grafo no mintió.** El camino de siempre habría sido ~6 búsquedas más mapear a mano cada línea a
  su función; grep además no da ni el nivel 2 ni distingue src de tests. Ahorro real y medible.
- **El ancla sobre una captura real de hace 3 días** (`NameError` en `graph.py:967`,
  `20260731T222603-1225ce`): **CALLÓ** — y ese silencio era mentira por omisión: la línea ya no cae
  en ningún símbolo porque el fichero cambió después de la captura. El ancla resolvía contra el
  código de HOY sin decirlo; en el peor caso habría podido apuntar al def equivocado que hoy ocupa
  esa línea. **Afinado en la misma sesión** (`05bab0d`): con el mismo hecho de git del ciclo del
  error, ahora avisa ("el fichero cambió después de la captura, commit X — el ancla apunta al código
  de HOY") o explica su silencio con el commit exacto. El negativo valió más que los positivos.
- **Primera lectura real de la consola en este repo**: la captura se leyó de verdad (el embudo
  avanza), pero el fallo original ya estaba arreglado hace días — la lectura sirvió para afinar la
  herramienta, no para resolver el fallo. El criterio de SCOPE (resolver fallos leyendo) **sigue
  1/3**: no se infla con esto.

Ronda 2, tras el push:

- **El "ojo" era necesario, demostrado con el peor caso posible**: la captura `AttributeError` de
  hace 3 días (`cli.py:269`) ancla HOY en `_ficheros_tocados` — una función que **nació 3 días
  después del crash**. Sin el aviso, el ancla habría señalado con toda seguridad a un culpable que
  no existía cuando ocurrió el fallo; con `ojo: el fichero cambió después de la captura (05bab0d)`,
  el lector sabe cuánto fiarse.
- **Ambigüedad sin fantasmas**: `gb calls _run` lista los `_run` de los tests cada uno con lo suyo,
  y `companions._run` (borrado el día anterior) no aparece: el grafo describe el código de hoy.
- **Segundo negativo cazado y afinado en la misma sesión**: la sonda del watch solo miraba `.py` —
  leer capturas dejó los anillos del ciclo viejos en el mapa (regenerado 12:13:56, lecturas
  12:19:37). Afinado: la sonda hace stat también del histórico, las lecturas y el git local, así
  que leer una captura o commitear regenera el mapa solo (verificado en vivo: 12:21:19), y de paso
  los halos de obra se apagan al commitear sin esperar al siguiente edit.

Y la pregunta de completitud ("¿es esto lo que el LLM necesita?"), respondida por el propio LLM con
su sesión delante: la estructura y la historia estaban completas; lo que faltaba era **la firma** —
cinco lecturas de fichero en un día solo para ver parámetros. Añadida (`f671303`): la ficha dice
`parse_ts(value)` (args, defaults, `/`, `*`, async, decoradores que cambian la llamada — AST puro),
y todas las cuentas separan src de tests ("7 llamantes" → "6 de src, 1 de tests": los tests son la
red, no la onda). **Criterio pendiente para la próxima sesión orgánica:** escribir una llamada
correcta a una función no leída, solo con la ficha delante.

Pista fuerte que deja la sesión: el grafo **ahorra y no miente** cuando se le pregunta — y las dos
mentiras por omisión que tenía (ancla sin aviso de código movido, mapa con capas viejas) las destapó
el uso en una tarde y se afinaron en caliente. La consola sigue esperando su caso natural — el
crash asíncrono o lejano, donde leer el estado gana a re-ejecutar.

## 2026-08-04 · guardia-mvp: el primer producto de fuera sobre el pipeline de gb — **y el embudo honesto de su desarrollo**

Marcos señala que la adopción sí se probó: live code se desarrolló con gb y el resultado es
[guardia-mvp](https://github.com/Llicklair/guardia-mvp) (público, 42 commits). Verificado contra el
repo y contra el histórico local — y el dato parte en dos mitades que no se parecen:

- **La familia graph/gate tiene adopción real y estructural.** El About de guardia declara "sobre el
  pipeline de galaxy-brain"; su `check.sh` corre `gb graph src --gate`, y sus fronteras de seguridad
  viven en un `src/.gb-boundaries` propio: el evaluador no puede importar crisol/despliegue/aplicador,
  y el generador de ataques no ve la gramática. **El gate de gb es quien hace cumplir el
  generador ≠ evaluador (H2) de otro producto**, con 254 tests al otro lado. Esto no es "gb estaba
  instalado": es gb como pieza estructural del diseño de seguridad de un segundo repo.
- **La consola capturó, pero nadie leyó.** Embudo de live code (31-jul → 2-ago): 3 firmas / 6
  capturas (SyntaxError ×2, AttributeError ×2, FileNotFoundError ×2), **0 leídas**, 1 intervenida,
  1 en silencio. Los fallos se arreglaron sin `gb show`: la promesa central de la consola no se
  ejercitó, y el criterio de SCOPE (≥3 fallos resueltos leyendo el estado) **sigue en 1/3** — este
  dato no lo avanza. Se apunta como manda la regla 10: el no-uso es dato, no se maquilla.
- **La libreta de usos** (existe desde el 3-ago, así que no cubre el desarrollo de live code):
  113 `graph --context` (auto), 23 `--gate`, 17 `check`, 19 `calls --hook` (casi todo pruebas
  manuales del propio desarrollo de hoy, aún no uso orgánico), 4 `show`, 3 `calls` elegidos.

Lectura conjunta: la adopción de gb no es un sí/no — el gate ya vive cableado en el CI de otro
producto, y la consola sigue sin su primera lectura real. El termómetro distingue familias, que es
exactamente su trabajo.

## 2026-08-04 · GitNexus fuera; `gb calls` ocupa su sitio — **la consulta puntual, ahora del grafo propio**

Decisión de Marcos: borrar todo rastro de GitNexus (npm global, índices, hook, MCP, skills y el
companion — `864af90`) y convertir el grafo propio en la columna. La primera pieza es `gb calls`
(`4b5f8c1`): llamantes y llamados de un símbolo con fichero:línea sobre el índice de `symbols`
(que ahora guarda fichero y línea por nodo), `--depth N` para la onda, y un modo `--hook` que da el
mismo servicio que daba el PreToolUse de GitNexus — símbolos relacionados con lo que se busca —
pero determinista, sin dependencias y callado cuando no hay coincidencias.

- **Medido en este repo** (49 módulos): 526 ms el comando. El hook midió "180 ms" que eran **mudez,
  no velocidad**: PowerShell 5.1 pipa con BOM, `json.loads` lo rechazaba y el hook callaba por
  contrato — un silencio con causa evitable, indistinguible de "no había nada". Lo delató que 180 ms
  es menos que el propio analyze; la cifra buena hay que dudarla igual que la mala. Arreglado con el
  `_BOM` que graph/symbols ya usaban (`95d3ff9`); medición honesta: **430 ms aquí, 330 ms sobre 600
  módulos sintéticos** (3.000 nodos, 4.199 aristas). El frío de primer toque (AV de Windows) fue
  7,6 s una sola vez; la consulta sobre un informe ya construido, 2,4 ms — todo el coste es el parse.
- De regalo, el ciclo del error en vivo durante el propio desarrollo: el crash del debug
  (JSONDecodeError del BOM) lo capturó la consola sola (`gb show 20260804T035450-e18147`) antes de
  ningún print. El primer aviso del bug lo dio la herramienta que lo contiene.
- **Criterio 1 de la fase "grafo como columna", cumplido el mismo día** (`233c975`): `gb last`/`gb
  show` anclan el crash a su nodo — el frame más interno del proyecto → el símbolo que **contiene**
  la línea (`[line, end]` del AST, no "el def más cercano por arriba") → sus llamantes. Demo real
  end-to-end: un KeyError capturado en un proyecto aparte salió como `en el grafo: lib.base ·
  lib.py:5 · le llaman (1): lib.ayuda`. Medido: **158 ms** el `gb show` entero, ancla incluida.
  Fail-safe: sin proyecto, con frame de librería o en línea de módulo, el bloque calla y la ficha
  del crash queda como estaba. Pendiente igual que el hook: la sesión real donde el ancla ahorre
  pasos, apuntada aquí (regla 10).
- Probado sobre un ambiguo real (`gb calls analyze`): devuelve las tres coincidencias con sus 26
  llamantes, cada uno con su sitio. Ambigüedad como material, no como error.
- **Pendiente, y es el criterio de la fase**: que en una sesión de trabajo real la inyección del
  hook ahorre al menos una lectura de fichero. Se anota aquí cuando ocurra — y si no ocurre,
  también: el abandono es dato (regla 10).

## 2026-07-31 · Usar `gb` en OTRO repo mientras se construía este — **tres fallos silenciosos que 283 tests no vieron**

Marcos abrió un proyecto distinto (documentación de un sistema de defensa) y trabajó con `gb` de
verdad: `floor --init`, `graph --gate` como gate de cada tanda, `symbols` para orientar el diseño,
`check` contra HEAD, `.gb-boundaries` como columna del diseño (41 reglas). Cero agentes, cero cuota:
solo lo determinista. En un día salieron tres defectos, y los tres son de la misma familia.

### 1 — Un BOM de UTF-8 borraba ficheros del mapa (`690d430`)

Python compila un `.py` con BOM sin pestañear —lo descarta al decodificar—, pero `ast.parse` sobre el
texto ya decodificado ve un `U+FEFF` y lanza `SyntaxError`. El fichero caía en `errors` y sus imports
desaparecían del grafo. **El caso caro: un ciclo real quedaba oculto y la gate pasaba en verde.** En
Windows no es raro (PowerShell y varios editores escriben BOM por defecto). Apareció al construir un
fixture con `Set-Content -Encoding utf8`, es decir, por accidente y no por buscarlo.

### 2 — La clave del caché dependía de cómo se escribiera la ruta (`240bc4e`)

`os.path.abspath` no unifica la letra de unidad en Windows: `c:\x` y `C:\x` daban claves distintas
para la misma carpeta, y ambas formas circulan de verdad en una sesión. El caché no acertaba nunca,
así que `--if-changed` habría repetido el mapa entero en cada edición — justo el ruido que ese modo
existe para evitar. Apareció al comprobar que el caché tuviera la entrada del propio repo: no estaba.

### 3 — El gate pasaba en verde sin comprobar una sola frontera (`dfbe9ab`)

Reportado desde el uso real. El `.gb-boundaries` estaba en la raíz, se analizaba `src/`, se cargaban
cero reglas y `--gate` salía verde. La causa era **una asimetría de una sola rama**: con reglas se
imprimía "Sin cruces de frontera prohibidos (N regla(s))" y con cero reglas la sección entera
desaparecía. O sea que *"no he mirado"* era indistinguible de *"está limpio"*.

### La lección, y es la más cara del proyecto hasta hoy

**Los tres son fallos silenciosos que se leen como éxito, y ninguno se encuentra escribiendo más
tests.** Un test fija lo que ya sabes comprobar; estos vivían justo en el punto ciego de lo que
sabíamos comprobar. La suite estaba en 262 en verde mientras los tres existían.

Regla operativa que sale de aquí, y que aplica a cualquier salida futura: **si algo puede leerse como
"comprobado y limpio", tiene que decir QUÉ comprobó — también, y sobre todo, cuando la respuesta es
"nada".** El silencio nunca puede ser un veredicto. Es la misma idea que la regla 11 de
[ARCHITECTURE.md](../ARCHITECTURE.md) aplicada al revés: no basta con que la señal salga siempre,
hace falta que la AUSENCIA de señal no se pueda confundir con una señal buena.

Consecuencia práctica: el termómetro honesto del proyecto sigue siendo **usarlo**, no ampliarlo.

---

## 2026-07-30 · Fase A (correlación) — **NEGATIVO en el caso principal**

**Qué se probó.** Si el estado capturado sirve para resolver un fallo sin volver a ejecutar el
programa. Montaje realista: agregación de facturas para un cierre mensual, con una línea malformada
(sin `cantidad`) escondida en la factura `F-2026-0042` entre cinco facturas correctas. El traceback
dice *dónde*; lo que hace falta saber es *en qué factura*.

### Resultado 1 — con pytest, no hay captura ninguna

```
$ python -m pytest -q          # el test falla con KeyError: 'cantidad'
$ gb last --since 120s
(sin capturas en los ultimos 120s para este proyecto)
exit=1
```

**Causa:** pytest **atrapa** la excepción del test. Nunca llega a `sys.excepthook`, así que el hook de
galaxy-brain no se ejecuta y no hay nada que guardar. **El fallo más común del bucle de trabajo de un
agente — un test que falla — está fuera de cobertura**, y eso no estaba escrito en ninguna parte
cuando se justificó la Fase A.

### Resultado 2 — y aunque capturara, `pytest -l` ya da más

Salida de `pytest -q -l`, de serie, sin instalar nada:

```
facturas.py:11: in <dictcomp>
    f       = {'id': 'F-2026-0042', 'lineas': [{'cantidad': 1, 'precio': 250.0}, {'precio': 40.0}, ...]}
facturas.py:7:  in total_factura
    factura = {'id': 'F-2026-0042', ...}
facturas.py:4:  in linea_total
    linea   = {'precio': 40.0}
```

Con eso el bug queda identificado entero: factura `F-2026-0042`, segunda línea, falta `cantidad`.

### Resultado 3 — como script sí captura, pero la vista por defecto rinde menos

El mismo bug lanzado como script (sin pytest) sí se captura: el aviso sale con su
`gb show <id>` y `gb last --since 60s` devuelve exit 0. Pero la vista por defecto muestra **solo el
frame más interno**:

```
      linea = {'precio': 40.0}
```

**No dice qué factura.** Ese dato está uno o dos frames más afuera, detrás de `--full`. Sobre
exactamente los mismos datos, `pytest -l` entregó más respuesta útil que `gb last`.

El supuesto de diseño *"se conservan los frames más internos: ahí está el fallo"* acierta en el
**dónde** y falla en el **con qué**: el estado que identifica el caso concreto suele vivir más arriba.

### Consecuencias

1. **La consola se estrecha** a lo que de verdad cubre: excepciones no capturadas (scripts, CLIs,
   servidores, procesos largos). No tests.
2. **Para tests se adopta `pytest -l` por referencia**, no se construye nada. Es la regla 7 de
   [CLAUDE.md](../CLAUDE.md) aplicada al pie de la letra: lo externo se integra por referencia. Coste:
   una línea. Construir una captura para pytest habría sido reimplementar un flag que ya existe — la
   sobreingeniería exacta que este proyecto dice combatir.
3. **Queda abierto, sin tocar:** si `gb last` debería mostrar por defecto también los locales del
   frame más externo que sea del usuario. Es un cambio sugerido por evidencia, pero antes de pulir
   toca preguntar qué se resta.

**Coste de la prueba:** cinco minutos. **Lo que ahorró:** cinco sesiones midiendo un criterio que
medía el caso equivocado.

---

## 2026-07-30 · `gb symbols` contra el índice de GitNexus — **93% de recall, y las discrepancias favorecen la honestidad**

Mismo repo, mismo commit, arista a arista (CALLS internas de `src/galaxybrain`,
función→función). GitNexus usa tree-sitter + inferencia; `gb symbols` solo resuelve
hechos sintácticos y cuenta lo que no puede.

**Suyas: 215 · Mías: 222 · Comunes: 200 → recall 93%.**

Las discrepancias, verificadas a mano (muestra, no exhaustivo):

- **Solo suyas (15):** al menos 4 son **falsos positivos de ellos** — su resolutor casó
  `analyze` por nombre con el módulo equivocado (`cmd_check → symbols.analyze` cuando el
  código llama a `changes.analyze`, y autollamadas `analyze→analyze` que no existen).
  Una es un acierto real suyo: `build_parser → common`, función **anidada**, que gb declara
  fuera de alcance. Es la validación empírica de la tesis del módulo: *una arista falsa se
  cree; una ausente y declarada, no.*
- **Solo mías (22):** ganancias reales (alias `from .graph import _git as _git_output`,
  llamadas `modulo.funcion()` vía import) más artefactos del script de comparación
  (paquetes `__init__` mapeados a ruta sintética).

**De la misma sesión, dos datos de la Fase A:** el script de comparación petó 3 veces
(3 excepciones no capturadas, 3 capturas). La primera se resolvió **enteramente desde
`gb show`** sin re-ejecutar (`shell=True` + `.CMD`): **contador (c) 1/3**. La causa raíz
final (gitnexus escribe resultados por **stderr**) exigió correr el comando aparte, porque
`saferepr` trunca el repr de un `CompletedProcess` de 18 KB antes de llegar al stderr —
**límite real de la captura, apuntado**: el estado grande anidado queda fuera del alcance
del `--full`.

---

## 2026-07-30 · Fase B, primera prueba — **`gb check` contra sus propios commits**

En vez de escribir más tests, se corrió `gb check` sobre los diez commits reales de
la sesión. Traía 17 tests en verde. Encontró **cuatro defectos**, tres suyos y uno
heredado de v1.

### Lo que salió bien

- **`f7967dd` → 7 × `TEST_FILE_DELETED`.** Es el commit donde se retiró `eval/`.
  Se borraron siete ficheros de test **y lo único que lo dijo fue el propio
  agente**. Con `gb check` en el pre-commit, esa lista habría salido sola delante
  de quien decide. Eso es *imposible de esconder* funcionando.
- **`115ee8c` → `ASSERT_REMOVED`** (tras el arreglo): nombra la función y la
  aserción exacta que desapareció.

### Los cuatro defectos

1. **Enmascaramiento por aritmética** (el grave). `ASSERT_REMOVED` era un neto por
   fichero: quitar la aserción que fallaba y añadir un test trivial que pasa hacía
   subir el neto y desaparecer la resta. Es la ruta de amaño más obvia después de
   borrar el fichero, y era justo la que se escapaba.
2. **Y el primer arreglo no valía.** Contar por *hunk*, usando la función que git
   pone en la cabecera, seguía tapándolo: git etiqueta el hunk con la función donde
   **empieza**, y en el caso real el borrado y el test nuevo caían en el mismo
   hunk. Solo se vio volviendo a correrlo sobre el commit real — el test sintético
   pasaba. La regla correcta: las aserciones dentro de un test **nuevo** no cuentan
   como sustitución de las quitadas.
3. **Patrón dentro de un docstring.** Marcó su propio docstring, donde
   `@pytest.mark.skip` aparece entre backticks. Vaciar literales de una línea no
   bastaba: las líneas interiores de una cadena triple no llevan comillas. Se
   anclaron los decoradores a principio de línea.
4. **Heredado de v1:** `^\s*assert\s+(True|1)\b` casaba **dentro** de
   `assert 1 == 1`, marcando una comparación legítima como aserción debilitada.

### Estado final

Diez commits: **2 con señal, ambas verdaderas; ocho limpios; cero falsos
positivos.**

### La lección, que ya va por la cuarta vez hoy

Los cuatro defectos aparecieron **corriendo la herramienta sobre trabajo real**,
con la suite en verde en todo momento. Ninguno lo habría encontrado escribiendo más
tests: el defecto 2 es el caso puro, donde el test sintético pasaba y el commit real
fallaba. Escribir tests comprueba lo que ya imaginaste; usarlo te enseña lo que no.

---

## 2026-07-30 · Fase A, segunda prueba — **POSITIVO, y encuentra el caso donde no hay rival**

Tras estrechar el alcance a "excepciones no capturadas", tocaba comprobar si ese alcance nuevo
aguantaba o también era más pequeño de lo dicho. Dos formas de morir que no son un script simple:

**A) Excepción en un hilo, con el proceso principal sobreviviendo.**

```
$ python hilo.py
[galaxy-brain] estado capturado -> gb show 20260730T014616-30ee65
el proceso principal sobrevive, exit 0
```

Capturado, con el nombre del hilo (`· hilo ingesta`). Un fallo que **no mata el proceso** y sale con
código 0 es de los que se pierden enteros: nadie mira, el exit code miente. Queda registrado.

**B) Subproceso que muere y cuyo stderr se traga el padre** — `subprocess.run(..., capture_output=True)`.

```
$ python padre.py
lanzo el hijo...
el hijo murio con exit 1 - y su stderr me lo he tragado
```

El traceback **no existe en ningún sitio**: el padre lo consumió y no lo imprimió. La línea de aviso
tampoco se vio nunca, así que no hay id que copiar. Y aun así:

```
$ gb last --since 120s
KeyError: 'cantidad'
hace 18s · facturas.py:4 · prueba-uso
      linea = {'precio': 40.0}
exit=0
```

**Este es el caso donde galaxy-brain no tiene rival.** No hay pytest que valga (`-l` no aplica), no
hay traceback que leer (se lo tragaron), no hay id que copiar (el aviso murió con el stderr). La
única copia del estado es la que se escribió a disco, y `--since` es la única forma de llegar a ella.

### Lo que corrige de la propuesta de valor

La primera prueba parecía decir *"gb rinde menos que `pytest -l`"*. Con esta segunda, la frase
correcta es otra: **el territorio de gb es exactamente donde la evidencia se destruye sola.** Donde
hay traceback visible, las herramientas de siempre compiten y a veces ganan. Donde el fallo se
traga —subprocesos, hilos, demonios, procesos largos, cron— no compite nadie, porque no queda nada
que leer.

Eso también dice dónde NO invertir: mejorar la vista por defecto para competir con `pytest -l` es
pelear en el terreno del otro. La ventaja está en el terreno donde el otro no aparece.

---

## 2026-07-24 · A/B de la báscula (Harbor) — **el resultado, por fin en el repo**

Se registra hoy, 2026-07-30, al retirar `eval/`. Vivía solo en memoria, que es la deuda que
[SCOPE.md](../SCOPE.md) apuntaba: un proyecto sobre evidencia con la suya fuera del repo.

**Montaje.** Dos brazos sobre tareas idénticas en contenedores Harbor — **A: Claude Code de serie** ·
**B: Claude Code + galaxy-brain (forja)** — juzgados por verificadores objetivos independientes del
brazo. Tareas t1 (json no-dict), t2 (int32 con signo), t5 (gate de ruff), t6 (fuga en error).

**Resultado: las recompensas convergen 8/8.** Los dos brazos resolvieron lo mismo. La disciplina ganó
en **coste y evidencia**, no en **pasa/falla**.

**Las tres honestidades, que importan tanto como el número:**

1. **Es un *fix benchmark*, no de descubrimiento.** Lo dice el propio README del rig: los dos brazos
   reciben el mismo informe de bug, así que la supuesta ventaja de descubrimiento de la forja queda
   excluida **por construcción**. Nunca se midió lo que se quería medir.
2. **Ninguna tarea tenía trampa donde el atajo fuese el camino de menor esfuerzo.** Sin eso los brazos
   no se pueden separar por recompensa: el diseño impedía el resultado que buscaba.
3. **n = 1 por tarea y brazo** (8 ejecuciones de las 18 diseñadas). No demuestra que el arnés estorbe;
   tampoco que sirva, que era la razón de construirlo.

**Lo que se conserva del diseño, aunque el código se vaya:**

- **Verificadores independientes del brazo.** Quien juzga no sabe qué brazo produjo el parche.
- **`test-guard` como post-check universal**, con la métrica que sigue siendo la buena:
  *success WITH gaming is failure* — comprar el verde tocando tests que ya existían es un fallo,
  no un éxito.
- **Tamaño del diff como desempate** cuando el verificador da el mismo resultado.
- **Y la lección negativa, la más cara:** un A/B sin una tarea donde hacer trampa sea *más fácil* que
  hacerlo bien no puede separar disciplina de suerte. Si algún día se mide la Fase B, esa tarea va
  primero, no última.

**Consecuencia:** `eval/` se retira (708 líneas trackeadas). Medía la tesis de v1, que está retirada,
contra un commit fijado de un repo privado que solo corre en Docker en esta máquina. No se volverá a
ejecutar. El conocimiento se queda aquí; el código, no.

---

## 2026-07-30 · Pruebas de uso dirigidas — un stack nuevo y un amaño realista

**`gb floor` sobre un repo Node (stack 2 de 3 del criterio):** detecta `npm test` y
eslint, y en el mapa **dice** "hoy `gb graph` solo lee Python" en vez de callar.
Cero avisos falsos.

**`gb check` contra un amaño realista — NEGATIVO, y arreglado:** romper el
descuento, degradar `assert total(x) == 90.0` a `assert total(x)` y añadir un test
trivial pasó **limpio**: neto 1↔1 y WEAKENER solo cazaba `assert True` literal.
Nueva señal `ASSERT_WEAKENED` (pérdida neta de aserciones *que comparan* con total
estable), con contrapeso. Sexta vez en dos días: la suite estaba verde y el hueco lo
encontró el uso, no un test.

## 15-ago-2026 — La sonda del embudo: capturadas vs leidas (mejora 3 del plan)

La instrumentacion ya existia (`store.mark_read()` en cada `show`/`last`,
regla 10: medir el abandono, no impedirlo). La sonda es la LECTURA de esos
datos, segmentada. Numeros del store real, hoy:

- **148 capturadas, 52 leidas.** Reales 45/100 (45%), efimeras 7/48 (14%) —
  el filtro de efimeros hace su trabajo: lo que se oculta por defecto es
  justo lo que nadie necesita leer.
- **Donde importa, el embudo es sano: live code 19/20 leidas (95%).**
  Cuando muere un proceso de verdad, la ficha se lee casi siempre. Es la
  cifra que valida la consola como producto.
- **El 70% sin leer de galaxy-brain es auto-ruido en rafaga.** Las cuatro
  firmas mas repetidas jamas leidas (24 capturas entre ellas) viven en
  ventanas de 1 a 11 SEGUNDOS: `NameError graph.py:634` son 13 capturas en
  2 segundos (9-ago 20:22:01-03) — los hijos de la estigmergia y el watch
  estrellandose contra fuente de gb a medio editar, que sana al teclazo
  siguiente. No son fallos desatendidos: son duplicados que nadie necesito.

**Candidata que sale de la medicion (para SCOPE, no se implementa aqui):**
colapso de rafagas en captura — misma firma en <60 s se apunta como UNA
captura con contador. Restaria las ~24 fichas de ruido sin perder un solo
hecho; la libreta agrupada ya ensena "13x", el colapso solo evitaria
escribir 13 veces el mismo estado. Se decide en SCOPE.md con esta evidencia.

## 15-ago-2026 — El primer CI multiplataforma (mejora 4 del plan): cuatro verdades por el precio de una

El workflow (suite+ruff+gate en windows, ubuntu 3.12 y el 3.9 que el README
promete) tardo CINCO rondas en ponerse verde, y cada roja fue un hecho que
ningun test local podia dar:

1. **La suite dependia del estado de la maquina**: sin `gb on` no hay .pth y
   todo lo que espera capturas falla. El CI ahora instala y ACTIVA, como un
   usuario real.
2. **`/usr/bin/sg` de Debian es setgroups, no ast-grep**: la deteccion por
   nombre lo daba por bueno y la extraccion devolvia vacio en cualquier
   Linux. Y su gemelo: en WSL el PATH heredado de Windows trae un shim npm
   LLAMADO ast-grep que muere sin node. `binario()` ahora ejecuta y verifica
   — un nombre en el PATH no es una herramienta (regla 7, medida dos veces).
3. **git 2.54 emite `%cI` con sufijo `Z` en UTC y el fromisoformat de
   Python <=3.10 no la traga**: intervencion/cambiado/en-silencio se perdian
   ENTEROS y en silencio en Linux+py viejo con git nuevo. `parse_ts`
   normaliza la Z. El diagnostico exigio sondas en el propio runner (la
   biseccion local no reproducia: WSL y Windows llevan git 2.53) y un
   espejismo — "cualquier companero envenena" era en realidad "algun fixture
   a-c pone TZ no-UTC y hace de antidoto".
4. **La bomba del test patologico no detonaba en 3.9-linux** (el parser come
   20k atributos encadenados sin inmutarse): el menos unario da MemoryError
   en todas las versiones medidas. Una bomba que no detona en todas partes
   no prueba la garantia.

Moraleja repetida tres veces en un dia: lo que el entorno del desarrollador
no puede reproducir, solo una pata DISTINTA lo enseña. El badge "Python >=
3.9" paso de promesa a hecho medido.

## 15-ago-2026 — "¿y si eligieron ruby o c?": cuatro mejoras y un punto ciego de método

La pregunta era si gb rinde igual fuera de Python. Buscando la respuesta
salio algo que cambia la pregunta.

**El hallazgo (mejora 1).** En JS/TS/TSX, `from "./a.js"` dejaba arista y
`from './a.js'` NO dejaba ninguna. Solo cambian las comillas. Y llevaba
meses en verde porque **la sonda de conformidad tambien estaba escrita con
dobles**: el punto ciego era del METODO, no del patron. Cada lenguaje se
validaba con UNA forma sintactica elegida a ojo, asi que una variante
trivial desactivaba una capa entera en silencio y con el banco aprobando.

La cura es la matriz: una forma que el lenguaje considera equivalente se
prueba como equivalente. Al escribirla salieron **13 rojos de 15** solo en
la familia JS (default, namespace, side-effect, `require` de ts,
`import type`, `import()` perezoso, los dos barriles), y al extenderla,
**6 mas** en PHP —que declaraba solo comillas simples, el espejo exacto— y
Lua. Ruby y C pasaron enteros a la primera: su cobertura ya era real.

**La consecuencia (mejora 2).** El gate multilenguaje no habia que
construirlo: el constructor llevaba cableado desde el ADR 0009. Estaba MUDO
— sin aristas de import no hay ciclos ni fronteras, asi que `gb graph
--gate` pasaba en VERDE sobre cualquier repo JS sin comprobar nada. Curados
los patrones: ciclo detectado, cruce de frontera por import y por llamada,
exit 1. Y `gb floor` dejo de afirmar que gb solo lee Python, que era verdad
ayer y hoy es mentira.

**Mejora 3.** El checkpoint corria `python -m pytest` siempre, asi que sobre
un repo JS verificaba la union con la herramienta equivocada. Ahora usa el
comando del proyecto y estrena SIN_VEREDICTO (3): no comprobado no es
fallado. El fallback importa tanto como la deteccion — si los ficheros son
`.py` es pytest y punto, exigir configuracion a repos que hoy funcionan
habria sido una regresion gratis (lo dijeron 9 tests al intentarlo).

**Mejora 4.** Ruby gano su licencia con el procedimiento entero: 4 roturas,
0 fugas, cascada exacta, 50% de ahorro. Y quedo escrito que los ocho
restantes no han fallado nada: **no tienen banco**. Sin banco no hay
medicion, y llamarlo fallo seria la misma cobertura fingida de siempre.

**La leccion transferible:** una sonda que prueba un ejemplar mide el
ejemplar, no la clase. Da igual cuantos lenguajes diga la tabla; lo que
cubres es lo que probaste, con las comillas que escribiste ese dia.
