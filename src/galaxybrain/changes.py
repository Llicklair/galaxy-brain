"""Qué le hizo un cambio a la evidencia. Fase B del PLANTEAMIENTO: *imposible de
esconder*.

Un verde se puede comprar de dos formas: arreglando el código, o ablandando lo
que lo comprueba. La segunda no la ve nadie leyendo el diff por encima, porque
mirar los ficheros de test es justo lo que no se hace. Esto los mira siempre.

**Informa, NO bloquea, y es deliberado.** Las señales de aquí son PROXIES, no
hechos: borrar un test puede ser una limpieza legítima, y `pytest.approx` puede
ser la forma correcta de comparar flotantes. Gatear proxies fue el error de v1
(ver PLANTEAMIENTO §1) y una gate que chilla sin motivo acaba en `--no-verify`.
Lo que hace imposible esconder algo no es que bloquee: es que la lista salga
SIEMPRE, delante de quien decide, sin que haya que acordarse de pedirla.

Consolidado en Python (antes en Node) por la hard rule 3 — un lenguaje, un
runtime. Es código propio, no una herramienta externa reimplementada, así que no
choca con la regla 7. En el camino se cerró un fallo del original: un fichero de
tests BORRADO ENTERO produce `+++ /dev/null` y el parser antiguo lo saltaba,
justo el amaño más descarado de todos.
"""

import os
import re

# Se reutiliza el runner de git del grafo en vez de duplicarlo: la disciplina de
# codificacion que lleva dentro (utf-8 + errors=replace, core.quotePath=false) se
# aprendio a base de fallos reales y tiene que ser la misma en los dos sitios.
from .graph import _git as _git_output

TEST_FILE = re.compile(
    r"(^|[\\/])(tests?|__tests__|spec)([\\/]|$)"
    r"|\.(test|spec)\.[jt]sx?$"
    r"|(^|[\\/])test_[^\\/]+\.py$"
    r"|_test\.(py|go|rb)$",
    re.IGNORECASE,
)

TEST_DEF = [
    re.compile(r"^\s*def\s+test_\w+"),  # pytest
    re.compile(r"^\s*(it|test)\s*\("),  # jest/vitest/mocha
    re.compile(r"^\s*func\s+Test\w+"),  # go
    re.compile(r"^\s*(it|specify|scenario)\s+['\"]"),  # rspec
]

ASSERTION = [
    re.compile(r"^\s*(assert\s|assert\()"),
    re.compile(r"\bexpect\s*\("),
    re.compile(r"\bassert(Equal|True|False|In|Is|Raises|AlmostEqual|Greater|Less|Regex)\w*\s*\("),
    re.compile(r"^\s*\w*\.?(should|must)\b"),
    re.compile(r"\bt\.(is|deepEqual|truthy|falsy|throws)\("),
]

# Anclados a principio de linea. Un decorador de verdad SIEMPRE va ahi (modulo
# indentacion); una mencion en prosa —un docstring, un comentario— casi nunca. Lo
# descubrio este modulo marcando su propio docstring, donde `@pytest.mark.skip`
# aparece entrecomillado con backticks a mitad de frase. Vaciar literales no bastaba:
# las lineas interiores de una cadena triple no llevan comillas, asi que no hay nada
# que vaciar. Anclar es mas barato y mas robusto que entender cadenas multilinea.
SKIP_ADDED = [
    re.compile(r"^\s*@pytest\.mark\.(skip|skipif|xfail)"),
    re.compile(r"^\s*@unittest\.skip"),
    re.compile(r"^\s*(it|test|describe)\.(skip|todo|failing)\s*\("),
    re.compile(r"^\s*x(it|test|describe)\s*\("),
    re.compile(r"^\s*pytest\.skip\s*\("),
]

WEAKENER = [
    re.compile(r"pytest\.approx\s*\("),
    re.compile(r"assertAlmostEqual\s*\("),
    re.compile(r"\.(toBeTruthy|toBeDefined|toBeInstanceOf)\s*\("),
    # Solo la asercion truthy PELADA (`assert True`, `assert 1`, con mensaje o sin
    # el). El patron heredado de v1 terminaba en \b y por tanto casaba dentro de
    # `assert 1 == 1`, que es una comparacion de verdad. Marcar eso como
    # "debilitada" es ruido, y el ruido es lo que manda una revision a --no-verify.
    re.compile(r"^\s*assert\s+(True|1)\s*($|,|#)"),
    re.compile(r"\bor\s+True\b"),
    re.compile(r"\|\|\s*true\b"),
    re.compile(r"expect\s*\(\s*true\s*\)", re.IGNORECASE),
]


#: Un literal de cadena completo, con escapes. Se usa para VACIARLOS antes de
#: buscar patrones: si no, un marcador escrito DENTRO de un string cuenta como si
#: fuera código. Ese falso positivo no es teórico — lo dio este mismo modulo en su
#: primer cambio real, marcando el `@pytest.mark.skip` que sus propios tests usan
#: como dato de prueba. Y es recurrente por construcción en cualquier proyecto que
#: teste un detector: sus fixtures contienen por fuerza lo que el detector busca.
_STRING = re.compile(r"""(['"])(?:\\.|(?!\1).)*\1""")

#: `git diff --unified=0` pone en la cabecera del hunk la funcion que lo contiene
#: (heuristica de git). Es gratis y es lo que permite contar POR FUNCION.
_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@\s*(.*)$")


def _code_only(line):
    """La línea con sus literales de cadena vaciados (`"x"` -> `""`).

    Best-effort a propósito: no entiende cadenas triples que abarcan varias líneas,
    porque el diff se procesa línea a línea. Cubre el caso real, que es un patrón
    escrito como dato dentro de una cadena de una sola línea.
    """
    return _STRING.sub(lambda m: m.group(1) * 2, line)


#: Una asercion que COMPARA (==, in, is, <...) afirma algo concreto; una truthy
#: pelada solo afirma "no es falsy". Degradar la primera a la segunda es la forma
#: de amano que el conteo neto no ve: 1 asercion quitada, 1 puesta, resta cero.
#: Encontrado en prueba de uso real (descuento roto + assert sin ==): paso limpio.
_COMPARA = re.compile(r"(==|!=|<=|>=|<|>|\bin\b|\bis\b|\.raises|approx)")


def _matches(patterns, line):
    code = _code_only(line)
    return any(p.search(code) for p in patterns)


def _replacement_asserts(added):
    """De las aserciones añadidas, las que cuentan como SUSTITUCION de una quitada.

    Las que viven dentro de un test NUEVO no cuentan, y ahí está todo el asunto:
    *añadir un test trivial que pasa mientras borras la aserción que fallaba* es la
    ruta de amaño que este modulo existe para cerrar. Si las nuevas compensan a las
    viejas, esa ruta queda invisible por aritmética.

    No vale fiarse de la funcion que git pone en la cabecera del hunk: etiqueta el
    hunk con la funcion donde EMPIEZA, y en el caso real que descubrio esto
    (115ee8c) el borrado y el test nuevo caian en el mismo hunk. Hay que seguir las
    definiciones dentro de las propias lineas añadidas.
    """
    out = []
    in_new_test = False
    for line in added:
        if _matches(TEST_DEF, line):
            in_new_test = True
            continue
        if not in_new_test and _matches(ASSERTION, line):
            out.append(line)
    return out


def parse_diff(text):
    """El diff unificado a {fichero: {"added": [...], "removed": [...], "deleted": bool}}.

    Solo ficheros de test. Se siguen las DOS cabeceras (`--- a/` y `+++ b/`) porque
    un fichero borrado entero sale como `+++ /dev/null`: mirando solo la `+++` se
    perdia el caso mas grave, que es justamente eliminar el fichero de pruebas.
    """
    files = {}
    current = None
    section = None
    old_path = None
    for line in (text or "").split("\n"):
        hunk = _HUNK.match(line)
        if hunk is not None:
            if current is not None:
                section = {"func": hunk.group(1).strip(), "added": [], "removed": []}
                current["sections"].append(section)
            continue
        if line.startswith("--- "):
            target = line[4:].strip()
            old_path = None if target == "/dev/null" else re.sub(r"^a/", "", target)
            continue
        if line.startswith("+++ "):
            target = line[4:].strip()
            if target == "/dev/null":
                path, deleted = old_path, True
            else:
                path, deleted = re.sub(r"^b/", "", target), False
            if path and TEST_FILE.search(path):
                current = files.setdefault(
                    path, {"added": [], "removed": [], "deleted": deleted, "sections": []}
                )
                current["deleted"] = current["deleted"] or deleted
            else:
                current = None
            section = None
            continue
        if current is None:
            continue
        # Se descartan los marcadores del propio diff (+++/---), ya tratados arriba.
        if line.startswith("+") and not line.startswith("+++"):
            current["added"].append(line[1:])
            if section is not None:
                section["added"].append(line[1:])
        elif line.startswith("-") and not line.startswith("---"):
            current["removed"].append(line[1:])
            if section is not None:
                section["removed"].append(line[1:])
    return files


def test_signals(files):
    """Las señales sobre los ficheros de test tocados. Hechos sobre el diff; el
    juicio de si cada uno es legítimo lo pone un humano, no esto."""
    flags = []
    for path in sorted(files):
        data = files[path]
        added, removed = data["added"], data["removed"]

        removed_defs = [l for l in removed if _matches(TEST_DEF, l)]
        added_defs = [l for l in added if _matches(TEST_DEF, l)]

        if data.get("deleted"):
            flags.append(
                {
                    "file": path,
                    "signal": "TEST_FILE_DELETED",
                    "detail": "el fichero de tests entero fue borrado (%d definicion(es) dentro)"
                    % len(removed_defs),
                    "evidence": [l.strip() for l in removed_defs[:3]],
                }
            )
        elif len(removed_defs) > len(added_defs):
            flags.append(
                {
                    "file": path,
                    "signal": "TEST_REMOVED",
                    "detail": "%d definicion(es) de test borrada(s)"
                    % (len(removed_defs) - len(added_defs)),
                    "evidence": [l.strip() for l in removed_defs[:3]],
                }
            )

        # Neto POR FUNCION, no por fichero. El neto por fichero tenia un agujero
        # justo en la ruta de amaño mas obvia despues de borrar el fichero: quitas
        # la asercion que fallaba y añades un test trivial que pasa, el neto sube y
        # la resta desaparece. Comprobado sobre un commit real de este repo (115ee8c),
        # donde se quito una asercion de un test existente y el detector callo.
        # El precio: mover aserciones de una funcion a otra ahora se señala. Es
        # aceptable — se nombra la funcion, y descartarlo cuesta un vistazo.
        if not data.get("deleted"):
            for section in data.get("sections") or []:
                gone = [l for l in section["removed"] if _matches(ASSERTION, l)]
                came = _replacement_asserts(section["added"])
                gone_cmp = [l for l in gone if _COMPARA.search(_code_only(l))]
                came_cmp = [l for l in came if _COMPARA.search(_code_only(l))]
                if len(gone) <= len(came) and len(gone_cmp) > len(came_cmp):
                    where = section["func"] or "nivel de modulo"
                    flags.append({
                        "file": path,
                        "signal": "ASSERT_WEAKENED",
                        "detail": "en %s: %d asercion(es) degradada(s) de comparacion a truthy"
                        % (where, len(gone_cmp) - len(came_cmp)),
                        "evidence": [l.strip() for l in gone_cmp[:3]],
                    })
                if len(gone) > len(came):
                    where = section["func"] or "nivel de modulo"
                    flags.append(
                        {
                            "file": path,
                            "signal": "ASSERT_REMOVED",
                            "detail": "en %s: perdida neta de aserciones -%d (quitadas %d, puestas %d)"
                            % (where, len(gone) - len(came), len(gone), len(came)),
                            "evidence": [l.strip() for l in gone[:3]],
                        }
                    )

        skips = [l for l in added if _matches(SKIP_ADDED, l)]
        if skips:
            flags.append(
                {
                    "file": path,
                    "signal": "SKIP_ADDED",
                    "detail": "%d marcador(es) skip/xfail/todo aniadido(s)" % len(skips),
                    "evidence": [l.strip() for l in skips[:3]],
                }
            )

        weak = [l for l in added if _matches(WEAKENER, l)]
        if weak:
            flags.append(
                {
                    "file": path,
                    "signal": "WEAKENER_ADDED",
                    "detail": "%d asercion(es) en forma debilitada" % len(weak),
                    "evidence": [l.strip() for l in weak[:3]],
                }
            )
    return flags


def analyze(root, rev_range=None, skip=None, include_nested=False, staged=False):
    """El informe de un cambio: qué le hizo a los tests y al acoplamiento.

    Con `staged=True` mira lo que está en el índice en vez de un rango de commits.
    Esa es la única forma correcta de usarlo en un pre-commit: ahí el commit TODAVÍA
    NO EXISTE, así que `HEAD~1..HEAD` revisaría el commit anterior — no el que se
    está haciendo. Revisar lo que no es se lee igual de verde que revisar bien.

    Devuelve siempre `covered` y `not_covered`: decir qué NO se ha mirado es parte
    del contrato, porque una revisión que calla lo que no cubrió se lee como si lo
    cubriera todo (el mismo invariante 4 que ya costó un arreglo en `gb graph`).
    """
    from . import graph

    label = "staged" if staged else rev_range
    report = {
        "root": root,
        "range": label,
        "staged": staged,
        "range_error": None,
        "test_files_changed": 0,
        "flags": [],
        "coupling": None,
        "covered": [],
        "not_covered": [],
    }

    if not os.path.isdir(root):
        report["range_error"] = "la raiz no existe o no es un directorio: %s" % root
        return report

    if staged:
        diff = _git_output(root, "diff", "--unified=0", "--cached")
    elif rev_range:
        diff = _git_output(root, "diff", "--unified=0", rev_range)
    else:
        report["range_error"] = "hace falta un rango git, o --staged"
        return report

    if diff is None:
        # Sin diff no hay NADA que revisar. Devolver un informe vacio y limpio seria
        # exactamente la falsa cobertura que este modulo dice evitar.
        report["range_error"] = (
            "no pude leer el diff de '%s' (repo git? rango valido?)" % label
        )
        return report

    files = parse_diff(diff)
    report["test_files_changed"] = len(files)
    report["flags"] = test_signals(files)
    report["covered"].append("ficheros de test tocados en %s" % label)

    # Con --staged la baseline es HEAD: se compara lo que va a entrar contra lo
    # ultimo commiteado.
    base = "HEAD" if staged else (rev_range.split("..")[0] or None)
    if base:
        coupling = graph.analyze(
            root,
            since=base,
            skip=skip or graph.DEFAULT_SKIP,
            include_nested=include_nested,
        )
        if coupling.get("baseline_ok"):
            report["coupling"] = {
                "base": base,
                "new_pairs": coupling["new_pairs"],
                "new_violations": coupling["new_violations"],
                "modules": coupling["modules"],
                "boundaries": coupling["boundaries"],
            }
            report["covered"].append("acoplamiento nuevo vs %s" % base)
            if not coupling["boundaries"]:
                # Sin reglas cargadas, la parte de fronteras revisa CERO. Callarlo
                # dejaria un "sin cruces prohibidos" que en realidad significa "no
                # he mirado" — el invariante 4, otra vez.
                report["not_covered"].append(
                    "fronteras: 0 reglas cargadas bajo %s (el .gb-boundaries suele "
                    "vivir en la raiz del paquete; apunta ahi el rango o mueve el fichero)"
                    % root
                )
            if coupling["modules"] == 0:
                report["not_covered"].append(
                    "acoplamiento: 0 modulos analizados bajo %s, no se comprobo nada" % root
                )
        else:
            report["not_covered"].append(
                "acoplamiento: no pude construir la baseline de '%s'" % base
            )
    else:
        report["not_covered"].append("acoplamiento: el rango no trae base comparable")

    # Dicho de frente, no omitido: lo que esta revision NO mira.
    report["not_covered"].append(
        "la suite no se ejecuta aqui (la corre el pre-commit); esto revisa el diff, no el resultado"
    )
    report["not_covered"].append(
        "tests que ya eran debiles antes del cambio: esto compara, no audita lo preexistente"
    )
    if staged:
        # Asimetria real y facil de pasar por alto: las senales salen del INDICE,
        # pero el acoplamiento se calcula sobre el WORKING TREE (asi lo hace
        # build_graph). Si hay cambios sin stagear, las dos mitades no miran
        # exactamente lo mismo. Se dice, no se disimula.
        report["not_covered"].append(
            "cambios sin stagear: las senales salen del indice, el acoplamiento del "
            "working tree — si tienes cosas a medias, las dos mitades no miran lo mismo"
        )
    return report
