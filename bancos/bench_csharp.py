"""Criterio 6 en C#: `gb tests` sobre un proyecto .NET real, 0 falsos verdes.

Mismo protocolo que JS, Go y Rust. C# aporta dos cosas que ninguno de los otros
tres tenia:

  - sus METODOS solo se extraen con patron CONTEXTUAL (`class A { ... }` mas
    `--selector method_declaration`), porque suelto ast-grep parsea el patron
    como funcion local y el `$` de la metavariable produce nodos ERROR
  - sus llamadas son CUALIFICADAS por la clase (`Carrito.Total(...)`), asi que
    dependen de la resolucion por sufijo contra modulos que existen

Runner: `dotnet test` con xunit. A diferencia de node/go/cargo, aqui el runner NO
viene incluido: necesita restaurar paquetes de NuGet. Si no estan en cache, este
banco no puede correr — y eso se dice, no se disimula.

La rotura es en RUNTIME (`throw`), nunca de compilacion: un fallo de build haria
fallar cualquier seleccion y el banco daria 0 falsos verdes sin haber medido nada.
"""

import json
import os
import shutil
import subprocess
import sys

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bench-cs")
GB = [sys.executable, "-m", "galaxybrain.cli"]
DOTNET = shutil.which("dotnet")

MODULOS = {
    "Iva": "namespace Bench;\n\npublic static class Iva\n{\n"
           "    public static double Get() { return 0.21; }\n}\n",
    "Carrito": "namespace Bench;\n\npublic static class Carrito\n{\n"
               "    public static double Subtotal(double[] xs)\n    {\n"
               "        double t = 0; foreach (var x in xs) { t += x; } return t;\n    }\n\n"
               "    public static double Total(double[] xs)\n    {\n"
               "        return Subtotal(xs) * (1 + Iva.Get());\n    }\n}\n",
    "Descuento": "namespace Bench;\n\npublic static class Descuento\n{\n"
                 "    public static double Aplicar(double[] xs, double d)\n    {\n"
                 "        return Carrito.Total(xs) * (1 - d);\n    }\n}\n",
    "Factura": "namespace Bench;\n\npublic static class Factura\n{\n"
               "    public static double Emitir(double[] xs)\n    {\n"
               "        return Descuento.Aplicar(xs, 0.1);\n    }\n}\n",
    "Informe": "namespace Bench;\n\npublic static class Informe\n{\n"
               "    public static string Linea(double[] xs)\n    {\n"
               "        var v = Factura.Emitir(xs); return $\"TOTAL {v}\";\n    }\n}\n",
    "Texto": "namespace Bench;\n\npublic static class Texto\n{\n"
             "    public static string Mayus(string s) { return s.ToUpper(); }\n}\n",
}

#: fichero de test -> (clase de test, expresion que ejercita la cadena)
TESTS = {
    "IvaTests": "var v = Iva.Get(); Assert.True(v > 0);",
    "CarritoTests": "var v = Carrito.Total(new double[]{10}); Assert.True(v > 0);",
    "DescuentoTests": "var v = Descuento.Aplicar(new double[]{10}, 0.1); Assert.True(v > 0);",
    "FacturaTests": "var v = Factura.Emitir(new double[]{10}); Assert.True(v > 0);",
    "InformeTests": "var v = Informe.Linea(new double[]{10}); Assert.NotEmpty(v);",
    "TextoTests": "var v = Texto.Mayus(\"a\"); Assert.Equal(\"A\", v);",
}

CSPROJ_SRC = ("<Project Sdk=\"Microsoft.NET.Sdk\">\n  <PropertyGroup>\n"
              "    <TargetFramework>net10.0</TargetFramework>\n"
              "    <Nullable>disable</Nullable>\n  </PropertyGroup>\n</Project>\n")


def _corre(cmd, cwd=RAIZ, timeout=900):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, timeout=timeout)
    return p.returncode, p.stdout.decode("utf-8", "replace")


def genera():
    shutil.rmtree(RAIZ, ignore_errors=True)
    os.makedirs(os.path.join(RAIZ, "src"), exist_ok=True)
    os.makedirs(os.path.join(RAIZ, "tests"), exist_ok=True)
    open(os.path.join(RAIZ, ".gitignore"), "w", encoding="utf-8").write("bin/\nobj/\n")
    for nombre, cuerpo in MODULOS.items():
        open(os.path.join(RAIZ, "src", nombre + ".cs"), "w", encoding="utf-8").write(cuerpo)
    open(os.path.join(RAIZ, "src", "Bench.csproj"), "w", encoding="utf-8").write(CSPROJ_SRC)

    # el proyecto de tests se crea con la plantilla, que es lo que trae xunit
    subprocess.run([DOTNET, "new", "xunit", "-o", "tests", "--force"],
                   cwd=RAIZ, capture_output=True, timeout=600)
    for f in os.listdir(os.path.join(RAIZ, "tests")):
        if f.endswith(".cs") and f not in {n + ".cs" for n in TESTS}:
            os.remove(os.path.join(RAIZ, "tests", f))
    for clase, cuerpo in TESTS.items():
        open(os.path.join(RAIZ, "tests", clase + ".cs"), "w", encoding="utf-8").write(
            "using Xunit;\nusing Bench;\n\npublic class %s\n{\n    [Fact]\n"
            "    public void Comprueba()\n    {\n        %s\n    }\n}\n" % (clase, cuerpo))
    subprocess.run([DOTNET, "add", "tests", "reference", "src/Bench.csproj"],
                   cwd=RAIZ, capture_output=True, timeout=600)
    subprocess.run(["git", "init", "-q"], cwd=RAIZ, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=RAIZ, capture_output=True)
    subprocess.run(["git", "-c", "user.email=b@b", "-c", "user.name=b", "commit", "-qm", "init"],
                   cwd=RAIZ, capture_output=True)


def dotnet_test(ficheros=None):
    """rc de `dotnet test`. Con ficheros, se filtra por la CLASE de cada uno —
    en .NET se selecciona por nombre cualificado, no por ruta."""
    # Al proyecto de tests EXPLICITO: `dotnet test` a secas exige un .sln o un
    # .csproj en el directorio actual, y aqui la raiz no tiene ninguno.
    cmd = [DOTNET, "test", os.path.join("tests", "tests.csproj"), "--nologo", "-v", "q"]
    if ficheros:
        clases = [os.path.splitext(os.path.basename(f))[0] for f in ficheros]
        cmd += ["--filter", "|".join("FullyQualifiedName~%s" % c for c in clases)]
    return _corre(cmd)[0] != 0


def limpia():
    subprocess.run(["git", "checkout", "HEAD", "--", "."], cwd=RAIZ, capture_output=True)


def rompe(modulo, metodo):
    """Rotura en RUNTIME, no de compilacion: un fallo de build haria fallar
    cualquier seleccion y el banco daria 0 falsos verdes sin medir nada."""
    ruta = os.path.join(RAIZ, "src", modulo + ".cs")
    s = open(ruta, encoding="utf-8").read()
    i = s.index(" %s(" % metodo)
    j = s.index("{", s.index(")", i)) + 1
    open(ruta, "w", encoding="utf-8", newline="").write(
        s[:j] + ' throw new System.Exception("ESTRES");' + s[j:])


def seleccion():
    rc, out = _corre(GB + ["tests", "--worktree", "--json"])
    if not out.strip().startswith("{"):
        return None, False, "gb tests no devolvio json"
    d = json.loads(out)
    if d.get("range_error"):
        return None, False, d["range_error"]
    return list(d.get("tests") or []), bool(d.get("todo")), None


if not DOTNET:
    print("dotnet no esta instalado: sin runner no hay rojos reales")
    raise SystemExit(1)

genera()
print("compilando la linea base...", flush=True)
if dotnet_test():
    print("ERROR: la suite base no esta verde; el banco no puede medir nada")
    raise SystemExit(1)

print("proyecto C#: %d clases, %d tests · runner: dotnet test (xunit)\n"
      % (len(MODULOS), len(TESTS)))
print("%-24s %4s %9s %10s  %s" % ("rotura", "sel", "rojo_sel", "rojo_full", "veredicto"))
print("-" * 82)

OBJETIVOS = [("Iva", "Get"), ("Carrito", "Subtotal"), ("Carrito", "Total"),
             ("Descuento", "Aplicar"), ("Factura", "Emitir"),
             ("Informe", "Linea"), ("Texto", "Mayus")]

falsos = ahorro = 0
for modulo, metodo in OBJETIVOS:
    limpia()
    rompe(modulo, metodo)
    sel, todo, error = seleccion()
    if error:
        print("%-24s  ERROR: %s" % ("%s.%s" % (modulo, metodo), error[:44]))
        continue
    rojo_sel = dotnet_test(sel) if sel and not todo else dotnet_test()
    rojo_full = dotnet_test()
    if rojo_full and not rojo_sel:
        v, falsos = "*** FALSO VERDE ***", falsos + 1
    elif rojo_full:
        v = "ok (lo pilla)%s" % (" [cayo a todo]" if todo else "")
        ahorro += len(TESTS) - (len(sel) if sel and not todo else len(TESTS))
    else:
        v = "sin cobertura"
    print("%-24s %4d %9s %10s  %s"
          % ("%s.%s" % (modulo, metodo), len(sel), rojo_sel, rojo_full, v))

limpia()
print("-" * 82)
print("%d roturas · %d FALSOS VERDES · ahorro medio %.0f%% de la suite"
      % (len(OBJETIVOS), falsos, 100.0 * ahorro / (len(OBJETIVOS) * len(TESTS))))
