"""A/B B: gb le habla al ORQUESTADOR, no al agente. Tres agentes en paralelo.

    python bancos/ab_paralelo/correr.py validar          # sin agentes: referencias, gratis
    python bancos/ab_paralelo/correr.py lanzar [--n 3]   # gasta cuota
    python bancos/ab_paralelo/correr.py medir
    ... --modelo claude-haiku-4-5-20251001   # agentes e integradores; destino ab-gb/p-<modelo>

Una tanda de agentes por repeticion (no ven gb: `gb` falso en el PATH y
GB_DISABLE), y sobre las MISMAS tres ramas, tres orquestadores (README.md):
  ci   cada rama verde sola -> merge. Sin integrador. ¿Llega main roto?
  sin  merge -> suite -> si roja, integrador con la salida de pytest.
  con  `gb tests --run --union` ANTES del merge -> merge -> si rojo, integrador
       con la salida de gb + la de pytest. Lo unico que cambia es ese primer hecho.
"""

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ_GB = os.path.dirname(os.path.dirname(AQUI))
V2_OCULTA = os.path.join(RAIZ_GB, "bancos", "ab_paralelo", "oculta", "aceptacion_v2.py")
P_OCULTA = os.path.join(AQUI, "oculta", "aceptacion_p.py")
DESTINO = os.path.join(os.path.dirname(RAIZ_GB), "ab-gb", "p")
SHIM = os.path.join(DESTINO, "_sin_gb")
MODELO = None                    # None: el de la configuracion de claude
TAREAS = ("a", "b", "c")
RONDAS = 2                       # intentos del integrador
#: El unico test de la v2 que cambia con C (0.005 -> "0.01" era HALF_UP); su
#: version al par vive en aceptacion_p.py.
V2_HALF_UP = "test_valoracion_redondea_solo_al_final"

PROMPT_AGENTE = ("%s\n\nTrabaja solo dentro de este directorio; no escribas ficheros fuera "
                 "de el.\n")
PROMPT_INTEGRADOR = (
    "En este repo se acaban de integrar tres cambios hechos en paralelo por tres personas:\n"
    "%s\nLa verificacion tras integrarlos:\n\n```\n%s\n```\n\n"
    "Deja la suite en verde (`python -m pytest -q`) sin deshacer ninguno de los tres cambios. "
    "Haz commit al terminar. Trabaja solo dentro de este directorio.\n")


def _git(repo, *args, check=True):
    return subprocess.run(["git", "-C", repo] + list(args), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", check=check)


def _borra(ruta):
    """rmtree que puede con los objetos de git, de solo lectura en Windows."""
    def quita_solo_lectura(funcion, camino, _info):
        os.chmod(camino, 0o700)
        funcion(camino)
    if os.path.exists(ruta):
        shutil.rmtree(ruta, onerror=quita_solo_lectura)


def _shim():
    os.makedirs(SHIM, exist_ok=True)
    for nombre, texto in (("gb", "#!/bin/sh\necho \"gb: command not found\" >&2\nexit 127\n"),
                          ("gb.cmd", "@echo gb: command not found 1>&2\r\n@exit /b 127\r\n")):
        with open(os.path.join(SHIM, nombre), "w", encoding="utf-8", newline="") as fh:
            fh.write(texto)


def _entorno_agente():
    e = dict(os.environ, GB_DISABLE="1")
    e["PATH"] = SHIM + os.pathsep + e.get("PATH", "")
    return e


def _suite(repo):
    """(rc, salida) de la suite VISIBLE del repo, como la correria cualquiera."""
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
                       cwd=repo, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=dict(os.environ, GB_DISABLE="1"), timeout=600)
    return r.returncode, (r.stdout + r.stderr)


def _junit(args, repo):
    xml = tempfile.mktemp(suffix=".xml")
    subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                    "-c", os.path.join(AQUI, "oculta", "pytest.ini"), "--junitxml", xml] + args,
                   env=dict(os.environ, ALMACEN_REPO=repo, GB_DISABLE="1"),
                   capture_output=True, text=True, timeout=900)
    casos = {}
    for caso in ET.parse(xml).getroot().iter("testcase"):
        fallo = caso.find("failure") if caso.find("failure") is not None else caso.find("error")
        casos[caso.get("name")] = fallo is None
    return casos


def oculta(repo, que):
    """{test: verde} de la suite oculta que juzga `que` (a, b, c o union)."""
    v2 = [V2_OCULTA]
    if que in ("c", "union"):
        v2 += ["-k", "not " + V2_HALF_UP]
    casos = _junit(v2, repo)
    marcas = {"a": None, "b": "b", "c": "c", "union": "b or c or union"}[que]
    if marcas:
        casos.update(_junit(["-m", marcas, P_OCULTA], repo))
    return casos


def _verdes(casos):
    return "%d/%d" % (sum(casos.values()), len(casos))


# --- montaje --------------------------------------------------------------------


def montar(rep):
    """main (la base) + un worktree por tarea. Devuelve el directorio de la repeticion."""
    raiz = os.path.join(DESTINO, "r%d" % rep)
    main = os.path.join(raiz, "main")
    _borra(raiz)
    shutil.copytree(os.path.join(AQUI, "base"), main)
    _git(main, "init", "-q", "-b", "main")
    _git(main, "config", "user.email", "ab@local")
    _git(main, "config", "user.name", "ab")
    open(os.path.join(main, ".gitignore"), "w").write("__pycache__/\n.pytest_cache/\n")
    _git(main, "add", "-A")
    _git(main, "commit", "-q", "-m", "base")
    for t in TAREAS:
        _git(main, "worktree", "add", "-q", "-b", t, os.path.join(raiz, t))
    return raiz


def _cierra_rama(raiz, t):
    """Lo que dejo el agente, commiteado en su rama. Devuelve el sha."""
    wt = os.path.join(raiz, t)
    _git(wt, "add", "-A")
    _git(wt, "commit", "-q", "--no-verify", "-m", "agente %s (resto)" % t, check=False)
    return _git(wt, "rev-parse", "HEAD").stdout.strip()


def _claude(cwd, prompt, salida):
    inicio = time.time()
    r = subprocess.run(
        [shutil.which("claude") or "claude", "-p", "--output-format", "json",
         "--permission-mode", "bypassPermissions", "--max-turns", "80"]
        + (["--model", MODELO] if MODELO else []),
        input=prompt, cwd=cwd, env=_entorno_agente(), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=3600)
    try:
        datos = json.loads(r.stdout)
    except ValueError:
        datos = {"error": "salida no json", "stdout": r.stdout[-2000:], "stderr": r.stderr[-2000:]}
    datos["segundos"] = round(time.time() - inicio)
    json.dump(datos, open(salida, "w", encoding="utf-8"), indent=2)
    return datos


# --- los tres orquestadores -----------------------------------------------------


def _clon(raiz, nombre):
    """Arbol de integracion FUERA del repo: un worktree mas lo veria `converge`."""
    destino = os.path.join(raiz, nombre)
    _borra(destino)
    subprocess.run(["git", "clone", "-q", os.path.join(raiz, "main"), destino], check=True)
    _git(destino, "config", "user.email", "ab@local")
    _git(destino, "config", "user.name", "ab")
    conflictos = []
    for t in TAREAS:
        r = _git(destino, "merge", "--no-edit", "-q", "origin/%s" % t, check=False)
        if r.returncode:
            conflictos.append(t)
            _git(destino, "add", "-A")
            _git(destino, "commit", "-q", "--no-verify", "-m", "merge %s con conflictos" % t,
                 check=False)
    return destino, conflictos


def converge(raiz):
    """`gb tests --run --union` sobre los worktrees, cada uno con su diff SIN commitear
    contra la base (converge compara contra HEAD). Deja las ramas como estaban."""
    tips = {t: _git(os.path.join(raiz, t), "rev-parse", "HEAD").stdout.strip() for t in TAREAS}
    base = _git(os.path.join(raiz, "main"), "rev-parse", "HEAD").stdout.strip()
    for t in TAREAS:
        _git(os.path.join(raiz, t), "reset", "-q", "--soft", base)
    try:
        # Sin ruta posicional: el primer posicional de `gb tests` es el RANGO.
        r = subprocess.run([sys.executable, "-m", "galaxybrain.cli", "tests", "--run", "--union"],
                           cwd=os.path.join(raiz, "main"), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=1800,
                           env={k: v for k, v in os.environ.items() if k != "GB_DISABLE"})
    finally:
        for t in TAREAS:
            _git(os.path.join(raiz, t), "reset", "-q", "--soft", tips[t])
    return r.returncode, r.stdout + r.stderr


def _cola(texto, lineas=150):
    return "\n".join(texto.splitlines()[-lineas:])


def integrar(raiz, brazo, hecho_gb=None, agentes=True):
    """Merge + suite + hasta RONDAS integradores. `hecho_gb` va delante en el brazo con."""
    wt, conflictos = _clon(raiz, "int-" + brazo)
    descripcion = "".join("- %s: %s\n" % (t.upper(), open(os.path.join(AQUI, "tareas", t + ".md"),
                                                          encoding="utf-8").readline().strip())
                          for t in TAREAS)
    rondas = []
    rc, salida = _suite(wt)
    primero = rc
    for n in range(RONDAS):
        if rc == 0 or not agentes:
            break
        verificacion = _cola(salida)
        if conflictos:
            verificacion = "conflictos de merge en: %s\n\n%s" % (", ".join(conflictos), verificacion)
        if hecho_gb and n == 0:
            verificacion = ("ANTES del merge, gb verifico cada rama sola y su union "
                            "(`gb tests --run --union`):\n%s\n\nY tras el merge, pytest:\n%s"
                            % (_cola(hecho_gb, 120), verificacion))
        d = _claude(wt, PROMPT_INTEGRADOR % (descripcion, verificacion),
                    os.path.join(raiz, ".integrador-%s-%d.json" % (brazo, n + 1)))
        rondas.append({"usd": round(d.get("total_cost_usd") or 0, 2), "turnos": d.get("num_turns"),
                       "seg": d.get("segundos")})
        _git(wt, "add", "-A")
        _git(wt, "commit", "-q", "--no-verify", "-m", "integrador %d" % (n + 1), check=False)
        rc, salida = _suite(wt)
    return {"brazo": brazo, "conflictos": conflictos, "roja_al_merge": primero != 0,
            "verde_final": rc == 0, "rondas": rondas,
            "oculta_union": _verdes(oculta(wt, "union"))}


def orquestar(raiz, agentes=True):
    ramas = {}
    for t in TAREAS:
        rc, _ = _suite(os.path.join(raiz, t))
        ramas[t] = {"visible_sola": rc == 0, "oculta_sola": _verdes(oculta(os.path.join(raiz, t), t))}
    rc_gb, hecho = converge(raiz)
    open(os.path.join(raiz, ".converge.txt"), "w", encoding="utf-8").write(hecho)
    ci_wt, ci_conf = _clon(raiz, "int-ci")
    ci_rc, _ = _suite(ci_wt)
    filas = {
        "ramas": ramas,
        "converge": {"rc": rc_gb, "choque_semantico": "CHOQUE SEMANTICO" in hecho,
                     "rescate": "RESCATE ACCIDENTAL" in hecho,
                     "no_compone": "no se pudo componer" in hecho,
                     "ramas_rojas": [t for t in TAREAS if "ROJA   %s" % t in hecho]},
        "ci": {"todas_verdes_solas": all(r["visible_sola"] for r in ramas.values()),
               "main_roto": ci_rc != 0, "conflictos": ci_conf,
               "oculta_union": _verdes(oculta(ci_wt, "union"))},
        "sin": integrar(raiz, "sin", agentes=agentes),
        "con": integrar(raiz, "con", hecho_gb=hecho if rc_gb else None, agentes=agentes),
    }
    json.dump(filas, open(os.path.join(raiz, ".resultado.json"), "w", encoding="utf-8"), indent=2)
    return filas


# --- acciones -------------------------------------------------------------------


def validar(_n=None):
    """Las referencias en lugar de agentes: cada rama verde sola, la union roja por
    el choque A x B, converge lo nombra, y la union arreglada pasa la oculta."""
    raiz = montar(0)
    for t in TAREAS:
        wt = os.path.join(raiz, t)
        shutil.copytree(os.path.join(AQUI, "referencia", t), wt, dirs_exist_ok=True)
        _git(wt, "add", "-A")
        _git(wt, "commit", "-q", "-m", "referencia %s" % t)
    filas = orquestar(raiz, agentes=False)
    print(json.dumps(filas, indent=2))
    # La union arreglada a mano: B adopta el Resultado de A.
    wt = os.path.join(raiz, "int-sin")
    ruta = os.path.join(wt, "almacen", "cli.py")
    texto = open(ruta, encoding="utf-8").read()
    viejo = ("    colas, ventas = fifo.procesar(movimientos)\n"
             "    return informes.resumen(fifo.stock(colas), fifo.valor(colas), ventas, args.json)")
    assert texto.count(viejo) == 1, "la referencia B cambio: actualiza validar()"
    open(ruta, "w", encoding="utf-8").write(texto.replace(viejo, (
        "    r = fifo.procesar(movimientos)\n"
        "    return informes.resumen(fifo.stock(r.colas), fifo.valor(r.colas), r.ventas, args.json)")))
    arreglada = oculta(wt, "union")
    print("union arreglada: visible rc=%d, oculta %s" % (_suite(wt)[0], _verdes(arreglada)))
    print("fallan:", [k for k, v in arreglada.items() if not v])
    malos = []
    if not all(r["visible_sola"] for r in filas["ramas"].values()):
        malos.append("alguna rama de referencia no pasa sola su suite visible")
    if not filas["sin"]["roja_al_merge"]:
        malos.append("la union de referencia NO sale roja: no hay choque que medir")
    if not filas["converge"]["choque_semantico"]:
        malos.append("converge no nombra el choque")
    if filas["sin"]["conflictos"]:
        malos.append("conflictos de texto entre referencias: %s" % filas["sin"]["conflictos"])
    if not all(arreglada.values()):
        malos.append("la union arreglada no pasa la oculta")
    print("\nVALIDO" if not malos else "\nNO VALIDO:\n- " + "\n- ".join(malos))


def lanzar(n):
    import concurrent.futures

    _shim()
    for rep in range(1, n + 1):
        raiz = os.path.join(DESTINO, "r%d" % rep)
        if os.path.exists(os.path.join(raiz, ".resultado.json")):
            print("r%d ya hecha" % rep)
            continue
        raiz = montar(rep)
        with concurrent.futures.ThreadPoolExecutor(3) as pool:
            hechos = list(pool.map(lambda t: _claude(
                os.path.join(raiz, t),
                PROMPT_AGENTE % open(os.path.join(AQUI, "tareas", t + ".md"), encoding="utf-8").read(),
                os.path.join(raiz, ".agente-%s.json" % t)), TAREAS))
        for t, d in zip(TAREAS, hechos):
            _cierra_rama(raiz, t)
            print("r%d %s: %s$ %s turnos" % (rep, t, round(d.get("total_cost_usd") or 0, 2),
                                            d.get("num_turns")), flush=True)
        filas = orquestar(raiz)
        print("r%d: %s" % (rep, json.dumps({k: filas[k] for k in ("converge", "ci", "sin", "con")})),
              flush=True)


def medir(_n=None):
    for ruta in sorted(glob.glob(os.path.join(DESTINO, "r[1-9]*", ".resultado.json"))):
        f = json.load(open(ruta, encoding="utf-8"))
        rep = os.path.basename(os.path.dirname(ruta))
        print("== %s  ramas: %s" % (rep, " ".join("%s=%s/%s" % (t, "ok" if r["visible_sola"] else "ROJA",
                                                                   r["oculta_sola"])
                                                   for t, r in f["ramas"].items())))
        c = f["converge"]
        print("   converge rc=%s choque=%s rescate=%s no_compone=%s rojas=%s" % (
            c["rc"], c["choque_semantico"], c.get("rescate"), c.get("no_compone"),
            c.get("ramas_rojas")))
        print("   ci : main_roto=%s oculta=%s conflictos=%s" % (
            f["ci"]["main_roto"], f["ci"]["oculta_union"], f["ci"]["conflictos"]))
        for b in ("sin", "con"):
            x = f[b]
            print("   %s: roja_al_merge=%s rondas=%d usd=%.2f seg=%s verde=%s oculta=%s" % (
                b, x["roja_al_merge"], len(x["rondas"]), sum(r["usd"] for r in x["rondas"]),
                sum(r["seg"] or 0 for r in x["rondas"]), x["verde_final"], x["oculta_union"]))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("accion", choices=("validar", "lanzar", "medir"))
    p.add_argument("--n", type=int, default=3)
    p.add_argument("--modelo")
    a = p.parse_args()
    if a.modelo:
        global MODELO, DESTINO, SHIM
        MODELO = a.modelo
        DESTINO = DESTINO + "-" + a.modelo.split("-")[1]      # ab-gb/p-haiku
        SHIM = os.path.join(DESTINO, "_sin_gb")
    {"validar": validar, "lanzar": lanzar, "medir": medir}[a.accion](a.n)


if __name__ == "__main__":
    main()
