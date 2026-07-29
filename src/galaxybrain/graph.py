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
    files = {}
    for path in _iter_py_files(root, skip):
        mod = module_name(path, root)
        if mod:
            files[mod] = path
    nodes = set(files)

    edges = {}
    errors = {}
    for mod, path in files.items():
        try:
            with open(path, "r", encoding="utf-8") as handle:
                tree = ast.parse(handle.read(), filename=path)
        except (OSError, SyntaxError, ValueError) as error:
            errors[path] = "%s: %s" % (type(error).__name__, error)
            continue
        raw = _import_targets(tree, mod)
        internal = {_to_internal(t, nodes) for t in raw}
        internal.discard(None)
        internal.discard(mod)  # sin auto-aristas
        edges[mod] = internal
    for mod in nodes:
        edges.setdefault(mod, set())
    return nodes, edges, errors


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


def analyze(root, skip=DEFAULT_SKIP):
    """El informe completo del acoplamiento del proyecto."""
    nodes, edges, errors = build_graph(root, skip)
    fan_out = {mod: len(deps) for mod, deps in edges.items()}
    fan_in = {mod: 0 for mod in nodes}
    for deps in edges.values():
        for dep in deps:
            fan_in[dep] = fan_in.get(dep, 0) + 1
    cycles = find_cycles(edges)
    edge_count = sum(len(d) for d in edges.values())
    return {
        "root": root,
        "modules": len(nodes),
        "edges": edge_count,
        "cycles": cycles,
        "fan_in": fan_in,
        "fan_out": fan_out,
        "errors": errors,
    }
