"""El buzón de los hooks no-Python: registros crudos -> el almacén de gb.

Los hooks nativos de la consola multilenguaje (rama `spike/consola-multilenguaje`)
escriben en `~/.galaxy-brain/crashes.jsonl`. Ese fichero es un BUZÓN, no un
almacén: los hechos se quedan ahí crudos, y lo que se archiva es derivado. El
almacén sigue siendo el de siempre —`index.jsonl` + `errors/<proyecto>/<id>.json`—
y ni `store.py` ni `render.py` cambian una línea, que es literalmente lo que pide
el criterio 3 de la ADR 0012.

Una sola dirección: de fuera hacia dentro. Lo que no se pueda derivar se deja en
`None` y se DECLARA; no se inventa (regla 9).
"""

import os

# Prefijos de fichero que NO son codigo tuyo, por lenguaje. Lo que gb hace en
# Python con `capture.is_library_frame`, aqui declarado a mano: es la unica
# forma de que `_headline_index` apunte a tu codigo y no al bootstrap del
# runtime. Lo que no este en la tabla cuenta como codigo tuyo (falso negativo:
# ensucia, no esconde).
LIBRERIA = {
    "js": ("node:", "internal/", "node_modules/", "node_modules\\"),
    "ts": ("node:", "internal/", "node_modules/", "node_modules\\"),
    "java": ("java.", "javax.", "jdk.", "sun."),
    "csharp": ("System.", "Microsoft."),
    "ruby": ("<internal:",),
    "php": ("/vendor/", "\\vendor\\"),
    "go": ("/usr/local/go/", "runtime/"),
    "rust": ("/rustc/",),
}

#: Hooks que emiten la pila con el frame MAS INTERNO PRIMERO. gb asume el orden
#: de Python (mas interno el ULTIMO): sin invertir, `gb show` senala el
#: arranque del runtime en vez de tu linea. Medido con el registro js real.
INTERNO_PRIMERO = frozenset(["js", "ts", "java", "csharp", "ruby", "php", "go", "rust", "lua"])


def _es_libreria(fichero, lang):
    if not fichero:
        return False
    fich = str(fichero)
    return any(fich.startswith(p) or p in fich for p in LIBRERIA.get(lang, ()))


def _frame(bruto, lang):
    """Un frame de hook nativo al frame que `render._render_frame` sabe pintar."""
    fichero = bruto.get("file") or bruto.get("short_src") or bruto.get("source")
    # Java/C# no traen `function`: traen clase + metodo por separado.
    funcion = bruto.get("function") or bruto.get("method") or bruto.get("what") or "?"
    if bruto.get("class") and not bruto.get("function"):
        funcion = "%s.%s" % (bruto["class"], funcion)

    # `source` es un STRING en el schema v2 y una LISTA de {n,text,is_fail} en gb.
    # Sin convertir, render itera el string caracter a caracter y revienta con
    # AttributeError dentro de `gb show`.
    # Solo cuenta como texto fuente si el frame trae `file` aparte: en lua
    # `source` ES el fichero (`@C:/...`), y tomarlo por codigo pintaba la ruta
    # como si fuera la linea que peto.
    fuente = bruto.get("source")
    linea = bruto.get("line")
    if isinstance(fuente, str) and bruto.get("file"):
        fuente = [{"n": linea, "text": fuente, "is_fail": True}]
    elif not isinstance(fuente, list):
        fuente = []

    return {
        "file": fichero,
        "line": linea if isinstance(linea, int) else None,
        "function": funcion,
        "is_library": bool(bruto.get("native")) or _es_libreria(fichero, lang),
        "source": fuente,
        # None y no {}: `render` distingue "no hay locales" de "no se
        # capturaron". Ningun hook no-Python las da salvo lua.
        "locals": bruto.get("locals") or None,
    }


def _int(valor):
    """El pid llega como int en js y como STRING en java."""
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def normaliza(bruto):
    """Registro de hook nativo -> registro que `store.write` archiva y
    `render.render_record` pinta. Nunca lanza."""
    lang = bruto.get("language") or bruto.get("lang") or "unknown"

    # rust escribe `error`, el resto `exception`.
    exc = bruto.get("exception") or bruto.get("error") or {}
    # lua escribe `stack` con otras claves.
    brutos = bruto.get("frames") or bruto.get("stack") or []
    # rust escribe un unico `location` suelto en vez de una pila.
    if not brutos and bruto.get("location"):
        brutos = [bruto["location"]]

    frames = [_frame(f, lang) for f in brutos if isinstance(f, dict)]
    if lang in INTERNO_PRIMERO:
        frames.reverse()

    proc = bruto.get("process") or {}
    cwd = proc.get("cwd") or bruto.get("cwd")
    proyecto = proc.get("project") or bruto.get("project")
    if not proyecto and cwd:
        proyecto = _proyecto_de(cwd)

    # La cadena del v2 son excepciones enteras y a gb le falta `kind`, que lee
    # sin `.get`: sin esto `gb show` peta con KeyError.
    cadena = [
        {
            "kind": "cause",
            "type": (c or {}).get("type", "?"),
            "message": (c or {}).get("message", ""),
        }
        for c in (exc.get("chain") or [])
        if isinstance(c, dict)
    ]

    return {
        "schema": 1,
        "ts": bruto.get("ts"),
        # De donde vino la captura. El v2 lo llama `capture_method`.
        "source": bruto.get("capture_method") or bruto.get("hook") or "hook-nativo",
        # gb lo usa solo para decir "hilo X" cuando no es el principal.
        "thread": _hilo(exc.get("origin") or bruto.get("origin")),
        "language": lang,
        "exception": {
            "type": exc.get("type") or "?",
            "module": exc.get("module"),
            "message": exc.get("message") or "",
            "chain": cadena,
            # OJO: `origen` (es) de gb es el fichero de un SyntaxError sin
            # frames; `origin` (en) del v2 es donde afloro la excepcion. Mismo
            # nombre, cosas distintas: NO se mapean.
            "origen": None,
        },
        "frames": frames,
        "frames_trimmed": 0,
        "traceback": bruto.get("traceback") or bruto.get("backtrace"),
        "process": {
            "cwd": cwd,
            "project": proyecto,
            "pid": _int(proc.get("pid")),
            "runtime": proc.get("runtime"),
            "argv_forma": proc.get("argv_forma"),
            "program": proc.get("command"),
        },
    }


def _hilo(origen):
    """`main`/`goroutine-1`/`thread-main` -> el nombre de hilo que gb ensena.

    gb solo lo pinta si NO es `MainThread`, asi que lo normal se calla."""
    if not origen or origen in ("main", "thread-main", "exception", "process"):
        return "MainThread"
    return str(origen)


def _proyecto_de(cwd):
    """La raiz con `.git` desde cwd hacia arriba, o None. Mismo criterio que gb."""
    actual = os.path.abspath(cwd)
    while True:
        if os.path.exists(os.path.join(actual, ".git")):
            return actual
        padre = os.path.dirname(actual)
        if padre == actual:
            return None
        actual = padre


def _id_estable(registro):
    """Un id derivado del CONTENIDO, para que reingestar no duplique.

    `store.make_id` mete `os.urandom` a propósito: dos crashes idénticos en el
    mismo segundo son dos crashes, y merecen dos entradas. Aquí es al revés —
    una línea del buzón es UN hecho, y pasarla dos veces tiene que dar la misma
    entrada.

    Hace falta porque la marca de agua sola no basta: vive en un fichero
    (`crashes.offset`) que se puede borrar, rotar o perder, y entonces el buzón
    se relee entero. Pasó: 17 capturas duplicadas en un histórico real. Con el
    id derivado del contenido, releer es gratis en vez de destructivo.
    """
    import hashlib

    exc = registro.get("exception") or {}
    frames = registro.get("frames") or []
    primero = frames[0] if frames else {}
    huella = "|".join(str(x) for x in (
        registro.get("ts"), registro.get("language"), exc.get("type"),
        exc.get("message"), primero.get("file"), primero.get("line"),
        (registro.get("process") or {}).get("pid"),
    ))
    stamp = str(registro.get("ts", "")).replace(":", "").replace("-", "").replace("+", "p")
    sufijo = hashlib.sha256(huella.encode("utf-8", "replace")).hexdigest()[:6]
    return "%s-%s" % (stamp[:15] or "sin-fecha", sufijo)


def _ya_archivado(registro):
    """¿Este registro ya está en el almacén? Un `isfile`, sin leer el índice.

    O(1) a propósito: esto corre antes de CADA comando de gb, y leer el índice
    entero para decidirlo costaría el histórico completo por invocación
    (regla 2).
    """
    from . import store

    proc = registro.get("process") or {}
    destino = (store.root() / "errors" / store._slug(proc.get("project") or proc.get("cwd"))
               / ("%s.json" % registro["id"]))
    return destino.is_file()


def _ruta_buzon():
    """El buzón, bajo el home de gb — `GB_HOME` incluido.

    Los hooks usan `Path.home()` fijo y por eso no lo respetan; gb sí, y por eso
    la suite puede probar esto sin tocar el histórico de nadie. La diferencia se
    declara en vez de disimularse: lo que un hook escriba fuera de `GB_HOME` no
    se ve, y eso es de los hooks, no de aquí.
    """
    from . import config

    return os.path.join(str(config.home()), "crashes.jsonl")


def drena(limite=500):
    """Pasa al almacén las líneas NUEVAS del buzón. Devuelve cuántas entraron.

    Marca de agua por BYTES en `crashes.offset`: releer el fichero entero en cada
    invocación de gb sería pagar el histórico completo por cada comando, y contar
    líneas no vale — el buzón se escribe desde varios procesos y una línea a
    medias desplazaría la cuenta para siempre.

    Idempotente: dos pasadas seguidas no duplican. Y acotada por `limite`, porque
    un buzón de 10.000 líneas no puede convertir un `gb last` en una importación
    masiva (regla 2: < 1 s). Lo que no entra hoy entra en la siguiente.

    No lanza nunca: si algo aquí falla, el comando que la llamó sigue como si el
    buzón no existiera (propiedad 5 de ARCHITECTURE).
    """
    import json

    from . import store

    buzon = _ruta_buzon()
    marca = buzon.replace("crashes.jsonl", "crashes.offset")
    try:
        if not os.path.isfile(buzon):
            return 0
        try:
            with open(marca, "r", encoding="utf-8") as fh:
                desde = int((fh.read() or "0").strip() or 0)
        except (OSError, ValueError):
            desde = 0
        tam = os.path.getsize(buzon)
        if desde > tam:
            desde = 0          # el buzón se rotó o se vació: se relee entero
        if desde == tam:
            return 0

        entraron = 0
        with open(buzon, "r", encoding="utf-8", errors="replace") as fh:
            fh.seek(desde)
            for linea in fh:
                if entraron >= limite:
                    break
                desde += len(linea.encode("utf-8", "replace"))
                linea = linea.strip()
                if not linea:
                    continue
                try:
                    registro = normaliza(json.loads(linea))
                except Exception:      # noqa: BLE001 — una línea rota no para el resto
                    continue
                if not registro:
                    continue
                registro["id"] = _id_estable(registro)
                if _ya_archivado(registro):
                    continue          # relectura del buzón: ya estaba
                try:
                    store.write(registro)
                    entraron += 1
                except Exception:      # noqa: BLE001
                    continue
        with open(marca, "w", encoding="utf-8") as fh:
            fh.write(str(desde))
        return entraron
    except Exception:              # noqa: BLE001 — el buzón nunca tumba a gb
        return 0
