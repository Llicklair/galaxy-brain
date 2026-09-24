"""FIRMA_CAMBIADA_SIN_LLAMANTES fuera de Python.

Hasta el 24-sep-2026 la señal solo existia en Python: la firma vieja salia de
`ast` y los nodos de los otros 16 lenguajes llevaban `sig` vacio. Ahora el motor
multilenguaje escribe la firma y la version de git de los ficheros tocados pasa
por el mismo motor. Mismo contrato que en Python: solo avisa de lo que ROMPE
llamadas (obligatorio nuevo, parametro que desaparece), nunca de un cambio
retrocompatible, del cuerpo, ni del formato.
"""

import os
import subprocess

import pytest

from galaxybrain import changes, cli, lenguajes

pytestmark = pytest.mark.skipif(
    not lenguajes.binario(),
    reason="ast-grep no instalado; la capa multilenguaje es opcional (ADR 0009)",
)


def _git(root, *args):
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
                   cwd=root, check=True, capture_output=True)


def _repo(tmp_path, suma_nueva):
    root = str(tmp_path / "ts")
    os.makedirs(root)
    with open(os.path.join(root, "lib.ts"), "w", encoding="utf-8") as fh:
        fh.write("export function suma(a: number, b: number) {\n  return a + b;\n}\n")
    with open(os.path.join(root, "app.ts"), "w", encoding="utf-8") as fh:
        fh.write("import { suma } from './lib';\n\nexport function usa() {\n  return suma(1, 2);\n}\n")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "base")
    with open(os.path.join(root, "lib.ts"), "w", encoding="utf-8") as fh:
        fh.write(suma_nueva)
    _git(root, "commit", "-qam", "cambia suma")
    report = changes.analyze(root, "HEAD~1..HEAD", informe_simbolos=cli._analiza_simbolos(root))
    return {f["signal"] for f in report["flags"]}


def test_un_obligatorio_nuevo_sin_tocar_al_llamante_da_senal(tmp_path):
    senales = _repo(tmp_path, "export function suma(a: number, b: number, c: number) {\n"
                              "  return a + b + c;\n}\n")
    assert "FIRMA_CAMBIADA_SIN_LLAMANTES" in senales


@pytest.mark.parametrize("nueva", [
    "export function suma(a: number, b: number, c = 0) {\n  return a + b + c;\n}\n",   # opcional
    "export function suma(a: number, b: number) {\n  return b + a;\n}\n",              # cuerpo
    "export function suma(a: number,\n                     b: number) {\n  return a + b;\n}\n",  # formato
])
def test_lo_retrocompatible_no_da_senal(tmp_path, nueva):
    assert "FIRMA_CAMBIADA_SIN_LLAMANTES" not in _repo(tmp_path, nueva)


def test_un_generico_con_comas_es_un_solo_parametro():
    assert not changes._firma_rompe_llamadas("(Map<String, Integer> m)", "(Map<String, Integer> m)")
    assert not changes._firma_rompe_llamadas("(Map<String, Integer> m)",
                                             "(Map<String, Integer> m, int b = 1)")
    assert changes._firma_rompe_llamadas("(Map<String, Integer> m)", "(Map<String, Integer> m, int b)")
