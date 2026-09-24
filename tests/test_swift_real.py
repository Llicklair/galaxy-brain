"""Swift: los simbolos y los `import` que swift-argument-parser enseño (banco
de repos reales).

Medido el 24-sep-2026 sobre apple/swift-argument-parser: la lista literal de
modificadores no veia `mutating func`, ni `func` genericas, ni `struct` con
`: Protocolo` o `<T>`, ni `enum`, ni `protocol`. El patron `import $SRC` no
casaba `@testable`/`internal`/`@preconcurrency import` ni `import func X.f`.
Y `import Foundation` caia por sufijo en `Utilities/Foundation.swift`: las 22
aristas del grafo eran esa, y las reales (hacia el target de un fichero
`ArgumentParserToolInfo`) no salia ninguna.
"""

import os

import pytest

from galaxybrain import lenguajes

pytestmark = pytest.mark.skipif(
    not lenguajes.binario(),
    reason="ast-grep no instalado; la capa multilenguaje es opcional (ADR 0009)",
)

FORMAS = """public struct Argument<Value>: Decodable where Value: Codable {
  public init(x: Int) { self.x = x }
  mutating func run() throws { helper() }
  func container<K>(keyedBy type: K.Type) throws -> Int where K: CodingKey { 1 }
}
extension Ajeno { func bash() -> String { "" } }
public protocol ParsableCommand: ParsableArguments { mutating func requisito() throws }
final class Tree<Element> { func hijos() {} }
enum Kind: String { case a }
actor Counter { func inc() {} }
@discardableResult public static func libre() -> Int { 1 }
"""


def _escribe(root, rel, texto):
    ruta = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write(texto)


def test_swift_ve_cada_forma_de_definicion(tmp_path):
    _escribe(str(tmp_path), "a.swift", FORMAS)
    quals = {n["qual"] for n in lenguajes.analyze(str(tmp_path))["nodes"]}
    esperados = {"a.Argument", "a.run", "a.container", "a.bash", "a.ParsableCommand",
                 "a.Tree", "a.hijos", "a.Kind", "a.Counter", "a.inc", "a.libre"}
    assert esperados <= quals, "swift no ve: %s" % sorted(esperados - quals)
    # un `extension` nombra un tipo AJENO y un requisito de protocolo no tiene cuerpo
    assert "a.Ajeno" not in quals
    assert "a.requisito" not in quals


PAQUETE = """// swift-tools-version:5.9
import PackageDescription
let package = Package(name: "demo", targets: [
    .target(name: "Nucleo", dependencies: ["Info"]),
    .target(name: "Info"),
    .executableTarget(name: "cli", dependencies: ["Nucleo"], path: "Herramientas/cli"),
    .testTarget(name: "NucleoTests", dependencies: ["Nucleo"]),
])
"""


def _paquete(root):
    _escribe(root, "Package.swift", PAQUETE)
    _escribe(root, "Sources/Info/Info.swift", "public struct Info { public let n: Int }\n")
    # un fichero PROPIO llamado como un modulo del sistema: el cebo del sufijo
    _escribe(root, "Sources/Nucleo/Foundation.swift", "extension String { func x() {} }\n")
    _escribe(root, "Sources/Nucleo/Nucleo.swift",
             "import Foundation\ninternal import Info\n"
             "public func arranca() -> Int { 1 }\n")
    _escribe(root, "Herramientas/cli/main.swift",
             "import Foundation\n@preconcurrency import Nucleo\nimport func Info.x\n")
    _escribe(root, "Tests/NucleoTests/NucleoTests.swift",
             "@testable import Nucleo\nimport XCTest\n")
    return root


def test_import_de_swift_nombra_un_target_no_un_fichero(tmp_path):
    root = _paquete(str(tmp_path))
    aristas = {(e[0], e[1]) for e in lenguajes.analyze(root)["edges"] if e[2] == "IMPORTS"}
    # `import Foundation` es el SDK, no Sources/Nucleo/Foundation.swift
    assert not [a for a in aristas if a[1] == "Sources.Nucleo.Foundation"], aristas
    # target de UN fichero -> arista, con `internal import` y con `import func X.f`
    assert ("Sources.Nucleo.Nucleo", "Sources.Info.Info") in aristas
    assert ("Herramientas.cli.main", "Sources.Info.Info") in aristas
    # target de VARIOS ficheros (Nucleo): no hay destino unico, no se adivina
    assert not [a for a in aristas if a[1].startswith("Sources.Nucleo.")], aristas
    assert len(aristas) == 2, aristas


def test_sin_package_swift_ningun_import_es_propio(tmp_path):
    root = str(tmp_path)
    _escribe(root, "App/Foundation.swift", "struct Foundation {}\n")
    _escribe(root, "App/Vista.swift", "import Foundation\nimport Vista\n")
    aristas = [e for e in lenguajes.analyze(root)["edges"] if e[2] == "IMPORTS"]
    assert not aristas, aristas
