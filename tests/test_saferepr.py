"""saferepr corre sobre objetos de un programa que acaba de fallar: objetos a
medio construir, enormes, o con __repr__ roto. Aqui se comprueba que ninguno de
esos casos propaga una excepcion hacia arriba."""

import pytest

from galaxybrain import saferepr


class ReprQueRevienta:
    def __repr__(self):
        raise RuntimeError("no me representes")


class ReprInfinito:
    def __repr__(self):
        return "x" * 10_000_000


def test_repr_roto_no_propaga():
    text = saferepr.safe_repr(ReprQueRevienta())
    assert "repr() fallo" in text
    assert "RuntimeError" in text


def test_repr_gigante_se_recorta():
    text = saferepr.safe_repr(ReprInfinito())
    assert len(text) < 1000
    assert "chars)" in text


def test_lista_enorme_se_resume_no_se_vuelca():
    text = saferepr.safe_repr(list(range(50_000)))
    assert "50000 en total" in text
    assert len(text) < 1000


def test_dict_anidado_se_corta_en_profundidad():
    nested = {"a": {"b": {"c": {"d": {"e": 1}}}}}
    text = saferepr.safe_repr(nested)
    assert len(text) < 500


@pytest.mark.parametrize(
    "name",
    ["password", "API_KEY", "db_passwd", "auth_token", "user_credentials", "SESSION_ID"],
)
def test_nombres_sensibles_se_redactan(name):
    assert saferepr.repr_local(name, "valor-real-secreto") == saferepr.REDACTED


def test_nombre_normal_no_se_redacta():
    assert saferepr.repr_local("usuario", "ana") == "'ana'"


def test_clave_sensible_dentro_de_un_dict_tambien_se_redacta():
    text = saferepr.safe_repr({"user": "ana", "password": "hunter2"})
    assert "hunter2" not in text
    assert saferepr.REDACTED in text
    assert "ana" in text


def test_secreto_anidado_en_dict_se_redacta():
    """S4: la clave sensible a profundidad >=2 debe redactarse, no volcarse."""
    text = saferepr.repr_local("cfg", {"a": {"b": {"password": "hunter2"}}})
    assert "hunter2" not in text
    assert saferepr.REDACTED in text


def test_secreto_en_dict_dentro_de_lista_se_redacta():
    text = saferepr.repr_local("data", [[{"token": "sk-secreto"}]])
    assert "sk-secreto" not in text
    assert saferepr.REDACTED in text


def test_secreto_a_un_nivel_sigue_redactado():
    text = saferepr.repr_local("conf", {"outer": {"api_key": "AKIA-real"}})
    assert "AKIA-real" not in text
    assert saferepr.REDACTED in text


def test_secreto_mas_hondo_que_el_cap_queda_oculto_no_filtrado():
    """Pasado el cap de profundidad no se filtra: se resume el contenedor."""
    deep = {"l1": {"l2": {"l3": {"l4": {"l5": {"l6": {"password": "muy-hondo"}}}}}}}
    text = saferepr.repr_local("cfg", deep)
    assert "muy-hondo" not in text  # oculto por el resumen, no filtrado


def test_valor_no_sensible_anidado_si_se_ve():
    text = saferepr.repr_local("cfg", {"db": {"host": "localhost", "port": 5432}})
    assert "localhost" in text
    assert "5432" in text


def test_redact_text_redacta_por_nombre_en_texto_libre():
    r = saferepr.redact_text
    assert "hunter2" not in r('password = "hunter2"')
    assert "sk-x" not in r("api_key='sk-x'")
    assert "abc123" not in r("config error: token=abc123")
    assert "vvv" not in r('{"session": "vvv"}')
    assert saferepr.REDACTED in r('password = "hunter2"')


def test_redact_text_no_toca_lo_no_sensible():
    assert saferepr.redact_text('host = "localhost"') == 'host = "localhost"'
    assert saferepr.redact_text("texto normal sin nada") == "texto normal sin nada"


def test_atributos_de_objeto_sensibles_se_redactan():
    """S5: un dataclass/objeto con un campo sensible no vuelca su valor vía repr."""
    from dataclasses import dataclass

    @dataclass
    class Creds:
        user: str
        api_key: str

    text = saferepr.repr_local("c", Creds(user="ana", api_key="sk-secreto"))
    assert "sk-secreto" not in text
    assert saferepr.REDACTED in text
    assert "ana" in text  # lo no sensible se conserva


def test_objeto_a_medio_construir():
    class Incompleto:
        def __repr__(self):
            return "Incompleto(%s)" % self.no_existe  # AttributeError

    assert "repr() fallo" in saferepr.safe_repr(Incompleto())


def test_lista_que_se_contiene_a_si_misma_no_cuelga():
    """Estructura ciclica: el cap de profundidad corta el descenso; ni
    RecursionError ni salida ilimitada."""
    ciclica = [1, 2]
    ciclica.append(ciclica)

    text = saferepr.safe_repr(ciclica)

    assert len(text) < 500
    assert text.startswith("[1, 2, [")


def test_dict_ciclico_con_secreto_sigue_redactando():
    """El ciclo no debe abrir un hueco por el que se cuele el valor sensible."""
    ciclico = {"password": "hunter2"}
    ciclico["self"] = ciclico

    text = saferepr.repr_local("cfg", ciclico)

    assert "hunter2" not in text
    assert saferepr.REDACTED in text
    assert len(text) < 500


def test_repr_que_devuelve_algo_que_no_es_str_se_describe():
    """repr() exige str: si __repr__ devuelve otra cosa, CPython lanza
    TypeError y aqui se convierte en descripcion, no en fallo."""

    class ReprNoStr:
        def __repr__(self):
            return 42  # no es str

    text = saferepr.safe_repr(ReprNoStr())

    assert text == "<ReprNoStr: repr() fallo con TypeError>"
    # y tampoco propaga cuando va dentro de un contenedor
    assert "repr() fallo con TypeError" in saferepr.safe_repr([ReprNoStr()])


def test_bytes_y_str_enormes_se_recortan_al_limite():
    """Atomos gigantes: se recortan, no se vuelcan cinco megas al disco."""
    for gigante in (b"\x00" * 5_000_000, "y" * 5_000_000):
        text = saferepr.safe_repr(gigante, limit=240)
        assert len(text) < 300
        assert "chars)" in text


def test_contenedor_con_len_roto_se_describe_no_propaga():
    """Un contenedor a medio construir revienta al recorrerlo; ese fallo se
    describe igual que el de un repr roto."""

    class LenRoto(list):
        def __len__(self):
            raise ValueError("len roto")

    assert saferepr.safe_repr(LenRoto([1, 2, 3])) == "<LenRoto: repr() fallo con ValueError>"

    class ItemsRoto(dict):
        def items(self):
            raise ValueError("items roto")

    assert saferepr.safe_repr(ItemsRoto(a=1)) == "<ItemsRoto: repr() fallo con ValueError>"


# --- redaccion con claves que no son str (la fuga del 5-ago-2026) -----------

def test_una_clave_bytes_sensible_ya_no_vuelca_el_secreto():
    """`{b"password": ...}` se saltaba la redaccion entera: el call-site pasaba
    "" a is_sensitive para claves no-str y el valor acababa en disco sin tapar."""
    salida = saferepr.safe_repr({b"password": "hunter2"})
    assert "hunter2" not in salida
    assert saferepr.REDACTED in salida


def test_repr_local_con_nombre_bytes_no_propaga_y_redacta():
    """El docstring del modulo promete que aqui NADA propaga; con un nombre
    bytes, `name.lower()` devolvia bytes y el `in` contra patrones str lanzaba
    TypeError."""
    assert saferepr.repr_local(b"password", "x") == saferepr.REDACTED
    assert "no-sensible" in saferepr.repr_local(b"contador", "no-sensible")


def test_una_clave_de_otro_tipo_tambien_se_mira_por_su_texto():
    salida = saferepr.safe_repr({("api_key",): "sk-123"})
    assert "sk-123" not in salida
    assert saferepr.REDACTED in salida


def test_una_clave_cuyo_str_revienta_se_redacta_en_vez_de_colarse():
    """Si el nombre ni siquiera puede decirse, el coste asimetrico manda: mejor
    perder un valor que escribir un secreto."""
    class SinNombre:
        def __str__(self):
            raise RuntimeError("sin nombre")
        def __repr__(self):
            raise RuntimeError("sin repr")
        def __hash__(self):
            return 1
        def __eq__(self, otro):
            return self is otro

    salida = saferepr.safe_repr({SinNombre(): "quiza-secreto"})
    assert "quiza-secreto" not in salida


def test_las_claves_normales_siguen_enseniando_su_valor():
    salida = saferepr.safe_repr({"contador": 3, "usuario": "ana"})
    assert "3" in salida and "ana" in salida
