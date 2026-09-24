"""Dart contra lo que salio en un repo real (petitparser, 24-sep-2026).

Tres agujeros con la sonda de conformidad en verde:

  - `package:<propio>/x.dart` —la forma idiomatica de tests, ejemplos y mucho
    `lib/`— no dejaba arista: se resolvia como ruta relativa. La regla exacta
    es el `name:` del pubspec.yaml, como el `module` de go.mod.
  - `export` (los barriles), `import ... as x`/`show` y las comillas dobles no
    casaban `import '$SRC';`: 147 de 646 aristas perdidas.
  - `abstract class P<R> extends B`, mixin, extension, getters y metodos `=>`
    no eran simbolos: 10 clases de 194.
"""
import os

import pytest

from galaxybrain import lenguajes

necesita_astgrep = pytest.mark.skipif(
    not lenguajes.binario(),
    reason="ast-grep no instalado; la capa multilenguaje es opcional (ADR 0009)",
)


def _arbol(tmp_path, ficheros):
    raiz = str(tmp_path / "pkg")
    for rel, texto in ficheros.items():
        ruta = os.path.join(raiz, *rel.split("/"))
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, "w", encoding="utf-8") as fh:
            fh.write(texto)
    return raiz


def _imports(raiz):
    return {(e[0], e[1]) for e in lenguajes.analyze(raiz)["edges"] if e[2] == "IMPORTS"}


@necesita_astgrep
def test_package_propio_resuelve_por_el_pubspec_y_el_ajeno_no_cae_en_un_homonimo(tmp_path):
    raiz = _arbol(tmp_path, {
        "pubspec.yaml": "name: app\n",
        "lib/src/util.dart": "int uno() => 1;\n",
        # homonimo local del paquete externo `meta`
        "lib/meta.dart": "int dos() => 2;\n",
        "test/util_test.dart": ("import 'package:app/src/util.dart';\n"
                                "import 'package:meta/meta.dart';\n"
                                "import 'dart:async';\n"),
        # un ejemplo con SU pubspec importa el paquete padre por su nombre
        "example/pubspec.yaml": "name: app_example\n",
        "example/lib/main.dart": "import 'package:app/src/util.dart';\n",
    })
    aristas = _imports(raiz)
    assert ("test.util_test", "lib.src.util") in aristas, aristas
    assert ("example.lib.main", "lib.src.util") in aristas, aristas
    assert not any(d == "lib.meta" for _o, d in aristas), aristas


@necesita_astgrep
def test_export_part_y_combinadores_dejan_arista_y_part_of_no_fabrica_ciclo(tmp_path):
    raiz = _arbol(tmp_path, {
        "lib/a.dart": "int a() => 1;\n",
        "lib/b.dart": "int b() => 1;\n",
        "lib/c.dart": "int c() => 1;\n",
        "lib/d.dart": "part of 'barril.dart';\nint d() => 1;\n",
        "lib/barril.dart": ("export 'a.dart';\n"
                            "import \"b.dart\" as b;\n"
                            "import 'c.dart' show c;\n"
                            "part 'd.dart';\n"),
    })
    informe = lenguajes.analyze(raiz)
    aristas = {(e[0], e[1]) for e in informe["edges"] if e[2] == "IMPORTS"}
    for destino in ("lib.a", "lib.b", "lib.c", "lib.d"):
        assert ("lib.barril", destino) in aristas, aristas
    # `part of` es la vuelta del mismo `part`: contarla seria un ciclo inventado
    assert ("lib.d", "lib.barril") not in aristas, aristas


@necesita_astgrep
def test_las_formas_de_definicion_de_dart_son_simbolos(tmp_path):
    raiz = _arbol(tmp_path, {"lib/p.dart": (
        "abstract class Parser<R> extends Base implements Otro {\n"
        "  factory Parser.of(int y) => Impl(y);\n"
        "  int get tamano => 1;\n"
        "  Result<R> parse(String input, {int start = 0}) =>\n"
        "      parseOn(input, start);\n"
        "  static int doble(int n) => n * 2;\n"
        "  Future<void> corre() async {\n    await algo();\n  }\n"
        "  Parser<R> copy();\n"
        "}\n\n"
        "sealed class Result<R> {}\n\n"
        "mixin Mezcla on Parser {\n  void mezclar() {}\n}\n\n"
        "extension Ext<R> on Parser<R> {\n  int cuenta() => 1;\n}\n\n"
        "enum Color { rojo, verde }\n\n"
        "Parser<String> char(\n  String value, {\n  String? message,\n}) {\n"
        "  return Parser.of(1);\n}\n")})
    nodos = {(n["kind"], n["qual"]) for n in lenguajes.analyze(raiz)["nodes"]}
    for esperado in [("class", "lib.p.Parser"), ("class", "lib.p.Result"),
                     ("class", "lib.p.Mezcla"), ("class", "lib.p.Ext"),
                     ("class", "lib.p.Color"), ("method", "lib.p.of"),
                     ("method", "lib.p.tamano"), ("method", "lib.p.parse"),
                     ("method", "lib.p.doble"), ("method", "lib.p.corre"),
                     ("method", "lib.p.mezclar"), ("method", "lib.p.cuenta"),
                     ("function", "lib.p.char")]:
        assert esperado in nodos, (esperado, sorted(nodos))
    # abstracto, sin cuerpo: no hay codigo que llamar y no se promete
    assert not any(q == "lib.p.copy" for _k, q in nodos), sorted(nodos)
