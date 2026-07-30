"""Lo externo: detectado y verificado, nunca replicado.

La regla 7 dice cómo se integra una herramienta ajena — *detección + instalador
oficial + verificación* — y este módulo es esa regla hecha código. No envuelve
nada, no llama a nada por ti: mira si está, mira si sirve **aquí**, y lo dice.

El caso que lo motiva: GitNexus construye el grafo de código a nivel de símbolo
(`Function`, `Class`, `Method`, con aristas `CALLS`/`EXTENDS`/`IMPLEMENTS`), que es
una liga por encima del grafo de imports de `gb graph`. Rehacerlo aquí exigiría
resolver tipos —y eso es una dependencia, o un grafo de suposiciones con pinta de
hechos, que es peor—. Así que no se rehace: se detecta y se señala.

Sin subprocesos en el camino de la gate. Esto se consulta desde `gb floor`, que
contesta *"qué tiene este proyecto"*; el pre-commit tiene un presupuesto de 10 s y
no puede pagar un arranque de proceso ajeno.
"""

import os
import re
import shutil
import subprocess

#: Bloques que una herramienta se escribe a si misma en un fichero compartido.
#: Convencion comun (`<!-- x:start -->` … `<!-- x:end -->`), asi que se detecta el
#: patron, no una herramienta concreta (hard rule 6).
_TOOL_BLOCK = re.compile(
    r"<!--\s*([\w.-]+):start\s*-->.*?<!--\s*\1:end\s*-->", re.DOTALL | re.IGNORECASE
)
_TOOL_OPEN = re.compile(r"<!--\s*([\w.-]+):start\s*-->", re.IGNORECASE)


def _run(command, cwd, timeout=20):
    try:
        result = subprocess.run(
            command, cwd=cwd, capture_output=True, encoding="utf-8",
            errors="replace", timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return (result.stdout or "") + (result.stderr or "")


def gitnexus(root):
    """¿Está GitNexus instalado, y tiene indexado ESTE repo?

    Instalado no es lo mismo que sirve: un indice de otro repo no ayuda aqui, y un
    indice viejo miente. Por eso se comprueba contra `root`, no en abstracto.
    """
    ruta = shutil.which("gitnexus")
    if not ruta:
        return {
            "name": "gitnexus",
            "installed": False,
            "usable": False,
            "detail": "no instalado",
            "hint": "npm i -g gitnexus  (grafo de codigo a nivel de simbolo)",
        }

    # La RUTA RESUELTA, no el nombre pelado: en Windows el ejecutable es un `.CMD`
    # y `subprocess` sin shell no lo encuentra por nombre. Comprobado: lanzaba
    # FileNotFoundError, y el informe lo traducia a "sin indexar" — un estado
    # distinto y mas tranquilizador que el real, que era "no pude comprobarlo".
    salida = _run([ruta, "status"], cwd=root)
    if salida is None:
        return {
            "name": "gitnexus", "installed": True, "usable": False, "stale": None,
            "detail": "instalado, pero no pude ejecutar `gitnexus status` aqui",
            "hint": "gitnexus status",
        }

    bajo = salida.lower()
    if "not indexed" in bajo:
        return {
            "name": "gitnexus", "installed": True, "usable": False, "stale": None,
            "detail": "instalado, pero este repo NO esta indexado",
            "hint": "gitnexus analyze",
        }

    # Un indice viejo es PEOR que no tenerlo: se presenta como el mapa del proyecto
    # y describe un proyecto que ya no existe. GitNexus lo sabe y lo dice; se
    # traslada en vez de resumirlo a "indexado".
    fresco = "up-to-date" in bajo or "up to date" in bajo
    return {
        "name": "gitnexus",
        "installed": True,
        "usable": fresco,
        "stale": not fresco,
        "detail": (
            "indexado y al dia: grafo a nivel de simbolo disponible"
            if fresco
            else "indexado pero DESFASADO respecto al commit actual: el mapa describe otro codigo"
        ),
        "hint": "gitnexus serve" if fresco else "gitnexus analyze",
    }


def tool_generated_ratio(text):
    """Qué proporción del texto la escribió una herramienta, no una persona.

    Un fichero de contexto que es en su mayoría bloques auto-generados **no es el
    contexto del proyecto**: es una herramienta anunciandose. Darlo por bueno seria
    aprobar el continente ignorando el contenido — y ese es el modo de fallo que
    convierte una comprobacion en teatro.
    """
    if not text.strip():
        return 0.0, []
    herramientas = []
    total = len(text)
    dentro = 0
    for match in _TOOL_BLOCK.finditer(text):
        herramientas.append(match.group(1))
        dentro += len(match.group(0))
    if not herramientas:
        # Bloque abierto sin cerrar: cuenta desde la marca hasta el final, que es
        # como se comporta de hecho un apendice al final del fichero.
        abierto = _TOOL_OPEN.search(text)
        if abierto:
            herramientas.append(abierto.group(1))
            dentro = total - abierto.start()
    return (dentro / total if total else 0.0), sorted(set(herramientas))
