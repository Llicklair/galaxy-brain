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

Portado de `scripts/test-guard.js` (v1, Node) a Python por la hard rule 3 — un
lenguaje, un runtime. Es código propio consolidado, no una herramienta externa
reimplementada, así que no choca con la regla 7. En el camino se cerró un fallo
del original: un fichero de tests BORRADO ENTERO produce `+++ /dev/null` y el
parser antiguo lo saltaba, justo el amaño más descarado de todos.
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

SKIP_ADDED = [
    re.compile(r"@pytest\.mark\.(skip|skipif|xfail)"),
    re.compile(r"@unittest\.skip"),
    re.compile(r"\b(it|test|describe)\.(skip|todo|failing)\s*\("),
    re.compile(r"^\s*x(it|test|describe)\s*\("),
    re.compile(r"pytest\.skip\s*\("),
]

WEAKENER = [
    re.compile(r"pytest\.approx\s*\("),
    re.compile(r"assertAlmostEqual\s*\("),
    re.compile(r"\.(toBeTruthy|toBeDefined|toBeInstanceOf)\s*\("),
    re.compile(r"^\s*assert\s+(True|1)\b"),
    re.compile(r"\bor\s+True\b"),
    re.compile(r"\|\|\s*true\b"),
    re.compile(r"expect\s*\(\s*true\s*\)", re.IGNORECASE),
]


def _matches(patterns, line):
    return any(p.search(line) for p in patterns)


def parse_diff(text):
    """El diff unificado a {fichero: {"added": [...], "removed": [...], "deleted": bool}}.

    Solo ficheros de test. Se siguen las DOS cabeceras (`--- a/` y `+++ b/`) porque
    un fichero borrado entero sale como `+++ /dev/null`: mirando solo la `+++` se
    perdia el caso mas grave, que es justamente eliminar el fichero de pruebas.
    """
    files = {}
    current = None
    old_path = None
    for line in (text or "").split("\n"):
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
                    path, {"added": [], "removed": [], "deleted": deleted}
                )
                current["deleted"] = current["deleted"] or deleted
            else:
                current = None
            continue
        if current is None:
            continue
        # Se descartan los marcadores del propio diff (+++/---), ya tratados arriba.
        if line.startswith("+") and not line.startswith("+++"):
            current["added"].append(line[1:])
        elif line.startswith("-") and not line.startswith("---"):
            current["removed"].append(line[1:])
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

        removed_asserts = [l for l in removed if _matches(ASSERTION, l)]
        added_asserts = [l for l in added if _matches(ASSERTION, l)]
        if len(removed_asserts) > len(added_asserts) and not data.get("deleted"):
            flags.append(
                {
                    "file": path,
                    "signal": "ASSERT_REMOVED",
                    "detail": "perdida neta de aserciones: -%d (quitadas %d, puestas %d)"
                    % (
                        len(removed_asserts) - len(added_asserts),
                        len(removed_asserts),
                        len(added_asserts),
                    ),
                    "evidence": [l.strip() for l in removed_asserts[:3]],
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


def analyze(root, rev_range, skip=None, include_nested=False):
    """El informe de un cambio: qué le hizo a los tests y al acoplamiento.

    Devuelve siempre `covered` y `not_covered`: decir qué NO se ha mirado es parte
    del contrato, porque una revisión que calla lo que no cubrió se lee como si lo
    cubriera todo (el mismo invariante 4 que ya costó un arreglo en `gb graph`).
    """
    from . import graph

    report = {
        "root": root,
        "range": rev_range,
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

    diff = _git_output(root, "diff", "--unified=0", rev_range)
    if diff is None:
        # Sin diff no hay NADA que revisar. Devolver un informe vacio y limpio seria
        # exactamente la falsa cobertura que este modulo dice evitar.
        report["range_error"] = (
            "no pude leer el diff de '%s' (repo git? rango valido?)" % rev_range
        )
        return report

    files = parse_diff(diff)
    report["test_files_changed"] = len(files)
    report["flags"] = test_signals(files)
    report["covered"].append("ficheros de test tocados en %s" % rev_range)

    base = rev_range.split("..")[0] or None
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
    return report
