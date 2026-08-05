"""Quién está tocando qué, ahora mismo — derivado, no declarado.

Esto **no** es el `gb activity` que se descartó (docs/grafo-neuronal-orquestacion.md,
apartado 0). Aquel pedía a cada agente que anunciara su presencia con un comando, y
en cuanto uno se olvidaba, todo lo construido encima mentía con cara de hecho.

Aquí nadie declara nada: se lee el disco. **Un agente es un worktree** — esa es toda
la atribución que hace falta, y sale gratis porque la identidad del agente ya está en
la ruta donde trabaja. Si el agente muere a medias, su rastro sigue siendo cierto; si
nunca existió, no aparece.

Lo que se puede derivar y lo que no, dicho de frente:

- **Sí**: qué nodos ha tocado, hace cuánto, y a qué nodos se propaga por el grafo de
  llamadas (con quién «se comunica»).
- **No**: qué cree el agente que está haciendo. Su narrativa solo la tiene él, y
  pedírsela nos devolvería al registro declarado que ya se rechazó.
"""

import os
import time

from . import aislado
from . import graph as graph_mod

# El DEFINES es estructura (un módulo contiene una función), no comunicación. Para
# «con quién habla este nodo» solo cuentan las aristas de llamada.
ESTRUCTURA = ("DEFINES",)


def ficheros_tocados(root):
    """Los .py tocados respecto a HEAD: modificados, añadidos, renombrados o
    sin trackear, estén o no en el índice. Rutas absolutas.

    UNA fuente: `git status --porcelain` trae staged, unstaged y untracked en una
    pasada. Sin repo git devuelve lista vacía y la capa calla (regla 9).
    """
    salida = graph_mod._git(root, "status", "--porcelain")
    if not salida:
        return []
    toplevel = (graph_mod._git(root, "rev-parse", "--show-toplevel") or "").strip()
    base = toplevel or os.path.abspath(root)
    ficheros = []
    for linea in salida.splitlines():
        if len(linea) < 4:
            continue
        estado, ruta = linea[:2], linea[3:]
        if "D" in estado:
            continue  # borrado: ya no hay fichero, luego no hay nodo que marcar
        if " -> " in ruta:
            ruta = ruta.split(" -> ")[-1]
        ruta = ruta.strip().strip('"')
        if not ruta.endswith(".py"):
            continue
        ficheros.append(os.path.join(base, *ruta.split("/")))
    return ficheros


def nodos_tocados(root, informe_simbolos):
    """Los nodos módulo cuyo fichero está tocado sin commitear.

    El join es delicado en Windows ('c:' vs 'C:', separadores mezclados): los dos
    lados se comparan por normcase, nunca por igualdad literal.
    """
    modulos = {
        os.path.normcase(n.get("qual") or ""): n.get("qual")
        for n in informe_simbolos.get("nodes", [])
        if n.get("kind") == "module"
    }
    tocados = set()
    for fichero in ficheros_tocados(root):
        try:
            mod = graph_mod.module_name(fichero, root)
        except ValueError:  # otra unidad de disco en Windows
            continue
        qual = modulos.get(os.path.normcase(mod))
        if qual:
            tocados.add(qual)
    return tocados


def _mapa_de_modulos(informe_simbolos):
    """qual del símbolo -> módulo que lo contiene.

    Las aristas del grafo conectan SÍMBOLOS; la capa de cambio solo sabe de
    FICHEROS. Para cruzar las dos hay que subir cada extremo de la arista a su
    módulo, y el informe ya trae ese campo por nodo — no se deduce del prefijo del
    nombre, que fallaría con cualquier símbolo anidado.
    """
    return {
        n.get("qual"): (n.get("module") or n.get("qual"))
        for n in informe_simbolos.get("nodes", [])
        if n.get("qual")
    }


def _vecinos(informe_simbolos, nodos, de_modulo=None):
    """A qué otros módulos se propaga lo tocado: llamantes y llamados, un salto.

    Un salto y no la clausura entera a propósito: la consola de un agente tiene
    que caber en un vistazo. La onda completa ya la da `gb calls --depth N`.
    """
    if not nodos:
        return []
    de_modulo = _mapa_de_modulos(informe_simbolos) if de_modulo is None else de_modulo
    dentro = set(nodos)
    fuera = set()
    for arista in informe_simbolos.get("edges") or ():
        if len(arista) < 2:
            continue
        clase = arista[2] if len(arista) > 2 else ""
        if clase in ESTRUCTURA:
            continue
        mo = de_modulo.get(arista[0], arista[0])
        md = de_modulo.get(arista[1], arista[1])
        if mo == md:
            continue  # llamada dentro del mismo modulo: no es comunicacion
        if mo in dentro and md not in dentro:
            fuera.add(md)
        elif md in dentro and mo not in dentro:
            fuera.add(mo)
    return sorted(x for x in fuera if x)


def instantanea(raiz, informe_simbolos, ahora=None):
    """La foto de quién toca qué, ahora mismo, en todos los worktrees vivos.

    `raiz` es la ruta que se analizó para `informe_simbolos` (p. ej. `.../src`);
    de cada worktree se mira su ruta equivalente, para que los nodos casen con los
    del mapa canónico.
    """
    ahora = time.time() if ahora is None else ahora
    foto = {"base": "", "agentes": [], "por_nodo": {}, "cruces": [], "motivo": ""}

    raiz = os.path.abspath(raiz)
    toplevel = (graph_mod._git(raiz, "rev-parse", "--show-toplevel") or "").strip()
    if not toplevel:
        foto["motivo"] = "sin repositorio git: no hay agentes que derivar"
        return foto
    rel = os.path.relpath(raiz, os.path.abspath(toplevel))

    arboles = aislado._worktrees(toplevel)
    cabeza = dict(arboles).get(os.path.abspath(toplevel), "")
    foto["base"] = cabeza[:7]
    de_modulo = _mapa_de_modulos(informe_simbolos)

    for ruta, head in arboles:
        if not aislado._tiene_cambios(ruta):
            continue
        analisis = os.path.normpath(os.path.join(ruta, rel)) if rel != "." else ruta
        if not os.path.isdir(analisis):
            continue
        ficheros = ficheros_tocados(analisis)
        if not ficheros:
            continue
        nodos = sorted(nodos_tocados(analisis, informe_simbolos))
        # Un agente que solo esta creando modulos NUEVOS no casa con ningun nodo
        # del mapa canonico — y esconderlo seria esconder justo al que mas esta
        # construyendo. Aparece igual, con la cuenta de lo que aun no tiene sitio
        # en el mapa: es un hecho, y el mapa dira que no lo dibuja todavia.
        reciente = 0.0
        for fichero in ficheros:
            try:
                reciente = max(reciente, os.stat(fichero).st_mtime)
            except OSError:
                pass
        foto["agentes"].append({
            "fuera_del_mapa": max(0, len(ficheros) - len(nodos)),
            "nombre": os.path.basename(os.path.normpath(ruta)),
            "ruta": ruta,
            "base": head[:7],
            "misma_base": bool(cabeza) and head == cabeza,
            "nodos": nodos,
            "vecinos": _vecinos(informe_simbolos, nodos, de_modulo),
            "ficheros": len(ficheros),
            "hace_seg": int(max(0, ahora - reciente)) if reciente else None,
        })

    for agente in foto["agentes"]:
        for qual in agente["nodos"]:
            foto["por_nodo"].setdefault(qual, {"agentes": [], "vecino_de": []})
            foto["por_nodo"][qual]["agentes"].append(agente["nombre"])
        for qual in agente["vecinos"]:
            foto["por_nodo"].setdefault(qual, {"agentes": [], "vecino_de": []})
            foto["por_nodo"][qual]["vecino_de"].append(agente["nombre"])

    foto["cruces"] = sorted(q for q, d in foto["por_nodo"].items() if len(d["agentes"]) > 1)
    return foto
