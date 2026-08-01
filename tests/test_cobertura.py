"""Que dispara una captura y que no — ejecutado, no documentado.

Era la pregunta sin respuesta comprobable: la frontera de la consola vivia en
SCOPE.md y en la cabeza de quien la escribio. Un documento envejece y nadie sabe
si sigue siendo cierto; esto lo demuestra cada vez que se lanza.

Las dos mitades pesan igual. Un "no captura" que en realidad captura te llena el
historico de ruido; un "captura" que no captura es un fallo que desaparece sin
que nadie lo eche de menos — y ese es el modo de fallo que esta herramienta
existe para hacer imposible.
"""

import os

from galaxybrain import bootstrap, render


def test_la_matriz_declara_los_DOS_lados():
    """Una matriz que solo ensenara lo que funciona seria propaganda: dejaria
    creer que lo no listado tambien se captura."""
    esperados = {esperado for _n, esperado, _c in bootstrap._CASOS}
    assert esperados == {True, False}


def test_cada_caso_se_ejecuta_de_verdad_y_coincide():
    """El test lento y el que vale: 8 subprocesos reales, ~1 s."""
    resultados = bootstrap.coverage()
    discrepan = [r["caso"] for r in resultados if not r["ok"]]
    assert not discrepan, "la frontera no es la que dice ser: %s" % discrepan
    assert len(resultados) == len(bootstrap._CASOS)


def test_no_ensucia_el_historico_de_quien_lo_lanza():
    """Cada sonda corre con su GB_HOME en un temporal. Medir la consola no puede
    meter ocho fallos de mentira en tu libreta (regla 7)."""
    from galaxybrain import config

    antes = len(list((config.home() / "errors").rglob("*.json"))) if config.home().exists() else 0
    bootstrap.coverage()
    despues = len(list((config.home() / "errors").rglob("*.json"))) if config.home().exists() else 0
    assert antes == despues


def test_los_temporales_se_borran():
    import glob
    import tempfile

    bootstrap.coverage()
    assert not glob.glob(os.path.join(tempfile.gettempdir(), "gb-cobertura-*"))


def test_el_informe_enumera_lo_que_NO_captura(tmp_path):
    salida = render.render_coverage(bootstrap.coverage(), render.Style(False))
    assert "LO QUE SI deja registro" in salida
    assert "LO QUE NO" in salida
    assert "try/except" in salida
    assert "EJECUTADO, no documentado" in salida


def test_una_discrepancia_se_ve_y_se_explica():
    """Si un caso deja de comportarse como se dice, el informe tiene que decir
    QUE esperaba y QUE paso — no solo marcarlo en rojo."""
    falso = [
        {"caso": "inventado", "esperado": True, "observado": False, "detalle": "", "ok": False}
    ]
    salida = render.render_coverage(falso, render.Style(False))
    assert "DISCREPAN" in salida
    assert "esperaba capturar" in salida
    assert "no capturo" in salida
