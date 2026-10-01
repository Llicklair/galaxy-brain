"""A/B F: el mismo encargo vago en un repo vacio, con `gb floor --init` y sin el.

    python bancos/ab_floor/correr.py montar [--n 2]
    python bancos/ab_floor/correr.py lanzar [--n 2]
    python bancos/ab_floor/correr.py medir

Ver README.md. Reusa de la v2 (`bancos/ab_dos_repos`) la suite oculta, el juez por
fase y el lanzador; lo nuevo es el montaje (CON = `floor --init`; SIN = nada y `gb`
inexistente) y dos metricas: la fuerza de SUS tests contra mutantes de SU codigo, y
cuanta ley acabo escrita.
"""

import argparse
import ast
import concurrent.futures
import glob
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))


def _carga_v2():
    """El `correr.py` de la v2 con nombre propio: los dos ficheros se llaman igual,
    y un `import correr` devolvia ESTE, a medio cargar."""
    import importlib.util

    ruta = os.path.join(os.path.dirname(AQUI), "ab_dos_repos", "correr.py")
    spec = importlib.util.spec_from_file_location("ab_v2_correr", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


v2 = _carga_v2()

RAIZ_GB = v2.RAIZ_GB
DESTINO = os.path.join(os.path.dirname(RAIZ_GB), "ab-gb", "f")
SHIM = os.path.join(DESTINO, "_sin_gb")
BRAZOS = ("sin", "con")
FASES = v2.FASES

PROMPT_F1 = ("Construye el programa descrito en ENCARGO.md de este repositorio. "
             "Haz commit cuando este terminado.")
PROMPT_CAMBIO = v2.PROMPT_CAMBIO


def _repo(brazo, i):
    return os.path.join(DESTINO, "%s-%d" % (brazo, i))


def _prompt(fase):
    if fase == "fase1":
        return PROMPT_F1
    return PROMPT_CAMBIO % open(os.path.join(AQUI, "spec", fase + ".md"), encoding="utf-8").read()


def _shim():
    os.makedirs(SHIM, exist_ok=True)
    for nombre, texto in (("gb", "#!/bin/sh\necho \"gb: command not found\" >&2\nexit 127\n"),
                          ("gb.cmd", "@echo gb: command not found 1>&2\r\n@exit /b 127\r\n")):
        with open(os.path.join(SHIM, nombre), "w", encoding="utf-8", newline="") as fh:
            fh.write(texto)


def montar(n):
    _shim()
    for i in range(1, n + 1):
        for brazo in BRAZOS:
            repo = _repo(brazo, i)
            if os.path.exists(repo):
                print("ya existe, no se toca: %s" % repo)
                continue
            os.makedirs(repo)
            v2._git(repo, "init", "-q", "-b", "main")
            v2._git(repo, "config", "user.email", "ab@local")
            v2._git(repo, "config", "user.name", "ab")
            shutil.copy(os.path.join(AQUI, "spec", "ENCARGO.md"), repo)
            if brazo == "con":
                subprocess.run([sys.executable, "-m", "galaxybrain.cli", "floor", "--init", repo],
                               capture_output=True, text=True, check=True)
            v2._git(repo, "add", "-A")
            v2._git(repo, "commit", "-q", "--no-verify", "-m", "encargo")
            print("montado: %s" % repo)


def _entorno(brazo):
    entorno = dict(os.environ)
    if brazo == "sin":
        entorno["GB_DISABLE"] = "1"
        entorno["PATH"] = SHIM + os.pathsep + entorno.get("PATH", "")
    else:
        entorno.pop("GB_DISABLE", None)
    return entorno


def construir(brazo, i):
    repo = _repo(brazo, i)
    partes = []
    original = v2._entorno
    v2._entorno = _entorno          # el lanzador de la v2, con el entorno de este banco
    try:
        for fase in FASES:
            d = v2._fase(repo, brazo, fase, _prompt(fase))
            partes.append("%s %s$" % (fase, round(d.get("total_cost_usd") or 0, 2)))
    finally:
        v2._entorno = original
    return "%s-%d: %s" % (brazo, i, " · ".join(partes))


def lanzar(n):
    for i in range(1, n + 1):
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            for linea in pool.map(construir, BRAZOS, (i, i)):
                print(linea, flush=True)


# --- metricas nuevas ------------------------------------------------------------

_SWAP_CMP = {ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt,
             ast.Eq: ast.NotEq, ast.NotEq: ast.Eq}
_SWAP_BIN = {ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.FloorDiv}


def _puntos(arbol):
    """Los nodos mutables de un fichero, en orden estable."""
    puntos = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Compare) and type(nodo.ops[0]) in _SWAP_CMP:
            puntos.append(nodo)
        elif isinstance(nodo, ast.BinOp) and type(nodo.op) in _SWAP_BIN:
            puntos.append(nodo)
    return puntos


def _muta(nodo):
    if isinstance(nodo, ast.Compare):
        nodo.ops[0] = _SWAP_CMP[type(nodo.ops[0])]()
    else:
        nodo.op = _SWAP_BIN[type(nodo.op)]()


def fuerza_de_sus_tests(repo, cuantos=30, semilla=0):
    """(muertos, total): mutantes de SU codigo que SU suite mata.

    Solo operadores (comparaciones y aritmetica), muestreados con semilla fija:
    lo mismo en los dos brazos. Los equivalentes existen y caen igual en los dos.
    Sin tests propios, ninguno muere — que es exactamente lo que vale esa suite."""
    paquete = next(iter(glob.glob(os.path.join(repo, "almacen"))
                        + glob.glob(os.path.join(repo, "src", "almacen"))), None)
    if not paquete:
        return 0, 0
    candidatos = []
    for ruta in sorted(glob.glob(os.path.join(paquete, "*.py"))):
        texto = open(ruta, encoding="utf-8").read()
        try:
            n = len(_puntos(ast.parse(texto)))
        except SyntaxError:
            continue
        candidatos += [(ruta, k) for k in range(n)]
    random.Random(semilla).shuffle(candidatos)
    muestra = candidatos[:cuantos]
    muertos = 0
    for ruta, k in muestra:
        tmp = tempfile.mkdtemp()
        copia = os.path.join(tmp, "r")
        shutil.copytree(repo, copia, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        destino = os.path.join(copia, os.path.relpath(ruta, repo))
        arbol = ast.parse(open(destino, encoding="utf-8").read())
        _muta(_puntos(arbol)[k])
        open(destino, "w", encoding="utf-8").write(ast.unparse(arbol))
        try:
            r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider"],
                               cwd=copia, capture_output=True, text=True, timeout=180,
                               env=dict(os.environ, GB_DISABLE="1"))
            # rc 5 = pytest no encontro tests: el mutante sobrevive.
            muertos += r.returncode not in (0, 5)
        except subprocess.TimeoutExpired:
            muertos += 1
        shutil.rmtree(tmp, ignore_errors=True)
    return muertos, len(muestra)


def ley_escrita(repo):
    """Cuanta ley quedo por escrito y cuanto andamio sin rellenar."""
    reglas = 0
    for ruta in glob.glob(os.path.join(repo, "**", ".gb-boundaries"), recursive=True):
        reglas += sum(1 for linea in open(ruta, encoding="utf-8") if "-/->" in linea
                      and not linea.lstrip().startswith("#"))
    arquitectura = os.path.join(repo, "ARCHITECTURE.md")
    numeradas = 0
    if os.path.exists(arquitectura):
        numeradas = len(re.findall(r"(?m)^\d+\.\s+(?!<!--)\S",
                                   open(arquitectura, encoding="utf-8").read()))
    pendientes = 0
    for ruta in glob.glob(os.path.join(repo, "**", "*"), recursive=True):
        if os.path.isfile(ruta) and ".git" not in ruta.split(os.sep):
            try:
                pendientes += open(ruta, encoding="utf-8", errors="replace").read().count("gb:pendiente")
            except OSError:
                pass
    return {"reglas_frontera": reglas, "reglas_numeradas": numeradas, "marcas_pendientes": pendientes}


def forma_por_fase(repo):
    """La forma del codigo de PRODUCCION en cada foto: la hipotesis del espagueti
    (con gb el codigo se enreda menos a la larga) se ve en la pendiente, no en el
    final. Aristas sin tests: un test importa medio repo y ensuciaria la cuenta."""
    sys.path.insert(0, os.path.join(RAIZ_GB, "src"))
    from galaxybrain import graph

    serie, anterior = [], v2._git(repo, "rev-list", "--max-parents=0", "HEAD").stdout.split()[0]
    for fase in FASES:
        wt = v2._en_tag(repo, fase)
        rep = graph.analyze(wt)
        aristas = [(a, b) for a, b in (rep.get("edge_list") or [])
                   if not graph.es_modulo_de_test(a) and not graph.es_modulo_de_test(b)]
        tocados = [f for f in v2._git(repo, "diff", "--name-only", anterior, fase).stdout.split()
                   if f.endswith(".py") and "test" not in f]
        serie.append({"fase": fase, "aristas": len(aristas), "ciclos": len(rep.get("cycles") or []),
                      "ficheros_tocados": len(tocados)})
        v2._git(repo, "worktree", "remove", "--force", wt, check=False)
        anterior = fase
    return serie


def forma(repo):
    sys.path.insert(0, os.path.join(RAIZ_GB, "src"))
    from galaxybrain import graph

    rep = graph.analyze(repo)
    fan_out = rep.get("fan_out") or {}
    return {"modulos": rep.get("modules", 0), "ciclos": len(rep.get("cycles") or []),
            "fan_out_max": max(fan_out.values()) if fan_out else 0}


def medir(_n=None):
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
        por_fase = {}
        for f in FASES:
            wt = v2._en_tag(repo, f)
            por_fase[f] = v2._oculta(wt, v2._marcas_hasta(f))
            v2._git(repo, "worktree", "remove", "--force", wt, check=False)
        final = por_fase[FASES[-1]]
        pasaron = {k for f in FASES[:-1] for k, v in por_fase[f].items() if v is None}
        muertos, total = fuerza_de_sus_tests(repo)
        fila = {"build": nombre}
        for f in FASES:
            fila[f] = "%d/%d" % (v2._verdes(por_fase[f]), len(por_fase[f]))
        fila["regresiones"] = sum(1 for k in pasaron if final.get(k) is not None)
        fila["sus_tests_matan"] = "%d/%d" % (muertos, total)
        fila.update(ley_escrita(repo))
        fila.update(forma(repo))
        serie = forma_por_fase(repo)
        fila["aristas_por_fase"] = [s["aristas"] for s in serie]
        fila["tocados_por_fase"] = [s["ficheros_tocados"] for s in serie]
        fila["usd"] = round(sum((fases[f].get("total_cost_usd") or 0) for f in FASES), 2)
        fila["min"] = round(sum((fases[f].get("segundos") or 0) for f in FASES) / 60)
        filas.append(fila)
    json.dump(filas, open(os.path.join(DESTINO, "resultados.json"), "w", encoding="utf-8"), indent=2)
    if filas:
        cab = list(filas[0])
        print(" | ".join(cab))
        for f in filas:
            print(" | ".join(str(f[k]) for k in cab))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("accion", choices=("montar", "lanzar", "medir"))
    p.add_argument("--n", type=int, default=2)
    a = p.parse_args()
    {"montar": montar, "lanzar": lanzar, "medir": medir}[a.accion](a.n)


if __name__ == "__main__":
    main()
