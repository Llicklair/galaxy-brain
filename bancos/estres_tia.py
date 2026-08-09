"""Estres de `gb tests` sobre codigo ajeno (guardia).

La pregunta: cuando gb dice "corre SOLO estos tests", ¿esta dentro el test que
de verdad se rompe? Un grafo al 40% de resolucion puede seleccionar de MENOS, y
seleccionar de menos es la unica forma en que este comando hace daño: da verde
teniendo el arbol roto.

Protocolo por objetivo:
  1. inyectar `raise RuntimeError` al principio de una funcion (rompe seguro)
  2. seleccion = gb tests --worktree
  3. rojo_sel  = pytest <seleccion>      -> ¿lo pilla?
  4. rojo_full = pytest                  -> ¿habia algo que pillar?
  5. rojo_full and not rojo_sel  ==>  FALSO VERDE
"""

import ast
import json
import os
import subprocess
import sys

WT = sys.argv[1]
# "vistos"     = simbolos CON llamantes resueltos (el caso comodo)
# "invisibles" = simbolos con CERO llamantes resueltos: el 60% que el AST no ve.
#                Si hay un falso verde en algun sitio, tiene que estar aqui.
MODO = sys.argv[2] if len(sys.argv) > 2 else "vistos"
TOPE = int(sys.argv[3]) if len(sys.argv) > 3 else 8
GB = [sys.executable, "-m", "galaxybrain.cli"]
ENTORNO = dict(os.environ, PYTHONPATH=os.path.join(WT, "src"))


def corre(cmd, timeout=600):
    p = subprocess.run(cmd, cwd=WT, capture_output=True, timeout=timeout, env=ENTORNO)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def limpia():
    subprocess.run(["git", "checkout", "HEAD", "--", "."], cwd=WT, capture_output=True)


def objetivos():
    """Funciones de src/ con al menos un llamante segun el propio grafo."""
    _, out, _ = corre(GB + ["symbols", "src", "--json"])
    d = json.loads(out)
    entrantes = {}
    for _origen, destino, tipo in (d.get("edges") or []):
        if tipo == "CALLS":
            entrantes[destino] = entrantes.get(destino, 0) + 1
    nodos = {n["qual"]: n for n in d["nodes"]}
    cands = []
    for qual, n in nodos.items():
        if n["kind"] not in ("function", "method"):
            continue
        if qual.startswith("tests.") or n["name"].startswith("_"):
            continue
        c = entrantes.get(qual, 0)
        if (c >= 1) if MODO == "vistos" else (c == 0):
            cands.append((c, qual, n["file"], n["line"]))
    # los invisibles no tienen orden natural: se barren todos hasta el tope
    cands.sort(reverse=(MODO == "vistos"))
    return cands[:TOPE]


def rompe(fichero, linea):
    """raise al inicio del cuerpo. Devuelve False si no se puede (deja limpio)."""
    # las rutas del grafo son relativas a la raiz analizada (aqui, src/)
    ruta = fichero if os.path.isabs(fichero) else os.path.join(WT, "src", fichero)
    src = open(ruta, encoding="utf-8").read()
    try:
        arbol = ast.parse(src)
    except SyntaxError:
        return False
    destino = None
    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)) and nodo.lineno == linea:
            destino = nodo
            break
    if destino is None or not destino.body:
        return False
    primera = destino.body[0]
    lineas = src.splitlines(keepends=True)
    sangria = " " * primera.col_offset
    lineas.insert(primera.lineno - 1, sangria + 'raise RuntimeError("ESTRES-TIA")\n')
    open(ruta, "w", encoding="utf-8", newline="").write("".join(lineas))
    return True


def ficheros_de(seleccion_json):
    d = json.loads(seleccion_json)
    for clave in ("tests", "selection", "seleccion", "files", "ficheros"):
        v = d.get(clave)
        if isinstance(v, list) and v:
            return [x if isinstance(x, str) else (x.get("file") or x.get("path")) for x in v]
    return []


print("objetivo".ljust(46), "sel", "rojo_sel", "rojo_full", "veredicto")
print("-" * 92)
filas = []
for _llamantes, qual, fichero, linea in objetivos():
    limpia()
    if not rompe(fichero, linea):
        continue
    rc, out, err = corre(GB + ["tests", "--worktree", "--json"])
    sel = ficheros_de(out) if rc == 0 and out.strip().startswith("{") else None
    if sel is None:
        print("%-46s  (gb tests no devolvio json: %s)" % (qual[:46], (err or out)[:40]))
        continue
    if sel:
        rc_sel, o1, e1 = corre([sys.executable, "-m", "pytest", "-q", *sel])
        rojo_sel = rc_sel != 0
    else:
        rojo_sel = False           # seleccion vacia = "no corras nada"
    rc_full, o2, e2 = corre([sys.executable, "-m", "pytest", "-q"])
    rojo_full = rc_full != 0

    if rojo_full and not rojo_sel:
        v = "*** FALSO VERDE ***"
    elif rojo_full and rojo_sel:
        v = "ok (lo pilla)"
    elif not rojo_full:
        v = "sin cobertura (nadie lo prueba)"
    else:
        v = "?"
    filas.append((qual, len(sel), rojo_sel, rojo_full, v))
    print("%-46s %3d   %-8s %-9s %s" % (qual[:46], len(sel), rojo_sel, rojo_full, v))

limpia()
print("-" * 92)
falsos = [f for f in filas if f[4].startswith("***")]
print("total %d objetivos · %d falsos verdes · %d sin cobertura"
      % (len(filas), len(falsos), len([f for f in filas if f[4].startswith("sin")])))
