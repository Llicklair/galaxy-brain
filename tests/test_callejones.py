"""Una cadena de llamantes que se CORTA en un metodo no estrecha la seleccion.

bench_rust con rojos reales (24-sep-2026): rompiendo `iva`, el test que usa
`Precio::nuevo(..).con_iva()` se ponia rojo y no se elegia — `con_iva` llama a
`iva`, pero a `con_iva` solo se le llama sobre un valor, y eso no se resuelve
fuera de Python. La subida moria ahi y la seleccion quedaba corta.
"""

import os
import subprocess

import pytest

from galaxybrain import impacted, lenguajes

pytestmark = pytest.mark.skipif(
    not lenguajes.binario(),
    reason="ast-grep no instalado; la capa multilenguaje es opcional (ADR 0009)",
)


def _escribe(raiz, rel, texto):
    ruta = os.path.join(raiz, *rel.split("/"))
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write(texto)


def test_un_metodo_sin_llamantes_en_la_subida_corre_todo(tmp_path):
    raiz = str(tmp_path / "crate")
    _escribe(raiz, "src/lib.rs", "pub mod iva;\npub mod precio;\n")
    _escribe(raiz, "src/iva.rs", "pub fn iva() -> f64 {\n    0.21\n}\n")
    _escribe(raiz, "src/precio.rs",
             "use crate::iva::iva;\n\npub struct Precio { base: f64 }\n\n"
             "impl Precio {\n    pub fn con_iva(&self) -> f64 {\n        self.base * iva()\n    }\n}\n")
    _escribe(raiz, "tests/iva.rs",
             "use bench::iva::iva;\n\n#[test]\nfn va() {\n    let v = iva();\n    assert!(v > 0.0);\n}\n")
    _escribe(raiz, "tests/precio.rs",
             "use bench::precio::Precio;\n\n#[test]\nfn va() {\n    let p = Precio { base: 1.0 };\n"
             "    let v = p.con_iva();\n    assert!(v > 0.0);\n}\n")
    for args in (["init", "-q"], ["-c", "user.email=t@t", "-c", "user.name=t", "add", "-A"],
                 ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base"]):
        subprocess.run(["git", *args], cwd=raiz, check=True, capture_output=True)
    _escribe(raiz, "src/iva.rs", "pub fn iva() -> f64 {\n    0.10\n}\n")

    report = impacted.analyze(raiz, worktree=True, grafo=lenguajes.analyze(raiz))
    assert report["todo"] is True, report
    assert "con_iva" in report["motivo"], report["motivo"]
