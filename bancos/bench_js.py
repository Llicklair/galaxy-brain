"""Criterio 6: `gb tests` sobre JS, 0 falsos verdes. El liston que decide.

Mismo protocolo que las 42 roturas de Python, sobre un proyecto JS de verdad:
romper un simbolo, preguntar a gb que correr, correr SOLO eso, correr todo, y
si la suite entera se pone roja y la seleccion no, es un FALSO VERDE.

Runner: `node --test`, que viene DENTRO de Node. Sin npm install, sin vitest,
sin red — el banco no puede depender de instalar medio ecosistema, y un rojo de
verdad vale mas que una comprobacion estructural contra el mismo grafo que se
esta juzgando (eso seria circular).
"""

import json
import os
import shutil
import subprocess
import sys

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bench-js-tia")
GB = [sys.executable, "-m", "galaxybrain.cli"]

#: 6 modulos con dependencias reales entre si, y 6 ficheros de test que los
#: cubren por caminos distintos: unos directos, otros a traves de un tercero.
#: La gracia esta en los indirectos — ahi es donde una seleccion pobre falla.
MODULOS = {
    "iva.js": "export function iva() { return 0.21; }\n",
    "carrito.js":
        'import { iva } from "./iva.js";\n'
        "export function subtotal(xs) { let t = 0; for (const x of xs) t += x; return t; }\n"
        "export function total(xs) { return subtotal(xs) * (1 + iva()); }\n",
    "descuento.js":
        'import { total } from "./carrito.js";\n'
        "export function conDescuento(xs, d) { return total(xs) * (1 - d); }\n",
    "factura.js":
        'import { conDescuento } from "./descuento.js";\n'
        "export function emitir(xs) { return conDescuento(xs, 0.1); }\n",
    "informe.js":
        'import { emitir } from "./factura.js";\n'
        "export function linea(xs) { return `TOTAL ${emitir(xs).toFixed(2)}`; }\n",
    "texto.js": "export function mayus(s) { return s.toUpperCase(); }\n",
}

TESTS = {
    "iva.test.js": ('import { iva } from "../src/iva.js";', "iva()", "0.21"),
    "carrito.test.js": ('import { total } from "../src/carrito.js";', "total([10])", "12.1"),
    "descuento.test.js": ('import { conDescuento } from "../src/descuento.js";',
                          "conDescuento([10], 0.1)", "10.89"),
    "factura.test.js": ('import { emitir } from "../src/factura.js";', "emitir([10])", "10.89"),
    "informe.test.js": ('import { linea } from "../src/informe.js";', "linea([10])",
                        '"TOTAL 10.89"'),
    "texto.test.js": ('import { mayus } from "../src/texto.js";', 'mayus("a")', '"A"'),
}


def genera():
    shutil.rmtree(RAIZ, ignore_errors=True)
    os.makedirs(os.path.join(RAIZ, "src"))
    os.makedirs(os.path.join(RAIZ, "test"))
    for nombre, cuerpo in MODULOS.items():
        open(os.path.join(RAIZ, "src", nombre), "w", encoding="utf-8").write(cuerpo)
    for nombre, (imp, expr, esperado) in TESTS.items():
        open(os.path.join(RAIZ, "test", nombre), "w", encoding="utf-8").write(
            'import { test } from "node:test";\n'
            'import assert from "node:assert";\n'
            "%s\n"
            'test("%s", () => { assert.deepStrictEqual(%s, %s); });\n'
            % (imp, nombre, expr, esperado)
        )
    open(os.path.join(RAIZ, "package.json"), "w", encoding="utf-8").write(
        '{ "name": "bench", "type": "module" }\n')
    subprocess.run(["git", "init", "-q"], cwd=RAIZ, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=RAIZ, capture_output=True)
    subprocess.run(["git", "-c", "user.email=b@b", "-c", "user.name=b", "commit", "-qm", "init"],
                   cwd=RAIZ, capture_output=True)


def corre(cmd, cwd=RAIZ, timeout=300):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, timeout=timeout)
    return p.returncode, p.stdout.decode("utf-8", "replace")


NODE = shutil.which("node")


def node_test(ficheros=None):
    """rc de `node --test`. Sin ficheros, la suite entera."""
    cmd = [NODE, "--test"] + (list(ficheros) if ficheros else ["test/"])
    return corre(cmd)[0] != 0


def limpia():
    subprocess.run(["git", "checkout", "HEAD", "--", "."], cwd=RAIZ, capture_output=True)


def rompe(modulo, funcion):
    """Rotura DURA: la funcion lanza. Cualquier test que pase por ahi lo nota."""
    ruta = os.path.join(RAIZ, "src", modulo)
    src = open(ruta, encoding="utf-8").read()
    marca = "export function %s(" % funcion
    i = src.index(marca)
    j = src.index("{", i) + 1
    open(ruta, "w", encoding="utf-8", newline="").write(
        src[:j] + ' throw new Error("ESTRES"); ' + src[j:])


def seleccion():
    """(ficheros, todo, error). `todo=True` con lista vacia significa CORRELO
    TODO, no 'no corras nada' — leerlo mal fabrica falsos verdes que no existen,
    y me paso en la primera tirada de este banco."""
    rc, out = corre(GB + ["tests", "--worktree", "--json"])
    if not out.strip().startswith("{"):
        return None, False, "gb tests no devolvio json"
    d = json.loads(out)
    if d.get("range_error"):
        return None, False, d["range_error"]
    ficheros = [x if isinstance(x, str) else (x.get("file") or x.get("path"))
                for x in (d.get("tests") or [])]
    return ficheros, bool(d.get("todo")), None


if not NODE:
    print("node no esta instalado: el banco no puede dar rojos reales")
    raise SystemExit(1)

genera()
print("proyecto: %d modulos, %d ficheros de test · runner: node --test\n"
      % (len(MODULOS), len(TESTS)))
print("%-26s %4s %9s %10s  %s" % ("rotura", "sel", "rojo_sel", "rojo_full", "veredicto"))
print("-" * 84)

OBJETIVOS = [("iva.js", "iva"), ("carrito.js", "subtotal"), ("carrito.js", "total"),
             ("descuento.js", "conDescuento"), ("factura.js", "emitir"),
             ("informe.js", "linea"), ("texto.js", "mayus")]

falsos = ahorro = 0
for modulo, funcion in OBJETIVOS:
    limpia()
    rompe(modulo, funcion)
    sel, todo, error = seleccion()
    if error:
        print("%-26s  ERROR: %s" % ("%s:%s" % (modulo, funcion), error[:44]))
        continue
    rojo_sel = node_test(sel) if sel else node_test()   # sin lista, la suite entera
    rojo_full = node_test()
    if rojo_full and not rojo_sel:
        v = "*** FALSO VERDE ***"
        falsos += 1
    elif rojo_full:
        v = "ok (lo pilla)%s" % (" [cayo a todo]" if todo else "")
        ahorro += len(TESTS) - (len(sel) if sel and not todo else len(TESTS))
    else:
        v = "sin cobertura"
    print("%-26s %4d %9s %10s  %s"
          % ("%s:%s" % (modulo, funcion), len(sel), rojo_sel, rojo_full, v))

limpia()
print("-" * 84)
print("%d roturas · %d FALSOS VERDES · ahorro medio %.0f%% de la suite"
      % (len(OBJETIVOS), falsos, 100.0 * ahorro / (len(OBJETIVOS) * len(TESTS))))
