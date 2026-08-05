"""Reglas de frontera (`.gb-boundaries`): declarar qué capa no puede importar a
cuál y fallar en los cruces. Un cruce prohibido es un hecho (lo declaraste), así
que la barra de casi-cero-falsos-positivos se cubre comprobando (a) que sin
fichero no hay reglas y (b) que la frontera es de punto (no casa por prefijo laxo)."""

import os

from galaxybrain import cli, graph, render


def _write(root, rel, content):
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def _plain(report):
    return render.render_graph(report, render.Style(False))


def test_cero_reglas_no_puede_ser_mudo(tmp_path):
    """El peor modo de fallo de un gate: pasar en verde sin comprobar nada.

    Antes, la rama de cero reglas era la UNICA muda — con reglas se leia "Sin
    cruces (N regla(s))" y sin reglas no salia nada, asi que "no he mirado" era
    indistinguible de "esta limpio". Encontrado usando la herramienta de verdad.
    """
    root = str(tmp_path)
    _write(root, "pkg/__init__.py", "")
    _write(root, "pkg/a.py", "")

    salida = _plain(graph.analyze(root))
    assert "0 reglas cargadas" in salida
    assert graph.BOUNDARIES_FILE in salida  # y DONDE se busco: sin eso no es accionable


def test_sin_fichero_en_ningun_sitio_el_gate_pasa(tmp_path):
    """Las fronteras son opt-in: no declararlas es legitimo y no puede bloquear."""
    root = str(tmp_path)
    _write(root, "pkg/__init__.py", "")
    _write(root, "pkg/a.py", "")

    report = graph.analyze(root)
    assert report["boundaries_elsewhere"] is None
    assert cli._graph_gate(report) == 0


def test_un_fichero_mal_COLOCADO_tumba_el_gate(tmp_path):
    """El caso real: `.gb-boundaries` en la raiz del repo y se analiza `src/`.

    Nadie recibe un error, se cargan cero reglas y el verde se lee como
    "comprobado y limpio". Aqui el verde significaria "no he mirado".
    """
    root = str(tmp_path)
    _write(root, ".gb-boundaries", "pkg.a -/-> pkg.b\n")
    _write(root, "src/pkg/__init__.py", "")
    _write(root, "src/pkg/a.py", "from pkg import b\n")
    _write(root, "src/pkg/b.py", "")

    report = graph.analyze(os.path.join(root, "src"))
    assert report["boundaries"] == 0
    assert report["boundaries_elsewhere"] is not None
    assert cli._graph_gate(report) == 1
    assert "no se esta aplicando" in _plain(report)


def test_un_fichero_en_src_se_ENCUENTRA_analizando_desde_la_raiz(tmp_path):
    """Hacia abajo NO se denuncia: se encuentra y se aplica.

    Es el hallazgo 6 del uso real. `gb graph src` cargaba 33 reglas y `gb check`
    —que analiza desde la raiz del repo— cargaba CERO con el mismo fichero, asi
    que esa mitad de la gate llevaba tiempo siendo decorativa. Denunciarlo habria
    sido mejor que callarlo, pero encontrarlo es mejor que denunciarlo: las dos
    rutas tienen que dar el MISMO numero o la incoherencia vuelve por otro lado.
    """
    root = str(tmp_path)
    _write(root, "src/.gb-boundaries", "pkg.a -/-> pkg.b\n")
    _write(root, "src/pkg/__init__.py", "")
    _write(root, "src/pkg/a.py", "from pkg import b\n")
    _write(root, "src/pkg/b.py", "")

    desde_raiz = graph.analyze(root)
    desde_src = graph.analyze(os.path.join(root, "src"))

    assert desde_raiz["boundaries"] == desde_src["boundaries"] == 1
    assert desde_raiz["boundaries_elsewhere"] is None  # no esta extraviado: se uso
    # y el cruce se ve desde las dos, que es lo que de verdad estaba roto
    assert len(desde_raiz["violations"]) == 1
    assert len(desde_src["violations"]) == 1
    assert cli._graph_gate(desde_raiz) == 1  # falla por el CRUCE, no por config


def test_hacia_ARRIBA_se_denuncia_en_vez_de_adoptarse(tmp_path):
    """Subir podria agarrar el fichero del proyecto que te contiene, y aplicar
    fronteras ajenas es peor que no aplicar ninguna. Por eso ese caso se dice."""
    root = str(tmp_path)
    _write(root, ".gb-boundaries", "pkg.a -/-> pkg.b\n")
    _write(root, "sub/pkg/__init__.py", "")
    _write(root, "sub/pkg/a.py", "")

    report = graph.analyze(os.path.join(root, "sub"))
    assert report["boundaries"] == 0
    assert report["boundaries_elsewhere"] is not None
    assert cli._graph_gate(report) == 1


def test_el_fichero_que_SI_se_lee_no_cuenta_como_extraviado(tmp_path):
    """Contra el falso positivo obvio: encontrarse a si mismo y fallar siempre."""
    root = str(tmp_path)
    _write(root, ".gb-boundaries", "pkg.a -/-> pkg.b\n")
    _write(root, "pkg/__init__.py", "")
    _write(root, "pkg/a.py", "")
    _write(root, "pkg/b.py", "")

    report = graph.analyze(root)
    assert report["boundaries"] == 1
    assert report["boundaries_elsewhere"] is None
    assert cli._graph_gate(report) == 0


def test_load_boundaries_parsea(tmp_path):
    root = str(tmp_path)
    _write(
        root,
        ".gb-boundaries",
        "# reglas de capas\n  web -/-> db  \n\ndomain -/-> web   # comentario\nlinea sin flecha\n",
    )
    parsed = graph.load_boundaries(root)
    rules = parsed["rules"]
    assert ("web", "db") in rules
    assert ("domain", "web") in rules
    assert len(rules) == 2  # los comentarios se ignoran
    assert "linea sin flecha" in parsed["malformed"]  # línea con contenido pero sin -/-> : se avisa
    assert parsed["error"] is None


def test_under_es_frontera_de_punto():
    assert graph._under("myapp.web", "myapp.web")
    assert graph._under("myapp.web.handlers", "myapp.web")
    assert not graph._under("myapp.website", "myapp.web")  # sin falso positivo por prefijo laxo
    assert not graph._under("myapp", "myapp.web")


def test_analyze_detecta_cruce_prohibido(tmp_path):
    root = str(tmp_path)
    _write(root, ".gb-boundaries", "app.web -/-> app.db\n")
    _write(root, "app/__init__.py", "")
    _write(root, "app/web.py", "from app import db\n")  # cruce prohibido
    _write(root, "app/db.py", "")

    report = graph.analyze(root)
    assert report["boundaries"] == 1
    assert any(
        v["importer"] == "app.web" and v["imported"] == "app.db" for v in report["violations"]
    )


def test_sin_fichero_de_fronteras_no_hay_reglas(tmp_path):
    root = str(tmp_path)
    _write(root, "app/__init__.py", "")
    _write(root, "app/web.py", "from app import db\n")
    _write(root, "app/db.py", "")

    report = graph.analyze(root)  # la gate de fronteras es opt-in
    assert report["boundaries"] == 0
    assert report["violations"] == []


def test_frontera_de_punto_no_da_falso_positivo(tmp_path):
    root = str(tmp_path)
    _write(root, ".gb-boundaries", "app.web -/-> app.db\n")
    _write(root, "app/__init__.py", "")
    _write(root, "app/website.py", "from app import db\n")  # website != web: NO viola
    _write(root, "app/db.py", "")

    assert graph.analyze(root)["violations"] == []


def test_regla_que_no_casa_ningun_modulo_se_avisa(tmp_path):
    """El footgun: una regla que no casa con nada (typo o raíz equivocada) nunca
    dispara y da falsa sensación de cobertura. Debe avisarse."""
    root = str(tmp_path)
    _write(root, ".gb-boundaries", "app.web -/-> app.db\ninexistente.x -/-> app.db\n")
    _write(root, "app/__init__.py", "")
    _write(root, "app/web.py", "")
    _write(root, "app/db.py", "")

    report = graph.analyze(root)
    avisadas = [u["rule"] for u in report["unmatched_rules"]]
    assert "inexistente.x -/-> app.db" in avisadas
    assert "app.web -/-> app.db" not in avisadas  # esa sí casa (web y db existen)


def test_regla_con_flecha_mal_escrita_es_malformed_no_muda(tmp_path):
    """El footgun del review: `-->` en vez de `-/->` antes se descartaba en
    silencio y la frontera no enforced nada sin aviso."""
    root = str(tmp_path)
    _write(root, ".gb-boundaries", "app.web --> app.db\n")  # flecha mal
    _write(root, "app/__init__.py", "")

    report = graph.analyze(root)
    assert report["boundaries"] == 0
    assert "app.web --> app.db" in report["malformed_boundaries"]


def test_dos_flechas_en_una_linea_es_malformed(tmp_path):
    root = str(tmp_path)
    _write(root, ".gb-boundaries", "a -/-> b -/-> c\n")
    _write(root, "app/__init__.py", "")

    report = graph.analyze(root)
    assert report["boundaries"] == 0  # no produce una regla basura
    assert report["malformed_boundaries"]


def test_boundaries_explicito_inexistente_es_error(tmp_path):
    root = str(tmp_path)
    _write(root, "app/__init__.py", "")
    report = graph.analyze(root, boundaries=os.path.join(root, "no-existe.txt"))
    assert report["boundaries_error"]  # ruta explícita ausente -> error, no silencio


def test_default_ausente_no_es_error(tmp_path):
    root = str(tmp_path)
    _write(root, "app/__init__.py", "")
    report = graph.analyze(root)  # sin fichero por defecto = opt-in, sin error
    assert report["boundaries_error"] is None


def test_gate_falla_con_config_de_reglas_rota(tmp_path):
    """La gate NUNCA pasa en verde con reglas que no enforced nada."""
    root = str(tmp_path)
    _write(root, "app/__init__.py", "")

    from galaxybrain import cli

    _write(root, ".gb-boundaries", "app.web --> app.db\n")  # flecha mal
    assert cli.main(["graph", root, "--gate", "--color", "never"]) == 1

    _write(root, ".gb-boundaries", "inexistente.x -/-> tampoco.y\n")  # no casa nada
    assert cli.main(["graph", root, "--gate", "--color", "never"]) == 1

    # fichero explícito ilegible
    assert (
        cli.main(["graph", root, "--gate", "--boundaries", os.path.join(root, "typo.txt"), "--color", "never"])
        == 1
    )


def test_fichero_solo_de_comentarios_no_inventa_reglas_ni_avisos(tmp_path):
    """Comentarios, lineas en blanco y una regla COMENTADA mezclados.

    Dos maneras de equivocarse aqui, opuestas: parsear la regla comentada (aplicar
    una frontera que alguien desactivo a proposito) o meterla en `malformed` y
    tumbar el gate por una linea que nunca fue una regla. Ninguna de las dos: cero
    reglas, cero avisos, y el informe diciendo que NO ha comprobado nada — que es
    justo lo que un fichero sin reglas activas significa.
    """
    root = str(tmp_path)
    _write(root, ".gb-boundaries", "# cabecera\n\n   \n# app.web -/-> app.db\n\t\n")
    _write(root, "app/__init__.py", "")
    _write(root, "app/web.py", "from app import db\n")  # lo que la regla comentada prohibiria
    _write(root, "app/db.py", "")

    report = graph.analyze(root)
    assert report["boundaries"] == 0
    assert report["malformed_boundaries"] == []  # una regla comentada no es un typo
    assert report["boundaries_error"] is None
    assert report["violations"] == []  # y no se aplica: estaba desactivada
    assert "SIN FRONTERAS COMPROBADAS" in _plain(report)  # pero no se calla


def test_regla_a_medio_casar_se_avisa_y_tumba_el_gate(tmp_path):
    """El typo mas facil de no ver: el SRC existe y el DST no.

    Media regla que casa se lee como regla viva —"app.web esta vigilado"— y no
    dispara jamas. El aviso tiene que decir QUE lado falla, o revisarlo obliga a
    releer el grafo entero a mano.
    """
    root = str(tmp_path)
    _write(root, ".gb-boundaries", "app.web -/-> app.dbb\n")  # dbb: el DST no existe
    _write(root, "app/__init__.py", "")
    _write(root, "app/web.py", "")
    _write(root, "app/db.py", "")

    report = graph.analyze(root)
    assert report["boundaries"] == 1  # la regla se parsea bien: el typo es semantico
    (aviso,) = report["unmatched_rules"]
    assert aviso["rule"] == "app.web -/-> app.dbb"
    assert aviso["src_matches"] is True and aviso["dst_matches"] is False
    assert cli._graph_gate(report) == 1  # enforced nada -> nunca verde


def test_con_dos_ficheros_manda_el_de_la_RAIZ(tmp_path):
    """`.gb-boundaries` en la raiz Y en `src/`, analizando la raiz.

    La regla de descubrimiento es "la raiz gana siempre"; sin este test, cambiar el
    orden de busqueda en `find_boundaries` aplicaria en silencio las fronteras del
    subdirectorio. Cual de los dos manda tiene que ser un hecho comprobable, no un
    detalle del recorrido de `os.walk`.
    """
    root = str(tmp_path)
    _write(root, ".gb-boundaries", "raizmod -/-> otromod\n")
    _write(root, "src/.gb-boundaries", "src.pkg.a -/-> src.pkg.b\n")
    _write(root, "raizmod.py", "import otromod\n")  # cruce, pero solo segun la raiz
    _write(root, "otromod.py", "")
    _write(root, "src/pkg/__init__.py", "")
    _write(root, "src/pkg/a.py", "")

    report = graph.analyze(root)
    assert report["boundaries_path"] == os.path.join(root, graph.BOUNDARIES_FILE)
    assert [(v["importer"], v["imported"]) for v in report["violations"]] == [
        ("raizmod", "otromod")
    ]  # se aplica la regla de la raiz, no la de src/
    # y el segundo fichero, el que NO se aplica, queda localizado en el informe
    assert report["boundaries_elsewhere"] == os.path.join(root, "src", graph.BOUNDARIES_FILE)


def test_fichero_hondo_se_encuentra_a_dos_niveles_y_mas_abajo_se_DICE(tmp_path):
    """Hasta donde llega la busqueda hacia abajo, y que pasa al pasarse.

    A dos niveles el fichero SE ENCUENTRA, pero sus nombres de modulo son relativos
    a SU carpeta, asi que desde la raiz no casan con nada: encontrarlo no basta,
    tiene que avisar de que no enforced nada. Mas hondo ya cae fuera del alcance
    declarado de `find_boundaries` — y entonces lo unico que impide repetir el bug
    historico (fichero que existe, gate en verde, nadie enterado) es que el informe
    DIGA que ha cargado cero reglas y donde busco.
    """
    root = str(tmp_path)
    _write(root, "a/b/.gb-boundaries", "pkg.x -/-> pkg.y\n")
    _write(root, "a/b/pkg/__init__.py", "")
    _write(root, "a/b/pkg/x.py", "from pkg import y\n")
    _write(root, "a/b/pkg/y.py", "")

    hondo = graph.analyze(root)
    assert hondo["boundaries"] == 1  # dos niveles: dentro de alcance, se lee
    # pero desde aqui los modulos se llaman a.b.pkg.x, no pkg.x: la regla no casa
    assert [u["rule"] for u in hondo["unmatched_rules"]] == ["pkg.x -/-> pkg.y"]
    assert hondo["violations"] == []
    assert cli._graph_gate(hondo) == 1  # y por eso no puede quedar en verde

    # desde SU carpeta, el mismo fichero si enforced: mismo cruce, ahora visto
    dentro = graph.analyze(os.path.join(root, "a", "b"))
    assert dentro["boundaries"] == 1 and dentro["unmatched_rules"] == []
    assert len(dentro["violations"]) == 1

    # un nivel mas abajo, fuera de alcance: no se encuentra, pero no se calla
    mas_hondo = str(tmp_path / "raiz2")
    _write(mas_hondo, "a/b/c/.gb-boundaries", "pkg.x -/-> pkg.y\n")
    _write(mas_hondo, "a/b/c/pkg/__init__.py", "")
    _write(mas_hondo, "a/b/c/pkg/x.py", "from pkg import y\n")
    _write(mas_hondo, "a/b/c/pkg/y.py", "")

    fuera = graph.analyze(mas_hondo)
    assert fuera["boundaries"] == 0
    salida = _plain(fuera)
    assert "SIN FRONTERAS COMPROBADAS" in salida
    assert graph.BOUNDARIES_FILE in salida  # y donde se busco


def test_regla_duplicada_no_duplica_el_cruce(tmp_path):
    """La misma regla dos veces (copiar-pegar, o un merge) cuenta como dos reglas
    cargadas, pero un cruce es UNO: si cada arista se reportara una vez por regla
    que la atrapa, la lista de cruces creceria con el ruido del fichero en vez de
    con los problemas del codigo."""
    root = str(tmp_path)
    _write(root, ".gb-boundaries", "app.web -/-> app.db\napp.web  -/->  app.db   # otra vez\n")
    _write(root, "app/__init__.py", "")
    _write(root, "app/web.py", "from app import db\n")
    _write(root, "app/db.py", "")

    report = graph.analyze(root)
    assert report["boundaries"] == 2  # no se deduplica en silencio: se cargaron dos
    assert len(report["violations"]) == 1  # pero el cruce se cuenta una vez
    assert report["unmatched_rules"] == []  # y la copia no se confunde con un typo
    assert cli._graph_gate(report) == 1


def test_cli_gate_falla_con_cruce_y_pasa_sin_el(tmp_path):
    root = str(tmp_path)
    _write(root, ".gb-boundaries", "app.web -/-> app.db\n")
    _write(root, "app/__init__.py", "")
    _write(root, "app/db.py", "")
    _write(root, "app/web.py", "from app import db\n")  # viola

    from galaxybrain import cli

    assert cli.main(["graph", root, "--gate", "--color", "never"]) == 1
    _write(root, "app/web.py", "X = 1\n")  # respeta la regla
    assert cli.main(["graph", root, "--gate", "--color", "never"]) == 0


# --- los dos verdes mudos del gate, cerrados (5-ago-2026) --------------------

def test_un_fichero_hondo_ya_no_deja_el_gate_en_verde_mudo(tmp_path):
    """A profundidad >=3 el fichero no se carga (fuera del alcance declarado de
    find_boundaries), pero ahora SE DENUNCIA: elsewhere lo localiza y el gate
    falla. Antes: boundaries 0, elsewhere None, exit 0 — dfbe9ab un nivel mas
    abajo."""
    root = str(tmp_path)
    _write(root, "a/b/c/.gb-boundaries", "pkg.x -/-> pkg.y\n")
    _write(root, "a/b/c/pkg/__init__.py", "")
    _write(root, "a/b/c/pkg/x.py", "from pkg import y\n")
    _write(root, "a/b/c/pkg/y.py", "")

    report = graph.analyze(root)
    assert report["boundaries"] == 0
    assert report["boundaries_elsewhere"] == os.path.join(
        root, "a", "b", "c", graph.BOUNDARIES_FILE)
    assert cli._graph_gate(report) == 1


def test_dos_fuentes_de_reglas_tumban_el_gate_aunque_no_haya_cruce(tmp_path):
    """Con reglas cargadas Y un segundo fichero sin aplicar, el verde decia
    "todas tus fronteras comprobadas" con la mitad sin mirar. Config rota =
    falla siempre, como las reglas malformadas; y el texto lo dice."""
    root = str(tmp_path)
    _write(root, ".gb-boundaries", "modA -/-> modB\n")
    _write(root, "src/.gb-boundaries", "src.pkg.a -/-> src.pkg.b\n")
    _write(root, "modA.py", "")   # sin import: ningun cruce
    _write(root, "modB.py", "")

    report = graph.analyze(root)
    assert report["violations"] == []
    assert report["boundaries"] == 1
    assert report["boundaries_elsewhere"] == os.path.join(root, "src", graph.BOUNDARIES_FILE)
    assert cli._graph_gate(report) == 1
    assert "NO se esta aplicando" in _plain(report)


def test_las_fronteras_de_un_subproyecto_anidado_no_son_asunto_nuestro(tmp_path):
    """El guardia del falso positivo: un subproyecto anidado con su propio
    fichero de reglas NO se denuncia — sus fronteras son suyas. Denunciarlo
    tumbaria el gate del padre por un fichero que jamas debio aplicar, y ese
    falso positivo es el camino directo a --no-verify."""
    root = str(tmp_path)
    _write(root, ".gb-boundaries", "modA -/-> modB\n")
    _write(root, "modA.py", "")
    _write(root, "modB.py", "")
    _write(root, "vendorizado/pyproject.toml", "[project]\nname='otro'\n")
    _write(root, "vendorizado/.gb-boundaries", "x -/-> y\n")

    report = graph.analyze(root)
    assert report["boundaries_elsewhere"] is None
    assert cli._graph_gate(report) == 0
