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


def user_site_pth():
    """Donde cae el .pth cuando purelib es de solo lectura (Python de la Store,
    interpretes de sistema). Solo vale si este interprete carga el user-site al
    arrancar; si esta deshabilitado (venv, -s, PYTHONNOUSERSITE), no es candidato."""
    import site

    if not getattr(site, "ENABLE_USER_SITE", False):
        return None
    try:
        return Path(site.getusersitepackages()) / PTH_NAME
    except (AttributeError, OSError):
        return None


def pth_candidates():
    """Donde puede vivir el .pth, en orden de preferencia: purelib primero,
    user-site como repliegue cuando purelib no acepta escrituras."""
    candidatos = [site_packages() / PTH_NAME]
    user = user_site_pth()
    if user is not None and user != candidatos[0]:
        candidatos.append(user)
    return candidatos


def pth_path():
    """El .pth activo si ya existe en algun candidato; si no, el preferido."""
    candidatos = pth_candidates()
    for candidato in candidatos:
        try:
            if candidato.exists():
                return candidato
        except OSError:
            continue
    return candidatos[0]


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


#: Que dispara una captura y que no. Cada caso se EJECUTA de verdad en un
#: subproceso con su propio historico, y se mira si dejo registro.
#:
#: Documentar la frontera no basta: un documento envejece y nadie sabe si sigue
#: siendo cierto. Esto la demuestra cada vez que se lanza. Y las dos mitades
#: pesan igual — un "no captura" que en realidad captura llenaria el historico de
#: ruido, y un "captura" que no captura es un fallo que desaparece sin rastro.
_CASOS = (
    ("excepcion no capturada", True, "raise ValueError('x')"),
    (
        "excepcion en un hilo",
        True,
        "import threading\n"
        "def t():\n    raise RuntimeError('en el hilo')\n"
        "h = threading.Thread(target=t); h.start(); h.join()",
    ),
    (
        "excepcion en __del__ (no propagable)",
        True,
        "class X:\n    def __del__(self):\n        raise ValueError('finalizador')\n"
        "x = X()\ndel x",
    ),
    (
        "asyncio: propaga fuera de run()",
        True,
        "import asyncio\nasync def m():\n    raise ValueError('propaga')\nasyncio.run(m())",
    ),
    (
        "asyncio: tarea suelta que nadie espera",
        False,
        "import asyncio\n"
        "async def rota():\n    raise ValueError('suelta')\n"
        "async def m():\n    asyncio.ensure_future(rota())\n    await asyncio.sleep(0.2)\n"
        "asyncio.run(m())",
    ),
    ("sys.exit(1)", False, "import sys; sys.exit(1)"),
    ("KeyboardInterrupt", False, "raise KeyboardInterrupt()"),
    (
        "excepcion atrapada por try/except",
        False,
        "try:\n    raise ValueError('la maneje yo')\nexcept ValueError:\n    pass",
    ),
)


#: La sonda se arma SOLA en cada hijo. Esto mide la FRONTERA (que fallo deja
#: registro con el hook puesto); la instalacion es otra pregunta y ya tiene su
#: medidor (`verify`). Mezclarlas era el bug: con la captura de la maquina
#: apagada, las 4 discrepancias decian "agujero en la frontera" cuando la
#: verdad era "no instalado" — y los tests heredaban ese estado (26-ago-2026).
_ARMA = "import galaxybrain.autoinstall\n"


def coverage():
    """Ejecuta cada modo de fallo y comprueba si dejo registro.

    La lectura util es la DISCREPANCIA: algo que deberia capturarse y no aparece
    es un agujero; algo que no deberia y aparece es ruido futuro.
    """
    import json as _json
    import shutil
    import tempfile

    resultados = []
    for nombre, esperado, codigo in _CASOS:
        casa = tempfile.mkdtemp(prefix="gb-cobertura-")
        entorno = dict(os.environ)
        entorno.pop("GB_DISABLE", None)
        entorno["GB_HOME"] = casa  # historico aparte: esto no ensucia el tuyo
        entorno["GB_QUIET"] = "1"  # aqui se mide, no se avisa
        observado, detalle = None, ""
        try:
            subprocess.run(
                [sys.executable, "-c", _ARMA + codigo],
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                env=entorno,
            )
            indice = os.path.join(casa, "index.jsonl")
            lineas = []
            if os.path.exists(indice):
                with open(indice, "r", encoding="utf-8") as handle:
                    lineas = [linea for linea in handle if linea.strip()]
            observado = bool(lineas)
            if lineas:
                try:
                    detalle = _json.loads(lineas[-1]).get("type", "")
                except ValueError:
                    detalle = ""
        except (OSError, subprocess.SubprocessError) as error:
            detalle = "no se pudo ejecutar: %s" % error
        finally:
            shutil.rmtree(casa, ignore_errors=True)

        resultados.append(
            {
                "caso": nombre,
                "esperado": esperado,
                "observado": observado,
                "detalle": detalle,
                "ok": observado == esperado,
            }
        )
    return resultados


def enable():
    """Escribe el .pth y COMPRUEBA que el entorno sigue sano. (ok, mensaje)."""
    path = pth_path()
    ya_estaba = False
    try:
        if path.exists() and path.read_text(encoding="utf-8").strip() == PTH_LINE:
            ya_estaba = True
    except OSError:
        pass

    if not ya_estaba:
        # La unica prueba de escribibilidad es escribir: en el Python de la
        # Store, os.access() responde True sobre un purelib (WindowsApps) que
        # luego rechaza open() con EACCES. Si purelib no traga, repliegue al
        # user-site — que este interprete tambien carga al arrancar.
        candidatos = [path] + [c for c in pth_candidates() if c != path]
        escrito, fallo = None, (path, "sin candidatos")
        for candidato in candidatos:
            try:
                candidato.parent.mkdir(parents=True, exist_ok=True)
                candidato.write_text(PTH_LINE + "\n", encoding="utf-8")
                escrito = candidato
                break
            except OSError as error:
                fallo = (candidato, error)
        if escrito is None:
            return False, "no se pudo escribir %s (%s)" % fallo
        path = escrito

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
