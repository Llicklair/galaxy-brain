"""El mapa lo refresca quien pasa: el rebote decide, un hijo suelto ejecuta.

Aqui se prueba la decision y el cableado; el subproceso real se sustituye por
un contador — un detached de verdad en CI es ruido, y su unica logica propia
(escritura atomica de who --html) ya tiene sus tests.
"""

import os
import subprocess
import time

from galaxybrain import cli


def test_sin_mapa_no_hay_nada_que_refrescar(tmp_path):
    assert cli._mapa_a_refrescar(str(tmp_path), time.time()) is None


def test_mapa_fresco_rebota_y_viejo_dispara(tmp_path):
    mapa = tmp_path / "mapa.html"
    mapa.write_text("x", encoding="utf-8")
    ahora = time.time()
    assert cli._mapa_a_refrescar(str(tmp_path), ahora) is None  # recien escrito
    viejo = ahora - 120
    os.utime(str(mapa), (viejo, viejo))
    assert cli._mapa_a_refrescar(str(tmp_path), ahora) == str(mapa)


def test_el_hijo_no_engendra_nietos(monkeypatch):
    llamadas = []
    monkeypatch.setenv("GB_MAPA_HIJO", "1")
    monkeypatch.setattr(subprocess, "Popen",
                        lambda *a, **k: llamadas.append(a))
    cli._refresca_mapa_estigmergia()
    assert not llamadas


def test_un_comando_deja_el_refresco_en_vuelo(tmp_path, monkeypatch):
    mapa = tmp_path / "mapa.html"
    mapa.write_text("x", encoding="utf-8")
    viejo = time.time() - 120
    os.utime(str(mapa), (viejo, viejo))
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GB_MAPA_HIJO", raising=False)
    llamadas = []
    monkeypatch.setattr(subprocess, "Popen",
                        lambda *a, **k: llamadas.append((a[0], k)))
    cli._refresca_mapa_estigmergia()
    assert llamadas and "who" in llamadas[0][0] and "--html" in llamadas[0][0]
    # el hijo nace marcado y con las tres tuberias cerradas
    assert llamadas[0][1]["env"]["GB_MAPA_HIJO"] == "1"
    assert llamadas[0][1]["stdout"] is subprocess.DEVNULL
    if os.name == "nt":
        # consola invisible heredable: sin ella, cada git.exe del hijo
        # abria una ventana visible (el parpadeo del 14-ago)
        assert llamadas[0][1]["creationflags"] & 0x08000000
    # y la marca de en-vuelo quedo puesta: el siguiente comando rebota
    assert cli._mapa_a_refrescar(str(tmp_path), time.time()) is None
