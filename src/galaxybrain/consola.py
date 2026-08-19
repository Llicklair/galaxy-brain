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
        # Cambia de "desactivado" a envolvente el 19-ago-2026, y no por rebajar
        # el criterio: el que fallaba era `runZonedGuarded` (manejo puro, exit
        # 255 -> 0, traza borrada y reescribir tu main()). Leer su stderr desde
        # fuera no toca el programa y le deja el exit code intacto.
        "via": "fallback-stderr",
        "arranque": "envolvente: python gb-run.py dart run <programa>",
        "env": None,
        "marca": None,
        "techo": ("solo se ve lo que MATA al proceso: una excepcion capturada dentro, o en un "
                  "isolate que no tumba el programa, no deja registro"),
    },
    "elixir": {
        # El envolvente ya lo cubre, pero NADIE lo ha ejecutado: no hay Erlang
        # en esta maquina (su instalador exige elevacion), asi que el parser
        # esta escrito contra el formato documentado y no contra una tirada
        # real. Se dice aqui en vez de dejar que se lea como verificado.
        "via": "fallback-stderr",
        "arranque": "envolvente: python gb-run.py mix run",
        "env": None,
        "marca": None,
        "techo": ("SIN MEDIR: no hay Erlang en esta maquina, asi que su parser esta escrito "
                  "contra el formato documentado y no contra una ejecucion real"),
    },
    "swift": {
        # Sigue en `desactivado` aunque gb ya empaquete su fuente: NADIE lo ha
        # medido. Ponerlo en `hook-nativo` porque compila seria dar por
        # verificado lo que solo esta construido, y esa es exactamente la
        # diferencia que este campo existe para marcar.
        "via": "desactivado",
        "arranque": "DYLD_INSERT_LIBRARIES libgb_hook.dylib (se construye con swiftc)",
        "env": "DYLD_INSERT_LIBRARIES",
        "marca": "gb_hook",
        "techo": ("sin medir: el toolchain exige elevacion en esta maquina. Se construye donde "
                  "haya swiftc (macOS), y ahi aun depende de que SIP permita la inyeccion"),
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


#: Los que no tienen gancho de observacion instalable y se cubren ENVOLVIENDO la
#: invocacion: `gb-run.py` lanza el programa y lee su stderr cuando muere. Es
#: Python puro y sin dependencias, asi que no hay nada que compilar.
#:
#: Su techo va escrito en MECANISMOS y no se disimula: el tipo se deriva del
#: mensaje en 6 de 9 formas de panic, y un panic en hilo secundario deja exit 0
#: y cero registros. Cubierto por una via distinta, con su limite escrito — que
#: es lo que este proyecto le exige a cualquier capa.
HOOKS_ENVOLVENTE = {
    "go": "gb-run.py",
    "rust": "gb-run.py",
    # Dart y elixir entran por aqui y no por un hook interno: el suyo exige
    # tocar el codigo de quien lo instala (dart, reescribir main(); elixir,
    # editar config.exs y lib/). Desde fuera no hace falta, y ademas dart
    # conserva su exit 255 en vez de convertirlo en 0.
    "dart": "gb-run.py",
    "elixir": "gb-run.py",
}

#: Los hooks de fichero suelto y cero dependencias: se copian y ya funcionan.
#: Los que hay que construir van en COMPILABLES, mas abajo.
HOOKS_EMPAQUETADOS = {
    "js": "gb-hook.js",
    "ts": "gb-hook.js",     # Node ejecuta TS nativo: mismo hook, sin cambios
    "tsx": "gb-hook.js",    # y un .tsx nunca es lo que corre (ver `techo`)
    "ruby": "gb-hook.rb",
    "php": "gb-hook.php",
    "lua": "gb-hook.lua",
}

#: Como se arma cada uno con la ruta REAL, ya desplegada. `None` = no se arma
#: con una variable de entorno y hay que decirlo, no disimularlo.
_ARRANQUE_REAL = {
    "NODE_OPTIONS": 'NODE_OPTIONS="--require %s"',
    "RUBYOPT": 'RUBYOPT="-r %s"',
    "LUA_INIT": 'LUA_INIT="@%s"',
}

#: Los que no se arman con una variable de entorno igualmente merecen la linea
#: EXACTA con su ruta: que php pida una bandera no es motivo para devolverle al
#: usuario un nombre de fichero suelto que tendra que ir a buscar.
_ARRANQUE_POR_LENGUAJE = {
    "php": "php -d auto_prepend_file=%s <tu script.php>",
    "go": "python %s go run ./cmd",
    "rust": "python %s cargo run",
    "dart": "python %s dart run tu_programa.dart",
    "elixir": "python %s mix run",
}


def _dir_hooks():
    from . import config

    return os.path.join(str(config.home()), "hooks")


def desplegados():
    """Los hooks que YA estan en disco: {lenguaje: ruta}. Vacio si ninguno."""
    base = _dir_hooks()
    fuera = {}
    for lang, fichero in HOOKS_EMPAQUETADOS.items():
        ruta = os.path.join(base, fichero)
        if os.path.isfile(ruta):
            fuera[lang] = ruta
    return fuera


def despliega(destino=None):
    """Copia a disco los hooks que gb trae. Devuelve una ficha por lenguaje.

    Hasta hoy `consola.py` DECLARABA que js se arma con `NODE_OPTIONS` y nadie
    ponia el fichero en ningun sitio: la consola multilenguaje estaba medida,
    documentada y era inusable. Esto la pone en el disco del usuario.

    Lo que gb NO puede hacer, y por eso se imprime en vez de ejecutarse: un
    proceso no puede cambiar el entorno de quien lo llamo. La variable la
    exporta la persona (o su orquestador); aqui se da la linea exacta, con la
    ruta real, para que no haya que inventarsela.
    """
    import shutil

    base = destino or _dir_hooks()
    os.makedirs(base, exist_ok=True)
    origen = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hooks_lang")

    todos = dict(HOOKS_EMPAQUETADOS)
    todos.update(HOOKS_ENVOLVENTE)

    fichas = []
    for lang in sorted(todos):
        fichero = todos[lang]
        de, a = os.path.join(origen, fichero), os.path.join(base, fichero)
        if not os.path.isfile(de):
            continue
        if not os.path.isfile(a) or os.path.getmtime(de) > os.path.getmtime(a):
            shutil.copyfile(de, a)
        ficha = mecanismo(lang) or {}
        plantilla = (_ARRANQUE_REAL.get(ficha.get("env") or "")
                     or _ARRANQUE_POR_LENGUAJE.get(lang))
        fichas.append({
            "lenguaje": lang,
            "ruta": a,
            # La linea exacta, con la ruta real ya puesta.
            "exporta": (plantilla % a) if plantilla else None,
            "arranque": ficha.get("arranque") or "",
            # Si se arma exportando una variable o invocando con bandera: no es
            # lo mismo y el usuario tiene que saber cual de las dos le toca.
            "por_entorno": bool(ficha.get("env")),
        })
    return fichas


#: Los hooks que NO son un fichero suelto: hay que construirlos. gb trae la
#: FUENTE y la compila en la maquina del usuario con la herramienta que ese
#: lenguaje ya exige tener — quien programa en Java tiene un JDK, y si no lo
#: tiene tampoco tiene nada que capturar. Lo que no se hace es meter binarios en
#: el repo: no se pueden auditar, no valen para otra plataforma y envejecen mal.
#:
#: `herramientas` se comprueba ANTES de intentar nada, para poder decir «te
#: falta javac» en vez de escupir el error de un compilador que no esta.
COMPILABLES = {
    "java": {
        "dir": "jvm", "salida": "gb-agent.jar", "herramientas": ("javac", "jar"),
        "exporta": 'JAVA_TOOL_OPTIONS="-javaagent:%s"',
    },
    # Kotlin y Scala corren sobre la misma maquina virtual y heredan el agente
    # sin tocar una linea: medido el 18-ago-2026, 100 % los dos.
    "kotlin": {
        "dir": "jvm", "salida": "gb-agent.jar", "herramientas": ("javac", "jar"),
        "exporta": 'JAVA_TOOL_OPTIONS="-javaagent:%s"',
    },
    "scala": {
        "dir": "jvm", "salida": "gb-agent.jar", "herramientas": ("javac", "jar"),
        "exporta": 'JAVA_TOOL_OPTIONS="-javaagent:%s"',
    },
    "csharp": {
        "dir": "dotnet", "salida": "GbHook.dll", "herramientas": ("dotnet",),
        "exporta": 'DOTNET_STARTUP_HOOKS="%s"',
    },
    "c": {
        "dir": "c", "salida": "gb-hook.so", "herramientas": ("gcc",),
        "exporta": 'LD_PRELOAD="%s"',
    },
    # Swift solo se construye donde hay `swiftc` —en la practica, macOS— y su
    # instalacion depende ademas de que SIP permita DYLD_INSERT_LIBRARIES. Se
    # empaqueta igual: fuera de macOS dira "falta swiftc", que es un hecho sobre
    # ESTA maquina, y no "swift no se puede", que seria falso.
    "swift": {
        "dir": "swift", "salida": "libgb_hook.dylib", "herramientas": ("swiftc",),
        "exporta": 'DYLD_INSERT_LIBRARIES="%s"',
    },
}

#: C en Windows no es el mismo hook con otra ruta: es otro mecanismo (envolvente
#: depurador), otra fuente y otra forma de invocarlo.
_COMPILABLE_C_WINDOWS = {
    "dir": "c", "salida": "gb-run.exe", "herramientas": ("gcc",),
    "exporta": "%s --soltar <tu programa.exe>",
}


def compilable(lang, plataforma=None):
    """La ficha de construccion de `lang`, resuelta para la plataforma."""
    plataforma = sys.platform if plataforma is None else plataforma
    if lang == "c":
        return dict(_COMPILABLE_C_WINDOWS if plataforma.startswith("win")
                    else COMPILABLES["c"])
    ficha = COMPILABLES.get(lang)
    return dict(ficha) if ficha else None


def _orden(ficha, carpeta, plataforma):
    """El comando de construccion, ya resuelto. Lista de argv, sin shell."""
    import glob

    if ficha["dir"] == "jvm":
        clases = sorted(os.path.basename(c) for c in glob.glob(os.path.join(carpeta, "*.class")))
        if not clases:   # primera pasada: compilar
            return [["javac", "GbAgent.java"]]
        return [["jar", "cfm", "gb-agent.jar",
                 os.path.join("META-INF", "MANIFEST.MF")] + clases]
    if ficha["dir"] == "dotnet":
        return [["dotnet", "build", os.path.join("GbHook", "GbHook.csproj"),
                 "-c", "Release", "-o", ".", "--nologo", "-v", "quiet"]]
    if ficha["dir"] == "swift":
        return [["swiftc", "-emit-library", "-o", "libgb_hook.dylib", "gb_hook.swift"]]
    if plataforma.startswith("win"):
        return [["gcc", "-O2", "-Wall", "-o", "gb-run.exe", "gb_run_win.c"]]
    return [["gcc", "-shared", "-fPIC", "-O2", "-o", "gb-hook.so", "gb_hook.c"]]


def compila(lang, base=None, plataforma=None, timeout=300):
    """Construye el hook de `lang` en casa del usuario. Nunca lanza.

    Devuelve `{"lenguaje", "ok", "ruta", "exporta", "falta", "error"}`. `falta`
    lleva las herramientas que no estan, que es la unica respuesta util cuando
    no se puede construir: «no disponible» a secas no dice si el problema es
    tuyo, mio o de la maquina.
    """
    import shutil
    import subprocess

    plataforma = sys.platform if plataforma is None else plataforma
    ficha = compilable(lang, plataforma)
    salida = {"lenguaje": lang, "ok": False, "ruta": None,
              "exporta": None, "falta": [], "error": ""}
    if not ficha:
        return salida

    falta = [h for h in ficha["herramientas"] if not shutil.which(h)]
    if falta:
        salida["falta"] = falta
        return salida

    base = base or _dir_hooks()
    origen = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "hooks_lang", ficha["dir"])
    carpeta = os.path.join(base, ficha["dir"])
    if not os.path.isdir(origen):
        salida["error"] = "esta instalacion de gb no trae la fuente de %s" % lang
        return salida
    # Se construye en casa del usuario y no en site-packages: ese directorio
    # puede ser de solo lectura, compartido entre entornos, o borrarse al
    # actualizar. Y asi el .jar vive al lado del resto de hooks.
    shutil.copytree(origen, carpeta, dirs_exist_ok=True)

    destino = os.path.join(carpeta, ficha["salida"])
    if os.path.isfile(destino):
        salida.update(ok=True, ruta=destino, exporta=ficha["exporta"] % destino)
        return salida

    try:
        for _ in range(2):   # jvm necesita dos pasadas: javac y luego jar
            for orden in _orden(ficha, carpeta, plataforma):
                proceso = subprocess.run(orden, cwd=carpeta, capture_output=True,
                                         text=True, timeout=timeout)
                if proceso.returncode != 0:
                    salida["error"] = (proceso.stderr or proceso.stdout or "").strip()[:400]
                    return salida
            if os.path.isfile(destino):
                break
    except (OSError, subprocess.SubprocessError) as exc:
        salida["error"] = str(exc)[:400]
        return salida

    if not os.path.isfile(destino):
        salida["error"] = "el comando termino bien pero no dejo %s" % ficha["salida"]
        return salida
    salida.update(ok=True, ruta=destino, exporta=ficha["exporta"] % destino)
    return salida


def construye_todo(base=None, plataforma=None):
    """Intenta construir TODOS los compilables. Una ficha por lenguaje.

    Se intentan todos aunque falten herramientas: el resultado con `falta` es
    justo lo que convierte «no tienes la consola de Java» en «instala un JDK».
    """
    vistos, fichas = {}, []
    for lang in sorted(COMPILABLES):
        ficha = compilable(lang, plataforma)
        clave = (ficha["dir"], ficha["salida"])
        if clave in vistos:
            # java/kotlin/scala comparten agente: se construye una vez y se
            # nombran los tres, porque el usuario busca SU lenguaje en la lista.
            copia = dict(vistos[clave])
            copia["lenguaje"] = lang
            fichas.append(copia)
            continue
        resultado = compila(lang, base, plataforma)
        vistos[clave] = resultado
        fichas.append(resultado)
    return fichas


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
