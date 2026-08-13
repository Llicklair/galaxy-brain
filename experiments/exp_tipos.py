"""exp_tipos.py — Experimento: detección de cambios en return type annotations.

Pregunta a responder: ¿es viable usar cambios en anotaciones de tipo de retorno
como señal de riesgo en galaxy-brain?

Cuando una función cambia su tipo de retorno (p.ej. `list` → `Optional[list]`),
los callers que asumen el tipo antiguo pueden romperse silenciosamente.

Uso:
    python experiments/exp_tipos.py <directorio>

Produce:
    - Conteo de funciones con/sin anotación de retorno (cobertura)
    - Ejemplo simulado de cambio de tipo y qué flagearía el detector
    - Veredicto sobre viabilidad de la señal
"""

import ast
import os
import sys
import copy
from typing import Optional


# ---------------------------------------------------------------------------
# 1. Extracción de return type annotations via AST
# ---------------------------------------------------------------------------

def _annotation_text(node: Optional[ast.expr]) -> Optional[str]:
    """Convierte un nodo de anotación AST a texto legible. None si no hay anotación."""
    if node is None:
        return None
    try:
        return ast.unparse(node)
    except Exception:
        return repr(node)


def extract_return_types(source: str, filename: str = "<unknown>") -> dict:
    """Extrae las anotaciones de retorno de todas las funciones en `source`.

    Devuelve:
        {
          "qual_name": {          # e.g. "MiClase.mi_metodo" o "funcion_suelta"
            "return_type": str | None,
            "line": int,
            "has_annotation": bool,
          },
          ...
        }
    """
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as e:
        print(f"  [WARN] SyntaxError en {filename}: {e}")
        return {}

    results = {}

    def _visit_func(node, prefix=""):
        qual = (prefix + "." + node.name) if prefix else node.name
        ann = _annotation_text(node.returns)
        results[qual] = {
            "return_type": ann,
            "line": node.lineno,
            "has_annotation": ann is not None,
        }
        # Funciones anidadas (depth 1 extra, best-effort)
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                _visit_func(child, prefix=qual)

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _visit_func(node)
        elif isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    _visit_func(child, prefix=node.name)

    return results


# ---------------------------------------------------------------------------
# 2. Comparar dos versiones de return types
# ---------------------------------------------------------------------------

def diff_return_types(before: dict, after: dict) -> list[dict]:
    """Compara los tipos de retorno entre dos versiones y devuelve los cambios.

    Solo reporta funciones donde la anotación CAMBIÓ (incluyendo None → algo
    o algo → None, que también es un cambio de contrato).
    """
    changes = []
    all_names = set(before) | set(after)

    for name in sorted(all_names):
        b = before.get(name)
        a = after.get(name)

        if b is None and a is not None:
            # Función nueva con anotación
            changes.append({
                "name": name,
                "kind": "new_function",
                "before": None,
                "after": a["return_type"],
                "line": a["line"],
            })
            continue
        if b is not None and a is None:
            # Función eliminada
            changes.append({
                "name": name,
                "kind": "deleted_function",
                "before": b["return_type"],
                "after": None,
                "line": b["line"],
            })
            continue

        # Ambas existen: comparar anotación
        type_before = b["return_type"]
        type_after = a["return_type"]

        if type_before != type_after:
            changes.append({
                "name": name,
                "kind": "return_type_changed",
                "before": type_before,
                "after": type_after,
                "line": a["line"],
            })

    return changes


# ---------------------------------------------------------------------------
# 3. Heurística de riesgo: ¿el cambio puede romper callers?
# ---------------------------------------------------------------------------

def risk_level(change: dict) -> str:
    """Clasifica el riesgo de un cambio de tipo de retorno.

    HIGH:   cambio que introduce None (Optional, Union con None) donde antes no había.
            Un caller que haga `.attribute` o indexing sin None-check va a explotar.
    MEDIUM: cambio a un tipo más restrictivo o totalmente diferente.
    LOW:    añadir anotación donde no había (no cambia runtime).
    INFO:   función nueva o eliminada.
    """
    b = change["before"]
    a = change["after"]
    kind = change["kind"]

    if kind in ("new_function", "deleted_function"):
        return "INFO"

    # Antes no había anotación, ahora hay: no rompe callers (solo documentación)
    if b is None and a is not None:
        return "LOW"

    # Antes había, ahora se quitó: pérdida de información de tipo
    if b is not None and a is None:
        return "MEDIUM"

    # El cambio más peligroso: introducir Optional/None donde no había
    introduces_none = (
        a is not None and (
            "None" in a or
            a.startswith("Optional[") or
            ("Union" in a and "None" in a)
        )
    ) and (b is not None and "None" not in b and "Optional" not in b)

    if introduces_none:
        return "HIGH"

    # Cambio de tipo a algo completamente distinto
    return "MEDIUM"


# ---------------------------------------------------------------------------
# 4. Escaneo de un directorio
# ---------------------------------------------------------------------------

def scan_directory(dirpath: str) -> tuple[dict, dict]:
    """Escanea todos los .py en `dirpath` y retorna (por_archivo, stats_globales).

    por_archivo: { "rel/path.py": { qual_name: {...} } }
    stats: { "total_functions": int, "with_annotation": int, "files": int }
    """
    por_archivo = {}
    total_funcs = 0
    with_ann = 0
    files = 0

    for root, dirs, fnames in os.walk(dirpath):
        # Saltar __pycache__
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for fname in sorted(fnames):
            if not fname.endswith(".py"):
                continue
            fpath = os.path.join(root, fname)
            relpath = os.path.relpath(fpath, dirpath).replace(os.sep, "/")
            try:
                with open(fpath, "r", encoding="utf-8-sig", errors="replace") as f:
                    source = f.read()
            except OSError as e:
                print(f"  [WARN] No se pudo leer {relpath}: {e}")
                continue

            funcs = extract_return_types(source, filename=relpath)
            por_archivo[relpath] = funcs
            files += 1
            total_funcs += len(funcs)
            with_ann += sum(1 for v in funcs.values() if v["has_annotation"])

    stats = {
        "total_functions": total_funcs,
        "with_annotation": with_ann,
        "without_annotation": total_funcs - with_ann,
        "files": files,
        "coverage_pct": (with_ann / total_funcs * 100) if total_funcs else 0.0,
    }
    return por_archivo, stats


# ---------------------------------------------------------------------------
# 5. Simulación de cambio deliberado
# ---------------------------------------------------------------------------

SIMULATION_PATCH = {
    # (archivo_relativo, funcion_qualname): nuevo tipo de retorno simulado
    # Se elige el primer archivo con funciones anotadas que encontremos
    # y se modifica en memoria para el diff. Ver _run_simulation().
}


def _run_simulation(por_archivo: dict) -> list[dict]:
    """Simula un cambio de tipo en la función más representativa que encontremos.

    Estrategia: busca la primera función con return type annotation concreta
    (no None) y simula cambiarla a Optional[<tipo_original>].
    """
    target_file = None
    target_func = None
    original_type = None

    for relpath, funcs in sorted(por_archivo.items()):
        for name, info in sorted(funcs.items()):
            if info["has_annotation"] and info["return_type"] not in (None, "None"):
                target_file = relpath
                target_func = name
                original_type = info["return_type"]
                break
        if target_file:
            break

    if not target_file:
        return []

    # Estado "antes": la anotación real
    before_funcs = por_archivo[target_file]

    # Estado "después": simular Optional wrapping
    new_type = f"Optional[{original_type}]"
    after_funcs = copy.deepcopy(before_funcs)
    after_funcs[target_func]["return_type"] = new_type

    changes = diff_return_types(before_funcs, after_funcs)

    # Anotar con info de simulación para el reporte
    for c in changes:
        c["simulated"] = True
        c["file"] = target_file

    return changes, target_file, target_func, original_type, new_type


# ---------------------------------------------------------------------------
# 6. Main / reporte
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        # Default: intentar con la ruta hardcodeada del experimento
        target = r"C:/Users/Marcos/Desktop/live code/src/guardia"
        print(f"No se especificó directorio; usando default: {target}\n")
    else:
        target = sys.argv[1]

    if not os.path.isdir(target):
        print(f"ERROR: '{target}' no es un directorio válido.")
        sys.exit(1)

    print("=" * 70)
    print("exp_tipos.py — Detector de cambios en return type annotations")
    print("=" * 70)
    print(f"Directorio analizado: {target}\n")

    # --- Escaneo ---
    por_archivo, stats = scan_directory(target)

    print("COBERTURA DE ANOTACIONES")
    print("-" * 40)
    print(f"  Archivos .py escaneados : {stats['files']}")
    print(f"  Funciones totales       : {stats['total_functions']}")
    print(f"  Con anotación retorno   : {stats['with_annotation']}")
    print(f"  Sin anotación retorno   : {stats['without_annotation']}")
    print(f"  Cobertura               : {stats['coverage_pct']:.1f}%")
    print()

    # Desglose por archivo
    print("DESGLOSE POR ARCHIVO")
    print("-" * 40)
    for relpath, funcs in sorted(por_archivo.items()):
        total = len(funcs)
        ann = sum(1 for v in funcs.values() if v["has_annotation"])
        pct = (ann / total * 100) if total else 0.0
        bar = "█" * int(pct / 10) + "░" * (10 - int(pct / 10))
        print(f"  {relpath:<30s} {ann:>3}/{total:<3} [{bar}] {pct:4.0f}%")

    print()

    # Muestra de las anotaciones encontradas
    print("MUESTRA DE ANOTACIONES ENCONTRADAS")
    print("-" * 40)
    shown = 0
    for relpath, funcs in sorted(por_archivo.items()):
        for name, info in sorted(funcs.items()):
            if info["has_annotation"]:
                print(f"  {relpath}::{name}  →  {info['return_type']}  (línea {info['line']})")
                shown += 1
                if shown >= 20:
                    remaining = sum(
                        1 for f in por_archivo.values()
                        for v in f.values() if v["has_annotation"]
                    ) - shown
                    if remaining > 0:
                        print(f"  ... y {remaining} más")
                    break
        if shown >= 20:
            break

    print()

    # --- Simulación de cambio ---
    print("SIMULACIÓN DE CAMBIO DE TIPO")
    print("-" * 40)

    sim_result = _run_simulation(por_archivo)
    if not sim_result:
        print("  No se encontraron funciones con anotación para simular.")
    else:
        changes, sim_file, sim_func, orig_type, new_type = sim_result
        print(f"  Archivo  : {sim_file}")
        print(f"  Función  : {sim_func}")
        print(f"  Antes    : -> {orig_type}")
        print(f"  Después  : -> {new_type}  (simulado)")
        print()
        print("  Cambios detectados por el diff:")
        for c in changes:
            risk = risk_level(c)
            print(f"    [{risk}] {c['name']}")
            print(f"           antes  : {c['before']}")
            print(f"           después: {c['after']}")
            print(f"           línea  : {c['line']}")
            print()

        print("  Lo que haría un checker real con esta señal:")
        print("    - Buscar todos los callers de esta función en el grafo de gb")
        print("    - Para cada caller, analizar si hace `.attribute` o `[index]`")
        print("      sobre el valor de retorno sin un None-check previo")
        print("    - Flagear como 'potencialmente roto' si asume tipo no-None")
        print()

    # --- Veredicto ---
    print("VEREDICTO: ¿ES VIABLE ESTA SEÑAL?")
    print("-" * 40)

    coverage = stats["coverage_pct"]
    total = stats["total_functions"]
    ann = stats["with_annotation"]

    if total == 0:
        verdict = "BLOQUEADO"
        reason = "No se encontraron funciones Python."
    elif coverage >= 60:
        verdict = "VIABLE"
        reason = (
            f"{coverage:.0f}% de cobertura de anotaciones es suficiente para "
            "generar señales útiles. El extractor AST funciona limpiamente."
        )
    elif coverage >= 30:
        verdict = "PARCIALMENTE VIABLE"
        reason = (
            f"{coverage:.0f}% de cobertura. Señal útil en las partes anotadas, "
            "pero hay un punto ciego grande. Combinar con mypy o pyright para "
            "inferir tipos donde faltan."
        )
    else:
        verdict = "COBERTURA BAJA"
        reason = (
            f"Solo {coverage:.0f}% de funciones tienen anotaciones ({ann}/{total}). "
            "La señal existiría pero cubriría muy poco. El proyecto necesita más "
            "type annotations para que este detector aporte valor real."
        )

    print(f"  Veredicto : {verdict}")
    print(f"  Razón     : {reason}")
    print()
    print("  Bloqueos técnicos identificados:")
    print("    1. NINGUNO para extracción AST pura — ast.unparse() funciona limpio")
    print("       sobre cualquier sintaxis de anotación (str, Optional, Union, etc.)")
    print("    2. LIMITACIÓN: anotaciones en formato string ('NombreTipo') requieren")
    print("       evaluación diferida (PEP 563 / __future__ annotations). El texto")
    print("       se extrae igual, pero la comparación es léxica, no semántica.")
    print("    3. LIMITACIÓN: tipos inferidos (sin anotación) son invisibles. Para")
    print("       un proyecto sin anotaciones, esta señal es ciega.")
    print("    4. OPORTUNIDAD: integración natural con gb — el grafo ya tiene las")
    print("       aristas CALLS. Añadir 'return_type' a cada nodo de función costaría")
    print("       ~15 líneas en symbols.py (_scan_module + _firma).")
    print()
    print("=" * 70)


if __name__ == "__main__":
    main()
