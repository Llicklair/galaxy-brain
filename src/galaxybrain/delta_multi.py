"""Detectores delta para lenguajes no-Python, via ast-grep.

Extiende las senales de delta.py a los lenguajes que la tabla de
lenguajes.LENGUAJES soporta. El principio es identico: mide lo que ANADIO
este cambio (la diferencia antes/despues), no el estado absoluto.

Requiere ast-grep instalado — el mismo binario que lenguajes.py usa para el
grafo multi-lenguaje. Sin el, devuelve None y el fichero se salta en
silencio (igual que un .py con SyntaxError en la via clasica).
"""

import json
import os
import subprocess
import tempfile

from . import lenguajes as _lang

# ---------------------------------------------------------------------------
# Patrones de error tragado (silencios) por lenguaje.
# Solo lenguajes con try/catch sintatico; Go, Rust, C y Lua no lo tienen.
# Cada entrada: (patron, selector_opcional)
# ---------------------------------------------------------------------------

_SILENCIOS = {
    "js":     [("try { $$$ } catch($E) { }", None)],
    "ts":     [("try { $$$ } catch($E) { }", None)],
    "tsx":    [("try { $$$ } catch($E) { }", None)],
    "java":   [("try { $$$ } catch ($T $E) { }", None)],
    "kotlin": [("try { $$$ } catch ($E: $T) { }", None)],
    "csharp": [("try { $$$ } catch ($T $E) { }", None),
               ("try { $$$ } catch { }", None)],
    "php":    [("try { $$$ } catch ($T $E) { }", None)],
    "scala":  [("try { $$$ } catch { case $E => }", None)],
    "swift":  [("do { $$$ } catch { }", None)],
    "dart":   [("try { $$$ } catch ($E) { }", None)],
}

# ---------------------------------------------------------------------------
# Patrones de guarda (precondicion que lanza) por lenguaje. La eliminacion de
# una de estas ensancha en silencio el dominio de entradas de la funcion —
# la misma senal que delta.py caza en Python con `if ...: raise`.
# A diferencia de Python no se exige "al principio de la funcion": el patron
# posicional no se puede expresar barato en ast-grep, y un `if cond: throw`
# eliminado en CUALQUIER punto sigue siendo informacion.
# ---------------------------------------------------------------------------

_GUARDAS = {
    "js":     [("if ($C) { throw $E; }", None), ("if ($C) throw $E;", None)],
    "ts":     [("if ($C) { throw $E; }", None), ("if ($C) throw $E;", None)],
    "tsx":    [("if ($C) { throw $E; }", None), ("if ($C) throw $E;", None)],
    "java":   [("if ($C) { throw $E; }", None), ("if ($C) throw $E;", None)],
    "kotlin": [("if ($C) { throw $E }", None), ("if ($C) throw $E", None)],
    "csharp": [("if ($C) { throw $E; }", None), ("if ($C) throw $E;", None)],
    "php":    [("if ($C) { throw $E; }", None)],
    "scala":  [("if ($C) throw $E", None)],
    "swift":  [("guard $C else { throw $E }", None)],
    "dart":   [("if ($C) { throw $E; }", None), ("if ($C) throw $E;", None)],
    "ruby":   [("raise $E if $C", None)],
    "go":     [("if $C { panic($E) }", None)],
    "rust":   [("if $C { panic!($$$) }", None)],
}

# Cache del binario de ast-grep: una sola comprobacion por proceso.
_ag_cache = None


def _ag():
    global _ag_cache
    if _ag_cache is None:
        _ag_cache = _lang.disponible()
    return _ag_cache


def _corre(ag, patron, lang_ag, fichero, selector=None):
    """Una pasada de ast-grep sobre un fichero."""
    orden = [ag, "run", "-p", patron, "-l", lang_ag, "--json=compact"]
    if selector:
        orden += ["--selector", selector]
    try:
        p = subprocess.run(orden + [fichero], capture_output=True, timeout=30)
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
    return (match.get("metaVariables", {}).get("single", {})
            .get(nombre, {}) or {}).get("text")


def _linea(match):
    return match.get("range", {}).get("start", {}).get("line", 0) + 1


def _fin(match):
    return match.get("range", {}).get("end", {}).get("line", 0) + 1


class Hechos:
    """Los mismos atributos que delta._Visitante, para que la comparacion
    en delta.analyze() funcione sin cambios."""

    def __init__(self):
        self.silencios = []
        self.amplios = []
        self.pendientes = []
        self.cuerpos = {}
        self.tipos_retorno = {}
        self.guardas = []


def hechos(texto, lang_id):
    """Extrae hechos de un fichero no-Python via ast-grep.

    Devuelve None si ast-grep no esta o el lenguaje no esta en la tabla.
    """
    ag, _ = _ag()
    if not ag:
        return None

    cfg = _lang.LENGUAJES.get(lang_id)
    if not cfg:
        return None

    ext = cfg["extensiones"][0]
    resultado = Hechos()

    with tempfile.TemporaryDirectory() as tmpdir:
        ruta = os.path.join(tmpdir, "source" + ext)
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(texto)

        # --- silencios: try/catch con cuerpo vacio ---
        for patron, selector in _SILENCIOS.get(lang_id, []):
            for m in _corre(ag, patron, cfg["ag"], ruta, selector):
                resultado.silencios.append(
                    (_linea(m), "error tragado: catch vacio"))

        # --- guardas: precondiciones que lanzan ---
        vistos_guardas = set()
        for patron, selector in _GUARDAS.get(lang_id, []):
            for m in _corre(ag, patron, cfg["ag"], ruta, selector):
                linea = _linea(m)
                texto = " ".join((m.get("text") or "").split())[:80]
                if (linea, texto) in vistos_guardas:
                    continue      # una guarda puede casar con dos formas
                vistos_guardas.add((linea, texto))
                resultado.guardas.append((linea, texto))

        # --- tipos de retorno y cuerpos: reutilizar patrones de LENGUAJES ---
        for entrada in cfg["simbolos"]:
            kind, patron = entrada[0], entrada[1]
            selector = entrada[2] if len(entrada) > 2 else None
            if kind not in ("function", "method"):
                continue
            for m in _corre(ag, patron, cfg["ag"], ruta, selector):
                nombre = _meta(m, "NAME")
                if not nombre:
                    continue
                inicio, fin = _linea(m), _fin(m)
                if nombre not in resultado.cuerpos:
                    resultado.cuerpos[nombre] = (inicio, fin)
                ret = _meta(m, "RET")
                if ret and nombre not in resultado.tipos_retorno:
                    resultado.tipos_retorno[nombre] = (inicio, ret.strip())

    # --- pendientes (TODO/FIXME) por regex, igual que delta.py ---
    for numero, linea in enumerate(texto.split("\n"), 1):
        limpia = linea.strip()
        if not any(limpia.startswith(p) for p in ("//", "#", "--", "/*", "*", "%%")):
            continue
        for marca in ("TODO", "FIXME", "XXX", "HACK"):
            if marca in limpia:
                resultado.pendientes.append((numero, limpia[:70]))
                break

    return resultado
