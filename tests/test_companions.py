"""Lo externo: detectado y verificado, nunca replicado (regla 7).

Dos cosas que este modulo tiene que hacer bien, y las dos fallaron en su primera
ejecucion real:

1. **No aplanar estados distintos.** "sin indexar", "desfasado" y "no pude
   comprobarlo" son tres cosas, y la tercera se presento como la primera — un
   estado mas tranquilizador que el real.
2. **No aprobar el continente ignorando el contenido.** Un AGENTS.md escrito
   entero por una herramienta pasa cualquier comprobacion ingenua y no contiene
   nada del proyecto.
"""

import shutil

from galaxybrain import companions

# --- cuanto de un fichero lo escribio una herramienta ------------------------


def test_un_fichero_escrito_entero_por_una_herramienta_se_detecta():
    texto = "<!-- gitnexus:start -->\n# GitNexus\nusa estas tools\n<!-- gitnexus:end -->\n"

    ratio, herramientas = companions.tool_generated_ratio(texto)
    assert ratio > 0.9
    assert herramientas == ["gitnexus"]


def test_un_fichero_escrito_por_una_persona_da_cero():
    texto = "# mi proyecto\n\n## Comandos\n\npytest -q\n"

    ratio, herramientas = companions.tool_generated_ratio(texto)
    assert ratio == 0.0
    assert herramientas == []


def test_un_bloque_abierto_al_final_cuenta_hasta_el_final():
    """El caso real: la herramienta APENDA su bloque al final y no lo cierra."""
    texto = "# mi proyecto\n" + "x\n" * 5 + "<!-- ctx:start -->\n" + "reglas\n" * 40

    ratio, herramientas = companions.tool_generated_ratio(texto)
    assert ratio > 0.7
    assert herramientas == ["ctx"]


def test_un_fichero_mixto_no_se_da_por_generado():
    """Contexto de verdad mas un apendice pequeno sigue siendo el contexto del
    proyecto. Marcarlo como 'generado' seria el falso positivo simetrico."""
    texto = "# mi proyecto\n" + "contenido real de verdad\n" * 60 + (
        "<!-- x:start -->\nnota\n<!-- x:end -->\n"
    )

    ratio, _ = companions.tool_generated_ratio(texto)
    assert ratio < 0.3


def test_varias_herramientas_se_listan_ordenadas():
    texto = (
        "<!-- zeta:start -->\na\n<!-- zeta:end -->\n"
        "<!-- alfa:start -->\nb\n<!-- alfa:end -->\n"
    )

    _ratio, herramientas = companions.tool_generated_ratio(texto)
    assert herramientas == ["alfa", "zeta"]


def test_un_fichero_vacio_no_revienta():
    assert companions.tool_generated_ratio("") == (0.0, [])


# --- deteccion de gitnexus ---------------------------------------------------


def test_sin_gitnexus_instalado_lo_dice_y_da_el_instalador(monkeypatch, tmp_path):
    """Regla 7: detectar, y apuntar al instalador OFICIAL. Nunca replicar."""
    monkeypatch.setattr(shutil, "which", lambda _n: None)

    info = companions.gitnexus(str(tmp_path))
    assert info["installed"] is False
    assert info["usable"] is False
    assert "npm i -g gitnexus" in info["hint"]


def test_instalado_pero_sin_indexar_no_es_usable(monkeypatch, tmp_path):
    monkeypatch.setattr(shutil, "which", lambda _n: "/fake/gitnexus")
    monkeypatch.setattr(companions, "_run", lambda *_a, **_k: "Repository not indexed.")

    info = companions.gitnexus(str(tmp_path))
    assert info["installed"] is True and info["usable"] is False
    assert info["hint"] == "gitnexus analyze"


def test_un_indice_desfasado_NO_pasa_por_usable(monkeypatch, tmp_path):
    """Un indice viejo es peor que ninguno: se presenta como el mapa del proyecto y
    describe un codigo que ya no existe."""
    monkeypatch.setattr(shutil, "which", lambda _n: "/fake/gitnexus")
    monkeypatch.setattr(
        companions, "_run",
        lambda *_a, **_k: "Indexed commit: aaa111\nCurrent commit: bbb222\nStatus: stale\n",
    )

    info = companions.gitnexus(str(tmp_path))
    assert info["usable"] is False
    assert info["stale"] is True
    assert "DESFASADO" in info["detail"]


def test_indexado_y_al_dia_si_es_usable(monkeypatch, tmp_path):
    monkeypatch.setattr(shutil, "which", lambda _n: "/fake/gitnexus")
    monkeypatch.setattr(companions, "_run", lambda *_a, **_k: "Status: up-to-date\n")

    info = companions.gitnexus(str(tmp_path))
    assert info["usable"] is True and info["stale"] is False
    assert info["hint"] == "gitnexus serve"


def test_no_poder_comprobarlo_NO_se_traduce_a_sin_indexar(monkeypatch, tmp_path):
    """El fallo exacto de la primera ejecucion: en Windows el ejecutable es un .CMD,
    subprocess sin shell lanzaba FileNotFoundError, y el informe lo contaba como
    'sin indexar' — un estado distinto y mas tranquilizador que el real."""
    monkeypatch.setattr(shutil, "which", lambda _n: "/fake/gitnexus")
    monkeypatch.setattr(companions, "_run", lambda *_a, **_k: None)

    info = companions.gitnexus(str(tmp_path))
    assert info["installed"] is True and info["usable"] is False
    assert "no pude ejecutar" in info["detail"]
    assert "NO esta indexado" not in info["detail"]
