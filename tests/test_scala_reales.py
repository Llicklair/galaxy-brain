"""Scala: los imports, los simbolos y las llamadas del Scala de verdad.

Medido sobre scala/scala-xml el 24-sep-2026 (banco de repos reales):

- `import $SRC` capturaba SOLO el primer identificador (`scala` de
  `scala.xml.parsing.ConstructingParser`): los imports absolutos y agrupados no
  dejaban arista, y solo casaban por casualidad los relativos de un segmento.
- Y leer el nombre entero no basta: por la via generica (sufijo sin
  mayusculas) `org.xml.sax.XMLReader` caia en `scala/xml/XML.scala` y
  `util.Properties` en un `Properties.scala` de test. Las aristas inventadas
  que ya dieron Go, Rust y Java.
- Los patrones veian 311 de 1020 `def` y 74 de 242 tipos: ni un `trait`, ni
  una `case class` sin cuerpo, ni un `def` sin tipo de retorno o con modificador.
- Y al verse `private[xml] def assertEquals` de un helper de test, cada
  `assertEquals(...)` de JUnit (`import org.junit.Assert.assertEquals`) caia en
  el por nombre: 250 llamadas inventadas.
"""

import os

import pytest

from galaxybrain import lenguajes

pytestmark = pytest.mark.skipif(
    not lenguajes.binario(),
    reason="ast-grep no instalado; la capa multilenguaje es opcional (ADR 0009)",
)


def _arbol(raiz, ficheros):
    for rel, fuente in ficheros.items():
        ruta = os.path.join(raiz, *rel.split("/"))
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, "w", encoding="utf-8") as fh:
            fh.write(fuente)
    return lenguajes.analyze(raiz)


def _aristas(informe, tipo):
    return {(e[0], e[1]) for e in informe["edges"] if e[2] == tipo}


def test_scala_import_absoluto_agrupado_relativo_y_comodin(tmp_path):
    informe = _arbol(str(tmp_path / "sc"), {
        # dos clausulas `package` apiladas: `factory.Loader` es relativo a app.xml
        "src/app/xml/XML.scala": ("package app\npackage xml\n\nimport factory.Loader\n\n"
                                  "object XML extends Loader {\n"
                                  "  def load(s: String): String = s\n}\n"),
        "src/app/xml/factory/Loader.scala": ("package app.xml.factory\n\n"
                                             "trait Loader {\n  def base = 1\n}\n"),
        "src/app/xml/parsing/Parser.scala": ("package app.xml.parsing\n\n"
                                             "class Parser(s: String)\n"),
        "src/app/test/UsaTest.scala": ("package app.test\n\n"
                                       "import app.xml.{XML, Nope => Otro}\n"
                                       "import app.xml.factory._\n"
                                       "import app.xml.parsing.Parser\n\n"
                                       "class UsaTest\n"),
    })
    aristas = _aristas(informe, "IMPORTS")

    assert ("app.xml.XML", "app.xml.factory.Loader") in aristas, aristas
    assert ("app.test.UsaTest", "app.xml.XML") in aristas, \
        "se perdio el import AGRUPADO `a.{B, C => D}`: %s" % aristas
    assert ("app.test.UsaTest", "app.xml.factory.Loader") in aristas, \
        "se perdio `import pkg._` de un paquete de un solo modulo: %s" % aristas
    assert ("app.test.UsaTest", "app.xml.parsing.Parser") in aristas, \
        "se perdio el import absoluto: %s" % aristas


def test_scala_un_import_externo_no_cae_en_un_modulo_propio(tmp_path):
    informe = _arbol(str(tmp_path / "sc"), {
        "src/app/xml/XML.scala": "package app.xml\n\nobject XML\n",
        "src/app/Properties.scala": "package app\n\nobject Properties\n",
        "src/app/xml/sax/Filter.scala": ("package app.xml.sax\n\n"
                                         "import org.xml.sax.{XMLReader, Locator}\n"
                                         "import javax.xml.parsers.SAXParserFactory\n"
                                         "import util.Properties.versionNumberString\n"
                                         "import scala.collection.Seq\n\n"
                                         "class Filter\n"),
    })
    aristas = _aristas(informe, "IMPORTS")

    assert not [d for o, d in aristas if o.endswith("Filter")], aristas


def test_scala_extrae_cada_forma_de_definicion(tmp_path):
    informe = _arbol(str(tmp_path / "sc"), {
        "src/a/b/Formas.scala": (
            "package a.b\n\n"
            "trait T\n"
            "sealed trait U { def abstracto: Int }\n"
            "case class C(x: Int)\n"
            "case class D(x: Int) extends U { def abstracto = x }\n"
            "class E[A](a: A) extends T with U {\n"
            "  override def abstracto: Int = 1\n"
            "  private[b] def g(y: Int) = y + h\n"
            "  def h = 2\n"
            "  def llaves(): Unit = {\n    println(1)\n  }\n"
            "}\n"
            "object O extends T {\n"
            "  final def ind(x: Int): Int =\n    x + 1\n"
            "}\n"),
    })
    nombres = {n["qual"].rsplit(".", 1)[-1] for n in informe["nodes"] if n["kind"] != "module"}

    for esperado in ("T", "U", "C", "D", "E", "O", "g", "h", "llaves", "ind", "abstracto"):
        assert esperado in nombres, "%s no es simbolo: %s" % (esperado, sorted(nombres))
    # el `def abstracto: Int` de U no tiene cuerpo: no es una definicion
    lineas = {n["line"] for n in informe["nodes"] if n["qual"].endswith(".abstracto")}
    assert 4 not in lineas, lineas


def test_scala_una_llamada_importada_de_fuera_no_cae_en_un_homonimo(tmp_path):
    informe = _arbol(str(tmp_path / "sc"), {
        "src/app/Helpers.scala": ("package app\n\nobject Helpers {\n"
                                  "  private[app] def assertEquals(a: String, b: String): Unit = ()\n"
                                  "}\n"),
        "src/app/ExtTest.scala": ("package app\n\nimport org.junit.Assert.assertEquals\n\n"
                                  "class ExtTest {\n  def t(): Unit = {\n"
                                  "    assertEquals(\"a\", \"b\")\n  }\n}\n"),
        "src/app/OwnTest.scala": ("package app\n\nimport app.Helpers.assertEquals\n\n"
                                  "class OwnTest {\n  def t(): Unit = {\n"
                                  "    assertEquals(\"a\", \"b\")\n  }\n}\n"),
    })
    llamadas = _aristas(informe, "CALLS")

    assert ("app.OwnTest.t", "app.Helpers.assertEquals") in llamadas, llamadas
    assert ("app.ExtTest.t", "app.Helpers.assertEquals") not in llamadas, \
        "el assertEquals de JUnit cayo en el helper propio: %s" % llamadas
