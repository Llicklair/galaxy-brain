"""Convertir un objeto vivo en texto sin romper nada ni tardar.

Esta es la pieza peligrosa del proyecto. Corre sobre objetos arbitrarios de un
programa que acaba de fallar, es decir, sobre objetos que pueden estar a medio
construir. `repr()` de un objeto asi puede lanzar, puede tardar, o puede
devolver diez megas.

Regla 9 de ARCHITECTURE (fallar hacia el lado seguro) aplicada al detalle:
aqui NADA propaga una excepcion hacia arriba. Un valor que no se puede
representar se describe; no se pierde el frame entero por su culpa.
"""

import re

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


#: Cuánto se DESCIENDE en estructuras anidadas. Ojo: no es donde se deja de
#: redactar —la redacción por clave ocurre en cada nivel de _repr_mapping— sino
#: donde se deja de bajar: más hondo, un contenedor se resume por tamaño en vez
#: de volcar su contenido. Acota coste y profundidad sin abrir un canal de fuga.
_MAX_DEPTH = 4


def safe_repr(obj, limit=None, max_items=None, _depth=0):
    """repr acotado, a prueba de excepciones y de objetos enormes.

    Las colecciones se resumen en vez de volcarse: de una lista de 50.000
    elementos, lo informativo es que tiene 50.000, no los primeros mil.
    """
    limit = config.max_value_chars() if limit is None else limit
    max_items = config.max_items() if max_items is None else max_items

    if isinstance(obj, _SAFE_ATOMS):
        return _repr_atom(obj, limit)

    # Los contenedores SIEMPRE pasan por su manejador, a cualquier profundidad:
    # ahí es donde _repr_mapping redacta las claves sensibles. El cap se aplica
    # al DESCENDER (en _repr_value), nunca aquí cortocircuitando a repr() crudo —
    # eso era S4: un dict con una clave sensible anidada se volcaba sin redactar.
    try:
        if isinstance(obj, dict):
            return _repr_mapping(obj, limit, max_items, _depth)
        if isinstance(obj, (list, tuple, set, frozenset)):
            return _repr_sequence(obj, limit, max_items, _depth)
    except BaseException as error:  # noqa: BLE001
        return _describe_unrepresentable(obj, error)

    # Objeto arbitrario: su repr puede exponer atributos sensibles por nombre
    # (un dataclass/pydantic/namedtuple con un campo `password`). Redacción por
    # nombre aplicada al texto del repr (S5).
    return redact_text(_repr_atom(obj, limit))


def _repr_value(value, limit, max_items, depth):
    """Un valor hijo de un contenedor, respetando el cap de profundidad.

    Pasado el cap no se desciende, y tampoco se vuelca el contenido de un
    contenedor: se resume por tamaño. Así un secreto anidado más hondo que el
    cap queda OCULTO, no filtrado (era S4)."""
    if depth > _MAX_DEPTH:
        if isinstance(value, dict):
            return "{...%d %s...}" % (len(value), "clave" if len(value) == 1 else "claves")
        if isinstance(value, (list, tuple, set, frozenset)):
            return "[...%d...]" % len(value)
        return _repr_atom(value, min(limit, 80))
    return safe_repr(value, limit, max_items, depth)


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
        shown.append(_repr_value(item, min(limit, 80), max_items, depth + 1))

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
        # La clave viaja tal cual: is_sensitive ya sabe tratar cualquier tipo.
        # El guard viejo (`"" si no es str`) era la fuga: una clave bytes se
        # saltaba la redaccion entera.
        if is_sensitive(key):
            value_text = REDACTED
        else:
            value_text = _repr_value(value, min(limit, 80), max_items, depth + 1)
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

    Acepta CUALQUIER tipo de nombre. Una clave `bytes` se colaba entera:
    `{b"password": ...}` volcaba el secreto sin tapar porque el call-site pasaba
    "" para claves no-str (hallado por la tirada de agentes del 5-ago-2026). La
    conversion a texto preserva el nombre visible (`str(b'password')` contiene
    'password'), y si ni convertirse puede, se redacta: el mismo coste
    asimetrico manda fallar hacia el lado que no escribe secretos.
    """
    if not isinstance(name, str):
        try:
            name = str(name)
        except Exception:
            return True
    lowered = name.lower()
    return any(pattern in lowered for pattern in config.REDACT_PATTERNS)


def repr_local(name, value):
    """El repr de una variable local, respetando la redaccion por nombre."""
    if is_sensitive(name):
        return REDACTED
    return safe_repr(value)


#: Un identificador que CONTIENE un patrón sensible, seguido de `=` o `:` (con
#: comilla opcional en medio, para dicts JSON), y un valor: cadena entrecomillada
#: o palabra suelta hasta un delimitador. El disparador es el NOMBRE, no el
#: contenido — por eso no es olfateo de secretos, es la misma redacción por
#: nombre de is_sensitive aplicada a texto.
_ASSIGN_RE = re.compile(
    r"(?i)(\b\w*(?:%s)\w*\b)(['\"]?\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|[^\s,)\]}]+)"
    % "|".join(re.escape(p) for p in config.REDACT_PATTERNS)
)


def redact_text(text):
    """Redacción por nombre aplicada a TEXTO LIBRE (líneas fuente, mensajes de
    excepción, reprs de objeto).

    Cubre `password = "x"`, `token=abc`, `"session": "v"`, `Creds(api_key='x')`.
    NO cubre secretos posicionales, `password hunter2` sin separador, ni
    contraseñas embebidas en URLs — eso queda como límite honesto documentado.
    Nunca lanza: corre sobre texto de un proceso que se está muriendo.
    """
    try:
        return _ASSIGN_RE.sub(lambda m: m.group(1) + m.group(2) + REDACTED, text)
    except BaseException:  # noqa: BLE001
        return text
