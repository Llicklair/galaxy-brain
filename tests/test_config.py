"""Los límites de configuración vienen de variables de entorno que el usuario
puede poner a cualquier cosa, incluido 0 o negativos. Un límite mal saneado
rompe el recorte o miente en los contadores (era B3)."""

from galaxybrain import config


def test_max_frames_nunca_baja_de_1(monkeypatch):
    # B3: GB_MAX_FRAMES=0 hacía entries[-0:] = lista entera (no recorta) y el
    # contador de recortados mentía; negativos tiraban los frames externos.
    monkeypatch.setenv("GB_MAX_FRAMES", "0")
    assert config.max_frames() >= 1
    monkeypatch.setenv("GB_MAX_FRAMES", "-5")
    assert config.max_frames() >= 1


def test_context_lines_permite_cero(monkeypatch):
    # 0 es un valor válido y útil: desactiva la captura de líneas fuente (S1).
    monkeypatch.setenv("GB_CONTEXT_LINES", "0")
    assert config.context_lines() == 0


def test_limites_no_admiten_negativos(monkeypatch):
    for name, getter in (
        ("GB_MAX_LOCALS", config.max_locals),
        ("GB_MAX_VALUE_CHARS", config.max_value_chars),
        ("GB_MAX_ITEMS", config.max_items),
        ("GB_CONTEXT_LINES", config.context_lines),
    ):
        monkeypatch.setenv(name, "-3")
        assert getter() >= 0, name
