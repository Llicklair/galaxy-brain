"""Los hooks. Este modulo se importa en el arranque de cada proceso Python del
venv, asi que solo toca `sys` y `os` a nivel de modulo. Todo lo demas se importa
dentro del handler, es decir, cuando ya ha habido un fallo.

Consecuencia buscada: mientras el programa funciona, el coste es cero. No es
"bajo", es cero — `sys.excepthook` solo se ejecuta cuando el proceso se muere.
Por eso v2 empieza por excepciones no capturadas y no por otra cosa.
"""

import os
import sys

_MARK = "_galaxy_brain_hook"

_previous_excepthook = None
_previous_threadhook = None

#: Estas no son fallos: son formas normales de terminar.
_IGNORED = (SystemExit, KeyboardInterrupt)


def _env_flag(name):
    """Igual que config._flag, repetido aqui a proposito: importar `config` en
    el arranque traeria `pathlib`, y este modulo corre en cada proceso Python
    del entorno. Diez lineas duplicadas cuestan menos que un import."""
    return os.environ.get(name, "").strip().lower() not in ("", "0", "false", "no", "off")


def is_installed():
    return getattr(sys.excepthook, _MARK, False) is True


def install():
    """Encadena nuestros hooks a los que ya hubiera. Idempotente."""
    global _previous_excepthook, _previous_threadhook

    if is_installed():
        return False
    if _env_flag("GB_DISABLE"):
        return False

    _previous_excepthook = sys.excepthook
    setattr(_excepthook, _MARK, True)
    sys.excepthook = _excepthook

    if _env_flag("GB_NO_THREADS"):
        return True

    # `import threading` es el 80% del coste de arranque de este hook (5,2 de
    # 6,4 ms medidos). Se paga a proposito: sin esto, una excepcion en un hilo
    # no deja rastro, y los fallos de hilo son justo los que mas cuesta
    # reproducir a mano. GB_NO_THREADS=1 lo devuelve para CLIs diminutos.
    threading = sys.modules.get("threading")
    if threading is None:
        import threading  # noqa: PLC0415
    if hasattr(threading, "excepthook"):
        _previous_threadhook = threading.excepthook
        setattr(_threadhook, _MARK, True)
        threading.excepthook = _threadhook

    return True


def uninstall():
    global _previous_excepthook, _previous_threadhook

    if _previous_excepthook is not None:
        sys.excepthook = _previous_excepthook
        _previous_excepthook = None
    if _previous_threadhook is not None:
        import threading

        threading.excepthook = _previous_threadhook
        _previous_threadhook = None
    return True


def _excepthook(exc_type, exc, tb):
    # 1) Primero, el comportamiento original INTACTO. Si lo de abajo se cuelga o
    #    revienta, el programa ya ha hecho exactamente lo que habria hecho sin
    #    nosotros (regla 9).
    try:
        if _previous_excepthook is not None:
            _previous_excepthook(exc_type, exc, tb)
        else:
            sys.__excepthook__(exc_type, exc, tb)
    except BaseException:  # noqa: BLE001
        pass

    if isinstance(exc, _IGNORED) or (
        isinstance(exc_type, type) and issubclass(exc_type, _IGNORED)
    ):
        return

    _capture(exc_type, exc, tb, source="excepthook", thread="MainThread")


def _threadhook(args):
    try:
        if _previous_threadhook is not None:
            _previous_threadhook(args)
    except BaseException:  # noqa: BLE001
        pass

    exc_type = getattr(args, "exc_type", None)
    if exc_type is None or (isinstance(exc_type, type) and issubclass(exc_type, _IGNORED)):
        return

    thread = getattr(args, "thread", None)
    _capture(
        exc_type,
        getattr(args, "exc_value", None),
        getattr(args, "exc_traceback", None),
        source="threading",
        thread=getattr(thread, "name", None),
    )


def _capture(exc_type, exc, tb, source, thread):
    """Todo lo caro vive aqui, detras de un try que no deja escapar nada."""
    try:
        from . import capture, config, store

        if config.disabled():
            return
        record = capture.build_record(exc_type, exc, tb, source=source, thread=thread)
        path = store.write(record)
        if path is not None and not config.quiet():
            _notice(record)
    except BaseException:  # noqa: BLE001 - jamas romper el programa observado
        pass


def _notice(record):
    """Una linea. Si esto crece, deja de ser una nota y pasa a ser ruido."""
    try:
        sys.stderr.write(
            "\n[galaxy-brain] estado capturado -> gb last   (id %s)\n" % record.get("id", "?")
        )
        sys.stderr.flush()
    except BaseException:  # noqa: BLE001
        pass
