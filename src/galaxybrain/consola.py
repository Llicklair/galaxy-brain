"""Qué vía de captura de errores tiene cada lenguaje, y qué NO ve.

El criterio 4 de la [ADR 0012](../../docs/adr/0012-consola-multilenguaje.md)
pide que `gb status` **declare el mecanismo activo** — hook nativo, fallback
stderr o desactivado. Hasta hoy ese conocimiento existía solo en markdown
(`docs/CONSOLA-MULTILENGUAJE.md`), o sea que el programa no podía decirlo: la
herramienta sabía capturar y no sabía explicar por dónde.

Y el silencio, aquí, se lee como un dato. `gb last` vacío en un repo con Go
significa una de dos cosas OPUESTAS —«no ha petado nada» o «por aquí no miro»—
y presentarlas igual es exactamente el fallo que `carencias` arregló para el
grafo (ver `graph.carencias_presentes`). Esto es lo mismo para la consola.

Tres campos por lenguaje, y ninguno se inventa:

- `via`     — `hook-nativo` · `fallback-stderr` · `desactivado`. El vocabulario
              es el de la ADR, literal.
- `arranque`— cómo se instala de verdad (la variable de entorno o el envolvente).
- `techo`   — lo que esa vía NO ve. Cadena vacía solo si de verdad no hay techo
              conocido; nunca por no haberlo mirado.

Todo lo de aquí está medido en `docs/CONSOLA-MULTILENGUAJE.md` (bancos de
`gb-lenguajes`). Un lenguaje sin medir se declara `desactivado` con el motivo,
que es distinto de «no funciona».
"""

import os
import sys

# La marca que delata un hook de gb dentro de una variable de entorno que puede
# llevar tambien cosas del usuario (NODE_OPTIONS suele traer --max-old-space).
_MARCA = "gb-hook"
_MARCA_JVM = "gb-agent"

MECANISMOS = {
    "python": {
        "via": "hook-nativo",
        "arranque": "fichero .pth (sys.excepthook)",
        "env": None,
        "marca": None,
        "techo": "solo los procesos del entorno donde gb escribio el .pth",
    },
    "js": {
        "via": "hook-nativo",
        "arranque": "NODE_OPTIONS --require gb-hook.js",
        "env": "NODE_OPTIONS",
        "marca": _MARCA,
        "techo": "",
    },
    "ts": {
        "via": "hook-nativo",
        "arranque": "NODE_OPTIONS --require gb-hook.js",
        "env": "NODE_OPTIONS",
        "marca": _MARCA,
        "techo": "",
    },
    "tsx": {
        "via": "hook-nativo",
        "arranque": "NODE_OPTIONS --require gb-hook.js (heredado de Node)",
        "env": "NODE_OPTIONS",
        "marca": _MARCA,
        # Node no ejecuta .tsx: lo que corre siempre es el JS transpilado, asi
        # que la captura se guarda etiquetada como ts.
        "techo": "un .tsx nunca es lo que corre; su captura se archiva como ts",
    },
    "java": {
        "via": "hook-nativo",
        "arranque": "JAVA_TOOL_OPTIONS -javaagent:gb-agent.jar",
        "env": "JAVA_TOOL_OPTIONS",
        "marca": _MARCA_JVM,
        "techo": "la JVM imprime 'Picked up JAVA_TOOL_OPTIONS' en stderr: es del instalador, no del hook",
    },
    "kotlin": {
        "via": "hook-nativo",
        "arranque": "JAVA_TOOL_OPTIONS -javaagent:gb-agent.jar (mismo agente que java)",
        "env": "JAVA_TOOL_OPTIONS",
        "marca": _MARCA_JVM,
        "techo": "la JVM imprime 'Picked up JAVA_TOOL_OPTIONS' en stderr: es del instalador, no del hook",
    },
    "scala": {
        "via": "hook-nativo",
        "arranque": "JAVA_TOOL_OPTIONS -javaagent:gb-agent.jar (mismo agente que java)",
        "env": "JAVA_TOOL_OPTIONS",
        "marca": _MARCA_JVM,
        "techo": "la JVM imprime 'Picked up JAVA_TOOL_OPTIONS' en stderr: es del instalador, no del hook",
    },
    "csharp": {
        "via": "hook-nativo",
        "arranque": "DOTNET_STARTUP_HOOKS GbHook.dll",
        "env": "DOTNET_STARTUP_HOOKS",
        "marca": "GbHook",
        "techo": "",
    },
    "ruby": {
        "via": "hook-nativo",
        "arranque": "RUBYOPT -r gb-hook.rb",
        "env": "RUBYOPT",
        "marca": _MARCA,
        "techo": "",
    },
    "php": {
        "via": "hook-nativo",
        "arranque": "php -d auto_prepend_file=gb-hook.php",
        # Medido el 16-ago: por variable de entorno no entra; hay que pasar la
        # bandera en la invocacion. Se declara en vez de fingir que se arma solo.
        "env": None,
        "marca": None,
        "techo": "no se arma con una variable de entorno: hay que pasar la bandera al invocar php",
    },
    "lua": {
        "via": "hook-nativo",
        "arranque": "LUA_INIT @gb-hook.lua",
        "env": "LUA_INIT",
        "marca": _MARCA,
        "techo": "",
    },
    "go": {
        "via": "fallback-stderr",
        "arranque": "envolvente: gb run <programa>",
        "env": None,
        "marca": None,
        "techo": "el tipo sale del mensaje en 6 de 9 formas de panic; un panic en hilo secundario deja exit 0 y cero registros",
    },
    "rust": {
        "via": "fallback-stderr",
        "arranque": "envolvente: gb run <programa>",
        "env": None,
        "marca": None,
        "techo": "igual que go, y set_hook exigiria tocar tu codigo",
    },
    "c": {
        # Dos plataformas, dos mecanismos distintos: se resuelve en estado().
        "via": "hook-nativo",
        "arranque": "LD_PRELOAD gb-hook.so",
        "env": "LD_PRELOAD",
        "marca": _MARCA,
        "techo": "",
    },
    "dart": {
        "via": "desactivado",
        "arranque": "—",
        "env": None,
        "marca": None,
        "techo": "runZonedGuarded es manejo puro: lleva el exit code de 255 a 0 y borra la traza",
    },
    "elixir": {
        "via": "desactivado",
        "arranque": "—",
        "env": None,
        "marca": None,
        "techo": "sin medir: Erlang no se pudo instalar sin administrador",
    },
    "swift": {
        "via": "desactivado",
        "arranque": "—",
        "env": None,
        "marca": None,
        "techo": "sin medir: el toolchain no se pudo instalar sin administrador",
    },
}

# En Windows no existe LD_PRELOAD, asi que C cambia de mecanismo entero: el
# programa se lanza como depurado y se suelta el depurador en la primera
# excepcion mortal, para que su propio filtro de ultimo recurso siga corriendo.
# Medido el 18-ago-2026: 100 % en programa intacto, capturados y espurios.
_C_WINDOWS = {
    "via": "hook-nativo",
    "arranque": "envolvente: gb-run.exe --soltar <programa>",
    "env": None,
    "marca": None,
    "techo": "tras soltar el depurador deja de observar: una segunda excepcion ya no se ve",
}


def mecanismo(lang, plataforma=None):
    """La ficha de `lang`, resuelta para la plataforma (None = la de ahora)."""
    plataforma = sys.platform if plataforma is None else plataforma
    if lang == "c" and plataforma.startswith("win"):
        return dict(_C_WINDOWS)
    ficha = MECANISMOS.get(lang)
    return dict(ficha) if ficha else None


def armado(lang, entorno=None, plataforma=None):
    """¿Está la vía puesta AHORA MISMO? True, False, o None si no es comprobable.

    None no es un fallo: php se arma con una bandera en la invocación y go con
    un envolvente, y no hay nada en el entorno que delate ninguno de los dos.
    Decir «no armado» de algo que no se puede comprobar seria inventar.
    """
    entorno = os.environ if entorno is None else entorno
    ficha = mecanismo(lang, plataforma)
    if not ficha:
        return None
    if lang == "python":
        from . import bootstrap
        return bool(bootstrap.is_enabled())
    if ficha["via"] == "desactivado":
        return False
    if not ficha["env"]:
        return None
    return ficha["marca"].lower() in (entorno.get(ficha["env"]) or "").lower()


def estado(root, entorno=None, plataforma=None):
    """Una ficha por lenguaje PRESENTE bajo `root`, python incluido siempre.

    Solo los lenguajes que hay de verdad en el árbol: enumerar los 17 en un repo
    de uno es ruido, y el ruido se acaba saltando igual que un aviso falso — la
    misma razón que en `graph.carencias_presentes`.
    """
    from . import graph

    presentes = set(graph.lenguajes_presentes(root))
    presentes.add("python")  # gb corre sobre Python: su consola siempre aplica
    fichas = []
    for lang in sorted(presentes):
        ficha = mecanismo(lang, plataforma)
        if not ficha:
            continue
        ficha["lenguaje"] = lang
        ficha["armado"] = armado(lang, entorno, plataforma)
        fichas.append(ficha)
    return fichas


def linea(ficha):
    """La ficha en una línea, para `gb status`. Sin colores: los pone quien pinta."""
    if ficha["armado"] is True:
        marca = "armado"
    elif ficha["armado"] is False:
        marca = "NO armado"
    else:
        marca = "no comprobable"
    texto = "%s (%s) — %s" % (ficha["via"], ficha["arranque"], marca)
    if ficha["techo"]:
        texto += " · no ve: %s" % ficha["techo"]
    return texto
