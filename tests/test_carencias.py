"""El motor dice lo que NO puede ver, donde se lee el número que no puede ver.

La tabla de `lenguajes` lleva desde el principio un campo `carencias` y un
docstring que promete que «se enseña al usuario y no se disimula». No se
enseñaba: nadie leía el campo. El límite estaba declarado en el código y era
invisible desde fuera, que para el usuario es igual que no estarlo.

Lo destapó el banco `gb-lenguajes` el 18-ago-2026, en su peor forma — la del
silencio que se lee como un dato. En los proyectos `java`, `csharp`, `kotlin` y
`scala`, `gb graph` decía:

    3 modulos, 0 aristas internas, 0 ciclo(s)
    Sin ciclos de imports.

sobre código donde `gb symbols` veía 2 llamadas cruzando de módulo a módulo. Las
clases del mismo paquete se usan sin `import`, así que no hay arista que derivar.
El acoplamiento está; la vista de imports no puede verlo. Y «0 aristas porque no
hay» se imprimía igual que «0 aristas porque por aquí no se ve».

No se rellena con aristas inventadas (ADR 0001, ADR 0008): se declara el techo.
"""

import os

from galaxybrain import graph, lenguajes, render


def _write(root, rel, contenido=""):
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(contenido)


def _plano(report):
    return render.render_graph(report, render.Style(False))


def test_los_lenguajes_de_mismo_paquete_declaran_su_carencia():
    """Los cuatro medidos como ciegos. Si alguien quita una, este test lo dice."""
    for lang in ("java", "csharp", "kotlin", "scala"):
        carencias = lenguajes.LENGUAJES[lang].get("carencias") or ()
        assert carencias, "%s se quedo sin declarar su limite" % lang
        assert any("SIN import" in c for c in carencias), lang


def test_solo_se_nombran_los_lenguajes_QUE_HAY(tmp_path):
    """Enumerar los limites de 16 lenguajes en un repo de uno es ruido, y el
    ruido se acaba saltando igual que un aviso falso."""
    root = str(tmp_path)
    _write(root, "src/Carrito.java", "class Carrito { }\n")

    carencias = graph.carencias_presentes(root)
    assert any("Java" in c for c in carencias)
    assert not any("Swift" in c or "Ruby" in c for c in carencias)


def test_un_proyecto_python_no_arrastra_carencias_ajenas(tmp_path):
    root = str(tmp_path)
    _write(root, "app/__init__.py")
    _write(root, "app/web.py", "import os\n")

    assert graph.carencias_presentes(root) == ()
    assert "NO puede ver" not in _plano(graph.analyze(root))


def test_cero_aristas_con_modulos_avisa_de_que_ese_cero_engana(tmp_path):
    """El caso exacto del banco: hay modulos, hay cero aristas, y el lenguaje
    tiene un limite conocido. Ese cero es el que se lee mal."""
    root = str(tmp_path)
    _write(root, "src/Carrito.java", "class Carrito { int t() { return Iva.get(); } }\n")
    _write(root, "src/Iva.java", "class Iva { static int get() { return 21; } }\n")

    report = graph.analyze(root, constructor=_constructor_java)
    assert report["carencias"], "el informe no lleva el limite del lenguaje"

    texto = _plano(report)
    assert "OJO con el 0" in texto
    assert "0 aristas aqui NO significa 0 acoplamiento" in texto


def test_con_aristas_el_limite_se_dice_sin_alarma(tmp_path):
    """El limite sigue siendo cierto, pero el numero ya no engana: mismo dato,
    otro tono. Un aviso que grita siempre deja de leerse."""
    root = str(tmp_path)
    _write(root, "src/Carrito.java", "class Carrito { }\n")

    def constructor(_root, _skip, _nested, _skipped):
        return {"Carrito", "Iva"}, {"Carrito": {"Iva"}}, {}

    report = graph.analyze(root, constructor=constructor)
    texto = _plano(report)
    assert "OJO con el 0" not in texto
    assert "NO puede ver" in texto


def test_un_repo_mixto_no_suelta_un_muro_pero_dice_cuantos_faltan(tmp_path):
    """Siete lenguajes juntaron siete limites de golpe en el banco. Un muro no se
    lee, y no leerlo es el mismo silencio de antes; recortar sin decirlo, peor
    todavia. Se enseñan tres y se cuenta el resto."""
    root = str(tmp_path)
    for rel in ("a.java", "b.cs", "c.kt", "d.scala", "e.swift", "f.rb", "g.rs"):
        _write(root, "src/%s" % rel, "// x\n")

    report = graph.analyze(root, constructor=_constructor_java)
    texto = _plano(report)

    assert len(report["carencias"]) > 3, "el banco junta varios lenguajes"
    assert texto.count("\n  - ") == 3
    assert "limite(s) mas" in texto


def test_una_raiz_que_no_existe_no_inventa_limites(tmp_path):
    """Sin arbol que mirar no hay lenguaje presente que declarar, y el ERROR ya
    dice lo suyo. Amontonar avisos sobre un error tapa el error."""
    report = graph.analyze(os.path.join(str(tmp_path), "no-existe"))
    assert report["root_error"]
    assert report["carencias"] == []


def _constructor_java(_root, _skip, _nested, _skipped):
    """Los dos modulos que ast-grep encontraria, sin arista: es justo lo que pasa
    en Java y lo que hace falta para el caso. Asi el test no depende del binario
    externo (ADR 0009: la capa multilenguaje es opcional)."""
    return {"Carrito", "Iva"}, {}, {}
