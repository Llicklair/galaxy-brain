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

Fase 1 cubrió el camino del desconocido — el primer contacto medido en la
sonda del lanzamiento: el aviso de captura, la ficha de `gb show`/`gb last`,
el ancla al grafo y `on`/`off`/`status`. Fase 2 (15-ago) cubre el camino
rutinario del verificador: `gb tests` entero (cabecera, motivos, checkpoint
--isolated/--union y el pie honesto) y el marco de `gb check` (brief del
hook incluido). La prosa de motivo se traduce AL CREARSE, así que con
GB_LANG=en también sale en inglés en `--json`: es una frase para humanos,
no un hecho del código. Pendiente por fases: los textos de cada señal de
check, floor (sus niveles se componen dinámicamente: no es una tabla, es
su propio refactor) y el mapa.
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
    # fase 2 — el verificador: gb tests (cabecera, motivos y el pie honesto)
    "Nada que correr: %s": "Nothing to run: %s",
    "La suite ENTERA: %d test(s) en %d fichero(s)":
        "The WHOLE suite: %d test(s) in %d file(s)",
    "%d de %d test(s) (%.0f%%) en %d fichero(s)":
        "%d of %d test(s) (%.0f%%) in %d file(s)",
    "Disparado por %d simbolo(s) del diff:":
        "Triggered by %d symbol(s) in the diff:",
    "  ... y %d mas": "  ... and %d more",
    "Ficheros:": "Files:",
    "  (subproceso: va siempre)": "  (subprocess: always runs)",
    "Lo que esto NO garantiza:": "What this does NOT guarantee:",
    "  - la seleccion sale del grafo de LLAMADAS: lo que se invoca por tabla\n"
    "    o por getattr no deja arista que seguir (los subprocesos si estan\n"
    "    cubiertos: sus ficheros entran enteros)":
        "  - selection comes from the CALL graph: whatever is invoked through\n"
        "    a table or getattr leaves no edge to follow (subprocesses ARE\n"
        "    covered: their files run whole)",
    "  - la herencia propaga por la arista extends (bases resueltas por\n"
    "    nombre): una base dinamica o de otro paquete sigue sin arista que\n"
    "    seguir, y ahi la seleccion no ve a las subclases":
        "  - inheritance propagates through the extends edge (bases resolved\n"
        "    by name): a dynamic base or one from another package still leaves\n"
        "    no edge, and there the selection cannot see the subclasses",
    "  - no ejecuta nada: pasa estos ficheros a pytest, o usa --run":
        "  - it runs nothing: pass these files to pytest, or use --run",
    "la raiz no existe o no es un directorio: %s":
        "the root does not exist or is not a directory: %s",
    "el diff esta vacio: nada que correr": "the diff is empty: nothing to run",
    "no se pudo leer el diff (¿sin git, o rango invalido?): todo":
        "could not read the diff (no git, or invalid range?): everything runs",
    "%s tocado: cambia la suite entera, se corre todo":
        "%s touched: it changes the whole suite, everything runs",
    "el diff no toca ningun .py que el grafo vea: todo":
        "the diff touches no .py the graph can see: everything runs",
    "%s: su grafo de llamadas no esta medido lo bastante completo como para "
    "estrechar sin arriesgar un verde falso, asi que se corre todo":
        "%s: its call graph is not measured complete enough to narrow without "
        "risking a false green, so everything runs",
    "import interno roto: `%s` (%s:%s) apunta a algo que ya no existe%s — "
    "una referencia colgante no deja arista por la que subir, se corre todo":
        "broken internal import: `%s` (%s:%s) points at something that no "
        "longer exists%s — a dangling reference leaves no edge to climb, so "
        "everything runs",
    "el diff toca .py pero no cae dentro de ningun simbolo del grafo "
    "(codigo a nivel de modulo, imports, constantes): todo":
        "the diff touches .py but lands inside no graph symbol (module-level "
        "code, imports, constants): everything runs",
    "el cierre de llamantes no termino (¿ciclo de llamadas?): todo":
        "the caller closure did not finish (call cycle?): everything runs",
    "ningun test alcanza lo que cambiaste — eso es el dato, no un ahorro: todo":
        "no test reaches what you changed — that is the finding, not a "
        "saving: everything runs",
    "%d test(s) alcanzan los %d simbolo(s) que toca el diff":
        "%d test(s) reach the %d symbol(s) the diff touches",
    # fase 2 — el verificador: gb tests --isolated/--union (el checkpoint)
    "no es un repositorio git: no hay base limpia contra la que medir":
        "not a git repository: no clean base to measure against",
    "el repositorio no tiene ningun commit todavia":
        "the repository has no commits yet",
    "no se pudo obtener el diff: %s": "could not get the diff: %s",
    "no se pudo montar el arbol limpio: %s":
        "could not set up the clean tree: %s",
    "arbol limpio en %s + tu diff": "clean tree at %s + your diff",
    "el diff no aplica sobre %s: %s": "the diff does not apply on %s: %s",
    "no se pudo lanzar pytest: %s": "could not launch pytest: %s",
    "no es un repositorio git": "not a git repository",
    "ningun worktree con cambios que verificar":
        "no worktree with changes to verify",
    "--- %s (solo) ---": "--- %s (alone) ---",
    "--- union de %d rama(s) sobre %s ---": "--- union of %d branch(es) on %s ---",
    "los worktrees parten de bases distintas (%s): no se calcula la union":
        "the worktrees start from different bases (%s): the union is not computed",
    "hay tests que no viajan (%s): la union esta tan incompleta como esas ramas":
        "there are tests that do not travel (%s): the union is as incomplete "
        "as those branches",
    "no se pudo montar la union: %s": "could not set up the union: %s",
    "no se pudo componer la union: %s": "could not compose the union: %s",
    "[gb tests] --union ejecuta suites: pide --run explicitamente\n":
        "[gb tests] --union runs suites: ask for --run explicitly\n",
    "%d fichero(s) de test no existen en el arbol limpio (git add?):":
        "%d test file(s) do not exist in the clean tree (git add?):",
    # fase 2 — el verificador: gb check (el brief del hook y el marco largo)
    "[gb check] SIN COMPROBAR: %s": "[gb check] NOT CHECKED: %s",
    " · onda: %d simbolo(s), max %d llamante(s)":
        " · ripple: %d symbol(s), max %d caller(s)",
    "[gb check] %s: %d fichero(s) de test tocado(s), sin senales%s "
    "(detalle: gb check%s)":
        "[gb check] %s: %d test file(s) touched, no signals%s "
        "(detail: gb check%s)",
    "%s — %d fichero(s) de test tocado(s), %d senal(es)":
        "%s — %d test file(s) touched, %d signal(s)",
    "SENALES del cambio (justifica cada una, no bloquean):":
        "SIGNALS in the change (justify each one; they do not block):",
    "SIN COMPROBAR: %s": "NOT CHECKED: %s",
    "Sin senales.": "No signals.",
    "ACOPLAMIENTO nuevo vs %s:": "NEW COUPLING vs %s:",
    "Dependencia(s) nueva(s) sin regla de frontera (punto ciego — informa, no bloquea):":
        "New dependency(ies) without a boundary rule (blind spot — informs, "
        "does not block):",
    "Sin acoplamiento nuevo vs %s (%d modulos).":
        "No new coupling vs %s (%d modules).",
    "ONDA del diff (simbolos tocados y quien les llama — informa, no bloquea):":
        "RIPPLE of the diff (touched symbols and their callers — informs, "
        "does not block):",
    "  %s %s · %s:%s · %d le llaman": "  %s %s · %s:%s · %d call it",
    "  ... y %d mas (la lista entera: gb check --json)":
        "  ... and %d more (the full list: gb check --json)",
    "  (quien exactamente: gb calls <simbolo> --depth 2)":
        "  (who exactly: gb calls <symbol> --depth 2)",
    "Lo que esto NO ha mirado:": "What this has NOT looked at:",
}


def t(plantilla):
    """La plantilla en el idioma activo; se traduce ANTES de formatear."""
    if not en():
        return plantilla
    return _TABLA.get(plantilla, plantilla)
