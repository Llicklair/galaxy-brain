"""`ipcRenderer.invoke('canal')` -> quien registra `ipcMain.handle('canal')`.

Medido el 24-sep-2026: en marktext 76 de 81 envios con canal literal y un solo
receptor; en Motrix <1% (canales en constantes). Por eso solo canal escrito,
receptor unico, y fuera de tests.
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


def test_el_envio_literal_llega_a_su_unico_receptor(tmp_path):
    raiz = str(tmp_path / "app")
    _escribe(raiz, "main/ipc.ts",
             "import { ipcMain } from 'electron';\n\n"
             "export function registra() {\n"
             "  ipcMain.handle('guardar', async (_e, x) => { return x; });\n"
             "  ipcMain.on('doble', () => {});\n}\n"
             "export function otro() {\n  ipcMain.on('doble', () => {});\n}\n")
    _escribe(raiz, "test/falso.test.ts",
             "import { ipcMain } from 'electron';\nipcMain.handle('guardar', () => 0);\n")
    _escribe(raiz, "renderer/boton.ts",
             "import { ipcRenderer } from 'electron';\n\n"
             "export function boton(canal: string) {\n"
             "  ipcRenderer.invoke('guardar', 1);\n"
             "  ipcRenderer.send(canal);\n"
             "  ipcRenderer.send('doble');\n}\n")
    informe = lenguajes.analyze(raiz)
    llamadas = {(o, d) for o, d, t in informe["edges"] if t == "CALLS"}
    assert ("renderer.boton.boton", "main.ipc.registra") in llamadas, llamadas
    # 'doble' tiene dos receptores y `canal` es una variable: ninguna arista mas
    assert not any(d == "main.ipc.otro" for _o, d in llamadas), llamadas
    assert informe["unresolved"].get("ipc-sin-receptor-unico") == 1
    importa = {(o, d) for o, d, t in informe["edges"] if t == "IMPORTS"}
    assert ("renderer.boton", "main.ipc") in importa, importa
