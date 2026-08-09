"""Estres 2: roturas SUTILES. La tanda anterior inyectaba `raise` — una bomba
que cualquier test que pase por ahi nota. Esta cambia el SIGNIFICADO sin romper
nada: un `==` que pasa a `!=`, un `True` que pasa a `False`, un `<` que pasa a
`<=`, un `+` que pasa a `-`. El codigo sigue corriendo; solo responde mal.

Dos preguntas distintas y las dos importan:

  1. sobre gb      -> si la suite entera se pone roja, ¿esta el rojo DENTRO de
                      la seleccion de `gb tests`? (falso verde = seleccion de menos)
  2. sobre el repo -> si NADIE se pone rojo, el mutante SOBREVIVE: hueco de la
                      suite de guardia, no de gb. Se cuenta aparte.

CIRUGIA DE TEXTO, no `ast.unparse`: reescribir el fichero entero cambiaria TODAS
las lineas, el diff seria total, `gb tests` seleccionaria todo y el experimento
se aprobaria solo. Aqui se toca el span exacto del operador: el diff es de un
caracter, que es justo el caso dificil.

mutmut no corre en Windows nativo, de ahi el bicho a mano.
"""

import ast
import json
import os
import random
import subprocess
import sys

WT = sys.argv[1]
TOPE = int(sys.argv[2]) if len(sys.argv) > 2 else 20
GB = [sys.executable, "-m", "galaxybrain.cli"]
ENTORNO = dict(os.environ, PYTHONPATH=os.path.join(WT, "src"))
random.seed(20260808)          # reproducible: sin esto la tanda no se puede repetir

#: Orden IMPORTANTE: `<=` antes que `<`, o se mutaria la mitad del operador.
PARES = [("==", "!="), ("!=", "=="), ("<=", "<"), (">=", ">"), ("<", "<="), (">", ">="),
         ("//", "*"), ("+", "-"), ("-", "+"), ("*", "//")]


def corre(cmd, timeout=900):
    p = subprocess.run(cmd, cwd=WT, capture_output=True, timeout=timeout, env=ENTORNO)
    return p.returncode, p.stdout.decode("utf-8", "replace")


def limpia():
    subprocess.run(["git", "checkout", "HEAD", "--", "."], cwd=WT, capture_output=True)


def _span_operador(izq, der):
    """El hueco de texto entre dos hijos: ahi vive el operador. Solo en una
    linea — un operador partido en dos lineas se salta, no se adivina."""
    if izq.end_lineno != der.lineno:
        return None
    return (izq.end_lineno, izq.end_col_offset, der.col_offset)


def candidatas(ruta):
    """(descripcion, linea, col_ini, col_fin, texto_nuevo) por cada mutacion."""
    src = open(ruta, encoding="utf-8").read()
    try:
        arbol = ast.parse(src)
    except SyntaxError:
        return []
    lineas = src.splitlines()
    fuera = []

    def _op(span, etiqueta):
        if span is None:
            return
        ln, a, b = span
        trozo = lineas[ln - 1][a:b]
        for viejo, nuevo in PARES:
            if viejo in trozo:
                i = trozo.index(viejo)
                fuera.append(("%s %s->%s" % (etiqueta, viejo, nuevo), ln,
                              a + i, a + i + len(viejo), nuevo))
                return

    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Compare) and len(nodo.ops) == 1:
            _op(_span_operador(nodo.left, nodo.comparators[0]), "cmp")
        elif isinstance(nodo, ast.BinOp):
            _op(_span_operador(nodo.left, nodo.right), "bin")
        elif isinstance(nodo, ast.Constant) and nodo.value in (True, False) \
                and isinstance(nodo.value, bool) and nodo.lineno == nodo.end_lineno:
            fuera.append(("%s->%s" % (nodo.value, not nodo.value), nodo.lineno,
                          nodo.col_offset, nodo.end_col_offset, str(not nodo.value)))
    return fuera


def aplica(ruta, linea, a, b, nuevo):
    src = open(ruta, encoding="utf-8").read()
    lineas = src.splitlines(keepends=True)
    cruda = lineas[linea - 1]
    fin = len(cruda.rstrip("\r\n"))
    if b > fin:
        return False
    lineas[linea - 1] = cruda[:a] + nuevo + cruda[b:]
    texto = "".join(lineas)
    try:
        ast.parse(texto)                      # una mutacion que no compila no es una mutacion
    except SyntaxError:
        return False
    open(ruta, "w", encoding="utf-8", newline="").write(texto)
    return True


# --- el barrido -------------------------------------------------------------

fuentes = []
for dirpath, _d, files in os.walk(os.path.join(WT, "src")):
    for f in files:
        if f.endswith(".py") and not f.startswith("__"):
            fuentes.append(os.path.join(dirpath, f))

todas = [(r, *c) for r in fuentes for c in candidatas(r)]
random.shuffle(todas)
print("universo de mutaciones posibles: %d\n" % len(todas))

print("%-26s %-16s %4s %4s %8s %9s  %s"
      % ("fichero", "mutacion", "lin", "sel", "rojo_sel", "rojo_full", "veredicto"))
print("-" * 104)
falsos = superv = matados = hechas = 0
supervivientes = []
for ruta, desc, linea, a, b, nuevo in todas:
    if hechas >= TOPE:
        break
    limpia()
    if not aplica(ruta, linea, a, b, nuevo):
        continue
    rc, out = corre(GB + ["tests", "--worktree", "--json"])
    try:
        d = json.loads(out)
    except Exception:
        continue
    sel = [x if isinstance(x, str) else (x.get("file") or x.get("path"))
           for x in (d.get("tests") or d.get("files") or [])]
    hechas += 1
    rojo_sel = (corre([sys.executable, "-m", "pytest", "-q", *sel])[0] != 0) if sel else False
    rojo_full = corre([sys.executable, "-m", "pytest", "-q"])[0] != 0

    if rojo_full and not rojo_sel:
        v, falsos = "*** FALSO VERDE (gb) ***", falsos + 1
    elif rojo_full:
        v, matados = "mutante muerto", matados + 1
    else:
        v, superv = "SOBREVIVE (hueco de guardia)", superv + 1
        supervivientes.append("%s:%d  %s" % (os.path.basename(ruta), linea, desc))
    print("%-26s %-16s %4d %4d %8s %9s  %s"
          % (os.path.basename(ruta)[:26], desc, linea, len(sel), rojo_sel, rojo_full, v))

limpia()
print("-" * 104)
print("%d mutantes · %d muertos · %d SOBREVIVEN · %d FALSOS VERDES (gb)"
      % (hechas, matados, superv, falsos))
if supervivientes:
    print("\nsupervivientes (lo que la suite de guardia no nota):")
    for s in supervivientes:
        print("  " + s)
