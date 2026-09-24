"""PHP: los simbolos, los `use` y las llamadas de metodo del PHP de verdad.

Medido sobre league/container el 24-sep-2026: 0 aristas de import (los 296
`use` internos no se leian), 1 clase de src/ de 57 (`final`, `readonly`,
`implements` e `interface` tapaban el patron plano), casi ningun metodo (el
`: Tipo` de retorno tapaba el resto) y 0 llamadas (`$this->x()` es otro nodo).
La matriz va por forma porque la gramatica no deja metavariable en el
modificador, el retorno ni el atributo: probar solo la plana certificaria de mas.
"""

import json
import os

import pytest

from galaxybrain import lenguajes

pytestmark = pytest.mark.skipif(
    not lenguajes.binario(),
    reason="ast-grep no instalado; la capa multilenguaje es opcional (ADR 0009)",
)

FUENTE = """<?php
namespace App;

#[Attribute]
final class Plana extends Base implements Contrato {
    public function a() { return $this->b(); }
    public function b(): int { return self::c(); }
    public static function c(): ?int { return static::d(); }
    private static function d(): int { return 1; }
    protected function e(): void { parent::e(); }
    #[Override]
    public function f(string $x): string { return $x; }
    final public function g() {}
    function h() {}
}
final readonly class Lectura {}
abstract class Abstracta { abstract protected function i(): void; }
interface Contrato { public function j(): self; }
trait Rasgo { public function k() {} }
enum Palo: string { case A = 'a'; public function l(): string { return 'x'; } }
function suelta(): int { return 1; }
"""


def _escribe(raiz, rel, texto):
    ruta = os.path.join(raiz, *rel.split("/"))
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write(texto)


def test_clases_y_metodos_con_modificador_retorno_y_atributo(tmp_path):
    raiz = str(tmp_path / "php")
    _escribe(raiz, "a.php", FUENTE)
    nombres = {n["qual"].rsplit(".", 1)[-1] for n in lenguajes.analyze(raiz)["nodes"]
               if n["kind"] != "module"}
    esperados = {"Plana", "Lectura", "Abstracta", "Contrato", "Rasgo", "Palo", "suelta",
                 "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l"}
    assert esperados <= nombres, "faltan: %s" % sorted(esperados - nombres)


def test_this_self_static_resuelven_por_ambito_y_parent_no(tmp_path):
    raiz = str(tmp_path / "php")
    _escribe(raiz, "a.php", FUENTE)
    llamadas = {(o, d) for o, d, t in lenguajes.analyze(raiz)["edges"] if t == "CALLS"}
    assert {("a.a", "a.b"), ("a.b", "a.c"), ("a.c", "a.d")} <= llamadas
    # parent::e() es el metodo del PADRE, no este: por ambito saldria una auto-arista
    assert ("a.e", "a.e") not in llamadas


def _proyecto_psr4(raiz):
    _escribe(raiz, "composer.json", json.dumps(
        {"autoload": {"psr-4": {"App\\": "src/"}},
         "autoload-dev": {"psr-4": {"App\\Tests\\": "tests/"}}}))
    _escribe(raiz, "src/Container.php", "<?php\nnamespace App;\nclass Container {}\n")
    _escribe(raiz, "src/Util/Caja.php", "<?php\nnamespace App\\Util;\nclass Caja {}\n")
    _escribe(raiz, "src/Servicio.php",
             "<?php\nnamespace App;\n"
             "use App\\Util\\Caja;\n"
             "use App\\Container as C, Psr\\Log\\LoggerInterface;\n"
             # externos cuyo nombre corto COINCIDE con un fichero propio
             "use Psr\\Container\\ContainerInterface;\n"
             "use Vendor\\Util\\Caja as Otra;\n"
             "use function App\\Util\\ayuda;\n"
             "class Servicio {}\n")
    _escribe(raiz, "tests/ServicioTest.php",
             "<?php\nnamespace App\\Tests;\nuse App\\Servicio;\nclass ServicioTest {}\n")


def test_use_resuelve_por_psr4_y_no_por_nombre_corto(tmp_path):
    raiz = str(tmp_path / "psr4")
    _proyecto_psr4(raiz)
    aristas = {(o, d) for o, d, t in lenguajes.analyze(raiz)["edges"] if t == "IMPORTS"}
    assert aristas == {("Servicio", "Util.Caja"), ("Servicio", "Container"),
                       ("tests.ServicioTest", "Servicio")}, aristas


def test_sin_composer_un_use_no_deja_arista(tmp_path):
    """Sin el mapa PSR-4 no hay hecho: `use App\\Util\\Caja` podria vivir en
    cualquier sitio, y casarlo por nombre es el bug de Rust y Go."""
    raiz = str(tmp_path / "sin")
    _escribe(raiz, "Util/Caja.php", "<?php\nnamespace App\\Util;\nclass Caja {}\n")
    _escribe(raiz, "Servicio.php", "<?php\nuse Vendor\\Util\\Caja;\nclass Servicio {}\n")
    aristas = {(o, d) for o, d, t in lenguajes.analyze(raiz)["edges"] if t == "IMPORTS"}
    assert not aristas, aristas
