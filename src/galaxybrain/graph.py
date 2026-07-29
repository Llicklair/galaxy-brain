"""Acoplamiento por el grafo de imports. v3, primer incremento.

Determinista, cero modelos, cero dependencias (solo `ast`/stdlib). Devuelve el
MAPA de acoplamiento del proyecto — quién importa a quién, qué ciclos hay, qué
módulos están más acoplados. No dicta: muestra. Un ciclo de imports es un HECHO,
no una opinión, y por eso casi no tiene falsos positivos (ARCHITECTURE-v2, la
condición de calidad de v3: una gate que chilla sin motivo acaba en --no-verify).

Conecta con el §9 de las conclusiones: lo que cambia todo es que el almacén
tenga forma; un grafo responde "¿quién depende de X?" con aristas, no con
ficheros enteros.

Límites honestos, dichos de frente: es análisis ESTÁTICO. No ve imports
dinámicos (`__import__`, `importlib.import_module`), y cuenta los imports dentro
de `if TYPE_CHECKING:` o de funciones como aristas aunque no sean dependencias
de runtime. Es un grafo de acoplamiento a nivel de módulo, no un call graph.
"""

import ast
import os

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


def _iter_py_files(root, skip):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip and not d.startswith(".")]
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


def _import_targets(tree, this_module):
    """Módulos que este AST importa (nombres punteados), resolviendo relativos.

    Para `from pkg import x` añade tanto `pkg` como `pkg.x`, porque `x` puede ser
    un submódulo o un nombre; el filtrado posterior contra el conjunto de módulos
    reales del proyecto se queda solo con los que son módulos de verdad.
    """
    targets = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                targets.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            base = _resolve_base(node, this_module)
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


def _resolve_base(node, this_module):
    """El módulo base de un `from ... import` (absoluto o relativo)."""
    if node.level == 0:
        return node.module or ""
    # Relativo: subir `level` desde el PAQUETE que contiene este módulo.
    parts = this_module.split(".")
    container = parts[:-1]  # paquete contenedor de this_module
    up = node.level - 1  # nivel 1 = mismo paquete; cada nivel extra sube uno más
    if up > len(container):
        return None
    if up:
        container = container[: len(container) - up]
    prefix = ".".join(container)
    if node.module:
        return (prefix + "." + node.module) if prefix else node.module
    return prefix


def build_graph(root, skip=DEFAULT_SKIP):
    """Construye el grafo de imports INTERNOS del proyecto en `root`.

    Devuelve (nodes, edges, errors):
      - nodes: set de nombres de módulo del proyecto
      - edges: dict módulo -> set de módulos internos que importa (sin auto-aristas)
      - errors: dict fichero -> mensaje (ficheros que no parsean)
    """
    items = []
    for path in _iter_py_files(root, skip):
        mod = module_name(path, root)
        if not mod:
            continue
        try:
            with open(path, "r", encoding="utf-8") as handle:
                text = handle.read()
        except OSError:
            text = None
        items.append((mod, path, text))
    return _graph_from_sources(items)


def _graph_from_sources(items):
    """Núcleo compartido: grafo a partir de (módulo, ubicación, texto).

    `items`: iterable de (module_name, location, source_or_None). location es la
    ruta (de fichero o de git) que se usa como clave de error, para que el aviso
    apunte a algo que un humano reconozca.
    """
    nodes = {mod for mod, _loc, _text in items}
    edges = {}
    errors = {}
    for mod, loc, text in items:
        if text is None:
            errors[loc] = "no se pudo leer"
            edges[mod] = set()
            continue
        try:
            tree = ast.parse(text, filename=loc)
        except (SyntaxError, ValueError) as error:
            errors[loc] = "%s: %s" % (type(error).__name__, error)
            edges[mod] = set()
            continue
        internal = {_to_internal(t, nodes) for t in _import_targets(tree, mod)}
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
        result = subprocess.run(
            ["git", "-C", cwd, *args],
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


def build_graph_from_git(root, ref, skip=DEFAULT_SKIP):
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
    rel = os.path.relpath(root, repo).replace("\\", "/")
    args = ["ls-tree", "-r", "--name-only", ref]
    if rel not in (".", ""):
        args += ["--", rel]
    listing = _git(repo, *args)
    if listing is None:
        return None

    items = []
    for gitpath in listing.splitlines():
        gitpath = gitpath.strip()
        if not gitpath.endswith(".py"):
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
        items.append((mod, gitpath, text))
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


def analyze(root, skip=DEFAULT_SKIP, since=None):
    """El informe del acoplamiento del proyecto.

    Si `since` es una ref de git, añade el delta: qué acoplamiento cíclico es
    NUEVO respecto a esa baseline (a nivel de pares co-cíclicos, para no dar
    falsos positivos cuando un ciclo simplemente encoge).
    """
    nodes, edges, errors = build_graph(root, skip)
    fan_out = {mod: len(deps) for mod, deps in edges.items()}
    fan_in = {mod: 0 for mod in nodes}
    for deps in edges.values():
        for dep in deps:
            fan_in[dep] = fan_in.get(dep, 0) + 1
    cycles = find_cycles(edges)
    edge_count = sum(len(d) for d in edges.values())
    report = {
        "root": root,
        "modules": len(nodes),
        "edges": edge_count,
        "cycles": cycles,
        "fan_in": fan_in,
        "fan_out": fan_out,
        "errors": errors,
        "since": since,
        "baseline_ok": None,
        "new_cycles": [],
        "new_pairs": [],
    }
    if since is not None:
        base = build_graph_from_git(root, since, skip)
        if base is None:
            report["baseline_ok"] = False
        else:
            _bn, base_edges, _be = base
            base_pairs = cyclic_pairs(find_cycles(base_edges))
            new_pairs = cyclic_pairs(cycles) - base_pairs
            report["baseline_ok"] = True
            report["new_pairs"] = [sorted(p) for p in new_pairs]
            report["new_cycles"] = [
                c
                for c in cycles
                if any(
                    frozenset((c[i], c[j])) in new_pairs
                    for i in range(len(c))
                    for j in range(i + 1, len(c))
                )
            ]
    return report
