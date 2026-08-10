"""Criterio 6 en Go: `gb tests` sobre un proyecto MULTIPAQUETE, 0 falsos verdes.

Mismo protocolo que JS y Rust. Lo que Go aporta de nuevo es el caso duro de
verdad: sus llamadas entre paquetes son CUALIFICADAS (`iva.Iva()`), que es como
llaman tambien Java, C#, Kotlin y Scala. Si el motor no las resuelve, el grafo
de llamadas de media tabla se queda vacio.

Se usa layout multipaquete a proposito —un directorio por paquete— y no un
paquete plano: un banco que evita el caso dificil mide su propia comodidad.

Runner: `go test ./...`, que viene con Go. Para una seleccion, `go test ./pkg/`.
"""

import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import estricto  # noqa: E402  (el banco es un script, no un paquete)

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bench-go")
GB = [sys.executable, "-m", "galaxybrain.cli"]
GO = shutil.which("go") or r"C:\Program Files\Go\bin\go.exe"

#: paquete -> (fuente, import extra). La cadena: iva <- carrito <- descuento <-
#: factura <- informe; texto queda aislado como control.
PAQUETES = {
    "iva": 'package iva\n\nfunc Iva() float64 { return 0.21 }\n',
    "carrito": (
        'package carrito\n\nimport "bench/iva"\n\n'
        "func Subtotal(xs []float64) float64 { t := 0.0; for _, x := range xs { t += x }; return t }\n\n"
        "func Total(xs []float64) float64 { return Subtotal(xs) * (1 + iva.Iva()) }\n"),
    "descuento": (
        'package descuento\n\nimport "bench/carrito"\n\n'
        "func ConDescuento(xs []float64, d float64) float64 { return carrito.Total(xs) * (1 - d) }\n"),
    "factura": (
        'package factura\n\nimport "bench/descuento"\n\n'
        "func Emitir(xs []float64) float64 { return descuento.ConDescuento(xs, 0.1) }\n"),
    "informe": (
        'package informe\n\nimport (\n\t"fmt"\n\t"bench/factura"\n)\n\n'
        'func Linea(xs []float64) string { v := factura.Emitir(xs); return fmt.Sprintf("TOTAL %.2f", v) }\n'),
    "texto": 'package texto\n\nimport "strings"\n\nfunc Mayus(s string) string { return strings.ToUpper(s) }\n',
}

TESTS = {
    "iva": ('package iva\n\nimport "testing"\n\n'
            "func TestIva(t *testing.T) { v := Iva(); if v <= 0 { t.Fatal(\"mal\") } }\n"),
    "carrito": ('package carrito\n\nimport "testing"\n\n'
                "func TestTotal(t *testing.T) { v := Total([]float64{10}); if v <= 0 { t.Fatal(\"mal\") } }\n"),
    "descuento": ('package descuento\n\nimport "testing"\n\n'
                  "func TestConDescuento(t *testing.T) { v := ConDescuento([]float64{10}, 0.1); if v <= 0 { t.Fatal(\"mal\") } }\n"),
    "factura": ('package factura\n\nimport "testing"\n\n'
                "func TestEmitir(t *testing.T) { v := Emitir([]float64{10}); if v <= 0 { t.Fatal(\"mal\") } }\n"),
    "informe": ('package informe\n\nimport "testing"\n\n'
                "func TestLinea(t *testing.T) { v := Linea([]float64{10}); if len(v) == 0 { t.Fatal(\"mal\") } }\n"),
    "texto": ('package texto\n\nimport "testing"\n\n'
              "func TestMayus(t *testing.T) { v := Mayus(\"a\"); if v != \"A\" { t.Fatal(\"mal\") } }\n"),
}


def genera():
    # `ignore_errors` puede dejar el directorio a medio borrar (Windows bloquea
    # ficheros), y un `makedirs` sin exist_ok revienta ahi dejando el banco VACIO
    # — que es como este banco reporto "0 nodos" en una tirada que no era suya.
    shutil.rmtree(RAIZ, ignore_errors=True)
    os.makedirs(RAIZ, exist_ok=True)
    open(os.path.join(RAIZ, "go.mod"), "w", encoding="utf-8").write("module bench\n\ngo 1.24\n")
    for pkg, fuente in PAQUETES.items():
        d = os.path.join(RAIZ, pkg)
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, pkg + ".go"), "w", encoding="utf-8").write(fuente)
        open(os.path.join(d, pkg + "_test.go"), "w", encoding="utf-8").write(TESTS[pkg])
    subprocess.run(["git", "init", "-q"], cwd=RAIZ, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=RAIZ, capture_output=True)
    subprocess.run(["git", "-c", "user.email=b@b", "-c", "user.name=b", "commit", "-qm", "init"],
                   cwd=RAIZ, capture_output=True)


def corre(cmd, timeout=600):
    p = subprocess.run(cmd, cwd=RAIZ, capture_output=True, timeout=timeout)
    return p.returncode, p.stdout.decode("utf-8", "replace")


def go_test(ficheros=None):
    if ficheros is None:
        return corre([GO, "test", "./..."])[0] != 0
    # de `iva/iva_test.go` a `./iva/`, que es lo que go test recibe
    paquetes = sorted({"./" + os.path.dirname(f).replace("\\", "/") + "/" for f in ficheros})
    return corre([GO, "test"] + paquetes)[0] != 0


def limpia():
    subprocess.run(["git", "checkout", "HEAD", "--", "."], cwd=RAIZ, capture_output=True)


def rompe(pkg, funcion):
    ruta = os.path.join(RAIZ, pkg, pkg + ".go")
    src = open(ruta, encoding="utf-8").read()
    i = src.index("func %s(" % funcion)
    j = src.index("{", i) + 1
    open(ruta, "w", encoding="utf-8", newline="").write(
        src[:j] + ' panic("ESTRES"); ' + src[j:])


def seleccion():
    rc, out = corre(GB + ["tests", "--worktree", "--json"])
    if not out.strip().startswith("{"):
        return None, False, "gb tests no devolvio json"
    d = json.loads(out)
    if d.get("range_error"):
        return None, False, d["range_error"]
    return list(d.get("tests") or []), bool(d.get("todo")), None


genera()
rc, _ = corre([GO, "version"])
if rc != 0:
    print("go no ejecuta")
    raise SystemExit(1)
if go_test():
    print("ERROR: la suite base no esta verde")
    raise SystemExit(1)

print("proyecto Go: %d paquetes, %d tests · llamadas CUALIFICADAS entre paquetes\n"
      % (len(PAQUETES), len(TESTS)))
print("%-26s %4s %9s %10s  %s" % ("rotura", "sel", "rojo_sel", "rojo_full", "veredicto"))
print("-" * 84)

OBJETIVOS = [("iva", "Iva"), ("carrito", "Subtotal"), ("carrito", "Total"),
             ("descuento", "ConDescuento"), ("factura", "Emitir"),
             ("informe", "Linea"), ("texto", "Mayus")]

falsos = ahorro = con_fuga = medidas = 0
for pkg, funcion in OBJETIVOS:
    limpia()
    rompe(pkg, funcion)
    sel, todo, error = seleccion()
    if error:
        print("%-26s  ERROR: %s" % ("%s.%s" % (pkg, funcion), error[:44]))
        continue
    rojo_sel = go_test(sel) if sel and not todo else go_test()
    # Criterio ESTRICTO: la seleccion tiene que contener TODOS los
    # rojos. Un banco pequenio tapa la fuga con que otro caiga rojo.
    rojos, fugados = estricto.fuga(
        sel, todo, ["%s/%s_test.go" % (k, k) for k in TESTS], go_test)
    rojo_full = bool(rojos)
    if rojo_full and not rojo_sel:
        v, falsos = "*** FALSO VERDE ***", falsos + 1
    elif rojo_full:
        v = "ok (lo pilla)%s" % (" [cayo a todo]" if todo else "")
        ahorro += len(TESTS) - (len(sel) if sel and not todo else len(TESTS))
    else:
        v = "sin cobertura"
    if not todo:
        medidas += 1
    if fugados:
        con_fuga += 1
    print("%-26s %4d %9s %10s  %s%s"
          % ("%s.%s" % (pkg, funcion), len(sel), rojo_sel, rojo_full, v,
             estricto.linea_extra(rojos, fugados)))

limpia()
print("-" * 84)
print(estricto.resumen(len(OBJETIVOS), falsos, con_fuga,
                       100.0 * ahorro / (len(OBJETIVOS) * len(TESTS)), medidas))
