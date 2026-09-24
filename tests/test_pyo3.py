"""Python -> Rust por pyo3, con los dos lados escritos.

Medido el 24-sep-2026 sobre tach y watchfiles: 44 de 45 usos se resuelven por
nombre literal y gb no veia ninguno. Casos: el renombre `#[pyo3(name = ...)]`,
el homonimo que el registro desempata (la `fn` del fichero del pymodule), el
`from pkg import modulo` + `modulo.x`, y el pymodule con argumentos.
"""

import os
import subprocess

import pytest

from galaxybrain import cli, lenguajes

pytestmark = pytest.mark.skipif(
    not lenguajes.binario(),
    reason="ast-grep no instalado; la capa multilenguaje es opcional (ADR 0009)",
)


def _escribe(raiz, rel, texto):
    ruta = os.path.join(raiz, *rel.split("/"))
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write(texto)


def test_python_llama_a_lo_que_registra_el_pymodule(tmp_path):
    raiz = str(tmp_path / "proy")
    _escribe(raiz, "src/lib.rs",
             "mod sync;\n\n"
             "#[pyfunction]\n#[pyo3(name = \"check\")]\nfn check_internal(x: i32) -> i32 {\n    x\n}\n\n"
             "#[pyfunction]\npub fn sync_project(a: i32) -> i32 {\n    sync::sync_project(a)\n}\n\n"
             "#[pyclass]\npub struct Motor {\n    x: i32,\n}\n\n"
             "#[pymodule(gil_used = false)]\nfn extension(m: &Bound<PyModule>) -> PyResult<()> {\n"
             "    m.add_function(wrap_pyfunction!(check_internal, m)?)?;\n"
             "    m.add_function(wrap_pyfunction!(sync_project, m)?)?;\n"
             "    m.add_class::<Motor>()?;\n    Ok(())\n}\n")
    _escribe(raiz, "src/sync.rs", "pub fn sync_project(a: i32) -> i32 {\n    a\n}\n")
    _escribe(raiz, "pkg/__init__.py", "")
    _escribe(raiz, "pkg/cli.py",
             "from pkg.extension import Motor, sync_project as sincroniza\n"
             "from pkg import extension\n\n\n"
             "def corre():\n    return extension.check(1)\n\n\n"
             "def arranca():\n    return Motor()\n\n\n"
             "def sincro():\n    return sincroniza(1)\n")
    subprocess.run(["git", "init", "-q"], cwd=raiz, check=True, capture_output=True)

    informe = cli._analiza_simbolos(raiz)
    llamadas = {(o, d) for o, d, t in informe["edges"] if t == "CALLS"}
    assert ("pkg.cli.corre", "lib.check_internal") in llamadas, llamadas          # renombre
    assert ("pkg.cli.arranca", "lib.Motor") in llamadas, llamadas                 # clase
    assert ("pkg.cli.sincro", "lib.sync_project") in llamadas, llamadas           # homonimo
    assert ("pkg.cli.sincro", "sync.sync_project") not in llamadas
    importa = {(o, d) for o, d, t in informe["edges"] if t == "IMPORTS"}
    assert ("pkg.cli", "lib") in importa, importa


def test_pyo3_entra_en_el_grafo_de_modulos(tmp_path):
    """Para ciclos y fronteras del gate hace falta la arista de MODULO, que
    sale del constructor de `graph`, no del informe de simbolos."""
    test_python_llama_a_lo_que_registra_el_pymodule(tmp_path)
    raiz = str(tmp_path / "proy")
    _nodos, aristas, _err = cli._constructor_fusionado(raiz)
    assert "lib" in aristas.get("pkg.cli", set()), aristas.get("pkg.cli")
