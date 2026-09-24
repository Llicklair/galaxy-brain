"""Un import solo resuelve contra modulos de SU familia de lenguajes.

pot-desktop (24-sep-2026): `use crate::APP;` en Rust casaba, sin mayusculas,
con `src/App.jsx`, y salian aristas Rust -> JSX inventadas. Un import de Rust no
puede apuntar a JavaScript; lo que cruza de lenguaje (lanzamientos, FFI) va por
su propio camino, con su propia evidencia.
"""

import os

import pytest

from galaxybrain import lenguajes

pytestmark = pytest.mark.skipif(
    not lenguajes.binario(),
    reason="ast-grep no instalado; la capa multilenguaje es opcional (ADR 0009)",
)


def _escribe(raiz, rel, texto):
    ruta = os.path.join(raiz, *rel.split("/"))
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write(texto)


def test_un_use_de_rust_no_cae_en_un_jsx_homonimo(tmp_path):
    raiz = str(tmp_path / "app")
    _escribe(raiz, "src-tauri/src/main.rs", "mod cmd;\nmod util;\nstatic APP: i32 = 1;\nfn main() {}\n")
    _escribe(raiz, "src-tauri/src/cmd.rs",
             "use crate::APP;\nuse crate::util::ayuda;\npub fn f() -> i32 { ayuda() }\n")
    _escribe(raiz, "src-tauri/src/util.rs", "pub fn ayuda() -> i32 { 1 }\n")
    _escribe(raiz, "src/App.jsx", "import x from './otro';\nexport default function App() { return x; }\n")
    _escribe(raiz, "src/otro.js", "export default 1;\n")

    aristas = {(o, d) for o, d, t in lenguajes.analyze(raiz)["edges"] if t == "IMPORTS"}
    assert ("src-tauri.src.cmd", "App") not in aristas, aristas
    assert ("src-tauri.src.cmd", "src-tauri.src.util") in aristas, aristas
    assert ("App", "otro") in aristas, aristas
