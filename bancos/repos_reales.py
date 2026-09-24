"""El banco de repos REALES: la conformidad medida contra codigo que no escribimos.

Por que existe. Las sondas de conformidad miden cada lenguaje contra fixtures
escritos aqui, y un fixture solo prueba la forma que a su autor se le ocurrio.
El 24-sep-2026, generando videos sobre repos ajenos, salieron en una tarde tres
fallos que llevaban meses con la suite en verde:

  - Rust (tach): `use globset::Glob` caia en `resolvers/glob.rs` y fabricaba un
    CICLO que el gate bloquearia — bloquear sobre algo que no es un hecho.
  - Go (google/uuid): `import "time"` caia en `time.go`; las 6 aristas del
    grafo eran inventadas.
  - JS (express): `app.use = function use(...)` y los metodos de clase no eran
    simbolos; gb no veia ni un metodo de la libreria.

Criterio de terminado (escrito antes del codigo):
  1. Un repo real por lenguaje, clavado a un commit: reproducible.
  2. Por repo, comprobaciones CURADAS leyendo su codigo: simbolos que deben
     verse, aristas que deben existir y aristas que NO deben (los falsos de
     arriba quedan como regresion), llamadas resueltas y ciclos esperados.
  3. Las metricas (modulos, aristas, ciclos, simbolos, llamadas) contra una
     linea base: un cambio del motor que mueva numeros se ve en cada pasada.
  4. Una comprobacion curada que falla -> exit 1.

No entra en la suite: clona de la red (una vez; luego cachea). Se corre a mano,
como los demas bancos:

    python bancos/repos_reales.py            # comprueba y enseña deltas
    python bancos/repos_reales.py --base     # reescribe la linea base

Añadir un lenguaje es una entrada en REPOS con sus comprobaciones leidas del
codigo real — no copiadas de la salida de gb, que seria certificar lo que hay.
"""

import json
import os
import subprocess
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(AQUI, "repos_reales.base.json")
CACHE = os.environ.get("GB_REPOS_REALES") or os.path.join(tempfile.gettempdir(), "gb-repos-reales")

REPOS = [
    {
        "nombre": "import-linter", "lenguaje": "python",
        "url": "https://github.com/seddonym/import-linter",
        "sha": "31927f1457e3df673912cb5efb0afa6dbc37585f",
        "simbolos": ["importlinter.domain.contract.ContractCheck",
                     "importlinter.application.use_cases.create_report",
                     "importlinter.contracts.forbidden.ForbiddenContract.check"],
        "aristas": [["importlinter.cli", "importlinter.application.use_cases"]],
        "llamadas": [["importlinter.application.use_cases.create_report",
                      "importlinter.application.use_cases._build_graph"]],
        "ciclos": 0,
    },
    {
        "nombre": "tach", "lenguaje": "rust+python",
        "url": "https://github.com/gauge-sh/tach",
        "sha": "65df67ac51a8d0e8f9e0398ea72c924fea34fd25",
        "simbolos": ["filesystem.file_to_module_path"],
        "aristas": [["filesystem", "config"]],
        # crates externos que casaban con modulos propios por sufijo
        "no_aristas": [["filesystem", "resolvers.glob"], ["interrupt", "commands.sync"],
                       ["processors.ignore_directive", "commands.sync"]],
        "ciclos": 0,
    },
    {
        "nombre": "express", "lenguaje": "js",
        "url": "https://github.com/expressjs/express",
        "sha": "9a34acf03cb818ff3f8bc40e44176e277a25cbb9",
        "simbolos": ["lib.application.use", "lib.response.send", "lib.express.createApplication"],
        "aristas": [["lib.express", "lib.application"]],
        # this.x() por ambito: dentro de `app.x = function` y de `res.x = function`
        "llamadas": [["lib.application.defaultConfiguration", "lib.application.set"],
                     ["lib.response.send", "lib.response.get"]],
        "ciclos": 0,
    },
    {
        "nombre": "ky", "lenguaje": "ts",
        "url": "https://github.com/sindresorhus/ky",
        "sha": "0d59458a0a58e1c3d7c6db0ab17ed5c7cd671e47",
        "simbolos": ["source.core.Ky.Ky"],
        "aristas": [["source.core.Ky", "source.core.constants"]],
        # REAL, y a sabiendas: types/hooks.ts hace `import type ... from
        # '../index.js'`, que cierra el ciclo con el barril. Es solo de tipos (se
        # borra al compilar); si eso debe contar es una decision abierta, no un
        # fallo del motor. Si cambia, este numero lo dice.
        "ciclos": 1,
    },
    {
        "nombre": "uuid", "lenguaje": "go",
        "url": "https://github.com/google/uuid",
        "sha": "2d3c2a9cc518326daf99a383f07c4d3c44317e4d",
        "simbolos": ["uuid.Parse", "version4.NewRandom"],
        # un solo paquete: sus ficheros no se importan entre si. Estas caian
        # de `import "database/sql/driver"` y `import "time"` (stdlib).
        "no_aristas": [["null", "sql"], ["version6", "time"]],
        "llamadas": [["version4.New", "version4.NewRandom"]],
        "ciclos": 0,
    },
]


def _git(*args, cwd=None):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def clon(repo):
    """El repo en su commit exacto, clonado una vez y cacheado."""
    ruta = os.path.join(CACHE, repo["nombre"])
    if os.path.isdir(ruta) and _git("rev-parse", "HEAD", cwd=ruta).stdout.strip() == repo["sha"]:
        return ruta
    os.makedirs(ruta, exist_ok=True)
    _git("init", "-q", cwd=ruta)
    _git("fetch", "-q", "--depth", "1", repo["url"], repo["sha"], cwd=ruta)
    r = _git("checkout", "-q", "FETCH_HEAD", cwd=ruta)
    if r.returncode != 0:
        raise SystemExit("no pude clonar %s@%s: %s" % (repo["url"], repo["sha"][:8], r.stderr))
    return ruta


def _gb(*args):
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    p = subprocess.run([sys.executable, "-m", "galaxybrain.cli", *args, "--json"],
                       capture_output=True, env=env, timeout=900)
    return json.loads(p.stdout.decode("utf-8", "replace") or "{}")


def mide(repo):
    ruta = clon(repo)
    g, s = _gb("graph", ruta), _gb("symbols", ruta)
    aristas = {tuple(e) for e in g.get("edge_list") or []}
    llamadas = {(o, d) for o, d, t in s.get("edges") or [] if t == "CALLS"}
    quals = {n["qual"] for n in s.get("nodes") or []}
    fallos = []
    for q in repo.get("simbolos", []):
        if q not in quals:
            fallos.append("falta el simbolo %s" % q)
    for o, d in repo.get("aristas", []):
        if (o, d) not in aristas:
            fallos.append("falta la arista %s -> %s" % (o, d))
    for o, d in repo.get("no_aristas", []):
        if (o, d) in aristas:
            fallos.append("arista INVENTADA %s -> %s" % (o, d))
    for o, d in repo.get("llamadas", []):
        if (o, d) not in llamadas:
            fallos.append("falta la llamada %s -> %s" % (o, d))
    ciclos = len(g.get("cycles") or [])
    if "ciclos" in repo and ciclos != repo["ciclos"]:
        fallos.append("%d ciclo(s), se esperaban %d" % (ciclos, repo["ciclos"]))
    metricas = {
        "modulos": g.get("modules", 0), "aristas": len(aristas), "ciclos": ciclos,
        "simbolos": len([n for n in s.get("nodes") or [] if n.get("kind") != "module"]),
        "llamadas": s.get("calls_resolved") or 0,
    }
    return metricas, fallos


def main(argv):
    base = {}
    if os.path.isfile(BASE):
        with open(BASE, encoding="utf-8") as fh:
            base = json.load(fh)
    nueva, rotos = {}, 0
    print("%-14s %-12s %s" % ("repo", "lenguaje", "modulos aristas ciclos simbolos llamadas"))
    for repo in REPOS:
        metricas, fallos = mide(repo)
        nueva[repo["nombre"]] = metricas
        antes = base.get(repo["nombre"], {})
        celdas = []
        for k in ("modulos", "aristas", "ciclos", "simbolos", "llamadas"):
            v, a = metricas[k], antes.get(k)
            celdas.append("%d%s" % (v, "" if a in (None, v) else " (%+d)" % (v - a)))
        print("%-14s %-12s %s" % (repo["nombre"], repo["lenguaje"], "  ".join(celdas)))
        for f in fallos:
            print("    ROTO: %s" % f)
        rotos += len(fallos)
    if "--base" in argv:
        with open(BASE, "w", encoding="utf-8") as fh:
            json.dump(nueva, fh, indent=1, sort_keys=True)
            fh.write("\n")
        print("linea base reescrita: %s" % BASE)
    print("%d repo(s) - %d comprobacion(es) rota(s)" % (len(REPOS), rotos))
    return 1 if rotos else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
