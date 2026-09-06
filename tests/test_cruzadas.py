"""Las llamadas entre lenguajes que se leen del código, sin ejecutarlo.

Dos cifras que no son la misma y por eso no se mezclan: el SITIO de llamada
(sintaxis: sale siempre) y el DESTINO (solo si está escrito ahí). Medido sobre
el banco de `gb-lenguajes`: 13 de 13 sitios en el proyecto políglota, 0 %
destinos porque el comando viaja en una variable; y 100 % cuando la ruta está
escrita, que es el caso corriente de un repo mixto.
"""

import os

from galaxybrain import cruzadas


def _escribe(raiz, nombre, texto):
    ruta = os.path.join(str(raiz), nombre)
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write(texto)
    return ruta


def test_el_sitio_de_llamada_sale_en_todos_los_lenguajes(tmp_path):
    """Encontrar «aquí se lanza un proceso» es sintaxis pura: no depende de
    resolver nombres, así que acierta siempre."""
    _escribe(tmp_path, "a.js", 'spawnSync("x");\n')
    _escribe(tmp_path, "b.rb", 'system("x")\n')
    _escribe(tmp_path, "c.lua", 'os.execute("x")\n')
    _escribe(tmp_path, "d.php", '<?php passthru("x");\n')
    _escribe(tmp_path, "e.go", 'exec.Command("x")\n')
    _escribe(tmp_path, "f.rs", 'Command::new("x")\n')

    langs = {s["lang"] for s in cruzadas.sitios(str(tmp_path))}
    assert langs == {"js", "rb", "lua", "php", "go", "rs"}


def test_el_destino_sale_cuando_esta_escrito(tmp_path):
    _escribe(tmp_path, "cliente.js", 'spawnSync("ruby", ["motor.rb"]);\n')
    _escribe(tmp_path, "motor.rb", "puts 1\n")

    sitio = [s for s in cruzadas.sitios(str(tmp_path)) if s["lang"] == "js"][0]
    assert os.path.basename(sitio["destino"]) == "motor.rb"


def test_tambien_dentro_de_una_linea_de_comando_entera(tmp_path):
    """`os.execute("php x.php")` es un solo literal con el comando dentro.
    Mirar solo el literal completo perdía justo estas — y son mayoría en lua,
    php y C, los que ejecutan por shell. Medido: 60 % -> 100 %."""
    _escribe(tmp_path, "arranque.lua", 'os.execute("php motor.php")\n')
    _escribe(tmp_path, "motor.php", "<?php echo 1;\n")

    sitio = [s for s in cruzadas.sitios(str(tmp_path)) if s["lang"] == "lua"][0]
    assert os.path.basename(sitio["destino"]) == "motor.php"


def test_lo_que_viene_de_una_variable_NO_se_inventa(tmp_path):
    """Una arista inventada es peor que un hueco: manda a leer el fichero que
    no es. El sitio se devuelve igual —saber que ESE fichero lanza algo es un
    hecho— pero sin destino."""
    _escribe(tmp_path, "cliente.js", "spawnSync(process.env.CMD);\n")
    _escribe(tmp_path, "motor.rb", "puts 1\n")

    sitio = [s for s in cruzadas.sitios(str(tmp_path)) if s["lang"] == "js"][0]
    assert sitio["destino"] is None


def test_un_literal_que_no_esta_en_el_arbol_tampoco_cuenta(tmp_path):
    """«ruby» o «python» son literales, no ficheros del proyecto. Sin esta
    comprobación, cualquier cadena de texto se convertiría en una arista."""
    _escribe(tmp_path, "cliente.js", 'spawnSync("ruby", ["-e", "puts 1"]);\n')

    sitio = cruzadas.sitios(str(tmp_path))[0]
    assert sitio["destino"] is None


def test_la_arista_casa_con_nodos_de_cualquier_extension(tmp_path):
    """`graph.module_name` corta tres caracteres porque es de y para Python: con
    `.lua` devolvía `arranque.` —con el punto colgando— y la arista no casaba
    con ningún nodo del mapa. Se veía como «0 aristas» sin decir por qué."""
    _escribe(tmp_path, "arranque.lua", 'os.execute("php motor.php")\n')
    _escribe(tmp_path, "motor.php", "<?php echo 1;\n")
    informe = {"nodes": [{"kind": "module", "qual": "arranque"},
                         {"kind": "module", "qual": "motor"}]}

    aristas = cruzadas.aristas(str(tmp_path), informe)
    assert [(a["de"], a["a"]) for a in aristas] == [("arranque", "motor")]


def test_sin_nodos_en_el_mapa_no_hay_media_arista(tmp_path):
    _escribe(tmp_path, "arranque.lua", 'os.execute("php motor.php")\n')
    _escribe(tmp_path, "motor.php", "<?php echo 1;\n")

    assert cruzadas.aristas(str(tmp_path), {"nodes": []}) == []


def test_toda_clase_de_arista_del_mapa_tiene_leyenda():
    """El contrato que evita el fallo de raíz: la leyenda se GENERA de la tabla
    de clases, así que no se puede añadir una línea al mapa y olvidarse de
    nombrarla. Antes eran dos trozos de código distintos escritos a mano, y por
    eso la rosa y la ámbar se pintaron sin nombre durante tres commits."""
    from galaxybrain import viz

    for clase in viz.CLASES_ARISTA:
        assert clase["etiqueta"], "%s sin etiqueta" % clase["clave"]
        assert clase["color"].startswith("#"), "%s sin color" % clase["clave"]

    presentes = {c["clave"]: True for c in viz.CLASES_ARISTA}
    html = viz._leyenda_aristas(presentes)
    for clase in viz.CLASES_ARISTA:
        assert clase["etiqueta"] in html


def test_la_leyenda_NO_nombra_lo_que_no_esta_en_pantalla():
    """En un repo de un solo lenguaje, «lanza otro lenguaje» manda a buscar una
    línea que no existe. Nombrar de más es tan malo como nombrar de menos."""
    from galaxybrain import viz

    html = viz._leyenda_aristas({"import": True})
    assert "import (exacto)" in html
    assert "lanza otro lenguaje" not in html
    assert "lo lanzo" not in html


def test_mencionar_un_lanzador_en_un_comentario_NO_es_lanzar(tmp_path):
    """El caso real (26-ago-2026): `impacted.py` salio en el mapa con la marca
    de «lanza un proceso» por citar `subprocess.run(` en un comentario `#:`.
    Un sitio que no es codigo manda a leer una llamada que no existe."""
    _escribe(tmp_path, "a.py", "#: para el AST, `subprocess.run([...])` es una llamada\nx = 1\n")
    _escribe(tmp_path, "b.js", "// aqui NO se usa spawnSync(cmd)\nlet y = 1;\n")
    _escribe(tmp_path, "c.lua", "-- os.execute(cmd) queda prohibido aqui\nlocal z = 1\n")
    _escribe(tmp_path, "d.java", " * Runtime.getRuntime().exec(cmd) — javadoc\nclass D {}\n")

    assert cruzadas.sitios(str(tmp_path)) == []


def test_el_comentario_no_tapa_el_codigo_de_la_linea_siguiente(tmp_path):
    """La otra mitad del criterio: quitar comentarios no puede costar sitios
    reales. El mismo fichero, comentario arriba y llamada de verdad debajo."""
    _escribe(tmp_path, "real.py",
             "# subprocess.run() se documenta aqui\nimport subprocess\nsubprocess.run(['x'])\n")

    sitios = cruzadas.sitios(str(tmp_path))
    assert [s["linea"] for s in sitios] == [3]


def test_la_arista_de_lanzamiento_entra_al_grafo(tmp_path):
    """Un spawn con el destino ESCRITO y unico en el arbol tiene el rango de un
    import: esta en el codigo y se lee sin ejecutar. Desde el 6-sep-2026 entra
    al grafo con todos los derechos — ciclos, fan-in/out, fronteras — en vez de
    quedarse en candidata del mapa."""
    from galaxybrain import cli, graph

    _escribe(tmp_path, "orquestador.py",
             'import subprocess\nsubprocess.run(["node", "motor.js"])\n')
    _escribe(tmp_path, "motor.js", "console.log(1);\n")

    report = graph.analyze(str(tmp_path), constructor=cli._constructor_fusionado)
    assert ["orquestador", "motor"] in report["edge_list"]
    assert any(a["de"] == "orquestador" and a["a"] == "motor"
               for a in report["aristas_lanzamiento"])


def test_un_ciclo_entre_lenguajes_bloquea_el_gate(tmp_path):
    """py lanza js y js lanza py: un ciclo real que ningun import confiesa.
    Antes el gate pasaba en verde con el acoplamiento delante."""
    from galaxybrain import cli, graph

    _escribe(tmp_path, "a.py", 'import subprocess\nsubprocess.run(["node", "b.js"])\n')
    _escribe(tmp_path, "b.js", 'spawnSync("python", ["a.py"]);\n')

    report = graph.analyze(str(tmp_path), constructor=cli._constructor_fusionado)
    assert report["cycles"], "el ciclo de lanzamientos no se detecto"
    assert cli._graph_gate(report) != 0


def test_un_basename_ambiguo_no_fabrica_arista(tmp_path):
    """Dos ficheros con el mismo nombre en carpetas distintas: el literal ya no
    dice a cual apunta. Antes ganaba el primero del paseo — la arista al
    fichero que no es, el fallo exacto que este modulo promete no fabricar."""
    from galaxybrain import cli, graph

    _escribe(tmp_path, "cliente.py",
             'import subprocess\nsubprocess.run(["node", "motor.js"])\n')
    os.makedirs(os.path.join(str(tmp_path), "uno"))
    os.makedirs(os.path.join(str(tmp_path), "dos"))
    _escribe(tmp_path, os.path.join("uno", "motor.js"), "console.log(1);\n")
    _escribe(tmp_path, os.path.join("dos", "motor.js"), "console.log(2);\n")

    report = graph.analyze(str(tmp_path), constructor=cli._constructor_fusionado)
    assert report["aristas_lanzamiento"] == []


def test_en_un_arbol_de_un_solo_lenguaje_no_se_pasea(tmp_path):
    """El guardian de latencia: sin mezcla de lenguajes no hay cruce posible y
    no se paga el paseo. El lanzamiento py->py queda fuera a proposito — lo
    prometido es la interconexion ENTRE lenguajes (decidido el 6-sep-2026)."""
    from galaxybrain import graph

    _escribe(tmp_path, "a.py", 'import subprocess\nsubprocess.run(["python", "b.py"])\n')
    _escribe(tmp_path, "b.py", "x = 1\n")

    report = graph.analyze(str(tmp_path))
    assert report["aristas_lanzamiento"] == []
