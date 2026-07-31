"""galaxy-brain — consola de errores determinista.

Regla 1 de ARCHITECTURE: cero modelos en el camino caliente.
Regla 3: presupuesto de latencia. Este modulo se importa en el arranque de
*cada* proceso Python del venv donde este instalado, asi que no importa nada
pesado: solo `sys` y `os`. Todo lo demas se carga cuando ya ha habido un fallo,
momento en el que el proceso se estaba muriendo de todos modos.
"""

__version__ = "0.2.0"

__all__ = ["install", "uninstall", "is_installed", "__version__"]


def install():
    """Registra los hooks de captura. Idempotente."""
    from .hooks import install as _install

    return _install()


def uninstall():
    """Restaura los hooks previos. Idempotente."""
    from .hooks import uninstall as _uninstall

    return _uninstall()


def is_installed():
    from .hooks import is_installed as _is_installed

    return _is_installed()
