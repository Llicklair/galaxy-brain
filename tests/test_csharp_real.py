"""C#: los simbolos y los `using` que MediatR enseño (banco de repos reales).

Medido el 24-sep-2026 sobre jbogard/MediatR: los patrones casaban los
modificadores EXACTOS, asi que de 51 tipos se veian 2 y faltaban los metodos
genericos, `=> expr`, `override`, `async` e `internal`. Y un `using` de un
namespace de varios ficheros caia por el ultimo segmento en un fichero
homonimo de OTRO proyecto (la misma clase de fallo que Go y Rust).
"""

import os

import pytest

from galaxybrain import lenguajes

pytestmark = pytest.mark.skipif(
    not lenguajes.binario(),
    reason="ast-grep no instalado; la capa multilenguaje es opcional (ADR 0009)",
)

FORMAS = """namespace Demo;

public record Punto(int X, int Y);
public sealed record Persona
{
    public string Saluda() => "hola";
}
internal static partial class Utiles
{
    public static async Task<int> CargaAsync<T>(T x) where T : class { return 1; }
    private static int Doble(int x) => x * 2;
    internal virtual int Nada() { return Doble(2); }
    protected override string ToString() { return ""; }
    public abstract void Abstracto();
}
public class Hijo : Base, IRepo { }
public readonly struct Unidad : IEquatable<Unidad> { }
public interface IRepo { int Cuenta(); }
public enum Color { Rojo, Verde }
"""


def _escribe(root, rel, texto):
    ruta = os.path.join(root, rel)
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write(texto)


def test_toda_forma_de_tipo_y_metodo_es_simbolo(tmp_path):
    root = str(tmp_path)
    _escribe(root, "Formas.cs", FORMAS)
    informe = lenguajes.analyze(root)
    quals = {n["qual"] for n in informe["nodes"]}

    for nombre in ("Punto", "Persona", "Utiles", "Hijo", "Unidad", "IRepo", "Color",
                   "Saluda", "CargaAsync", "Doble", "Nada", "ToString"):
        assert "Formas." + nombre in quals, nombre
    # sin cuerpo no es una definicion: ni el abstracto ni el miembro de interfaz
    assert "Formas.Abstracto" not in quals
    assert "Formas.Cuenta" not in quals
    llamadas = {(o, d) for o, d, t in informe["edges"] if t == "CALLS"}
    assert ("Formas.Nada", "Formas.Doble") in llamadas


def test_un_using_solo_es_interno_si_el_arbol_declara_el_namespace(tmp_path):
    root = str(tmp_path)
    # namespace de VARIOS ficheros: no hay destino unico
    _escribe(root, "tests/Contratos/Peticiones/Ping.cs", "namespace T.Contratos.Peticiones;\n")
    _escribe(root, "tests/Contratos/Peticiones/Pong.cs", "namespace T.Contratos.Peticiones;\n")
    # namespace de UN fichero, bajo una carpeta que no es su raiz
    _escribe(root, "tests/Contratos/Respuestas/Eco.cs",
             "﻿namespace T.Contratos.Respuestas;\npublic class Eco { }\n")
    # homonimos por el ultimo segmento: `Peticiones` y `Text`
    _escribe(root, "samples/Ejemplos/Peticiones.cs", "namespace Ejemplos;\n")
    _escribe(root, "src/Util/Text.cs", "namespace App.Util;\npublic class Text { }\n")
    _escribe(root, "tests/Usings.cs",
             "global using T.Contratos.Peticiones;\n"
             "global using T.Contratos.Respuestas;\n"
             "using System.Text;\n"
             "using static App.Util.Text;\n")
    informe = lenguajes.analyze(root)
    imports = {(o, d) for o, d, t in informe["edges"] if t == "IMPORTS"}
    desde = {d for o, d in imports if o == "tests.Usings"}

    assert "samples.Ejemplos.Peticiones" not in desde      # inventada por sufijo
    assert "tests.Contratos.Respuestas.Eco" in desde        # global using, 1 fichero
    assert "Util.Text" in desde                              # using static
    # y `using System.Text;` no es del arbol: sin la estatica no habria arista
    # (antes caia en `src/Util/Text.cs` por el ultimo segmento)
    _escribe(root, "tests/Usings.cs", "using System.Text;\n")
    informe = lenguajes.analyze(root)
    imports = {(o, d) for o, d, t in informe["edges"] if t == "IMPORTS"}
    assert ("tests.Usings", "Util.Text") not in imports
