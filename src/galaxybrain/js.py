"""El grafo de JS/TS, derivado con `ast-grep` por referencia (ADR 0009).

Devuelve **la misma forma de informe** que el motor de Python (`symbols.analyze`):
`nodes`, `edges`, contadores de llamadas y `unresolved` por causa. Ese es el punto
entero — el 74 % del código de gb (el mapa, la CLI, el almacén, el suelo) opera
sobre el grafo ya derivado y no debe enterarse del lenguaje. Dos motores que
conviven, no uno genérico peor que ambos.

Por qué un binario externo y no un parser propio ni una dependencia Python: no
vendorizar es regla 7, y una dependencia Python rompería el "cero dependencias"
que hace la instalación trivial. El precio, declarado en SCOPE: quien use JS
instala `ast-grep`; quien use Python no instala nada.

Límites, dichos de frente igual que en la vía Python (ADR 0008): es análisis
ESTÁTICO por patrón. No resuelve llamadas sobre variables (`obj.metodo()`), no
sigue `require()` dinámico ni reexports, y no distingue dos símbolos homónimos en
módulos distintos salvo por el import que los trae. Todo eso **se cuenta y se
declara**; no se adivina.
"""

import json
import os
import shutil
import subprocess

#: Extensiones que este motor cubre, con el lenguaje que ast-grep debe usar.
EXTENSIONES = {
    ".js": "js", ".mjs": "js", ".cjs": "js", ".jsx": "jsx",
    ".ts": "ts", ".tsx": "tsx",
}

#: Directorios que nunca son código del proyecto.
SKIP = frozenset(("node_modules", "dist", "build", "coverage", ".next", "out", "vendor"))

#: Patrones de DEFINICIÓN. Se corren todos y se deduplica por (fichero, línea):
#: `export function f(){}` casa tanto con el patrón exportado como con el simple,
#: y contar dos veces el mismo símbolo inflaría el grafo.
PATRONES_SIMBOLO = (
    ("function", "export function $NAME($$$) { $$$ }"),
    ("function", "function $NAME($$$) { $$$ }"),
    ("function", "export default function $NAME($$$) { $$$ }"),
    ("function", "export const $NAME = ($$$) => { $$$ }"),
    ("function", "const $NAME = ($$$) => { $$$ }"),
    ("function", "export async function $NAME($$$) { $$$ }"),
    ("function", "async function $NAME($$$) { $$$ }"),
    ("class", "export class $NAME { $$$ }"),
    ("class", "class $NAME { $$$ }"),
)

#: Patrones de IMPORT. `$SRC` es el especificador tal cual lo escribió el autor.
PATRONES_IMPORT = (
    'import { $$$ } from "$SRC"',
    'import $NAME from "$SRC"',
    'import * as $NAME from "$SRC"',
    'import "$SRC"',
    'require("$SRC")',
)

#: Patrón de LLAMADA. Uno solo: `$FN($$$)` casa cualquier invocación, y el
#: trabajo de decidir cuáles se pueden resolver se hace después, con nombres.
PATRON_LLAMADA = "$FN($$$)"

#: Globales del runtime que no son símbolos del proyecto. Equivalen a los
#: builtins de Python: se excluyen del denominador para que el porcentaje de
#: resolución signifique algo.
GLOBALES = frozenset((
    "console", "require", "setTimeout", "setInterval", "clearTimeout", "clearInterval",
    "fetch", "parseInt", "parseFloat", "isNaN", "String", "Number", "Boolean", "Array",
    "Object", "JSON", "Math", "Date", "Promise", "Error", "Symbol", "Map", "Set",
    "RegExp", "encodeURIComponent", "decodeURIComponent", "structuredClone", "queueMicrotask",
    # el vocabulario de los runners de test, que si no domina el recuento
    "describe", "it", "test", "expect", "beforeEach", "afterEach", "beforeAll", "afterAll",
    "vi", "jest", "assert",
))


# --- el binario: detectar, y verificar EJECUTANDO (regla 7) ------------------


def binario():
    """Ruta del ejecutable de ast-grep, o None.

    `shutil.which` y no confiar en el PATH del shell: en Windows ast-grep es un
    shim `.CMD` de npm y `subprocess(["ast-grep", ...])` da WinError 2 aunque en
    la terminal funcione. Es el 'instalado != funcional' de la regla 7, y se
    reprodujo el 8-ago montando el primer proyecto JS.
    """
    for nombre in ("ast-grep", "sg"):
        ruta = shutil.which(nombre)
        if ruta:
            return ruta
    return None


def disponible():
    """(ruta, version) si el binario responde de verdad, o (None, motivo).

    Detectarlo no basta: se ejecuta. Un shim roto o un binario de otra
    arquitectura existen en el PATH y no sirven.
    """
    ruta = binario()
    if not ruta:
        return None, "ast-grep no esta instalado (https://ast-grep.github.io)"
    try:
        p = subprocess.run([ruta, "--version"], capture_output=True, timeout=20)
    except (OSError, subprocess.SubprocessError) as error:
        return None, "ast-grep esta en el PATH pero no ejecuta: %s" % error
    if p.returncode != 0:
        return None, "ast-grep responde con error al invocarlo"
    return ruta, p.stdout.decode("utf-8", "replace").strip()


def _corre(ruta, patron, lenguaje, raiz):
    """Una pasada de ast-grep, devuelta ya parseada. Lista vacía si algo falla:
    un patrón que no casa nada y un patrón mal escrito dan lo mismo aquí, y por
    eso los contadores del informe declaran cuánto se vio — no se infiere."""
    try:
        p = subprocess.run(
            [ruta, "run", "-p", patron, "-l", lenguaje, "--json=compact", raiz],
            capture_output=True, timeout=120,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    salida = p.stdout.decode("utf-8", "replace").strip()
    if not salida:
        return []
    try:
        datos = json.loads(salida)
    except ValueError:
        return []
    return datos if isinstance(datos, list) else []


def _meta(match, nombre):
    return (match.get("metaVariables", {}).get("single", {}).get(nombre, {}) or {}).get("text")


def _linea(match):
    return match.get("range", {}).get("start", {}).get("line", 0) + 1


# --- nombres de modulo ------------------------------------------------------


def module_name(ruta, raiz):
    """Nombre punteado de un fichero JS/TS, con el mismo criterio que la vía
    Python: relativo a la raíz, sin extensión, y descontando `src/` para que
    `src/carrito.js` sea `carrito` y no `src.carrito`."""
    rel = os.path.relpath(ruta, raiz).replace("\\", "/")
    partes = [p for p in rel.split("/") if p and p != "."]
    if partes and partes[0] == "src":
        partes = partes[1:]
    if not partes:
        return ""
    partes[-1] = os.path.splitext(partes[-1])[0]
    if partes[-1] == "index":            # `import "./cosas"` resuelve a cosas/index.js
        partes = partes[:-1]
    return ".".join(partes)


def _resuelve_import(especificador, fichero, raiz, modulos):
    """El módulo interno al que apunta un import, o None si es externo.

    Solo se resuelve lo relativo (`./x`, `../x`): un paquete de node_modules no
    es código de este proyecto y su arista no dice nada del acoplamiento propio.
    """
    if not especificador.startswith("."):
        return None
    base = os.path.dirname(fichero)
    destino = os.path.normpath(os.path.join(base, especificador))
    candidatos = [destino] + [destino + ext for ext in EXTENSIONES]
    candidatos += [os.path.join(destino, "index" + ext) for ext in EXTENSIONES]
    for cand in candidatos:
        nombre = module_name(cand, raiz)
        if nombre in modulos:
            return nombre
    # el fichero puede no existir (import roto) o tener otra extension: se
    # devuelve el nombre derivado igualmente, que es lo que el autor escribio
    derivado = module_name(destino, raiz)
    return derivado if derivado in modulos else None


def _ficheros(raiz):
    fuera = []
    for dirpath, dirnames, filenames in os.walk(raiz):
        dirnames[:] = [d for d in dirnames if d not in SKIP and not d.startswith(".")]
        for name in filenames:
            ext = os.path.splitext(name)[1].lower()
            if ext in EXTENSIONES and not name.endswith(".d.ts"):
                fuera.append(os.path.join(dirpath, name))
    return fuera


def hay_codigo(raiz):
    """¿Hay algo que este motor pueda mirar? Barato, sin invocar el binario."""
    return bool(_ficheros(raiz))


# --- el analisis ------------------------------------------------------------


def analyze(root, lenguajes=("js", "ts")):
    """El informe, con la MISMA forma que `symbols.analyze` de la vía Python.

    `root_error` no vacío significa "no he podido mirar" y ningún consumidor
    debe leerlo como "no hay nada": es la distinción que la Fase 0 dejó fijada.
    """
    root = os.path.abspath(root)
    informe = {
        "root": root, "root_error": "", "nodes": [], "edges": [], "errors": [],
        "calls_total": 0, "calls_candidates": 0, "calls_resolved": 0, "calls_builtin": 0,
        "unresolved": {}, "not_covered": [], "since": None, "baseline_ok": None,
        "new_nodes": [], "gone_nodes": [], "new_calls": [], "motor": "ast-grep",
    }
    if not os.path.isdir(root):
        informe["root_error"] = "no existe: %s" % root
        return informe

    ficheros = _ficheros(root)
    if not ficheros:
        informe["root_error"] = "ni un fichero JS/TS bajo %s" % root
        return informe

    ruta, detalle = disponible()
    if not ruta:
        informe["root_error"] = detalle
        return informe
    informe["motor"] = detalle

    modulos = {}
    for fichero in ficheros:
        nombre = module_name(fichero, root)
        if nombre:
            modulos[nombre] = fichero
    for nombre, fichero in sorted(modulos.items()):
        informe["nodes"].append({
            "qual": nombre, "kind": "module", "module": nombre, "doc": "",
            "file": os.path.relpath(fichero, root), "line": 1, "end": None, "sig": "",
        })

    por_fichero = {os.path.abspath(f): module_name(f, root) for f in ficheros}
    lenguajes_reales = sorted({EXTENSIONES[os.path.splitext(f)[1].lower()] for f in ficheros}
                              & set(lenguajes) or {"js"})

    # --- simbolos ---
    definidos = {}
    vistos = set()
    for lenguaje in lenguajes_reales:
        for kind, patron in PATRONES_SIMBOLO:
            for m in _corre(ruta, patron, lenguaje, root):
                nombre = _meta(m, "NAME")
                fichero = os.path.abspath(os.path.join(root, m.get("file", "")))
                modulo = por_fichero.get(fichero)
                if not nombre or modulo is None:
                    continue
                linea = _linea(m)
                clave = (fichero, linea, nombre)
                if clave in vistos:
                    continue          # `export function f` casa con dos patrones
                vistos.add(clave)
                qual = "%s.%s" % (modulo, nombre) if modulo else nombre
                informe["nodes"].append({
                    "qual": qual, "kind": kind, "module": modulo, "doc": "",
                    "file": os.path.relpath(fichero, root), "line": linea,
                    "end": None, "sig": "",
                })
                informe["edges"].append([modulo, qual, "DEFINES"])
                definidos.setdefault(nombre, []).append(qual)

    # --- imports ---
    aristas_import = set()
    for lenguaje in lenguajes_reales:
        for patron in PATRONES_IMPORT:
            for m in _corre(ruta, patron, lenguaje, root):
                especificador = _meta(m, "SRC")
                fichero = os.path.abspath(os.path.join(root, m.get("file", "")))
                origen = por_fichero.get(fichero)
                if not especificador or origen is None:
                    continue
                destino = _resuelve_import(especificador, fichero, root, modulos)
                if destino and destino != origen:
                    aristas_import.add((origen, destino))
    for origen, destino in sorted(aristas_import):
        informe["edges"].append([origen, destino, "IMPORTS"])

    # --- llamadas ---
    sin_resolver = {}
    for lenguaje in lenguajes_reales:
        for m in _corre(ruta, PATRON_LLAMADA, lenguaje, root):
            llamado = (_meta(m, "FN") or "").strip()
            fichero = os.path.abspath(os.path.join(root, m.get("file", "")))
            origen_mod = por_fichero.get(fichero)
            if not llamado or origen_mod is None:
                continue
            informe["calls_total"] += 1
            if llamado in GLOBALES:
                informe["calls_builtin"] += 1
                continue
            informe["calls_candidates"] += 1
            if "." in llamado or "(" in llamado or "[" in llamado:
                # `obj.metodo()`, `f()()`, `a[b]()`: exigen inferencia de tipos.
                # El MISMO techo que la via Python, y por el mismo motivo — una
                # arista inventada es peor que una arista ausente (ADR 0008).
                sin_resolver["atributo-de-variable"] = sin_resolver.get("atributo-de-variable", 0) + 1
                continue
            candidatos = definidos.get(llamado)
            if not candidatos:
                sin_resolver["nombre-desconocido"] = sin_resolver.get("nombre-desconocido", 0) + 1
                continue
            if len(candidatos) > 1:
                # Homonimos en modulos distintos: elegir uno seria adivinar.
                sin_resolver["nombre-ambiguo"] = sin_resolver.get("nombre-ambiguo", 0) + 1
                continue
            informe["calls_resolved"] += 1
            informe["edges"].append([origen_mod, candidatos[0], "CALLS"])

    informe["unresolved"] = sin_resolver
    informe["not_covered"] = [
        "llamadas sobre variables (`obj.metodo()`): exigen inferencia de tipos. Se cuentan, "
        "no se adivinan — una arista inventada es peor que una arista ausente",
        "reexports, `require()` dinamico y alias de bundler: invisibles al patron",
        "homonimos en modulos distintos: se cuentan aparte en vez de elegir uno",
    ]
    return informe
