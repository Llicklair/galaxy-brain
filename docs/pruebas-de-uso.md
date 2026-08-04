# Pruebas de uso — la libreta del arnés

Registro de cada prueba de uso real: qué se probó, qué salió y qué cambió por ello.
Existe porque [SCOPE.md](../SCOPE.md) arrastra una deuda concreta — el único dato empírico del
proyecto (el A/B de la báscula) vive en memoria y no en el repo. Un proyecto sobre evidencia no puede
tener la suya fuera, así que aquí se queda, incluida la que va en contra.

Formato: fecha, qué se probó, resultado, consecuencia. Los resultados negativos se escriben con el
mismo detalle que los positivos, o más.

---

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

Pista fuerte que deja la sesión: el grafo **ahorra y no miente** cuando se le pregunta, y la
consola sigue esperando su caso natural — el crash asíncrono o lejano, donde leer el estado gana a
re-ejecutar. El mapa vivo (watcher con candado) aguantó toda la sesión regenerándose solo.

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
