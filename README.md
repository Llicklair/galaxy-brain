# galaxy-brain v2

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

Para quitarlo: `gb off`. Es una línea y no deja rastro — que apagarlo sea barato es deliberado
(ARCHITECTURE-v2, regla 10: el abandono es un dato, no algo que blindar).

## Uso

```bash
gb last              # el último fallo de este proyecto
gb last --full       # con todos los frames
gb list -n 20        # el histórico: qué se rompe y cuántas veces
gb show <id>         # uno concreto
gb status            # qué hay activo
```

Sin argumentos, `gb last` y `gb list` filtran por el repo en el que estás.

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
ejecuta cuando el proceso ya se está muriendo. Por eso v2 empieza por excepciones no capturadas y
no por instrumentación continua.

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

## Secretos — redacción parcial, best-effort

El estado alrededor de un fallo es exactamente donde viven las credenciales. La consola **redacta por
nombre** (`password`, `token`, `api_key`, `secret`, `auth`, `credential`, `session`, `cookie`…) cuando
el secreto aparece como **variable local suelta** o **clave de diccionario poco anidada**. Es una
heurística por nombre, no por contenido: adivinar si una cadena es un secreto es caro y falible; el
nombre lo escribió un humano a propósito.

**Pero la cobertura es parcial, y hay que decirlo claro.** Una revisión adversarial
([docs/review-2026-07-29.md](docs/review-2026-07-29.md)) confirmó cinco canales por los que un secreto
llega igualmente a disco:

- el **texto del traceback** y las **líneas de código fuente** se guardan crudos;
- el **mensaje de la excepción** (`raise ValueError(f"bad token {t}")`) se guarda crudo;
- **`sys.argv`** entero (`mytool --password X`);
- un dict con el secreto **anidado ≥2 niveles** (el cap de profundidad anula la redacción);
- los **atributos de un objeto** (`dataclass`/pydantic con un campo `password`).

Redactar cualquiera de esos de forma fiable exige heurísticas de contenido, que este proyecto rechaza
a propósito (dan falsa sensación de seguridad). Así que la regla de oro no depende de la redacción:
**el histórico vive en tu `$HOME` en texto plano; trátalo como sensible y no lo subas a ningún sitio.**
La redacción por nombre quita el ruido más obvio, no es una garantía.

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
