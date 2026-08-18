"""El mapa no puede heredar el sitio de OTRO grafo.

El navegador guarda las posiciones ya convergidas para que un refresco no haga
bailar el mapa. La clave de ese guardado era solo el TÍTULO del documento — el
mismo (`mapa · galaxy-brain`) para cualquier alcance y cualquier versión del
grafo. Y cuando las posiciones guardadas cubren todos los nodos, el JS da la
física por terminada (`iter = MAXIT`): se pinta con los sitios viejos sobre
aristas nuevas, sin lanzar nada y sin avisar.

Lo destapó Marcos el 18-ago-2026: el MISMO fichero se veía con dos formas
distintas en el navegador y en el integrado de VS Code — uno traía posiciones
guardadas y el otro arrancaba limpio.

Con la huella del DATO en la clave, un grafo distinto no puede heredar el sitio
de otro, y dos navegadores con el mismo grafo convergen a la misma forma: la
siembra es determinista (hash, cero `Math.random`).
"""

import re

from galaxybrain import graph, symbols, viz


def _mapa(root):
    return viz.render_graph_cloud(symbols.analyze(root),
                                  graph_report=graph.analyze(root), gen_ts=0)


def _huella(html):
    m = re.search(r"const HUELLA = '([0-9a-f]+)'", html)
    return m.group(1) if m else None


def _escribe(tmp, rel, texto=""):
    import os
    p = os.path.join(str(tmp), *rel.split("/"))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(texto)


def test_el_mapa_lleva_huella_del_dato(tmp_path):
    _escribe(tmp_path, "app/__init__.py")
    _escribe(tmp_path, "app/web.py", "import os\n")
    assert _huella(_mapa(str(tmp_path)))


def test_el_mismo_grafo_da_la_misma_huella(tmp_path):
    """Si no fuera estable, cada regeneración tiraría las posiciones y el mapa
    bailaría en cada refresco — que es justo lo que el guardado venía a evitar."""
    _escribe(tmp_path, "app/__init__.py")
    _escribe(tmp_path, "app/web.py", "import os\n")
    assert _huella(_mapa(str(tmp_path))) == _huella(_mapa(str(tmp_path)))


def test_otro_grafo_da_OTRA_huella(tmp_path):
    """El caso que importa: si aparece una arista, las posiciones guardadas ya
    no describen este grafo y no deben reutilizarse."""
    _escribe(tmp_path, "app/__init__.py")
    _escribe(tmp_path, "app/web.py")
    _escribe(tmp_path, "app/db.py")
    antes = _huella(_mapa(str(tmp_path)))

    _escribe(tmp_path, "app/web.py", "from app import db\n")   # arista nueva
    assert _huella(_mapa(str(tmp_path))) != antes


def test_la_clave_de_posiciones_la_incluye(tmp_path):
    _escribe(tmp_path, "app/__init__.py")
    _escribe(tmp_path, "app/web.py", "import os\n")
    html = _mapa(str(tmp_path))
    assert "'gb-pos:' + document.title + ':' + HUELLA" in html
