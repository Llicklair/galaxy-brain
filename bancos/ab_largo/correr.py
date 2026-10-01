"""A/B L: 14 pasos encadenados, con `floor --init` + gb y sin gb. ¿Se enreda menos?

    python bancos/ab_largo/correr.py montar [--n 2]
    python bancos/ab_largo/correr.py lanzar [--n 2]
    python bancos/ab_largo/correr.py medir

Reusa el banco F (montaje, entorno sin gb, lanzador) y la suite oculta de la v2 para
las fases 1-4; las 5-14 las juzga `oculta/aceptacion_largo.py`. Lo que se mira es la
PENDIENTE de la forma del codigo de produccion y del coste por paso (README.md).
"""

import argparse
import ast
import glob
import json
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

AQUI = os.path.dirname(os.path.abspath(__file__))


def _carga(nombre, ruta):
    import importlib.util

    spec = importlib.util.spec_from_file_location(nombre, ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


F = _carga("ab_f_correr", os.path.join(os.path.dirname(AQUI), "ab_floor", "correr.py"))
V2 = F.v2
FASES = tuple("fase%d" % n for n in range(1, 15))
F.DESTINO = os.path.join(os.path.dirname(V2.RAIZ_GB), "ab-gb", "l")
F.SHIM = os.path.join(F.DESTINO, "_sin_gb")
F.FASES = FASES
F.AQUI = AQUI                      # ENCARGO.md y fase*.md salen de bancos/ab_largo/spec

#: El brazo CON, tras la F (1-oct-2026): el andamio vacio de `floor --init` no se
#: rellena y encarece un 32 %, asi que aqui NO va. Va la conexion minima de gb y la
#: LEY VIVA: tras cada fase se derivan las hojas nuevas y se añaden, con su porque.
HOOK_CON = ("#!/bin/sh\n"
            "gb graph . --gate --since HEAD --brief || exit 1\n"
            "gb check --staged --brief\n")
AJUSTES_CON = json.dumps({"hooks": {"SessionStart": [{"matcher": "", "hooks": [
    {"type": "command", "command": "gb graph --context", "timeout": 15}]}]}}, indent=2)


def montar(n):
    F._shim()
    for i in range(1, n + 1):
        for brazo in F.BRAZOS:
            repo = F._repo(brazo, i)
            if os.path.exists(repo):
                print("ya existe, no se toca: %s" % repo)
                continue
            os.makedirs(repo)
            V2._git(repo, "init", "-q", "-b", "main")
            V2._git(repo, "config", "user.email", "ab@local")
            V2._git(repo, "config", "user.name", "ab")
            import shutil

            shutil.copy(os.path.join(AQUI, "spec", "ENCARGO.md"), repo)
            if brazo == "con":
                os.makedirs(os.path.join(repo, ".githooks"))
                os.makedirs(os.path.join(repo, ".claude"))
                with open(os.path.join(repo, ".githooks", "pre-commit"), "w", encoding="utf-8",
                          newline="\n") as fh:
                    fh.write(HOOK_CON)
                open(os.path.join(repo, ".claude", "settings.json"), "w",
                     encoding="utf-8").write(AJUSTES_CON)
                open(os.path.join(repo, ".gitattributes"), "w", encoding="utf-8").write(
                    ".githooks/** text eol=lf\n")
                V2._git(repo, "config", "core.hooksPath", ".githooks")
            V2._git(repo, "add", "-A")
            V2._git(repo, "commit", "-q", "--no-verify", "-m", "encargo")
            print("montado: %s" % repo)


def ley_viva(repo):
    """Lo que haria un gb que MANTIENE la ley: deriva las hojas de hoy y añade las
    que falten a `.gb-boundaries`, cada una con su porque. Devuelve cuantas añadio."""
    sys.path.insert(0, os.path.join(V2.RAIZ_GB, "src"))
    from galaxybrain import graph

    ruta = os.path.join(repo, ".gb-boundaries")
    declaradas = graph.load_boundaries(repo, ruta).get("rules") or () if os.path.exists(ruta) else ()
    rep = graph.analyze(repo)
    hojas = graph.proponer_hojas(rep, declaradas)
    if not hojas:
        return 0
    with open(ruta, "a", encoding="utf-8") as fh:
        if os.path.getsize(ruta) == 0:
            fh.write("# Ley derivada por gb del codigo: las HOJAS no importan nada del proyecto.\n"
                     "# Si una deja de serlo, cambia la regla a conciencia, no la saltes.\n")
        for h in hojas:
            fh.write("\n# %s: hoy no importa ningun modulo del proyecto; la importan %s\n%s -/-> *\n"
                     % (h["modulo"], ", ".join(h["importado_por"]), h["modulo"]))
    V2._git(repo, "add", ".gb-boundaries")
    V2._git(repo, "commit", "-q", "--no-verify", "-m", "ley derivada (gb): %d hoja(s)" % len(hojas))
    return len(hojas)


def construir(brazo, i):
    repo = F._repo(brazo, i)
    partes = []
    original = V2._entorno
    V2._entorno = F._entorno
    try:
        for fase in FASES:
            d = V2._fase(repo, brazo, fase, F._prompt(fase))
            nuevas = ley_viva(repo) if brazo == "con" else 0
            partes.append("%s %s$%s" % (fase, round(d.get("total_cost_usd") or 0, 2),
                                        " +%d hojas" % nuevas if nuevas else ""))
    finally:
        V2._entorno = original
    return "%s-%d: %s" % (brazo, i, " · ".join(partes))


def lanzar(n):
    import concurrent.futures

    for i in range(1, n + 1):
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            for linea in pool.map(construir, F.BRAZOS, (i, i)):
                print(linea, flush=True)


def _oculta_largo(repo, hasta):
    """Tests de las fases 5..hasta de la suite L. {nombre: None si verde}."""
    n = int(hasta[4:])
    if n < 5:
        return {}
    marcas = " or ".join("fase%d" % k for k in range(5, n + 1))
    xml = tempfile.mktemp(suffix=".xml")
    subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                    "-c", os.path.join(AQUI, "oculta", "pytest.ini"), "-m", marcas,
                    "--junitxml", xml, os.path.join(AQUI, "oculta", "aceptacion_largo.py")],
                   env=dict(os.environ, ALMACEN_REPO=repo), capture_output=True, text=True)
    casos = {}
    for caso in ET.parse(xml).getroot().iter("testcase"):
        fallo = caso.find("failure") if caso.find("failure") is not None else caso.find("error")
        casos[caso.get("name")] = None if fallo is None else (fallo.get("message") or "")
    return casos


def _funciones(raiz):
    """Longitudes (en lineas) de las funciones del codigo de produccion."""
    largos = []
    for ruta in glob.glob(os.path.join(raiz, "**", "*.py"), recursive=True):
        partes = os.path.relpath(ruta, raiz).replace("\\", "/").split("/")
        if any(p.startswith("test") or p == "tests" for p in partes) or ".git" in partes:
            continue
        try:
            arbol = ast.parse(open(ruta, encoding="utf-8").read())
        except (SyntaxError, UnicodeDecodeError):
            continue
        for nodo in ast.walk(arbol):
            if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
                largos.append((nodo.end_lineno or nodo.lineno) - nodo.lineno + 1)
    return largos


def medir(_n=None):
    sys.path.insert(0, os.path.join(V2.RAIZ_GB, "src"))
    from galaxybrain import graph

    filas = []
    for repo in sorted(glob.glob(os.path.join(F.DESTINO, "*-*"))):
        nombre = os.path.basename(repo)
        datos = {}
        for f in FASES:
            ruta = os.path.join(repo, ".ab-%s.json" % f)
            datos[f] = json.load(open(ruta, encoding="utf-8")) if os.path.exists(ruta) else None
        hechas = [f for f in FASES if datos[f]]
        if not hechas:
            continue
        serie, anterior = [], V2._git(repo, "rev-list", "--max-parents=0", "HEAD").stdout.split()[0]
        for f in hechas:
            wt = V2._en_tag(repo, f)
            marca_v2 = V2._marcas_hasta(f) if f in V2.FASES else None
            v2 = V2._oculta(wt, marca_v2)
            largo = _oculta_largo(wt, f)
            rep = graph.analyze(wt)
            aristas = [(a, b) for a, b in (rep.get("edge_list") or [])
                       if not graph.es_modulo_de_test(a) and not graph.es_modulo_de_test(b)]
            modulos = [m for m in (rep.get("fan_in") or {}) if not graph.es_modulo_de_test(m)]
            largos = _funciones(wt)
            tocados = [x for x in V2._git(repo, "diff", "--name-only", anterior, f).stdout.split()
                       if x.endswith(".py") and "test" not in x]
            serie.append({
                "fase": f,
                "v2_verdes": "%d/%d" % (V2._verdes(v2), len(v2)),
                "largo_verdes": "%d/%d" % (V2._verdes(largo), len(largo)),
                "aristas_prod": len(aristas), "modulos_prod": len(modulos),
                "ciclos": len(rep.get("cycles") or []),
                "tocados": len(tocados),
                "fn_max": max(largos) if largos else 0,
                "fn_media": round(sum(largos) / len(largos), 1) if largos else 0,
                "usd": round(datos[f].get("total_cost_usd") or 0, 2),
                "turnos": datos[f].get("num_turns"),
            })
            V2._git(repo, "worktree", "remove", "--force", wt, check=False)
            anterior = f
        filas.append({"build": nombre, "serie": serie})
        print("== %s" % nombre)
        cab = ("fase", "v2_verdes", "largo_verdes", "aristas_prod", "modulos_prod", "ciclos",
               "tocados", "fn_max", "fn_media", "usd", "turnos")
        print("   " + " | ".join(cab))
        for s in serie:
            print("   " + " | ".join(str(s[k]) for k in cab))
    json.dump(filas, open(os.path.join(F.DESTINO, "resultados.json"), "w", encoding="utf-8"),
              indent=2)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("accion", choices=("montar", "lanzar", "medir"))
    p.add_argument("--n", type=int, default=2)
    a = p.parse_args()
    {"montar": montar, "lanzar": lanzar, "medir": medir}[a.accion](a.n)


if __name__ == "__main__":
    main()
