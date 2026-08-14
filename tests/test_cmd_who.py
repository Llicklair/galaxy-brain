"""`gb who`: la superficie CLI de la actividad derivada.

La mecanica de `instantanea()` ya la cubre test_actividad.py; aqui se prueba
solo el contrato del comando — que existe, que termina bien y que dice la
verdad cuando no hay nada que derivar.
"""

import os
import subprocess
import sys

import pytest


def _who(*args, env=None):
    entorno = dict(os.environ)
    if env:
        entorno.update(env)
    return subprocess.run(
        [sys.executable, "-m", "galaxybrain.cli", "who", *args],
        capture_output=True, text=True, timeout=180, env=entorno)


def test_sin_git_lo_dice_y_no_revienta(tmp_path):
    (tmp_path / "calc.py").write_text("def suma(a, b):\n    return a + b\n",
                                      encoding="utf-8")
    p = _who(str(tmp_path))
    assert p.returncode == 0
    assert "sin repositorio git" in p.stdout


def test_html_refresca_el_mapa_de_la_raiz_si_ya_existe(tmp_path):
    """Un mapa.html en la raiz es la costumbre del usuario declarada en disco:
    --html sin ruta lo refresca a EL, no a la copia de GB_HOME que no mira
    nadie (medido 14-ago: el principal se pudrio mientras gb escribia fuera).
    """
    raiz = tmp_path / "proyecto"
    raiz.mkdir()
    (raiz / "calc.py").write_text("def suma(a, b):\n    return a + b\n",
                                  encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=str(raiz), timeout=60)
    viejo = raiz / "mapa.html"
    viejo.write_text("<html>foto vieja</html>", encoding="utf-8")
    hogar = tmp_path / "hogar"
    p = _who(str(raiz), "--html", env={"GB_HOME": str(hogar)})
    assert p.returncode == 0
    nuevo = viejo.read_text(encoding="utf-8")
    assert "foto vieja" not in nuevo and "lienzo" in nuevo
    if hogar.exists():
        assert not list(hogar.glob("*/mapa.html"))


def test_html_es_el_canvas_con_su_consola(tmp_path):
    """El mapa principal es el canvas de viz.py (restaurado 14-ago): el grafo
    navegable y la consola de errores, no una pagina de presencia."""
    raiz = tmp_path / "proyecto"
    raiz.mkdir()
    (raiz / "calc.py").write_text("def suma(a, b):\n    return a + b\n",
                                  encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=str(raiz), timeout=60)
    destino = raiz / "mapa.html"
    p = _who(str(raiz), "--html", str(destino),
             env={"GB_HOME": str(tmp_path / "hogar")})
    assert p.returncode == 0
    html = destino.read_text(encoding="utf-8")
    assert '<canvas id="lienzo">' in html
    assert "const CAPTURAS" in html   # la consola de errores viaja siempre
    assert "GEN_TS" in html           # y la actividad envejece en el navegador
    # el cajon de archivos: modal de codigo estilo gitnexus + salto al editor
    assert 'id="archivos"' in html and "btnArchivos" in html
    assert "const ARCHIVOS" in html and "vscode://file/" in html
    assert "calc.py" in html          # el fichero del proyecto esta en el cajon
    assert 'id="codigo"' in html and ", CODIGO = " in html
    assert "def suma(a, b):" in html  # el CODIGO viaja embebido, listo p/modal
    assert "muestraFicha(fijado)" in html  # el clic enciende nodo + tarjeta
    assert "window.onerror" in html and "EL LIENZO PETO" in html  # confiesa
    assert 'id="nacedero"' in html    # la cuna de las estrellas nuevas


def test_html_sin_mapa_en_la_raiz_escribe_fuera_del_proyecto(tmp_path):
    raiz = tmp_path / "proyecto"
    raiz.mkdir()
    (raiz / "calc.py").write_text("def suma(a, b):\n    return a + b\n",
                                  encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=str(raiz), timeout=60)
    hogar = tmp_path / "hogar"
    p = _who(str(raiz), "--html", env={"GB_HOME": str(hogar)})
    assert p.returncode == 0
    assert not (raiz / "mapa.html").exists()
    assert list(hogar.glob("*/mapa.html"))


def test_la_foto_vieja_se_confiesa_en_el_canvas(tmp_path):
    """El fosil del 14-ago: un mapa parado tiene que declararse viejo SOLO.
    El aviso viaja oculto desde el primer segundo y el JS solo lo destapa."""
    raiz = tmp_path / "proyecto"
    raiz.mkdir()
    (raiz / "calc.py").write_text("def suma(a, b):\n    return a + b\n",
                                  encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=str(raiz), timeout=60)
    destino = raiz / "mapa.html"
    p = _who(str(raiz), "--html", str(destino),
             env={"GB_HOME": str(tmp_path / "hogar")})
    assert p.returncode == 0
    html = destino.read_text(encoding="utf-8")
    assert 'id="vieja"' in html
    assert "LIMITE_FOTO = 600" in html   # foto unica: la ventana de presencia
    assert "en reposo" in html           # gris informativo, no alarma
    assert "f85149" not in html.split('id="vieja"')[1][:300]  # sin rojo de averia


def test_el_limite_de_foto_no_deriva_de_la_ventana_de_presencia():
    from galaxybrain import viz
    from galaxybrain.actividad import VENTANA_COMMIT

    assert viz._limite_foto(0) == VENTANA_COMMIT  # duplicado a proposito
    # con watch mandan los LATIDOS, no los ticks: el watch solo re-renderiza
    # al cambiar algo, y reescribe cada LATIDO_WATCH como minimo
    assert viz._limite_foto(3) == 3 * viz.LATIDO_WATCH
    assert viz._limite_foto(60) == 180            # ticks largos: 3 ticks
    assert "YA NO ESCRIBE" in viz._aviso_vieja(3)
    assert "reposo" in viz._aviso_vieja(0)
    # el rojo de averia es SOLO del watch muerto; el reposo va en gris
    assert "f85149" in viz._estilo_vieja(3)
    assert "f85149" not in viz._estilo_vieja(0)


def test_el_js_del_mapa_compila(tmp_path):
    """Un error de sintaxis en el JS deja el mapa EN BLANCO entero (paso el
    14-ago: un \\n sin escapar en la plantilla — Python lo convirtio en salto
    de linea DENTRO de un string JS y ningun test lo vio). node --check caza
    la clase completa, no el caso: cualquier rotura sintactica futura."""
    import re
    import shutil
    node = shutil.which("node")
    if not node:
        pytest.skip("sin node en la maquina")
    raiz = tmp_path / "proyecto"
    raiz.mkdir()
    (raiz / "calc.py").write_text("def suma(a, b):\n    return a + b\n",
                                  encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=str(raiz), timeout=60)
    destino = raiz / "mapa.html"
    p = _who(str(raiz), "--html", str(destino),
             env={"GB_HOME": str(tmp_path / "hogar")})
    assert p.returncode == 0
    scripts = re.findall(r"<script>(.*?)</script>",
                         destino.read_text(encoding="utf-8"), re.S)
    assert scripts
    js = tmp_path / "mapa.js"
    js.write_text("\n;\n".join(scripts), encoding="utf-8")
    q = subprocess.run([node, "--check", str(js)], capture_output=True,
                       text=True, timeout=60)
    assert q.returncode == 0, q.stderr[:400]


def test_un_modulo_naciendo_sale_con_su_nombre(tmp_path):
    """El agente que crea un modulo NUEVO era el mas invisible (tirada de
    cuatro): ahora su fichero aun-sin-nodo viaja con nombre en `nacientes`."""
    raiz = tmp_path / "proyecto"
    raiz.mkdir()
    (raiz / "calc.py").write_text("def suma(a, b):\n    return a + b\n",
                                  encoding="utf-8")
    for orden in (["git", "init", "-q"], ["git", "add", "-A"],
                  ["git", "-c", "user.name=t", "-c", "user.email=t@t.t",
                   "commit", "-q", "-m", "base"]):
        subprocess.run(orden, cwd=str(raiz), timeout=60)
    wt = tmp_path / "wt-agente"
    subprocess.run(["git", "worktree", "add", str(wt), "-b", "agente-x"],
                   cwd=str(raiz), capture_output=True, timeout=60)
    (wt / "novedad.py").write_text("def brilla():\n    return 1\n",
                                   encoding="utf-8")
    import json
    p = subprocess.run(
        [sys.executable, "-m", "galaxybrain.cli", "who", "--json"],
        cwd=str(raiz), capture_output=True, text=True, timeout=180)
    assert p.returncode == 0, p.stderr[:300]
    agentes = {a["nombre"]: a for a in json.loads(p.stdout)["agentes"]}
    assert agentes["wt-agente"]["nacientes"] == ["novedad"]


def test_json_trae_las_claves_del_contrato(tmp_path):
    import json

    (tmp_path / "calc.py").write_text("def suma(a, b):\n    return a + b\n",
                                      encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), timeout=60)
    p = _who(str(tmp_path), "--json")
    assert p.returncode == 0
    foto = json.loads(p.stdout)
    for clave in ("base", "agentes", "por_nodo", "cruces"):
        assert clave in foto
