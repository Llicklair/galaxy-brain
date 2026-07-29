"""Convertir una excepcion no capturada en un hecho guardable.

Aqui no hay juicio ninguno: una excepcion es un hecho, la traza es un hecho, el
valor de una variable en el momento del fallo es un hecho. Interpretar es un
paso posterior, separado y descartable (ARCHITECTURE-v2, reglas 6 y 8).
"""

import datetime
import linecache
import os
import sys
import sysconfig
import traceback

from . import config
from .saferepr import repr_local

_LIBRARY_MARKERS = None


def _library_markers():
    """Prefijos de ruta que consideramos 'no es tu codigo'."""
    global _LIBRARY_MARKERS
    if _LIBRARY_MARKERS is None:
        paths = set()
        for key in ("purelib", "platlib", "stdlib", "platstdlib"):
            try:
                value = sysconfig.get_paths().get(key)
            except BaseException:  # noqa: BLE001
                value = None
            if value:
                paths.add(os.path.normcase(os.path.abspath(value)))
        _LIBRARY_MARKERS = tuple(sorted(paths))
    return _LIBRARY_MARKERS


def is_library_frame(filename):
    try:
        normalized = os.path.normcase(os.path.abspath(filename))
    except BaseException:  # noqa: BLE001
        return True
    if "site-packages" in normalized or "dist-packages" in normalized:
        return True
    return normalized.startswith(_library_markers())


def _source_context(filename, lineno):
    """Las lineas alrededor del fallo. Sin esto, el numero de linea obliga a
    abrir el fichero, que es justo el paso manual que esto viene a quitar."""
    span = config.context_lines()
    lines = []
    for number in range(max(1, lineno - span), lineno + span + 1):
        text = linecache.getline(filename, number)
        if not text:
            continue
        lines.append({"n": number, "text": text.rstrip("\n"), "is_fail": number == lineno})
    return lines


def _frame_locals(frame, capture_values):
    if not capture_values:
        return None
    try:
        raw = dict(frame.f_locals)
    except BaseException:  # noqa: BLE001
        return None

    # Los dunder de un frame de modulo (__builtins__, __loader__, __spec__...)
    # son ocho lineas que no dicen nada sobre ningun fallo. Sepultan las dos
    # variables que si importan, y una salida que hay que filtrar con la vista
    # es una salida que se deja de leer.
    names = sorted(name for name in raw if not (name.startswith("__") and name.endswith("__")))
    limit = config.max_locals()
    out = {}
    for name in names[:limit]:
        out[name] = repr_local(name, raw[name])
    if len(names) > limit:
        out["..."] = "(%d variables mas, recortadas por GB_MAX_LOCALS)" % (len(names) - limit)
    return out


def _walk_frames(tb):
    """Los frames de la traza, del mas externo al mas interno."""
    frames = []
    while tb is not None:
        frames.append((tb.tb_frame, tb.tb_lineno))
        tb = tb.tb_next
    return frames


def describe_frames(tb):
    entries = _walk_frames(tb)

    # Si hay que recortar, se conservan los mas internos: el fallo esta abajo.
    limit = config.max_frames()
    trimmed = len(entries) - limit
    if trimmed > 0:
        entries = entries[-limit:]

    capture_all = config.capture_library_locals()
    described = []
    for frame, lineno in entries:
        code = frame.f_code
        filename = code.co_filename
        is_lib = is_library_frame(filename)
        described.append(
            {
                "file": filename,
                "line": lineno,
                "function": code.co_name,
                "is_library": is_lib,
                "source": _source_context(filename, lineno),
                "locals": _frame_locals(frame, capture_all or not is_lib),
            }
        )
    return described, max(0, trimmed)


def describe_chain(exc, max_depth=3):
    """`raise X from Y` y las excepciones durante el manejo de otra.

    Solo tipo y mensaje: los frames de la cadena rara vez son lo que buscas y
    multiplicarian el tamano del registro.
    """
    chain = []
    seen = {id(exc)}
    current = exc
    while len(chain) < max_depth:
        nxt = getattr(current, "__cause__", None)
        kind = "cause"
        if nxt is None:
            if getattr(current, "__suppress_context__", False):
                break
            nxt = getattr(current, "__context__", None)
            kind = "context"
        if nxt is None or id(nxt) in seen:
            break
        seen.add(id(nxt))
        chain.append(
            {
                "kind": kind,
                "type": type(nxt).__name__,
                "message": _message(nxt),
            }
        )
        current = nxt
    return chain


def _message(exc):
    try:
        return str(exc)
    except BaseException as error:  # noqa: BLE001
        return "<str() fallo con %s>" % type(error).__name__


def _project_root(start=None):
    """La raiz del proyecto observado: el ancestro mas cercano con .git.

    Nada project-specific (CLAUDE.md regla 6): se detecta, no se configura.
    """
    try:
        current = os.path.abspath(start or os.getcwd())
    except BaseException:  # noqa: BLE001
        return None
    while True:
        if os.path.isdir(os.path.join(current, ".git")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def _entry_dir():
    """La carpeta del programa que se lanzo, si la hay.

    El cwd miente a menudo: se ejecuta un script desde otra carpeta y el fallo
    acaba archivado bajo el proyecto equivocado. La ruta del script que
    arranco el proceso es una senal mejor. Con `python -c` o el REPL no existe,
    y entonces el cwd es lo unico que hay.
    """
    try:
        entry = sys.argv[0]
    except BaseException:  # noqa: BLE001
        return None
    if not entry or entry.startswith("-"):
        return None
    try:
        path = os.path.abspath(entry)
        if not os.path.exists(path):
            return None
        directory = path if os.path.isdir(path) else os.path.dirname(path)
    except BaseException:  # noqa: BLE001
        return None
    # Un entry point instalado (pytest, uvicorn...) vive en site-packages o
    # Scripts/: eso no es el proyecto del usuario.
    if is_library_frame(directory):
        return None
    return directory


def detect_project(cwd=None):
    return _project_root(_entry_dir()) or _project_root(cwd)


def build_record(exc_type, exc, tb, source="excepthook", thread=None):
    """El registro completo. Funcion pura salvo por leer el proceso vivo."""
    frames, trimmed = describe_frames(tb)
    try:
        text = "".join(traceback.format_exception(exc_type, exc, tb))
    except BaseException:  # noqa: BLE001
        text = ""

    cwd = None
    try:
        cwd = os.getcwd()
    except BaseException:  # noqa: BLE001
        pass

    return {
        "schema": 1,
        "ts": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": source,
        "thread": thread,
        "exception": {
            "type": getattr(exc_type, "__name__", str(exc_type)),
            "module": getattr(exc_type, "__module__", None),
            "message": _message(exc),
            "chain": describe_chain(exc),
        },
        "frames": frames,
        "frames_trimmed": trimmed,
        "traceback": text,
        "process": {
            "cwd": cwd,
            "project": detect_project(cwd),
            "argv": list(sys.argv),
            "python": sys.version.split()[0],
            "executable": sys.executable,
            "platform": sys.platform,
            "pid": os.getpid(),
        },
    }
