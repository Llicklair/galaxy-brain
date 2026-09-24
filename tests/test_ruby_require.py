"""Ruby: `require` por $LOAD_PATH y `def self.x` sin parentesis.

Medido sobre addressable el 24-sep-2026: la gema no usa ni un
`require_relative` —todo es `require "addressable/uri"`— y el grafo salia a 0
aristas; y `def self.port_mapping` no era simbolo mientras `def $NAME` fabricaba
decenas de simbolos llamados `self`. La matriz cubre las tres comillas del
`require` y la colision con la stdlib (`require "set"` contra un
`lib/gema/set.rb` propio), que es la arista inventada de Go y Rust.
"""


import pytest

from galaxybrain import lenguajes

pytestmark = pytest.mark.skipif(
    not lenguajes.binario(),
    reason="ast-grep no instalado; la capa multilenguaje es opcional (ADR 0009)",
)

GEMA = ('require "set"\nrequire \'json\'\nrequire("gema/set")\n'
        'require "gema/version"\n'
        "module Gema\n  def self.uno(a)\n    dos(a)\n  end\n"
        "  def self.dos(a)\n    a\n  end\n  def self.sin_args\n    uno(1)\n  end\nend\n")


def _arbol(tmp_path):
    (tmp_path / "lib" / "gema").mkdir(parents=True)
    (tmp_path / "test").mkdir()
    (tmp_path / "lib" / "gema.rb").write_text(GEMA, encoding="utf-8")
    for n in ("set", "json", "version"):
        (tmp_path / "lib" / "gema" / (n + ".rb")).write_text(
            "def %s_f(a)\n  a\nend\n" % n, encoding="utf-8")
    (tmp_path / "test" / "gema_test.rb").write_text(
        'require "gema"\nrequire "minitest/autorun"\n', encoding="utf-8")
    return lenguajes.analyze(str(tmp_path))


def test_require_de_gema_por_load_path_y_no_por_sufijo(tmp_path):
    inf = _arbol(tmp_path)
    imps = {(o, d) for o, d, t in inf["edges"] if t == "IMPORTS"}
    assert imps == {("lib.gema", "lib.gema.set"),
                    ("lib.gema", "lib.gema.version"), ("test.gema_test", "lib.gema")}, imps


def test_def_self_sin_parentesis_es_simbolo_y_self_no(tmp_path):
    inf = _arbol(tmp_path)
    quals = {n["qual"] for n in inf["nodes"]}
    assert {"lib.gema.uno", "lib.gema.dos", "lib.gema.sin_args"} <= quals
    assert not any(q.endswith(".self") for q in quals), quals
    llamadas = {(o, d) for o, d, t in inf["edges"] if t == "CALLS"}
    assert ("lib.gema.uno", "lib.gema.dos") in llamadas
    assert ("lib.gema.sin_args", "lib.gema.uno") in llamadas
