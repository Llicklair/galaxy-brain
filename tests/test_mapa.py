"""El mapa persistente: memoria entre miradas, nunca estado servido como actual.

Cada test redirige GB_HOME a un directorio propio: el snapshot vive FUERA del
proyecto observado (ARCHITECTURE regla 7) y un test que escribiera en el home
real del desarrollador seria exactamente la clase de suciedad que esa regla
prohibe.
"""

import os
import time

from galaxybrain import mapa, symbols


def _proyecto(tmp_path, fuente="def suma(a, b):\n    return a + b\n"):
    raiz = tmp_path / "proyecto"
    raiz.mkdir()
    (raiz / "calc.py").write_text(fuente, encoding="utf-8")
    return str(raiz)


def _mirada(raiz):
    informe = symbols.analyze(raiz)
    viejo = mapa.cargar(raiz)
    cambios = mapa.delta(viejo, informe)
    mapa.guardar(raiz, informe)
    return informe, cambios


def test_primera_mirada_no_tiene_con_que_compararse(tmp_path, monkeypatch):
    monkeypatch.setenv("GB_HOME", str(tmp_path / "home"))
    raiz = _proyecto(tmp_path)
    _informe, cambios = _mirada(raiz)
    assert cambios is None
    assert mapa.cargar(raiz) is not None      # pero el snapshot quedo guardado


def test_sin_tocar_nada_el_delta_es_vacio_y_las_huellas_lo_saben(tmp_path, monkeypatch):
    monkeypatch.setenv("GB_HOME", str(tmp_path / "home"))
    raiz = _proyecto(tmp_path)
    _mirada(raiz)
    _informe, cambios = _mirada(raiz)
    assert cambios is not None and mapa.vacio(cambios)
    # El atajo barato tambien lo ve, sin re-derivar:
    assert mapa.sin_cambios(raiz, mapa.cargar(raiz))


def test_un_simbolo_nuevo_aparece_en_el_delta_con_su_nombre(tmp_path, monkeypatch):
    monkeypatch.setenv("GB_HOME", str(tmp_path / "home"))
    raiz = _proyecto(tmp_path)
    _mirada(raiz)
    with open(os.path.join(raiz, "calc.py"), "a", encoding="utf-8") as f:
        f.write("\ndef resta(a, b):\n    return a - b\n")
    _informe, cambios = _mirada(raiz)
    assert "calc.resta" in cambios["nuevos"]
    assert not cambios["idos"]


def test_un_fichero_borrado_sale_como_idos(tmp_path, monkeypatch):
    monkeypatch.setenv("GB_HOME", str(tmp_path / "home"))
    raiz = _proyecto(tmp_path)
    (os.path.join(raiz, "extra.py"))
    with open(os.path.join(raiz, "extra.py"), "w", encoding="utf-8") as f:
        f.write("def sobra():\n    pass\n")
    _mirada(raiz)
    os.remove(os.path.join(raiz, "extra.py"))
    _informe, cambios = _mirada(raiz)
    assert "extra.sobra" in cambios["idos"]
    # Y el atajo NO puede decir "sin cambios" con un fichero borrado:
    # (el snapshot ya es el nuevo; se comprueba contra el estado previo)


def test_fichero_nuevo_invalida_el_atajo_sin_cambios(tmp_path, monkeypatch):
    monkeypatch.setenv("GB_HOME", str(tmp_path / "home"))
    raiz = _proyecto(tmp_path)
    _mirada(raiz)
    viejo = mapa.cargar(raiz)
    assert mapa.sin_cambios(raiz, viejo)
    with open(os.path.join(raiz, "nuevo.py"), "w", encoding="utf-8") as f:
        f.write("def novedad():\n    pass\n")
    # Crear un modulo entero no puede leerse como "sin cambios" — el mismo
    # agujero que el diff con los ficheros sin trackear.
    assert not mapa.sin_cambios(raiz, viejo)


def test_editar_un_fichero_invalida_el_atajo(tmp_path, monkeypatch):
    monkeypatch.setenv("GB_HOME", str(tmp_path / "home"))
    raiz = _proyecto(tmp_path)
    _mirada(raiz)
    viejo = mapa.cargar(raiz)
    time.sleep(0.01)          # que el mtime_ns no pueda coincidir por azar
    with open(os.path.join(raiz, "calc.py"), "a", encoding="utf-8") as f:
        f.write("\n# tocado\n")
    assert not mapa.sin_cambios(raiz, viejo)


def test_snapshot_corrupto_se_trata_como_ausente(tmp_path, monkeypatch):
    monkeypatch.setenv("GB_HOME", str(tmp_path / "home"))
    raiz = _proyecto(tmp_path)
    _mirada(raiz)
    ruta = mapa._ruta(raiz)
    with open(ruta, "w", encoding="utf-8") as f:
        f.write("{esto no es json")
    assert mapa.cargar(raiz) is None
    # Y la siguiente mirada simplemente vuelve a ser "la primera": no revienta.
    _informe, cambios = _mirada(raiz)
    assert cambios is None
    assert mapa.cargar(raiz) is not None


def test_el_snapshot_vive_fuera_del_proyecto(tmp_path, monkeypatch):
    monkeypatch.setenv("GB_HOME", str(tmp_path / "home"))
    raiz = _proyecto(tmp_path)
    _mirada(raiz)
    dentro = [f for f in os.listdir(raiz) if f != "calc.py" and f != "__pycache__"]
    assert dentro == []       # el arnes no ensucia el proyecto observado
    assert mapa._ruta(raiz).startswith(str(tmp_path / "home"))
