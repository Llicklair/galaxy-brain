"""Los hooks. Este modulo se importa en el arranque de cada proceso Python del
venv, asi que solo toca `sys` y `os` a nivel de modulo. Todo lo demas se importa
dentro del handler, es decir, cuando ya ha habido un fallo.

Consecuencia buscada: mientras el programa funciona, el coste es cero. No es
"bajo", es cero — `sys.excepthook` solo se ejecuta cuando el proceso se muere.
Por eso la consola empieza por excepciones no capturadas y no por otra cosa.
"""

import os
import sys

_MARK = "_galaxy_brain_hook"

_previous_excepthook = None
_previous_threadhook = None
_previous_unraisablehook = None

#: Estas no son fallos: son formas normales de terminar.
_IGNORED = (SystemExit, KeyboardInterrupt)

#: Tope de capturas "unraisable" por proceso. Un `__del__` que revienta suele
#: reventar para TODAS las instancias de su clase, asi que un bucle que crea diez
#: mil objetos escribiria diez mil registros: inundaria el historico y, peor,
#: frenaria el programa observado (regla 4). Al llegar al tope se dice y se para;
#: callarse seria convertir un limite en un silencio que se lee como "no paso nada".
_MAX_UNRAISABLE = 10
_unraisable_vistas = 0


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

    global _previous_unraisablehook

    _previous_excepthook = sys.excepthook
    setattr(_excepthook, _MARK, True)
    sys.excepthook = _excepthook

    # La tercera puerta. Va ANTES del corte de GB_NO_THREADS a proposito: ese flag
    # existe para no pagar `import threading`, y esto no importa nada — asignar el
    # hook es gratis, asi que quien apaga los hilos no deberia perder ademas los
    # fallos de finalizador.
    if hasattr(sys, "unraisablehook"):
        _previous_unraisablehook = sys.unraisablehook
        setattr(_unraisablehook, _MARK, True)
        sys.unraisablehook = _unraisablehook

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
    global _previous_excepthook, _previous_threadhook, _previous_unraisablehook

    if _previous_excepthook is not None:
        sys.excepthook = _previous_excepthook
        _previous_excepthook = None
    if _previous_unraisablehook is not None:
        sys.unraisablehook = _previous_unraisablehook
        _previous_unraisablehook = None
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


def _unraisablehook(args):
    """Una excepcion que Python NO pudo propagar: `__del__`, un callback de
    weakref, el recolector de basura.

    Es la unica de las tres puertas que desaparecia sin dejar rastro: el
    interprete la imprime, el proceso NO muere, y por eso `sys.excepthook` no la
    ve jamas. No es un segundo tipo de fallo — es el mismo hecho (una excepcion
    que nadie capturo) saliendo por otro sitio.
    """
    global _unraisable_vistas

    try:
        if _previous_unraisablehook is not None:
            _previous_unraisablehook(args)
        else:
            sys.__unraisablehook__(args)
    except BaseException:  # noqa: BLE001
        pass

    exc_type = getattr(args, "exc_type", None)
    if exc_type is None or (isinstance(exc_type, type) and issubclass(exc_type, _IGNORED)):
        return

    _unraisable_vistas += 1
    if _unraisable_vistas > _MAX_UNRAISABLE:
        return
    if _unraisable_vistas == _MAX_UNRAISABLE:
        try:
            sys.stderr.write(
                "\n[galaxy-brain] %d fallos de finalizador en este proceso; dejo de "
                "guardarlos para no frenarte. Los anteriores estan en `gb list`.\n"
                % _MAX_UNRAISABLE
            )
        except BaseException:  # noqa: BLE001
            pass

    # El hilo no se sabe: un finalizador corre donde el GC lo despierte, y
    # afirmar "MainThread" seria inventarse un hecho.
    _capture(
        exc_type,
        getattr(args, "exc_value", None),
        getattr(args, "exc_traceback", None),
        source="unraisable",
        thread=None,
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
    """Una linea. Si esto crece, deja de ser una nota y pasa a ser ruido.

    Lleva el comando EXACTO, con el id dentro, en vez de un `gb last` generico y
    el id aparte. Cuesta lo mismo y quita el unico paso que quedaba: el id es la
    correlacion perfecta — no hay ventana de tiempo ni riesgo de leer el fallo de
    antes. Quien lee esta linea (humano o agente) puede copiarla y ya.
    """
    try:
        from .idioma import t
        sys.stderr.write(
            t("\n[galaxy-brain] estado capturado -> gb show %s\n") % record.get("id", "?")
        )
        sys.stderr.flush()
    except BaseException:  # noqa: BLE001
        pass
