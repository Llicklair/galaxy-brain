"""Los errores clásicos, medidos como DELTA: no cuántos hay, cuántos añadiste.

Un `except: pass` que lleva seis meses ahí es una decisión de alguien; el mismo
`except: pass` aparecido en este diff es una pregunta sin responder. La diferencia
no está en el patrón, está en **cuándo apareció** — y eso es lo que ninguna
herramienta de las que existen mide (investigado el 5-ago-2026: SpecDetect4LLM,
Hallmark, sloppylint y RADAR miden umbrales absolutos sobre el estado).

Por eso aquí no hay umbrales. No se dice "esta función es muy larga" — se dice
"esta función creció 40 líneas". El estado es del autor; el delta es del cambio.

**Informa, nunca gatea** (ARCHITECTURE, regla 11). Son proxies: un `except
Exception: pass` puede ser exactamente lo correcto (gb tiene 22, y son la regla 9
cumplida a rajatabla). Gatear proxies fabrica los falsos positivos que acaban en
`--no-verify`, y ese error ya se pagó una vez.

Cero dependencias: `ast` de la librería estándar. ast-grep habría servido, pero
una señal que solo aparece si el usuario instaló algo es una señal que no aparece.
"""

import ast
import os

from . import changes

#: Cuánto tiene que crecer un cuerpo para que crecer sea noticia. No es un umbral
#: sobre el tamaño (una función de 300 líneas que no cambia no dice nada aquí):
#: es cuánto se movió en ESTE diff. 30 líneas es un cambio que ya no se lee de una
#: sentada; por debajo, avisar sería ruido.
CRECIMIENTO = 30


class _Visitante(ast.NodeVisitor):
    """Recolecta los hechos de un fichero: handlers, marcas y tamaños."""

    def __init__(self):
        self.silencios = []      # (linea, texto) — el error se traga entero
        self.amplios = []        # (linea, texto) — captura todo, aunque haga algo
        self.pendientes = []     # (linea, texto) — NotImplementedError, TODO/FIXME
        self.cuerpos = {}        # nombre -> (inicio, fin)

    def visit_ExceptHandler(self, node):
        cuerpo = [s for s in node.body
                  if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))]
        tragado = len(cuerpo) == 1 and isinstance(cuerpo[0], (ast.Pass, ast.Continue))
        if node.type is None:
            tipo = "except:"
        elif isinstance(node.type, ast.Name):
            tipo = "except %s:" % node.type.id
        else:
            tipo = "except (...):"
        if tragado:
            self.silencios.append((node.lineno, "%s se traga el error sin dejar rastro" % tipo))
        elif isinstance(node.type, ast.Name) and node.type.id in ("Exception", "BaseException"):
            self.amplios.append((node.lineno, "%s captura todo, no un fallo concreto" % tipo))
        self.generic_visit(node)

    def visit_Raise(self, node):
        exc = node.exc
        nombre = None
        if isinstance(exc, ast.Call) and isinstance(exc.func, ast.Name):
            nombre = exc.func.id
        elif isinstance(exc, ast.Name):
            nombre = exc.id
        if nombre == "NotImplementedError":
            self.pendientes.append((node.lineno, "NotImplementedError: queda sin implementar"))
        self.generic_visit(node)

    def _registrar(self, node):
        fin = getattr(node, "end_lineno", None)
        if fin:
            self.cuerpos[node.name] = (node.lineno, fin)
        self.generic_visit(node)

    visit_FunctionDef = _registrar
    visit_AsyncFunctionDef = _registrar
    visit_ClassDef = _registrar


def _hechos(texto):
    """Los hechos de un texto fuente. Si no parsea, no hay hechos (no es un error)."""
    try:
        arbol = ast.parse(texto)
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return None
    visitante = _Visitante()
    visitante.visit(arbol)
    for numero, linea in enumerate(texto.split("\n"), 1):
        limpia = linea.strip()
        if not limpia.startswith("#"):
            # Solo comentarios: un TODO dentro de una cadena o de un nombre no es
            # una marca de trabajo pendiente, y contarlo seria ruido.
            continue
        for marca in ("TODO", "FIXME", "XXX", "HACK"):
            if marca in limpia:
                visitante.pendientes.append((numero, limpia[:70]))
                break
    return visitante


def _texto_en(root, ruta, ref):
    """El fichero tal y como estaba en `ref` — o None si allí no existía."""
    if ref is None:
        path = os.path.join(root, ruta.replace("/", os.sep))
        try:
            with open(path, "r", encoding="utf-8-sig", errors="replace") as handle:
                return handle.read()
        except OSError:
            return None
    return changes._git_output(root, "show", "%s:%s" % (ref, ruta))


def _nuevas(antes, ahora):
    """Las entradas de `ahora` que no estaban en `antes`, comparadas por TEXTO.

    Por texto y no por línea: si añades diez líneas arriba, todos los handlers de
    abajo cambian de número sin haber cambiado. Comparar por línea los marcaría
    como nuevos, y una señal que se dispara por un cambio que no ocurrió es
    exactamente el falso positivo que manda una revisión a `--no-verify`.
    """
    if antes is None:
        return list(ahora)
    cuenta = {}
    for _linea, texto in antes:
        cuenta[texto] = cuenta.get(texto, 0) + 1
    nuevas = []
    for linea, texto in ahora:
        if cuenta.get(texto, 0) > 0:
            cuenta[texto] -= 1
        else:
            nuevas.append((linea, texto))
    return nuevas


def analyze(root, rev_range=None, staged=False, worktree=False):
    """Qué errores clásicos AÑADIÓ este cambio. Informe, nunca veredicto."""
    report = {
        "root": root,
        "range": "worktree" if worktree else ("staged" if staged else rev_range),
        "range_error": None,
        "silencios": [],    # errores que se tragan
        "amplios": [],      # capturas demasiado anchas
        "pendientes": [],   # trabajo declarado sin terminar
        "crecidos": [],     # cuerpos que engordaron de golpe
        "ficheros": 0,
    }
    if not os.path.isdir(root):
        report["range_error"] = "la raiz no existe o no es un directorio: %s" % root
        return report

    if worktree:
        diff = changes._git_output(root, "diff", "--unified=0", "HEAD")
        base = "HEAD"
    elif staged:
        diff = changes._git_output(root, "diff", "--unified=0", "--cached")
        base = "HEAD"
    else:
        rev_range = rev_range or "HEAD~1..HEAD"
        report["range"] = rev_range
        diff = changes._git_output(root, "diff", "--unified=0", rev_range)
        base = rev_range.split("..")[0] or "HEAD~1"

    if diff is None:
        report["range_error"] = "no se pudo leer el diff (¿sin git, o rango invalido?)"
        return report

    # Con un rango, el "ahora" es el extremo derecho; en worktree/staged, el disco.
    ahora_ref = None
    if not (worktree or staged):
        derecha = rev_range.split("..")[-1] if ".." in rev_range else rev_range
        ahora_ref = derecha or "HEAD"

    for ruta in sorted(changes._hunks_py(diff)):
        texto_ahora = _texto_en(root, ruta, ahora_ref)
        if texto_ahora is None:
            continue
        hechos_ahora = _hechos(texto_ahora)
        if hechos_ahora is None:
            continue
        report["ficheros"] += 1

        texto_antes = _texto_en(root, ruta, base)
        hechos_antes = _hechos(texto_antes) if texto_antes is not None else None

        for clave in ("silencios", "amplios", "pendientes"):
            previas = getattr(hechos_antes, clave) if hechos_antes else None
            for linea, texto in _nuevas(previas, getattr(hechos_ahora, clave)):
                report[clave].append({"file": ruta, "line": linea, "what": texto})

        if hechos_antes is not None:
            for nombre, (inicio, fin) in hechos_ahora.cuerpos.items():
                viejo = hechos_antes.cuerpos.get(nombre)
                if not viejo:
                    continue
                crecio = (fin - inicio) - (viejo[1] - viejo[0])
                if crecio >= CRECIMIENTO:
                    report["crecidos"].append({
                        "file": ruta, "line": inicio, "name": nombre,
                        "grew": crecio, "now": fin - inicio,
                    })

    report["crecidos"].sort(key=lambda c: -c["grew"])

    # Ficheros nuevos sin trackear: el diff no los ve.
    sin_trackear = changes.untracked_py(root)
    report["untracked_py"] = sin_trackear

    return report


def total(report):
    return sum(len(report[k]) for k in ("silencios", "amplios", "pendientes", "crecidos"))
