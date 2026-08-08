"""Historico local, append-only, fuera del proyecto observado.

Esto es la libreta de la Fase 0 del plan, pero automatica: que se rompio,
cuantas veces y donde. Un fichero JSON por captura y un indice de una linea por
captura, para que listar sea barato y no haya que abrir mil ficheros.

Regla 7 de ARCHITECTURE: nada de esto toca el repo observado.
"""

import datetime
import hashlib
import json
import os
from pathlib import Path

from . import config

INDEX_NAME = "index.jsonl"

#: Las capturas que alguien ha MIRADO de verdad. Append-only, igual que el indice.
#:
#: Existe por la regla 10: el abandono es dato, no un bug a blindar. Este proyecto
#: mide su latencia, su overhead y su recall, y no medía lo unico que decide si
#: sirve — si lo que captura llega a leerse. Guardar mil fallos que nadie abre no
#: es una consola de errores, es un vertedero con indice.
#:
#: NO es telemetria: no sale de tu maquina, vive junto al historico y se borra
#: borrandolo. Y no blinda nada — apuntar que dejaste de mirar es justo lo
#: contrario de impedir que dejes de mirar.
READS_NAME = "leidas.jsonl"


def root():
    return config.home()


def _slug(path):
    """Nombre de carpeta estable y legible para un proyecto.

    Nombre + hash corto de la ruta completa: dos repos llamados `api` en
    carpetas distintas no se mezclan.
    """
    if not path:
        return "sin-proyecto"
    name = os.path.basename(os.path.normpath(path)) or "raiz"
    digest = hashlib.sha256(os.path.normcase(path).encode("utf-8", "replace")).hexdigest()[:8]
    safe = "".join(char if (char.isalnum() or char in "-_.") else "-" for char in name)
    return "%s-%s" % (safe[:40], digest)


def make_id(record):
    """Identificador ordenable por tiempo, sin depender de un contador global."""
    stamp = record.get("ts", "").replace(":", "").replace("-", "").replace("+", "p")
    suffix = hashlib.sha256(
        ("%s|%s|%s" % (stamp, record.get("process", {}).get("pid"), os.urandom(8))).encode(
            "utf-8", "replace"
        )
    ).hexdigest()[:6]
    return "%s-%s" % (stamp[:15] or "sin-fecha", suffix)


def write(record):
    """Persiste el registro. Devuelve la ruta, o None si no se pudo.

    Nunca lanza: quien llama esta en mitad de la muerte de un proceso ajeno.
    """
    try:
        record_id = record.get("id") or make_id(record)
        record["id"] = record_id
        project = record.get("process", {}).get("project") or record.get("process", {}).get("cwd")
        folder = root() / "errors" / _slug(project)
        folder.mkdir(parents=True, exist_ok=True)

        path = folder / ("%s.json" % record_id)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(record, handle, ensure_ascii=False, indent=1)

        _append_index(record, path)
        return path
    except BaseException:  # noqa: BLE001 - regla 9: fallar hacia el lado seguro
        return None


def _append_index(record, path):
    entry = {
        "id": record["id"],
        "ts": record.get("ts"),
        "type": record.get("exception", {}).get("type"),
        "message": (record.get("exception", {}).get("message") or "")[:200],
        "project": record.get("process", {}).get("project"),
        "where": _headline_frame(record),
        "path": str(path),
    }
    index = root() / INDEX_NAME
    index.parent.mkdir(parents=True, exist_ok=True)
    with open(index, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def mark_read(record_id, project=None):
    """Apunta que una captura se ha mirado. Silencioso y a prueba de fallos.

    Se llama cuando el estado se ENSEÑA entero (`show`, `last`), no cuando se
    lista: `gb list` es la libreta de que se rompe, no la lectura de un fallo.
    """
    if not record_id:
        return
    try:
        destino = root() / READS_NAME
        destino.parent.mkdir(parents=True, exist_ok=True)
        entrada = {
            "id": record_id,
            "ts": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        if project:
            entrada["project"] = project
        with open(destino, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entrada, ensure_ascii=False) + "\n")
    except BaseException:  # noqa: BLE001 - regla 9: leer un fallo nunca puede fallar
        pass


def read_stats(project=None):
    """(capturas, capturas distintas leidas, veces que se han abierto).

    Distintas y no totales: abrir tres veces el mismo fallo no son tres fallos
    aprovechados. La tercera cifra se guarda aparte porque volver a un registro
    viejo tambien dice algo, pero no es lo mismo.
    """
    capturas = {e.get("id") for e in read_index(project=project) if e.get("id")}
    leidas, aperturas = set(), 0
    destino = root() / READS_NAME
    if destino.exists():
        try:
            with open(destino, "r", encoding="utf-8") as handle:
                for linea in handle:
                    linea = linea.strip()
                    if not linea:
                        continue
                    try:
                        ident = json.loads(linea).get("id")
                    except ValueError:
                        continue  # una linea corrupta no invalida el recuento
                    if ident in capturas:
                        aperturas += 1
                        leidas.add(ident)
        except OSError:
            pass
    return len(capturas), len(leidas), aperturas


def read_ids():
    """El conjunto de ids apuntados en la libreta de lecturas.

    Es la materia prima del eslabon "leida" del ciclo del error: read_stats()
    devuelve recuentos, pero para cruzar lecturas con firmas hacen falta los ids.
    Se devuelve crudo, sin filtrar por proyecto — quien cruza ya tiene los ids
    del proyecto en su indice. Regla 9: una libreta ilegible es un conjunto
    vacio, no una excepcion.
    """
    destino = root() / READS_NAME
    ids = set()
    if not destino.exists():
        return ids
    try:
        with open(destino, "r", encoding="utf-8") as handle:
            for linea in handle:
                linea = linea.strip()
                if not linea:
                    continue
                try:
                    ident = json.loads(linea).get("id")
                except ValueError:
                    continue  # una linea corrupta no invalida la libreta
                if ident:
                    ids.add(ident)
    except OSError:
        pass
    return ids


#: La otra mitad del termometro de adopcion (regla 10): READS_NAME dice si lo
#: capturado se LEE; esta libreta dice si gb se INVOCA siquiera. "¿El agente tiene
#: la herramienta en cuenta?" era la unica pregunta del proyecto sin instrumento.
#: Mide invocacion, no aprovechamiento — un `gb show` corrido e ignorado cuenta
#: igual: es termometro, no cura. Tampoco es telemetria: no sale de tu maquina.
USOS_NAME = "usos.jsonl"

#: Al pasar este tamano la libreta se compacta a los ultimos 90 dias. Un
#: termometro no necesita historia infinita, necesita la ventana reciente.
_USOS_TOPE = 512 * 1024


def mark_uso(comando):
    """Apunta una invocacion de gb. Silencioso y a prueba de fallos (regla 9)."""
    if not comando:
        return
    try:
        destino = root() / USOS_NAME
        destino.parent.mkdir(parents=True, exist_ok=True)
        entrada = {
            "cmd": comando,
            "ts": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        with open(destino, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entrada, ensure_ascii=False) + "\n")
        if destino.stat().st_size > _USOS_TOPE:
            _compact_usos(destino)
    except BaseException:  # noqa: BLE001 - apuntar el uso nunca puede romper el comando
        pass


def _leer_usos(destino):
    """(comando, cuando) por linea legible; las corruptas no invalidan el recuento."""
    with open(destino, "r", encoding="utf-8") as handle:
        for linea in handle:
            linea = linea.strip()
            if not linea:
                continue
            try:
                entrada = json.loads(linea)
            except ValueError:
                continue
            cuando = parse_ts(entrada.get("ts"))
            if cuando is None or cuando.tzinfo is None:
                # Sin zona no se puede comparar con la ventana sin adivinar.
                continue
            yield entrada.get("cmd") or "?", cuando


def _compact_usos(destino, dias=90):
    corte = datetime.datetime.now().astimezone() - datetime.timedelta(days=dias)
    vivas = [
        json.dumps({"cmd": cmd, "ts": cuando.isoformat(timespec="seconds")}, ensure_ascii=False)
        for cmd, cuando in _leer_usos(destino)
        if cuando >= corte
    ]
    tmp = destino.with_suffix(".tmp")
    tmp.write_text("\n".join(vivas) + ("\n" if vivas else ""), encoding="utf-8")
    os.replace(tmp, destino)


def uso_stats(dias=7):
    """{comando: invocaciones} de los ultimos `dias` dias. Vacio si no hay libreta."""
    destino = root() / USOS_NAME
    if not destino.exists():
        return {}
    corte = datetime.datetime.now().astimezone() - datetime.timedelta(days=dias)
    counts = {}
    try:
        for cmd, cuando in _leer_usos(destino):
            if cuando >= corte:
                counts[cmd] = counts.get(cmd, 0) + 1
    except OSError:
        return {}
    return counts


def _headline_frame(record):
    """El frame que le importa a un humano: el mas interno que sea tuyo."""
    frames = record.get("frames") or []
    for frame in reversed(frames):
        if not frame.get("is_library"):
            return "%s:%s" % (frame.get("file"), frame.get("line"))
    if frames:
        return "%s:%s" % (frames[-1].get("file"), frames[-1].get("line"))
    # Sin frames: un SyntaxError no llega a ejecutar el fichero, pero la propia
    # excepcion sabe cual es. Antes se archivaba con sitio "?" y ademas escapaba
    # al filtro de efimeros —un `?` puede ser un fichero real— asi que un script
    # por stdin acababa en la cola de pendientes sin decir de donde venia.
    return (record.get("exception") or {}).get("origen")


def parse_ts(value):
    """El `ts` de una entrada a datetime consciente de zona, o None.

    Se guarda con `isoformat()` y offset local, asi que `fromisoformat` lo lee
    tal cual. None si falta o no parsea: no se adivina una fecha.
    """
    if not value:
        return None
    try:
        return datetime.datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def read_index(limit=None, project=None, since=None):
    """Entradas del indice, de la mas reciente a la mas antigua.

    `since` (datetime con zona) descarta lo anterior a ese instante. Una entrada
    con `ts` ilegible se descarta tambien: no se puede demostrar que sea
    reciente, y entregar una captura vieja como si fuera la de ahora es peor que
    no entregar nada — quien la lee arreglaria el fallo equivocado con total
    confianza.
    """
    index = root() / INDEX_NAME
    if not index.exists():
        return []
    entries = []
    with open(index, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except ValueError:
                continue  # una linea corrupta no invalida el historico
    entries.reverse()
    if project:
        target = os.path.normcase(os.path.abspath(project))
        entries = [
            item
            for item in entries
            if item.get("project") and os.path.normcase(os.path.abspath(item["project"])) == target
        ]
    if since is not None:
        fresh = []
        for item in entries:
            stamp = parse_ts(item.get("ts"))
            if stamp is not None and stamp >= since:
                fresh.append(item)
        entries = fresh
    if limit is not None:
        entries = entries[:limit]
    return entries


def is_ephemeral(entry):
    """¿La captura viene de algo que NO es un fichero del proyecto?

    `python -c ...` y la entrada por tubería producen frames cuyo "fichero" es
    `<string>` o `<stdin>`: no existen en disco, no se pueden abrir y no van a
    volver a ocurrir. Son exploración, no el código. Mezclarlas con los fallos
    reales llena la libreta de efímeros y entierra lo que sí se repite —
    reportado usando la herramienta de verdad.

    El discriminante es un HECHO, no una intención adivinada: los ángulos los
    pone el propio intérprete para las fuentes que no son ficheros. Un `?` (sin
    frame, típico de `SyntaxError`) NO cuenta: eso también le pasa a un fichero
    real, y esconderlo sería peor que el ruido.
    """
    return (entry.get("where") or "").strip().startswith("<")


def es_exploracion(entry):
    """¿La captura apunta a algo que NO es código de un proyecto?

    Más ancho que `is_ephemeral`: además de `<string>`/`<stdin>`, cuenta las
    capturas sin sitio (`where` vacío o `?`, donde no hay nada que abrir) y los
    scripts que viven en el TEMPORAL del sistema — las sondas y bancos de los
    agentes. El discriminante sigue siendo un hecho (la ruta), no una intención.

    Existe para el termómetro de lectura: no leer exploración es correcto, y
    contarla como abandono infla el denominador. Medido el 6-ago-2026: 47 de 55
    capturas del histórico eran exploración, y el "13 de 55 leídas" escondía un
    6/6 en el código real (docs/pruebas-de-uso.md).
    """
    if is_ephemeral(entry):
        return True
    fichero = fichero_de(entry)
    if not fichero:
        return True
    return any(_dentro_de(fichero, raiz) for raiz in _raices_temporales())


def fichero_de(entry):
    """El fichero de una captura, sin el `:linea`. None si no tiene sitio.

    El `where` es `ruta:linea`, y en Windows la ruta trae su propia `:` de
    unidad (`C:\\x\\a.py:7`): por eso se corta por la ULTIMA y mirando a partir
    del tercer caracter. Vivia copiado en dos sitios; una ruta partida de dos
    formas distintas es un bug de Windows esperando.
    """
    donde = (entry.get("where") or "").strip()
    if not donde or donde == "?" or donde.startswith("<"):
        return None
    return donde.rsplit(":", 1)[0] if ":" in donde[2:] else donde


def _dentro_de(ruta, base):
    """¿`ruta` cuelga de `base`? Normalizado, y con la frontera del separador.

    Comparar rutas a pelo en Windows miente —la caja y los separadores— y ya
    costo un bug (el join del ancla con git, 31-jul). `startswith` sin el
    separador tambien: `/proy-viejo` empieza por `/proy`.
    """
    try:
        ruta = os.path.normcase(os.path.abspath(ruta))
        base = os.path.normcase(os.path.abspath(base))
    except (OSError, ValueError):
        return False
    return ruta == base or ruta.startswith(base + os.sep)


def es_del_proyecto(entry, raiz):
    """¿La captura senala un fichero DE ESTE arbol?

    Lo que decide si algo entra en la cola de trabajo: un script de scratchpad
    ejecutado con el cwd aqui se archiva con este proyecto, pero su fichero vive
    en otro arbol y no hay nada que arreglar en el. La pregunta no es "¿esta en
    el temporal?" —un proyecto legitimo puede vivir ahi— sino esta.
    """
    fichero = fichero_de(entry)
    return bool(fichero) and _dentro_de(fichero, raiz)


def _raices_temporales():
    """Dónde viven los temporales: gettempdir() del entorno actual MÁS las
    raíces canónicas del SO. Solo gettempdir() no basta: un subproceso que
    redefine TMP (un sandbox, un runner) mueve la vara y el MISMO store cuenta
    distinto según quién pregunte — medido el 6-ago-2026: 12 o 25 capturas 'de
    código' sobre el mismo histórico. La vara tiene que ser del sistema, no del
    entorno de quien mira."""
    import tempfile

    raices = [tempfile.gettempdir()]
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA")
        if local:
            raices.append(os.path.join(local, "Temp"))
        raices.append(os.path.expanduser(os.path.join("~", "AppData", "Local", "Temp")))
    else:
        raices.extend(["/tmp", "/var/tmp"])
    unicas = []
    for raiz in raices:
        try:
            raiz = os.path.normcase(os.path.abspath(raiz))
        except (OSError, ValueError):
            continue
        if raiz not in unicas:
            unicas.append(raiz)
    return unicas


def summarize(entries):
    """Agrupa el histórico por firma (tipo + sitio) y cuenta ocurrencias.

    Es el "cuántas veces se rompió" que el scope promete como libreta
    automática: un KeyError que peta catorce veces en el mismo sitio es UNA
    línea con un 14, no catorce líneas que hay que contar a ojo.

    `entries` viene de lo más reciente a lo más antiguo (read_index), así que la
    primera vez que se ve una firma es la ocurrencia más nueva.
    """
    groups = {}
    order = []
    for entry in entries:
        key = (entry.get("type"), entry.get("where"))
        group = groups.get(key)
        if group is None:
            group = {
                "type": entry.get("type"),
                "where": entry.get("where"),
                "project": entry.get("project"),
                "count": 0,
                "last_ts": entry.get("ts"),
                "last_id": entry.get("id"),
                "last_message": entry.get("message"),
                "first_ts": entry.get("ts"),
            }
            groups[key] = group
            order.append(key)
        group["count"] += 1
        group["first_ts"] = entry.get("ts")  # se va quedando en la más antigua
    result = [groups[key] for key in order]
    result.sort(key=lambda g: (g["count"], g["last_ts"] or ""), reverse=True)
    return result


def load(record_id=None, project=None, since=None):
    """Carga un registro por id, o el mas reciente si no se da id.

    Con `since`, solo mira capturas posteriores a ese instante: es la diferencia
    entre "el ultimo fallo" y "el fallo de lo que acabo de ejecutar".
    """
    entries = read_index(project=project, since=since)
    if not entries:
        return None
    if record_id is None:
        entry = entries[0]
    else:
        entry = next(
            (item for item in entries if (item.get("id") or "").startswith(record_id)),
            None,
        )
        if entry is None:
            return None
    path = Path(entry.get("path", ""))
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (ValueError, OSError):
        return None
