# El Grafo Neuronal — enrutador y checkpoint para agentes en paralelo

> **Estado:** Diseño, con una tirada medida encima (apartado 9). Sin código todavía.
> **Fecha:** 5 de agosto de 2026
> **Aviso:** la hipótesis central del apartado 2 **no se confirmó** al medirla. El apartado 9 manda
> sobre el 4: el checkpoint está justificado por la medida, el enrutador no.
> **Reemplaza:** la v1 de este mismo documento (misma fecha), descartada. El apartado 0 dice por qué.
> **Encuadre:** cómo `gb` sirve a un orquestador que corre N agentes a la vez sobre un repo, sin
> dejar de ser lo que es: un proveedor de hechos deterministas.

---

## 0. Qué se descartó de la v1, y por qué queda escrito

La v1 proponía `gb disjoint`, `gb activity` y `gb conflict`. Se descartan los tres. Queda escrito
porque un descarte sin motivo se vuelve a proponer en seis meses.

**`disjoint` como garantía de paralelismo seguro — error de categoría.** La v1 afirmaba que
`disjoint: true` daba «garantía total de que no pisarán sus blast-waves». Es falso: la onda se
calcula sobre el código **actual**, y el trabajo del agente es cambiarlo. Añade un import, toca un
config compartido, renombra algo. La disyunción previa no sobrevive a la edición. No se arregla
con más ingeniería — **la colisión no se predice, se observa.**

**`activity` declarado — depende de la honestidad de quien no la tiene.** `gb activity mark` pide
que cada agente anuncie su presencia. En cuanto uno olvida marcar, todo lo construido encima miente
con cara de hecho. Y la presencia es derivable: `mtime`, `git status` y las capturas del store ya
la dan sin que nadie coopere.

**`conflict` — protege contra el fallo que no ocurre.** La colisión física (dos agentes escribiendo
el mismo fichero a la vez) ya la impide el sistema de ficheros cuando cada agente corre en su
worktree, que es como los orquestadores actuales lanzan trabajo en paralelo. El modo de fallo real
es otro, y es el apartado 2.

---

## 1. La ley que gobierna este diseño: derivado sobre declarado

> Cada pieza que **exige que un agente declare algo** es el eslabón débil.
> Cada pieza que **`gb` deriva** es sólida. El trabajo de diseño es empujar todo al lado derivado.

Es la misma ley que ya rige el mapa (el grafo se deriva siempre; persistirlo está prohibido),
aplicada a la coordinación. Un agente que declara puede olvidarse, mentir o morir a medias. Un
hecho derivado del disco y del diff no tiene esos modos de fallo.

Corolario práctico: **este diseño no añade estado persistido nuevo.**

---

## 2. El fallo real de N agentes en paralelo

No es la colisión. Es la **deriva semántica entre ficheros disjuntos**:

- El agente A cambia la firma de `store.append()`. El agente B, en otro fichero, escribe código
  contra la firma vieja. **Nunca tocaron el mismo fichero.** Revienta en el merge.
- Dos agentes arreglan el mismo bug de fondo en dos sitios distintos.
- El refactor de A hace pasar los tests de B por el motivo equivocado.

Los tres son invisibles para cualquier registro de presencia, y los tres son visibles en el grafo
de llamadas **antes de ejecutar nada**. Ahí está la ventaja estructural de `gb`, y la v1 no la usaba.

---

## 3. Por qué la analogía de red neuronal aplica — y dónde deja de aplicar

Lo que hace funcionar a una red neuronal no es que las neuronas «compartan información». Son tres
propiedades:

| Propiedad de la red | ¿Transfiere a agentes? | Traducción |
|---|---|---|
| **Topología fija y conocida** | **Sí** | El cableado es el grafo de llamadas. Quién escucha a quién lo dicen las aristas, no el orquestador. |
| **Señal estrecha y tipada** | **Sí** | No «estoy refactorizando auth», sino `store.append: (x) → (x, *, flush=False)`. Derivado del diff. |
| **Propagación determinista y síncrona** | **No** | Los agentes son asíncronos y estocásticos. |

La tercera es la que no se puede fingir, por dos motivos independientes:

1. **Compartir no es obedecer.** En la red, la señal *determina* la activación siguiente. Aquí la
   señal es texto en un contexto y el receptor es un modelo probabilístico: puede escribir la
   llamada vieja igual. Información en contexto es un consejo, no una restricción.
2. **Nadie interrumpe a nadie.** B lee el estado compartido cuando B decide, no cuando A cambia
   algo. En esa ventana B escribe contra hechos caducados. Compartir **mueve** la carrera, no la
   elimina.

Consecuencia de diseño: la propagación síncrona que no puedes tener **se sustituye por una
verificación determinista en la frontera**. De ahí las dos mecánicas.

---

## 4. Las mecánicas

### A. El enrutador — la señal, por las aristas del grafo

Dado un diff, producir hechos tipados y entregarlos **solo a quien cuelga de la arista afectada**:

```
store.append: (entry) → (entry, *, flush=False)
  llamantes fuera del diff:  cli.py:412 · watch.py:88
```

Que sea estrecho no es estética: es lo que evita que 4 agentes compartiendo se coman el contexto
entre ellos. Cada agente recibe el fan-in de sus nodos, no la cháchara de los otros tres.

> **MEDIDO (5-ago-2026, tarde) — el enrutador queda JUSTIFICADO.** Evidencia fabricada sobre el
> banco desechable `experimento/`: A rompió la firma de `nucleo.calcula` («(a, b) → (a, b, base)»,
> obligatorio, sin default — invisible para la suite entera: 552 verdes con el contrato roto), y
> dos agentes B idénticos escribieron llamadas directas nuevas. El criterio se escribió y commiteó
> ANTES de lanzar (`23f7270`).
>
> | Brazo | A solo | B solo | Unión |
> |---|---|---|---|
> | Control (sin señal) | ok | ok | **ROJA** — `TypeError: missing 'base'` en las 2 llamadas ciegas |
> | Tratamiento (hecho enrutado en el despacho) | ok | ROJA | **VERDE** (257 passed) |
>
> El hecho enrutado no fue redactado: se derivó del diff real de A con la maquinaria de firmas de
> `symbols` («calcula: (a, b) → (a, b, base); su llamante capa.procesa ya adaptado»). B₂ lo aplicó
> **pagando su verde local** — sus tests salían rojos en su propio árbol (firma vieja) y lo
> reportó tal cual, con el porqué en el docstring y una predicción comprobable (unión: 4 passed)
> que se cumplió al dígito. *Compartir no es obedecer* sigue siendo cierto en general, pero con el
> hecho correcto, estrecho y en el despacho, este agente obedeció contra su propia evidencia local.
>
> **Hallazgo colateral que hereda el bucle:** el checkpoint marcó a B₂ como «rescate accidental»
> (exit global 1 con la unión verde). La heurística no puede distinguir rescate-por-suerte de
> **coordinación-por-señal**: el rastro observable es idéntico (rama roja sola, unión verde). Un
> agente correctamente enrutado se parece, desde fuera, a uno rescatado. La desambiguación exige
> que el enrutador deje constancia de qué hecho entregó a quién — registro del ORQUESTADOR (el
> bucle), no de `gb`: gb deriva; quién recibió qué señal es historia de la tirada.
>
> **Nota de método:** los worktrees del harness de agentes nacen anclados a un commit fijo de la
> sesión (no «uno por detrás» como se creyó primero) — el experimento corrió sobre worktrees
> propios (`git worktree add --detach <ruta> main`) con la ruta pasada al agente. El banco
> `experimento/` queda en el repo hasta que la fase 2 (el bucle) lo reuse o lo retire.

**Piezas que ya existen:** `symbols.py` extrae la firma tecleable de cada `def`
([`_firma`](../src/galaxybrain/symbols.py#L104), volcada en `sigs`); `delta.py` sabe leer un
fichero en un ref arbitrario de git ([`_texto_en`](../src/galaxybrain/delta.py#L101)); `changes.py`
ya cruza los rangos del diff con los `def` del grafo
([`_onda_del_diff`](../src/galaxybrain/changes.py#L226)). Falta el diff de firmas entre dos refs y
el filtro «llamantes que no están en este diff».

### B. El checkpoint — el cierre, antes de que el trabajo aterrice

> **Construido el 5-ago-2026 (primera rebanada): `gb tests --run --isolated`.** Monta un árbol
> desechable en `HEAD`, le aplica encima el diff que se está midiendo y corre ahí los tests
> impactados. Lo que no viaja en el diff, no viaja — y se dice cuánto se quedó fuera.
> Separa **hecho** (`exit_code`: lo que dijo pytest) de **veredicto** (si se pudo verificar el cambio
> *entero*): con un fichero de test que no viaja, pytest puede decir 0 y la verificación seguir coja.
> El veredicto arranca en 1, porque no haber podido comprobar nunca es un pase. Aísla el **árbol**,
> no el **entorno**: decidir qué es un entorno «limpio» para cada stack sería adivinar (regla 6).
> Módulo: `src/galaxybrain/aislado.py`; 17 tests en `tests/test_aislado.py`.
> En su primer uso real sobre este repo salió 1 y con razón: `test_aislado.py` y `test_delta.py`
> aún no estaban en git, así que la verificación estaba incompleta.
>
> **Nota de método, porque se repitió tres veces:** cada vez que se corrió esto fuera del laboratorio
> encontró un fallo que la suite no veía — un exit 0 con la cobertura coja, una rama invisible por
> tener solo ficheros nuevos, y un «rescate accidental» declarado con una sola rama. Los tests
> comprueban lo que ya sabías que preguntar; el uso real trae las preguntas.

Re-derivar contra el grafo del momento, sobre la **unión** de los diffs paralelos:

- qué símbolos cambiaron de firma en un worktree y tienen llamantes que no se enteraron, **en otro**;
- la unión de las ondas y qué tests la cubren — con la suite entera ante cualquier duda, que es lo
  que `gb tests` ya hace.

Esto coge exactamente el caso en que el consejo del enrutador llegó tarde o se ignoró. Es la mitad
que la v1 no tenía y sin la cual compartir información no garantiza nada.

### C. El canvas — la actividad de cada agente sobre cada nodo, en vivo

**Requisito, fijado el 5-ago-2026:** ver sobre el grafo en qué nodos está trabajando cada agente,
mientras trabaja. No es un adorno de la propuesta: es la razón de que exista.

> **Construido el 5-ago-2026 (primera rebanada).** `actividad.instantanea()` deriva la foto —quién
> toca qué, hace cuánto, con qué módulos habla— recorriendo los worktrees registrados; nadie declara
> nada. El mapa la dibuja: **consola anclada sobre el nodo** (nombre del agente, nodos que toca,
> con cuántos habla, hace cuánto; ámbar/blanco cuando dos agentes coinciden), **un color por agente**
> (paleta de 4 validada: ΔE 20,6 normal / 8,6 deutan; del 5º en adelante tono neutro compartido),
> **halo pulsante del color del agente** —separado del fucsia quieto de tocado-sin-commitear, que es
> estado del árbol, no presencia—, y **ficha fijable a la derecha** que sobrevive al auto-refresco
> (`sessionStorage`, el nodo guardado por ID, nunca por índice). Módulo: `src/galaxybrain/actividad.py`;
> tests en `tests/test_actividad.py` (11) y `tests/test_viz.py` (+3 de la capa de agentes).
>
> **Coste medido (regla 4):** la capa añade **186 ms por regeneración** con 1 worktree activo (git
> por subproceso: lista de worktrees + status/diff por árbol activo), sobre los 334 ms del derive de
> símbolos que ya se pagaba. Regeneración completa ≈ 650 ms aquí — dentro del presupuesto de 1 s por
> edición. El **tick** del watch sigue sin pagar subprocesos (solo `stat`). Escala con el número de
> worktrees *activos*, no registrados: cada activo añade ~3-4 llamadas a git (~60-80 ms). Con >4
> activos en un repo grande hay que re-medir antes de darlo por bueno.
>
> **Cobertura del sondeo, dicho honesto:** el watch detecta cambios recorriendo el árbol observado.
> Los worktrees que cuelgan dentro del repo (`.claude/worktrees/…`) disparan la regeneración solos;
> un worktree hermano FUERA del árbol observado no la dispara — su actividad aparece en la siguiente
> regeneración que provoque cualquier otro cambio. Ampliar el sondeo a los N árboles es la mejora
> pendiente de esta rebanada.

#### El obstáculo que destapó el experimento

Los agentes en paralelo **no comparten árbol**: cada uno corre en su worktree. Y todo el mapa de
`gb` asume una raíz y solo una — [`_firma_py`](../src/galaxybrain/cli.py#L882) hace `os.walk` sobre
un root, y `graph`/`symbols` derivan de una ruta. Consecuencia comprobada: durante las tres tareas
de esta tarde, un `--watch` sobre el checkout principal **se habría quedado quieto** mientras se
escribían ~470 líneas en otros árboles. Cada worktree tenía su grafo completo; ninguno veía a los demás.

#### La forma correcta: una raíz canónica + N superposiciones

No hacen falta N grafos. Los worktrees parten del mismo commit, así que **son los mismos nodos**:

```
1 vez   : derivar el grafo de la raíz canónica            (~162 ms aquí)
por wt  : git diff --name-only  →  la onda (_onda_del_diff)  →  nodos tocados
          nodo + worktree  =  nodo + agente
```

Un derive caro y N diffs baratos, no N derives. Eso es lo que lo mete dentro del presupuesto de
latencia (regla 3) con varios agentes vivos.

#### El refresco: dos velocidades, y por qué no puede ser una

Escrito arriba a lo bruto —«por cada worktree, un `git diff` en cada vuelta»— esto **no se sostiene**:
un `git diff` es un **spawn de proceso**, y en Windows cuesta decenas de ms. Con 4 worktrees a 200 ms
serían ~20 procesos por segundo de forma permanente, compitiendo por CPU con lo observado. Y lo
observado aquí son agentes corriendo inferencia y suites de tests. **La regla 4 (overhead sobre el
proceso observado, medido no estimado) es la que manda en este apartado**, no la 3: un canvas que
roba CPU a los agentes para mirarlos falsea justo lo que mide.

La forma correcta es la que `gb` ya usa en `--watch`, extendida a N árboles:

| Velocidad | Qué hace | Coste |
|---|---|---|
| **rápida** (sub-segundo) | `os.stat` de los `.py` de los N worktrees — la vía de [`_firma_py`](../src/galaxybrain/cli.py#L882). Sin subprocesos. Detecta **que** algo se movió y **en cuál**. | despreciable |
| **lenta** (solo si la rápida se dispara) | el `git diff` y la onda, **únicamente del worktree que cambió** | 1 spawn por cambio real |

Así el coste no escala con la frecuencia del sondeo sino con la **actividad real**: un agente pensando
40 s no cuesta nada; uno escribiendo cuesta un diff. El derive del grafo canónico solo se repite si
cambia la propia raíz.

#### «Tiempo real» aquí significa sondeo

Sin dependencias no hay notificaciones del sistema de ficheros: `watchdog` queda fuera por la regla de
cero dependencias y la stdlib no trae watcher multiplataforma. **El sondeo es forzado, no una elección
de diseño.** (Salida teórica: `ctypes` + `ReadDirectoryChangesW`; solo-Windows y mucha complejidad para
lo que da — descartada salvo que la medida diga otra cosa.)

Traducción: tiempo real = la cadencia del sondeo, que puede bajar al medio segundo. **No es push**, y
no se escribe ni se enseña como si lo fuera.

#### Sobre añadir `watchdog` (planteado y aplazado el 5-ago-2026)

Se planteó meter la dependencia y scriptear su instalación para tener push de verdad. **Aplazado, con
el número que lo desbloquea escrito.**

Qué compraría, contra el diseño de dos velocidades y no contra el ingenuo: casi nada. El coste caro ya
solo se dispara con actividad real; lo que queda en reposo es `os.stat` sobre los `.py` — 58 aquí,
~2.400 en un repo de 600 módulos con 4 worktrees, con la caché caliente. Lo único que compra de verdad
es el **suelo de latencia** (sondear a 500 ms son hasta 500 ms de retraso; push es instantáneo), y eso
hoy es estética, no un problema medido.

Qué costaría: `dependencies = []` es el argumento con el que [SCOPE.md](../SCOPE.md) rechazó ser
servidor MCP — romperlo ahora invalida esa decisión hacia atrás. Y `gb` se instala en el venv de otros
proyectos: cada venv destino cargaría con `watchdog` para un canvas que quizá no usa. **Scriptear la
instalación queda descartado aparte**: la regla 7 dice que lo externo entra por referencia (detección +
instalador oficial + verificación), no con un instalador propio que toca el entorno del usuario.

**La forma admisible, si algún día entra:** dependencia **opcional con degradación silenciosa** — nunca
un import a nivel de módulo; el bucle prueba `import watchdog`, usa push si está y sondea si no.
`dependencies = []` sigue siendo cierto y nadie instala nada a la fuerza. Es la regla 7 (detección) más
la 9 (fallar hacia el lado seguro). No necesita script.

**Qué lo desbloquea:** la medida de overhead que ya exige el criterio de terminado.

#### MEDIDO el 5-ago-2026 — veredicto: `watchdog` NO se paga

Coste de una vuelta del sondeo (`_firma_py`, cachés del FS calientes, 16 núcleos):

| Escenario en reposo | CPU/seg | % de 1 núcleo |
|---|---|---|
| este repo (60 `.py`), 4 ramas, 2 Hz | 19,8 ms | **1,98 %** |
| este repo, 4 ramas, 10 Hz | 98,8 ms | 9,9 % |
| 600 módulos, 4 ramas, 2 Hz | 135 ms | 13,5 % |
| 600 módulos, 4 ramas, 10 Hz | 677 ms | 67,7 % |
| 600 módulos, 8 ramas, 10 Hz | 1.354 ms | 135 % |

**En la escala que aplica —este repo, un puñado de ramas, 2 Hz— sondear cuesta el 2 % de un núcleo.**
Ahí `watchdog` no compra nada que justifique romper `dependencies = []`. El tema se cierra.

Donde sí se rompe es en repos grandes a alta frecuencia, y ahí la cura barata es **bajar la
frecuencia**, no añadir una dependencia: 600 módulos a 2 Hz cuestan 13,5 % y a 10 Hz, 68 %. La
frecuencia es un parámetro; la dependencia es para siempre.

**Y la medida encontró un bug que ya se estaba pagando.** `_firma_py` podaba el ruido con un
`continue`, que salta los ficheros de esa carpeta pero **no impide que `os.walk` siga bajando**: en
este repo recorría 290 directorios y 1.499 ficheros en vez de 16 y 98 — 22 ms por vuelta en vez de
2,5. Lo pagaba el `--watch` de hoy, en cada tick, hubiera cambios o no. Podando sobre `dirs` in place:
**×9**. De paso se arregló que el filtro comparaba subcadenas (`.github` se leía como `.git`, y un
proyecto colgando de ahí se quedaba sin vigilar y sin decirlo). Dos tests lo fijan en
`tests/test_watch.py`.

Límites de la medida, para no citarla de más: cachés calientes, disco local, Windows, una sola
sesión y con la máquina ocupada. El árbol de 600 módulos es sintético y plano — uno real y más
profundo costaría algo más.

#### Persistencia: qué sí y qué no

«Tenerlo todo el rato» y «guardarlo» no son lo mismo, y la diferencia es una regla dura:

- **Proceso vivo que re-deriva** — sí. Es lo que ya hace `--watch`.
- **Grafo persistido para tenerlo a mano** — **no.** Un mapa guardado miente en cuanto alguien edita,
  y mentir con cara de hecho es peor que no estar. El mapa se deriva siempre; lo que se persiste son
  las capturas.

**Y la atribución sale gratis:** la identidad del agente **es la ruta de su worktree**. No hace falta
que nadie declare nada — cae del lado derivado de la ley del apartado 1. (Esto corrige lo que se dijo
antes: derivar la actividad no cuesta perder el «quién», siempre que haya worktrees.)

#### Estados por nodo

| Estado | De dónde sale |
|---|---|
| estable | no aparece en ningún diff |
| tocado por un agente | está en la onda de un worktree — se etiqueta con cuál |
| **tocado por varios** | está en la onda de dos o más — el caso que interesa mirar |
| roto | tiene una captura anclada (ya existe) |
| nuevo | está en un worktree y no en la raíz canónica |

#### Límites, escritos antes de construir

- **Es sondeo, no notificación** (detallado arriba). Con las dos velocidades el coste escala con la
  actividad real, no con la frecuencia ni con el número de worktrees. Nada empuja eventos.
- **Los nodos nuevos no están en la raíz canónica.** Un símbolo que un agente acaba de crear no
  tiene sitio en el mapa base; se pinta aparte o no se pinta, pero no se inventa su posición.
- **Si un worktree parte de otro commit, la superposición miente.** Pasó hoy: los worktrees estaban
  en `6d7409e` y `main` en `bdc949f`. Cuando la base no coincide hay que **decirlo**, no dibujarlo
  (regla 9: fallar hacia el lado seguro).

#### Coste honesto

Esto **no** es una capa de color por encima de lo que hay. Toca la raíz del render: el mapa deja de
tener una fuente y pasa a tener una base más N superposiciones, y eso sube desde `_firma_py` hasta
el HTML. Es la pieza más cara de las tres, y sigue siendo la última del orden del apartado 9 — pero
es la que el usuario pidió, así que se construye entera o no se construye.

---

## 5. Encaje en las familias (CLAUDE.md, regla dura 4)

Ninguna de las dos mecánicas abre familia nueva:

- Enrutador y checkpoint responden **«qué le hizo cada cambio»** — familia `check · tests`. Son la
  misma pregunta con N diffs en vez de uno.
- El canvas responde **«qué forma tiene»** — familia `graph · symbols · calls`. Es el mismo mapa,
  con una base y N superposiciones derivadas de los worktrees vivos (apartado 4C). No abre familia,
  pero **sí ensancha lo que el mapa acepta como fuente**: de una raíz a una raíz más N. Es el punto
  donde este diseño toca hueso, y hay que entrar con eso sabido.

---

## 6. Lo que este diseño NO construye

- **No orquesta.** Quién arranca, con qué competencia y en qué orden lo decide Claude Code. `gb`
  contesta preguntas.
- **No bloquea.** Ambas mecánicas informan (regla 11). Lo único que sigue deteniendo un commit es
  lo de siempre: ciclo de imports nuevo o cruce de frontera declarado.
- **No persiste actividad**, ni pide a ningún agente que declare nada.
- **No promete ausencia de cruces.** En una red neuronal las neuronas se cruzan constantemente; lo
  que la hace funcionar es que **cruzarse es barato y se resuelve**. Ese es el objetivo, no evitarlo.

---

## 7. Criterio de terminado (comprobable, antes de la primera línea)

**Enrutador.** Sobre un diff que cambia la firma de un símbolo, devuelve el hecho tipado y los
llamantes con `fichero:línea` **que no están en ese diff**. Sobre un diff que no cambia ninguna
firma, devuelve vacío. Por debajo del presupuesto de latencia (regla 3) en este repo.

**Checkpoint, rebanada 1 — CUMPLIDO (5-ago-2026).** Un diff se verifica sobre árbol limpio derivado
de `HEAD`; los ficheros que no viajan se dicen; el veredicto distingue «pasó» de «se pudo comprobar
entero»; el disco queda como se encontró aunque pytest falle o el parche no aplique. *(482 tests
verdes, gate limpio.)*

**Checkpoint, rebanada 2 — CUMPLIDO (5-ago-2026): `gb tests --run --union`.** Cada worktree con
cambios se verifica **solo** sobre base limpia, y luego **todos juntos**; lo que se reporta es la
diferencia. Una rama que corrió sus tests, falló, y sale verde en la unión es un **rescate
accidental**: su verde lo puso otra rama. Si las bases no coinciden, se dice y no se calcula la
unión — superponer diffs de bases distintas fabrica un árbol que no existió nunca. Si un test no
viaja en una rama, tampoco viaja a la unión: esa unión se declara igual de incompleta.
*(489 tests verdes, gate limpio.)*

**Canvas, rebanada 1 — CUMPLIDO (5-ago-2026).** El mapa muestra cada nodo con qué worktree lo ha
divergido (consola anclada + color por agente), marca los nodos tocados por más de uno, la ficha
fijada sobrevive al refresco, y ningún agente declara nada. La base distinta se dice en la consola
(`OJO: parte de otra base`) en vez de dibujarse. Overhead medido con 1 worktree activo: 186 ms por
regeneración, cero subprocesos en el tick (regla 4 satisfecha en esta escala).

**Canvas, rebanada 2 — pendiente.** (a) El sondeo del watch amplía a los N árboles aunque cuelguen
fuera del repo observado; (b) re-medir el overhead con ≥4 worktrees activos en un repo grande — si
no sale despreciable, se baja la frecuencia antes que añadir nada.

## 8. Criterios de fracaso, escritos ahora que no duele

- El enrutador emite tanto que un agente lo ignora, o hay que teclear una bandera para que sea útil
  (la norma va en el defecto, no en el prompt).
- El checkpoint no coge ni un solo fallo real que el merge no hubiera cogido igual de barato.
- Aparece la tentación de que `gb` decida el reparto. Eso es orquestar: se rechaza.

---

## 9. Lo medido (5-ago-2026) — la hipótesis del apartado 2 NO se confirmó

Experimento: 3 agentes, worktrees aislados, misma base (`6d7409e`), tres tareas que un orquestador
repartiría como disjuntas. Control: cada diff verde en solitario. Medición: solape contrafactual de
ficheros y líneas, más la suite y el gate sobre la **unión** de los tres diffs.

| Pregunta | Resultado |
|---|---|
| ¿Colisión física (si hubieran compartido árbol)? | **No.** A y B tocaron ambos `cli.py`, pero en líneas distintas. Los 3 parches aplican limpios sobre el mismo árbol. |
| ¿Deriva semántica en la unión? | **No.** 468 tests verdes, gate verde. |

**Por qué no hubo deriva, que es lo que importa:** los dos agentes que cambiaron una firma
(`cli._emit_onda`, `render.render_graph`) **añadieron un parámetro con valor por defecto**. Cambio
compatible hacia atrás; ningún llamante se enteró ni tenía que enterarse. La deriva del apartado 2
requiere un cambio *incompatible*, y ninguno de los tres lo hizo espontáneamente.

### Pero apareció otro fallo, y es peor

Los tres agentes chocaron con el **mismo** problema de entorno: el `.pth` del editable install
pre-importa `galaxybrain` desde el checkout principal al arrancar el intérprete, así que un `pytest`
lanzado en un worktree prueba **el código de otro árbol**. Los tres lo detectaron. Los tres lo
resolvieron **de forma distinta**:

- A: `PYTHONPATH` externo — **fuera del diff**.
- B: parcheó `tests/conftest.py` para expulsar de `sys.modules` lo que no venga de su `src` — dentro del diff.
- C: un `sitecustomize.py` en scratchpad — **fuera del diff**.

Consecuencia medida: **el diff de A en solitario, sobre base limpia, sale ROJO** (3 fallos). Su
«449 passed» era cierto en su sesión y no reproducible desde su artefacto. La unión sale verde solo
porque B tocó `conftest.py` para todos — un **rescate accidental** de la verificación de A por un
agente que no sabía que existía.

Eso no es colisión ni deriva. Es **verificación no reproducible desde el artefacto**: el agente da
por bueno su trabajo contra un entorno que no viaja en el diff. Un verificador que puede validar
código que no es el tuyo es peor que no tener verificador.

### Qué cambia en el diseño

- **El checkpoint (4B) queda justificado, y con otro trabajo del previsto.** Su valor primario no es
  detectar deriva entre diffs — es **re-verificar cada diff desde base limpia**, porque el verde que
  reporta un agente no es evidencia. Esto sí se midió: coge un fallo real que nadie más cogió.
- **El enrutador (4A) queda sin evidencia.** No hubo ni una firma incompatible que enrutar. Se
  mantiene en el diseño pero **baja de prioridad**: construirlo ahora sería resolver un problema que
  no se ha visto.
- **Orden revisado:** checkpoint → (medir otra vez) → enrutador → canvas.

### Límites de esta medida, para no citarla de más

n=1: una tirada, tres tareas, un repo, y las tareas las elegí yo. Que los agentes escriban cambios
compatibles hacia atrás puede ser la norma o puede ser suerte de estas tres tareas. Lo que sí queda
firme es lo positivo —el fallo de verificación ocurrió y está medido—, no lo negativo: **«no hay
deriva» no está demostrado, solo no observado aquí.**

Instrumento: `medir_paralelo.py` (scratchpad de la sesión). Dos trampas que hubo que corregir para
que la medición valiera, ambas del mismo tipo —medir en silencio el árbol equivocado—: el `.pth` de
arriba, y `subprocess(text=True)`, que en Windows decodifica con cp1252 y corrompe los acentos del
diff hasta que `git apply` lo rechaza.
