"""El bucle: la arista determinista entre agentes estocasticos.

NO es parte de gb y no debe serlo nunca (ARCHITECTURE: gb provee, no orquesta;
docs/grafo-neuronal-orquestacion.md: "si algun dia gb orquesta, este documento
es el bug"). Es el ORQUESTADOR: consume gb por CLI/JSON exactamente como lo
haria cualquier motor externo — esa es la superficie de integracion que el
proyecto promete, asi que este fichero tambien la prueba.

La tesis que implementa (§4, medida el 5-ago-2026): la señal no puede obligar a
un LLM, pero si obliga a un bucle. Los nodos (agentes) son estocasticos; el
determinismo va en las aristas:

    preparar -> lanzar A -> DERIVAR hechos de su diff -> ENRUTAR en el despacho
    de B -> aterrizar con `gb tests --run --union` -> decidir (verde: acta y
    parar; roja: UN reintento con el fallo como hecho) -> acta SIEMPRE.

Nunca mergea (regla de trabajo: los bucles no mergean; el merge lo dirige un
humano). El acta registra que hecho se entrego a quien: con ese registro, una
rama roja-sola con union verde se lee como COORDINADA (escribio para el arbol
futuro por señal) y no como rescatada — la ambiguedad que el checkpoint no
puede resolver solo, resuelta donde toca: en la historia de la tirada, que es
del orquestador.

Ejecutores de agente:
  real     -> `claude -p` (Opus, headless) en el worktree de la tarea.
  simulado -> aplica un parche preparado (--simula DIR con <id>.diff). Sin
              cuota, determinista: es lo que testea la maquinaria del bucle.
"""

import argparse
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GB = [sys.executable, "-m", "galaxybrain.cli"]


def _corre(cmd, cwd=None, entrada=None, timeout=None):
    """Subproceso con el entorno limpio de GIT_* (aviso 4 del protocolo)."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    try:
        r = subprocess.run(cmd, cwd=cwd or RAIZ, capture_output=True,
                           input=entrada, timeout=timeout, env=env)
    except (OSError, subprocess.TimeoutExpired) as error:
        return 1, b"", str(error).encode("utf-8", "replace")
    return r.returncode, r.stdout, r.stderr


def _texto(b):
    return b.decode("utf-8", errors="replace")


def preparar_worktree(id_tarea):
    """Worktree PROPIO en main (aviso 2 del protocolo: el ancla del harness)."""
    ruta = os.path.join(RAIZ, ".claude", "worktrees", "bucle-%s" % id_tarea)
    _corre(["git", "worktree", "remove", "--force", ruta])
    rc, _, err = _corre(["git", "worktree", "add", "--detach", ruta, "main"])
    if rc != 0:
        raise RuntimeError("no se pudo preparar %s: %s" % (ruta, _texto(err)))
    return ruta


def quitar_worktree(ruta):
    _corre(["git", "worktree", "remove", "--force", ruta])
    _corre(["git", "worktree", "prune"])


def firmas_de(ruta):
    """qual -> firma, via `gb symbols --json`: el bucle consume gb por CLI."""
    rc, salida, err = _corre(GB + ["symbols", ruta, "--json"])
    if rc != 0:
        raise RuntimeError("gb symbols fallo en %s: %s" % (ruta, _texto(err)[:200]))
    informe = json.loads(_texto(salida))
    return {n["qual"]: n.get("sig", "") for n in informe.get("nodes", []) if n.get("sig")}


def hechos_entre(antes, despues):
    """Los hechos entre dos mapas de firmas. Pura: sin disco, sin subprocesos."""
    hechos = []
    for qual in sorted(set(antes) | set(despues)):
        if antes.get(qual) != despues.get(qual):
            hechos.append("%s: %s -> %s" % (
                qual, antes.get(qual, "(no existia)"), despues.get(qual, "(borrada)")))
    return hechos


def derivar_hechos(worktree, firmas_base):
    """Los hechos del diff de un agente: firmas que cambiaron respecto a la BASE.

    Derivado, no declarado: sale de comparar los dos arboles, no de lo que el
    agente diga que hizo. La base es un worktree LIMPIO de main, nunca el arbol
    del orquestador: su working tree puede llevar cosas sin commitear (este
    propio fichero lo estuvo) y comparar contra el atribuye al agente hechos
    que son del orquestador. Lo cazo el primer test del bucle.
    """
    return hechos_entre(firmas_base, firmas_de(worktree))


def ejecutar_simulado(tarea, worktree, dir_parches):
    parche = os.path.join(dir_parches, "%s.diff" % tarea["id"])
    if not os.path.isfile(parche):
        raise RuntimeError("falta el parche simulado %s" % parche)
    with open(parche, "rb") as fh:
        rc, _, err = _corre(["git", "apply", "--3way", "-"], cwd=worktree,
                            entrada=fh.read())
    if rc != 0:
        raise RuntimeError("el parche %s no aplica: %s" % (parche, _texto(err)[:200]))


def ejecutar_real(tarea, worktree, prompt, timeout_seg):
    exe = shutil.which("claude")
    if not exe:
        raise RuntimeError("claude CLI no esta en PATH: el ejecutor real no puede correr")
    rc, salida, err = _corre(
        [exe, "-p", prompt, "--model", "opus", "--permission-mode", "acceptEdits"],
        cwd=worktree, timeout=timeout_seg)
    if rc != 0:
        raise RuntimeError("claude -p salio %d: %s" % (rc, (_texto(err) or _texto(salida))[:300]))


def componer_prompt(tarea, hechos_enrutados, extra=""):
    """El despacho: tarea + señal. La señal son HECHOS, no ordenes — lo que el
    agente haga con ellos es suyo; lo que el bucle haga con el veredicto, no."""
    bloques = [
        "Tu directorio de trabajo es el actual (un worktree preparado). Trabaja SOLO aqui.",
        tarea["prompt"],
        "TRAMPA DE ENTORNO: un .pth pre-importa galaxybrain desde el checkout principal. "
        "Corre pytest con PYTHONPATH=<este-dir>;<este-dir>/src desde este directorio. "
        "NO commitees, NO push.",
    ]
    if hechos_enrutados:
        bloques.insert(1, "SEÑAL DEL ENRUTADOR (hechos derivados del grafo de otro worktree "
                          "en vuelo; tu arbol puede estar desfasado respecto a donde aterriza "
                          "tu trabajo):\n" + "\n".join("- " + h for h in hechos_enrutados))
    if extra:
        bloques.append(extra)
    return "\n\n".join(bloques)


def veredicto_union():
    """`gb tests --run --union` y su lectura: (exit, union_verde, ramas_rojas)."""
    rc, salida, err = _corre(GB + ["tests", "--run", "--union"], timeout=1800)
    texto = _texto(salida) + _texto(err)
    union_verde = bool(re.search(r"^  ok\s+union", texto, re.M))
    ramas_rojas = re.findall(r"^  ROJA\s+(\S+)", texto, re.M)
    ramas_rojas = [r for r in ramas_rojas if r != "union"]
    return rc, union_verde, ramas_rojas, texto[-2000:]


def interpretar(ramas_rojas, union_verde, entregas):
    """Coordinada o rescatada: la desambiguacion que el checkpoint no puede
    hacer solo (§4A, hallazgo colateral). Una rama roja-sola con union verde
    que RECIBIO señal se lee coordinada: escribio para el arbol futuro. Sin
    señal recibida, es el rescate accidental de siempre y se dice."""
    lectura = {}
    if not union_verde:
        return lectura
    for rama in ramas_rojas:
        id_tarea = rama.replace("bucle-", "")
        lectura[rama] = "coordinada" if entregas.get(id_tarea) else "RESCATADA (revisar)"
    return lectura


def correr(tirada, dir_parches=None, max_reintentos=1, timeout_agente=900):
    acta = {
        "inicio": time.strftime("%Y-%m-%d %H:%M:%S"),
        "modo": "simulado" if dir_parches else "real",
        "tareas": [t["id"] for t in tirada["tareas"]],
        "entregas": {},          # id_tarea -> [hechos que recibio en el despacho]
        "reintentos": 0,
        "veredicto": None,
        "lectura_ramas": {},
        "pasos": [],
    }
    worktrees = {}
    try:
        base = preparar_worktree("base")
        worktrees["base"] = base
        firmas_base = firmas_de(base)
        hechos_acumulados = []
        for tarea in tirada["tareas"]:
            wt = preparar_worktree(tarea["id"])
            worktrees[tarea["id"]] = wt
            enrutados = hechos_acumulados if tarea.get("depende_de") else []
            if enrutados:
                acta["entregas"][tarea["id"]] = list(enrutados)
            prompt = componer_prompt(tarea, enrutados)
            acta["pasos"].append("lanzada %s (%d hecho(s) enrutado(s))"
                                 % (tarea["id"], len(enrutados)))
            if dir_parches:
                ejecutar_simulado(tarea, wt, dir_parches)
            else:
                ejecutar_real(tarea, wt, prompt, timeout_agente)
            nuevos = derivar_hechos(wt, firmas_base)
            acta["pasos"].append("derivados de %s: %s" % (tarea["id"], nuevos or "nada"))
            hechos_acumulados.extend(h for h in nuevos if h not in hechos_acumulados)

        intento = 0
        while True:
            rc, union_verde, ramas_rojas, cola = veredicto_union()
            acta["pasos"].append("union: %s (exit %d; ramas rojas: %s)"
                                 % ("VERDE" if union_verde else "ROJA", rc, ramas_rojas))
            if union_verde or intento >= max_reintentos:
                acta["veredicto"] = "verde" if union_verde else "roja"
                acta["lectura_ramas"] = interpretar(ramas_rojas, union_verde, acta["entregas"])
                acta["cola_union"] = cola
                break
            # UN reintento: la ultima tarea dependiente, con el fallo como hecho.
            intento += 1
            acta["reintentos"] = intento
            ultima = tirada["tareas"][-1]
            wt = worktrees[ultima["id"]]
            _corre(["git", "checkout", "--", "."], cwd=wt)
            extra = ("REINTENTO: la union de todos los diffs fallo. Cola del fallo:\n"
                     + cola[-1200:])
            acta["entregas"].setdefault(ultima["id"], []).append("(cola del fallo de union)")
            if dir_parches:
                break  # en simulado no hay reintento distinto que aplicar
            ejecutar_real(ultima, wt, componer_prompt(ultima, hechos_acumulados, extra),
                          timeout_agente)
            acta["pasos"].append("reintento de %s" % ultima["id"])
        # Los diffs se conservan como evidencia; el merge NUNCA es del bucle.
        acta["diffs"] = {}
        for id_tarea, wt in worktrees.items():
            if id_tarea == "base":
                continue
            rc, diff, _ = _corre(["git", "diff", "HEAD"], cwd=wt)
            acta["diffs"][id_tarea] = _texto(diff)
    finally:
        for wt in worktrees.values():
            quitar_worktree(wt)
        acta["fin"] = time.strftime("%Y-%m-%d %H:%M:%S")
        destino = os.path.join(RAIZ, ".claude", "bucle-acta.json")
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        with io.open(destino, "w", encoding="utf-8") as fh:
            json.dump(acta, fh, ensure_ascii=False, indent=2)
    return acta


def main(argv=None):
    parser = argparse.ArgumentParser(description="el bucle: orquestador determinista sobre gb")
    parser.add_argument("tirada", help="JSON con las tareas de la tirada")
    parser.add_argument("--simula", metavar="DIR",
                        help="ejecutor simulado: DIR con <id>.diff por tarea (sin cuota)")
    parser.add_argument("--timeout-agente", type=int, default=900)
    args = parser.parse_args(argv)
    with io.open(args.tirada, encoding="utf-8") as fh:
        tirada = json.load(fh)
    acta = correr(tirada, dir_parches=args.simula, timeout_agente=args.timeout_agente)
    print("veredicto: %s | lectura: %s | acta: .claude/bucle-acta.json"
          % (acta["veredicto"], acta["lectura_ramas"] or "(sin ramas rojas)"))
    return 0 if acta["veredicto"] == "verde" else 1


if __name__ == "__main__":
    sys.exit(main())
