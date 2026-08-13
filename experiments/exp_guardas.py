"""exp_guardas.py — Detector de guardas eliminadas (experimento gb).

Una guarda es un if al principio del cuerpo de una función cuyo cuerpo
es un único raise o return. Eliminarla amplía silenciosamente el dominio
de entrada de la función. Este script detecta guardas en un directorio y
simula qué marcaría un detector de *eliminación* al comparar dos versiones.

Uso:
    python exp_guardas.py <directorio> [<directorio2> ...]
    python exp_guardas.py  (usa los dos directorios hardcodeados por defecto)
"""

import ast
import os
import sys
import textwrap
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Tipos
# ---------------------------------------------------------------------------

@dataclass
class Guarda:
    funcion: str
    linea: int
    patron: str          # "raise", "return", "raise <Tipo>", etc.
    texto: str           # fragmento de código (for display)
    posicion: int        # índice dentro del cuerpo de la función (0 = primera)
    archivo: str


@dataclass
class ResultadoArchivo:
    ruta: str
    guardas: list[Guarda] = field(default_factory=list)
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Detección AST
# ---------------------------------------------------------------------------

_MAX_POSICION = 3   # solo miramos las primeras N sentencias del cuerpo


def _es_guarda(stmt) -> Optional[str]:
    """¿Es esta sentencia una guarda de precondición?

    Criterio: if con cuerpo de UNA sola sentencia que sea raise o return.
    El else/elif amplía el contrato en vez de restringirlo — no es guarda.
    Retorna una descripción corta del patrón o None.
    """
    if not isinstance(stmt, ast.If):
        return None
    # Si tiene else/elif probablemente no sea una guarda de entrada
    if stmt.orelse:
        return None
    if len(stmt.body) != 1:
        return None
    cuerpo = stmt.body[0]
    if isinstance(cuerpo, ast.Raise):
        exc = cuerpo.exc
        if exc is None:
            return "raise (re-raise)"
        if isinstance(exc, ast.Call) and isinstance(exc.func, ast.Name):
            return f"raise {exc.func.id}(...)"
        if isinstance(exc, ast.Name):
            return f"raise {exc.id}"
        return "raise <expr>"
    if isinstance(cuerpo, ast.Return):
        val = cuerpo.value
        if val is None:
            return "return"
        if isinstance(val, ast.Constant) and val.value is None:
            return "return None"
        return "return <valor>"
    return None


def _texto_if(lines: list[str], linea: int) -> str:
    """Extrae el texto del if (hasta 3 líneas) para mostrarlo."""
    idx = linea - 1
    fragmento = lines[idx : idx + 3]
    return " | ".join(l.rstrip() for l in fragmento)


def _guardas_en_funcion(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    lines: list[str],
    ruta: str,
) -> list[Guarda]:
    guardas = []
    cuerpo = node.body
    # Saltar docstring inicial
    inicio = 0
    if cuerpo and isinstance(cuerpo[0], ast.Expr) and isinstance(cuerpo[0].value, ast.Constant):
        inicio = 1
    for i, stmt in enumerate(cuerpo[inicio : inicio + _MAX_POSICION], start=inicio):
        patron = _es_guarda(stmt)
        if patron:
            guardas.append(Guarda(
                funcion=node.name,
                linea=stmt.lineno,
                patron=patron,
                texto=_texto_if(lines, stmt.lineno),
                posicion=i,
                archivo=ruta,
            ))
    return guardas


class _VisitanteGuardas(ast.NodeVisitor):
    def __init__(self, lines: list[str], ruta: str):
        self.lines = lines
        self.ruta = ruta
        self.guardas: list[Guarda] = []

    def _visitar_funcion(self, node):
        self.guardas.extend(_guardas_en_funcion(node, self.lines, self.ruta))
        self.generic_visit(node)

    visit_FunctionDef = _visitar_funcion
    visit_AsyncFunctionDef = _visitar_funcion


def analizar_archivo(ruta: str) -> ResultadoArchivo:
    resultado = ResultadoArchivo(ruta=ruta)
    try:
        with open(ruta, encoding="utf-8-sig", errors="replace") as f:
            texto = f.read()
    except OSError as e:
        resultado.error = str(e)
        return resultado
    try:
        arbol = ast.parse(texto, filename=ruta)
    except SyntaxError as e:
        resultado.error = f"SyntaxError: {e}"
        return resultado
    lines = texto.splitlines()
    visitante = _VisitanteGuardas(lines, ruta)
    visitante.visit(arbol)
    resultado.guardas = visitante.guardas
    return resultado


def analizar_directorio(directorio: str) -> list[ResultadoArchivo]:
    resultados = []
    for dirpath, _dirs, files in os.walk(directorio):
        for fname in sorted(files):
            if fname.endswith(".py"):
                ruta = os.path.join(dirpath, fname)
                resultados.append(analizar_archivo(ruta))
    return resultados


# ---------------------------------------------------------------------------
# Simulación de detección de ELIMINACIÓN
# ---------------------------------------------------------------------------

def simular_eliminacion(guardas_antes: list[Guarda], guardas_despues: list[Guarda]) -> list[dict]:
    """Qué guardas de `antes` ya no existen en `despues` (por función + patrón).

    Usa la misma lógica de _nuevas() de delta.py: compara por TEXTO (patrón)
    dentro de la misma función, no por número de línea, para evitar falsos
    positivos cuando el código se mueve.
    """
    # Construir multiset de (funcion, patron) en `despues`
    cuenta: dict[tuple, int] = {}
    for g in guardas_despues:
        k = (g.funcion, g.patron)
        cuenta[k] = cuenta.get(k, 0) + 1

    eliminadas = []
    for g in guardas_antes:
        k = (g.funcion, g.patron)
        if cuenta.get(k, 0) > 0:
            cuenta[k] -= 1
        else:
            eliminadas.append({
                "funcion": g.funcion,
                "linea_antes": g.linea,
                "patron": g.patron,
                "archivo": g.archivo,
                "texto": g.texto,
            })
    return eliminadas


# ---------------------------------------------------------------------------
# Presentación
# ---------------------------------------------------------------------------

_SEP = "─" * 72


def _ruta_corta(ruta: str, base: str) -> str:
    try:
        return os.path.relpath(ruta, base)
    except ValueError:
        return ruta


def imprimir_resultados(resultados: list[ResultadoArchivo], base: str, titulo: str):
    total_guardas = sum(len(r.guardas) for r in resultados)
    archivos_con_guardas = [r for r in resultados if r.guardas]
    errores = [r for r in resultados if r.error]

    print(f"\n{'═' * 72}")
    print(f"  {titulo}")
    print(f"{'═' * 72}")
    print(f"  Archivos analizados : {len(resultados)}")
    print(f"  Archivos con guardas: {len(archivos_con_guardas)}")
    print(f"  Total de guardas    : {total_guardas}")
    if errores:
        print(f"  Errores de parse    : {len(errores)}")
    print()

    if not archivos_con_guardas:
        print("  (ninguna guarda encontrada)")
        return

    for r in archivos_con_guardas:
        corta = _ruta_corta(r.ruta, base)
        print(f"  {_SEP}")
        print(f"  {corta}  ({len(r.guardas)} guarda{'s' if len(r.guardas) != 1 else ''})")
        for g in r.guardas:
            print(f"    L{g.linea:<5} {g.funcion}()  [{g.patron}]")
            wrapped = textwrap.wrap(g.texto, width=64)
            for line in wrapped:
                print(f"           {line}")
        print()


def imprimir_simulacion_eliminacion(
    guardas_v1: list[Guarda],
    guardas_v2: list[Guarda],
    base: str,
):
    """Muestra qué marcaría gb si v1→v2 fuera un diff."""
    eliminadas = simular_eliminacion(guardas_v1, guardas_v2)
    print(f"\n{'═' * 72}")
    print("  SIMULACIÓN: guardas eliminadas (v1 → v2 del mismo codebase)")
    print(f"{'═' * 72}")
    if not eliminadas:
        print("  (ninguna guarda eliminada en la simulación)")
        return
    for e in eliminadas:
        corta = _ruta_corta(e["archivo"], base)
        print(f"  ELIMINADA: {corta}:{e['linea_antes']}  {e['funcion']}()  [{e['patron']}]")
        print(f"    era: {e['texto'][:80]}")
    print()


# ---------------------------------------------------------------------------
# Demo de eliminación sintética (ilustra el mecanismo sin necesitar git)
# ---------------------------------------------------------------------------

_CODIGO_V1 = textwrap.dedent("""\
    def procesar(datos):
        if datos is None:
            raise ValueError("datos no puede ser None")
        if len(datos) == 0:
            return
        return sum(datos)

    def cargar(ruta):
        if not ruta:
            raise TypeError("ruta vacía")
        with open(ruta) as f:
            return f.read()
""")

_CODIGO_V2 = textwrap.dedent("""\
    def procesar(datos):
        # guarda de None eliminada — ahora acepta None silenciosamente
        if len(datos) == 0:
            return
        return sum(datos)

    def cargar(ruta):
        if not ruta:
            raise TypeError("ruta vacía")
        with open(ruta) as f:
            return f.read()
""")


def demo_sintetica():
    print(f"\n{'═' * 72}")
    print("  DEMO SINTÉTICA: así se vería una detección en un diff real")
    print(f"{'═' * 72}")

    def _guardas_texto(codigo: str, nombre: str) -> list[Guarda]:
        arbol = ast.parse(codigo)
        lines = codigo.splitlines()
        v = _VisitanteGuardas(lines, nombre)
        v.visit(arbol)
        return v.guardas

    g_v1 = _guardas_texto(_CODIGO_V1, "<v1>")
    g_v2 = _guardas_texto(_CODIGO_V2, "<v2>")

    print("\n  Código v1 (guardas presentes):")
    print(textwrap.indent(_CODIGO_V1.rstrip(), "    "))
    print("\n  Código v2 (una guarda eliminada):")
    print(textwrap.indent(_CODIGO_V2.rstrip(), "    "))

    print(f"\n  Guardas en v1: {len(g_v1)}")
    for g in g_v1:
        print(f"    {g.funcion}() L{g.linea} [{g.patron}]")
    print(f"\n  Guardas en v2: {len(g_v2)}")
    for g in g_v2:
        print(f"    {g.funcion}() L{g.linea} [{g.patron}]")

    eliminadas = simular_eliminacion(g_v1, g_v2)
    print(f"\n  gb marcaría {len(eliminadas)} eliminación(es):")
    for e in eliminadas:
        print(f"    ⚠  {e['funcion']}() eliminó [{e['patron']}]")
        print(f"       era: {e['texto']}")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

DIRECTORIOS_DEFAULT = [
    r"C:\Users\Marcos\Desktop\live code\src\guardia",
    r"C:\Users\Marcos\Desktop\galaxy-brain\src\galaxybrain",
]


def main():
    dirs = sys.argv[1:] if len(sys.argv) > 1 else DIRECTORIOS_DEFAULT

    todos_los_resultados: dict[str, list[ResultadoArchivo]] = {}

    for d in dirs:
        if not os.path.isdir(d):
            print(f"AVISO: directorio no encontrado: {d}")
            continue
        resultados = analizar_directorio(d)
        todos_los_resultados[d] = resultados
        imprimir_resultados(resultados, d, f"Directorio: {d}")

    # Simulación: si hay 2+ directorios, comparamos el primero consigo mismo
    # con una guardia sintéticamente "eliminada" para ilustrar el detector.
    # (En producción, v1 y v2 serían el mismo árbol en dos commits.)
    if len(todos_los_resultados) >= 1:
        demo_sintetica()

    # Resumen global
    print(f"\n{'═' * 72}")
    print("  RESUMEN GLOBAL")
    print(f"{'═' * 72}")
    total = 0
    for d, resultados in todos_los_resultados.items():
        n = sum(len(r.guardas) for r in resultados)
        total += n
        archivos = len([r for r in resultados if r.guardas])
        print(f"  {os.path.basename(d):<30}  {n:>3} guardas en {archivos} archivos")
    print(f"  {'TOTAL':<30}  {total:>3} guardas")
    print()

    # Viabilidad
    print(f"{'═' * 72}")
    print("  EVALUACIÓN DE VIABILIDAD")
    print(f"{'═' * 72}")
    if total == 0:
        densidad = "señal MUY RARA"
    elif total < 10:
        densidad = "señal escasa — posible nicho de alto valor"
    elif total < 30:
        densidad = "señal moderada — viable con umbral bajo"
    else:
        densidad = "señal densa — cuidado con el ruido"
    print(f"  Densidad: {densidad} ({total} guardas en {sum(len(v) for v in todos_los_resultados.values())} archivos)")
    print("""
  Consideraciones:
  - Las guardas de tipo 'raise <Tipo>' son las más valiosas: su eliminación
    amplía el contrato silenciosamente y puede causar errores tardíos.
  - Las de tipo 'return' son más ambiguas (pueden ser early-exits normales).
  - Comparar por (funcion, patron) en vez de por línea evita los falsos
    positivos por renumeración (misma lógica que delta._nuevas).
  - La señal es RARA comparada con silencios/broadcastings, pero de ALTA
    especificidad: un programador que quita una guarda rara vez lo hace
    por accidente. Vale la pena capturarla.
  - Recomendación: añadir como detector opcional en delta.py, igual que
    'crecidos' (informa, nunca gatekeepa).
""")


if __name__ == "__main__":
    main()
