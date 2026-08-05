"""Acoplamiento por el grafo de imports.

Determinista, cero modelos, cero dependencias (solo `ast`/stdlib). Devuelve el
MAPA de acoplamiento del proyecto — quién importa a quién, qué ciclos hay, qué
módulos están más acoplados. No dicta: muestra. Un ciclo de imports es un HECHO,
no una opinión, y por eso casi no tiene falsos positivos (ARCHITECTURE, regla 11:
una gate que chilla sin motivo acaba en --no-verify).

Lo que cambia todo es que el almacén tenga forma: un grafo responde "¿quién
depende de X?" con aristas, no con ficheros enteros.

Límites honestos, dichos de frente: es análisis ESTÁTICO. No ve imports
dinámicos (`__import__`, `importlib.import_module`), y cuenta los imports dentro
de `if TYPE_CHECKING:` o de funciones como aristas aunque no sean dependencias
de runtime. Es un grafo de acoplamiento a nivel de módulo, no un call graph.

El delta (`--since`) compara por NOMBRE de módulo, tanto los pares co-cíclicos
como los cruces de frontera: renombrar o mover un módulo cambia su nombre y puede
marcar como "nuevo" un ciclo o un cruce que ya existía (falso positivo). Cerrarlo
requiere seguir renombrados con git (`--find-renames`) y mapear nombres
viejos->nuevos — trabajo futuro. Mitigación hoy: sin `--since`, la gate es
absoluta (no compara nombres, solo el hecho presente).
"""

import ast
import hashlib
import json
import os

#: El BOM de UTF-8, como carácter. Escrito con chr() y no literal a propósito: un
#: BOM literal dentro del fuente es invisible, sobrevive mal a un copy-paste y es
#: exactamente la clase de carácter que este módulo existe para tolerar.
_BOM = chr(0xFEFF)

#: Directorios que no son código del proyecto (no se analizan).
DEFAULT_SKIP = frozenset(
    (
        "__pycache__",
        "site-packages",
        "dist-packages",
        "node_modules",
        "build",
        "dist",
        "venv",
        ".venv",
        ".tox",
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".galaxy-brain",
    )
)


#: Ficheros que marcan la raiz de un proyecto Python distinto. Un directorio
#: anidado que tenga uno de estos NO es codigo de este proyecto: es otro proyecto
#: metido dentro (fixture, vendorizado, submodulo, ejemplo). Sus ciclos son suyos.
PROJECT_MARKERS = ("pyproject.toml", "setup.py", "setup.cfg", ".git")


def _is_nested_project(path):
    return any(os.path.exists(os.path.join(path, marker)) for marker in PROJECT_MARKERS)


def _iter_py_files(root, skip, include_nested=False, skipped=None):
    """Los .py de ESTE proyecto bajo `root`.

    Poda los subproyectos anidados (ver PROJECT_MARKERS) salvo `include_nested`.
    Lo podado se acumula en `skipped` para poder DECIRLO: una gate que reduce su
    cobertura en silencio miente en verde, que es justo lo que no puede pasar.
    """
    for dirpath, dirnames, filenames in os.walk(root):
        keep = []
        for name in dirnames:
            if name in skip or name.startswith("."):
                continue
            full = os.path.join(dirpath, name)
            if not include_nested and _is_nested_project(full):
                if skipped is not None:
                    skipped.append(os.path.relpath(full, root).replace("\\", "/"))
                continue
            keep.append(name)
        dirnames[:] = keep
        for name in filenames:
            if name.endswith(".py"):
                yield os.path.join(dirpath, name)


def module_name(path, root):
    """Nombre de módulo punteado para un .py dentro de root.

    Consciente del layout `src/`: si el primer segmento es `src`, se cuenta la
    ruta del módulo desde ahí, para que `src/galaxybrain/store.py` sea
    `galaxybrain.store` y no `src.galaxybrain.store`.
    """
    rel = os.path.relpath(path, root).replace("\\", "/")
    parts = [p for p in rel.split("/") if p and p != "."]
    if parts and parts[0] == "src":
        parts = parts[1:]
    if not parts:
        return ""
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1][:-3]  # sin .py
    return ".".join(parts)


def _import_targets(tree, this_module, is_package):
    """Módulos que este AST importa (nombres punteados), resolviendo relativos.

    `is_package` importa para los imports relativos: en un __init__.py el paquete
    actual es el propio módulo, no su padre — sin esto, `from .x import y` dentro
    de un __init__ resolvía un nivel demasiado arriba.
    """
    targets = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                targets.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            base = _resolve_base(node, this_module, is_package)
            if base is None:
                continue
            for alias in node.names:
                # Solo el target MÁS específico: `from pkg import x` -> `pkg.x`.
                # Si x es un nombre y no un submódulo, _to_internal cae al paquete
                # `pkg` por prefijo. Añadir `pkg` aquí duplicaría la arista.
                if base:
                    targets.add(base + "." + alias.name)
                else:
                    targets.add(alias.name)
    return {t for t in targets if t}


def _resolve_base(node, this_module, is_package):
    """El módulo base de un `from ... import` (absoluto o relativo)."""
    if node.level == 0:
        return node.module or ""
    # Relativo: subir `level` desde el PAQUETE que contiene los imports. Para un
    # __init__ ese paquete es el propio módulo (__package__ == __name__); para un
    # módulo normal, su padre.
    parts = this_module.split(".")
    container = parts if is_package else parts[:-1]
    up = node.level - 1  # nivel 1 = mismo paquete; cada nivel extra sube uno más
    if up > len(container):
        return None
    if up:
        container = container[: len(container) - up]
    prefix = ".".join(container)
    if node.module:
        return (prefix + "." + node.module) if prefix else node.module
    return prefix


def build_graph(root, skip=DEFAULT_SKIP, include_nested=False, skipped=None):
    """Construye el grafo de imports INTERNOS del proyecto en `root`.

    Devuelve (nodes, edges, errors):
      - nodes: set de nombres de módulo del proyecto
      - edges: dict módulo -> set de módulos internos que importa (sin auto-aristas)
      - errors: dict fichero -> mensaje (ficheros que no parsean)
    """
    items = []
    for path in _iter_py_files(root, skip, include_nested, skipped):
        mod = module_name(path, root)
        if not mod:
            continue
        try:
            # errors="replace" como en _git: un .py guardado en cp1252 (comunísimo
            # en Windows) no debe tumbar el análisis, y ambas rutas (working tree y
            # git) deben leer el mismo fichero igual o el delta diverge.
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                text = handle.read()
        except OSError:
            text = None
        items.append((mod, path, text, os.path.basename(path) == "__init__.py"))
    return _graph_from_sources(items)


def _graph_from_sources(items):
    """Núcleo compartido: grafo a partir de (módulo, ubicación, texto).

    `items`: iterable de (module_name, location, source_or_None). location es la
    ruta (de fichero o de git) que se usa como clave de error, para que el aviso
    apunte a algo que un humano reconozca.
    """
    nodes = {mod for mod, _loc, _text, _pkg in items}
    edges = {}
    errors = {}
    for mod, loc, text, is_pkg in items:
        if text is None:
            errors[loc] = "no se pudo leer"
            edges[mod] = set()
            continue
        try:
            # El BOM de UTF-8 no es sintaxis: el interprete lo descarta al compilar,
            # pero ast.parse sobre texto YA decodificado lo ve como U+FEFF y lanza
            # SyntaxError. Sin este lstrip, un fichero que Python ejecuta sin
            # pestanear desaparece del mapa — y en Windows es comunisimo, porque
            # PowerShell y varios editores escriben UTF-8 con BOM por defecto.
            tree = ast.parse(text.lstrip(_BOM), filename=loc)
        # RecursionError/MemoryError no son SyntaxError ni ValueError: un .py
        # patológico (anidamiento enorme) no puede tumbar el análisis entero.
        except (SyntaxError, ValueError, RecursionError, MemoryError) as error:
            errors[loc] = "%s: %s" % (type(error).__name__, error)
            edges[mod] = set()
            continue
        internal = {_to_internal(t, nodes) for t in _import_targets(tree, mod, is_pkg)}
        internal.discard(None)
        internal.discard(mod)  # sin auto-aristas
        edges[mod] = internal
    for mod in nodes:
        edges.setdefault(mod, set())
    return nodes, edges, errors


def _git(cwd, *args):
    """Corre git y devuelve stdout, o None si falla (no-repo, ref inválida...).

    Decodifica como UTF-8 con `errors="replace"`: los blobs de git son el código
    fuente, que lleva acentos; `text=True` usaría el codec del locale (cp1252 en
    Windows) y reventaría al leer UTF-8 — y un blob mal leído corrompería la
    baseline y daría falsos positivos en el delta.
    """
    import subprocess

    try:
        # core.quotePath=false: sin esto, git C-escapa las rutas con bytes no-ASCII
        # (`"caf\303\251.py"`), el .endswith(".py") falla y el módulo acentuado se
        # cae de la baseline -> falso positivo en el delta. Reproducido.
        result = subprocess.run(
            ["git", "-C", cwd, "-c", "core.quotePath=false", *args],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def _nested_prefixes_in_listing(paths, root_rel):
    """Prefijos (rutas git) de subproyectos anidados, deducidos del propio listado.

    Se calcula sobre la ref, no sobre el disco: la baseline debe verse a sí misma,
    o un subproyecto que hoy existe y entonces no (o al revés) mueve la frontera y
    el delta inventa ciclos "nuevos".
    """
    root_rel = "" if root_rel in (".", "") else root_rel.rstrip("/") + "/"
    prefixes = set()
    for path in paths:
        head, _sep, tail = path.rpartition("/")
        if tail not in PROJECT_MARKERS or not head:
            continue
        prefix = head + "/"
        if prefix == root_rel or not prefix.startswith(root_rel):
            continue  # el marcador de la propia raiz no la poda a ella misma
        prefixes.add(prefix)
    return prefixes


def build_graph_from_git(root, ref, skip=DEFAULT_SKIP, include_nested=False):
    """Grafo de la baseline: los .py bajo `root` tal como estaban en `ref`.

    Lee los blobs directamente de git — NO toca el working tree. Los nombres de
    módulo se calculan con el mismo `root` que el working tree para que aristas y
    ciclos sean comparables. Devuelve (nodes, edges, errors), o None si no hay
    repo o la ref no existe.
    """
    repo = _git(root, "rev-parse", "--show-toplevel")
    if repo is None:
        return None
    repo = repo.strip()
    try:
        rel = os.path.relpath(root, repo).replace("\\", "/")
    except ValueError:
        return None  # cross-drive en Windows (SUBST/unidad mapeada): no comparamos
    args = ["ls-tree", "-r", "--name-only", ref]
    if rel not in (".", ""):
        args += ["--", rel]
    listing = _git(repo, *args)
    if listing is None:
        return None

    entries = [line.strip() for line in listing.splitlines() if line.strip()]
    nested = set() if include_nested else _nested_prefixes_in_listing(entries, rel)

    items = []
    for gitpath in entries:
        if not gitpath.endswith(".py"):
            continue
        if any(gitpath.startswith(prefix) for prefix in nested):
            continue
        parts = gitpath.split("/")
        if any(p in skip or p.startswith(".") for p in parts):
            continue
        abspath = os.path.join(repo, *parts)
        try:
            if os.path.relpath(abspath, root).startswith(".."):
                continue  # fuera de root
        except ValueError:
            continue
        mod = module_name(abspath, root)
        if not mod:
            continue
        text = _git(repo, "show", "%s:%s" % (ref, gitpath))
        items.append((mod, gitpath, text, parts[-1] == "__init__.py"))
    return _graph_from_sources(items)


def cyclic_pairs(cycles):
    """Pares (no ordenados) de módulos en el MISMO ciclo.

    Es la unidad honesta para detectar acoplamiento cíclico nuevo: quitar un
    módulo de un ciclo no crea pares nuevos; añadir acoplamiento cíclico sí.
    """
    pairs = set()
    for cyc in cycles:
        for i in range(len(cyc)):
            for j in range(i + 1, len(cyc)):
                pairs.add(frozenset((cyc[i], cyc[j])))
    return pairs


def _to_internal(target, nodes):
    """Mapea un target de import al módulo interno más específico, o None.

    `from galaxybrain.saferepr import redact_text` produce el target
    `galaxybrain.saferepr.redact_text`; el módulo real es `galaxybrain.saferepr`,
    así que se recorta por sufijos hasta dar con un módulo del proyecto.
    """
    if target in nodes:
        return target
    parts = target.split(".")
    for cut in range(len(parts) - 1, 0, -1):
        candidate = ".".join(parts[:cut])
        if candidate in nodes:
            return candidate
    return None


def find_cycles(edges):
    """Componentes fuertemente conexos con acoplamiento cíclico (Tarjan iterativo).

    Devuelve la lista de ciclos (cada uno, lista de módulos), los de tamaño >1 o
    con auto-arista. Iterativo a propósito: un monorepo grande reventaría la
    recursión.
    """
    index = {}
    low = {}
    on_stack = set()
    stack = []
    counter = [0]
    sccs = []

    def strongconnect(root_node):
        work = [(root_node, iter(sorted(edges.get(root_node, ()))))]
        index[root_node] = low[root_node] = counter[0]
        counter[0] += 1
        stack.append(root_node)
        on_stack.add(root_node)
        while work:
            node, it = work[-1]
            advanced = False
            for succ in it:
                if succ not in index:
                    index[succ] = low[succ] = counter[0]
                    counter[0] += 1
                    stack.append(succ)
                    on_stack.add(succ)
                    work.append((succ, iter(sorted(edges.get(succ, ())))))
                    advanced = True
                    break
                if succ in on_stack:
                    low[node] = min(low[node], index[succ])
            if advanced:
                continue
            if low[node] == index[node]:
                comp = []
                while True:
                    w = stack.pop()
                    on_stack.discard(w)
                    comp.append(w)
                    if w == node:
                        break
                sccs.append(comp)
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])

    for node in sorted(edges):
        if node not in index:
            strongconnect(node)

    cycles = []
    for comp in sccs:
        if len(comp) > 1:
            cycles.append(sorted(comp))
        elif len(comp) == 1 and comp[0] in edges.get(comp[0], ()):
            cycles.append(comp)  # auto-import (raro pero real)
    cycles.sort(key=lambda c: (-len(c), c))
    return cycles


BOUNDARIES_FILE = ".gb-boundaries"


def load_boundaries(root, path=None):
    """Lee las reglas de frontera del proyecto. Texto plano, una por línea:

        SRC -/-> DST

    significa: ningún módulo bajo SRC puede importar uno bajo DST. Comentarios con
    `#`. Por defecto se busca `.gb-boundaries` en `root`. Devuelve un dict
    {rules, malformed, error}: `rules` las reglas parseadas; `malformed` las líneas
    que parecían regla pero no lo son (typo, se avisan, no se descartan mudas);
    `error` un mensaje si el fichero debía leerse y no se pudo. La gate de fronteras
    es opt-in: si el fichero por defecto no existe, no hay error.
    """
    explicit = path is not None
    if path is None:
        path = os.path.join(root, BOUNDARIES_FILE)
    try:
        # utf-8-sig: con BOM, la primera regla del fichero se leia como basura y
        # acababa en `malformed` — enforced nada y por un caracter invisible.
        with open(path, "r", encoding="utf-8-sig", errors="replace") as handle:
            content = handle.read()
    except FileNotFoundError:
        # Fichero por defecto ausente = opt-in (sin error). Ruta EXPLÍCITA que no
        # existe = error: pediste unas reglas que no están, y pasar en verde sería
        # la falsa cobertura del invariante 4.
        error = ("no encuentro el fichero de fronteras: %s" % path) if explicit else None
        return {"rules": [], "malformed": [], "error": error, "path": path}
    except OSError as error:
        # Existe pero no se puede leer (permisos, es un directorio…): nunca silencioso.
        return {
            "rules": [],
            "malformed": [],
            "error": "no pude leer %s (%s)" % (path, error),
            "path": path,
        }

    rules = []
    malformed = []
    for raw in content.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("-/->")]
        if len(parts) == 2 and parts[0] and parts[1]:
            rules.append((parts[0], parts[1]))
        else:
            # Contenido que NO es una regla válida (flecha con typo, dos flechas,
            # un lado vacío): enforced nada. Se avisa en vez de descartarse mudo.
            malformed.append(line)
    return {"rules": rules, "malformed": malformed, "error": None, "path": path}


def find_boundaries(root, max_depth=2):
    """Dónde está el `.gb-boundaries` que manda para `root`, o None.

    **La raíz gana siempre**; si no está ahí, se busca poco profundo, porque el
    layout típico es `root/src` o `root/paquete`.

    Esto existe para que haya UNA sola regla de descubrimiento. Antes `graph` miraba
    exactamente `root/.gb-boundaries` y `floor` sí buscaba, así que `gb graph src`
    cargaba 33 reglas y `gb check` —que analiza desde la raíz del repo— cargaba
    CERO en el mismo repo y con el mismo fichero. El que cargaba cero no comprobaba
    nada, y esa mitad de la gate llevaba tiempo siendo decorativa. Reportado usando
    la herramienta de verdad (2026-07-31).

    No se busca hacia ARRIBA a propósito: subir podría agarrar el fichero de otro
    proyecto que te contiene, y aplicar fronteras ajenas es peor que no aplicar
    ninguna. Ese caso lo denuncia `_boundaries_elsewhere` en vez de resolverlo solo.
    """
    directo = os.path.join(root, BOUNDARIES_FILE)
    if os.path.isfile(directo):
        return directo
    for depth_root, dirs, files in os.walk(root):
        rel = os.path.relpath(depth_root, root)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        if depth >= max_depth:
            dirs[:] = []
        dirs[:] = [d for d in dirs if d not in DEFAULT_SKIP and not d.startswith(".")]
        if BOUNDARIES_FILE in files:
            return os.path.join(depth_root, BOUNDARIES_FILE)
    return None


def _boundaries_elsewhere(root, consultado, max_arriba=3):
    """Un `.gb-boundaries` que existe pero NO es el que se ha leido, o None.

    El caso que engana de verdad: el fichero esta en la raiz del repo y se analiza
    `src/` (o al reves). Nadie recibe un error — simplemente se cargan cero reglas
    y el gate pasa en verde sin comprobar una sola frontera. Es el peor modo de
    fallo que puede tener un gate, porque el verde se lee como "comprobado y
    limpio". Encontrado usando la herramienta de verdad en otro repo (2026-07-31).

    Se mira arriba (hasta la raiz del repo git) y un nivel abajo, que es donde cae
    el layout tipico: root/src, root/paquete.
    """
    consultado = os.path.normcase(os.path.abspath(consultado))
    candidatos = []

    actual = os.path.abspath(root)
    for _ in range(max_arriba):
        padre = os.path.dirname(actual)
        if padre == actual:
            break
        candidatos.append(os.path.join(padre, BOUNDARIES_FILE))
        if os.path.isdir(os.path.join(padre, ".git")):
            break
        actual = padre

    # Hacia abajo: el arbol PROPIO entero (podado), no un solo nivel. Un fichero
    # a profundidad >=3 ni se encontraba ni se denunciaba: gate a 0 con un
    # fichero de reglas entero sin aplicar — el modo de fallo de dfbe9ab
    # sobreviviendo un nivel mas abajo (hallado por la tirada de agentes del
    # 5-ago-2026). Los subproyectos anidados se SALTAN: sus fronteras son suyas,
    # y denunciarlas aqui fabricaria el falso positivo que acaba en --no-verify.
    try:
        for dirpath, dirs, files in os.walk(root):
            dirs[:] = sorted(
                d for d in dirs
                if d not in DEFAULT_SKIP
                and not d.startswith(".")
                and not _is_nested_project(os.path.join(dirpath, d))
            )
            if BOUNDARIES_FILE in files:
                candidatos.append(os.path.join(dirpath, BOUNDARIES_FILE))
    except OSError:
        pass

    for candidato in candidatos:
        if os.path.normcase(candidato) != consultado and os.path.isfile(candidato):
            return candidato
    return None


def _under(module, pattern):
    """¿`module` es `pattern` o cuelga de él, en frontera de punto?

    Frontera de punto para no dar falsos positivos: `myapp.web` NO casa con
    `myapp.website`, solo con `myapp.web` y `myapp.web.*`.
    """
    return module == pattern or module.startswith(pattern + ".")


def find_violations(edges, rules):
    """Aristas (importador -> importado) que cruzan una frontera prohibida.

    Un cruce prohibido es un HECHO (declaraste la regla), no una opinión — de ahí
    los casi cero falsos positivos.
    """
    violations = []
    for importer in sorted(edges):
        for imported in sorted(edges[importer]):
            for src, dst in rules:
                if _under(importer, src) and _under(imported, dst):
                    violations.append(
                        {
                            "importer": importer,
                            "imported": imported,
                            "rule": "%s -/-> %s" % (src, dst),
                        }
                    )
                    break  # una violación por arista basta
    return violations


def unmatched_rules(nodes, rules):
    """Reglas cuyo SRC o DST no casa con NINGÚN módulo del grafo.

    Una regla que no casa con nada nunca dispara: es un typo o —muy común— señal
    de que apuntaste `gb graph` a otra raíz (los nombres de módulo dependen de
    ella: `gb graph src` da `galaxybrain.store`, `gb graph src/galaxybrain` da
    `store`). Avisar de esto evita el peor fallo de una gate: creer que cubre algo
    que en realidad no comprueba.
    """
    out = []
    for src, dst in rules:
        src_ok = any(_under(m, src) for m in nodes)
        dst_ok = any(_under(m, dst) for m in nodes)
        if not (src_ok and dst_ok):
            out.append(
                {"rule": "%s -/-> %s" % (src, dst), "src_matches": src_ok, "dst_matches": dst_ok}
            )
    return out


def _dotted_name(node):
    """Nombre punteado de una expresión ast (Name/Attribute), o None."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted_name(node.value)
        return (base + "." + node.attr) if base else node.attr
    return None


def _is_abc_class(classdef):
    """¿Es una clase abstracta estilo `abc`? (base ABC/ABCMeta, metaclass=ABCMeta,
    o algún método @abstractmethod). Los Protocol se tratan aparte: son
    estructurales y tener 0 subclases explícitas es NORMAL, no un smell."""
    for base in classdef.bases:
        name = (_dotted_name(base) or "").split(".")[-1]
        if name in ("ABC", "ABCMeta"):
            return True
    for kw in classdef.keywords:
        if kw.arg == "metaclass" and (_dotted_name(kw.value) or "").split(".")[-1] == "ABCMeta":
            return True
    for item in classdef.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in item.decorator_list:
                target = dec.func if isinstance(dec, ast.Call) else dec
                if (_dotted_name(target) or "").split(".")[-1] in ("abstractmethod", "abstractproperty"):
                    return True
    return False


def _is_protocol_class(classdef):
    return any((_dotted_name(b) or "").split(".")[-1] == "Protocol" for b in classdef.bases)


def overengineering(root, skip=DEFAULT_SKIP, include_nested=False):
    """Proxies de sobreingeniería — ADVISORY, NUNCA gate.

    El único que shippeamos por ser fact-adjacent y de bajo ruido: abstracciones
    (estilo abc.ABC) con 0 o 1 implementación concreta — la interfaz para una sola
    cosa, el smell clásico. Tiene falsos positivos LEGÍTIMOS (puntos de extensión,
    seams de test), así que NO es un veredicto ni bloquea: es una lista para que la
    mires tú. Gatearlo sería el error de la forja (opiniones como gate). Los
    Protocol se excluyen (estructurales). El matching de subclases es por nombre
    simple: best-effort, coherente con lo advisory.
    """
    abstract = []  # {"module", "class"}
    subclass_bases = {}  # nombre simple de base -> nº de clases que la heredan
    for path in _iter_py_files(root, skip, include_nested):
        mod = module_name(path, root)
        if not mod:
            continue
        try:
            # utf-8-sig: descarta el BOM si lo hay (ver el lstrip de _graph_from_sources)
            # y se comporta igual que utf-8 cuando no lo hay.
            with open(path, "r", encoding="utf-8-sig", errors="replace") as handle:
                tree = ast.parse(handle.read())
        except (SyntaxError, ValueError, RecursionError, MemoryError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for base in node.bases:
                simple = (_dotted_name(base) or "").split(".")[-1]
                if simple:
                    subclass_bases[simple] = subclass_bases.get(simple, {})
                    subclass_bases[simple][node.name] = True  # una clase distinta que la hereda
            if _is_abc_class(node) and not _is_protocol_class(node):
                abstract.append({"module": mod, "class": node.name})

    out = []
    for abc_class in abstract:
        heirs = subclass_bases.get(abc_class["class"], {})
        impls = len([h for h in heirs if h != abc_class["class"]])
        if impls <= 1:
            out.append({"module": abc_class["module"], "class": abc_class["class"], "impls": impls})
    out.sort(key=lambda x: (x["impls"], x["module"], x["class"]))
    return out


def analyze(root, skip=DEFAULT_SKIP, since=None, boundaries=None, smells=False, include_nested=False):
    """El informe del acoplamiento del proyecto.

    Con `since` (ref de git) añade el delta de acoplamiento cíclico NUEVO. Con un
    fichero de fronteras (`.gb-boundaries`) añade los cruces prohibidos; con ambos,
    también qué cruces son nuevos respecto a la baseline.

    `root_error` y `skipped_nested` existen por el invariante 4: analizar una raíz
    que no está, o quedarse sin módulos porque todo era subproyecto, NO puede salir
    en verde. Una gate que cubre cero y calla es peor que no tenerla.
    """
    root_error = None
    if not os.path.isdir(root):
        root_error = "la raiz no existe o no es un directorio: %s" % root

    skipped_nested = []
    nodes, edges, errors = build_graph(root, skip, include_nested, skipped_nested)
    fan_out = {mod: len(deps) for mod, deps in edges.items()}
    fan_in = {mod: 0 for mod in nodes}
    for deps in edges.values():
        for dep in deps:
            fan_in[dep] = fan_in.get(dep, 0) + 1
    cycles = find_cycles(edges)
    # Sin ruta explicita se DESCUBRE con la regla compartida: que `graph` y `check`
    # resolvieran sitios distintos hacia que el mismo repo tuviera 33 reglas para
    # uno y 0 para el otro (ver find_boundaries).
    if boundaries is None:
        boundaries = find_boundaries(root)
    boundaries_info = load_boundaries(root, boundaries)
    rules = boundaries_info["rules"]
    violations = find_violations(edges, rules)
    edge_count = sum(len(d) for d in edges.values())
    report = {
        "root": root,
        "root_error": root_error,
        "skipped_nested": sorted(skipped_nested),
        "include_nested": include_nested,
        "modules": len(nodes),
        "edges": edge_count,
        # La lista de aristas, no solo su numero: es el grafo de verdad, y sin ella
        # `--json` obliga a reconstruirlo por fuera. Ordenada, para que dos
        # ejecuciones den el mismo fichero.
        "edge_list": sorted([mod, dep] for mod, deps in edges.items() for dep in deps),
        "cycles": cycles,
        "fan_in": fan_in,
        "fan_out": fan_out,
        "errors": errors,
        "boundaries": len(rules),
        # La ruta CONSULTADA, se hayan encontrado reglas o no. Sin esto, "0 reglas"
        # es un dato inaccionable: no dice donde habria que poner el fichero.
        "boundaries_path": boundaries_info["path"],
        # Un `.gb-boundaries` que existe pero NO es el consultado. Es el caso que
        # de verdad enganna: crees que tienes fronteras y la gate no mira ninguna.
        "boundaries_elsewhere": _boundaries_elsewhere(root, boundaries_info["path"]),
        "violations": violations,
        "unmatched_rules": unmatched_rules(nodes, rules),
        "malformed_boundaries": boundaries_info["malformed"],
        "boundaries_error": boundaries_info["error"],
        "smells": smells,
        "abstractions": overengineering(root, skip, include_nested) if smells else [],
        "since": since,
        "baseline_ok": None,
        "new_cycles": [],
        "new_pairs": [],
        "new_violations": [],
    }
    if since is not None:
        base = build_graph_from_git(root, since, skip, include_nested)
        if base is None:
            report["baseline_ok"] = False
        else:
            _bn, base_edges, _be = base
            base_pairs = cyclic_pairs(find_cycles(base_edges))
            new_pairs = cyclic_pairs(cycles) - base_pairs
            report["baseline_ok"] = True
            # Ordenado también por fuera: un set de frozensets itera en orden que
            # depende de PYTHONHASHSEED; sin esto la salida no es reproducible.
            report["new_pairs"] = sorted(sorted(p) for p in new_pairs)
            report["new_cycles"] = [
                c
                for c in cycles
                if any(
                    frozenset((c[i], c[j])) in new_pairs
                    for i in range(len(c))
                    for j in range(i + 1, len(c))
                )
            ]
            # Cruces prohibidos NUEVOS: aplico las reglas ACTUALES a la baseline y
            # comparo por (importador, importado). Un cruce preexistente no bloquea.
            base_keys = {
                (v["importer"], v["imported"]) for v in find_violations(base_edges, rules)
            }
            report["new_violations"] = [
                v for v in violations if (v["importer"], v["imported"]) not in base_keys
            ]
    return report


def _escribir(raiz, rel, texto):
    ruta = os.path.join(raiz, *rel.split("/"))
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as handle:
        handle.write(texto)


def _sonda_ciclo(raiz):
    _escribir(raiz, "pkg/__init__.py", "")
    _escribir(raiz, "pkg/a.py", "from . import b\n")
    _escribir(raiz, "pkg/b.py", "from . import a\n")
    rep = analyze(raiz)
    return bool(rep["cycles"]), "%d ciclo(s) detectado(s)" % len(rep["cycles"])


def _sonda_cruce(raiz):
    _escribir(raiz, BOUNDARIES_FILE, "pkg.a  -/->  pkg.b\n")
    _escribir(raiz, "pkg/__init__.py", "")
    _escribir(raiz, "pkg/a.py", "from . import b\n")
    _escribir(raiz, "pkg/b.py", "")
    rep = analyze(raiz)
    return bool(rep["violations"]), "%d cruce(s) sobre %d regla(s)" % (
        len(rep["violations"]),
        rep["boundaries"],
    )


def _sonda_limpio(raiz):
    """La otra mitad, y la que casi nadie prueba: que NO grite sin motivo.

    Un detector que dispara siempre pasa todas las sondas de deteccion y es
    inservible. Sin esta, `--self-test` mediria solo la mitad barata.
    """
    _escribir(raiz, BOUNDARIES_FILE, "pkg.b  -/->  pkg.a\n")
    _escribir(raiz, "pkg/__init__.py", "")
    _escribir(raiz, "pkg/a.py", "from . import b\n")
    _escribir(raiz, "pkg/b.py", "")
    rep = analyze(raiz)
    limpio = not rep["cycles"] and not rep["violations"]
    return limpio, "sin ciclos ni cruces sobre %d regla(s)" % rep["boundaries"]


def _sonda_verde_silencioso(raiz):
    """El peor modo de fallo de un gate, y paso de verdad el 31-jul: el fichero de
    reglas en la raiz del repo, el analisis apuntando a `src/`, cero reglas
    cargadas y verde. Reproduce ese caso exacto.

    Limite conocido y dicho: solo se buscan ancestros y un nivel por debajo. Un
    `.gb-boundaries` en una carpeta HERMANA no se denuncia — rastrear hermanas
    arbitrarias invitaria a adoptar el fichero de un proyecto que no es este.
    """
    _escribir(raiz, BOUNDARIES_FILE, "pkg.a  -/->  pkg.b\n")
    _escribir(raiz, "src/pkg/__init__.py", "")
    _escribir(raiz, "src/pkg/a.py", "from . import b\n")
    _escribir(raiz, "src/pkg/b.py", "")
    rep = analyze(os.path.join(raiz, "src"))
    visto = rep["boundaries"] == 0 and rep["boundaries_elsewhere"] is not None
    return visto, "0 reglas cargadas y el fichero extraviado, senalado"


def _sonda_bom(raiz):
    """Un fichero que el interprete compila no puede desaparecer del mapa."""
    _escribir(raiz, "pkg/__init__.py", "")
    _escribir(raiz, "pkg/a.py", _BOM + "from . import b\n")
    _escribir(raiz, "pkg/b.py", "")
    rep = analyze(raiz)
    return (not rep["errors"] and rep["edges"] == 1), "%d error(es), %d arista(s)" % (
        len(rep["errors"]),
        rep["edges"],
    )


def _sonda_descubrimiento(raiz):
    """Dos rutas al mismo repo tienen que leer el MISMO fichero de reglas."""
    _escribir(raiz, "src/" + BOUNDARIES_FILE, "pkg.a  -/->  pkg.b\n")
    _escribir(raiz, "src/pkg/__init__.py", "")
    _escribir(raiz, "src/pkg/a.py", "from . import b\n")
    _escribir(raiz, "src/pkg/b.py", "")
    desde_raiz = analyze(raiz)
    desde_src = analyze(os.path.join(raiz, "src"))
    coherente = desde_raiz["boundaries"] == desde_src["boundaries"] == 1
    return coherente, "%d regla(s) desde la raiz, %d desde src" % (
        desde_raiz["boundaries"],
        desde_src["boundaries"],
    )


#: Cada sonda es un defecto que ocurrio DE VERDAD (31-jul-2026) o el falso
#: positivo simetrico. La lista crece cuando aparece un fallo nuevo, no antes.
_SONDAS = (
    ("ciclo de imports", "tiene que verlo", _sonda_ciclo),
    ("cruce de frontera", "tiene que verlo", _sonda_cruce),
    ("proyecto limpio", "tiene que CALLAR", _sonda_limpio),
    ("fichero de reglas extraviado", "tiene que denunciarlo", _sonda_verde_silencioso),
    ("fuente con BOM", "no puede perderla", _sonda_bom),
    ("misma raiz, dos rutas", "tiene que dar lo mismo", _sonda_descubrimiento),
)


def _primer_subdirectorio(root):
    """El primer subdirectorio con codigo, para las relaciones que comparan
    raiz contra subarbol. None si no hay ninguno: la relacion se salta."""
    try:
        for nombre in sorted(os.listdir(root)):
            sub = os.path.join(root, nombre)
            if nombre.startswith(".") or nombre in DEFAULT_SKIP or not os.path.isdir(sub):
                continue
            if analyze(sub)["modules"]:
                return sub
    except OSError:
        pass
    return None


def _rel_idempotencia(root, _sym):
    a, b = shape(analyze(root)), shape(analyze(root))
    return a == b, "dos analisis seguidos dan la misma forma", None


def _rel_grafia_de_ruta(root, _sym):
    """La misma carpeta escrita de otra forma es la misma carpeta.

    Esta relacion es la que habria cazado el bug de la clave de cache (`c:` vs
    `C:`) sin necesidad de que a nadie se le ocurriera mirar.
    """
    variantes = [root, root + os.sep, os.path.join(root, ".")]
    formas = [shape(analyze(v)) for v in variantes]
    return all(f == formas[0] for f in formas), "3 grafias de la misma ruta, una sola forma", None


def _rel_include_nested_monotono(root, _sym):
    """Mirar TAMBIEN los subproyectos no puede hacer DESAPARECER modulos.

    Es monotonia pura: `--include-nested` amplia el barrido, nunca lo estrecha.
    Si alguna vez se estrecha, la logica de omitir anidados esta comiendose
    codigo del proyecto — y lo haria en silencio, contando menos modulos.
    """
    estrecho = set(analyze(root).get("fan_in") or {})
    ancho = set(analyze(root, include_nested=True).get("fan_in") or {})
    perdidos = sorted(estrecho - ancho)
    if perdidos:
        return False, "con --include-nested DESAPARECEN %d modulo(s): %s" % (
            len(perdidos), ", ".join(perdidos[:4])
        ), None
    return True, "%d modulos sin anidados, %d con ellos (nunca menos)" % (
        len(estrecho), len(ancho)
    ), None


def _rel_huella_estable_por_json(root, _sym):
    """La forma tiene que sobrevivir al viaje a disco y volver identica.

    De esto depende el cache: si la ida y vuelta por JSON la cambiara, cada
    arranque diria que el proyecto entero se ha movido.
    """
    forma = shape(analyze(root))
    vuelta = json.loads(json.dumps(forma, ensure_ascii=False))
    return forma == vuelta, "la forma sobrevive a JSON sin cambiar", None


def _rel_ciclos_sobre_aristas_reales(root, _sym):
    """Cada paso de un ciclo tiene que ser una arista que existe de verdad.

    Es la relacion que protege lo unico que BLOQUEA: si el buscador de ciclos
    pudiera inventarse un tramo, estaria deteniendo commits por un import que
    nadie escribio.
    """
    rep = analyze(root)
    reales = {tuple(e) for e in (rep.get("edge_list") or [])}
    inventadas = []
    for ciclo in rep.get("cycles") or []:
        for i in range(len(ciclo)):
            paso = (ciclo[i], ciclo[(i + 1) % len(ciclo)])
            if paso not in reales:
                inventadas.append("%s->%s" % paso)
    if not rep.get("cycles"):
        return None, "", "este proyecto no tiene ciclos que verificar"
    return not inventadas, "%d ciclo(s), todos sus tramos son aristas reales" % len(
        rep["cycles"]
    ), (None if not inventadas else "tramos inventados: %s" % ", ".join(inventadas[:4]))


def _rel_graph_vs_symbols(root, sym):
    """Los dos analizadores tienen que ver el MISMO conjunto de modulos.

    Que `graph` y `symbols` se separen es exactamente la familia de fallo del
    31-jul: dos lecturas del mismo repo que dejan de coincidir sin avisar.
    """
    if sym is None:
        return None, "", "sin informe de simbolos (lo pasa quien llama)"
    de_graph = set(analyze(root).get("fan_in") or {})
    de_symbols = {n.get("module") for n in (sym.get("nodes") or []) if n.get("module")}
    fuera = sorted(de_symbols - de_graph)
    return not fuera, "%d modulo(s) en symbols, todos conocidos por graph" % len(de_symbols), (
        None if not fuera else "symbols ve modulos que graph no: %s" % ", ".join(fuera[:4])
    )


#: Relaciones que deben cumplirse sobre CUALQUIER proyecto, no sobre un fixture.
#: Ahi esta su valor: un fixture fija lo que ya sabias comprobar; una relacion se
#: evalua contra tu codigo de verdad y caza la incoherencia que nadie imagino.
#: Se descartaron dos candidatas en la primera ejecucion, y merece quedar escrito:
#: "los modulos del subarbol son un subconjunto de los de la raiz" y "la raiz y el
#: subdirectorio cargan las mismas fronteras". Ninguna es invariante — los nombres
#: de modulo son RELATIVOS a la raiz analizada, y las fronteras no se heredan hacia
#: abajo a proposito. Daban falso positivo sobre codigo sano, que es justo lo que la
#: regla 11 dice que acaba en `--no-verify`. Una relacion falsa es peor que ninguna.
_RELACIONES = (
    ("idempotencia", _rel_idempotencia),
    ("grafia de la ruta", _rel_grafia_de_ruta),
    ("include-nested es monotono", _rel_include_nested_monotono),
    ("la forma sobrevive a JSON", _rel_huella_estable_por_json),
    ("los ciclos usan aristas reales", _rel_ciclos_sobre_aristas_reales),
    ("graph y symbols ven lo mismo", _rel_graph_vs_symbols),
)


def relations(root, symbols_report=None):
    """Comprueba las relaciones metamorficas sobre un proyecto REAL.

    Cada una dice "estas dos formas de preguntar tienen que coincidir". No
    escriben nada: solo leen el arbol que les des.

    Una relacion que no aplica sale como SALTADA con su motivo, jamas como
    cumplida — contar un salto como un exito es la mentira que llevamos todo el
    dia desmontando.

    `symbols_report` lo pasa quien llama para no importar `symbols` desde aqui:
    `symbols` ya importa a `graph`, y el import inverso seria un ciclo — el mismo
    hecho que este modulo existe para detectar.
    """
    resultados = []
    for nombre, relacion in _RELACIONES:
        try:
            ok, detalle, motivo_salto = relacion(root, symbols_report)
        except BaseException as error:  # noqa: BLE001
            ok, detalle, motivo_salto = False, "", None
            detalle = "la relacion reviento: %s: %s" % (type(error).__name__, error)
        resultados.append(
            {
                "relacion": nombre,
                "ok": ok,  # None = saltada
                "detalle": detalle or motivo_salto or "",
                "saltada": ok is None,
            }
        )
    return {
        "relations": resultados,
        "broken": [r["relacion"] for r in resultados if r["ok"] is False],
        "skipped": [r["relacion"] for r in resultados if r["saltada"]],
    }


def self_test(root=None, symbols_report=None):
    """Verifica el gate ROMPIENDOLO a proposito, no comprobando que pasa.

    Un gate se degrada en silencio: sigue devolviendo cero y ya no mira nada. Los
    tests fijan lo que el autor sabia comprobar; esto fija que el detector sigue
    detectando cuando le pones delante el defecto. Es la leccion escrita en
    docs/pruebas-de-uso.md el 31-jul, cobrada sobre la propia herramienta.

    Cada sonda monta un proyecto de mentira en un temporal del sistema —jamas
    dentro del tuyo (regla 7)— y lo borra al salir.
    """
    import shutil
    import tempfile

    resultados = []
    for nombre, espera, sonda in _SONDAS:
        raiz = tempfile.mkdtemp(prefix="gb-selftest-")
        try:
            ok, detalle = sonda(raiz)
        except BaseException as error:  # noqa: BLE001 - una sonda rota es un fallo, no un crash
            ok, detalle = False, "la sonda reviento: %s: %s" % (type(error).__name__, error)
        finally:
            shutil.rmtree(raiz, ignore_errors=True)
        resultados.append({"sonda": nombre, "espera": espera, "ok": ok, "detalle": detalle})

    informe = {
        "probes": resultados,
        "failed": [r["sonda"] for r in resultados if not r["ok"]],
        "root": None,
        "relations": [],
        "broken": [],
        "skipped": [],
    }
    # Con una ruta se anade la otra mitad: las sondas comprueban que el detector
    # ve defectos de mentira; las relaciones comprueban que el analisis es
    # coherente consigo mismo sobre codigo DE VERDAD, que es donde vivian los
    # seis fallos del 31-jul.
    if root:
        informe["root"] = root
        informe.update(relations(root, symbols_report))
        informe["failed"] = informe["failed"] + informe["broken"]
    return informe


def shape(report):
    """La FORMA del informe: lo estructural, sin nada del cuerpo del código.

    Es lo que se persiste entre sesiones, y por eso se guarda entera y no como un
    hash: con la forma anterior en disco se puede decir **qué** cambió, no solo
    *que* cambió — y un aviso que dice "+1 arista: cli → foo" vale mucho más y
    ocupa mucho menos que repetir el mapa completo en cada edición.

    Sólo se mueve con algo estructural: un módulo, una arista, un ciclo o un cruce.
    Renombrar una variable o reescribir el cuerpo de una función NO la mueven, y
    esa insensibilidad es justo el punto.
    """
    return {
        # fan_in tiene una entrada por modulo analizado, tambien los que no importan
        # a nadie: un modulo nuevo y suelto ya es un cambio de forma.
        "modules": sorted(report.get("fan_in") or {}),
        "edges": sorted([list(e) for e in (report.get("edge_list") or [])]),
        "cycles": sorted([sorted(c) for c in (report.get("cycles") or [])]),
        "violations": sorted(
            [
                v.get("importer", "") + ">" + v.get("imported", "")
                for v in (report.get("violations") or [])
            ]
        ),
    }


def fingerprint(report):
    """La forma reducida a una huella corta y comparable."""
    crudo = json.dumps(shape(report), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(crudo.encode("utf-8")).hexdigest()[:16]


def shape_delta(antes, ahora):
    """Qué cambió entre dos formas.

    Devuelve `None` si no hay forma anterior (la primera vez en un proyecto no hay
    delta posible y quien llama debe enseñar el mapa entero), `{}` si no ha cambiado
    nada, o el desglose. Se dicen las dos direcciones: una arista que DESAPARECE es
    tan informativa como una que aparece, y un ciclo resuelto merece verse tanto
    como uno nuevo — si sólo se contaran las altas, el mapa mental se desincroniza
    en cuanto alguien borra algo.
    """
    if antes is None:
        return None

    def _aristas(forma):
        return {tuple(e) for e in (forma.get("edges") or [])}

    def _ciclos(forma):
        return {tuple(c) for c in (forma.get("cycles") or [])}

    mods_antes, mods_ahora = set(antes.get("modules") or []), set(ahora.get("modules") or [])
    ar_antes, ar_ahora = _aristas(antes), _aristas(ahora)
    cic_antes, cic_ahora = _ciclos(antes), _ciclos(ahora)
    vio_antes, vio_ahora = set(antes.get("violations") or []), set(ahora.get("violations") or [])

    delta = {
        "modules_added": sorted(mods_ahora - mods_antes),
        "modules_removed": sorted(mods_antes - mods_ahora),
        "edges_added": sorted(ar_ahora - ar_antes),
        "edges_removed": sorted(ar_antes - ar_ahora),
        "cycles_added": sorted(cic_ahora - cic_antes),
        "cycles_removed": sorted(cic_antes - cic_ahora),
        "violations_added": sorted(vio_ahora - vio_antes),
        "violations_removed": sorted(vio_antes - vio_ahora),
    }
    return delta if any(delta.values()) else {}
