"""El mapa HTML: un fichero autocontenido que no puede mentir a medias."""

import os
import re
import time

from galaxybrain import mapa_html


def _foto():
    return {
        "base": "abc1234",
        "agentes": [{
            "nombre": "wt-a", "base": "abc1234", "misma_base": True,
            "hace_seg": 5, "ficheros": 2, "fuera_del_mapa": 1,
            "nodos": ["core"], "simbolos": ["core.suma"],
            "commitados": [],
        }],
        "por_nodo": {"core.suma": {"agentes": ["wt-a", "wt-b"]}},
        "cruces": ["core.suma"],
        "motivo": "",
    }


def test_pinta_agente_simbolo_y_cruce():
    html = mapa_html.render(_foto())
    assert "wt-a" in html
    assert "core.suma" in html
    assert "CRUCES" in html


def test_con_refresco_lleva_meta_refresh_y_sin_el_no():
    assert "http-equiv='refresh'" in mapa_html.render(_foto(), refresco=3)
    assert "http-equiv" not in mapa_html.render(_foto(), refresco=0)


def test_un_nombre_hostil_queda_escapado():
    foto = _foto()
    foto["agentes"][0]["simbolos"] = ["<script>alert(1)</script>"]
    html = mapa_html.render(foto)
    # El mapa lleva UN <script> propio (el reloj); lo hostil jamas llega a serlo.
    assert "<script>alert" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_la_foto_lleva_su_epoca_y_su_reloj():
    antes = int(time.time())
    html = mapa_html.render(_foto())
    despues = int(time.time())
    epoca = re.search(r"data-gen='(\d+)'", html)
    assert epoca and antes <= int(epoca.group(1)) <= despues
    assert "id='edad'" in html and "setInterval" in html


def test_sin_refresco_es_foto_unica_y_caduca_con_la_presencia():
    html = mapa_html.render(_foto(), refresco=0)
    assert "foto unica" in html
    assert "gb who --watch --html" in html
    assert "data-limite='600'" in html  # = actividad.VENTANA_COMMIT
    assert "FOTO VIEJA" in html


def test_con_refresco_el_limite_delata_al_watch_muerto():
    assert "data-limite='10'" in mapa_html.render(_foto(), refresco=3)
    assert "data-limite='90'" in mapa_html.render(_foto(), refresco=30)
    assert "YA NO ESCRIBE" in mapa_html.render(_foto(), refresco=3)


def test_nadie_va_anclado_a_su_hora_no_al_presente():
    foto = dict(_foto(), agentes=[], cruces=[], por_nodo={})
    html = mapa_html.render(foto)
    assert "ahora mismo" not in html
    assert "Nadie tocaba nada a las" in html


def test_escritura_atomica_deja_el_fichero_y_ningun_tmp(tmp_path):
    destino = str(tmp_path / "mapa.html")
    assert mapa_html.escribir(destino, _foto(), refresco=2) == destino
    assert os.path.exists(destino)
    assert not os.path.exists(destino + ".tmp")
