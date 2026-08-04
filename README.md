<p align="center">
  <img src="assets/galaxia.svg" alt="galaxy-brain" width="100%">
</p>

# galaxy-brain

> **Cuando algo peta, te dice dónde y con qué estado, sin que tengas que reproducirlo a mano.**

Esa es la columna: una consola de errores. Alrededor, la misma disciplina aplicada a otros hechos
deterministas sobre tu código — qué forma tiene (`graph`/`symbols`), qué le hizo cada cambio
(`check`), qué le falta de base (`floor`), qué se aprendió entre repos (`memory`).

**Una sola herramienta, `gb`.** Un paquete Python, **cero llamadas a modelo** en el camino caliente,
**cero dependencias** fuera de la librería estándar. Una excepción es un hecho; el estado en el
momento del fallo es un hecho; la forma del grafo de imports es un hecho. Reportar hechos no necesita
juicio, y por eso puede ser instantáneo y no equivocarse de forma cara.

El alcance está cerrado a propósito, y la lista de lo que **no** hace —que es la que sostiene peso—
está escrita en [SCOPE.md](SCOPE.md). La ley de diseño, en [ARCHITECTURE.md](ARCHITECTURE.md).

<sub>386 tests · gate limpio · ruff · Python ≥ 3.9 · sin dependencias de runtime</sub>

---

## Qué te ahorra

Un traceback te dice **dónde**. Esto te dice además **con qué**:

```
KeyError: 'empresa'
hace 1min · facturacion/precios.py:6 · mi-api

  facturacion/precios.py:6  in precio_total
         4 |
         5 | def precio_total(cliente, cupon=None):
   →     6 |     base = TARIFAS[cliente["plan"]]
         7 |     unidades = cliente["asientos"]
         8 |     return base * unidades

      cliente = {'nombre': 'Beto', 'plan': 'empresa', 'asientos': 12}
      cupon   = None
```

El paso que desaparece es volver a lanzar el programa con un `print` puesto. El fallo ocurre una vez,
a menudo cuando no estás delante; la reproducción es el trabajo caro que esto elimina.

---

## Instalación

```bash
pip install -e .     # desde este repo
gb on                # activa la captura en este entorno Python
gb status            # comprueba que quedó activa
```

`gb on` deja un fichero `.pth` en site-packages. A partir de ahí **no hay que acordarse de nada**:
todo proceso Python de ese entorno queda cubierto, sin tocar el código de ningún proyecto.

Llevarlo a otro proyecto es un solo comando, con el venv de ese proyecto activado:

```bash
# bash / WSL
pip install -e <ruta-a-este-repo> && gb on && gb status

# Windows — instala.ps1 hace exactamente eso, sin escribir rutas (se autolocaliza)
powershell -ExecutionPolicy Bypass -File <ruta-a-este-repo>\instala.ps1
```

La cobertura es **por entorno Python, no por repo**. Y al ser editable (`-e`), un `git pull` aquí
actualiza todos los entornos sin reinstalar. Para quitarlo: `gb off` — una línea, sin rastro. Que
apagarlo sea barato es deliberado (regla 10: el abandono es un dato, no algo que blindar).

---

## La consola de errores

```bash
gb last              # el último fallo de este proyecto, con su estado
gb last --full       # con todos los frames
gb list -n 20        # el histórico: qué se rompe y cuántas veces
gb list --chrono     # el timeline crudo, más reciente primero
gb show <id>         # un fallo concreto — el id lo trae el propio aviso
gb status            # qué hay activo, y cuántas capturas se han leído
```

Sin argumentos, `gb last` y `gb list` filtran por el repo en el que estás. Y la ficha del fallo
termina **en el grafo**: `en el grafo: lib.base · function · lib.py:5 · le llaman (1): lib.ayuda` —
el crash anclado al símbolo que contiene la línea, con su onda a un comando de distancia.

**Un tipo de fallo, tres puertas de salida.** "Excepción no capturada" no es sinónimo de
`sys.excepthook`: el intérprete la deja salir por tres sitios, y los tres se cubren.

| Puerta | Cuándo | Estado |
|---|---|---|
| `sys.excepthook` | La excepción mata el hilo principal y el proceso | cubierto |
| `threading.excepthook` | Mata un hilo de `threading`, el proceso sigue | cubierto (`GB_NO_THREADS=1` lo quita) |
| `sys.unraisablehook` | Python **no pudo** propagarla: `__del__`, weakref, GC | cubierto |

La tercera era la única que desaparecía **sin dejar rastro**: el intérprete la imprime, el proceso no
muere, y no quedaba nada que enseñar. Ninguna de las tres cuesta nada mientras el programa funciona.

**Qué dispara una captura y qué no — ejecutado, no documentado:**

```bash
gb status --cobertura   # corre 8 modos de fallo de verdad y enseña cuál deja registro
```

```
LO QUE SI deja registro          LO QUE NO (y es correcto)
  + excepcion no capturada          - asyncio: tarea suelta que nadie espera
  + excepcion en un hilo            - sys.exit(1)
  + excepcion en __del__            - KeyboardInterrupt
  + asyncio fuera de run()          - excepcion atrapada por try/except
```

La frontera no se documenta —un documento envejece—: se **demuestra** cada vez que lo lanzas.

---

## El mapa

<p align="center">
  <img src="assets/grafo.svg" alt="El grafo de módulos de galaxy-brain" width="100%">
</p>

La otra mitad de la superficie: qué forma tiene el proyecto y quién llama a quién. Todo determinista,
cero modelos, cero dependencias — mismos hechos, distintas vistas. **`graph --html` y `symbols --html`
llevan a la misma página**: módulos, símbolos, imports y llamadas en un solo lienzo navegable.

```bash
gb graph src --gate         # ciclos de imports + fronteras (.gb-boundaries); para pre-commit
gb graph src --gate --since HEAD   # trinquete: solo falla con lo NUEVO, no con la deuda heredada
gb symbols src              # el grafo de símbolos: quién llama a quién, con su cobertura
gb symbols src --html m.html --open        # la nube interactiva (buscar, arrastrar, foco)
gb symbols src --html m.html --watch       # el mapa VIVO: se regenera al cambiar cualquier .py
gb symbols src --since HEAD~50             # lo que creció desde esa ref, marcado aparte
gb calls <simbolo>          # quién llama a un símbolo y a quién llama él, con fichero:línea
gb calls <simbolo> --depth 2               # la onda: también quién llama al que llama
gb check --staged           # qué le hizo un diff a los tests, al acoplamiento, y su onda (informa, no bloquea)
gb floor --init             # el suelo: qué falta antes de construir, y deja los documentos base
```

Al pulsar un nodo, la ficha responde con **hechos**: su descripción (sacada del docstring, no de un
modelo), quién lo llama, a quién llama, qué importa, y si está en un ciclo. El import se pinta distinto
de la llamada porque **el import es exacto y la llamada es inferida** — mezclarlos en un número dejaría
gatear sobre un proxy (regla 11).

Dos números honestos que van siempre en la salida: `gb symbols` **declara cuánto no pudo resolver**
(las llamadas `objeto.metodo()` exigen inferencia de tipos y aquí no se adivina: una arista falsa se
cree, una ausente se nota), y medido contra un índice con inferencia (GitNexus) da **93% de recall**
con cero dependencias. Los detalles y los negativos, en [docs/pruebas-de-uso.md](docs/pruebas-de-uso.md).

**El mapa siempre presente.** Enganchado a un hook de `SessionStart`, `gb graph --context` inyecta el
mapa comprimido (~110 tokens) al arrancar; con `--if-changed`, tras cada edición dice **qué** cambió
en vez de repetir el mapa. Y `gb symbols … --watch` lo mantiene actualizado en el navegador sin
depender de nada más que del sistema de ficheros.

---

## El gate se verifica rompiéndolo

Un gate se degrada en silencio: sigue devolviendo cero y ya no mira nada. Los tests fijan lo que ya
sabías comprobar; esto fija que el detector sigue detectando cuando le pones el defecto delante.

```bash
gb graph --self-test        # inyecta 6 defectos conocidos y falla si el gate NO los ve
gb graph src --self-test    # además: relaciones que deben cumplirse sobre TU código
```

Las **relaciones metamórficas** son "estas dos formas de preguntar tienen que coincidir", evaluadas
sobre tu repo real: la misma carpeta escrita `c:` o `C:` da la misma forma; los imports de un ciclo son
aristas que existen; `graph` y `symbols` ven los mismos módulos. Ahí vivían la mayoría de los defectos
reales que se han cazado.

---

## Memoria cross-repo

Un hecho aprendido en un repo no debería morir ahí. `gb memory` es un vault de notas markdown durables
(en `~/.claude/memory-global`, editables a mano, con `[[wikilinks]]` para abrir el grafo en Obsidian)
que afloran en **cualquier** proyecto vía un hook de `SessionStart`.

```bash
gb memory index              # el índice compacto, una línea por nota
gb memory recall <palabras>  # el texto completo de las notas más relevantes
gb memory context            # el payload de arranque (lo llama el hook de SessionStart)
gb memory add --name x --description "..." --scope always
```

Magro por diseño (H6): el arranque inyecta el índice de **todas** las notas pero el texto completo solo
de las `always` y las del proyecto actual; el resto se trae a demanda con `recall`. Nunca se vuelca el
vault entero.

---

## Coste, medido

Regla 4 de [ARCHITECTURE.md](ARCHITECTURE.md): el presupuesto se mide, no se estima. Python 3.11,
Windows 10, mediana de 20 arranques:

| | |
|---|---|
| Arranque limpio del intérprete | 21,2 ms |
| Con el hook instalado | 27,7 ms |
| **Coste del hook** | **6,4 ms** (medido A/B: 5,2 ms) |
| — de los cuales, `import threading` | 5,2 ms |

**Mientras el programa funciona, el coste es cero.** No "bajo": cero. Los hooks solo se ejecutan cuando
el proceso ya ha fallado. Para un CLI diminuto que jamás toca hilos: `GB_NO_THREADS=1`.

Otros números medidos: mapa de sesión ~110 tokens en 162 ms · `symbols` 93% de recall · lint (ruff)
130 ms · la suite en ~28 s, muy por debajo del umbral DORA de 600 s.

---

## Ajustes

Todo por variable de entorno; no hay fichero de configuración que mantener.

| Variable | Por defecto | Qué hace |
|---|---|---|
| `GB_DISABLE` | off | Apaga la captura sin desinstalar nada |
| `GB_QUIET` | off | Silencia la línea que se imprime tras el traceback |
| `GB_HOME` | `~/.galaxy-brain` | Dónde vive el histórico |
| `GB_NO_THREADS` | off | No captura excepciones de hilos (ahorra 5,2 ms de arranque) |
| `GB_ALL_FRAMES` | off | Guarda también las locales de frames de librería |
| `GB_MAX_FRAMES` | 20 | Frames guardados (se conservan los más internos) |
| `GB_CONTEXT_LINES` | 2 | Líneas de código alrededor de la que falló |
| `GB_OPEN_CMD` | navegador | Con qué se abre el mapa (`--open`); recibe la ruta como último argumento |

`GB_OPEN_CMD` existe porque gb **no conoce ningún editor** y no va a mantener una lista: la regla 6 dice
que un comando cableado es un bug. Esa variable apunta el mapa donde quieras (`GB_OPEN_CMD="firefox
--new-window"`).

---

## Secretos — redacción por nombre, con residuo honesto

El estado alrededor de un fallo es exactamente donde viven las credenciales. La consola **redacta por
nombre** (`password`, `token`, `api_key`, `secret`, `auth`, `credential`, `session`, `cookie`…). El
disparador es siempre el **nombre**, no el contenido: adivinar si una cadena es un secreto es caro y
falible; el nombre lo escribió un humano a propósito.

**El residuo, dicho claro:** un secreto **sin nombre sensible adyacente** llega a disco — un literal
posicional (`connect("hunter2")`), una contraseña en una URL (`user:pass@host`), o un valor secreto
bajo un nombre inocuo. Cerrar eso exigiría heurísticas de contenido, que este proyecto rechaza a
propósito porque fallan y dan falsa seguridad. Por eso la regla de oro no depende de la redacción: **el
histórico vive en tu `$HOME` en texto plano; trátalo como sensible y no lo subas a ningún sitio.**

---

## Límites conocidos, dichos de frente

- **Solo excepciones no capturadas.** Un `except: pass` que se traga el fallo es invisible aquí — y con
  razón: una excepción manejada es, por definición, una que el autor decidió que no era un fallo.
- **Hilo principal, hilos de `threading` y finalizadores** (`__del__`, weakref, GC). **`asyncio` con
  tareas sueltas** que nadie espera queda fuera: si la excepción propaga fuera de `asyncio.run()`, sí se
  captura.
- **Sin fichero fuente, no hay contexto de código.** `python -c`, `exec()` y el REPL guardan tipo,
  mensaje, frames y estado, pero no las líneas de alrededor (y `gb list` los aparta como efímeros).
- **El estado es el del momento en que muere el proceso**, no un depurador con viaje en el tiempo.
- **Objetos irrepresentables se describen, no se reconstruyen.** Un `__repr__` que revienta deja
  `<Tipo: repr() falló con X>` y no se lleva por delante el resto del frame.
- **Las muertes que no son Python** —un segfault, un OOM, un `kill`— no producen excepción, así que
  ningún hook las ve.

---

## Desarrollo

```bash
python -m pytest tests/ -q          # la suite
python -m ruff check src tests      # lint (caza defectos, no opina de estilo)
```

El pre-commit ([.githooks/pre-commit](.githooks/pre-commit)) corre lint + suite + gate en < 10 s;
engánchalo una vez con `git config core.hooksPath .githooks`. `git commit --no-verify` lo salta — y ese
salto es un dato, no una norma (regla 10: el abandono se investiga, no se blinda).

Las reglas de capas de la consola viven en [src/.gb-boundaries](src/.gb-boundaries): el núcleo (captura,
almacén, análisis) no importa la presentación (`cli`, `render`, `viz`). Un cruce nuevo detiene el
commit; una señal de ablandamiento de tests solo informa.
