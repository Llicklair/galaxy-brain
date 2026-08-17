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


@necesita_git
def test_un_proyecto_dentro_de_un_directorio_ignorado_sigue_teniendo_grafo(tmp_path):
    """El repo padre ignora la raiz -> sus reglas NO gobiernan dentro de ella.

    `git -C` escala hasta el repo que contenga la ruta. Analizar un proyecto que
    vive bajo un directorio ignorado por el padre (`tmp*/`, `vendor/`, el
    `pytest-of-*/` de esta misma suite) hacia que TODOS sus ficheros salieran
    ignorados: grafo vacio, sin un solo aviso. Costo 124 tests el 17-ago-2026, y
    en uso real es `gb graph <ruta>` devolviendo cero modulos en verde.
    """
    padre = str(tmp_path)
    subprocess.run(["git", "-C", padre, "init", "-q"], check=True)
    with open(os.path.join(padre, ".gitignore"), "w", encoding="utf-8") as fh:
        fh.write("aparte/\n")

    raiz = _repo(os.path.join(padre, "aparte"))          # sin `.gitignore` propio
    assert _vistos(raiz) == ["generado/generado.ts", "src/bueno.ts"]


@necesita_git
def test_la_raiz_ignorada_no_desactiva_su_propio_gitignore(tmp_path):
    """Desactivar el filtro del PADRE no es desactivar el del proyecto: si la
    raiz trae reglas propias, esas mandan."""
    padre = str(tmp_path)
    subprocess.run(["git", "-C", padre, "init", "-q"], check=True)
    with open(os.path.join(padre, ".gitignore"), "w", encoding="utf-8") as fh:
        fh.write("aparte/\n")

    raiz = _repo(os.path.join(padre, "aparte"), gitignore="generado/\n")
    subprocess.run(["git", "-C", raiz, "init", "-q"], check=True)   # repo propio
    assert _vistos(raiz) == ["src/bueno.ts"]


def test_preguntar_a_git_no_cuesta_un_proceso_por_fichero(tmp_path, monkeypatch):
    """El presupuesto de latencia (regla 2) no aguanta cientos de procesos.

    Lo que se fija no es un numero magico, es la FORMA del coste: constante en el
    numero de ficheros. Con `--stdin` la consulta es una, mas la que pregunta si
    la propia raiz esta ignorada; ninguna de las dos depende del barrido.
    """
    raiz = _repo(str(tmp_path), gitignore="generado/\n")
    llamadas = []
    real = subprocess.run

    def contando(cmd, *a, **k):
        if isinstance(cmd, (list, tuple)) and "check-ignore" in cmd:
            llamadas.append(cmd)
        return real(cmd, *a, **k)

    monkeypatch.setattr(lenguajes.subprocess, "run", contando)
    lenguajes._ficheros(raiz)
    pocos = len(llamadas)

    destino = os.path.join(raiz, "src")
    for i in range(40):
        with open(os.path.join(destino, "m%d.ts" % i), "w", encoding="utf-8") as fh:
            fh.write("export const x = %d;\n" % i)
    llamadas.clear()
    lenguajes._ficheros(raiz)
    assert len(llamadas) == pocos <= 2
