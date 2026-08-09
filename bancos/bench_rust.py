"""Criterio 6 en un SEGUNDO lenguaje: `gb tests` sobre Rust, 0 falsos verdes.

Mismo protocolo que el banco de JS, y por el mismo motivo: romper un simbolo,
preguntar a gb que correr, correr SOLO eso, correr todo, y si la suite entera se
pone roja y la seleccion no, es un falso verde.

Runner: `cargo test --test <nombre>`, que trae Rust de serie. Se eligio Rust y no
Go porque Go NO esta instalado en esta maquina y una instalacion es maquinaria
pesada que se pide aparte — mientras que cargo ya estaba. El valor es el mismo:
un segundo lenguaje con rojos y verdes de verdad, no una comprobacion
estructural contra el mismo grafo que se esta juzgando.

Los tests son de INTEGRACION (tests/*.rs), que es el analogo limpio del fichero
de test: cada uno es un binario propio y `cargo test --test x` corre solo ese.
"""

import json
import os
import shutil
import subprocess
import sys

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bench-rust")
GB = [sys.executable, "-m", "galaxybrain.cli"]
CARGO = shutil.which("cargo")

MODULOS = {
    "iva.rs": "pub fn iva() -> f64 { 0.21 }\n",
    "carrito.rs":
        "use crate::iva::iva;\n\n"
        "pub fn subtotal(xs: &[f64]) -> f64 { let mut t = 0.0; for x in xs { t += x; } t }\n\n"
        "pub fn total(xs: &[f64]) -> f64 { subtotal(xs) * (1.0 + iva()) }\n",
    "descuento.rs":
        "use crate::carrito::total;\n\n"
        "pub fn con_descuento(xs: &[f64], d: f64) -> f64 { total(xs) * (1.0 - d) }\n",
    "factura.rs":
        "use crate::descuento::con_descuento;\n\n"
        "pub fn emitir(xs: &[f64]) -> f64 { con_descuento(xs, 0.1) }\n",
    "informe.rs":
        "use crate::factura::emitir;\n\n"
        "pub fn linea(xs: &[f64]) -> String { format!(\"TOTAL {:.2}\", emitir(xs)) }\n",
    "texto.rs": "pub fn mayus(s: &str) -> String { s.to_uppercase() }\n",
}

#: (fichero de test, import, expresion) — se usa `use` + llamada PELADA porque es
#: lo idiomatico en Rust y porque una llamada con ruta (`a::b::c()`) no es un
#: identificador: caeria en `atributo-de-variable`, igual que en Python.
#: `assert_eq!(f(..), esperado)` es la forma idiomatica de Rust y la que el
#: motor ve (`$M!($FN($$$), $$$)`). `assert!(f() > 0)` NO se ve —el cuerpo del
#: macro es un arbol de tokens— y esta declarado en las carencias del lenguaje.
#: DOS estilos, porque el resultado depende de como este escrito el test y
#: elegir el favorable seria amañar el banco:
#:   "dentro"  -> la llamada va anidada en una expresion DENTRO del macro
#:                (`assert!(f(x) > 0.0)`): invisible, el cuerpo de un macro es un
#:                arbol de tokens.
#:   "ligado"  -> la llamada se liga antes (`let v = f(x); assert!(v > 0.0);`),
#:                que es igual de idiomatico y SI se ve.
ESTILO = os.environ.get("ESTILO", "ligado")

_CASOS = {
    "iva.rs": ("use bench::iva::iva;", "iva()"),
    "carrito.rs": ("use bench::carrito::total;", "total(&[10.0])"),
    "descuento.rs": ("use bench::descuento::con_descuento;", "con_descuento(&[10.0], 0.1)"),
    "factura.rs": ("use bench::factura::emitir;", "emitir(&[10.0])"),
    "informe.rs": ("use bench::informe::linea;", "linea(&[10.0])"),
    "texto.rs": ("use bench::texto::mayus;", 'mayus("a")'),
}

# Lo UNICO que cambia entre los dos estilos es si la llamada esta dentro del
# macro o ligada antes. Misma asercion, mismo tipo, mismo comportamiento ante un
# panic — asi la diferencia que mida el banco es la del motor, no la del test.
TESTS = {}
for _f, (_imp, _expr) in _CASOS.items():
    if ESTILO == "ligado":
        cuerpo = 'let v = %s;\n    assert!(format!("{:?}", v).len() > 0);' % _expr
    else:
        cuerpo = 'assert!(format!("{:?}", %s).len() > 0);' % _expr
    TESTS[_f] = (_imp, cuerpo)


def genera():
    shutil.rmtree(RAIZ, ignore_errors=True)
    os.makedirs(os.path.join(RAIZ, "src"))
    os.makedirs(os.path.join(RAIZ, "tests"))
    open(os.path.join(RAIZ, "Cargo.toml"), "w", encoding="utf-8").write(
        '[package]\nname = "bench"\nversion = "0.1.0"\nedition = "2021"\n\n[dependencies]\n')
    for nombre, cuerpo in MODULOS.items():
        open(os.path.join(RAIZ, "src", nombre), "w", encoding="utf-8").write(cuerpo)
    open(os.path.join(RAIZ, "src", "lib.rs"), "w", encoding="utf-8").write(
        "".join("pub mod %s;\n" % n[:-3] for n in MODULOS))
    for nombre, (imp, expr) in TESTS.items():
        open(os.path.join(RAIZ, "tests", nombre), "w", encoding="utf-8").write(
            "%s\n\n#[test]\nfn comprueba() {\n    %s\n}\n" % (imp, expr))
    # `target/` ANTES del add: cargo deja ahi miles de artefactos y en Windows
    # queda con ficheros bloqueados, asi que al regenerar el banco `rmtree` no lo
    # borra entero (ignore_errors), el `add` se atasca y el commit se queda sin
    # nada — que es como este banco dio 0% de ahorro con "no se pudo leer el
    # diff": el repo no tenia HEAD y `gb tests` caia, correctamente, a todo.
    open(os.path.join(RAIZ, ".gitignore"), "w", encoding="utf-8").write("target/\nCargo.lock\n")
    subprocess.run(["git", "init", "-q"], cwd=RAIZ, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=RAIZ, capture_output=True)
    subprocess.run(["git", "-c", "user.email=b@b", "-c", "user.name=b", "commit", "-qm", "init"],
                   cwd=RAIZ, capture_output=True)


def corre(cmd, timeout=600):
    p = subprocess.run(cmd, cwd=RAIZ, capture_output=True, timeout=timeout)
    return p.returncode, p.stdout.decode("utf-8", "replace")


def cargo_test(ficheros=None):
    """rc de cargo test. Con ficheros, solo esos binarios de integracion."""
    if ficheros is None:
        return corre([CARGO, "test", "-q"])[0] != 0
    cmd = [CARGO, "test", "-q"]
    for f in ficheros:
        cmd += ["--test", os.path.splitext(os.path.basename(f))[0]]
    return corre(cmd)[0] != 0


def limpia():
    subprocess.run(["git", "checkout", "HEAD", "--", "."], cwd=RAIZ, capture_output=True)


def rompe(modulo, funcion):
    ruta = os.path.join(RAIZ, "src", modulo)
    src = open(ruta, encoding="utf-8").read()
    i = src.index("pub fn %s(" % funcion)
    j = src.index("{", i) + 1
    open(ruta, "w", encoding="utf-8", newline="").write(
        src[:j] + ' panic!("ESTRES"); ' + src[j:])


def seleccion():
    rc, out = corre(GB + ["tests", "--worktree", "--json"])
    if not out.strip().startswith("{"):
        return None, False, "gb tests no devolvio json"
    d = json.loads(out)
    if d.get("range_error"):
        return None, False, d["range_error"]
    return list(d.get("tests") or []), bool(d.get("todo")), None


if not CARGO:
    print("cargo no esta instalado")
    raise SystemExit(1)

genera()
_rc, _hd = corre(["git", "rev-parse", "--short", "HEAD"])
if _rc != 0:
    print("ERROR: el repo del banco no tiene HEAD; sin baseline no se puede medir")
    raise SystemExit(1)
print("baseline commiteada: %s" % _hd.strip())
print("compilando la linea base (cargo tarda la primera vez)...", flush=True)
if cargo_test():
    print("ERROR: la suite base no esta verde; el banco no puede medir nada")
    raise SystemExit(1)

print("proyecto: %d modulos, %d tests de integracion · runner: cargo test\n"
      % (len(MODULOS), len(TESTS)))
print("%-26s %4s %9s %10s  %s" % ("rotura", "sel", "rojo_sel", "rojo_full", "veredicto"))
print("-" * 84)

OBJETIVOS = [("iva.rs", "iva"), ("carrito.rs", "subtotal"), ("carrito.rs", "total"),
             ("descuento.rs", "con_descuento"), ("factura.rs", "emitir"),
             ("informe.rs", "linea"), ("texto.rs", "mayus")]

falsos = ahorro = 0
for modulo, funcion in OBJETIVOS:
    limpia()
    rompe(modulo, funcion)
    sel, todo, error = seleccion()
    if error:
        print("%-26s  ERROR: %s" % ("%s:%s" % (modulo, funcion), error[:44]))
        continue
    rojo_sel = cargo_test(sel) if sel and not todo else cargo_test()
    rojo_full = cargo_test()
    if rojo_full and not rojo_sel:
        v, falsos = "*** FALSO VERDE ***", falsos + 1
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
