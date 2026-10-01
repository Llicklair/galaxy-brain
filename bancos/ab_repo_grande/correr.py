"""A/B v3: tareas REALES de un repo grande (guardia-mvp), con gb y sin gb.

La v1 y la v2 (bancos/ab_dos_repos) salieron perfectas en los dos brazos: un
proyecto que cabe entero en el contexto, con la ley escrita en el prompt, no
necesita gb. Esta mide donde gb dice aportar: un repo de 650 nodos, con la ley
de arquitectura escrita SOLO en `src/.gb-boundaries`, y tareas sacadas de su
historia real.

    python bancos/ab_repo_grande/correr.py validar           # cada tarea: oculta roja en el padre, verde en la solucion
    python bancos/ab_repo_grande/correr.py montar  [tareas]  # repos de los dos brazos, sin gastar cuota
    python bancos/ab_repo_grande/correr.py lanzar  [tareas]  # un `claude -p` por brazo y tarea, en pares
    python bancos/ab_repo_grande/correr.py medir

Los dos brazos reciben EL MISMO repo, ley incluida (`src/.gb-boundaries` de la
solucion real, como documento). Lo unico que cambia es gb:

    CON: gate y `check` en el pre-commit, hook de sesion, consola encendida.
    SIN: gb no existe (un `gb` falso delante en el PATH que dice "command not
         found", GB_DISABLE=1, y fuera las lineas de gb de los documentos).

Los dos llevan el pre-commit con `pytest`: eso es del proyecto, no de gb.
"""

import argparse
import concurrent.futures
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ_GB = os.path.dirname(os.path.dirname(AQUI))
GUARDIA = os.path.join(os.path.dirname(RAIZ_GB), "guardia-mvp")
DESTINO = os.path.join(os.path.dirname(RAIZ_GB), "ab-gb", "v3")
SHIM = os.path.join(DESTINO, "_sin_gb")
BRAZOS = ("sin", "con")
TAREAS = ("cf01e4d", "1f3c86e", "a78fa09", "6cdc32b", "8491351", "6434843")

PROMPT = ("En este repositorio llega este ticket:\n\n%s\n\n"
          "Implementalo con sus tests, deja la suite del proyecto en verde y haz commit.")

HOOK_COMUN = "#!/bin/sh\npython -m pytest -q || exit 1\n"
HOOK_GB = "gb graph src --gate --since HEAD --brief || exit 1\ngb check --staged --brief\n"
AJUSTES_GB = json.dumps({"hooks": {"SessionStart": [{"matcher": "", "hooks": [
    {"type": "command", "command": "gb graph src --context", "timeout": 15}]}]}}, indent=2)


def _git(repo, *args, check=True):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", check=check)


def _repo(brazo, sha):
    return os.path.join(DESTINO, "%s-%s" % (brazo, sha))


def _tests_de(sha):
    """Los ficheros de test que la solucion real añadio o cambio."""
    nombres = _git(GUARDIA, "show", "--name-only", "--format=", sha).stdout.split()
    return [n for n in nombres if n.startswith("tests/") and n.endswith(".py")]


def _ley(sha):
    return _git(GUARDIA, "show", "%s:src/.gb-boundaries" % sha).stdout


def _shim():
    os.makedirs(SHIM, exist_ok=True)
    for nombre, texto in (("gb", "#!/bin/sh\necho \"gb: command not found\" >&2\nexit 127\n"),
                          ("gb.cmd", "@echo gb: command not found 1>&2\r\n@exit /b 127\r\n")):
        with open(os.path.join(SHIM, nombre), "w", encoding="utf-8", newline="") as fh:
            fh.write(texto)


def _sin_lineas_de_gb(ruta):
    if not os.path.isfile(ruta):
        return
    texto = open(ruta, encoding="utf-8").read()
    limpio = "\n".join(linea for linea in texto.split("\n")
                       if not re.search(r"\bgb\b|galaxy|gb-boundaries|gb:", linea))
    open(ruta, "w", encoding="utf-8").write(limpio)


def montar(tareas):
    _shim()
    for sha in tareas:
        for brazo in BRAZOS:
            repo = _repo(brazo, sha)
            if os.path.exists(repo):
                print("ya existe, no se toca: %s" % repo)
                continue
            subprocess.run(["git", "clone", "-q", GUARDIA, repo], check=True)
            _git(repo, "checkout", "-q", "-b", "tarea", sha + "^")
            _git(repo, "config", "user.email", "ab@local")
            _git(repo, "config", "user.name", "ab")
            open(os.path.join(repo, "src", ".gb-boundaries"), "w", encoding="utf-8").write(_ley(sha))
            os.makedirs(os.path.join(repo, ".githooks"), exist_ok=True)
            os.makedirs(os.path.join(repo, ".claude"), exist_ok=True)
            hook = HOOK_COMUN + (HOOK_GB if brazo == "con" else "")
            with open(os.path.join(repo, ".githooks", "pre-commit"), "w", encoding="utf-8",
                      newline="\n") as fh:
                fh.write(hook)
            open(os.path.join(repo, ".claude", "settings.json"), "w", encoding="utf-8").write(
                AJUSTES_GB if brazo == "con" else "{}\n")
            if brazo == "sin":
                for doc in ("AGENTS.md", "CLAUDE.md", "README.md", "check.sh"):
                    _sin_lineas_de_gb(os.path.join(repo, doc))
            _git(repo, "config", "core.hooksPath", ".githooks")
            _git(repo, "add", "-A")
            _git(repo, "commit", "-q", "--no-verify", "-m", "base del experimento")
            _git(repo, "tag", "base")
            print("montado: %s" % repo)


def _entorno(brazo):
    entorno = dict(os.environ)
    if brazo == "sin":
        entorno["GB_DISABLE"] = "1"
        entorno["PATH"] = SHIM + os.pathsep + entorno.get("PATH", "")
    else:
        entorno.pop("GB_DISABLE", None)
    return entorno


def _ticket(sha):
    return open(os.path.join(AQUI, "tareas", sha + ".md"), encoding="utf-8").read()


def construir(brazo, sha):
    repo = _repo(brazo, sha)
    salida = os.path.join(repo, ".ab.json")
    if os.path.exists(salida):
        return "%s-%s: ya hecho" % (brazo, sha)
    inicio = time.time()
    r = subprocess.run(
        [shutil.which("claude") or "claude", "-p", "--output-format", "json",
         "--permission-mode", "bypassPermissions", "--max-turns", "150"],
        input=PROMPT % _ticket(sha), cwd=repo, env=_entorno(brazo), capture_output=True,
        text=True, encoding="utf-8", errors="replace", timeout=5400)
    try:
        datos = json.loads(r.stdout)
    except ValueError:
        datos = {"error": "salida no json", "stdout": r.stdout[-2000:], "stderr": r.stderr[-2000:]}
    datos["rc"], datos["segundos"] = r.returncode, round(time.time() - inicio)
    json.dump(datos, open(salida, "w", encoding="utf-8"), indent=2)
    _git(repo, "add", "-A", check=False)
    _git(repo, "commit", "-q", "--no-verify", "-m", "foto final", check=False)
    return "%s-%s: rc=%s %ss %s$" % (brazo, sha, r.returncode, datos["segundos"],
                                     round(datos.get("total_cost_usd") or 0, 2))


def lanzar(tareas):
    for sha in tareas:
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            for linea in pool.map(construir, BRAZOS, (sha, sha)):
                print(linea, flush=True)


# --- juzgar ------------------------------------------------------------------------


def _juzga(src_de, sha):
    """Corre la suite ORIGINAL del padre + los tests de la solucion real sobre el
    `src/` de `src_de`. Devuelve {test: None si verde, texto si rojo}."""
    tmp = tempfile.mkdtemp()
    destino = os.path.join(tmp, "r")
    subprocess.run(["git", "clone", "-q", GUARDIA, destino], check=True)
    _git(destino, "checkout", "-q", sha + "^")
    shutil.rmtree(os.path.join(destino, "src"))
    shutil.copytree(os.path.join(src_de, "src"), os.path.join(destino, "src"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    for ruta in _tests_de(sha):
        texto = _git(GUARDIA, "show", "%s:%s" % (sha, ruta)).stdout
        os.makedirs(os.path.dirname(os.path.join(destino, ruta)), exist_ok=True)
        open(os.path.join(destino, ruta), "w", encoding="utf-8").write(texto)
    xml = os.path.join(tmp, "j.xml")
    subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                    "--junitxml", xml, "tests"], cwd=destino, capture_output=True, text=True,
                   env=dict(os.environ, GB_DISABLE="1"), timeout=900)
    import xml.etree.ElementTree as ET

    casos = {}
    for caso in ET.parse(xml).getroot().iter("testcase"):
        fallo = caso.find("failure")
        if fallo is None:
            fallo = caso.find("error")
        clave = "%s::%s" % (caso.get("classname"), caso.get("name"))
        casos[clave] = None if fallo is None else (fallo.get("message") or "")[:300]
    shutil.rmtree(tmp, ignore_errors=True)
    return casos


def _nuevos(sha):
    """Los tests que la solucion real AÑADIO (los que el ticket pide)."""
    diff = _git(GUARDIA, "show", "--format=", sha, "--", "tests").stdout
    return set(re.findall(r"^\+\s*def (test_\w+)", diff, re.M))


def _es_nuevo(clave, nuevos):
    return clave.split("::")[-1].split("[")[0] in nuevos


def _nuevos_en_verde(casos, nuevos):
    """Cuantos de los tests nuevos pasan. Un nuevo que NO aparece cuenta rojo: si su
    fichero no colecta (importa algo que no existe), pytest lo apunta como un solo
    error de modulo y el nombre del test ni sale — contarlo verde seria mentir."""
    verdes = set()
    for clave, fallo in casos.items():
        nombre = clave.split("::")[-1].split("[")[0]
        if nombre in nuevos:
            if fallo is not None:
                nuevos = nuevos - {nombre}
            else:
                verdes.add(nombre)
    return len(verdes & nuevos)


def validar(tareas):
    """La tarea sirve si sus tests nuevos caen en el padre y pasan en la solucion."""
    ok = True
    for sha in tareas:
        nuevos = _nuevos(sha)
        padre = tempfile.mkdtemp()
        subprocess.run(["git", "clone", "-q", GUARDIA, padre], check=True)
        _git(padre, "checkout", "-q", sha + "^")
        en_padre = _juzga(padre, sha)
        _git(padre, "checkout", "-q", sha)
        en_solucion = _juzga(padre, sha)
        shutil.rmtree(padre, ignore_errors=True)
        rojos_padre = len(nuevos) - _nuevos_en_verde(en_padre, nuevos)
        rojos_sol = [k for k, v in en_solucion.items() if v]
        sirve = rojos_padre > 0 and not rojos_sol and _nuevos_en_verde(en_solucion, nuevos) == len(nuevos)
        ok &= sirve
        print("%s %s: %d tests nuevos · rojos en el padre: %d · rojos en la solucion: %d %s"
              % ("OK " if sirve else "NO ", sha, len(nuevos), rojos_padre, len(rojos_sol),
                 rojos_sol[:3]))
    return 0 if ok else 1


def _cruces(repo, sha):
    sys.path.insert(0, os.path.join(RAIZ_GB, "src"))
    from galaxybrain import graph

    tmp = tempfile.mkdtemp()
    shutil.copytree(os.path.join(repo, "src"), os.path.join(tmp, "src"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    open(os.path.join(tmp, "src", ".gb-boundaries"), "w", encoding="utf-8").write(_ley(sha))
    rep = graph.analyze(os.path.join(tmp, "src"))
    shutil.rmtree(tmp, ignore_errors=True)
    return {(v["importer"], v["imported"]) for v in rep.get("violations") or []}


def _veces(sesion, patron):
    rutas = glob.glob(os.path.expanduser("~/.claude/projects/*/%s.jsonl" % (sesion or "-")))
    if not rutas:
        return None
    n = 0
    for linea in open(rutas[0], encoding="utf-8", errors="replace"):
        if '"tool_use"' not in linea:
            continue
        try:
            bloques = json.loads(linea).get("message", {}).get("content") or []
        except ValueError:
            continue
        n += sum(1 for b in bloques if isinstance(b, dict) and b.get("type") == "tool_use"
                 and re.search(patron, json.dumps(b.get("input", {}))))
    return n


def medir(tareas):
    filas = []
    for sha in tareas:
        nuevos = _nuevos(sha)
        base = _cruces(_repo("con", sha), sha) if os.path.exists(_repo("con", sha)) else set()
        for brazo in BRAZOS:
            repo = _repo(brazo, sha)
            ruta = os.path.join(repo, ".ab.json")
            if not os.path.exists(ruta):
                continue
            datos = json.load(open(ruta, encoding="utf-8"))
            casos = _juzga(repo, sha)
            nuevos_verdes = _nuevos_en_verde(casos, nuevos)
            nuevos_total = len(nuevos)
            regresiones = sum(1 for k, v in casos.items() if v and not _es_nuevo(k, nuevos))
            # Cruces NUEVOS: los del final que no estaban en la base (misma base en los dos).
            wt = tempfile.mkdtemp()
            _git(repo, "worktree", "add", "-f", "--detach", wt, "base", check=False)
            antes = _cruces(wt, sha)
            _git(repo, "worktree", "remove", "--force", wt, check=False)
            cruces = sorted(_cruces(repo, sha) - antes)
            sesion = datos.get("session_id")
            filas.append({
                "tarea": sha, "brazo": brazo,
                "nuevos": "%d/%d" % (nuevos_verdes, nuevos_total),
                "regresiones": regresiones, "cruces": len(cruces),
                "detalle_cruces": ["%s -> %s" % c for c in cruces][:5],
                "usd": round(datos.get("total_cost_usd") or 0, 2),
                "min": round((datos.get("segundos") or 0) / 60),
                "turnos": datos.get("num_turns"),
                "pytest": _veces(sesion, r"pytest"),
                "gb_usado": _veces(sesion, r"\bgb\b|galaxybrain"),
            })
        del base
    json.dump(filas, open(os.path.join(DESTINO, "resultados.json"), "w", encoding="utf-8"),
              indent=2)
    cab = ("tarea", "brazo", "nuevos", "regresiones", "cruces", "usd", "min", "turnos",
           "pytest", "gb_usado")
    print(" | ".join(cab))
    for f in filas:
        print(" | ".join(str(f[k]) for k in cab))
        if f["detalle_cruces"]:
            print("      cruces: %s" % "; ".join(f["detalle_cruces"]))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("accion", choices=("validar", "montar", "lanzar", "medir"))
    p.add_argument("tareas", nargs="*")
    a = p.parse_args()
    tareas = a.tareas or list(TAREAS)
    acciones = {"validar": validar, "montar": montar, "lanzar": lanzar, "medir": medir}
    sys.exit(acciones[a.accion](tareas) or 0)


if __name__ == "__main__":
    main()
