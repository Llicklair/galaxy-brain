"""Un agente sobre un worktree, con el mapa mirándole. UN comando.

    python bucle/agente.py "arregla X"

Lo que hacía falta teclear antes para llegar aquí: crear el worktree a mano,
escribir un lanzador que teee el stdout a `<worktree>.consola.log`, arrancar el
watch, y buscar la ruta del mapa. Cinco pasos y un script desechable cada vez —
reportado en uso real (8-ago): «hemos gastado demasiados prompts hasta llegar
aquí, esto debería ser más ágil». La norma va en el defecto: lo correcto es lo
que sale sin escribir nada.

Vive en `bucle/` y no en `gb` a propósito: gb PROVEE (el grafo, la actividad
derivada, el mapa), no orquesta (ARCHITECTURE regla 4). Y NO reimplementa el
orquestador: reutiliza sus piezas —el worktree, el teeador de consola, el
formateador de líneas— porque dos copias del mismo lanzador divergen y una de
las dos acaba mintiendo.

NUNCA mergea: al terminar deja el diff y el worktree, y quien decide es el
humano (regla de trabajo: los bucles no mergean).
"""

import argparse
import importlib.util
import json
import os
import re
import sys


def _carga_orquestador():
    """El bucle, cargado por RUTA. `bucle/` no es paquete, asi que `import
    bucle` cae en un namespace package (PEP 420) y el modulo real nunca llega —
    la misma trampa que ya mordio al banco de replay."""
    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bucle.py")
    spec = importlib.util.spec_from_file_location("bucle_del_lanzador", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


bucle = _carga_orquestador()
RAIZ = bucle.RAIZ


def resuelve_nodo(raiz, qual, alcance=None):
    """El símbolo del grafo al que se ancla el agente, o None con su motivo.

    Consume `gb calls` por CLI como el resto del bucle: gb PROVEE el hecho, esto
    lo usa. Si el símbolo no existe —o el lenguaje no tiene motor— se devuelve el
    motivo tal cual lo dice gb, en vez de inventarse un ancla.
    """
    ruta = alcance or raiz
    rc, salida, err = bucle._corre(bucle.GB + ["calls", qual, ruta, "--json"], cwd=raiz)
    texto = bucle._texto(salida).strip()
    if rc != 0 or not texto.startswith("{"):
        return None, (bucle._texto(err).strip() or texto or "gb calls no respondio")[:200]
    datos = json.loads(texto)
    matches = datos.get("matches") or []
    if not matches:
        return None, "no hay ningun simbolo '%s' en %s" % (qual, ruta)
    if len(matches) > 1:
        nombres = ", ".join(m["symbol"]["qual"] for m in matches[:5])
        return None, "'%s' es ambiguo: %s — usa el nombre cualificado" % (qual, nombres)
    m = matches[0]
    # El PREFIJO del analisis respecto al repo. Sin el, las rutas no casan: el
    # grafo las da desde la raiz analizada (`galaxybrain/graph.py` cuando se
    # analiza `src/`) y el diff desde la raiz del repo (`src/galaxybrain/...`).
    # Sin esto, `llamantes_sin_tocar` no casaba NUNCA y acusaba a todos los
    # llamantes siempre — un acusador que acusa siempre es peor que ninguno, y
    # lo caza el control positivo de su test.
    prefijo = os.path.relpath(os.path.abspath(ruta), raiz).replace("\\", "/")
    return {"symbol": m["symbol"], "callers": m.get("callers") or [],
            "callees": m.get("callees") or [],
            "prefijo": "" if prefijo == "." else prefijo}, ""


def brief_del_nodo(nodo):
    """El encuadre que recibe el agente: DÓNDE trabajar y qué no puede romper.

    Ojo con lo que esto es y lo que no. La medición del proyecto dice que la
    información en contexto es una palanca DÉBIL (señal preventiva ignorada
    12/12); lo que corrige es la arista determinista que obliga (rechazo 4/4).
    Así que esto no está aquí para hacer al modelo más listo: está para ACOTAR
    —un fichero y un símbolo en vez del repo— y para dejar por escrito contra qué
    se le va a verificar después, que es lo que sí pesa.
    """
    s = nodo["symbol"]
    lineas = [
        "ANCLA: %s  (%s:%s)" % (s["qual"], s["file"], s["line"]),
        "firma actual: %s%s" % (s["qual"].rsplit(".", 1)[-1], s.get("sig") or "()"),
        "",
        "Trabaja sobre ESE simbolo. Si cambias su firma, actualiza a sus llamantes:",
    ]
    for c in nodo["callers"][:12]:
        lineas.append("  - %s  (%s:%s)" % (c["qual"], c["file"], c["line"]))
    if not nodo["callers"]:
        lineas.append("  (ninguno en el grafo: nadie lo llama todavia)")
    elif len(nodo["callers"]) > 12:
        lineas.append("  ... y %d mas" % (len(nodo["callers"]) - 12))
    return "\n".join(lineas)


def llamantes_sin_tocar(worktree, nodo):
    """De los llamantes del ancla, cuáles NO tocó el agente.

    Es un HECHO derivado del diff, no un veredicto (regla 9): "cambiaste la firma
    y no miraste 4 de sus 7 llamantes" es justo lo que hay que leer antes de
    mergear. Quien decide sigue siendo el humano.
    """
    tocados = {f.replace("\\", "/") for f in bucle.lineas_anadidas(worktree)}
    prefijo = nodo.get("prefijo") or ""
    fuera = []
    for c in nodo["callers"]:
        rel = c["file"].replace("\\", "/")
        completa = "%s/%s" % (prefijo, rel) if prefijo else rel
        if completa not in tocados:
            fuera.append("%s  (%s:%s)" % (c["qual"], c["file"], c["line"]))
    return fuera


def _carga_escalera():
    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "escalera.py")
    spec = importlib.util.spec_from_file_location("escalera_del_lanzador", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


escalera = _carga_escalera()


def _guarda_estado(worktree, estado):
    """El estado de la escalera, junto al worktree y en JSON.

    Vive fuera del worktree a proposito —igual que el log de consola— para no
    ensuciar el arbol que el agente esta editando ni aparecer en su propio diff.
    Lo lee el mapa: si el frontend no puede contarlo, la escalera es una caja
    negra, y una caja negra que acepta codigo sola es justo lo que no queremos.
    """
    ruta = os.path.normpath(worktree.rstrip("\\/")) + ".escalera.json"
    try:
        with open(ruta, "w", encoding="utf-8") as fh:
            json.dump(estado, fh, ensure_ascii=False, indent=2)
    except OSError:
        pass
    return ruta


def correr_escalera(worktree, nombre, tarea, nodo, topes, timeout, alcance=None):
    """Sube peldaños mientras el rechazo CAMBIE. Devuelve el estado final.

    La regla que gobierna el bucle no es un contador: si dos peldaños seguidos
    producen el MISMO rechazo, el modelo no esta convergiendo y seguir solo gasta
    cuota. Se para y se dice.

    NUNCA mergea ni commitea: al final el diff sigue en el worktree y quien
    decide es el humano — incluso cuando el veredicto es ACEPTAR, que significa
    "el grafo no encontro nada que objetar", no "esta en main".
    """
    estado = {"tarea": tarea, "worktree": worktree, "peldanos": [],
              "veredicto": None, "motivo": "", "ancla": (nodo or {}).get("symbol", {}).get("qual")}
    rechazo_previo = None
    for n in range(topes + 1):
        prompt = escalera.escalon(n, tarea, rechazo=rechazo_previo, ancla=nodo)
        print("\n== peldano %d ==%s" % (n, (" (con el rechazo anterior)" if rechazo_previo else "")),
              flush=True)
        try:
            bucle.ejecutar_real({"id": "%s-p%d" % (nombre, n)}, worktree, prompt, timeout, eco=True)
        except RuntimeError as error:
            print("[el agente termino mal] %s" % error)

        hechos = escalera.hechos_del_arbol(worktree, alcance=alcance)
        veredicto, motivo = escalera.decidir(hechos)
        estado["peldanos"].append({"n": n, "veredicto": veredicto, "motivo": motivo,
                                   "tocados": hechos.get("modulos_tocados", [])})
        estado["veredicto"], estado["motivo"] = veredicto, motivo
        _guarda_estado(worktree, estado)
        print("   -> %s: %s" % (veredicto.upper(), motivo))

        if veredicto != escalera.RECHAZAR:
            break                      # ACEPTAR o ESCALAR: la escalera termina
        if escalera.mismo_rechazo(rechazo_previo, motivo):
            estado["veredicto"] = escalera.ESCALAR
            estado["motivo"] = "dos peldanos con el mismo rechazo: no converge — %s" % motivo
            _guarda_estado(worktree, estado)
            print("   -> ESCALAR: el mismo rechazo dos veces, no converge")
            break
        rechazo_previo = motivo
    else:
        estado["veredicto"] = escalera.ESCALAR
        estado["motivo"] = "agotados los %d peldanos sin veredicto limpio" % topes
        _guarda_estado(worktree, estado)
    return estado


def nombre_por_defecto(tarea):
    """Un nombre legible derivado de la tarea: el worktree se llama como lo que
    hace, que es lo que se va a leer en la tarjeta del mapa."""
    palabras = re.findall(r"[a-zA-Z0-9_]+", tarea.lower())[:3]
    return "-".join(palabras) or "agente"


def asegura_mapa(raiz):
    """Un watch vivo sobre el repo, si no lo hay. Sin esto la actividad existe
    en disco pero nadie la pinta — el fallo que costo tres tandas invisibles.
    El candado de gb evita duplicados, asi que llamarlo de mas es inofensivo."""
    destino = os.path.join(raiz, "mapa.html")
    bucle._corre(bucle.GB + ["symbols", raiz, "--html", destino, "--watch", "--fondo",
                             "--refresco", "3"], cwd=raiz, timeout=60)
    return destino


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="un agente en un worktree, con el mapa mirandole")
    parser.add_argument("tarea", help="que tiene que hacer")
    parser.add_argument("--nombre", help="nombre del worktree (por defecto, de la tarea)")
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--sin-mapa", action="store_true",
                        help="no asegurar el watch (por defecto se arranca si falta)")
    parser.add_argument("--repo", default=RAIZ,
                        help="repo sobre el que trabajar (por defecto, este)")
    parser.add_argument("--nodo", metavar="QUAL",
                        help="anclar el agente a un simbolo del grafo (p.ej. carrito.total): "
                             "acota el trabajo a su fichero y verifica contra sus llamantes")
    parser.add_argument("--alcance", metavar="RUTA",
                        help="raiz que analiza el grafo para resolver --nodo (por defecto, el repo)")
    parser.add_argument("--escalera", type=int, default=0, metavar="N",
                        help="reintentar hasta N veces con el RECHAZO del grafo como hecho; "
                             "el veredicto (aceptar/rechazar/escalar) sale de hechos, sin modelo. "
                             "Por defecto 0: una tirada y el diff es tuyo")
    args = parser.parse_args(argv)

    raiz = os.path.abspath(args.repo)

    nodo = None
    if args.nodo:
        nodo, motivo = resuelve_nodo(raiz, args.nodo, args.alcance)
        if nodo is None:
            # Un ancla que no existe no se sustituye por "trabaja donde puedas":
            # el usuario pidio un sitio concreto y no esta.
            sys.stderr.write("[agente] no puedo anclar a '%s': %s\n" % (args.nodo, motivo))
            return 1

    nombre = args.nombre or nombre_por_defecto(args.tarea)
    worktree = bucle.preparar_worktree(nombre, raiz=raiz)
    print("repo     : %s" % raiz)
    if nodo:
        s = nodo["symbol"]
        print("ancla    : %s  (%s:%s) · %d llamante(s)"
              % (s["qual"], s["file"], s["line"], len(nodo["callers"])))
    print("worktree : %s" % worktree)
    if not args.sin_mapa:
        print("mapa     : file:///%s" % asegura_mapa(raiz).replace("\\", "/"))
    print("consola  : %s" % bucle._log_consola(worktree))
    print("-- el agente empieza; su tarjeta aparece en el mapa al primer cambio --\n",
          flush=True)

    if args.escalera:
        tarea = args.tarea if nodo is None else "%s\n\n%s" % (args.tarea, brief_del_nodo(nodo))
        estado = correr_escalera(worktree, nombre, tarea, nodo, args.escalera,
                                 args.timeout, alcance=args.alcance)
        print("\n== veredicto de la escalera: %s ==" % estado["veredicto"].upper())
        print("   %s" % estado["motivo"])
        print("   peldanos: %s" % " -> ".join(
            "%d:%s" % (p["n"], p["veredicto"]) for p in estado["peldanos"]))
        print("\nEl diff sigue en el worktree y SIN commitear: aceptar no es mergear.")
        print("revisalo con:  git -C %s diff" % worktree)
        return 0

    prompt = args.tarea if nodo is None else "%s\n\n%s" % (args.tarea, brief_del_nodo(nodo))
    try:
        bucle.ejecutar_real({"id": nombre}, worktree, prompt, args.timeout, eco=True)
    except RuntimeError as error:
        # Un agente que sale mal no es una excepcion del lanzador: es un hecho
        # de la tirada. Se dice y se sigue al diff, que puede tener trabajo util.
        print("\n[el agente termino mal] %s" % error)

    _rc, diff, _err = bucle._corre(["git", "diff", "--stat", "HEAD"], cwd=worktree)
    print("\n== lo que dejo (SIN commitear, SIN mergear) ==")
    print(bucle._texto(diff).strip() or "(nada)")

    if nodo:
        # La verificacion anclada, que es lo que de verdad aporta el --nodo: la
        # informacion en contexto es palanca debil (12/12 ignorada), la arista
        # que obliga es la fuerte (rechazo 4/4). Esto NO bloquea ni mergea: son
        # hechos derivados del diff para leer antes de decidir (regla 9).
        print("\n== contra el ancla ==")
        firmas = bucle.firmas_de(worktree)
        s = nodo["symbol"]
        antes = "%s%s" % (s["qual"].rsplit(".", 1)[-1], s.get("sig") or "()")
        ahora = firmas.get(s["qual"])
        if ahora is None:
            print("  la firma de %s ya no existe con ese nombre (movida o borrada)" % s["qual"])
        elif ahora != (s.get("sig") or ""):
            print("  FIRMA CAMBIADA: %s -> %s%s" % (antes, s["qual"].rsplit(".", 1)[-1], ahora))
            sin_tocar = llamantes_sin_tocar(worktree, nodo)
            if sin_tocar:
                print("  %d de %d llamante(s) SIN tocar:"
                      % (len(sin_tocar), len(nodo["callers"])))
                for linea in sin_tocar[:10]:
                    print("    - %s" % linea)
            else:
                print("  todos sus llamantes fueron tocados")
        else:
            print("  la firma de %s no cambio: sus %d llamante(s) siguen valiendo"
                  % (s["qual"], len(nodo["callers"])))
    print("\nrevisalo con:  git -C %s diff" % worktree)
    print("y cuando decidas TU:  git -C %s diff | git apply -" % worktree)
    return 0


if __name__ == "__main__":
    sys.exit(main())
