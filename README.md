# galaxy-brain

> **Cuando algo peta, te dice dónde y con qué estado, sin que tengas que reproducirlo a mano.**

Eso es todo lo que hace. Un lenguaje (Python), un runtime (local), un tipo de fallo (excepciones no
capturadas). El alcance está cerrado a propósito y la lista de lo que **no** hace está escrita en
[SCOPE.md](SCOPE.md).

Cero llamadas a modelo. Cero dependencias. Una excepción es un hecho; el estado en el momento del
fallo es un hecho. Reportar hechos no necesita juicio.

---

## Qué te ahorra

Un traceback te dice **dónde**. Esto te dice además **con qué**:

```
KeyError: 'empresa'
hace 1min - facturacion/precios.py:6 - mi-api

  facturacion/precios.py:6  in precio_total
         4 |
         5 | def precio_total(cliente, cupon=None):
   >     6 |     base = TARIFAS[cliente["plan"]]
         7 |     unidades = cliente["asientos"]
         8 |     return base * unidades

      cliente = {'nombre': 'Beto', 'plan': 'empresa', 'asientos': 12}
      cupon   = None
```

El paso que desaparece es volver a lanzar el programa con un `print` puesto.

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

Se lleva la herramienta entera (consola, mapa, gate, floor, memoria): es un solo paquete, no hay
versiones que elegir. La cobertura es **por entorno Python, no por repo** — si el otro proyecto usa un entorno
donde `gb` ya está activa, no hay nada que ejecutar. Y al ser editable (`-e`), un `git pull` aquí
actualiza todos los entornos sin reinstalar.

Para quitarlo: `gb off`. Es una línea y no deja rastro — que apagarlo sea barato es deliberado
(ARCHITECTURE, regla 10: el abandono es un dato, no algo que blindar).

### Opcional — con qué se abre el mapa

`--open` usa tu navegador. Nada más que hacer: el HTML es autocontenido y no necesita servidor.

Para mandarlo a otro sitio hay `GB_OPEN_CMD`, que recibe la ruta como último argumento:

```bash
GB_OPEN_CMD="firefox --new-window"   gb symbols src --html mapa.html --open
```

gb **no conoce ningún editor** y no va a mantener una lista de ellos: la regla 6 dice que un comando
cableado es un bug. Esa variable es todo lo que hace falta para apuntarlo donde quieras.

**Verlo dentro de VS Code / Cursor** necesita una extensión, porque ninguno de los dos sabe renderizar
HTML de serie — abrirlo con `code fichero.html` te enseña el código, no el mapa:

```bash
code --install-extension ms-vscode.live-server
```

Y el aviso honesto, comprobado: esa extensión **solo expone comandos del editor**, sin entrada por
línea de órdenes. O sea que `GB_OPEN_CMD` **no** puede lanzarla, y el flujo queda manual — generas el
fichero sin `--open` y haces clic derecho → *Show Preview*. Si eso te resulta más incómodo que
cambiar de ventana, no la instales: el navegador da más sitio para un mapa que se arrastra y se
amplía.

## Uso

```bash
gb last              # el último fallo de este proyecto
gb last --full       # con todos los frames
gb list -n 20        # el histórico: qué se rompe y cuántas veces
gb show <id>         # uno concreto
gb status            # qué hay activo
```

Sin argumentos, `gb last` y `gb list` filtran por el repo en el que estás.

## El mapa y las gates

La otra mitad de la superficie: qué forma tiene el proyecto y qué le hizo cada cambio.
Todo determinista, cero modelos, cero dependencias — mismos hechos, distintas vistas.

```bash
gb graph src --gate        # ciclos de imports + fronteras (.gb-boundaries); para pre-commit
gb graph src --html m.html # el mapa de módulos, dibujado
gb symbols src             # el grafo de símbolos: quién llama a quién, con su cobertura
gb symbols src --html n.html --open   # la nube interactiva (física en vivo, buscar, arrastrar)
gb symbols src --since HEAD~50        # lo que creció desde esa ref: la película, baseline en git
gb check --staged          # qué le hace este cambio a los tests y al acoplamiento (informa, no bloquea)
gb floor --init            # el suelo: qué falta antes de construir, y deja los documentos base
```

Dos números honestos que van siempre en la salida: `gb symbols` **declara cuánto no pudo
resolver** (las llamadas `objeto.metodo()` exigen inferencia de tipos y aquí no se adivina:
una arista falsa se cree, una ausente se nota), y medido contra un índice con inferencia
(GitNexus) da **93% de recall** con cero dependencias. Los detalles y los negativos, en
[docs/pruebas-de-uso.md](docs/pruebas-de-uso.md).

---

## Memoria cross-repo

Un hecho aprendido en un repo no debería morir ahí. `gb memory` es un vault de notas markdown
durables (en `~/.claude/memory-global`, editables a mano, con `[[wikilinks]]` para abrir el grafo en
Obsidian) que afloran en **cualquier** proyecto vía un hook de `SessionStart`.

```bash
gb memory index              # el índice compacto, una línea por nota
gb memory recall <palabras>  # el texto completo de las notas más relevantes
gb memory context            # el payload de arranque (lo llama el hook de SessionStart)
gb memory add --name x --description "..." --scope always
```

Magro por diseño (H6): el arranque inyecta el índice de **todas** las notas pero el texto completo
solo de las `always` y las del proyecto actual; el resto se trae a demanda con `recall`. Nunca se
vuelca el vault entero.

Para engancharlo, añade a `~/.claude/settings.json` un hook de `SessionStart` que ejecute
`gb memory context` (ver la nota de instalación al final).

---

## Coste, medido

Regla 4 de [ARCHITECTURE.md](ARCHITECTURE.md): el presupuesto se mide, no se estima.
Python 3.11, Windows 10, mediana de 20 arranques:

| | |
|---|---|
| Arranque limpio del intérprete | 21,2 ms |
| Con el hook instalado | 27,7 ms |
| **Coste del hook** | **6,4 ms** |
| — de los cuales, `import threading` | 5,2 ms |
| — de los cuales, código propio | 0,5 ms |

**Mientras el programa funciona, el coste es cero.** No "bajo": cero. `sys.excepthook` solo se
ejecuta cuando el proceso ya se está muriendo. Por eso la consola empieza por excepciones no
capturadas y no por instrumentación continua.

Los 5,2 ms de `threading` la mayoría de programas los pagan igual (logging, asyncio, requests lo
importan). Para un CLI diminuto que jamás toca hilos: `GB_NO_THREADS=1`.

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
| `GB_MAX_LOCALS` | 40 | Variables por frame |
| `GB_MAX_VALUE_CHARS` | 240 | Longitud máxima del repr de un valor |
| `GB_MAX_ITEMS` | 10 | Elementos de una colección antes de resumirla |
| `GB_CONTEXT_LINES` | 2 | Líneas de código alrededor de la que falló |

---

## Secretos — redacción por nombre, con residuo honesto

El estado alrededor de un fallo es exactamente donde viven las credenciales. La consola **redacta por
nombre** (`password`, `token`, `api_key`, `secret`, `auth`, `credential`, `session`, `cookie`…). El
disparador es siempre el **nombre**, no el contenido: adivinar si una cadena es un secreto es caro y
falible; el nombre lo escribió un humano a propósito. Se redacta cuando el nombre sensible aparece como:

- variable **local** o **clave de diccionario**, a cualquier profundidad de anidamiento;
- **atributo** de un objeto (`dataclass`/pydantic con un campo `password`);
- una asignación `nombre = valor` o `nombre: valor` en **texto libre** — líneas de código fuente,
  mensajes de excepción y el traceback (`token=abc`, `password = "x"`, `"api_key": "..."`);
- y `sys.argv` no se guarda entero: solo el programa y la cuenta (`mytool --password X` no llega).

**El residuo, dicho claro:** un secreto **sin nombre sensible adyacente** no se puede redactar por
nombre y llega a disco — un literal posicional (`connect("hunter2")`), prosa sin separador
(`"password hunter2"`), una contraseña embebida en una URL (`user:pass@host`), o un valor secreto bajo
un nombre de variable inocuo. Cerrar eso exigiría heurísticas de contenido (olfatear "lo que parece un
secreto"), que este proyecto rechaza a propósito porque fallan y dan falsa seguridad.

Por eso la regla de oro no depende de la redacción: **el histórico vive en tu `$HOME` en texto plano;
trátalo como sensible y no lo subas a ningún sitio.** `GB_CONTEXT_LINES=0` desactiva del todo la captura
de líneas fuente si prefieres no arriesgar ahí. Detalle: [docs/review-2026-07-29.md](docs/review-2026-07-29.md).

---

## Límites conocidos, dichos de frente

- **Solo excepciones no capturadas.** Un `except: pass` que se traga el fallo es invisible aquí.
- **Hilo principal e hilos de `threading`.** `asyncio` y `multiprocessing` no están cubiertos.
- **Sin fichero fuente, no hay contexto de código.** `python -c`, `exec()` y el REPL guardan tipo,
  mensaje, frames y estado, pero no las líneas de alrededor.
- **El estado es el del momento en que muere el proceso**, no el de cada paso previo. Esto no es un
  depurador con viaje en el tiempo y no pretende serlo.
- **Objetos irrepresentables se describen, no se reconstruyen.** Un `__repr__` que revienta deja
  `<Tipo: repr() falló con X>` y no se lleva por delante el resto del frame.

## Desarrollo

```bash
python -m pytest tests/ -q
```

### Gate de acoplamiento — sobre la propia herramienta

Un segundo determinista, cero modelos, cero dependencias (solo `ast`):

```bash
gb graph src --smells        # el mapa: modulos, ciclos, fan-in/out, sobreingenieria (advisory)
gb graph src --gate          # falla si hay un ciclo de imports NUEVO o un cruce de frontera prohibido
git config core.hooksPath .githooks   # engancha el pre-commit (tests + gate) — una vez
```

Las reglas de capas de la consola viven en [src/.gb-boundaries](src/.gb-boundaries) (el nucleo no
importa la presentacion). El pre-commit corre en < 10 s; `git commit --no-verify` lo salta — y ese
salto es un dato, no una norma (ARCHITECTURE regla 10: el abandono se investiga, no se blinda).
