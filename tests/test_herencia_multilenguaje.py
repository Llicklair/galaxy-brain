"""Herencia y dueño de los metodos en los lenguajes con clases.

Solo Python emitia `owner` y aristas EXTENDS (24-sep-2026), y con ellos la
seleccion sube de un metodo de la base a quien usa la subclase. En JS ni
siquiera `class Sub extends Base {` era simbolo. La arista sale solo si la base
casa con UNA clase del arbol; una base de fuera o ambigua se cuenta, no se
inventa.
"""

import os

import pytest

from galaxybrain import lenguajes

pytestmark = pytest.mark.skipif(
    not lenguajes.binario(),
    reason="ast-grep no instalado; la capa multilenguaje es opcional (ADR 0009)",
)

CASOS = {
    "a.js": "class Base { hola() { return 1; } }\nclass Sub extends Base { otra() { return 2; } }\n",
    "a.ts": ("class Base<T> { hola(): number { return 1; } }\n"
             "export class Sub extends Base<string> implements X { otra() { return 2; } }\n"),
    "A.java": ("class Base { int hola() { return 1; } }\n"
               "class Sub extends Base implements Runnable { public void run() { } }\n"),
    "A.kt": ("open class Base(val x: Int) { fun hola(): Int { return 1 } }\n"
             "class Sub(x: Int) : Base(x), Comparable<Sub> { fun otra(): Int { return 2 } }\n"),
    "A.cs": ("class Base { public int Hola() { return 1; } }\n"
             "class Sub : Base, IDisposable { public void Dispose() { } }\n"),
    "A.swift": ("class Base { func hola() -> Int { return 1 } }\n"
                "class Sub: Base, Codable { func otra() -> Int { return 2 } }\n"),
    "A.scala": ("class Base { def hola(): Int = { 1 } }\n"
                "class Sub extends Base with Serializable { def otra(): Int = { 2 } }\n"),
    "a.php": ("<?php\nclass Base { public function hola() { return 1; } }\n"
              "class Sub extends Base implements Countable { public function count(): int { return 0; } }\n"),
    "a.rb": "class Base\n  def hola\n    1\n  end\nend\nclass Sub < Base\n  def otra\n    2\n  end\nend\n",
    "a.dart": ("class Base { int hola() { return 1; } }\n"
               "class Sub extends Base with M implements I { int otra() { return 2; } }\n"),
}


def _informe(tmp_path, nombre, fuente):
    raiz = os.path.join(str(tmp_path), nombre.replace(".", "_"))
    os.makedirs(raiz)
    with open(os.path.join(raiz, nombre), "w", encoding="utf-8") as fh:
        fh.write(fuente)
    return lenguajes.analyze(raiz)


@pytest.mark.parametrize("nombre", sorted(CASOS))
def test_la_subclase_hereda_de_su_base_y_sus_metodos_tienen_dueno(tmp_path, nombre):
    informe = _informe(tmp_path, nombre, CASOS[nombre])
    modulo = os.path.splitext(nombre)[0]
    extends = {(o, d) for o, d, t in informe["edges"] if t == "EXTENDS"}
    assert extends == {("%s.Sub" % modulo, "%s.Base" % modulo)}, extends
    duenos = {n["owner"] for n in informe["nodes"] if n["kind"] == "method"}
    assert duenos == {"%s.Base" % modulo, "%s.Sub" % modulo}, duenos
    assert informe["unresolved"].get("base-sin-resolver", 0) >= (0 if nombre.endswith(".rb") or
                                                                    nombre == "a.js" else 1)


def test_new_de_la_subclase_es_una_llamada(tmp_path):
    informe = _informe(tmp_path, "b.js", CASOS["a.js"] + "function usa() { return new Sub(); }\n")
    assert ("b.usa", "b.Sub") in {(o, d) for o, d, t in informe["edges"] if t == "CALLS"}


def test_una_base_cualificada_no_elige_la_homonima_local(tmp_path):
    """addressable (24-sep-2026): `CustomURIClass < Addressable::URI` caia en el
    `Fake::URI` del spec por preferir la clase local — arista inventada."""
    raiz = os.path.join(str(tmp_path), "gema")
    os.makedirs(os.path.join(raiz, "lib"))
    os.makedirs(os.path.join(raiz, "spec"))
    with open(os.path.join(raiz, "lib", "uri.rb"), "w", encoding="utf-8") as fh:
        fh.write("module Addressable\n  class URI\n    def parse\n      1\n    end\n  end\nend\n")
    with open(os.path.join(raiz, "spec", "uri_spec.rb"), "w", encoding="utf-8") as fh:
        fh.write("module Fake\n  class URI\n    def x\n      1\n    end\n  end\nend\n"
                 "class CustomURIClass < Addressable::URI\n  def y\n    2\n  end\nend\n")
    informe = lenguajes.analyze(raiz)
    extends = [(o, d) for o, d, t in informe["edges"] if t == "EXTENDS"]
    assert not any(d.endswith("uri_spec.URI") for _o, d in extends), extends


def test_rust_impl_da_dueno_y_el_trait_es_herencia(tmp_path):
    """El `impl` no es un nodo de clase: sin tratarlo, los metodos de `impl X {}`
    no tenian dueño y `impl Trait for X` no era herencia. Un trait de fuera
    (`Display`) no inventa arista."""
    informe = _informe(tmp_path, "a.rs",
                       "pub trait Forma {\n    fn area(&self) -> f64;\n}\n"
                       "pub struct Cuadrado { l: f64 }\n"
                       "impl Cuadrado {\n    pub fn nuevo(l: f64) -> Self { Cuadrado { l } }\n}\n"
                       "impl Forma for Cuadrado {\n    fn area(&self) -> f64 { self.l * self.l }\n}\n"
                       "impl std::fmt::Display for Cuadrado {\n"
                       "    fn fmt(&self, f: &mut Formatter) -> Result { Ok(()) }\n}\n"
                       "fn suelta() {}\n")
    duenos = {n["qual"]: n.get("owner") for n in informe["nodes"] if n["kind"] in ("method", "function")}
    assert duenos == {"a.nuevo": "a.Cuadrado", "a.area": "a.Cuadrado", "a.fmt": "a.Cuadrado",
                      "a.suelta": None}, duenos
    extends = {(o, d) for o, d, t in informe["edges"] if t == "EXTENDS"}
    assert extends == {("a.Cuadrado", "a.Forma")}, extends
