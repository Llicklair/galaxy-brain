"""El JavaScript del mapa tiene que PARSEAR, no solo contener las cadenas.

Nacio de un fallo real y caro (1-ago-2026): se anadio `const esc` para escapar
nombres, sin ver que `esc` ya existia y era la ESCALA del zoom. Un `const`
duplicado en el mismo ambito es un SyntaxError, o sea el script entero muerto, o
sea la pagina en blanco — en LOS DOS repos, no solo en el que se noto.

Y 358 tests en verde mientras tanto. Todos comprobaban que las cadenas
estuvieran, ninguno que el script se pudiera ejecutar. Es exactamente el patron
que este proyecto persigue: una comprobacion que mira la forma y no el hecho.

Dos redes, a proposito:

1. La de siempre, sin dependencias: declaraciones duplicadas en el ambito
   superior. Es la clase exacta del fallo y no necesita nada instalado.
2. La completa, si hay Node: `node --check` parsea de verdad y caza todo lo
   demas. Se salta si no esta — y al saltarse lo DICE, porque un test que no
   corre no es un test que pasa.
"""

import collections
import re
import shutil
import subprocess

import pytest

from galaxybrain import graph, symbols, viz


def _js(tmp_path):
    ruta = tmp_path / "pkg"
    ruta.mkdir()
    (ruta / "__init__.py").write_text('"""Paquete."""\n', encoding="utf-8")
    (ruta / "a.py").write_text(
        '"""Modulo A."""\n\n\ndef f():\n    """Hace algo."""\n    return 1\n', encoding="utf-8"
    )
    html = viz.render_graph_cloud(
        symbols.analyze(str(tmp_path)), graph_report=graph.analyze(str(tmp_path))
    )
    return re.search(r"<script>(.*)</script>", html, re.S).group(1)


def _declaraciones_de_nivel_superior(js):
    """`const`/`let` al margen izquierdo: el ambito donde una colision mata todo.

    Se separa por comas de PRIMER nivel: `const a = 1, b = 2` son dos, pero la
    coma de `{x:1, y:2}` o la de `(a, b) => ...` no separa nada. La primera
    version de esto solo miraba tras las comas, asi que se dejaba justo el primer
    nombre de cada linea — que era el del fallo. Lo caza el test de abajo.
    """
    nombres = []
    for linea in js.splitlines():
        m = re.match(r"^(?:const|let)\s+(.*)$", linea)
        if not m:
            continue
        profundidad, trozo, partes = 0, "", []
        for caracter in m.group(1):
            if caracter in "([{":
                profundidad += 1
            elif caracter in ")]}":
                profundidad -= 1
            if caracter == "," and profundidad == 0:
                partes.append(trozo)
                trozo = ""
            else:
                trozo += caracter
        partes.append(trozo)
        for parte in partes:
            nombre = re.match(r"\s*([A-Za-z_$][\w$]*)\s*=", parte)
            if nombre:
                nombres.append(nombre.group(1))
    return nombres


def test_ninguna_declaracion_del_ambito_superior_se_repite(tmp_path):
    """El fallo exacto que tumbo el mapa, cazado sin necesitar Node."""
    nombres = _declaraciones_de_nivel_superior(_js(tmp_path))
    assert nombres, "no se encontro ninguna declaracion: el detector no esta mirando"
    repetidas = {n: c for n, c in collections.Counter(nombres).items() if c > 1}
    assert not repetidas, "declaradas dos veces (SyntaxError, pagina en blanco): %s" % repetidas


def test_el_detector_de_duplicados_detecta_de_verdad():
    """Vigilar al vigilante: si el detector no ve una colision evidente, los dos
    tests de arriba son decoracion."""
    js = "const uno = 1;\nlet dos = 2;\nconst uno = 3;\n"
    nombres = _declaraciones_de_nivel_superior(js)
    repetidas = {n: c for n, c in collections.Counter(nombres).items() if c > 1}
    assert repetidas == {"uno": 2}


def test_el_detector_ve_el_PRIMER_nombre_de_cada_linea():
    """La version inicial solo miraba tras las comas y se dejaba el primero — que
    era justo donde estaba el fallo real. Sin este test, el detector habria
    parecido funcionar contando otras 21 declaraciones."""
    assert _declaraciones_de_nivel_superior("const esc = 1;\n") == ["esc"]
    assert _declaraciones_de_nivel_superior("const a = 1, b = 2;\n") == ["a", "b"]


def test_una_coma_dentro_de_llaves_no_separa_declaraciones():
    """`{x:1, y:2}` es un valor, no dos declaraciones. Contarlo lo seria daria
    falsos positivos, y un detector que grita sin motivo acaba desactivado."""
    assert _declaraciones_de_nivel_superior("const mapa = {x:1, y:2};\n") == ["mapa"]
    assert _declaraciones_de_nivel_superior("const f = (a, b = 2) => a;\n") == ["f"]


def test_habria_cazado_EL_fallo(tmp_path):
    """La prueba que decide si todo esto sirve: las dos lineas reales que
    tumbaron el mapa, tal cual estaban en la plantilla."""
    js = (
        "let esc=1, ox=0, oy=0, camaraLibre=false;\n"
        "const escapa = s => String(s);\n"
        "const esc = s => String(s).replace(/[&<>\"]/g, c => c);\n"
    )
    nombres = _declaraciones_de_nivel_superior(js)
    repetidas = {n: c for n, c in collections.Counter(nombres).items() if c > 1}
    assert repetidas == {"esc": 2}, "el detector NO habria visto el fallo: %s" % nombres


@pytest.mark.skipif(shutil.which("node") is None, reason="sin Node: parseo completo no disponible")
def test_node_parsea_el_script_entero(tmp_path):
    """La red completa. Caza cualquier error de sintaxis, no solo los duplicados."""
    destino = tmp_path / "mapa.js"
    destino.write_text(_js(tmp_path), encoding="utf-8")
    resultado = subprocess.run(
        ["node", "--check", str(destino)], capture_output=True, text=True, timeout=60
    )
    assert resultado.returncode == 0, resultado.stderr


def test_la_consola_deriva_los_hechos_correctos(tmp_path):
    """La logica de la consola EJECUTADA con node, no solo parseada.

    La diferencia entre dos instantaneas tiene que producir exactamente los
    hechos que pasaron: escribio, creo, aparecio, toco, cruce, se fue. Y soltar
    un nodo solo se dice de quien sigue vivo — el que se fue ya tiene su evento.
    """
    if shutil.which("node") is None:
        pytest.skip("sin node no se puede EJECUTAR el script del mapa")
    import json

    js = _js(tmp_path)
    m = re.search(r"function eventosEntre\(prev, ahora\)\{[\s\S]*?\n\}", js)
    assert m, "la funcion de la consola tiene que estar en el mapa"
    arnes = m.group(0) + """
const prev = {ag:{a1:{hace:50,fuera:0,nodos:1}}, nodos:{'m.x':['a1']}};
const ahora = {ag:{a1:{hace:2,fuera:1,nodos:2}, a2:{hace:1,fuera:0,nodos:1}},
               nodos:{'m.x':['a1','a2'], 'm.y':['a2']}};
console.log(JSON.stringify(eventosEntre(prev, ahora)));
console.log(JSON.stringify(eventosEntre(ahora, {ag:{a2:ahora.ag.a2}, nodos:{'m.y':['a2']}})));
"""
    destino = tmp_path / "consola.js"
    destino.write_text(arnes, encoding="utf-8")
    r = subprocess.run(["node", str(destino)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    linea1, linea2 = r.stdout.strip().splitlines()

    tipos1 = {(e["a"], e["t"]) for e in json.loads(linea1)}
    assert ("a1", "escribe") in tipos1        # hace bajo de 50s a 2s: escribio
    assert ("a1", "crea") in tipos1           # fuera subio de 0 a 1
    assert ("a2", "aparece") in tipos1
    assert ("a2", "toca") in tipos1           # entro en m.x y m.y
    assert ("a1 + a2", "CRUCE") in tipos1     # m.x paso de 1 a 2 agentes
    assert ("a1", "aparece") not in tipos1    # ya estaba: aparecer seria mentir

    tipos2 = {(e["a"], e["t"]) for e in json.loads(linea2)}
    assert ("a1", "se va") in tipos2
    assert ("a1", "suelta") not in tipos2
