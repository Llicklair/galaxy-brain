"""Encender y apagar la captura automatica en un entorno Python.

El mecanismo es un fichero `.pth` en site-packages: Python ejecuta al arrancar
toda linea de un `.pth` que empiece por `import`. Es el mismo truco que usa
coverage.py, y es lo que hace posible la propiedad 2 (intercepta, no pregunta):
no hay que anadir una linea a ningun proyecto ni acordarse de nada.

La linea va envuelta en try/except a proposito. Si algun dia desinstalas el
paquete y el `.pth` se queda huerfano, el arranque de cada proceso Python del
entorno imprimiria un error. Eso es exactamente el tipo de dano que la
propiedad 5 prohibe.
"""

import os
import subprocess
import sys
import sysconfig
from pathlib import Path

PTH_NAME = "galaxybrain.pth"

PTH_LINE = (
    'import sys; exec("try:\\n    import galaxybrain.autoinstall\\n'
    'except Exception:\\n    pass\\n")'
)


def site_packages():
    return Path(sysconfig.get_paths()["purelib"])


def pth_path():
    return site_packages() / PTH_NAME


def verify(executable=None):
    """¿Arranca Python limpio Y queda el hook puesto?

    Se comprueba lanzando un interprete de verdad, no razonando sobre el
    fichero. Un `.pth` roto no da un error al escribirlo: da un traceback en el
    arranque de CADA proceso Python del entorno, para siempre, hasta que
    alguien lo relacione con esto. Es el peor fallo que puede tener esta
    herramienta, y por eso es el unico sitio donde se paga un subproceso.
    """
    environment = dict(os.environ)
    environment.pop("GB_DISABLE", None)
    probe = (
        "import sys; "
        "sys.stdout.write('1' if getattr(sys.excepthook, '_galaxy_brain_hook', False) else '0')"
    )
    try:
        result = subprocess.run(
            [executable or sys.executable, "-c", probe],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            env=environment,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return False, "no se pudo comprobar (%s)" % error

    installed = (result.stdout or "").strip() == "1"
    if installed:
        # El hook esta puesto: la señal autoritativa es stdout, no stderr. Un
        # stderr ajeno en el arranque (otro .pth, un DeprecationWarning de otra
        # libreria) no es asunto nuestro y NO debe hacer fallar la verificacion —
        # eso era B1: un ruido ajeno acababa borrando un .pth que funcionaba.
        return True, ""

    noise = (result.stderr or "").strip()
    if noise and (PTH_NAME in noise or ".pth" in noise or "galaxybrain" in noise):
        return False, "el .pth rompe el arranque de Python: %s" % noise.splitlines()[0]
    return False, (
        "el hook no quedo instalado — ¿esta el paquete instalado en este "
        "interprete? (pip install -e .)"
    )


def enable():
    """Escribe el .pth y COMPRUEBA que el entorno sigue sano. (ok, mensaje)."""
    path = pth_path()
    ya_estaba = False
    try:
        if path.exists() and path.read_text(encoding="utf-8").strip() == PTH_LINE:
            ya_estaba = True
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(PTH_LINE + "\n", encoding="utf-8")
    except OSError as error:
        return False, "no se pudo escribir %s (%s)" % (path, error)

    ok, detail = verify()
    if not ok:
        if ya_estaba:
            # No lo escribimos nosotros esta vez: NO lo borramos por un fallo de
            # verify (era B1). Un .pth preexistente es del usuario; se informa,
            # no se destruye.
            return False, "el .pth ya existia pero la verificacion falla: %s" % detail
        # Lo escribimos nosotros y algo va mal: revertimos nuestro propio cambio.
        # Preferimos no activarnos a dejar un Python que escupe errores en cada
        # arranque (propiedad 5: los falsos positivos tienen que ser inofensivos).
        try:
            path.unlink()
        except OSError:
            pass
        return False, "activacion revertida: %s" % detail

    return True, ("ya estaba activa: %s" if ya_estaba else "activada y verificada: %s") % path


def disable():
    path = pth_path()
    try:
        if not path.exists():
            return True, "no estaba activa"
        path.unlink()
        return True, "desactivada: %s" % path
    except OSError as error:
        return False, "no se pudo borrar %s (%s)" % (path, error)


def is_enabled():
    try:
        return pth_path().exists()
    except OSError:
        return False
