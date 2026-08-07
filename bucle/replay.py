"""El banco de replay: el verificador de adopcion, contra las tiradas reales ya vividas.

NO es aprendizaje. Es su precondicion y vale por si solo: cada cambio futuro al
verificador se valida contra las tiradas GRABADAS en vez de contra un test
sintetico. Un banco es lo unico que convierte "creo que sigue cazandolo" en
"lo caza, medido sobre los N casos que ocurrieron de verdad".

Como reconstruye sin gastar cuota: el acta guarda el diff final de cada
worktree y la cabecera `index <pre>..<post>` trae el SHA de la PRE-imagen, que
viene de un commit y por tanto siempre esta en el object store; `git cat-file`
la saca y `git apply` la lleva al estado exacto que se verifico — cero agentes,
cero red, milisegundos. Las lineas añadidas salen del mismo parser que usa la
tirada viva (`bucle.lineas_de_diff`) y la logica AST es literalmente la misma
funcion: un banco que reimplementa lo que valida no valida nada.

La verdad de campo NO es "las infracciones que registro el acta": el acta anota
las del PRIMER intento y el diff guardado es el estado FINAL (tras el rechazo).
Se deriva del acta cual de los dos corresponde — y por eso el banco tiene las
dos clases de caso: tiradas donde el rechazo corrigio (final limpio: cazar algo
ahi seria un falso positivo) y tiradas donde no corrigio (final sucio: no
cazarlo seria un falso negativo).

    python bucle/replay.py            # tabla + exit != 0 si alguna diverge
    python bucle/replay.py --json
"""

import argparse
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile


def _carga_orquestador():
    """El bucle, cargado por RUTA y no por `import bucle`.

    `bucle/` no tiene `__init__.py`, asi que bajo pytest el nombre `bucle` se
    resuelve como namespace package (PEP 420) y el modulo real nunca llega —
    fallo mudo que costo esta primera pasada del banco. Por ruta es
    deterministico y funciona igual como CLI suelta."""
    import importlib.util

    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bucle.py")
    spec = importlib.util.spec_from_file_location("bucle_del_banco", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


#: El verificador que este banco valida. Se referencia por el modulo (no por
#: `from ... import`) para que un test pueda sustituirlo por SU instancia y la
#: prueba de mutacion llegue de verdad al codigo que se ejecuta.
bucle = _carga_orquestador()

RAIZ = bucle.RAIZ
MARCA_REINTENTO = "-- tras el reintento --"


def blobs_del_diff(texto):
    """fichero -> (SHA pre-imagen, SHA post-imagen) de las cabeceras `index`."""
    blobs, actual = {}, None
    for linea in texto.splitlines():
        if linea.startswith("diff --git "):
            m = re.search(r" b/(.+)$", linea)
            actual = m.group(1).strip() if m else None
        elif linea.startswith("index ") and actual:
            m = re.match(r"index ([0-9a-f]+)\.\.([0-9a-f]+)", linea)
            if m:
                blobs[actual] = (m.group(1), m.group(2))
    return blobs


def _vacio(sha):
    """El SHA todo-ceros de git: el lado que no existe (alta o baja)."""
    return set(sha) == {"0"}


def materializa(diff, destino, root=None):
    """Rehace bajo `destino` el arbol que vio el verificador.

    PRE-imagen + `git apply`, no post-imagen directa: el post-blob solo esta en
    el object store por suerte — `git add -N` registra la intencion pero NO
    escribe el objeto, asi que reconstruir desde el post falla en cuanto la
    tirada no llego a stagear (lo delato este mismo banco en su primera
    pasada). El pre-blob, en cambio, viene de un commit y siempre esta; el
    parche lo lleva de ahi al estado exacto que se verifico.

    Devuelve (escritos, irrecuperables). Lo que no se puede rehacer se DICE: un
    banco que se salta en silencio lo que no sabe reconstruir se lee como verde
    completo, que es justo la mentira que este proyecto persigue."""
    escritos, perdidos = [], []
    for fichero, (pre, _post) in sorted(blobs_del_diff(diff).items()):
        ruta = os.path.join(destino, *fichero.split("/"))
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        if _vacio(pre):
            continue  # fichero nuevo: lo crea el parche
        proc = subprocess.run(
            ["git", "cat-file", "blob", pre],
            cwd=root or RAIZ, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        if proc.returncode != 0:
            perdidos.append("%s (pre %s)" % (fichero, pre))
            continue
        with open(ruta, "wb") as fh:
            fh.write(proc.stdout)
        escritos.append(fichero)

    if perdidos:
        return escritos, perdidos
    parche = os.path.join(destino, "_replay.patch")
    with open(parche, "wb") as fh:
        fh.write(diff.encode("utf-8", "replace"))
    aplicado = subprocess.run(
        ["git", "apply", "--unsafe-paths", "--directory", ".", "_replay.patch"],
        cwd=destino, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    os.remove(parche)
    if aplicado.returncode != 0:
        perdidos.append("git apply: %s" % aplicado.stderr.decode("utf-8", "replace").strip()[:120])
    return escritos, perdidos


def hechos_de(acta, tarea):
    """Los hechos derivados que el bucle tenia en la mano para esa tarea —
    viajen en el despacho (`entregas`) o retenidos para el rechazo
    (`senal_retenida`, brazos 4ª/5ª rebanada). Los marcadores entre parentesis
    ('(rechazo por adopcion)') son eventos, no hechos."""
    crudos = list((acta.get("entregas") or {}).get(tarea, []))
    crudos += list((acta.get("senal_retenida") or {}).get(tarea, []))
    return [h for h in crudos if not h.startswith("(")]


def esperado_del_final(acta, tarea):
    """La verdad de campo para el diff FINAL, derivada de los pasos del acta."""
    pasos = acta.get("pasos") or []
    registradas = list((acta.get("adopcion") or {}).get(tarea, []))
    hubo_rechazo = any(p.startswith("adopcion de %s:" % tarea) for p in pasos)
    reintento = next(
        (p for p in pasos if p.startswith("reintento de %s por adopcion:" % tarea)), None
    )
    if not hubo_rechazo:
        return []                       # nunca infringio: el final tiene que salir limpio
    if reintento is None:
        return registradas              # se rechazo pero no se reintento: el final es el sucio
    if "limpio" in reintento:
        return []                       # el rechazo corrigio: el final es limpio
    if MARCA_REINTENTO in registradas:  # quedaron infracciones: son las de despues de la marca
        return registradas[registradas.index(MARCA_REINTENTO) + 1:]
    return registradas


def replay_acta(acta, root=None):
    """Replaya cada tarea con hechos de un acta. Devuelve filas comparables."""
    filas = []
    for tarea in acta.get("tareas") or []:
        hechos = hechos_de(acta, tarea)
        diff = (acta.get("diffs") or {}).get(tarea) or (acta.get("diffs") or {}).get(
            "bucle-" + tarea, ""
        )
        if not hechos or not diff.strip():
            continue                    # sin hechos no hay adopcion que verificar
        temporal = tempfile.mkdtemp(prefix="gb-replay-")
        try:
            _escritos, perdidos = materializa(diff, temporal, root)
            obtenido = bucle.llamadas_contra_firma_vieja(
                temporal, hechos, lineas=bucle.lineas_de_diff(diff)
            )
        finally:
            shutil.rmtree(temporal, ignore_errors=True)
        # Las actas v0 (anteriores a la verificacion de adopcion) NO tienen
        # verdad de campo: el bucle de entonces no rechazaba nada, asi que su
        # diff final conserva las infracciones. Contarlas como fallo seria
        # acusar al verificador de hoy por lo que no existia ayer; contarlas
        # como acierto seria inventarse un veredicto. Se dicen aparte — y lo
        # que el verificador encuentre ahi es RETROACTIVO: que habria pasado.
        retroactivo = acta.get("adopcion") is None
        esperado = [] if retroactivo else esperado_del_final(acta, tarea)
        filas.append(
            {
                "acta": acta.get("inicio", "?"),
                "tarea": tarea,
                "esperado": esperado,
                "obtenido": obtenido,
                "irrecuperables": perdidos,
                "retroactivo": retroactivo,
                "ok": None if retroactivo else (
                    sorted(obtenido) == sorted(esperado) and not perdidos),
            }
        )
    return filas


def corre(dir_actas=None, root=None):
    dir_actas = dir_actas or os.path.join(RAIZ, ".claude", "actas")
    filas = []
    for nombre in sorted(os.listdir(dir_actas)) if os.path.isdir(dir_actas) else []:
        if not nombre.endswith(".json"):
            continue
        try:
            with io.open(os.path.join(dir_actas, nombre), encoding="utf-8") as fh:
                acta = json.load(fh)
        except (OSError, ValueError):
            filas.append({"acta": nombre, "tarea": "-", "esperado": [], "obtenido": [],
                          "irrecuperables": ["acta ilegible"], "ok": False})
            continue
        filas.extend(replay_acta(acta, root))
    return filas


def render(filas):
    if not filas:
        return "sin casos que replayar (¿actas sin diffs?)"
    lineas = []
    for f in filas:
        if f.get("retroactivo"):
            marca, detalle = "v0  ", "sin verdad de campo · %d retroactiva(s)" % len(f["obtenido"])
        else:
            marca = "ok  " if f["ok"] else "DIFIERE"
            detalle = "%d esperada(s) / %d obtenida(s)" % (len(f["esperado"]), len(f["obtenido"]))
        if f["irrecuperables"]:
            detalle += " · %d fichero(s) irrecuperable(s)" % len(f["irrecuperables"])
        lineas.append("  %s %s · %s · %s" % (marca, f["acta"], f["tarea"], detalle))
        if f["ok"] is False:
            for falta in sorted(set(map(str, f["esperado"])) - set(map(str, f["obtenido"]))):
                lineas.append("        NO cazada (falso negativo): %s" % falta)
            for sobra in sorted(set(map(str, f["obtenido"])) - set(map(str, f["esperado"]))):
                lineas.append("        cazada de mas (falso positivo): %s" % sobra)
    juzgables = [f for f in filas if f["ok"] is not None]
    retro = [f for f in filas if f.get("retroactivo")]
    cabecera = "%d caso(s) con verdad de campo · %d reproducen el veredicto · %d controles " \
               "positivos (final sucio)" % (
                   len(juzgables), sum(1 for f in juzgables if f["ok"]),
                   sum(1 for f in juzgables if f["esperado"]))
    if retro:
        cabecera += "\n%d acta(s) v0 sin verdad de campo: el verificador de HOY habria cazado " \
                    "%d infraccion(es) que aquella tirada dejo pasar" % (
                        len(retro), sum(len(f["obtenido"]) for f in retro))
    return "\n".join([cabecera] + lineas)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="banco de replay: el verificador de adopcion contra las tiradas grabadas")
    parser.add_argument("--json", action="store_true", help="salida cruda")
    parser.add_argument("--actas", metavar="DIR", help="directorio de actas")
    args = parser.parse_args(argv)
    filas = corre(args.actas)
    print(json.dumps(filas, ensure_ascii=False, indent=2) if args.json else render(filas))
    return 0 if all(f["ok"] for f in filas if f["ok"] is not None) else 1


if __name__ == "__main__":
    sys.exit(main())
