"""Elixir: el modulo lo nombra `defmodule`, no el fichero.

Medido sobre jason (michalmuskala/jason) el 24-sep-2026:

  - `alias Jason.{DecodeError, Codegen}` no casaba con ningun fichero y, al
    quitar el ultimo segmento, caia en `jason.ex`: cuatro modulos de `lib/`
    "dependian" de `Jason` sin nombrarlo, y las dependencias de verdad
    (`Codegen`, `Encoder`...) no salian.
  - `atom()` / `integer()` de StreamData en `property_test.exs` se colgaban
    del `Jason.Encode.atom` por nombre pelado: en Elixir no hay funciones
    globales, una llamada suelta es del propio modulo o de un `import`.
  - `def f(x) when ...`, `def project do`, `defmacro` y `defmodule A.B` no
    eran simbolos.

La colision con un modulo propio homonimo (`MiApp.Logger` frente al `Logger`
de Elixir, `MiApp.Enum` frente a `Enum`) es la misma arista inventada de Go,
Rust, PHP y Java.
"""

import pytest

from galaxybrain import lenguajes

pytestmark = pytest.mark.skipif(
    not lenguajes.binario(),
    reason="ast-grep no instalado; la capa multilenguaje es opcional (ADR 0009)",
)

CARRITO = (
    "defmodule MiApp.Carrito do\n"
    "  alias MiApp.{Impuestos, Precio}\n"
    "  alias MiApp.Errores.Vacio, as: SinNada\n"
    "  import MiApp.Util, only: [doble: 1]\n"
    "  require Logger\n"
    "  use GenServer\n"
    "\n"
    "  def total(xs) when is_list(xs), do: Impuestos.aplica(xs)\n"
    "  def vacio do\n"
    "    SinNada.nuevo()\n"
    "  end\n"
    "  defmacro atajo(x), do: x\n"
    "  defp redondea(x) when x > 1 do\n"
    "    x |> Precio.redondea() |> doble() |> integer()\n"
    "  end\n"
    "  def lista(xs), do: Enum.map(xs, &redondea/1)\n"
    "  def log(x), do: Logger.info(x)\n"
    "\n"
    "  defmodule Linea do\n"
    "    def precio(l), do: l\n"
    "  end\n"
    "\n"
    "  def linea(l), do: Linea.precio(l)\n"
    "end\n"
)

OTROS = {
    # `Impuestos` vive en `iva.ex`: el nombre del fichero no dice nada
    "iva.ex": "defmodule MiApp.Impuestos do\n  def aplica(xs), do: xs\nend\n",
    "precio.ex": "defmodule MiApp.Precio do\n  def redondea(x), do: x\nend\n",
    "util.ex": "defmodule MiApp.Util do\n  def doble(x), do: x * 2\nend\n",
    "errores.ex": "defmodule MiApp.Errores do\n  defmodule Vacio do\n"
                  "    def nuevo, do: :vacio\n  end\nend\n",
    # homonimos PROPIOS de modulos de Elixir y de una libreria
    "logger.ex": "defmodule MiApp.Logger do\n  def info(x), do: x\nend\n",
    "enum.ex": "defmodule MiApp.Enum do\n  def map(xs, f), do: f.(xs)\nend\n",
    "gen_server.ex": "defmodule MiApp.GenServer do\n  def start(x), do: x\nend\n",
    "generadores.ex": "defmodule MiApp.Generadores do\n  def integer, do: 1\nend\n",
}


def _arbol(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "carrito.ex").write_text(CARRITO, encoding="utf-8")
    for nombre, fuente in OTROS.items():
        (lib / nombre).write_text(fuente, encoding="utf-8")
    return lenguajes.analyze(str(tmp_path))


def test_todas_las_formas_de_def_y_defmodule_son_simbolos(tmp_path):
    quals = {n["qual"] for n in _arbol(tmp_path)["nodes"]}
    esperados = {"lib.carrito.total", "lib.carrito.vacio", "lib.carrito.atajo",
                 "lib.carrito.redondea", "lib.carrito.Carrito", "lib.carrito.Linea",
                 "lib.errores.Vacio", "lib.errores.nuevo"}
    assert esperados <= quals, esperados - quals


def test_los_usos_resuelven_por_lo_declarado_y_no_por_el_fichero(tmp_path):
    imps = {(o, d) for o, d, t in _arbol(tmp_path)["edges"] if t == "IMPORTS"}
    # alias multiple, `as:`, import con opciones: cada uno a su modulo declarado
    assert {("lib.carrito", "lib.iva"), ("lib.carrito", "lib.precio"),
            ("lib.carrito", "lib.errores"), ("lib.carrito", "lib.util")} <= imps, imps
    # `require Logger` y `use GenServer` son de Elixir, no los homonimos propios
    assert ("lib.carrito", "lib.logger") not in imps
    assert ("lib.carrito", "lib.gen_server") not in imps


def test_las_llamadas_siguen_alias_imports_y_anidados(tmp_path):
    llamadas = {(o, d) for o, d, t in _arbol(tmp_path)["edges"] if t == "CALLS"}
    assert {("lib.carrito.total", "lib.iva.aplica"),
            ("lib.carrito.vacio", "lib.errores.nuevo"),
            ("lib.carrito.redondea", "lib.precio.redondea"),
            ("lib.carrito.redondea", "lib.util.doble"),
            ("lib.carrito.linea", "lib.carrito.precio")} <= llamadas, llamadas


def test_un_modulo_de_fuera_no_cae_en_un_homonimo_propio(tmp_path):
    llamadas = {(o, d) for o, d, t in _arbol(tmp_path)["edges"] if t == "CALLS"}
    # `Enum.map` y `Logger.info` son de Elixir; `integer()` suelta no esta
    # importada (en jason era el generador de StreamData)
    assert ("lib.carrito.lista", "lib.enum.map") not in llamadas
    assert ("lib.carrito.log", "lib.logger.info") not in llamadas
    assert ("lib.carrito.redondea", "lib.generadores.integer") not in llamadas
