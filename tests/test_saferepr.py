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


def test_objeto_a_medio_construir():
    class Incompleto:
        def __repr__(self):
            return "Incompleto(%s)" % self.no_existe  # AttributeError

    assert "repr() fallo" in saferepr.safe_repr(Incompleto())
