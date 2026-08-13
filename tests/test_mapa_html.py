"""El mapa HTML: un fichero autocontenido que no puede mentir a medias."""

import os

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
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_escritura_atomica_deja_el_fichero_y_ningun_tmp(tmp_path):
    destino = str(tmp_path / "mapa.html")
    assert mapa_html.escribir(destino, _foto(), refresco=2) == destino
    assert os.path.exists(destino)
    assert not os.path.exists(destino + ".tmp")
