"""SWE-bench Verified, los casos DIFICILES, sin Docker: ¿aporta gb donde Opus falla?

    python bancos/swe_extremos/correr.py validar [--ids a,b]   # juez local vs oficial, gratis
    python bancos/swe_extremos/correr.py lista

Fase 1 (README.md): el juez local tiene que dar el veredicto oficial antes de gastar
nada en agentes — sin el parche de referencia, FAIL_TO_PASS falla; con el, todo
FAIL_TO_PASS y PASS_TO_PASS pasa. La instancia que no lo cumple se descarta y se
dice por que (Python 3.11 sin pines de version es la amenaza conocida).

Datos fuera del repo: ../ab-gb/swe/ (dataset, clones, venvs). Herramienta para el
parquet: el venv ../ab-gb/swe/herramientas (pyarrow); este script solo lee el JSON.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ_GB = os.path.dirname(os.path.dirname(AQUI))
SWE = os.path.join(os.path.dirname(RAIZ_GB), "ab-gb", "swe")
DIFICILES = ("1-4 hours", ">4 hours")
#: Repos cuyo runner es pytest: gb no sabe correr `tests/runtests.py` de Django
#: (descuadre de cobertura anotado el 2-oct-2026), y astropy/sklearn compilan C.
REPOS = ("sympy/sympy", "sphinx-doc/sphinx", "pytest-dev/pytest", "pylint-dev/pylint",
         "pydata/xarray")
#: Lo que cada repo necesita ademas de `pip install -e .`. Sin pines: la que no
#: instale o no reproduzca el veredicto con Python 3.11 se cae en `validar`.
EXTRA = {
    "sympy/sympy": ["pytest", "mpmath"],
    "sphinx-doc/sphinx": ["pytest", "html5lib", "cython"],
    "pytest-dev/pytest": ["hypothesis", "xmlschema", "pygments", "nose", "mock", "requests"],
    "pylint-dev/pylint": ["pytest", "pytest-timeout"],
    "pydata/xarray": ["pytest"],
}


def instancias():
    todas = json.load(open(os.path.join(SWE, "verified.json"), encoding="utf-8"))
    return [r for r in todas if r["difficulty"] in DIFICILES and r["repo"] in REPOS]


def _corre(cmd, cwd, timeout=1800, entrada=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout, input=entrada,
                       env=dict(os.environ, GB_DISABLE="1", PYTHONIOENCODING="utf-8"))
    return r.returncode, r.stdout + r.stderr


def _git(cwd, *args, entrada=None):
    return _corre(["git"] + list(args), cwd, entrada=entrada)


def montar(r):
    """Clon en su commit base + venv con el repo instalado. Devuelve (repo, python)."""
    nombre = r["repo"].replace("/", "__")
    espejo = os.path.join(SWE, "espejos", nombre + ".git")
    if not os.path.exists(espejo):
        os.makedirs(os.path.dirname(espejo), exist_ok=True)
        rc, out = _corre(["git", "clone", "-q", "--bare",
                          "https://github.com/%s.git" % r["repo"], espejo], SWE, timeout=3600)
        if rc:
            raise RuntimeError("clone: " + out[-500:])
    base = os.path.join(SWE, "inst", r["instance_id"])
    repo, venv = os.path.join(base, "repo"), os.path.join(base, "venv")
    python = os.path.join(venv, "Scripts", "python.exe")
    if not os.path.exists(repo):
        os.makedirs(base, exist_ok=True)
        _corre(["git", "clone", "-q", "--shared", espejo, repo], SWE)
        _git(repo, "checkout", "-q", r["base_commit"])
        _git(repo, "config", "user.email", "ab@local")
        _git(repo, "config", "user.name", "ab")
    if not os.path.exists(python):
        _corre([sys.executable, "-m", "venv", venv], base)
        rc, out = _corre([python, "-m", "pip", "install", "-q", "-e", "."] + EXTRA[r["repo"]], repo,
                         timeout=3600)
        open(os.path.join(base, "pip.log"), "w", encoding="utf-8").write(out)
        if rc:
            raise RuntimeError("pip: " + out[-800:])
    return repo, python


def ficheros_de_test(r):
    return sorted(set(re.findall(r"^diff --git a/(\S+) ", r["test_patch"], re.M)))


def _resultados(salida):
    """{nodeid: 'PASSED'|'FAILED'|'ERROR'|...} de la linea corta de `pytest -rA`."""
    estados = {}
    for linea in salida.splitlines():
        m = re.match(r"^(PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS) (.+?)(?: - .*)?$", linea)
        if m and "::" in m.group(2):
            estados[m.group(2)] = m.group(1)
            # El dataset oficial corta los nombres en el primer espacio
            # (`test_mark_option[(((`): esa clave tambien, y si varios
            # parametros la comparten, gana el ultimo — como en el parser
            # oficial. Lo que se busca es SU veredicto, no uno mejor.
            corto = m.group(2).split(" ")[0]
            if corto != m.group(2):
                estados[corto] = m.group(1)
    return estados


def _estado(nombre, estados):
    """El estado de un test de la lista oficial. Los de sympy vienen sin ruta."""
    if nombre in estados:
        return estados[nombre]
    sufijos = [v for k, v in estados.items() if k.endswith("::" + nombre)]
    return sufijos[0] if len(sufijos) == 1 else None


def juzgar(r, repo, python, parche):
    """Aplica `parche` (codigo) y el test_patch oficial sobre la base; corre los tests
    de la instancia. {resuelta, f2p, p2p, fallan}. Deja el repo en la base."""
    _git(repo, "reset", "-q", "--hard", r["base_commit"])
    _git(repo, "clean", "-qfd")
    try:
        if parche:
            rc, out = _git(repo, "apply", "-", entrada=parche)
            if rc:
                return {"resuelta": False, "motivo": "el parche no aplica: " + out[-300:]}
        rc, out = _git(repo, "apply", "-", entrada=r["test_patch"])
        if rc:
            return {"resuelta": False, "motivo": "el test_patch no aplica: " + out[-300:]}
        rc, salida = _corre([python, "-m", "pytest", "-rA", "-p", "no:cacheprovider", "-q"]
                            + ficheros_de_test(r), repo, timeout=3600)
        estados = _resultados(salida)
        f2p, p2p = json.loads(r["FAIL_TO_PASS"]), json.loads(r["PASS_TO_PASS"])
        verde = lambda n: _estado(n, estados) in ("PASSED", "XFAIL")
        fallan = [n for n in f2p + p2p if not verde(n)]
        return {"resuelta": not fallan,
                "f2p": "%d/%d" % (sum(map(verde, f2p)), len(f2p)),
                "p2p": "%d/%d" % (sum(map(verde, p2p)), len(p2p)),
                "fallan": fallan[:10], "cola": salida[-1500:] if not estados else ""}
    finally:
        _git(repo, "reset", "-q", "--hard", r["base_commit"])
        _git(repo, "clean", "-qfd")


def validar(ids=None):
    filas = []
    for r in instancias():
        if ids and r["instance_id"] not in ids:
            continue
        fila = {"id": r["instance_id"]}
        try:
            repo, python = montar(r)
            sin = juzgar(r, repo, python, None)
            con = juzgar(r, repo, python, r["patch"])
            f2p_sin = sin.get("f2p", "?/?").split("/")
            fila.update(sin_parche=sin, con_oro=con,
                        valida=con["resuelta"] and f2p_sin[0] != f2p_sin[1])
        except Exception as error:          # una instancia rota no para el resto
            fila.update(valida=False, motivo=str(error)[-600:])
        filas.append(fila)
        print("%-32s %s  sin=%s oro=%s/%s %s" % (
            fila["id"], "VALIDA" if fila["valida"] else "fuera ",
            fila.get("sin_parche", {}).get("f2p"), fila.get("con_oro", {}).get("f2p"),
            fila.get("con_oro", {}).get("p2p"),
            (fila.get("motivo") or fila.get("con_oro", {}).get("motivo") or "")[:120]), flush=True)
    previas = {}
    ruta = os.path.join(SWE, "validacion.json")
    if os.path.exists(ruta):
        previas = {f["id"]: f for f in json.load(open(ruta, encoding="utf-8"))}
    previas.update({f["id"]: f for f in filas})
    json.dump(list(previas.values()), open(ruta, "w", encoding="utf-8"), indent=2)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("accion", choices=("validar", "lista"))
    p.add_argument("--ids")
    a = p.parse_args()
    if a.accion == "lista":
        for r in instancias():
            print(r["instance_id"], r["difficulty"])
    else:
        validar(set(a.ids.split(",")) if a.ids else None)


if __name__ == "__main__":
    main()
