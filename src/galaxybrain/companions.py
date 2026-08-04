"""Lo externo: detectado y verificado, nunca replicado.

La regla 7 dice cómo se integra una herramienta ajena — *detección + instalador
oficial + verificación* — y este módulo es esa regla hecha código. No envuelve
nada, no llama a nada por ti: mira qué escribió cada herramienta en los
ficheros compartidos del proyecto, y lo dice.

Aquí vivió el detector de GitNexus; se retiró (2026-08) al decidir que el grafo
de símbolos es columna propia de `gb`, no una herramienta ajena que señalar. La
historia y la medición que lo avala (93% de recall de `gb symbols` contra ese
índice) quedan en floor.py y docs/pruebas-de-uso.md (2026-07-30).
"""

import re

#: Bloques que una herramienta se escribe a si misma en un fichero compartido.
#: Convencion comun (`<!-- x:start -->` … `<!-- x:end -->`), asi que se detecta el
#: patron, no una herramienta concreta (hard rule 6).
_TOOL_BLOCK = re.compile(
    r"<!--\s*([\w.-]+):start\s*-->.*?<!--\s*\1:end\s*-->", re.DOTALL | re.IGNORECASE
)
_TOOL_OPEN = re.compile(r"<!--\s*([\w.-]+):start\s*-->", re.IGNORECASE)


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
