"""Un agente sobre un worktree, con el mapa mirándole. UN comando.

    python bucle/agente.py "arregla X"

Lo que hacía falta teclear antes para llegar aquí: crear el worktree a mano,
escribir un lanzador que teee el stdout a `<worktree>.consola.log`, arrancar el
watch, y buscar la ruta del mapa. Cinco pasos y un script desechable cada vez —
reportado en uso real (8-ago): «hemos gastado demasiados prompts hasta llegar
aquí, esto debería ser más ágil». La norma va en el defecto: lo correcto es lo
que sale sin escribir nada.

Vive en `bucle/` y no en `gb` a propósito: gb PROVEE (el grafo, la actividad
derivada, el mapa), no orquesta (ARCHITECTURE regla 4). Esto consume gb por CLI
como lo haría cualquier motor externo.

NUNCA mergea: al terminar deja el diff y el worktree, y quien decide es el
humano (regla de trabajo: los bucles no mergean).
"""

import argparse
import io
import json
import os
import re
import subprocess
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _corre(cmd, cwd=None, timeout=None):
    entorno = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    try:
        proc = subprocess.run(cmd, cwd=cwd or RAIZ, capture_output=True,
                              timeout=timeout, env=entorno)
    except (OSError, subprocess.TimeoutExpired) as error:
        return 1, "", str(error)
    return (proc.returncode,
            proc.stdout.decode("utf-8", "replace"),
            proc.stderr.decode("utf-8", "replace"))


def _nombre_por_defecto(tarea):
    """Un nombre legible derivado de la tarea: el worktree se llama como lo que
    hace, que es lo que se va a leer en la tarjeta del mapa."""
    palabras = re.findall(r"[a-zA-Z0-9_]+", tarea.lower())[:3]
    return "-".join(palabras) or "agente"


def log_consola(worktree):
    """La convencion que `gb` lee del disco para pintar la terminal del agente:
    al lado del worktree, no dentro (dentro ensuciaria su git status)."""
    return os.path.normpath(worktree).rstrip("\\/") + ".consola.log"


def prepara_worktree(nombre):
    ruta = os.path.join(RAIZ, ".claude", "worktrees", nombre)
    _corre(["git", "worktree", "remove", "--force", ruta])
    try:
        os.remove(log_consola(ruta))          # consola fresca por tirada
    except OSError:
        pass
    rc, _salida, err = _corre(["git", "worktree", "add", "--detach", ruta, "HEAD"])
    if rc != 0:
        raise RuntimeError("no pude crear el worktree: %s" % err.strip()[:200])
    return ruta


def asegura_mapa():
    """Un watch vivo sobre el repo, si no lo hay. Sin esto la actividad existe
    en disco pero nadie la pinta — el fallo que costo tres tandas invisibles."""
    destino = os.path.join(RAIZ, "mapa.html")
    _corre([sys.executable, "-m", "galaxybrain.cli", "symbols", "--html", destino,
            "--watch", "--fondo", "--refresco", "3"], timeout=60)
    return destino


def despacha(tarea, worktree, modelo, timeout):
    """Lanza el agente y teea su consola en vivo. Devuelve su ultimo mensaje."""
    entorno = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    proc = subprocess.Popen(
        ["claude", "-p", tarea, "--model", modelo, "--permission-mode", "acceptEdits",
         "--output-format", "stream-json", "--verbose"],
        cwd=worktree, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=entorno)
    ultimo = ""
    with io.open(log_consola(worktree), "a", encoding="utf-8") as consola:
        consola.write("[%s] $ %s\n" % (time.strftime("%H:%M:%S"), os.path.basename(worktree)))
        consola.flush()
        for cruda in proc.stdout:
            try:
                evento = json.loads(cruda.decode("utf-8", "replace"))
            except ValueError:
                continue
            for bloque in (evento.get("message") or {}).get("content") or []:
                texto = None
                if bloque.get("type") == "tool_use":
                    entrada = bloque.get("input") or {}
                    pista = entrada.get("file_path") or entrada.get("pattern") or \
                        entrada.get("command") or ""
                    texto = "%s %s" % (bloque.get("name"), str(pista).split("\\")[-1][:64])
                elif bloque.get("type") == "text" and bloque.get("text", "").strip():
                    texto = bloque["text"].strip().splitlines()[0][:96]
                    ultimo = bloque["text"].strip()
                if texto:
                    linea = "[%s] %s" % (time.strftime("%H:%M:%S"), texto)
                    consola.write(linea + "\n")
                    consola.flush()
                    print("  " + texto, flush=True)
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
    return ultimo


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="un agente en un worktree, con el mapa mirandole")
    parser.add_argument("tarea", help="que tiene que hacer")
    parser.add_argument("--nombre", help="nombre del worktree (por defecto, de la tarea)")
    parser.add_argument("--modelo", default="opus")
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--sin-mapa", action="store_true",
                        help="no asegurar el watch (por defecto se arranca si falta)")
    args = parser.parse_args(argv)

    nombre = args.nombre or _nombre_por_defecto(args.tarea)
    worktree = prepara_worktree(nombre)
    print("worktree : %s" % worktree)
    if not args.sin_mapa:
        destino = asegura_mapa()
        print("mapa     : file:///%s" % destino.replace("\\", "/"))
    print("consola  : %s" % log_consola(worktree))
    print("-- el agente empieza; su tarjeta aparece en el mapa al primer cambio --\n",
          flush=True)

    despacha(args.tarea, worktree, args.modelo, args.timeout)

    rc, diff, _err = _corre(["git", "diff", "--stat", "HEAD"], cwd=worktree)
    print("\n== lo que dejo (SIN commitear, SIN mergear) ==")
    print(diff.strip() or "(nada)")
    print("\nrevisalo con:  git -C %s diff" % worktree)
    print("y cuando decidas TU:  git -C %s diff | git apply -" % worktree)
    return 0


if __name__ == "__main__":
    sys.exit(main())
