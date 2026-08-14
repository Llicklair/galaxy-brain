"""El idioma de la salida: español por defecto, inglés con `GB_LANG=en`.

Pedido el 14-ago, horas después del lanzamiento: la alternativa inglesa
importa para adopción. El diseño respeta las dos leyes de la casa:

- **La norma va en el defecto**: el español sigue siendo el defecto y la
  FUENTE — los 797 tests hablan español y no se tocan; el inglés es opt-in
  por entorno, imposible de activar sin querer.
- **Cobertura declarada, no fingida**: la tabla traduce PLANTILLAS enteras
  (con sus %s dentro, ANTES de formatear) y lo que no está en ella sale en
  español tal cual. El README lista qué superficies están cubiertas; una
  cadena a medias mentiría con acento.

Hoy cubre el camino del desconocido — el primer contacto medido en la sonda
del lanzamiento: el aviso de captura, la ficha de `gb show`/`gb last`, el
ancla al grafo y `on`/`off`/`status`. El resto (mapa, verificador, floor)
entra por fases, cada una con su entrada en la tabla y su test.
"""
import os


def en():
    """True si la salida va en inglés (GB_LANG=en, en-US, english...)."""
    return (os.environ.get("GB_LANG") or "").lower().startswith("en")


#: español exacto (la clave ES la cadena que usa el código) -> inglés.
_TABLA = {
    # el tiempo relativo de la ficha
    "hace %ds": "%ds ago",
    "hace %dmin": "%dmin ago",
    "hace %dh": "%dh ago",
    "hace %dd": "%dd ago",
    # la ficha de show/last
    "causada por": "caused by",
    "durante el manejo de": "while handling",
    "  (%d frames mas: gb show %s --full)": "  (%d more frames: gb show %s --full)",
    "  (%d frames externos recortados por GB_MAX_FRAMES)":
        "  (%d external frames trimmed by GB_MAX_FRAMES)",
    "%sefimero (%s: no es un fichero del proyecto)":
        "%sephemeral (%s: not a project file)",
    "%shilo %s": "%sthread %s",
    "  [libreria]": "  [library]",
    "      (locales no capturadas: frame de libreria — GB_ALL_FRAMES=1)":
        "      (locals not captured: library frame — GB_ALL_FRAMES=1)",
    # el aviso que ve todo desconocido en su primer crash
    "\n[galaxy-brain] estado capturado -> gb show %s\n":
        "\n[galaxy-brain] state captured -> gb show %s\n",
    # el ancla al grafo
    "en el grafo: %s": "in the graph: %s",
    "  nadie le llama en el grafo (entrada directa o despacho dinamico)":
        "  nothing calls it in the graph (direct entry or dynamic dispatch)",
}


def t(plantilla):
    """La plantilla en el idioma activo; se traduce ANTES de formatear."""
    if not en():
        return plantilla
    return _TABLA.get(plantilla, plantilla)
