"""Convertir un objeto vivo en texto sin romper nada ni tardar.

Esta es la pieza peligrosa del proyecto. Corre sobre objetos arbitrarios de un
programa que acaba de fallar, es decir, sobre objetos que pueden estar a medio
construir. `repr()` de un objeto asi puede lanzar, puede tardar, o puede
devolver diez megas.

Regla 9 de ARCHITECTURE-v2 (fallar hacia el lado seguro) aplicada al detalle:
aqui NADA propaga una excepcion hacia arriba. Un valor que no se puede
representar se describe; no se pierde el frame entero por su culpa.
"""

from . import config

_SAFE_ATOMS = (bool, int, float, complex, bytes, str, type(None))


def _truncate(text, limit):
    if len(text) <= limit:
        return text
    return text[:limit] + "...(+%d chars)" % (len(text) - limit)


def _describe_unrepresentable(obj, error):
    """Cuando repr() falla, el tipo sigue siendo un hecho util."""
    try:
        type_name = type(obj).__name__
    except BaseException:
        type_name = "?"
    return "<%s: repr() fallo con %s>" % (type_name, type(error).__name__)


def _repr_atom(obj, limit):
    try:
        return _truncate(repr(obj), limit)
    except BaseException as error:  # noqa: BLE001 - a proposito: nunca propagar
        return _describe_unrepresentable(obj, error)


def safe_repr(obj, limit=None, max_items=None, _depth=0):
    """repr acotado, a prueba de excepciones y de objetos enormes.

    Las colecciones se resumen en vez de volcarse: de una lista de 50.000
    elementos, lo informativo es que tiene 50.000, no los primeros mil.
    """
    limit = config.max_value_chars() if limit is None else limit
    max_items = config.max_items() if max_items is None else max_items

    if isinstance(obj, _SAFE_ATOMS):
        return _repr_atom(obj, limit)

    if _depth >= 2:
        # Suficiente profundidad. Mas abajo el detalle deja de ayudar.
        return _repr_atom(obj, min(limit, 80))

    try:
        if isinstance(obj, (list, tuple, set, frozenset)):
            return _repr_sequence(obj, limit, max_items, _depth)
        if isinstance(obj, dict):
            return _repr_mapping(obj, limit, max_items, _depth)
    except BaseException as error:  # noqa: BLE001
        return _describe_unrepresentable(obj, error)

    return _repr_atom(obj, limit)


def _repr_sequence(obj, limit, max_items, depth):
    open_c, close_c = {
        list: ("[", "]"),
        tuple: ("(", ")"),
        set: ("{", "}"),
        frozenset: ("frozenset({", "})"),
    }.get(type(obj), ("[", "]"))

    total = len(obj)
    shown = []
    for index, item in enumerate(obj):
        if index >= max_items:
            break
        shown.append(safe_repr(item, min(limit, 80), max_items, depth + 1))

    body = ", ".join(shown)
    if total > max_items:
        body += ", ...(%d en total)" % total
    return _truncate(open_c + body + close_c, limit)


def _repr_mapping(obj, limit, max_items, depth):
    total = len(obj)
    shown = []
    for index, (key, value) in enumerate(obj.items()):
        if index >= max_items:
            break
        key_text = safe_repr(key, 60, max_items, depth + 1)
        if is_sensitive(key if isinstance(key, str) else ""):
            value_text = REDACTED
        else:
            value_text = safe_repr(value, min(limit, 80), max_items, depth + 1)
        shown.append("%s: %s" % (key_text, value_text))

    body = ", ".join(shown)
    if total > max_items:
        body += ", ...(%d en total)" % total
    return _truncate("{" + body + "}", limit)


REDACTED = "<redactado>"


def is_sensitive(name):
    """¿El NOMBRE de esta variable sugiere que su valor no debe tocar el disco?

    Por nombre y no por contenido: adivinar si una cadena es un secreto es
    heuristica cara y falible; el nombre lo escribio un humano a proposito.
    Falso positivo = pierdes un valor que no necesitabas. Falso negativo =
    un token en un fichero. Coste asimetrico, propiedad 5.
    """
    lowered = name.lower()
    return any(pattern in lowered for pattern in config.REDACT_PATTERNS)


def repr_local(name, value):
    """El repr de una variable local, respetando la redaccion por nombre."""
    if is_sensitive(name):
        return REDACTED
    return safe_repr(value)
