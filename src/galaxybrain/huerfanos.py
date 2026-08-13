"""Lo que nadie usa — candidatos, no veredictos.

Un simbolo sin un solo llamante RESUELTO y un modulo que nadie importa son
hechos del grafo, y son exactamente lo que se busca antes de una limpieza. Pero
son PROXIES de "muerto", no pruebas: el despacho dinamico, un registro
(`TABLA = {"x": handler}`), un decorador que registra rutas o un `__all__`
usan codigo sin dejar arista. Por eso esto INFORMA y no bloquea (regla 9), y
por eso lo que el grafo no puede ver se dice en `not_covered` en vez de
disimularse.

Filtros deliberados, cada uno con su porque:
- los tests no se listan: un test sin llamantes es lo NORMAL (los invoca el
  runner, no el codigo);
- los metodos no se listan: casi toda llamada a metodo va sobre una variable
  (`obj.metodo()`), que el grafo declara como techo — listarlos seria ruido
  con cara de hallazgo, y el ruido es lo que manda una limpieza a ignorarse;
- lo usado COMO VALOR (pasado sin llamar) se excluye: hay arista de uso aunque
  no haya llamada;
- dunders, `main` y `conftest` se excluyen: los invoca el runtime.

Funciona sobre el informe de CUALQUIER motor (stdlib `ast` o ast-grep): ambos
devuelven la misma forma, que es el punto entero del ADR 0009.
"""

import os
import re

#: Nombres que invoca el runtime o el runner, no el codigo del proyecto.
#: `cli` esta porque es el entry point tipico de un script de pyproject —
#: medido sobre este mismo repo: salia como "huerfano" siendo el ejecutable.
_INVOCADOS_POR_FUERA = frozenset((
    "main", "conftest", "setup", "app", "wsgi", "asgi", "manage", "cli",
))


def _nombre_pelado(qual):
    return qual.rsplit(".", 1)[-1]


def analyze(informe, aristas_imports=None):
    """Candidatos a codigo muerto sobre un grafo ya derivado.

    `aristas_imports` — {modulo: {destinos}} del motor de grafo de modulos —
    añade el "nadie lo importa" al "nadie lo llama". Sin el, la parte de
    modulos se declara no cubierta en vez de adivinarse.
    """
    report = {
        "sin_llamantes": [],
        "solo_tests": [],
        "modulos_huerfanos": [],
        "not_covered": [
            "despacho dinamico, registros y decoradores: usan codigo sin dejar "
            "arista — un candidato de esta lista puede estar vivisimo",
            "metodos: casi toda llamada va sobre una variable (techo declarado "
            "del grafo), asi que no se listan — solo funciones y clases",
            "entry points externos (scripts de pyproject, cron, CI): invisibles "
            "para un grafo estatico",
            "imports perezosos (dentro de una funcion): no dejan arista de "
            "import — un modulo que solo se importa asi sale como huerfano "
            "(medido en este repo: actividad, autoinstall)",
        ],
    }
    if informe.get("root_error"):
        return report

    nodos = informe.get("nodes") or []
    por_qual = {n["qual"]: n for n in nodos}

    # Usos que dejan arista: llamadas y herencia. MEMBER_OF y DEFINES son
    # estructura, no uso. Se guarda QUIEN usa, no solo que se usa: hace falta
    # para distinguir "nadie lo llama" de "solo los tests lo llaman".
    entrantes = {}
    for arista in informe.get("edges") or []:
        origen, destino, tipo = arista[0], arista[1], arista[2]
        if tipo in ("CALLS", "EXTENDS"):
            entrantes.setdefault(destino, set()).add(origen)

    como_valor = set(informe.get("usados_como_valor") or [])

    def _origen_es_test(origen):
        # Por FICHERO, no por nombre: `changes.test_signals` es produccion
        # (detecta senales sobre tests) y por nombre contaba como test — con lo
        # que `_replacement_asserts` salio como "solo tests lo llaman" en la
        # primera tirada sobre este mismo repo. El fichero no engana: un test
        # vive donde el runner colecciona.
        nodo_origen = por_qual.get(origen)
        if nodo_origen is not None and nodo_origen.get("file"):
            rel = nodo_origen["file"].replace("\\", "/")
            base = rel.rsplit("/", 1)[-1]
            partes = rel.split("/")[:-1]
            return (base.startswith("test_") or base.endswith("_test.py")
                    or ".test." in base or ".spec." in base
                    or any(p in ("tests", "test", "spec", "__tests__") for p in partes))
        if nodo_origen is not None and nodo_origen.get("test"):
            return True
        return _es_test(origen, informe)

    for nodo in nodos:
        if nodo.get("kind") not in ("function", "class"):
            continue
        qual = nodo["qual"]
        if qual in como_valor:
            continue
        if nodo.get("test") or _es_test(qual, informe):
            continue
        nombre = _nombre_pelado(qual)
        if nombre.startswith("__") or nombre in _INVOCADOS_POR_FUERA:
            continue
        ficha = {
            "qual": qual, "kind": nodo["kind"],
            "file": nodo.get("file", ""), "line": nodo.get("line"),
        }
        llamantes = entrantes.get(qual)
        if not llamantes:
            report["sin_llamantes"].append(ficha)
        elif all(_origen_es_test(o) for o in llamantes):
            # Produccion que SOLO los tests mantienen vivo: sin uso real, pero
            # sobrevive a cualquier limpieza porque su suite pasa. Encontrado
            # como carencia en el experimento del 14-ago: gb contaba el test
            # como llamante valido y esta clase entera quedaba invisible.
            ficha["tests"] = len(llamantes)
            report["solo_tests"].append(ficha)

    # --- modulos que nadie importa NI llama ---
    if aristas_imports is None:
        report["not_covered"].append(
            "modulos huerfanos: sin el grafo de imports no se afirma nada")
    else:
        importados = set()
        for _origen, destinos in aristas_imports.items():
            importados.update(destinos)
        # Un modulo cuenta como usado si alguien lo importa O si alguno de sus
        # simbolos recibe una llamada desde OTRO modulo.
        usados_desde_fuera = set()
        for arista in informe.get("edges") or []:
            origen, destino, tipo = arista[0], arista[1], arista[2]
            if tipo not in ("CALLS", "EXTENDS"):
                continue
            mod_destino = (por_qual.get(destino) or {}).get("module")
            mod_origen = (por_qual.get(origen) or {}).get("module") or origen
            if mod_destino and mod_destino != mod_origen:
                usados_desde_fuera.add(mod_destino)
        for nodo in nodos:
            if nodo.get("kind") != "module":
                continue
            mod = nodo["qual"]
            if mod in importados or mod in usados_desde_fuera:
                continue
            if nodo.get("test") or _es_test(mod, informe):
                continue
            nombre = _nombre_pelado(mod)
            if nombre.startswith("__") or nombre in _INVOCADOS_POR_FUERA:
                continue
            if _es_entry_point(informe.get("root"), nodo.get("file")):
                continue
            report["modulos_huerfanos"].append({
                "module": mod, "file": nodo.get("file", ""),
            })

    report["sin_llamantes"].sort(key=lambda s: (s["file"], s["line"] or 0))
    report["solo_tests"].sort(key=lambda s: (s["file"], s["line"] or 0))
    report["modulos_huerfanos"].sort(key=lambda m: m["module"])
    return report


_GUARD_MAIN = re.compile(r"""__name__\s*==\s*["']__main__["']""")


def _es_entry_point(root, rel):
    """¿El fichero tiene el guard `if __name__ == "__main__"`?

    Hecho detectable, no heuristica — y cerro un falso positivo real: en el
    experimento del 14-ago `gb dead` listo `principal.py` como huerfano siendo
    el ejecutable del proyecto. La funcion `main` estaba exenta; su modulo no.
    Un fichero ilegible cuenta como no-entry: en la duda, el candidato se
    lista (es un proxy, no un veredicto) antes que esconderse.
    """
    if not root or not rel:
        return False
    try:
        with open(os.path.join(root, rel), "r", encoding="utf-8-sig",
                  errors="replace") as f:
            return bool(_GUARD_MAIN.search(f.read()))
    except OSError:
        return False


def _es_test(qual, informe):
    """El criterio de test del motor Python (`es_de_test`) sin importar symbols
    aqui arriba: por convencion de nombre, igual que alli."""
    partes = qual.split(".")
    return any(p.startswith("test") or p in ("tests", "conftest") for p in partes)


def total(report):
    return (len(report["sin_llamantes"]) + len(report["solo_tests"])
            + len(report["modulos_huerfanos"]))
