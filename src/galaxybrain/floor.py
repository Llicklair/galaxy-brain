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
    "tipos": ["mypy.ini", ".mypy.ini", "pyrightconfig.json", "pyrefly.toml", "tsconfig.json"],
    "formato": [".prettierrc", ".prettierrc.json", "prettier.config.js", ".editorconfig", "rustfmt.toml"],
}

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
    return found


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
%s
gb graph . --gate --since HEAD || exit 1
gb check --staged --brief
""" % tests


def _plantilla_claude_settings():
    """El arnés del agente, a nivel de PROYECTO: viaja con el repo, mergea con
    lo global de cada máquina y no toca la configuración personal de nadie.

    Los tres canales que hacen el grafo ambiental para el LLM: el mapa al
    arrancar la sesión, el delta tras cada edición (o silencio), y las fichas
    de símbolos en cada búsqueda. Sin esto, la consciencia de gb era artesanía
    del settings global de UNA máquina (prueba de uso, 4-ago): el usuario nuevo
    instalaba, capturaba… y su agente nunca veía el mapa. El modelo no sabe que
    gb existe; lo sabe su contexto — y el contexto se cablea aquí.
    """
    return """{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          { "type": "command", "command": "gb graph --context", "timeout": 15 },
          { "type": "command", "command": "gb symbols --html --watch --fondo --refresco 3", "timeout": 15 }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Edit|Write|NotebookEdit",
        "hooks": [
          { "type": "command", "command": "gb graph --context --if-changed", "timeout": 15 },
          { "type": "command", "command": "gb delta --worktree --brief", "timeout": 15 }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Grep|Glob",
        "hooks": [
          { "type": "command", "command": "gb calls --hook", "timeout": 10 }
        ]
      }
    ]
  }
}
"""


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
        elif graph_mod._git(root, "config", "core.hooksPath", ".githooks") is not None:
            hechos.append({"path": "core.hooksPath", "action": "enganchado"})
        else:
            hechos.append({"path": "core.hooksPath", "action": "no-pude"})

    # El mapa de la raiz es un artefacto DERIVADO que el watch reescribe cada
    # vez que algo cambia: sin esta linea, todo repo con el arnes vive con el
    # arbol sucio («mapa.html baila en cada git status» — reporte de uso real,
    # 7-ago). Aditivo, nunca pisa: si la linea exacta ya esta, no se toca.
    contenido = _read(root, ".gitignore")
    if any(linea.strip() == "mapa.html" for linea in contenido.splitlines()):
        hechos.append({"path": ".gitignore", "action": "ya-cubria mapa.html"})
    else:
        try:
            with open(os.path.join(root, ".gitignore"), "a", encoding="utf-8") as handle:
                if contenido and not contenido.endswith("\n"):
                    handle.write("\n")
                handle.write("# el mapa de gb es derivado: lo reescribe el watch\nmapa.html\n")
            hechos.append({"path": ".gitignore", "action": "mapa.html ignorado"})
        except OSError as error:
            hechos.append({"path": ".gitignore", "action": "error: %s" % error})
    return hechos


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


def analyze(root, run_tests=False):
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
    return report
