"""Kotlin: los simbolos y los imports del Kotlin de verdad.

Medido sobre ajalt/colormath el 24-sep-2026 (banco de repos reales): 10 185
lineas daban 191 simbolos y 70 llamadas resueltas, porque los patrones solo
cazaban `fun x() { }` y `class X { }` desnudos — ni cuerpos de expresion, ni
funciones de extension, ni `override`, ni `data class`/`object`. Y los imports
caian en el bug de Java: `android.graphics.Color` en el `Color.kt` propio,
`...transform.sequence` en `Transform.kt` por el sufijo sin mayusculas. Al
reves, `import ...internal.doCreate` (una funcion de nivel superior, la forma
idiomatica) no dejaba arista porque el fichero no se llama como la funcion.
"""

import os

import pytest

from galaxybrain import lenguajes

pytestmark = pytest.mark.skipif(
    not lenguajes.binario(),
    reason="ast-grep no instalado; la capa multilenguaje es opcional (ADR 0009)",
)

FUENTE = """package app.modelo

private fun <T> List<T>.segundo(): T = this[1]

fun Color.luminancia(): Float {
    return 0f
}

internal inline fun <T : Color> T.acotar(x: Int): T = this

fun fabrica(n: Int): Plana = Plana(n)

data class Plana(val n: Int) : Color {
    override fun toString(): String = "Plana($n)"
    companion object {
        fun cero() = Plana(0)
    }
}

sealed class Sellada

object Unico {
    fun hola() = 1
}

interface Contrato {
    fun abstracto(): Int
    fun defecto() = 2
}

enum class Palo { A, B }
"""


def _escribe(raiz, rel, texto):
    ruta = os.path.join(raiz, *rel.split("/"))
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write(texto)


def test_formas_de_declaracion_son_simbolos(tmp_path):
    raiz = str(tmp_path / "kt")
    _escribe(raiz, "app/modelo/Formas.kt", FUENTE)
    nombres = {n["qual"].rsplit(".", 1)[-1] for n in lenguajes.analyze(raiz)["nodes"]
               if n["kind"] != "module"}
    esperados = {"segundo", "luminancia", "acotar", "fabrica", "Plana", "toString", "cero",
                 "Sellada", "Unico", "hola", "Contrato", "defecto", "Palo"}
    assert esperados <= nombres, esperados - nombres
    # sin cuerpo no hay codigo que llamar, igual que en Java
    assert "abstracto" not in nombres


def _aristas(raiz):
    return {(o, d) for o, d, t in lenguajes.analyze(raiz)["edges"] if t == "IMPORTS"}


def test_import_externo_no_cae_en_el_homonimo_propio(tmp_path):
    raiz = str(tmp_path / "kt")
    _escribe(raiz, "app/Color.kt", "package app\n\ninterface Color\n")
    _escribe(raiz, "app/transform/Transform.kt",
             "package app.transform\n\nfun mezcla(a: Int) = a\n")
    _escribe(raiz, "app/transform/Interpolate.kt",
             "package app.transform\n\nfun <T> List<T>.sequence(n: Int) = this\n")
    _escribe(raiz, "ext/Android.kt",
             "package ext\n\nimport android.graphics.Color\n"
             "import androidx.compose.ui.graphics.Color as ComposeColor\n"
             "import org.jetbrains.skia.ColorSpace.Companion\n"
             "import app.transform.sequence\n\nfun f() = 1\n")
    aristas = _aristas(raiz)
    assert ("ext.Android", "app.Color") not in aristas
    # `sequence` vive en Interpolate.kt; por el sufijo sin mayusculas
    # `app.transform` caia en `Transform.kt`
    assert ("ext.Android", "app.transform.Transform") not in aristas
    assert ("ext.Android", "app.transform.Interpolate") in aristas


def test_import_de_nivel_superior_va_al_fichero_que_lo_declara(tmp_path):
    raiz = str(tmp_path / "kt")
    _escribe(raiz, "app/internal/Utils.kt",
             "package app.internal\n\n"
             "internal inline fun <T> List<T>.doCreate(x: Int): T = this[x]\n")
    _escribe(raiz, "app/internal/Mates.kt",
             "package app.internal\n\nfun grados(x: Double) = x\n")
    _escribe(raiz, "app/modelo/Lab.kt",
             "package app.modelo\n\nobject LabSpaces {\n    val LAB50 = 1\n}\n")
    _escribe(raiz, "app/modelo/Uso.kt",
             "package app.modelo\n\nimport app.internal.doCreate\n"
             "import app.modelo.LabSpaces.LAB50\n\nfun g() = LAB50\n")
    aristas = _aristas(raiz)
    assert ("app.modelo.Uso", "app.internal.Utils") in aristas
    assert ("app.modelo.Uso", "app.internal.Mates") not in aristas
    # `LabSpaces` es un object dentro de Lab.kt: el import nombra su miembro
    assert ("app.modelo.Uso", "app.modelo.Lab") in aristas
