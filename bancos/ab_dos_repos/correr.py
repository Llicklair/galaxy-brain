"""El A/B de verdad: monta los brazos, lanza las construcciones y las mide.

    python bancos/ab_dos_repos/correr.py montar  [--n 4]        # repos, sin gastar cuota
    python bancos/ab_dos_repos/correr.py lanzar  [--n 4]        # 2*n construcciones, 2 a la vez
    python bancos/ab_dos_repos/correr.py medir                  # la tabla de resultados

Las construcciones viven FUERA de este repo, en ../ab-gb/<brazo>-<i>. Cada fase es un
proceso `claude -p` aparte con su entorno: el brazo sin gb lleva GB_DISABLE=1, que apaga la
consola en todo lo que lance. Ver README.md para el porque de cada decision.
"""

import argparse
import concurrent.futures
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ_GB = os.path.dirname(os.path.dirname(AQUI))
#: v2 (1-oct-2026): la v1 (2 fases, sin rendimiento) salio 35/35 en los dos brazos —
#: efecto techo— y vive en ../ab-gb/v1. Esta sube la dificultad, mismo modelo.
DESTINO = os.path.join(os.path.dirname(RAIZ_GB), "ab-gb", "v2")
BRAZOS = ("sin", "con")
FASES = ("fase1", "fase2", "fase3", "fase4")

PROMPT_F1 = ("Construye el proyecto descrito en SCOPE.md de este repositorio, con sus tests. "
             "Trabaja hasta que se cumpla su criterio de terminado y haz commit del resultado.")
PROMPT_CAMBIO = ("Llega una peticion de cambio para este proyecto:\n\n%s\n\n"
                 "Implementala con sus tests y haz commit del resultado.")


def _prompt(fase):
    if fase == "fase1":
        return PROMPT_F1
    return PROMPT_CAMBIO % open(os.path.join(AQUI, "spec", fase + ".md"), encoding="utf-8").read()


def _marcas_hasta(fase):
    """Expresion -m con los tests de las fases <= `fase` (fase1 = sin marca)."""
    fuera = [f for f in FASES[FASES.index(fase) + 1:]]
    return " and ".join("not %s" % f for f in fuera) or None


def _git(repo, *args, check=True):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=check)


def _repo(brazo, i):
    return os.path.join(DESTINO, "%s-%d" % (brazo, i))


def montar(n):
    os.makedirs(DESTINO, exist_ok=True)
    for i in range(1, n + 1):
        for brazo in BRAZOS:
            repo = _repo(brazo, i)
            if os.path.exists(repo):
                print("ya existe, no se toca: %s" % repo)
                continue
            os.makedirs(repo)
            _git(repo, "init", "-q", "-b", "main")
            _git(repo, "config", "user.email", "ab@local")
            _git(repo, "config", "user.name", "ab")
            shutil.copy(os.path.join(AQUI, "spec", "SCOPE.md"), repo)
            if brazo == "con":
                subprocess.run([sys.executable, "-m", "galaxybrain.cli", "floor", "--init", repo],
                               capture_output=True, text=True, check=True)
                shutil.copy(os.path.join(AQUI, "spec", "gb-boundaries"),
                            os.path.join(repo, ".gb-boundaries"))
            _git(repo, "add", "-A")
            _git(repo, "commit", "-q", "--no-verify", "-m", "spec")
            print("montado: %s" % repo)


def _entorno(brazo):
    entorno = dict(os.environ)
    if brazo == "sin":
        entorno["GB_DISABLE"] = "1"
    else:
        entorno.pop("GB_DISABLE", None)
    return entorno


def _fase(repo, brazo, nombre, prompt):
    salida = os.path.join(repo, ".ab-%s.json" % nombre)
    if os.path.exists(salida):
        return json.load(open(salida, encoding="utf-8"))
    inicio = time.time()
    # En Windows `claude` es un .cmd de npm: ruta completa, y el prompt por stdin
    # (como argumento, el markdown de varias lineas no sobrevive a cmd.exe).
    r = subprocess.run(
        [shutil.which("claude") or "claude", "-p", "--output-format", "json",
         "--permission-mode", "bypassPermissions", "--max-turns", "120"],
        input=prompt, cwd=repo, env=_entorno(brazo), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=3600)
    try:
        datos = json.loads(r.stdout)
    except ValueError:
        datos = {"error": "salida no json", "stdout": r.stdout[-2000:], "stderr": r.stderr[-2000:]}
    datos["rc"] = r.returncode
    datos["segundos"] = round(time.time() - inicio)
    json.dump(datos, open(salida, "w", encoding="utf-8"), indent=2)
    # La foto: lo que haya, commiteado, sin hooks (esto es medir, no construir).
    _git(repo, "add", "-A", check=False)
    _git(repo, "commit", "-q", "--no-verify", "-m", "foto %s" % nombre, check=False)
    _git(repo, "tag", "-f", nombre, check=False)
    return datos


def construir(brazo, i):
    repo = _repo(brazo, i)
    partes = []
    for fase in FASES:
        d = _fase(repo, brazo, fase, _prompt(fase))
        partes.append("%s rc=%s %ss %s$" % (fase, d.get("rc"), d.get("segundos"),
                                            round(d.get("total_cost_usd") or 0, 2)))
    return "%s-%d: %s" % (brazo, i, " · ".join(partes))


def lanzar(n):
    # En pares (sin-i, con-i) a la vez: la misma hora del dia para los dos brazos.
    for i in range(1, n + 1):
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            for linea in pool.map(construir, BRAZOS, (i, i)):
                print(linea, flush=True)


# --- medir ---------------------------------------------------------------------


def _oculta(repo, marca):
    xml = tempfile.mktemp(suffix=".xml")
    args = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
            "-c", os.path.join(AQUI, "oculta", "pytest.ini"), "--junitxml", xml,
            os.path.join(AQUI, "oculta", "aceptacion_oculta.py")]
    if marca:
        args[-1:-1] = ["-m", marca]
    subprocess.run(args, env=dict(os.environ, ALMACEN_REPO=repo), capture_output=True, text=True)
    import xml.etree.ElementTree as ET

    casos = {}
    for caso in ET.parse(xml).getroot().iter("testcase"):
        fallo = caso.find("failure") if caso.find("failure") is not None else caso.find("error")
        casos[caso.get("name")] = None if fallo is None else (fallo.get("message") or "") + (fallo.text or "")
    return casos


def _en_tag(repo, tag):
    destino = tempfile.mkdtemp()
    _git(repo, "worktree", "add", "-f", "--detach", destino, tag, check=False)
    return destino


def _fronteras(repo):
    tmp = tempfile.mkdtemp()
    shutil.copytree(repo, os.path.join(tmp, "r"), ignore=shutil.ignore_patterns(".git"))
    shutil.copy(os.path.join(AQUI, "spec", "gb-boundaries"), os.path.join(tmp, "r", ".gb-boundaries"))
    sys.path.insert(0, os.path.join(RAIZ_GB, "src"))
    from galaxybrain import graph

    rep = graph.analyze(os.path.join(tmp, "r"))
    return len(rep.get("violations") or []), len(rep.get("cycles") or [])


def _ejecuciones_de_tests(sesion):
    if not sesion:
        return None
    rutas = glob.glob(os.path.expanduser("~/.claude/projects/*/%s.jsonl" % sesion))
    if not rutas:
        return None
    n = 0
    for linea in open(rutas[0], encoding="utf-8", errors="replace"):
        if '"tool_use"' in linea and "pytest" in linea:
            try:
                bloques = json.loads(linea).get("message", {}).get("content") or []
            except ValueError:
                continue
            n += sum(1 for b in bloques if isinstance(b, dict) and b.get("type") == "tool_use"
                     and "pytest" in json.dumps(b.get("input", {})))
    return n


def _verdes(casos):
    return sum(1 for v in casos.values() if v is None)


def medir():
    filas = []
    for repo in sorted(glob.glob(os.path.join(DESTINO, "*-*"))):
        nombre = os.path.basename(repo)
        fases = {}
        for f in FASES:
            ruta = os.path.join(repo, ".ab-%s.json" % f)
            fases[f] = json.load(open(ruta, encoding="utf-8")) if os.path.exists(ruta) else None
        if not fases[FASES[-1]]:
            print("%s: sin terminar" % nombre)
            continue
        # Cada foto se juzga con los tests de SU fase y las anteriores: lo que se
        # le habia pedido hasta ese momento, no lo que aun no existia.
        por_fase = {}
        for f in FASES:
            wt = _en_tag(repo, f)
            por_fase[f] = _oculta(wt, _marcas_hasta(f))
            _git(repo, "worktree", "remove", "--force", wt, check=False)
        final = por_fase[FASES[-1]]
        # Regresion: un test que paso en ALGUNA foto anterior y cae al final.
        pasaron = {k for f in FASES[:-1] for k, v in por_fase[f].items() if v is None}
        regresiones = sum(1 for k in pasaron if final.get(k) is not None)
        trazas = sum(1 for v in final.values() if v and "Traceback" in v)
        cruces, ciclos = _fronteras(repo)
        coste = sum((fases[f].get("total_cost_usd") or 0) for f in fases)
        minutos = sum((fases[f].get("segundos") or 0) for f in fases) / 60
        tests = [_ejecuciones_de_tests(fases[f].get("session_id")) for f in fases]
        fila = {"build": nombre}
        for f in FASES:
            fila[f] = "%d/%d" % (_verdes(por_fase[f]), len(por_fase[f]))
        fila.update({"regresiones": regresiones, "trazas": trazas, "cruces": cruces,
                     "ciclos": ciclos, "usd": round(coste, 2), "min": round(minutos),
                     "pytest": tests})
        filas.append(fila)
    json.dump(filas, open(os.path.join(DESTINO, "resultados.json"), "w", encoding="utf-8"), indent=2)
    cab = ("build",) + FASES + ("regresiones", "trazas", "cruces", "ciclos", "usd", "min", "pytest")
    print(" | ".join(cab))
    for f in filas:
        print(" | ".join(str(f[k]) for k in cab))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("accion", choices=("montar", "lanzar", "medir"))
    p.add_argument("--n", type=int, default=4)
    a = p.parse_args()
    {"montar": lambda: montar(a.n), "lanzar": lambda: lanzar(a.n), "medir": medir}[a.accion]()


if __name__ == "__main__":
    main()
