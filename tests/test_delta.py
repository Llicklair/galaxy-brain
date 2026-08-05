"""`gb delta`: los errores clasicos medidos como delta, no como umbral.

El invariante que gobierna este fichero es el de los falsos positivos. Una senal
que se dispara por codigo que no cambio es exactamente lo que manda una revision
a `--no-verify`, y por eso hay mas tests de "esto NO debe avisar" que de "esto SI".
"""

import subprocess

import pytest

from galaxybrain import delta


def _git(root, *args):
    subprocess.run(["git"] + list(args), cwd=str(root), check=True,
                   capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path):
    """Un repo con deuda YA EXISTENTE: lo que no debe volver a contarse."""
    root = tmp_path / "proyecto"
    root.mkdir()
    (root / "lib.py").write_text(
        "def viejo():\n"
        "    try:\n"
        "        pass\n"
        "    except ValueError:\n"
        "        pass\n"
        "\n"
        "\n"
        "def otro():\n"
        "    return 1\n",
        encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t.t")
    _git(root, "config", "user.name", "t")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "base con deuda")
    return root


def _escribir(root, rel, texto):
    (root / rel).write_text(texto, encoding="utf-8")


def test_la_deuda_que_ya_estaba_no_se_cuenta(repo):
    """El corazon del comando: el `except: pass` viejo no es noticia."""
    _escribir(repo, "lib.py", (repo / "lib.py").read_text(encoding="utf-8") + "\n\ndef nueva():\n    return 2\n")
    report = delta.analyze(str(repo), worktree=True)
    assert delta.total(report) == 0, "solo se anadio una funcion limpia"


def test_un_error_que_se_traga_recien_anadido_si_sale(repo):
    _escribir(repo, "lib.py",
              "def viejo():\n"
              "    try:\n"
              "        pass\n"
              "    except ValueError:\n"
              "        pass\n"
              "\n"
              "\n"
              "def nueva():\n"
              "    try:\n"
              "        pass\n"
              "    except Exception:\n"
              "        pass\n")
    report = delta.analyze(str(repo), worktree=True)
    assert len(report["silencios"]) == 1
    assert report["silencios"][0]["file"] == "lib.py"
    assert "Exception" in report["silencios"][0]["what"]


def test_desplazar_codigo_no_inventa_senales(repo):
    """El falso positivo que mata la herramienta.

    Si se comparara por LINEA, anadir diez lineas arriba movería el `except` de
    sitio y lo marcaria como nuevo sin que nadie lo haya tocado. Se compara por
    texto justamente por esto.
    """
    viejo = (repo / "lib.py").read_text(encoding="utf-8")
    _escribir(repo, "lib.py", "\n".join("# relleno %d" % i for i in range(20)) + "\n" + viejo)
    report = delta.analyze(str(repo), worktree=True)
    assert delta.total(report) == 0


def test_borrar_deuda_no_cuenta_como_anadirla(repo):
    _escribir(repo, "lib.py", "def otro():\n    return 1\n")
    report = delta.analyze(str(repo), worktree=True)
    assert delta.total(report) == 0


def test_captura_amplia_que_hace_algo_se_separa_del_silencio(repo):
    """`except Exception:` que registra no es lo mismo que uno que se traga."""
    _escribir(repo, "lib.py",
              "def nueva():\n"
              "    try:\n"
              "        pass\n"
              "    except Exception as error:\n"
              "        print(error)\n")
    report = delta.analyze(str(repo), worktree=True)
    assert len(report["amplios"]) == 1
    assert report["silencios"] == []


def test_trabajo_pendiente_nuevo(repo):
    _escribir(repo, "lib.py",
              "def nueva():\n"
              "    # TODO: terminar esto\n"
              "    raise NotImplementedError\n")
    report = delta.analyze(str(repo), worktree=True)
    assert len(report["pendientes"]) == 2, "el TODO y el NotImplementedError"


def test_un_todo_dentro_de_una_cadena_no_es_trabajo_pendiente(repo):
    """Solo comentarios: contar la palabra en cualquier sitio seria ruido."""
    _escribir(repo, "lib.py", 'def nueva():\n    return "TODO esta en el texto"\n')
    report = delta.analyze(str(repo), worktree=True)
    assert report["pendientes"] == []


def test_un_cuerpo_que_crece_de_golpe_sale(repo):
    cuerpo = "\n".join("    x = %d" % i for i in range(40))
    _escribir(repo, "lib.py", "def otro():\n%s\n    return 1\n" % cuerpo)
    report = delta.analyze(str(repo), worktree=True)
    assert len(report["crecidos"]) == 1
    assert report["crecidos"][0]["name"] == "otro"
    assert report["crecidos"][0]["grew"] >= delta.CRECIMIENTO


def test_una_funcion_larga_que_no_cambia_no_es_noticia(repo):
    """No es un umbral sobre el tamano: es sobre el movimiento."""
    cuerpo = "\n".join("    x = %d" % i for i in range(50))
    _escribir(repo, "lib.py", "def grande():\n%s\n" % cuerpo)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "nace grande")

    _escribir(repo, "lib.py", "def grande():\n%s\n    y = 1\n" % cuerpo)
    report = delta.analyze(str(repo), worktree=True)
    assert report["crecidos"] == [], "crecio una linea: eso no es crecer de golpe"


def test_un_fichero_que_no_parsea_no_rompe_el_informe(repo):
    _escribir(repo, "lib.py", "def roto(:\n")
    report = delta.analyze(str(repo), worktree=True)
    assert report["range_error"] is None
    assert delta.total(report) == 0


def test_un_fichero_nuevo_entero_cuenta_lo_que_trae(repo):
    _escribir(repo, "nuevo.py",
              "def f():\n"
              "    try:\n"
              "        pass\n"
              "    except Exception:\n"
              "        pass\n")
    _git(repo, "add", "-A")
    report = delta.analyze(str(repo), staged=True)
    assert len(report["silencios"]) == 1


def test_sin_cambios_no_dice_nada(repo):
    report = delta.analyze(str(repo), worktree=True)
    assert delta.total(report) == 0
    assert report["ficheros"] == 0


def test_una_raiz_que_no_existe_es_error_de_uso(tmp_path):
    report = delta.analyze(str(tmp_path / "no-existe"))
    assert report["range_error"]
