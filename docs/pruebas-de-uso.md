# Pruebas de uso — la libreta del arnés

Registro de cada prueba de uso real: qué se probó, qué salió y qué cambió por ello.
Existe porque [SCOPE.md](../SCOPE.md) arrastra una deuda concreta — el único dato empírico del
proyecto (el A/B de la báscula) vive en memoria y no en el repo. Un proyecto sobre evidencia no puede
tener la suya fuera, así que aquí se queda, incluida la que va en contra.

Formato: fecha, qué se probó, resultado, consecuencia. Los resultados negativos se escriben con el
mismo detalle que los positivos, o más.

---

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
