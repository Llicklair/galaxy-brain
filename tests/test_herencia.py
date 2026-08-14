"""La herencia propaga en la SELECCION: tocar la base arrastra los tests de
las subclases. Rojo real del 14-ago (cuentas-claras): con tests que solo
nombraban subclases, tocar la base daba "ningun test alcanza lo que
cambiaste" — la arista EXTENDS existia en el grafo y nadie la caminaba."""
import subprocess
import sys
import textwrap


def _repo(tmp_path):
    raiz = tmp_path / "proyecto"
    raiz.mkdir()
    (raiz / "reglas.py").write_text(textwrap.dedent('''
        class Regla:
            def partes(self, total, cuantos):
                if cuantos <= 0:
                    raise ValueError("nadie entre quien repartir")
                return self._trocea(total, cuantos)

            def _trocea(self, total, cuantos):
                raise NotImplementedError


        class Iguales(Regla):
            def _trocea(self, total, cuantos):
                return [total // cuantos] * cuantos


        class Fija(Regla):
            def _trocea(self, total, cuantos):
                return [total] + [0] * (cuantos - 1)
    '''), encoding="utf-8")
    (raiz / "tests").mkdir()
    (raiz / "tests" / "test_reglas.py").write_text(textwrap.dedent('''
        from reglas import Iguales


        def test_iguales_reparte():
            assert Iguales().partes(9, 3) == [3, 3, 3]
    '''), encoding="utf-8")
    (raiz / "sin_relacion.py").write_text("def suelta():\n    return 1\n",
                                          encoding="utf-8")
    (raiz / "tests" / "test_suelta.py").write_text(
        "from sin_relacion import suelta\n\n\ndef test_suelta():\n"
        "    assert suelta() == 1\n", encoding="utf-8")
    (raiz / "tests" / "test_fija.py").write_text(textwrap.dedent('''
        from reglas import Fija


        def test_fija_carga_al_primero():
            assert Fija().partes(9, 3) == [9, 0, 0]
    '''), encoding="utf-8")
    for orden in (["git", "init", "-q"],
                  ["git", "add", "-A"],
                  ["git", "-c", "user.name=t", "-c", "user.email=t@t.t",
                   "commit", "-q", "-m", "base"]):
        subprocess.run(orden, cwd=str(raiz), timeout=60)
    return raiz


def _tests_worktree(raiz):
    # cwd, no positional: `gb tests [range] [path]` interpreta un unico
    # positional como RANGO (mordio en este mismo test: analizo el repo padre)
    p = subprocess.run(
        [sys.executable, "-m", "galaxybrain.cli", "tests", "--worktree",
         "--json"],
        cwd=str(raiz), capture_output=True, text=True, timeout=180)
    assert p.returncode == 0, p.stderr[:300]
    import json
    return json.loads(p.stdout)


def test_tocar_la_base_arrastra_los_tests_de_la_subclase(tmp_path):
    raiz = _repo(tmp_path)
    # el bug del agente: un token en el METODO DE LA BASE
    reglas = raiz / "reglas.py"
    reglas.write_text(reglas.read_text(encoding="utf-8").replace(
        "cuantos <= 0", "cuantos < 0"), encoding="utf-8")
    seleccion = _tests_worktree(raiz)
    assert not seleccion.get("todo"), seleccion.get("motivo")
    ficheros = " ".join(seleccion.get("tests") or [])
    assert "test_reglas" in ficheros         # llega POR LA HERENCIA
    assert "test_suelta" not in ficheros     # y no arrastra al resto


def test_tocar_una_subclase_no_arrastra_a_su_hermana(tmp_path):
    """La direccion importa: extends sube de la subclase a la base, nunca
    baja ni cruza — tocar Iguales no puede arrastrar los tests de Fija."""
    raiz = _repo(tmp_path)
    sub = raiz / "reglas.py"
    sub.write_text(sub.read_text(encoding="utf-8").replace(
        "class Iguales(Regla):",
        'class Iguales(Regla):\n    """a partes iguales"""'), encoding="utf-8")
    seleccion = _tests_worktree(raiz)
    assert not seleccion.get("todo"), seleccion.get("motivo")
    ficheros = " ".join(seleccion.get("tests") or [])
    assert "test_reglas" in ficheros         # su propio test, claro
    assert "test_fija" not in ficheros       # la hermana ni se entera
    assert "test_suelta" not in ficheros     # y el resto tampoco
