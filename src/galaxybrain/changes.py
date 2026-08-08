"""Qué le hizo un cambio a la evidencia — *imposible de esconder*.

Un verde se puede comprar de dos formas: arreglando el código, o ablandando lo
que lo comprueba. La segunda no la ve nadie leyendo el diff por encima, porque
mirar los ficheros de test es justo lo que no se hace. Esto los mira siempre.

**Informa, NO bloquea, y es deliberado.** Las señales de aquí son PROXIES, no
hechos: borrar un test puede ser una limpieza legítima, y `pytest.approx` puede
ser la forma correcta de comparar flotantes. Gatear proxies fue el error que
hundió el enfoque anterior, y una gate que chilla sin motivo acaba en `--no-verify`.
Lo que hace imposible esconder algo no es que bloquee: es que la lista salga
SIEMPRE, delante de quien decide, sin que haya que acordarse de pedirla.

Consolidado en Python (antes en Node) por la hard rule 3 — un lenguaje, un
runtime. Es código propio, no una herramienta externa reimplementada, así que no
choca con la regla 7. En el camino se cerró un fallo del original: un fichero de
tests BORRADO ENTERO produce `+++ /dev/null` y el parser antiguo lo saltaba,
justo el amaño más descarado de todos.
"""

import ast
import datetime
import os
import re

# Se reutiliza el runner de git del grafo en vez de duplicarlo: la disciplina de
# codificacion que lleva dentro (utf-8 + errors=replace, core.quotePath=false) se
# aprendio a base de fallos reales y tiene que ser la misma en los dos sitios.
from . import store
from .graph import _BOM, module_name
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
    # el). El patron anterior terminaba en \b y por tanto casaba dentro de
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

#: El rango `+c,d` de la cabecera: donde CAE el hunk en el fichero nuevo. Es lo
#: que la onda necesita para cruzar el diff con el [line, end] de cada def.
_HUNK_RANGO = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


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

    Un rename PURO no emite cabeceras `---`/`+++` (git solo escribe `rename
    from/to`): sin leerlas, renombrar un fichero de tests fuera del patron de
    tests era una via silenciosa de perder la suite entera. Sale como
    `renamed_to` y test_signals lo señala.
    """
    files = {}
    current = None
    section = None
    old_path = None
    rename_from = None
    for line in (text or "").split("\n"):
        hunk = _HUNK.match(line)
        if hunk is not None:
            if current is not None:
                section = {"func": hunk.group(1).strip(), "added": [], "removed": []}
                current["sections"].append(section)
            continue
        if line.startswith("diff --git "):
            # Frontera entre ficheros: lo que siga es cabecera, no contenido.
            section = None
            continue
        if line.startswith("rename from "):
            rename_from = line[len("rename from "):].strip()
            continue
        if line.startswith("rename to ") and rename_from:
            destino = line[len("rename to "):].strip()
            if TEST_FILE.search(rename_from) and not TEST_FILE.search(destino):
                files.setdefault(rename_from, {
                    "added": [], "removed": [], "deleted": False, "sections": []
                })["renamed_to"] = destino
            rename_from = None
            continue
        if line.startswith("--- ") and _es_cabecera(line, section):
            target = line[4:].strip()
            old_path = None if target == "/dev/null" else re.sub(r"^a/", "", target)
            continue
        if line.startswith("+++ ") and _es_cabecera(line, section):
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
        # Las cabeceras reales ya se consumieron arriba: un "+++"/"---" que
        # llega aqui es contenido cuyo texto empieza por "++"/"--" (antes se
        # infracontaba, p. ej. un comentario SQL borrado).
        if line.startswith("+"):
            current["added"].append(line[1:])
            if section is not None:
                section["added"].append(line[1:])
        elif line.startswith("-"):
            current["removed"].append(line[1:])
            if section is not None:
                section["removed"].append(line[1:])
    return files


def _es_cabecera(line, section):
    """¿Este `--- `/`+++ ` es cabecera de fichero o contenido que empieza por
    `--`/`++`? Fuera de un hunk siempre es cabecera; dentro, solo si el objetivo
    tiene forma de ruta de diff (`a/…`, `b/…`, `/dev/null`)."""
    target = line[4:].strip()
    return (section is None or target == "/dev/null"
            or re.match(r"^[ab]/", target) is not None)


def _extensiones_fuente():
    """Las extensiones que el diff puede mapear a símbolos: `.py` de la vía de la
    stdlib más las que declare la tabla multilenguaje (ADR 0009).

    Se DERIVA en vez de escribirse. La primera versión era una lista a mano con
    `.py` y las de JS, y al abrir el catálogo a 17 lenguajes se quedó vieja al
    instante: el banco de Rust dio 0 % de ahorro porque ningún hunk de un `.rs`
    entraba, y las 7 roturas caían a "corre la suite entera" — seguro y sin
    valor. Es el mismo fallo que se acababa de arreglar en el aviso de frontera:
    dos listas de lo mismo divergen, y la que se queda vieja miente en silencio.
    """
    from . import lenguajes

    return tuple(sorted({".py"} | set(lenguajes.POR_EXTENSION)))


EXTENSIONES_FUENTE = _extensiones_fuente()


def _hunks_py(text, extensiones=EXTENSIONES_FUENTE):
    """{ruta: [(inicio, fin)]} de los hunks del diff, para TODO el código fuente.

    `parse_diff` mira solo ficheros de test porque su trabajo son las señales;
    esto mira el rango `+c,d` de cada hunk en cualquier fuente, que es lo que la
    onda necesita. Un hunk de solo borrado (`+c,0`) toca el punto c: el símbolo
    alrededor sigue afectado aunque no haya líneas nuevas.

    Conserva el nombre `_hunks_py` a propósito: lo llaman `impacted` y la onda, y
    renombrarlo por cosmética es un diff grande sin un solo cambio de conducta.
    """
    rangos = {}
    actual = None
    for line in (text or "").split("\n"):
        if line.startswith("+++ "):
            target = line[4:].strip()
            actual = None
            if target != "/dev/null":
                ruta = re.sub(r"^b/", "", target)
                if ruta.endswith(extensiones):
                    actual = rangos.setdefault(ruta, [])
            continue
        if actual is None:
            continue
        hunk = _HUNK_RANGO.match(line)
        if hunk is not None:
            inicio = int(hunk.group(1))
            cuantas = int(hunk.group(2)) if hunk.group(2) is not None else 1
            actual.append((inicio, inicio + max(cuantas, 1) - 1))
    return rangos


def _onda_del_diff(root, diff, informe=None):
    """Los símbolos que el diff TOCA y cuántos les llaman — la onda del cambio.

    Intersección de los rangos `+c,d` con el `[line, end]` de cada def del grafo
    de símbolos. INFORMA, nunca gatea (regla 9): "has tocado algo con 26
    llamantes" es un dato para leer antes del commit, no un veredicto. Si las
    rutas del diff no casan con la raíz analizada (root distinto del toplevel),
    sale vacío y calla — el informe del cambio ya se dio entero.
    """
    rangos = _hunks_py(diff)
    if not rangos:
        return []
    # El import va FUERA del `if`: `symbols` se usa mas abajo pase lo que pase,
    # y dejarlo dentro lo volvia inalcanzable justo en el camino nuevo (el que
    # recibe el informe ya calculado). 26 tests en rojo por una indentacion.
    from . import symbols

    if informe is None:
        informe = symbols.analyze(root)
    if informe.get("root_error"):
        return []
    entrantes, _salientes = symbols._indice_llamadas(informe)
    normal = {
        os.path.normcase(ruta.replace("/", os.sep)): tramos
        for ruta, tramos in rangos.items()
    }
    tocados = []
    for nodo in informe["nodes"]:
        if nodo["kind"] == "module":
            continue
        tramos = normal.get(os.path.normcase(nodo.get("file") or ""))
        if not tramos:
            continue
        inicio, fin = nodo.get("line"), nodo.get("end")
        if not inicio or not fin:
            continue
        if any(a <= fin and inicio <= b for a, b in tramos):
            tocados.append({
                "qual": nodo["qual"],
                "owner": nodo.get("owner"),
                "file": nodo.get("file", ""),
                "line": inicio,
                "callers": len(entrantes.get(nodo["qual"], ())),
            })
    # Tocar un metodo hace interseccion tambien con su CLASE entera; listar las
    # dos veces seria contar el mismo toque dos veces. Se queda el mas interno.
    con_metodo_tocado = {t["owner"] for t in tocados if t["owner"]}
    tocados = [t for t in tocados if t["qual"] not in con_metodo_tocado]
    tocados.sort(key=lambda t: (-t["callers"], t["qual"]))
    return tocados


def _firma_rompe_llamadas(vieja, nueva):
    """¿La firma nueva invalida llamadas que la vieja aceptaba?

    Añadir `eco=False` NO rompe a nadie: el llamante que no lo pasa sigue siendo
    correcto, y no tocarlo es lo acertado. Señalarlo igual convierte la señal en
    ruido en cada cambio retrocompatible — y el ruido es lo que manda una
    revisión a `--no-verify` (regla 11). Solo son hechos accionables: **un
    parámetro nuevo SIN default** (las llamadas viejas se quedan cortas) y **un
    parámetro que desaparece** (las que lo pasaban sobran).

    Conservador a propósito: con `*args`/`**kwargs` de por medio no se razona
    barato, así que no se acusa. Falso negativo > falso positivo (propiedad 5).
    """
    def _params(firma):
        cuerpo = (firma or "").strip()
        if cuerpo.startswith("(") and cuerpo.endswith(")"):
            cuerpo = cuerpo[1:-1]
        return [p.strip() for p in cuerpo.split(",") if p.strip()]

    viejos, nuevos = _params(vieja), _params(nueva)
    if any(p.startswith("*") for p in viejos + nuevos):
        return False
    nombre = lambda p: p.split("=")[0].split(":")[0].strip()  # noqa: E731
    v_nombres = {nombre(p) for p in viejos}
    for p in nuevos:
        if nombre(p) not in v_nombres and "=" not in p:
            return True                      # obligatorio nuevo: las viejas se quedan cortas
    return any(nombre(p) not in {nombre(q) for q in nuevos} for p in viejos)


def _firmas_cambiadas_sin_llamantes(root, diff, base_ref, informe):
    """Funciones cuya firma (parametros) cambio sin tocar ningun llamante resuelto.

    Hecho derivable del AST mas el grafo, no heuristica: la firma vieja sale de
    git, la nueva del AST actual, y los llamantes del grafo de simbolos. INFORMA,
    no bloquea (regla 9): un parametro con default puede ser un cambio
    intencionalmente retrocompatible, pero el hecho de que los call-sites no se
    actualizaron sigue siendo informacion.
    """
    rangos = _hunks_py(diff)
    if not rangos:
        return []
    if informe.get("root_error"):
        return []

    from . import symbols

    entrantes, _ = symbols._indice_llamadas(informe)

    # Simbolos tocados por el diff (misma interseccion que _onda_del_diff).
    normal = {
        os.path.normcase(ruta.replace("/", os.sep)): tramos
        for ruta, tramos in rangos.items()
    }
    tocados = set()
    for nodo in informe["nodes"]:
        if nodo["kind"] == "module":
            continue
        tramos = normal.get(os.path.normcase(nodo.get("file") or ""))
        if not tramos:
            continue
        inicio, fin = nodo.get("line"), nodo.get("end")
        if not inicio or not fin:
            continue
        if any(a <= fin and inicio <= b for a, b in tramos):
            tocados.add(nodo["qual"])

    # Firmas viejas del baseline de git.
    firmas_viejas = {}
    for ruta_diff in rangos:
        texto = _git_output(root, "show", "%s:%s" % (base_ref, ruta_diff))
        if not texto:
            continue
        abs_path = os.path.join(os.path.abspath(root), *ruta_diff.split("/"))
        mod = module_name(abs_path, root)
        if not mod:
            continue
        try:
            tree = ast.parse(texto.lstrip(_BOM), filename=ruta_diff)
        except (SyntaxError, ValueError, RecursionError, MemoryError):
            continue
        es_pkg = os.path.basename(ruta_diff) == "__init__.py"
        old_info = symbols._scan_module(mod, tree, es_pkg)
        firmas_viejas.update(old_info["sigs"])

    if not firmas_viejas:
        return []

    # Comparar firmas y comprobar llamantes.
    flags = []
    for nodo in informe["nodes"]:
        if nodo["kind"] not in ("function", "method"):
            continue
        qual = nodo["qual"]
        sig_nueva = nodo.get("sig", "")
        sig_vieja = firmas_viejas.get(qual)
        if sig_vieja is None or sig_nueva == sig_vieja:
            continue
        if not _firma_rompe_llamadas(sig_vieja, sig_nueva):
            continue   # retrocompatible: no tocar a los llamantes es CORRECTO
        llamantes = entrantes.get(qual, set())
        if not llamantes:
            continue
        if any(c in tocados for c in llamantes):
            continue
        flags.append({
            "file": nodo.get("file", ""),
            "signal": "FIRMA_CAMBIADA_SIN_LLAMANTES",
            "detail": "%s: firma cambio de %s a %s, %d llamante(s) sin tocar"
                      % (qual, sig_vieja, sig_nueva, len(llamantes)),
            "evidence": sorted(llamantes)[:3],
        })
    return flags


def test_signals(files):
    """Las señales sobre los ficheros de test tocados. Hechos sobre el diff; el
    juicio de si cada uno es legítimo lo pone un humano, no esto."""
    flags = []
    for path in sorted(files):
        data = files[path]
        added, removed = data["added"], data["removed"]

        removed_defs = [l for l in removed if _matches(TEST_DEF, l)]
        added_defs = [l for l in added if _matches(TEST_DEF, l)]

        if data.get("renamed_to"):
            flags.append(
                {
                    "file": path,
                    "signal": "TEST_FILE_RENAMED_OUT",
                    "detail": "renombrado a %s, fuera del patron de tests: "
                              "el runner deja de recogerlo" % data["renamed_to"],
                    "evidence": [],
                }
            )
        elif data.get("deleted"):
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
        "onda": [],
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
    # ultimo commiteado.  Se calcula antes porque lo usan la onda, la firma y el
    # acoplamiento.
    base = "HEAD" if staged else (rev_range.split("..")[0] or None)

    from . import symbols as _sym
    _informe = _sym.analyze(root)

    report["onda"] = _onda_del_diff(root, diff, informe=_informe)
    if report["onda"]:
        report["covered"].append("la onda del diff: simbolos tocados y sus llamantes")
        report["not_covered"].append(
            "la onda cuenta llamantes RESUELTOS: las llamadas por variable o "
            "despacho dinamico no suman (gb symbols declara cuanto queda fuera)"
        )

    if base and not _informe.get("root_error"):
        firma_flags = _firmas_cambiadas_sin_llamantes(
            root, diff, base, _informe,
        )
        report["flags"].extend(firma_flags)
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
            # La confusion tipica, y le paso a alguien usando esto de verdad:
            # `gb graph src` toma una RUTA en el primer positional y `gb check src`
            # toma un RANGO. Mismo hueco, significado distinto. Sin este aviso, el
            # mensaje se lee como "el baseline esta roto" en vez de "te has
            # equivocado de argumento", que es lo que de verdad pasa.
            pista = ""
            if os.path.isdir(os.path.join(root, base)) or os.path.isdir(base):
                pista = (
                    " — pero '%s' SI es un directorio: aqui el rango va PRIMERO y la "
                    "ruta despues (`gb check HEAD~1..HEAD %s`)" % (base, base)
                )
            report["not_covered"].append(
                "acoplamiento: no pude construir la baseline de '%s'%s" % (base, pista)
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


# ---------------------------------------------------------------------------
# El ciclo del error: capturado -> leida -> intervenido -> sin reaparecer.
# Vive aqui porque este modulo es el que ya habla con git sobre cambios, y el
# eslabon "intervenido" es exactamente eso: un commit posterior al fallo.
# ---------------------------------------------------------------------------


def _fichero_de_firma(where):
    """La ruta de fichero de un `where` del indice ("C:\\x\\a.py:42" -> "C:\\x\\a.py").

    Se parte por la DERECHA: en Windows la ruta lleva el ':' de la unidad, y
    partir por la izquierda devolveria "C" como fichero. None si no hay ':' o si
    la fuente no es un fichero real (`<string>`, `<stdin>`, `?`).
    """
    texto = (where or "").strip()
    if not texto or texto.startswith("<"):
        return None
    fichero, sep, _linea = texto.rpartition(":")
    if not sep:
        return None
    return fichero or None


def _ruta_para_git(root, fichero):
    """La ruta relativa a `root` que git entiende, o None si no se puede.

    normpath + relpath: en Windows relpath compara componente a componente con
    normcase, asi que 'c:/x/A.PY' y 'C:\\x\\a.py' acaban en la misma relativa
    (el bug de cache por 'c:' vs 'C:' ya costo un arreglo en este repo). En
    POSIX la caja se respeta: ahi dos rutas con distinta caja SON distintas.
    """
    try:
        rel = os.path.relpath(os.path.normpath(fichero), os.path.normpath(root))
    except ValueError:  # otra unidad de disco en Windows: no hay relativa posible
        return None
    return rel.replace(os.sep, "/")


def _ultimo_commit(root, fichero, cache):
    """(hash, datetime) del ultimo commit que toco `fichero`, o None.

    Hecho de git, no un juicio: que el fichero se tocara despues del fallo no
    dice que el cambio lo arreglara. Por eso el vocabulario del ciclo se queda
    en "intervenido" — devolver, no dictaminar.
    """
    clave = os.path.normcase(os.path.normpath(fichero))
    if clave in cache:
        return cache[clave]
    resultado = None
    rel = _ruta_para_git(root, fichero)
    if rel:
        salida = _git_output(root, "log", "-1", "--format=%h %cI", "--", rel)
        if salida and salida.strip():
            hash_, _sep, fecha = salida.strip().split("\n")[0].partition(" ")
            cuando = store.parse_ts(fecha.strip())
            if hash_ and cuando is not None and cuando.tzinfo is not None:
                resultado = (hash_, cuando)
    cache[clave] = resultado
    return resultado


def _ultimos_commits(root, ficheros, desde):
    """El ultimo commit de CADA fichero con UN solo `git log`, o None si no se pudo.

    Devuelve {clave normcase: (hash, datetime) | None} cubriendo TODOS los
    `ficheros` — las mismas claves que usa la cache de `_ultimo_commit`, para
    poder sembrarla. None entero si el batch no se pudo construir o parsear: el
    que llama cae en silencio al camino por-fichero (regla 9 — un atajo que
    falla no puede costar ni un aviso ni un bloqueo).

    Por que un batch: un spawn de git son ~25-40 ms en Windows, y un `git log -1`
    POR FICHERO con 30+ ficheros con capturas se come el presupuesto de < 1 s
    por edicion (hard rule 2, esto corre dentro de `_vigilar`). Solo interesan
    commits desde la ocurrencia mas antigua (`desde`): un commit anterior a
    TODAS las ocurrencias nunca es una intervencion, asi que un fichero sin
    commits en la ventana queda en None con la misma semantica aguas abajo que
    el camino por-fichero.
    """
    resultado = {}
    rutas = []
    for fichero in ficheros:
        resultado[os.path.normcase(os.path.normpath(fichero))] = None
        rel = _ruta_para_git(root, fichero)
        if rel:
            rutas.append(rel)
    if not rutas:
        return resultado
    # `--name-only` da las rutas relativas al TOPLEVEL del repo (no a `root`) y
    # siempre con '/': hay que reconstruir la absoluta desde el toplevel y
    # comparar por normcase — la misma normalizacion que la cache por-fichero.
    toplevel = _git_output(root, "rev-parse", "--show-toplevel")
    if not toplevel or not toplevel.strip():
        return None
    toplevel = toplevel.strip().split("\n")[0]
    salida = _git_output(
        root,
        "log",
        "--format=%x01%h %cI",
        "--name-only",
        "--since=" + desde.isoformat(timespec="seconds"),
        "--",
        *rutas,
    )
    if salida is None:
        return None
    actual = None
    for linea in salida.split("\n"):
        if linea.startswith("\x01"):
            hash_, _sep, fecha = linea[1:].partition(" ")
            cuando = store.parse_ts(fecha.strip())
            if not hash_ or cuando is None or cuando.tzinfo is None:
                return None  # cabecera ilegible: mejor por-fichero que adivinar
            actual = (hash_, cuando)
            continue
        nombre = linea.strip()
        if not nombre or actual is None:
            continue
        clave = os.path.normcase(os.path.normpath(os.path.join(toplevel, nombre)))
        # git lista de lo mas nuevo a lo mas viejo: la primera aparicion de un
        # fichero es su ultimo commit, las siguientes se ignoran.
        if clave in resultado and resultado[clave] is None:
            resultado[clave] = actual
    return resultado


def ciclo_errores(root, entries, leidas=None, ahora=None):
    """El ciclo del error por firma. Cada eslabon es un hecho externo, no un juicio:

    - capturada: la firma (tipo + sitio) esta en el historico, con sus ocurrencias.
    - leida: alguna captura de la firma se enseno entera (libreta de lecturas).
    - intervenida: el fichero del frame cabecera tiene un commit POSTERIOR a
      ALGUNA ocurrencia (git). Si la firma volvio a petar DESPUES de ese commit
      el eslabon no se borra: queda 'intervenida' con `reapariciones` > 0 — una
      intervencion que no aguanto es informacion valiosa, no ruido.
    - en-silencio: intervenida y cero ocurrencias desde ese commit. SIEMPRE con
      su ventana (`silencio_dias`): "sin reaparecer desde hace N d" es un hecho;
      un veredicto seria re-ejecutar, y eso gb no lo hace.

    `entries` viene de store.read_index (ya filtrado por proyecto y sin efimeros);
    `leidas` de store.read_ids(). `ahora` se inyecta para que los tests no
    dependan del reloj. Devuelve None si no hay firmas. Informa, no bloquea.
    """
    leidas = leidas or set()
    if ahora is None:
        ahora = datetime.datetime.now().astimezone()

    grupos, orden = {}, []
    for entry in entries:
        key = (entry.get("type"), entry.get("where"))
        grupo = grupos.get(key)
        if grupo is None:
            grupo = {
                "type": entry.get("type"),
                "where": entry.get("where"),
                "count": 0,
                "ids": [],
                "ts": [],
                # entries llega de lo mas reciente a lo mas antiguo: la primera
                # vez que se ve una firma es su ocurrencia mas nueva.
                "last_ts": entry.get("ts"),
                "last_id": entry.get("id"),
            }
            grupos[key] = grupo
            orden.append(key)
        grupo["count"] += 1
        if entry.get("id"):
            grupo["ids"].append(entry["id"])
        cuando = store.parse_ts(entry.get("ts"))
        if cuando is not None and cuando.tzinfo is not None:
            grupo["ts"].append(cuando)

    if not grupos:
        return None

    # La cache se siembra con UN solo `git log` para todos los ficheros; si el
    # batch devuelve None, `_ultimo_commit` hace su camino por-fichero de siempre.
    cache_git = {}
    ficheros = [f for f in (_fichero_de_firma(grupos[k]["where"]) for k in orden) if f]
    todos_ts = [t for g in grupos.values() for t in g["ts"]]
    if ficheros and todos_ts:
        batch = _ultimos_commits(root, ficheros, min(todos_ts))
        if batch is not None:
            cache_git.update(batch)

    firmas = []
    for key in orden:
        grupo = grupos[key]
        fichero = _fichero_de_firma(grupo["where"])
        commit = _ultimo_commit(root, fichero, cache_git) if fichero else None
        # Intervenida = commit posterior a ALGUNA ocurrencia: tocar el fichero
        # despues de un fallo es el hecho "alguien intervino", y no se borra
        # porque la firma vuelva a petar despues — eso queda como 'intervenida'
        # con reapariciones > 0, visible como intervencion que no aguanto.
        # (Exigir commit > TODAS las ocurrencias hacia 'intervenida' inalcanzable:
        # con reapariciones el commit dejaba de ser posterior y la firma volvia a
        # capturada, asi que intervenidas == sin_reaparecer siempre.)
        posterior = bool(commit and grupo["ts"] and commit[1] > min(grupo["ts"]))
        tras = sum(1 for t in grupo["ts"] if t > commit[1]) if posterior else 0
        leida = any(ident in leidas for ident in grupo["ids"])
        estado = "leida" if leida else "capturada"
        silencio_dias = None
        if posterior:
            if tras == 0:
                estado = "en-silencio"
                silencio_dias = max(0, int((ahora - commit[1]).total_seconds() // 86400))
            else:
                estado = "intervenida"
        firmas.append(
            {
                "type": grupo["type"],
                "where": grupo["where"],
                "file": fichero,
                "count": grupo["count"],
                "last_ts": grupo["last_ts"],
                "last_id": grupo["last_id"],
                "leida": leida,
                "intervencion": (
                    {"commit": commit[0], "ts": commit[1].isoformat(timespec="seconds")}
                    if posterior
                    else None
                ),
                "reapariciones": tras,
                "estado": estado,
                "silencio_dias": silencio_dias,
            }
        )

    firmas.sort(key=lambda f: (f["count"], f["last_ts"] or ""), reverse=True)
    embudo = {
        "capturadas": len(firmas),
        "leidas": sum(1 for f in firmas if f["leida"]),
        "intervenidas": sum(1 for f in firmas if f["intervencion"]),
        "sin_reaparecer": sum(1 for f in firmas if f["estado"] == "en-silencio"),
    }
    return {"firmas": firmas, "embudo": embudo}
