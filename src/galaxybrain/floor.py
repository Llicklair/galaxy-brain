"""El suelo: el andamiaje que cualquier proyecto necesita antes de construir.

Los siete niveles de `conclusiones-2026-07-29.md` §10, ordenados por impacto medido
—no por lo que suena bien—, comprobados sobre el repo con hechos detectados.

La estructura no es por temas, es por **quién obliga a que sea verdad**, que es la
única lectura que sobrevive al dato de la podredumbre documental (el 60% de la
documentación queda obsoleta en seis meses, porque nada en el proceso la obliga a
seguir siendo cierta):

  Nivel 1 · no puede pudrirse, porque se EJECUTA  — comandos, gates, mapa, fronteras
  Nivel 2 · se escribe una vez y se revisa        — AGENTS.md, ADRs, criterios EARS
  Nivel 3 · solo lo escribe un humano             — el criterio de terminado

Todo lo que se quede en el nivel 3 y no baje al 1 o al 2 se pudre. El trabajo de
este modulo es empujar hacia abajo lo que se pueda, y DECIR lo que no.

INFORMA, NO BLOQUEA (regla 2, devolver y no dictaminar). Un suelo incompleto no es
un delito: es una lista de lo que falta. Gatear esto lo convertiria en ceremonia, y
la ceremonia fue lo que mato a v1.

Nada cableado a ningun proyecto (hard rule 6): todo sale de leer el repo. Lo que ya
resuelve una herramienta del mercado se DELEGA por referencia (regla 7) — la higiene
de proceso (branch protection, deps pinneadas, revision) la mide OpenSSF Scorecard
desde hace anios y no se reimplementa aqui.
"""

import os
import re
import subprocess
import time

#: Umbral de DORA para el bucle de feedback: los tests automaticos tienen que
#: contestar en menos de diez minutos, en local y en CI. No es una opinion — es la
#: capacidad medida, y el motivo esta en el comportamiento que induce: una suite
#: larga entrena a agrupar cambios y a no commitear seguido.
DORA_FEEDBACK_SECONDS = 600

#: Referencia util al leer el informe: la mediana de los equipos buenos.
DORA_ELITE_SECONDS = 163


def _exists(root, *rel):
    return os.path.exists(os.path.join(root, *rel))


def _read(root, *rel):
    try:
        with open(os.path.join(root, *rel), "r", encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return ""


def _first_existing(root, candidates):
    return [c for c in candidates if _exists(root, *c.split("/"))]


def detect_test_command(root):
    """El comando de tests del proyecto, leido de su configuracion.

    Devuelve (comando, fuente) o (None, None). Se detecta, nunca se asume: un repo
    Go no corre pytest, y cablear un comando seria un bug (hard rule 6).
    """
    if _exists(root, "package.json"):
        content = _read(root, "package.json")
        if re.search(r'"scripts"\s*:\s*\{[^}]*"test"\s*:', content, re.DOTALL):
            return "npm test", "package.json"
    if _exists(root, "Cargo.toml"):
        return "cargo test", "Cargo.toml"
    if _exists(root, "go.mod"):
        return "go test ./...", "go.mod"
    pyproject = _read(root, "pyproject.toml")
    if "[tool.pytest" in pyproject:
        return "pytest -q", "pyproject.toml"
    for name in ("pytest.ini", "tox.ini", "setup.cfg"):
        if "pytest" in _read(root, name):
            return "pytest -q", name
    if _exists(root, "Makefile") and re.search(r"^test:", _read(root, "Makefile"), re.MULTILINE):
        return "make test", "Makefile"
    # Ultimo recurso honesto: hay carpeta de tests pero nada que diga como correrlos.
    for folder in ("tests", "test", "spec"):
        if os.path.isdir(os.path.join(root, folder)):
            return None, folder + "/ (hay tests, pero ningun comando declarado)"
    return None, None


#: Configuraciones que declaran una gate determinista. Se mira el fichero, no se
#: ejecuta nada: la presencia de la config es el hecho.
GATE_CONFIGS = {
    "lint": ["ruff.toml", ".ruff.toml", ".flake8", ".pylintrc", ".eslintrc",
             ".eslintrc.json", ".eslintrc.js", "eslint.config.js", "eslint.config.mjs",
             "biome.json", ".golangci.yml", ".golangci.yaml"],
    "tipos": ["mypy.ini", ".mypy.ini", "pyrightconfig.json", "tsconfig.json"],
    "formato": [".prettierrc", ".prettierrc.json", "prettier.config.js", ".editorconfig", "rustfmt.toml"],
}

GATE_INLINE = {
    "lint": ["[tool.ruff", "[flake8]", "[tool.pylint"],
    "tipos": ["[tool.mypy", "[tool.pyright"],
    "formato": ["[tool.black", "[tool.isort"],
}

CI_FILES = [
    ".github/workflows",
    ".gitlab-ci.yml",
    ".circleci/config.yml",
    "azure-pipelines.yml",
    "Jenkinsfile",
]

ISOLATION_FILES = ["Dockerfile", "docker-compose.yml", "compose.yaml", ".devcontainer"]

#: AGENTS.md es el estandar cross-tool (donado a la Linux Foundation en dic-2025;
#: lo leen nativamente Claude Code, Codex, Cursor, Copilot, Gemini CLI, Aider...).
#: Los demas son formatos de UNA herramienta: valen, pero no viajan.
AGENT_FILES = ["AGENTS.md"]
AGENT_FILES_SINGLE_TOOL = ["CLAUDE.md", ".cursorrules", ".github/copilot-instructions.md", "GEMINI.md"]

ADR_DIRS = ["docs/adr", "doc/adr", "adr", "docs/decisions", "docs/architecture/decisions"]


def detect_gates(root):
    found = {}
    for kind, names in GATE_CONFIGS.items():
        hits = _first_existing(root, names)
        if hits:
            found[kind] = hits[0]
    inline_sources = _read(root, "pyproject.toml") + _read(root, "setup.cfg")
    for kind, markers in GATE_INLINE.items():
        if kind not in found:
            for marker in markers:
                if marker in inline_sources:
                    found[kind] = "pyproject.toml/setup.cfg (%s)" % marker.strip("[")
                    break
    return found


def detect_boundaries(root, max_depth=2):
    """Busca `.gb-boundaries` en la raiz o en la raiz del paquete (`src/`, etc.).

    Buscar en vez de mirar solo la raiz no es comodidad: reportar "falta" cuando el
    fichero existe un nivel mas abajo manda a escribir algo que ya esta escrito, y
    un aviso falso es lo que hace que un informe deje de leerse.
    """
    from . import graph

    for depth_root, dirs, files in os.walk(root):
        rel = os.path.relpath(depth_root, root)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        if depth >= max_depth:
            dirs[:] = []
        dirs[:] = [d for d in dirs if d not in graph.DEFAULT_SKIP and not d.startswith(".")]
        if graph.BOUNDARIES_FILE in files:
            path = os.path.join(depth_root, graph.BOUNDARIES_FILE)
            info = graph.load_boundaries(root, path)
            return os.path.relpath(path, root).replace("\\", "/"), len(info["rules"])
    return None, 0


def detect_adrs(root):
    """Registros de decision. Sin ellos, el porque se convierte en folklore y el
    siguiente que pase por aqui —humano o agente— 'arregla' lo que era deliberado."""
    for folder in ADR_DIRS:
        path = os.path.join(root, *folder.split("/"))
        if os.path.isdir(path):
            try:
                files = [f for f in os.listdir(path) if f.endswith(".md")]
            except OSError:
                files = []
            if files:
                return folder, len(files)
    return None, 0


def time_test_command(root, command, timeout=900):
    """Cronometra el comando de tests. Devuelve (segundos, ok) o (None, None).

    Es OPT-IN a proposito: correr la suite de un proyecto ajeno es un efecto
    secundario que autoriza quien lo pide, no algo que un informe hace por su
    cuenta (CLAUDE.md, preguntar antes de maquinaria pesada).
    """
    if not command:
        return None, None
    started = time.time()
    try:
        result = subprocess.run(
            command, cwd=root, shell=True, capture_output=True, timeout=timeout
        )
    except (OSError, subprocess.SubprocessError):
        return None, None
    return time.time() - started, result.returncode == 0


def _level(key, title, status, detail, evidence=None, source=None):
    return {
        "key": key,
        "title": title,
        "status": status,  # ok | parcial | falta | no-detectable
        "detail": detail,
        "evidence": evidence or [],
        "source": source,
    }


def analyze(root, run_tests=False):
    """El informe del suelo. Siete niveles de §10 mas el contexto para agentes.

    `run_tests=True` cronometra la suite contra el umbral de DORA. Sin eso, el
    nivel 1 solo puede decir si HAY comando, no si es rapido — y se dice asi, en
    vez de dar por bueno lo que no se ha medido.
    """
    report = {"root": root, "root_error": None, "levels": [], "not_covered": [], "delegated": []}

    if not os.path.isdir(root):
        report["root_error"] = "la raiz no existe o no es un directorio: %s" % root
        return report

    # 1 — el bucle de feedback. El primero por impacto, y el unico con numero.
    command, source = detect_test_command(root)
    if command is None:
        report["levels"].append(
            _level(
                "feedback", "Bucle de feedback rapido", "falta",
                "no encuentro comando de tests"
                + (" (%s)" % source if source else "; sin tests declarados"),
            )
        )
    elif run_tests:
        seconds, ok = time_test_command(root, command)
        if seconds is None:
            report["levels"].append(
                _level("feedback", "Bucle de feedback rapido", "parcial",
                       "`%s` detectado, pero no pude ejecutarlo" % command, source=source)
            )
        else:
            dentro = seconds < DORA_FEEDBACK_SECONDS
            report["levels"].append(
                _level(
                    "feedback", "Bucle de feedback rapido", "ok" if dentro else "falta",
                    "`%s` tarda %.1fs (%s el umbral DORA de %ds; los buenos van por %ds)%s"
                    % (command, seconds, "dentro de" if dentro else "PASA",
                       DORA_FEEDBACK_SECONDS, DORA_ELITE_SECONDS,
                       "" if ok else " — y ademas la suite NO pasa"),
                    source=source,
                )
            )
    else:
        report["levels"].append(
            _level("feedback", "Bucle de feedback rapido", "parcial",
                   "`%s` detectado; sin cronometrar (usa --time)" % command, source=source)
        )
        report["not_covered"].append(
            "cuanto tarda el ciclo de feedback: detectar el comando no dice si es rapido, "
            "y es justo lo que mide el nivel 1 (--time lo cronometra)"
        )

    # 2 — gates deterministas.
    gates = detect_gates(root)
    ci = _first_existing(root, CI_FILES)
    if gates:
        report["levels"].append(
            _level("gates", "Gates deterministas en un comando", "ok" if len(gates) > 1 else "parcial",
                   "declaradas: %s" % ", ".join("%s (%s)" % (k, v) for k, v in sorted(gates.items())),
                   evidence=sorted(gates.values()))
        )
    else:
        report["levels"].append(
            _level("gates", "Gates deterministas en un comando", "falta",
                   "sin config de lint, tipos ni formato")
        )

    # 3 — el mapa.
    from . import graph

    coupling = graph.analyze(root)
    if coupling["modules"]:
        report["levels"].append(
            _level("mapa", "Un mapa, no una lectura", "ok",
                   "%d modulos, %d aristas, %d ciclo(s) — `gb graph`"
                   % (coupling["modules"], coupling["edges"], len(coupling["cycles"])))
        )
    else:
        report["levels"].append(
            _level("mapa", "Un mapa, no una lectura", "falta",
                   "0 modulos Python analizables desde aqui; hoy `gb graph` solo lee Python")
        )
        report["not_covered"].append(
            "el mapa de un proyecto que no sea Python: `gb graph` no lo cubre todavia"
        )

    # 4 — invariantes escritos.
    bounds_path, rules = detect_boundaries(root)
    report["levels"].append(
        _level("invariantes", "Los invariantes escritos", "ok" if rules else "falta",
               "%d regla(s) en %s" % (rules, bounds_path) if rules
               else "sin .gb-boundaries: las reglas que no estan escritas se rompen, "
                    "y quien las rompe no se entera",
               source=bounds_path)
    )

    # 5 — el porque de lo decidido.
    adr_dir, adr_count = detect_adrs(root)
    report["levels"].append(
        _level("porque", "El porque de lo ya decidido", "ok" if adr_count else "parcial",
               "%d registro(s) en %s" % (adr_count, adr_dir) if adr_count
               # "parcial", no "falta": solo se puede afirmar que no hay ADR en las
               # rutas convencionales. Un proyecto puede llevar sus decisiones en
               # otros documentos, y esto no sabe distinguir una decision razonada
               # de prosa cualquiera. Decir "falta" cuando existe en otro sitio es
               # el aviso falso que hace que un informe deje de leerse.
               else "sin ADR en las rutas convencionales (%s). Si las decisiones viven "
                    "en otros documentos, esto no puede verlo — pero sin registro el "
                    "porque se vuelve folklore y lo deliberado se 'arregla'"
                    % ", ".join(ADR_DIRS[:3]))
    )

    # 6 — equivocarse barato.
    isolation = _first_existing(root, ISOLATION_FILES)
    is_git = _exists(root, ".git")
    senales = []
    if is_git:
        senales.append("git (worktrees disponibles)")
    if isolation:
        senales.append(isolation[0])
    if ci:
        senales.append(ci[0])
    report["levels"].append(
        _level("barato", "Un entorno donde equivocarse salga barato",
               "ok" if len(senales) > 1 else ("parcial" if senales else "falta"),
               ", ".join(senales) if senales else "ni git, ni contenedor, ni CI")
    )

    # 7 — el criterio de terminado. NUNCA detectable, y por eso se pide siempre.
    report["levels"].append(
        _level("terminado", "Un criterio de terminado comprobable", "no-detectable",
               "esto no lo puede mirar ninguna herramienta: lo escribes tu, antes de empezar. "
               "Sin el, la causa numero uno de sobreingenieria sigue abierta")
    )

    # + contexto para agentes (no es de §10; sale del estandar del mercado).
    agents = _first_existing(root, AGENT_FILES)
    single = _first_existing(root, AGENT_FILES_SINGLE_TOOL)
    if agents:
        report["levels"].append(
            _level("agentes", "Contexto ejecutable para agentes", "ok",
                   "AGENTS.md presente (estandar cross-tool)")
        )
    elif single:
        report["levels"].append(
            _level("agentes", "Contexto ejecutable para agentes", "parcial",
                   "hay %s, pero es formato de UNA herramienta; AGENTS.md lo leen todas"
                   % single[0], evidence=single)
        )
    else:
        report["levels"].append(
            _level("agentes", "Contexto ejecutable para agentes", "falta",
                   "sin AGENTS.md: cada agente que entre empieza a ciegas")
        )

    # Lo que NO mira esto, dicho de frente (invariante 4).
    report["delegated"].append(
        "higiene de proceso (branch protection, deps pinneadas, revision, releases firmadas): "
        "lo mide OpenSSF Scorecard, no se reimplementa aqui"
    )
    report["not_covered"].append(
        "si lo que hay es BUENO: esto ve que existe un comando, una gate o un ADR, no si sirven"
    )
    report["not_covered"].append(
        "decisiones registradas fuera de la convencion ADR: no se distinguen de prosa"
    )
    report["not_covered"].append(
        "el techo: donde corre esto, contra que habla, que carga aguanta. Ninguna checklist lo genera"
    )
    return report
