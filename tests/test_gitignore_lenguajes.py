"""Lo que el repo ya ignora no entra en el grafo — se lee de git, no se adivina.

`SKIP` es una lista fija y por tanto siempre incompleta: acierta con
`node_modules` y falla con lo que cada proyecto decida. Salio de este mismo repo
el 16-ago-2026: al empezar a leer los otros lenguajes en repos con Python, el
mapa paso de 100 modulos a 218, y 112 de ellos eran nodos sueltos sin una sola
arista — 27 de un directorio de temporales de pytest **que git ya ignoraba**.

Cablear ese nombre en SKIP habria sido project-specific (regla 6). Lo que un
proyecto considera "no es mi codigo" ya esta escrito en su `.gitignore`.
"""

import os
import subprocess

import pytest

from galaxybrain import lenguajes

necesita_git = pytest.mark.skipif(
    not lenguajes.shutil.which("git"), reason="sin git no hay .gitignore que leer"
)


def _repo(raiz, gitignore=None):
    os.makedirs(os.path.join(raiz, "src"), exist_ok=True)
    os.makedirs(os.path.join(raiz, "generado"), exist_ok=True)
    for rel in ("src/bueno.ts", "generado/generado.ts"):
        with open(os.path.join(raiz, *rel.split("/")), "w", encoding="utf-8") as fh:
            fh.write("export function f() { return 1; }\n")
    if gitignore is not None:
        with open(os.path.join(raiz, ".gitignore"), "w", encoding="utf-8") as fh:
            fh.write(gitignore)
    return raiz


def _vistos(raiz):
    return sorted(os.path.relpath(r, raiz).replace(os.sep, "/")
                  for r, _ in lenguajes._ficheros(raiz))


@necesita_git
def test_lo_ignorado_por_el_repo_no_entra_en_el_grafo(tmp_path):
    raiz = _repo(str(tmp_path), gitignore="generado/\n")
    subprocess.run(["git", "-C", raiz, "init", "-q"], check=True)
    assert _vistos(raiz) == ["src/bueno.ts"]


@necesita_git
def test_sin_reglas_no_se_filtra_nada(tmp_path):
    """Un repo sin `.gitignore` no pierde ni un fichero: el filtro solo quita
    lo que su duenno ya habia declarado basura."""
    raiz = _repo(str(tmp_path))
    subprocess.run(["git", "-C", raiz, "init", "-q"], check=True)
    assert _vistos(raiz) == ["generado/generado.ts", "src/bueno.ts"]


def test_sin_git_se_ve_todo_en_vez_de_esconder(tmp_path):
    """Degradar hacia INFORMAR DE MAS. Quedarse corto se ve y se corrige;
    esconder codigo en silencio es el falso verde que ADR 0010 mato."""
    raiz = _repo(str(tmp_path), gitignore="generado/\n")   # sin `git init`
    assert _vistos(raiz) == ["generado/generado.ts", "src/bueno.ts"]


def test_preguntar_a_git_no_cuesta_un_proceso_por_fichero(tmp_path, monkeypatch):
    """El presupuesto de latencia (regla 2) no aguanta cientos de procesos: la
    consulta es UNA, con `--stdin`."""
    raiz = _repo(str(tmp_path), gitignore="generado/\n")
    llamadas = []
    real = subprocess.run

    def contando(cmd, *a, **k):
        if isinstance(cmd, (list, tuple)) and "check-ignore" in cmd:
            llamadas.append(cmd)
        return real(cmd, *a, **k)

    monkeypatch.setattr(lenguajes.subprocess, "run", contando)
    lenguajes._ficheros(raiz)
    assert len(llamadas) <= 1
