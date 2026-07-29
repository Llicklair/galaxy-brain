"""Presupuestos y ajustes. Todo por variable de entorno, nada de fichero de
configuracion: un fichero de config es superficie que hay que mantener, y v2
tiene una regla contra eso (CLAUDE.md, principio "restar antes que pulir").

Los limites de aqui son el presupuesto de la regla 4 (overhead) traducido a
numeros. Si un valor de estos hay que subirlo a menudo, es senal de que "que es
el estado" estaba mal decidido, no de que el limite sea bajo.
"""

import os
from pathlib import Path

#: Nombres de variables locales cuyo VALOR no se guarda nunca en disco.
#: Decision de producto, no tecnica: el estado alrededor de un fallo es
#: exactamente donde viven las credenciales.
REDACT_PATTERNS = (
    "passwd",
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "auth",
    "credential",
    "private_key",
    "session",
    "cookie",
)


def _int(name, default):
    try:
        return int(os.environ[name])
    except (KeyError, ValueError):
        return default


def _flag(name, default=False):
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in ("", "0", "false", "no", "off")


def home():
    """Donde vive el historico. FUERA del proyecto observado, siempre.

    ARCHITECTURE-v2 regla 7: el arnes nunca ensucia el proyecto que observa.
    """
    raw = os.environ.get("GB_HOME")
    if raw:
        return Path(raw)
    return Path.home() / ".galaxy-brain"


def max_frames():
    """Cuantos frames se guardan (se conservan los MAS INTERNOS: ahi esta el fallo)."""
    return _int("GB_MAX_FRAMES", 20)


def max_locals():
    """Cuantas variables por frame."""
    return _int("GB_MAX_LOCALS", 40)


def max_value_chars():
    """Longitud maxima del repr de un valor."""
    return _int("GB_MAX_VALUE_CHARS", 240)


def max_items():
    """Cuantos elementos de una coleccion se muestran antes de resumir."""
    return _int("GB_MAX_ITEMS", 10)


def context_lines():
    """Lineas de codigo fuente alrededor de la linea que fallo."""
    return _int("GB_CONTEXT_LINES", 2)


def capture_library_locals():
    """Por defecto NO se guardan locales de site-packages/stdlib.

    No es por tamano: es que el estado de una libreria casi nunca es lo que
    quieres mirar, y llenar la salida de ruido es la forma mas rapida de que
    una herramienta deje de usarse.
    """
    return _flag("GB_ALL_FRAMES", False)


def capture_threads():
    """Capturar tambien las excepciones de hilos.

    Cuesta lo que cuesta `import threading` en el arranque: 5,2 ms medidos de
    los 6,4 ms totales del hook (Python 3.11, Windows). La mayoria de programas
    reales importan threading de todas formas — logging, asyncio, requests — asi
    que ahi el coste no se anade, se adelanta. Para un CLI diminuto que jamas
    toca hilos, este interruptor lo devuelve.
    """
    return not _flag("GB_NO_THREADS", False)


def quiet():
    """Silencia la linea que se imprime tras el traceback."""
    return _flag("GB_QUIET", False)


def disabled():
    """Interruptor general. Existe para que apagarlo sea barato y visible.

    ARCHITECTURE-v2 regla 10: si acabas usando esto a diario, el dato es que
    la herramienta molesta. Se investiga, no se blinda.
    """
    return _flag("GB_DISABLE", False)
