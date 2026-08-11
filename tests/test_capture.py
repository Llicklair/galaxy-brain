"""La captura: qué se guarda de un fallo, y qué NO se guarda a propósito."""

from galaxybrain import capture

# --- la FORMA del comando: nombres de flag si, valores no --------------------


def test_la_forma_conserva_el_subcomando_y_tapa_los_valores():
    """El registro guardaba `program` y `argv_count`, y con eso no se sabe si
    murio `gb calls` o `gb tests`.

    Medido el 11-ago-2026 investigando por que se abandona la consola (regla 5):
    de 136 capturas, CERO sabian que comando habia muerto. Sin eso, actuar sobre
    una captura cuesta lo mismo que reejecutar — que es lo que se hace.
    """
    assert capture.forma_de_argv(["/usr/bin/gb", "calls", "lib.f", "--depth", "2"]) == [
        "gb", "calls", "<arg>", "--depth", "<arg>"]


def test_la_forma_no_deja_escapar_secretos_en_flags():
    """El defecto de no guardar argv es bueno y no se toca: los secretos viven
    en los flags y guardarlos crudos ya fue una fuga a disco."""
    assert capture.forma_de_argv(["t", "--password", "SECRETO", "--token=abc123"]) == [
        "t", "--password", "<arg>", "--token=<val>"]


def test_la_forma_no_guarda_el_codigo_de_python_c():
    """`python -c "<codigo>"`: `-c` es un flag y el codigo su VALOR.

    La primera version conservaba "la primera posicional" y con eso el codigo
    entero iba a disco — contenido del programa, no un subcomando. Solo `argv[1]`
    puede ser subcomando, que es la forma clasica `tool sub ...`.
    """
    assert capture.forma_de_argv(["python", "-c", "import x; x.secreto()"]) == [
        "python", "-c", "<arg>"]


def test_la_forma_tapa_rutas_y_cosas_que_no_parecen_subcomando():
    """El patron es estrecho a proposito: lo que no case se tapa, que es el lado
    seguro del error."""
    assert capture.forma_de_argv(["t", "/etc/passwd"]) == ["t", "<arg>"]
    assert capture.forma_de_argv(["t", "MiClaveSecreta"]) == ["t", "<arg>"]
    assert capture.forma_de_argv([]) == []
