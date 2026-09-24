"""`invoke('x')` en el frontend de Tauri -> la `fn x` marcada `#[tauri::command]`.

El enlace entre lenguajes mas comun de una app Tauri, con los dos lados
literales: medido el 24-sep-2026 sobre pot-desktop y clash-verge-rev, 116 de 116
sitios con destino unico, y gb no veia ninguno. Solo con nombre escrito y un
unico comando; `plugin:...` o un nombre en variable no dejan arista.
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


def test_invoke_literal_llama_al_comando_rust(tmp_path):
    raiz = str(tmp_path / "app")
    _escribe(raiz, "src-tauri/src/cmd.rs",
             "#[tauri::command]\npub async fn guardar<R: Runtime>(app: AppHandle<R>, x: i32) "
             "-> Result<(), String> {\n    Ok(())\n}\n\n"
             "#[tauri::command]\nfn abrir() {}\n")
    _escribe(raiz, "src/App.tsx",
             "import { invoke } from '@tauri-apps/api/core';\n\n"
             "export function Boton() {\n  return invoke<void>('guardar', { x: 1 });\n}\n"
             "export function Otro(cmd: string) {\n"
             "  invoke(cmd);\n  invoke('plugin:dialog|open');\n  return invoke(\"abrir\");\n}\n")
    informe = lenguajes.analyze(raiz)
    llamadas = {(o, d) for o, d, t in informe["edges"] if t == "CALLS"}
    assert ("App.Boton", "src-tauri.src.cmd.guardar") in llamadas, llamadas
    assert ("App.Otro", "src-tauri.src.cmd.abrir") in llamadas, llamadas
    importa = {(o, d) for o, d, t in informe["edges"] if t == "IMPORTS"}
    assert ("App", "src-tauri.src.cmd") in importa, importa
    # la variable y el plugin no inventan nada
    assert not [d for o, d in llamadas if o == "App.Otro" and d != "src-tauri.src.cmd.abrir"]


def test_rust_async_y_generico_es_simbolo(tmp_path):
    """Los patrones literales de Rust perdian `async fn`, genericos y `where`."""
    raiz = str(tmp_path / "r")
    _escribe(raiz, "a.rs", "pub async fn uno<R: Send>(a: i32) -> Result<(), String> where R: Sync {\n"
                           "    Ok(())\n}\nstruct S { x: i32 }\nimpl S { pub fn dos(&self) {} }\n"
                           "trait T { fn tres(&self); }\n")
    nombres = {n["qual"] for n in lenguajes.analyze(raiz)["nodes"]}
    assert {"a.uno", "a.dos", "a.S", "a.T"} <= nombres, nombres
    assert "a.tres" not in nombres, "un fn de trait sin cuerpo no es una definicion"
