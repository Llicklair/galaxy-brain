"""Lo externo: detectado y verificado, nunca replicado (regla 7).

Lo que este modulo tiene que hacer bien, y fallo en su primera ejecucion real:
**no aprobar el continente ignorando el contenido.** Un AGENTS.md escrito
entero por una herramienta pasa cualquier comprobacion ingenua y no contiene
nada del proyecto.
"""

from galaxybrain import companions

# --- cuanto de un fichero lo escribio una herramienta ------------------------


def test_un_fichero_escrito_entero_por_una_herramienta_se_detecta():
    texto = "<!-- una-tool:start -->\n# Una Tool\nusa estas tools\n<!-- una-tool:end -->\n"

    ratio, herramientas = companions.tool_generated_ratio(texto)
    assert ratio > 0.9
    assert herramientas == ["una-tool"]


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
