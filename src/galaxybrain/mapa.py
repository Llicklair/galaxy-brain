"""El mapa persistente: lo que el grafo era la ultima vez que alguien miro.

Revierte (14-ago-2026, decision del owner) el "grafo persistido: no" de
docs/grafo-neuronal-orquestacion.md. La objecion de entonces era real — un mapa
guardado miente en cuanto alguien edita — y la respuesta no es negar el
problema sino quitarle el colmillo: **el snapshot nunca se sirve como estado
actual**. El estado actual se RE-DERIVA siempre (437 ms medidos sobre este
repo, 13-ago); el snapshot solo se usa para COMPARAR — "desde tu ultima mirada:
+3 simbolos, 2 aristas nuevas" — y despues se sobrescribe. Un snapshot viejo no
puede mentir: como mucho produce un delta mas gordo.

Que se guarda: los quals de los nodos, las aristas, una huella (mtime_ns, size)
por fichero y el instante. Fuera del proyecto observado (ARCHITECTURE regla 7):
vive en `config.home()/<slug>/mapa.json`, junto al historico de capturas.

La huella habilita el atajo honesto: si NINGUN fichero cambio desde el
snapshot, el delta es por definicion vacio y quien llama puede decirlo sin
recalcular. El atajo dice "sin cambios desde <ts>", no finge haber mirado.
"""

import json
import os
import time

from . import config, store


def _ruta(root):
    """Donde vive el snapshot de este proyecto. Nunca dentro del proyecto."""
    return os.path.join(str(config.home()), store._slug(os.path.abspath(root)), "mapa.json")


def huellas(root, informe):
    """{ruta relativa: [mtime_ns, size]} de los ficheros que aportaron nodos.

    Se derivan del informe y no de un walk propio: asi la huella cubre
    exactamente lo que el grafo miro, con sus mismos skips, y las dos listas
    no pueden divergir.
    """
    out = {}
    for nodo in informe.get("nodes") or []:
        rel = nodo.get("file")
        if not rel or rel in out:
            continue
        try:
            st = os.stat(os.path.join(root, rel))
            out[rel] = [st.st_mtime_ns, st.st_size]
        except OSError:
            continue
    return out


def cargar(root):
    """El snapshot anterior, o None si no hay (primera mirada) o esta corrupto.

    Un snapshot ilegible se trata como ausente, no como error: la unica
    consecuencia es que esta mirada no tiene con que compararse.
    """
    try:
        with open(_ruta(root), "r", encoding="utf-8") as f:
            datos = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(datos, dict) or "quals" not in datos:
        return None
    return datos


def guardar(root, informe):
    """Sobrescribe el snapshot con lo que esta mirada acaba de derivar.

    Silencioso a prueba de fallos (regla 9): si el disco no deja, la mirada
    sigue valiendo — solo se pierde la memoria para la proxima.
    """
    datos = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "quals": sorted(n["qual"] for n in informe.get("nodes") or []),
        "edges": sorted(map(tuple, informe.get("edges") or [])),
        "huellas": huellas(root, informe),
    }
    ruta = _ruta(root)
    try:
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        tmp = ruta + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp, ruta)
    except OSError:
        return None
    return ruta


def sin_cambios(root, viejo):
    """¿Ningun fichero del snapshot cambio, y no aparecio ninguno nuevo?

    Solo compara huellas — barato (un stat por fichero). True permite decir
    "sin cambios desde <ts>" sin re-derivar. Cualquier duda (fichero ausente,
    stat fallido) es False: en la duda, se mira de verdad.
    """
    if not viejo:
        return False
    guardadas = viejo.get("huellas") or {}
    if not guardadas:
        return False
    for rel, (mtime, size) in guardadas.items():
        try:
            st = os.stat(os.path.join(root, rel))
        except OSError:
            return False                    # borrado: hay que mirar
        if st.st_mtime_ns != mtime or st.st_size != size:
            return False
    # Ficheros NUEVOS que el snapshot no conoce: sin esto, crear un modulo
    # entero daria "sin cambios" — el mismo agujero que el diff con los
    # ficheros sin trackear, y se cierra igual: mirando.
    from .graph import DEFAULT_SKIP, _iter_py_files

    conocidos = {r.replace(os.sep, "/") for r in guardadas}
    for path in _iter_py_files(root, DEFAULT_SKIP):
        if os.path.relpath(path, root).replace(os.sep, "/") not in conocidos:
            return False
    return True


def delta(viejo, informe):
    """Lo que cambio entre el snapshot y esta mirada. Hechos, no juicio.

    Devuelve None si no hay con que comparar (primera mirada).
    """
    if not viejo:
        return None
    ahora_quals = {n["qual"] for n in informe.get("nodes") or []}
    antes_quals = set(viejo.get("quals") or [])
    ahora_edges = {tuple(e) for e in informe.get("edges") or []}
    antes_edges = {tuple(e) for e in viejo.get("edges") or []}
    return {
        "ts": viejo.get("ts"),
        "nuevos": sorted(ahora_quals - antes_quals),
        "idos": sorted(antes_quals - ahora_quals),
        "aristas_nuevas": sorted(ahora_edges - antes_edges),
        "aristas_idas": sorted(antes_edges - ahora_edges),
    }


def vacio(cambios):
    """¿El delta no tiene nada que decir?"""
    return not any((cambios.get("nuevos"), cambios.get("idos"),
                    cambios.get("aristas_nuevas"), cambios.get("aristas_idas")))
