"""El suelo: el andamiaje que cualquier proyecto necesita antes de construir.

Los siete niveles del suelo, ordenados por impacto medido —no por lo que suena
bien—, comprobados sobre el repo con hechos detectados.

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
la ceremonia fue lo que mato al enfoque anterior.

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


#: Marca lo que el esqueleto NO puede rellenar solo. Existe para cerrar el lazo:
#: `--init` la pone, y `analyze` la detecta y NO da el nivel por cubierto. Un
#: documento presente pero sin rellenar es PEOR que ausente — pasa la lista y no
#: dice nada, que es como se fabrica un suelo de mentira.
PENDING_MARK = "<!-- gb:pendiente -->"

#: Los imprescindibles. Los tres primeros son la puerta de entrada de cualquiera
#: que llegue al proyecto —incluido tu dentro de seis meses—; los dos ultimos son
#: donde va a parar lo que se aprende. Se escriben pre-rellenados con lo DETECTADO;
#: lo que exige criterio se deja marcado con PENDING_MARK y una razon, nunca con un
#: hueco mudo: un encabezado vacio no se rellena, una pregunta si.
SCAFFOLD_FILES = ["AGENTS.md", "SCOPE.md", "ARCHITECTURE.md", "docs/adr/README.md", "docs/evidencia.md", ".githooks/pre-commit", ".claude/settings.json"]


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


#: fichero que lo declara -> comando de tests de ese ecosistema. Es una TABLA y
#: no una escalera de `if` porque anadir un toolchain tiene que costar una linea.
#:
#: Existia con cinco entradas cuando el grafo ya leia diecisiete lenguajes: el
#: suelo decia "no encuentro comando de tests" en un proyecto Maven o Gradle
#: perfectamente normal. Es la misma asimetria de dos listas de lo mismo que ya
#: habia mordido tres veces esta semana (9-ago).
TOOLCHAINS = (
    ("Cargo.toml", "cargo test"),
    ("go.mod", "go test ./..."),
    ("pom.xml", "mvn -q test"),
    ("build.gradle", "gradle test"),
    ("build.gradle.kts", "gradle test"),
    ("build.sbt", "sbt test"),
    ("mix.exs", "mix test"),
    ("Package.swift", "swift test"),
    ("pubspec.yaml", "dart test"),
    ("Rakefile", "rake test"),
    ("Gemfile", "bundle exec rake test"),
    ("composer.json", "composer test"),
    (".busted", "busted"),
)


def _dotnet(root):
    """Un proyecto .NET se reconoce por su `.sln` o cualquier `.csproj`, que no
    tienen nombre fijo — por eso no cabe en la tabla de arriba."""
    try:
        nombres = os.listdir(root)
    except OSError:
        return None
    for n in nombres:
        if n.endswith((".sln", ".csproj", ".fsproj")):
            return n
    return None


def detect_test_commands(root):
    """Todos los comandos de tests declarados, uno por ecosistema, en orden de
    preferencia: [(comando, fuente), ...].

    Un repo mixto tiene mas de una suite: tach (Rust + Python) declara `cargo
    test` y pytest, y quedarse con el primero escondia la de Python — medido
    comparando el suelo de repos parecidos el 24-sep-2026. `make test` solo
    entra si no hay nada mas: suele envolver a los otros.
    """
    encontrados = []
    if _exists(root, "package.json"):
        content = _read(root, "package.json")
        if re.search(r'"scripts"\s*:\s*\{[^}]*"test"\s*:', content, re.DOTALL):
            encontrados.append(("npm test", "package.json"))
    for fichero, comando in TOOLCHAINS:
        if _exists(root, fichero):
            encontrados.append((comando, fichero))
            break
    proyecto = _dotnet(root)
    if proyecto:
        encontrados.append(("dotnet test", proyecto))
    if "[tool.pytest" in _read(root, "pyproject.toml"):
        encontrados.append(("pytest -q", "pyproject.toml"))
    else:
        for name in ("pytest.ini", "tox.ini", "setup.cfg"):
            if "pytest" in _read(root, name):
                encontrados.append(("pytest -q", name))
                break
    if (not encontrados and _exists(root, "Makefile")
            and re.search(r"^test:", _read(root, "Makefile"), re.MULTILINE)):
        encontrados.append(("make test", "Makefile"))
    return encontrados


def detect_test_command(root):
    """El comando de tests del proyecto, leido de su configuracion.

    Devuelve (comando, fuente) o (None, None). Se detecta, nunca se asume: un repo
    Go no corre pytest, y cablear un comando seria un bug (hard rule 6).
    """
    encontrados = detect_test_commands(root)
    if encontrados:
        return encontrados[0]
    # Ultimo recurso honesto: hay carpeta de tests pero nada que diga como correrlos.
    for folder in ("tests", "test", "spec"):
        if os.path.isdir(os.path.join(root, folder)):
            return None, folder + "/ (hay tests, pero ningun comando declarado)"
    return None, None


#: Configuraciones que declaran una gate determinista. Se mira el fichero, no se
#: ejecuta nada: la presencia de la config es el hecho.
#: Medido sobre los 18 repos del banco de repos reales (24-sep-2026): con solo
#: las configs de Python/JS/Go, 7 decian "falta" teniendo la suya delante
#: (`.eslintrc.yml`, `phpstan.neon`, `.luacheckrc`, `checkstyle.xml`,
#: `analysis_options.yaml`...). El criterio de `floor` es 0 avisos falsos.
GATE_CONFIGS = {
    "lint": ["ruff.toml", ".ruff.toml", ".flake8", ".pylintrc", ".eslintrc",
             ".eslintrc.json", ".eslintrc.js", ".eslintrc.cjs", ".eslintrc.yml", ".eslintrc.yaml",
             "eslint.config.js", "eslint.config.mjs", "eslint.config.cjs", "eslint.config.ts",
             "biome.json", "biome.jsonc", ".golangci.yml", ".golangci.yaml", ".golangci.toml",
             ".rubocop.yml", "phpstan.neon", "phpstan.neon.dist", "psalm.xml",
             "clippy.toml", ".clippy.toml", "detekt.yml", ".swiftlint.yml", ".credo.exs",
             "analysis_options.yaml", ".clang-tidy", "checkstyle.xml", ".luacheckrc",
             ".scalafix.conf"],
    "tipos": ["mypy.ini", ".mypy.ini", "pyrightconfig.json", "pyrefly.toml", "tsconfig.json"],
    "formato": [".prettierrc", ".prettierrc.json", ".prettierrc.yml", ".prettierrc.yaml",
                ".prettierrc.js", ".prettierrc.cjs", "prettier.config.js", "prettier.config.mjs",
                "prettier.config.cjs", ".editorconfig", "rustfmt.toml", ".rustfmt.toml",
                ".scalafmt.conf", ".clang-format", ".swiftformat", ".stylua.toml", "stylua.toml",
                ".php-cs-fixer.php", ".php-cs-fixer.dist.php", ".formatter.exs", "dprint.json"],
}

#: Lenguajes cuyo compilador YA comprueba tipos: en ellos no hace falta una
#: config aparte, y decir "sin tipos" sobre jsoup o google/uuid era falso.
TIPADO_POR_COMPILADOR = ("java", "kotlin", "scala", "csharp", "swift", "go", "rust",
                         "dart", "c")

GATE_INLINE = {
    "lint": ["[tool.ruff", "[flake8]", "[tool.pylint"],
    "tipos": ["[tool.mypy", "[tool.pyright", "[tool.pyrefly"],
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
    if "tipos" not in found:
        from . import lenguajes

        try:
            presentes = {lang for _r, lang in lenguajes._ficheros(root)}
        except Exception:   # noqa: BLE001 - sin tabla no se afirma nada
            presentes = set()
        tipados = sorted(presentes & set(TIPADO_POR_COMPILADOR))
        if tipados:
            found["tipos"] = "el compilador (%s)" % ", ".join(tipados)
    return found


#: Invariantes escritos con OTRA herramienta: cuentan igual (regla 7, se delega
#: por referencia). Medido el 24-sep-2026: el suelo de import-linter y de tach
#: decia "falta" con sus contratos declarados delante. (fichero, marcador, quien).
INVARIANTES_EXTERNOS = (
    (".importlinter", None, "import-linter"),
    ("setup.cfg", "[importlinter", "import-linter"),
    ("pyproject.toml", "[tool.importlinter", "import-linter"),
    ("tach.toml", None, "tach"),
)


def detect_invariantes_externos(root):
    """[(fichero, herramienta)] de los contratos de arquitectura ajenos a gb."""
    hallados = []
    for fichero, marcador, quien in INVARIANTES_EXTERNOS:
        if not _exists(root, fichero):
            continue
        if marcador is None or marcador in _read(root, fichero):
            if all(q != quien for _f, q in hallados):
                hallados.append((fichero, quien))
    return hallados


def inventario_boundaries(root, max_depth=2):
    """Todos los `.gb-boundaries` hasta `max_depth`: [(ruta, reglas, aristas)].

    `detect_boundaries` da el que MANDA desde `root` (la raiz gana), que es lo
    que carga la gate analizando desde ahi. Pero el suelo pregunta otra cosa —si
    los invariantes estan escritos— y un repo puede tener en la raiz solo aristas
    declaradas y las prohibiciones en `src/`, donde las carga `gb graph src`.
    Medido sobre el propio gb el 24-sep-2026: decia "sin .gb-boundaries" con dos.
    """
    from . import graph

    hallados = []
    for actual, dirs, files in os.walk(root):
        rel = os.path.relpath(actual, root)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        if depth >= max_depth:
            dirs[:] = []
        dirs[:] = sorted(d for d in dirs if d not in graph.DEFAULT_SKIP and not d.startswith("."))
        if graph.BOUNDARIES_FILE in files:
            path = os.path.join(actual, graph.BOUNDARIES_FILE)
            info = graph.load_boundaries(root, path)
            hallados.append((
                os.path.relpath(path, root).replace("\\", "/"),
                len(info["rules"]),
                len(info["declared_edges"]),
            ))
    return hallados


def detect_boundaries(root, max_depth=2):
    """Busca `.gb-boundaries` en la raiz o en la raiz del paquete (`src/`, etc.).

    Buscar en vez de mirar solo la raiz no es comodidad: reportar "falta" cuando el
    fichero existe un nivel mas abajo manda a escribir algo que ya esta escrito, y
    un aviso falso es lo que hace que un informe deje de leerse.

    La busqueda vive en `graph` desde 2026-07-31: tener DOS reglas de descubrimiento
    (esta, que buscaba, y la de `graph`, que solo miraba la raiz) hacia que `floor`
    viera el fichero y la gate de `check` no. Una sola, compartida, o la
    incoherencia vuelve.
    """
    from . import graph

    path = graph.find_boundaries(root, max_depth)
    if path is None:
        return None, 0
    info = graph.load_boundaries(root, path)
    return os.path.relpath(path, root).replace("\\", "/"), len(info["rules"])


def _raiz_del_repo_por_encima(root):
    """La raiz del repo git que CONTIENE a `root`, si `root` no es esa raiz.

    None cuando `root` ya es la raiz, o cuando no hay repo. No se sube a mirar
    nada: solo se averigua si lo que estas midiendo es una parte de un todo, para
    poder decirlo. Cambiar el numero seria peor — `floor src` tiene que seguir
    respondiendo por `src`.
    """
    from . import graph

    salida = graph._git(root, "rev-parse", "--show-toplevel")
    if not salida:
        return None
    repo = os.path.abspath(salida.strip())
    if os.path.normcase(repo) == os.path.normcase(os.path.abspath(root)):
        return None
    return repo


def detect_adrs(root):
    """Registros de decision. Sin ellos, el porque se convierte en folklore y el
    siguiente que pase por aqui —humano o agente— 'arregla' lo que era deliberado."""
    for folder in ADR_DIRS:
        path = os.path.join(root, *folder.split("/"))
        if os.path.isdir(path):
            try:
                # El indice de la carpeta NO es una decision. Contarlo daria el nivel
                # por cubierto con cero decisiones registradas — y lo crea el propio
                # `--init`, asi que el esqueleto se aprobaria a si mismo.
                files = [
                    f for f in os.listdir(path)
                    if f.endswith(".md") and f.lower() not in ("readme.md", "index.md")
                ]
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


def _plantilla_agents(nombre, comando, gates, modulos):
    gates_txt = (
        "\n".join("- %s: `%s`" % (k, v) for k, v in sorted(gates.items()))
        if gates
        else "%s Sin gate de lint/tipos declarada. Es el nivel 2 del suelo: sin ella, "
        "cada revision discute estilo en vez de discutir el cambio." % PENDING_MARK
    )
    return """# %s

Contexto ejecutable para agentes. Formato [AGENTS.md](https://agents.md), que leen
Claude Code, Codex, Cursor, Copilot, Gemini CLI y Aider — a diferencia de un fichero
de una sola herramienta.

## Comandos

Lo de esta seccion se EJECUTA, asi que no puede pudrirse en silencio: si miente, falla.

```bash
%s
```

## Gates

%s

## Cuando algo pete (contrato con gb)

- Si muere un script, CLI o servidor: lee el estado YA capturado — `gb show <id>` (el aviso
  trae el id) o `gb last` — antes de re-ejecutar con prints. La ficha llega con su nodo del
  grafo y quien le llama.
- Para saber quien llama a un simbolo o que rompes al tocarlo: `gb calls <simbolo> [--depth 2]`
  antes de grepear o abrir ficheros a mano.
- Si el proyecto aun no tiene codigo y hay que elegir lenguaje: proponlo tu segun lo que se va
  a construir, y mete como un dato mas lo que gb ve en cada uno (`gb floor --json`, clave
  `cobertura`: grafo, tests estrechados, consola). gb no elige; da el hecho.
- De vez en cuando, `gb list`: el embudo capturada→leida→intervenida→en-silencio es el
  termometro del proyecto. No usar gb tambien es dato: se investiga, no se esconde.

## Arquitectura

%s

## Convenciones de commit y PR

%s Escribe aqui el formato de commit y que exige un PR para entrar. Sin esto, cada
agente inventa el suyo y el historico deja de poder leerse.
""" % (
        nombre,
        comando or (PENDING_MARK + " Sin comando de tests detectado. Declaralo aqui."),
        gates_txt,
        (
            "%d modulos analizados; el mapa vivo esta en `gb graph` (se deriva del "
            "codigo, asi que no se desincroniza)." % modulos
            if modulos
            else PENDING_MARK + " Describe en dos lineas como se divide el proyecto."
        ),
        PENDING_MARK,
    )


def _plantilla_scope(nombre):
    return """# %s — alcance

## En una frase

%s Una sola frase. Si algo no cabe en ella, no entra. Esa frase es la que despues
te deja decir que no sin discutir.

## Lo que NO entra

%s **Esta es la mitad que sostiene peso.** Un alcance que solo enumera funcionalidades
es una lista de deseos; lo que frena el crecimiento es la lista de lo descartado, con
su motivo. Escribe aqui lo que has decidido no hacer — sobre todo lo que te apetece.

## Criterio de terminado

%s Comprobable, escrito ANTES de la primera linea de codigo. No "que funcione bien":
algo que se pueda mirar y responder si o no. Es la cura mas barata que existe contra
la sobreingenieria, cuya causa numero uno es no saber cuando parar.

**Escribelo como COMANDO y deja de ser una intencion.** Lo de dentro de esta valla
se puede ejecutar, asi que un bucle que construya y verifique sabra cuando ha
terminado — y `gb floor` te dira si hoy pasa. En prosa nadie puede comprobarlo:

```gb:terminado
# sustituye esto por el comando que decide que el MVP esta terminado.
# ejemplos: `pytest tests/test_mvp.py -q` · `npm run e2e` · `go test ./caso`
```

Que el criterio sea BUENO sigue sin poder juzgarlo ninguna herramienta (`exit 0`
tambien pasa), asi que esta capa del suelo no se marca en verde nunca.
""" % (nombre, PENDING_MARK, PENDING_MARK, PENDING_MARK)


def _plantilla_architecture(nombre):
    return """# %s — la ley de diseno

Reglas **numeradas**, y lo de numeradas no es cosmetico: una regla con numero se cita
en una revision ("esto viola la 3") y una cita decide. Un principio en prosa no se cita,
y lo que no se cita no ata.

Una regla entra aqui solo si alguna vez vas a poder decir que algo la incumple.

1. %s
2. …

## Como se cambia esto

%s Di quien puede cambiar una regla y que hace falta para retirarla. Sin esto, la ley
se erosiona sola y nadie sabe cuando dejo de aplicarse.
""" % (nombre, PENDING_MARK + " Primera regla.", PENDING_MARK)


def _plantilla_adr():
    return """# Registros de decision (ADR)

Un fichero por decision: `0001-titulo-corto.md`. Formato
[MADR](https://adr.github.io/): contexto, decision, consecuencias.

## Cuando se escribe uno

Solo si la decision cambia **arquitectura, operacion, postura de seguridad o coste de
mantenimiento a largo plazo**. Con ese disparador salen pocos y se leen; sin el salen
doscientos y no se lee ninguno, que es la forma elegante de no tener ninguno.

## Por que

Sin registro del porque, la arquitectura se vuelve folklore: el siguiente que llegue
—persona o agente— repite los mismos debates, reabre lo cerrado y a veces elimina la
restriccion que mantenia el sistema en pie. Eso ultimo es lo caro.
"""


def _plantilla_evidencia():
    return """# Evidencia — la libreta

Cada medicion real: que se probo, que salio, que cambio por ello.

**Los resultados negativos se escriben con el mismo detalle que los positivos, o mas.**
Un proyecto que solo registra lo que funciono no tiene evidencia: tiene publicidad. Y el
dato que no esta en el repo, no existe — la memoria de nadie cuenta.

## Formato

`## AAAA-MM-DD · que se probo — VEREDICTO`, y debajo: montaje, resultado, consecuencia.

---

%s Primera entrada cuando midas algo. Si al mes no hay ninguna, la pregunta no es esta
libreta: es si estas midiendo algo.
""" % PENDING_MARK


def _plantilla_precommit(comando):
    """El gate enganchable del día uno — antes había que cablearlo a mano, que es
    exactamente lo contrario de "la norma va en el defecto" (prueba de uso, 4-ago).

    Solo bloquea hechos: un ciclo de imports NUEVO o un cruce de frontera
    declarada; `check` informa y sigue. El trinquete (`--since HEAD`) deja pasar
    la deuda heredada — así el mismo hook sirve en un repo recién nacido y en
    uno ya empezado sin fabricar falsos positivos.
    """
    tests = (
        "%s || exit 1" % comando
        if comando
        else "# %s declara aqui tu comando de tests (y quita esta linea)" % PENDING_MARK
    )
    return """#!/bin/sh
# Enganchado UNA vez con: git config core.hooksPath .githooks
# UTF-8 en la salida de Python aunque la consola sea cp1252 (Windows): sin esto
# los guiones y tildes del gate salen como basura en el log del commit.
export PYTHONUTF8=1
%s
gb graph . --gate --since HEAD --brief || exit 1
gb check --staged --brief
""" % tests


def _plantilla_claude_settings():
    """El arnés del agente, a nivel de PROYECTO: viaja con el repo, mergea con
    lo global de cada máquina y no toca la configuración personal de nadie.

    UN canal: el mapa comprimido al arrancar la sesión. Hubo tres — delta tras
    cada edición, fichas en cada búsqueda — y se retiraron el 13-ago-2026 con
    la medición delante: informar por acción no cambia nada (0/6), y un defecto
    que no cambia resultados es ruido pagado (sentencia por capa en SCOPE.md).
    El de sesión queda en observación con criterio de muerte escrito. El modelo
    no sabe que gb existe; lo sabe su contexto — y el contexto se cablea aquí.
    """
    return """{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          { "type": "command", "command": "gb graph --context", "timeout": 15 }
        ]
      }
    ]
  }
}
"""


#: Encabezados que declaran un criterio de terminado. Se busca el ENCABEZADO y no
#: la frase suelta: una mencion de pasada en un parrafo no es un criterio, y
#: contarla seria fabricar cobertura — el suelo de mentira que este modulo existe
#: para no construir.
_CRITERIO_RE = re.compile(
    r"^#{1,4}\s.*(criterios?\s+de\s+terminado|definition\s+of\s+done|terminado\s*\()",
    re.IGNORECASE | re.MULTILINE,
)

#: Donde se mira. No se recorre el repo entero: un criterio vive en los
#: documentos de decision, y buscar en todas partes invitaria a falsos positivos.
_CRITERIO_DOCS = ("SCOPE.md", "README.md", "ARCHITECTURE.md", "CLAUDE.md", "AGENTS.md")


#: El criterio de terminado, escrito como COMANDO. La valla lleva etiqueta
#: explicita (```gb:terminado) a proposito: adivinar "el primer bloque de codigo
#: bajo el encabezado" convertiria un ejemplo de prosa en un veredicto.
#:
#: Un criterio en prosa no se puede juzgar — por eso esa capa del suelo nunca se
#: marca en verde. Uno escrito como comando SI se puede EJECUTAR, y entonces deja
#: de ser una intencion y pasa a ser un hecho. Lo que sigue sin poder juzgarse es
#: si el criterio es BUENO (`exit 0` tambien pasa), asi que el nivel se queda en
#: no-detectable y lo unico que cambia es cuanta informacion da.
_CRITERIO_CMD_RE = re.compile(
    r"^```gb:terminado\s*\n(.*?)^```", re.MULTILINE | re.DOTALL)


def criterio_ejecutable(root):
    """(comando, fichero) del criterio de terminado, o (None, None).

    Se busca en los mismos documentos que el criterio en prosa: vive donde se
    declara el alcance, no en un fichero nuevo (restar antes que pulir).
    """
    for rel in _CRITERIO_DOCS:
        m = _CRITERIO_CMD_RE.search(_read(root, rel))
        if m:
            lineas = [ln.strip() for ln in m.group(1).splitlines()
                      if ln.strip() and not ln.strip().startswith("#")]
            if lineas:
                return "\n".join(lineas), rel
    return None, None


def correr_criterio(root, comando=None, timeout=1800):
    """Ejecuta el criterio y devuelve (paso, detalle). `None` si no hay criterio.

    Es el unico sitio de gb donde se ejecuta un comando que viene ESCRITO EN EL
    REPO ANALIZADO: `criterio_ejecutable` lo saca de un bloque ```gb:terminado
    de SCOPE/README/ARCHITECTURE/CLAUDE/AGENTS.md, y aqui va a `shell=True`. En
    tu propio repo eso lo escribiste tu; en un repo ajeno lo escribio su autor,
    que es la diferencia que importa — y por eso lo pide explicitamente quien
    llama: el camino por defecto no ejecuta nada de nadie.

    Hoy NADA de `src/galaxybrain/` llama aqui (solo `bucle/escalera.py`, que no
    viaja en el wheel) — pero esta funcion SI se instala con el paquete. El dia
    que algo de la CLI la llame, gb pasa a ejecutar comandos controlados por el
    repo que analiza: ese es el disparador de re-auditoria, y esta escrito aqui
    para que se lea antes de anadir el llamante.
    """
    if comando is None:
        comando, _fuente = criterio_ejecutable(root)
    if not comando:
        return None, "sin criterio de terminado ejecutable"
    try:
        p = subprocess.run(comando, shell=True, cwd=root, capture_output=True,
                           timeout=timeout)
    except (OSError, subprocess.SubprocessError) as error:
        return False, "el criterio no pudo ejecutarse: %s" % error
    return p.returncode == 0, "`%s` -> exit %d" % (comando.splitlines()[0], p.returncode)


#: El RECORRIDO. Las capas se ordenan por impacto medido; esto es el otro eje —
#: en qué orden se desbloquean. No son 8 capas en 4 fases uno a uno:
#:
#:   - la fase 3 no tiene ninguna capa. Construir no es un estado del proyecto,
#:     es lo que haces cuando el suelo esta puesto.
#:   - `terminado` sale DOS veces con preguntas distintas: en la 1 "¿lo has
#:     escrito?" y en la 4 "¿pasa?". Es la misma capa y no cuenta dos.
#:   - `porque` es transversal: se acumula en todas, no pertenece a ninguna.
#:
#: Y el criterio de terminado va PRIMERO, no al final. Es la regla del proyecto
#: (se escribe antes de la primera linea) y ahora ademas es lo que la fase de
#: construccion usa para saber cuando ha terminado: al final no serviria de nada.
FASES = (
    ("declarar", "Declarar — solo lo puedes escribir tu",
     ("terminado", "invariantes")),
    ("verificador", "Montar el verificador — que exista quien juzgue",
     ("feedback", "gates", "mapa", "barato", "agentes")),
    ("construir", "Construir — con el verificador puesto", ()),
    ("cerrar", "Cerrar — el criterio de terminado pasa", ()),
)

#: No pertenece a ninguna fase porque pertenece a todas.
TRANSVERSAL = ("porque",)


def _fase_de(clave):
    for nombre, _titulo, claves in FASES:
        if clave in claves:
            return nombre
    return "transversal" if clave in TRANSVERSAL else ""


def siguiente_paso(report):
    """La UNA cosa por la que empezar, o None si el suelo esta puesto.

    Se deriva del informe y del orden de las fases: la primera capa sin cubrir de
    la fase mas temprana. Devolver una lista de ocho deberes no ayuda a nadie —
    lo que desbloquea es saber cual va antes y por que.
    """
    porques = {
        "terminado": "sin el, la fase de construccion no puede saber cuando ha terminado",
        "invariantes": "sin invariantes escritos, el verificador no tiene nada que comprobar "
                       "y su verde solo significa 'no hay reglas'",
        "feedback": "sin comando de tests no hay veredicto que automatizar",
        "gates": "sin gates, cada revision depende de que alguien se acuerde",
        "mapa": "sin grafo no hay onda del cambio ni seleccion de tests",
        "barato": "sin worktrees, equivocarse cuesta el arbol principal",
        "agentes": "sin AGENTS.md, cada agente que entra empieza a ciegas",
    }
    estado = {n["key"]: n for n in report.get("levels", [])}
    for _nombre, _titulo, claves in FASES:
        for clave in claves:
            nivel = estado.get(clave) or {}
            # `no-detectable` cuenta como pendiente SOLO si no hay nada escrito:
            # el criterio nunca se marca en verde, pero declararlo si es un hecho.
            cubierto = nivel.get("status") == "ok" or (
                nivel.get("status") == "no-detectable" and nivel.get("evidence"))
            if not cubierto:
                return {"capa": clave, "titulo": nivel.get("title") or clave,
                        "fase": _fase_de(clave), "porque": porques.get(clave, "")}
    return None


#: Comandos dentro de vallas de codigo. Se lee el documento entero y no solo la
#: seccion "Comandos": el titulo de la seccion varia entre proyectos y exigir uno
#: concreto seria cablear una convencion (hard rule 6).
_VALLA_RE = re.compile(r"^```(?:bash|sh|shell|console)?\s*\n(.*?)^```", re.MULTILINE | re.DOTALL)

#: La primera palabra identifica la herramienta. Comparar la linea entera daria
#: falsos positivos por cualquier bandera: `pytest -q --strict` NO contradice a
#: `pytest -q`, es el mismo toolchain con otras opciones.
_HERRAMIENTAS = ("pytest", "npm", "yarn", "pnpm", "cargo", "go", "mvn", "gradle",
                 "sbt", "mix", "swift", "dart", "rake", "bundle", "composer",
                 "busted", "dotnet", "make", "tox", "nox", "lua", "php", "ruby")


def comandos_declarados(root, rel="AGENTS.md"):
    """Las herramientas que el documento dice usar. Hecho: esta escrito ahi."""
    fuera = []
    for bloque in _VALLA_RE.findall(_read(root, rel)):
        for linea in bloque.splitlines():
            linea = linea.strip().lstrip("$ ").strip()
            if not linea or linea.startswith("#"):
                continue
            primera = linea.split()[0]
            if primera in _HERRAMIENTAS:
                fuera.append((primera, linea))
    return fuera


def divergencia_de_comandos(root):
    """Lo ESCRITO contra lo DETECTADO, o None si no hay contradiccion.

    Es la podredumbre documental medida en su propia mano: un AGENTS.md que dice
    `npm test` en un repo que corre `pytest` manda a quien lo lea —humano o
    agente— a ejecutar algo que no existe. Y no es opinion: las dos mitades son
    hechos, una leida del documento y otra detectada del proyecto.

    Solo se compara la HERRAMIENTA, nunca la linea entera: `pytest -q --strict`
    no contradice a `pytest -q`. Un falso "te falta" es lo que hace que un
    informe deje de leerse, y este modulo existe para no fabricarlos.
    """
    detectado, _fuente = detect_test_command(root)
    if not detectado:
        return None
    herramienta = detectado.split()[0]
    declarados = comandos_declarados(root)
    if not declarados:
        return None                     # no dice nada: eso no es contradecir
    if any(h == herramienta for h, _linea in declarados):
        return None
    return {"detectado": detectado, "declarado": declarados[0][1],
            "herramientas": sorted({h for h, _l in declarados})}


def _busca_criterio(root):
    """Documentos que declaran un criterio de terminado. Hecho, no juicio."""
    hallados = []
    for rel in _CRITERIO_DOCS:
        if _CRITERIO_RE.search(_read(root, rel)):
            hallados.append(rel)
    carpeta = os.path.join(root, "docs")
    if os.path.isdir(carpeta):
        try:
            nombres = sorted(os.listdir(carpeta))
        except OSError:
            nombres = []
        for nombre in nombres:
            if nombre.lower().endswith(".md") and _CRITERIO_RE.search(_read(root, "docs", nombre)):
                hallados.append("docs/" + nombre)
    return hallados


def _level(key, title, status, detail, evidence=None, source=None):
    return {
        "key": key,
        "title": title,
        "status": status,  # ok | parcial | falta | no-detectable
        "detail": detail,
        "evidence": evidence or [],
        "source": source,
    }


def scaffold(root):
    """Deja los imprescindibles, pre-rellenados con lo detectado.

    **Nunca pisa un fichero existente.** Un esqueleto que sobreescribe la ley de un
    proyecto seria peor que no existir; ante un fichero presente, se informa y se deja.

    Lo que se puede detectar se escribe con su valor real —comandos, gates, numero de
    modulos—, y va al nivel 1: se ejecuta, luego no puede pudrirse en silencio. Lo que
    exige criterio se deja con PENDING_MARK y **la razon por la que importa**, nunca un
    encabezado mudo: un hueco vacio no se rellena, una pregunta si.
    """
    from . import graph

    nombre = os.path.basename(os.path.normpath(root)) or "proyecto"
    comando, _fuente = detect_test_command(root)
    gates = detect_gates(root)
    modulos = graph.analyze(root)["modules"]

    contenidos = {
        "AGENTS.md": _plantilla_agents(nombre, comando, gates, modulos),
        "SCOPE.md": _plantilla_scope(nombre),
        "ARCHITECTURE.md": _plantilla_architecture(nombre),
        "docs/adr/README.md": _plantilla_adr(),
        "docs/evidencia.md": _plantilla_evidencia(),
        ".githooks/pre-commit": _plantilla_precommit(comando),
        ".claude/settings.json": _plantilla_claude_settings(),
    }

    hechos = []
    for rel in SCAFFOLD_FILES:
        destino = os.path.join(root, *rel.split("/"))
        if os.path.exists(destino):
            hechos.append({"path": rel, "action": "ya-existia"})
            continue
        try:
            os.makedirs(os.path.dirname(destino), exist_ok=True)
            with open(destino, "w", encoding="utf-8") as handle:
                handle.write(contenidos[rel])
            if rel.endswith("pre-commit"):
                try:
                    os.chmod(destino, 0o755)  # en POSIX un hook sin +x no corre
                except OSError:
                    pass
            hechos.append({"path": rel, "action": "creado"})
        except OSError as error:
            hechos.append({"path": rel, "action": "error: %s" % error})

    # El enganche, AUTOMATICO: un pre-commit sin core.hooksPath es decoracion, y
    # "acuerdate del git config" fallo en uso real el mismo dia que se estreno el
    # arnes (7-ago: el hook existia, inactivo, y lo tuvo que sugerir el LLM — la
    # inversion exacta de la norma-en-el-defecto). --init ES el si explicito del
    # usuario; la salvaguarda es no pisar: un hooksPath ajeno se respeta y se dice.
    from . import graph as graph_mod

    if graph_mod._git(root, "rev-parse", "--git-dir") is None:
        hechos.append({"path": "core.hooksPath", "action": "sin-git"})
    else:
        actual = (graph_mod._git(root, "config", "core.hooksPath") or "").strip()
        if actual == ".githooks":
            hechos.append({"path": "core.hooksPath", "action": "ya-enganchado"})
        elif actual:
            hechos.append({"path": "core.hooksPath", "action": "respetado: %s" % actual})
        elif _hooks_propios(root, graph_mod):
            # Enganchar `.githooks` APAGA en silencio lo que ya vive en
            # .git/hooks (auditoria del 24-sep-2026): se respeta y se dice.
            hechos.append({
                "path": "core.hooksPath",
                "action": "respetado: ya hay hooks en .git/hooks (%s); "
                          "enganchar .githooks los apagaria — combinalos a mano"
                          % ", ".join(_hooks_propios(root, graph_mod)),
            })
        elif graph_mod._git(root, "config", "core.hooksPath", ".githooks") is not None:
            hechos.append({"path": "core.hooksPath", "action": "enganchado"})
        else:
            hechos.append({"path": "core.hooksPath", "action": "no-pude"})

    return hechos


def _hooks_propios(root, graph_mod):
    """Los hooks activos de `.git/hooks` (los `.sample` no cuentan)."""
    ruta = (graph_mod._git(root, "rev-parse", "--git-path", "hooks") or "").strip()
    if not ruta:
        return []
    ruta = ruta if os.path.isabs(ruta) else os.path.join(root, ruta)
    try:
        nombres = os.listdir(ruta)
    except OSError:
        return []
    return sorted(n for n in nombres
                  if not n.endswith(".sample") and os.path.isfile(os.path.join(ruta, n)))


def pending_sections(root):
    """Documentos del esqueleto que existen pero siguen sin rellenar.

    Es el cierre del lazo: `--init` los crea marcados y esto los delata. Un documento
    que existe y no dice nada pasa cualquier lista de comprobacion sin aportar nada —
    exactamente el suelo de mentira que este modulo existe para no fabricar.
    """
    pendientes = []
    for rel in SCAFFOLD_FILES:
        if _exists(root, *rel.split("/")) and PENDING_MARK in _read(root, *rel.split("/")):
            pendientes.append(rel)
    return pendientes


#: Orden de la consola en la tabla de cobertura: lo que observa desde dentro,
#: lo que lee stderr desde fuera, y lo que no tiene via medida.
_RANGO_CONSOLA = {"hook-nativo": 0, "fallback-stderr": 1, "desactivado": 2}


def cobertura_por_lenguaje():
    """Lo que gb ve en cada lenguaje, derivado de sus tablas — nunca escrito a mano.

    Para un proyecto SIN codigo, donde hay que elegir lenguaje (24-sep-2026).
    gb no elige: depende de que se construye, y eso lo sabe quien lo pide y su
    agente, no un analisis sin modelo (reglas 1 y 8). Lo que si es un hecho es
    donde gb cubre mas, y eso entra en la decision como un dato entre otros.

    Sale de `lenguajes.LENGUAJES` (licencia `tia`) y `consola.MECANISMOS` (via),
    asi que no se desfasa: un lenguaje que gana licencia sube solo de fila.
    """
    from . import consola, lenguajes

    filas = [{"lenguaje": "python", "grafo": True, "tests": True,
              "consola": consola.mecanismo("python")["via"]}]
    for lang in sorted(lenguajes.LENGUAJES):
        ficha = consola.mecanismo(lang) or {}
        filas.append({"lenguaje": lang, "grafo": True,
                      "tests": bool(lenguajes.LENGUAJES[lang].get("tia")),
                      "consola": ficha.get("via") or "desactivado"})
    filas.sort(key=lambda f: (not f["tests"], _RANGO_CONSOLA.get(f["consola"], 3)))
    return filas


def analyze(root, run_tests=False, constructor=None):
    """El informe del suelo. Siete niveles de §10 mas el contexto para agentes.

    `run_tests=True` cronometra la suite contra el umbral de DORA. Sin eso, el
    nivel 1 solo puede decir si HAY comando, no si es rapido — y se dice asi, en
    vez de dar por bueno lo que no se ha medido.
    """
    report = {
        "root": root,
        "root_error": None,
        "levels": [],
        "not_covered": [],
        "delegated": [],
        "subdir_de": None,
    }

    if not os.path.isdir(root):
        report["root_error"] = "la raiz no existe o no es un directorio: %s" % root
        return report

    # El suelo se mide donde se lo pides, y eso esta bien: `floor src` responde por
    # `src`. Lo que NO puede pasar es callar que `src` esta dentro de un proyecto
    # cuya raiz tiene los tests, la CI y el git que aqui salen como ausentes. El
    # numero no cambia; cambia lo que significa, y sin decirlo se lee como un
    # diagnostico del proyecto. Reportado usando gb de verdad (1-ago-2026).
    report["subdir_de"] = _raiz_del_repo_por_encima(root)

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
    otras = detect_test_commands(root)[1:]
    if command is not None and otras:
        report["levels"][-1]["detail"] += " · tambien: " + ", ".join(
            "`%s` (%s)" % par for par in otras
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

    # 3 — el mapa. Lo cubre `gb graph`, y punto.
    #
    # Aqui colgaba una coletilla de GitNexus ("instalado, pero este repo NO esta
    # indexado"). Se retira: su justificacion —`gb graph` ve modulos, GitNexus ve
    # simbolos y llamadas— es de ANTES de que existiera `gb symbols`, que hoy ve
    # simbolos y llamadas con un 93% de recall medido contra el propio GitNexus y
    # cero dependencias (docs/pruebas-de-uso.md). Lo unico que ese indice sigue
    # anadiendo es inferencia de tipos, y `gb symbols` ya declara ese limite en su
    # propia salida, que es donde toca.
    #
    # Colgar un "te falta esto" de un nivel YA marcado como cubierto fabrica una
    # tarea que no existe: es dictaminar en vez de devolver (regla 2).
    from . import companions, graph

    # El mismo motor que elige la CLI: sin el constructor, aqui se analizaba
    # SOLO Python y un repo JS salia con "0 modulos" — y el detalle llegaba a
    # decir que `gb graph` no lee otra cosa, que desde el 15-ago es falso. Un
    # informe que declara de menos empuja a la conclusion contraria a la real.
    coupling = graph.analyze(root, constructor=constructor)
    if coupling["modules"]:
        report["levels"].append(
            _level("mapa", "Un mapa, no una lectura", "ok",
                   "%d modulos, %d aristas, %d ciclo(s) — `gb graph`"
                   % (coupling["modules"], coupling["edges"], len(coupling["cycles"])))
        )
    else:
        report["levels"].append(
            _level("mapa", "Un mapa, no una lectura", "falta",
                   "0 modulos analizables desde aqui (ni Python ni los 16 lenguajes "
                   "de ast-grep); si el codigo esta en otra carpeta, apunta ahi")
        )
        report["not_covered"].append(
            "el mapa de un lenguaje fuera de la tabla: `gb graph` no lo cubre"
        )

    # 4 — invariantes escritos.
    bounds_path, _rules = detect_boundaries(root)
    ficheros = inventario_boundaries(root)
    con_reglas = [(ruta, n) for ruta, n, _aristas in ficheros if n]
    externos = detect_invariantes_externos(root)
    if con_reglas or externos:
        partes = ["%d regla(s) en %s" % (n, ruta) for ruta, n in con_reglas]
        partes += ["contratos en %s (%s)" % par for par in externos]
        detalle = "; ".join(partes)
        if con_reglas and bounds_path and all(r != bounds_path for r, _n in con_reglas):
            # La que manda desde aqui no prohibe nada: la gate las carga
            # analizando desde la carpeta de las reglas, no desde la raiz.
            detalle += " (desde la raiz manda %s, sin prohibiciones: la gate va con `gb graph %s`)" % (
                bounds_path, os.path.dirname(con_reglas[0][0]) or ".")
        nivel = _level("invariantes", "Los invariantes escritos", "ok", detalle,
                       source=con_reglas[0][0] if con_reglas else externos[0][0])
    elif ficheros:
        ruta, _n, aristas = ficheros[0]
        nivel = _level(
            "invariantes", "Los invariantes escritos", "falta",
            "%s existe pero no prohibe nada (%d arista(s) declarada(s) `=>`, 0 reglas "
            "`-/->`): las fronteras que no estan escritas se rompen sin que nadie se entere"
            % (ruta, aristas),
            source=ruta,
        )
    else:
        nivel = _level(
            "invariantes", "Los invariantes escritos", "falta",
            "sin .gb-boundaries: las reglas que no estan escritas se rompen, "
            "y quien las rompe no se entera",
        )
    report["levels"].append(nivel)

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

    # 7 — el criterio de terminado. Su CALIDAD no es detectable jamas —por eso el
    # estado nunca pasa a "ok"— pero su EXISTENCIA sí: es texto en un documento.
    # Distinguirlas importa porque el mensaje viejo acusaba a quien SÍ lo habia
    # escrito ("sin el, la causa numero uno sigue abierta"), y un "falta" falso
    # es lo que hace que un informe deje de leerse. Medido el 8-ago: los dos
    # repos reales que usan gb tienen su criterio en SCOPE.md y ambos recibian
    # el reproche.
    donde_criterio = _busca_criterio(root)
    comando_criterio, fuente_criterio = criterio_ejecutable(root)
    if comando_criterio:
        # Escrito como COMANDO deja de ser una intencion y pasa a ser algo que se
        # puede EJECUTAR — y entonces un bucle puede saber si termino. Lo que
        # sigue sin poder juzgarse es si el criterio es bueno (`exit 0` tambien
        # pasa), asi que el nivel se queda en no-detectable igual: lo unico que
        # cambia es cuanta informacion da.
        detalle_criterio = (
            "EJECUTABLE en %s: `%s` — se puede correr, asi que un bucle puede saber "
            "cuando ha terminado. Que sea un BUEN criterio sigue sin poder juzgarlo "
            "nadie, y por eso esta capa no se marca en verde nunca"
            % (fuente_criterio, comando_criterio.splitlines()[0][:90]))
    elif donde_criterio:
        detalle_criterio = (
            "en prosa, en %s — que exista es un hecho; si es COMPROBABLE solo lo sabes "
            "tu. Escrito como comando (valla ```gb:terminado) se podria EJECUTAR, y un "
            "bucle sabria cuando parar" % ", ".join(donde_criterio))
    else:
        detalle_criterio = (
            "no encuentro ninguno escrito, y esto no lo puede mirar ninguna herramienta: "
            "lo escribes tu, antes de empezar. Sin el, la causa numero uno de "
            "sobreingenieria sigue abierta")
    report["levels"].append(
        _level("terminado", "Un criterio de terminado comprobable", "no-detectable",
               detalle_criterio,
               evidence=([fuente_criterio] if comando_criterio else donde_criterio))
    )

    # + contexto para agentes (no es de §10; sale del estandar del mercado).
    agents = _first_existing(root, AGENT_FILES)
    single = _first_existing(root, AGENT_FILES_SINGLE_TOOL)
    pendientes = pending_sections(root)
    report["pending"] = pendientes
    ratio, herramientas = companions.tool_generated_ratio(_read(root, "AGENTS.md")) if agents else (0.0, [])
    if agents and ratio > 0.7:
        # Existe, pero lo escribio una herramienta para si misma. Darlo por bueno
        # seria aprobar el continente ignorando el contenido: quien llegue no
        # encuentra como arrancar el proyecto, encuentra un anuncio.
        report["levels"].append(
            _level("agentes", "Contexto ejecutable para agentes", "esqueleto",
                   "AGENTS.md existe pero el %d%% lo genero %s, no es el contexto del proyecto"
                   % (round(ratio * 100), " y ".join(herramientas) or "una herramienta"),
                   evidence=herramientas)
        )
    elif agents and "AGENTS.md" in pendientes:
        # Existe pero sigue siendo el esqueleto. Darlo por cubierto seria el suelo
        # de mentira: pasa la lista sin decir nada.
        report["levels"].append(
            _level("agentes", "Contexto ejecutable para agentes", "esqueleto",
                   "AGENTS.md existe pero conserva marcas sin rellenar")
        )
    elif agents and divergencia_de_comandos(root):
        # El documento existe y esta relleno, pero CONTRADICE al proyecto: manda
        # a quien lo lea —humano o agente— a ejecutar algo que no esta. Es la
        # podredumbre documental cazada con un hecho, no con una opinion sobre
        # si esta "completo". Parcial y nunca `falta`: el fichero SI aporta, y un
        # "te falta" falso es lo que hace que un informe deje de leerse.
        _div = divergencia_de_comandos(root)
        report["levels"].append(
            _level("agentes", "Contexto ejecutable para agentes", "parcial",
                   "AGENTS.md dice `%s` pero este proyecto corre `%s`: quien lo lea "
                   "ejecutara algo que no existe"
                   % (_div["declarado"], _div["detectado"]),
                   evidence=["AGENTS.md"])
        )
    elif agents:
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

    # + proyecto sin codigo: la cobertura de gb por lenguaje, para quien elija.
    if not graph.lenguajes_presentes(root, con_python=True):
        report["cobertura"] = cobertura_por_lenguaje()

    # + la consola de errores: no es un nivel de §10 (no mueve fases ni el
    # siguiente paso), es un aviso. Los lenguajes del proyecto cuyas muertes no
    # dejarian captura en la shell desde la que se corre floor.
    from . import consola

    report["consola"] = [
        {"lenguaje": f["lenguaje"], "via": f["via"], "armado": f["armado"],
         "arranque": f["arranque"]}
        for f in consola.pendientes(root)
    ]

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
    if pendientes:
        report["not_covered"].append(
            "si lo escrito en los documentos es CIERTO: solo se ve si quedan marcas sin rellenar"
        )
    # El RECORRIDO va al final a proposito: necesita TODOS los niveles ya
    # anadidos. Calcularlo a media lista dejaba el ultimo sin fase, y el
    # siguiente paso se derivaba de un informe incompleto.
    for nivel in report["levels"]:
        nivel["fase"] = _fase_de(nivel["key"])
    report["fases"] = [{"nombre": n, "titulo": t, "capas": list(c)} for n, t, c in FASES]
    report["siguiente"] = siguiente_paso(report)
    return report
