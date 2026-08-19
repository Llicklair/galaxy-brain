#!/usr/bin/env python3
"""
gb-run.py — Multi-language crash capture orchestrator for galaxy-brain.

Wraps any command with the appropriate language-specific crash hooks,
generating a shared GB_SESSION_ID so all crashes from a single invocation
can be correlated.

Usage:
    python gb-run.py <command> [args...]

Examples:
    python gb-run.py node app.js
    python gb-run.py python main.py
    python gb-run.py go run ./cmd
    python gb-run.py cargo run

Zero external dependencies — only Python 3 stdlib.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# -------------------------------------------------------------------
# Config
# -------------------------------------------------------------------

HOOKS_DIR = Path(__file__).resolve().parent
CRASHES_DIR = Path.home() / ".galaxy-brain"
CRASHES_FILE = CRASHES_DIR / "crashes.jsonl"


# -------------------------------------------------------------------
# Language detection
# -------------------------------------------------------------------

# Each entry: (language_name, file_globs_or_markers)
LANGUAGE_MARKERS: list[tuple[str, list[str]]] = [
    ("python",  [".py"]),
    ("node",    ["package.json", ".js", ".ts", ".mjs", ".cjs"]),
    ("go",      ["go.mod", ".go"]),
    ("ruby",    ["Gemfile", ".rb"]),
    ("php",     ["composer.json", ".php"]),
    ("rust",    ["Cargo.toml", ".rs"]),
    ("csharp",  [".csproj", ".cs"]),
    ("java",    [".java", "pom.xml", "build.gradle", "build.gradle.kts"]),
    ("lua",     [".lua"]),
    # Dart y elixir no llevan hook DENTRO del programa (el suyo exige tocar el
    # codigo del usuario): se cubren leyendo su stderr desde fuera, igual que go
    # y rust. Por eso solo hace falta reconocer el proyecto.
    # C faltaba en esta tabla, asi que el envolvente nunca lo daba por presente
    # y el arranque de su hook no se activaba jamas. Su lenguaje estaba medido,
    # empaquetado y construido... y aqui invisible (experimento poliglota).
    ("c",       [".c", ".h"]),
    ("dart",    ["pubspec.yaml", ".dart"]),
    ("elixir",  ["mix.exs", ".ex", ".exs"]),
]


def detect_languages(directory: str) -> list[str]:
    """Scan `directory` for language markers. Returns list of detected languages."""
    detected: list[str] = []
    try:
        entries = os.listdir(directory)
    except OSError:
        return detected

    # Build a set of extensions and exact filenames present
    extensions: set[str] = set()
    filenames: set[str] = set()
    for entry in entries:
        filenames.add(entry)
        _, ext = os.path.splitext(entry)
        if ext:
            extensions.add(ext)

    for lang, markers in LANGUAGE_MARKERS:
        for marker in markers:
            if marker.startswith("."):
                # It's an extension
                if marker in extensions:
                    detected.append(lang)
                    break
            else:
                # It's an exact filename
                if marker in filenames:
                    detected.append(lang)
                    break

    return detected


# -------------------------------------------------------------------
# Env var setup per language
# -------------------------------------------------------------------

def setup_env(
    detected_languages: list[str],
    session_id: str,
    env: dict[str, str],
) -> list[str]:
    """
    Configure environment variables for each detected language's hook.
    APPENDS to existing env vars (never overwrites).
    Returns a list of human-readable activation messages.
    """
    activated: list[str] = []
    hooks_dir = str(HOOKS_DIR)
    # Normalize to forward slashes for consistency in env vars
    hooks_dir_fwd = hooks_dir.replace("\\", "/")

    # Always set the session ID
    env["GB_SESSION_ID"] = session_id

    # W3C Trace Context por variable de entorno: el estandar que OpenTelemetry
    # define EXACTAMENTE para cruzar procesos cuando no hay red (CI, batch,
    # subprocess). Se siembra aqui la raiz; cada hook que pueda leera este
    # TRACEPARENT, se anotara como hijo del span que traiga, generara el suyo y
    # lo exportara para SUS hijos.
    #
    # Por que esto y no los pids: el pid del padre no se puede preguntar en
    # varios runtimes (lua, php y C# no tienen API portable) y el envolvente no
    # puede atribuir lo que lee de un stderr. La variable, en cambio, la hereda
    # todo hijo sin que nadie coopere.
    if not env.get("TRACEPARENT"):
        env["TRACEPARENT"] = "00-%s-%s-01" % (
            uuid.uuid4().hex, uuid.uuid4().hex[:16])

    for lang in detected_languages:
        if lang == "python":
            # Python hooks use .pth files; just ensure GB_SESSION_ID is set (done above)
            activated.append("python: GB_SESSION_ID set (existing .pth hook will read it)")

        elif lang == "node":
            hook_path = os.path.join(hooks_dir, "gb-hook.js")
            node_require = f"--require {hook_path}"
            existing = env.get("NODE_OPTIONS", "")
            if hook_path not in existing:
                env["NODE_OPTIONS"] = f"{existing} {node_require}".strip()
            activated.append(f"node: NODE_OPTIONS += --require gb-hook.js")

        elif lang == "go":
            # NO se toca GOTRACEBACK. Lo ponia en "all" para tener mas traza, y
            # eso CAMBIA el stderr del programa observado — justo lo que el
            # criterio 5 prohibe. La deteccion no lo necesita: el bloque
            # "goroutine N [running]:" lo imprime Go por defecto. Medido con los
            # 16 lenguajes a la vez, 19-ago-2026.
            activated.append("go: se lee su stderr tal cual (sin tocar GOTRACEBACK)")

        elif lang == "ruby":
            hook_path = os.path.join(hooks_dir, "gb-hook.rb")
            ruby_require = f"-r{hook_path}"
            existing = env.get("RUBYOPT", "")
            if hook_path not in existing:
                env["RUBYOPT"] = f"{existing} {ruby_require}".strip()
            activated.append(f"ruby: RUBYOPT += -r gb-hook.rb")

        elif lang == "php":
            hook_path = os.path.join(hooks_dir, "gb-hook.php")
            # PHP auto_prepend_file via ini setting
            existing = env.get("PHP_INI_SCAN_DIR", "")
            # Use -d flag approach via PHP_INI; note for user
            env["GB_PHP_HOOK"] = hook_path
            activated.append(
                f"php: GB_PHP_HOOK set (use: php -d auto_prepend_file={hook_path})"
            )

        elif lang == "rust":
            # Igual que go: RUST_BACKTRACE=1 añadia un "stack backtrace:" entero
            # al stderr del programa. Se gana frames y se pierde la propiedad
            # que sostiene toda esta capa — que mirar no cambie lo mirado. El
            # panic sigue trayendo tipo, mensaje y fichero:linea:columna; quien
            # quiera frames pone RUST_BACKTRACE el mismo, que es su decision.
            activated.append("rust: se lee su stderr tal cual (sin tocar RUST_BACKTRACE)")

        elif lang == "csharp":
            # `dotnet/`, no `dotnet-hook/`: es donde lo deja el instalador de gb
            # (`gb on --lenguajes`). Con la ruta vieja el envolvente decia "dll
            # not found, skipped" y C# se quedaba sin consola en un repo mixto
            # sin que nadie se enterara — el aviso se pierde entre las demas
            # lineas. Visto en el experimento poliglota, 19-ago-2026.
            hook_dll = os.path.join(hooks_dir, "dotnet", "GbHook.dll")
            if os.path.isfile(hook_dll):
                existing = env.get("DOTNET_STARTUP_HOOKS", "")
                sep = ";" if sys.platform == "win32" else ":"
                if hook_dll not in existing:
                    if existing:
                        env["DOTNET_STARTUP_HOOKS"] = f"{existing}{sep}{hook_dll}"
                    else:
                        env["DOTNET_STARTUP_HOOKS"] = hook_dll
                activated.append("csharp: DOTNET_STARTUP_HOOKS += GbHook.dll")
            else:
                activated.append("csharp: DOTNET_STARTUP_HOOKS (dll not found, skipped)")

        elif lang == "java":
            jar_path = os.path.join(hooks_dir, "jvm", "gb-agent.jar")
            if os.path.isfile(jar_path):
                agent_flag = f"-javaagent:{jar_path}"
                existing = env.get("JAVA_TOOL_OPTIONS", "")
                if jar_path not in existing:
                    env["JAVA_TOOL_OPTIONS"] = f"{existing} {agent_flag}".strip()
                activated.append("java: JAVA_TOOL_OPTIONS += -javaagent:gb-agent.jar")
            else:
                activated.append("java: JAVA_TOOL_OPTIONS (jar not found, skipped)")

        elif lang == "lua":
            hook_path = os.path.join(hooks_dir, "gb-hook.lua")
            # Lua's LUA_INIT runs code at startup; we use it to dofile the hook
            # Note: LUA_INIT with @ prefix loads a file
            existing = env.get("LUA_INIT", "")
            if not existing:
                env["LUA_INIT"] = f"@{hook_path}"
                activated.append("lua: LUA_INIT set to load gb-hook.lua")
            else:
                activated.append("lua: LUA_INIT already set, skipped (run via gb-hook.lua wrapper)")

    return activated


# -------------------------------------------------------------------
# Stderr crash detection (reused from gb-stderr-parser.py)
# -------------------------------------------------------------------

#: El tipo, DERIVADO del mensaje. Escribir la constante "panic" en los dos
#: lenguajes fue lo que disparo el criterio de aborto de la ADR 0012 el
#: 18-ago-2026 — y se disparo mal: el dato SI estaba en stderr, era el parser el
#: que no lo miraba. Medido: 6 de 9 formas reales de panic dan tipo (67 %).
#: Las otras tres siguen diciendo "panic", declarado y no inventado: un tipo a
#: ojo es peor que ninguno, porque manda a buscar el fallo que no es.
_TIPOS_POR_MENSAJE = (
    ("nil pointer dereference", "runtime error: nil pointer dereference"),
    ("index out of range", "runtime error: index out of range"),
    ("index out of bounds", "index out of bounds"),
    ("integer divide by zero", "runtime error: integer divide by zero"),
    ("slice bounds out of range", "runtime error: slice bounds out of range"),
    ("Option::unwrap()", "Option::unwrap on None"),
    ("Result::unwrap()", "Result::unwrap on Err"),
    ("attempt to subtract with overflow", "attempt to subtract with overflow"),
    ("attempt to add with overflow", "attempt to add with overflow"),
)


def tipo_de_mensaje(mensaje: str, por_defecto: str = "panic") -> str:
    """La clase del fallo a partir del texto, o `por_defecto` si no se sabe."""
    bajo = (mensaje or "").lower()
    for aguja, tipo in _TIPOS_POR_MENSAJE:
        if aguja.lower() in bajo:
            return tipo
    return por_defecto


def detect_go_crash(stderr: str) -> dict[str, Any] | None:
    """Detect a Go panic in stderr output."""
    goroutine_match = re.search(r"goroutine\s+(\d+)\s+\[running\]:", stderr)
    if not goroutine_match:
        return None

    goroutine_id = int(goroutine_match.group(1))
    panic_match = re.search(r"^panic:\s*(.+)$", stderr, re.MULTILINE)
    panic_message = panic_match.group(1).strip() if panic_match else "unknown panic"

    runtime_err = re.search(r"^(runtime error:.+)$", stderr, re.MULTILINE)
    if runtime_err and not panic_match:
        panic_message = runtime_err.group(1).strip()

    frames: list[dict[str, Any]] = []
    block_start = goroutine_match.end()
    block_match = re.search(r"\n(?:goroutine \d+|\Z|\n\n)", stderr[block_start:])
    block_end = block_start + block_match.start() if block_match else len(stderr)
    block = stderr[block_start:block_end]

    frame_re = re.compile(r"^\t(.+):(\d+)\s", re.MULTILINE)
    func_re = re.compile(r"^(\S+)\(", re.MULTILINE)
    func_names = func_re.findall(block)
    file_lines = frame_re.findall(block)

    for i, (file, line) in enumerate(file_lines):
        func_name = func_names[i] if i < len(func_names) else "<unknown>"
        frames.append({
            "file": file, "line": int(line), "column": 0, "function": func_name,
        })

    tb_start = panic_match.start() if panic_match else goroutine_match.start()
    traceback_text = stderr[tb_start:block_end].strip()

    return {
        "language": "go", "exc_type": tipo_de_mensaje(panic_message),
        "exc_message": panic_message,
        "origin": f"goroutine-{goroutine_id}", "frames": frames,
        "traceback": traceback_text,
    }


def detect_rust_crash(stderr: str) -> dict[str, Any] | None:
    """Detect a Rust panic in stderr output."""
    panic_match = re.search(
        r"thread '(.+?)'\s*(?:\(\d+\)\s*)?panicked at '(.+?)',\s*(.+?):(\d+):(\d+)",
        stderr,
    )
    if not panic_match:
        panic_match2 = re.search(
            r"thread '(.+?)'\s*(?:\(\d+\)\s*)?panicked at (.+?):(\d+):(\d+):\n(.+)",
            stderr,
        )
        if not panic_match2:
            return None
        thread = panic_match2.group(1)
        file = panic_match2.group(2)
        line = int(panic_match2.group(3))
        col = int(panic_match2.group(4))
        message = panic_match2.group(5).strip()
    else:
        thread = panic_match.group(1)
        message = panic_match.group(2)
        file = panic_match.group(3)
        line = int(panic_match.group(4))
        col = int(panic_match.group(5))

    frames = [{"file": file, "line": line, "column": col, "function": "<panic>"}]
    bt_re = re.compile(r"^\s*\d+:\s+(?:0x[0-9a-f]+ - )?(.+?)$", re.MULTILINE)
    for m in bt_re.finditer(stderr):
        fn_text = m.group(1).strip()
        if fn_text and "note:" not in fn_text:
            frames.append({"file": "", "line": 0, "column": 0, "function": fn_text})

    return {
        "language": "rust", "exc_type": tipo_de_mensaje(message), "exc_message": message,
        "origin": f"thread-{thread}", "frames": frames,
        "traceback": stderr.strip(),
    }


def detect_dart_crash(stderr: str) -> dict[str, Any] | None:
    """Detect a Dart unhandled exception in stderr output.

    Dart quedo fuera de la consola porque su UNICO gancho interno
    (`runZonedGuarded`) es manejo puro: lleva el exit code de 255 a 0, borra la
    traza y exige reescribir el `main()` del usuario. Eso sigue siendo cierto —
    y por eso aqui no se instala nada dentro del programa. Se lee su stderr
    desde fuera, que es la misma via que ya cubre go y rust, con el mismo techo:
    solo se ve lo que mata al proceso.
    """
    cabecera = re.search(r"^Unhandled exception:\s*\n(.+)$", stderr, re.MULTILINE)
    if not cabecera:
        return None
    linea = cabecera.group(1).strip()

    # `RangeError (length): Invalid value: ...` -> tipo y mensaje separados.
    tipo_match = re.match(r"^([A-Z][A-Za-z0-9_]*)(?:\s*\([^)]*\))?\s*:\s*(.*)$", linea)
    if tipo_match:
        exc_type, message = tipo_match.group(1), tipo_match.group(2).strip()
    else:
        exc_type, message = "UnhandledException", linea

    frames: list[dict[str, Any]] = []
    for frame in re.finditer(r"^#\d+\s+(.+?)\s+\((.+?)(?::(\d+))?(?::(\d+))?\)\s*$",
                             stderr, re.MULTILINE):
        frames.append({
            "function": frame.group(1).strip(),
            "file": frame.group(2),
            "line": int(frame.group(3)) if frame.group(3) else 0,
            "column": int(frame.group(4)) if frame.group(4) else 0,
        })

    return {
        "language": "dart", "exc_type": exc_type, "exc_message": message,
        "origin": "main", "frames": frames,
        "traceback": stderr[cabecera.start():].strip(),
    }


def detect_elixir_crash(stderr: str) -> dict[str, Any] | None:
    """Detect an Elixir/Erlang crash in stderr output.

    Mismo motivo que dart: su hook pide editar tu `config.exs` y definir el
    modulo en tu `lib/`, o sea tocar el codigo de quien lo instala. Desde fuera
    no hace falta.

    **Sin medir**: no hay Erlang en esta maquina (su instalador exige
    elevacion), asi que esto esta escrito contra el formato documentado y NO
    contra una ejecucion real. Va declarado en `consola.MECANISMOS` para que
    nadie lo lea como verificado.
    """
    error = re.search(r"^\*\*\s+\((\w+(?:\.\w+)*)\)\s*(.*)$", stderr, re.MULTILINE)
    if not error:
        return None

    frames: list[dict[str, Any]] = []
    for frame in re.finditer(r"^\s+(?:\([^)]*\)\s+)?(\S+):(\d+):\s+(.+)$",
                             stderr, re.MULTILINE):
        frames.append({
            "function": frame.group(3).strip(),
            "file": frame.group(1),
            "line": int(frame.group(2)),
            "column": 0,
        })

    return {
        "language": "elixir", "exc_type": error.group(1),
        "exc_message": error.group(2).strip(),
        "origin": "process", "frames": frames,
        "traceback": stderr[error.start():].strip(),
    }


STDERR_DETECTORS = [detect_go_crash, detect_rust_crash,
                    detect_dart_crash, detect_elixir_crash]


def _normaliza_saltos(stderr: str) -> str:
    r"""CRLF -> LF.

    En Windows el stderr llega con \r\n y los patrones de panic piden \n: sin
    esto, `thread 'main' panicked at x.rs:4:21:` + mensaje no casaba nunca y el
    registro no se escribia. Medido con rustc 1.95 el 19-ago-2026.
    """
    return stderr.replace("\r\n", "\n")


def detect_stderr_crashes(stderr: str) -> list[dict[str, Any]]:
    """TODOS los crashes que se reconozcan en ese stderr, uno por lenguaje.

    En un repo mixto este stderr es el del arbol de procesos entero: go, rust y
    dart pueden haber reventado en la misma cadena. Devolver solo el primero
    tiraba dos crashes reales a la basura sin decirlo.
    """
    stderr = _normaliza_saltos(stderr)
    fuera = []
    for detector in STDERR_DETECTORS:
        try:
            resultado = detector(stderr)
        except Exception:
            continue
        if resultado is not None:
            fuera.append(resultado)
    return fuera


def detect_stderr_crash(stderr: str) -> dict[str, Any] | None:
    """Run Go/Rust detectors on stderr; return first match or None."""
    stderr = _normaliza_saltos(stderr)
    for detector in STDERR_DETECTORS:
        try:
            result = detector(stderr)
            if result is not None:
                return result
        except Exception:
            continue
    return None


# -------------------------------------------------------------------
# Record building and writing
# -------------------------------------------------------------------

def find_project_root(start: str) -> str | None:
    """Walk up from `start` looking for a .git directory."""
    cur = Path(start).resolve()
    while True:
        if (cur / ".git").exists():
            return str(cur)
        parent = cur.parent
        if parent == cur:
            return None
        cur = parent


def redact_argv(argv: list[str]) -> list[str]:
    """Keep flag names, replace their values with <val>."""
    result: list[str] = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if re.match(r"^--?[a-zA-Z]", arg):
            eq_idx = arg.find("=")
            if eq_idx != -1:
                result.append(arg[: eq_idx + 1] + "<val>")
            else:
                result.append(arg)
                if i + 1 < len(argv) and not re.match(r"^--?[a-zA-Z]", argv[i + 1]):
                    result.append("<val>")
                    i += 1
        else:
            result.append(arg)
        i += 1
    return result


def _trace_vigente() -> dict[str, Any]:
    """`trace_id` y `parent_span` del TRACEPARENT que hay ahora en el entorno."""
    partes = (os.environ.get("TRACEPARENT") or "").split("-")
    if len(partes) != 4 or len(partes[1]) != 32:
        return {}
    fuera = {"trace_id": partes[1]}
    if len(partes[2]) == 16:
        fuera["parent_span"] = partes[2]
    return fuera


def build_stderr_record(
    crash: dict[str, Any],
    session_id: str,
    child_argv: list[str],
    child_pid: int | None,
) -> dict[str, Any]:
    """Build a schema-v2 crash record from a stderr-detected crash."""
    cwd = os.getcwd()
    return {
        "schema": 2,
        "ts": datetime.now(timezone.utc).astimezone().isoformat(),
        "session_id": session_id,
        "language": crash["language"],
        "exception": {
            "type": crash["exc_type"],
            "message": crash["exc_message"],
            "origin": crash["origin"],
        },
        "frames": crash["frames"],
        "process": {
            "cwd": cwd,
            "project": find_project_root(cwd),
            "argv_forma": redact_argv(child_argv),
            "runtime": f"gb-run/{crash['language']}",
            # SIN pid, y a proposito. Este registro sale de leer un stderr, y ese
            # texto no dice QUE proceso lo escribio: en un arbol mixto el panic
            # puede venir de un nieto. Poner aqui el pid del proceso envuelto
            # inventaba un padre —js aparecia colgando de dart— y con eso la
            # cadena reconstruida despues era falsa. Un hueco declarado vale mas
            # que un dato que parece bueno (19-ago-2026).
            "pid": None,
            "ppid": None,
            "pid_envuelto": child_pid,
            "pid_envolvente": os.getpid(),
        },
        "traceback": crash["traceback"],
        "capture_method": "stderr",
        # El trace vigente cuando se lanzo el programa. NO es el padre inmediato
        # —el panic puede venir de un nieto y el texto no dice de quien— sino el
        # ultimo ancestro que pudo rotar el TRACEPARENT. Es un enlace REAL, no
        # el mas fino: mejor un ancestro cierto que ningun sitio en el mapa.
        **_trace_vigente(),
    }


def write_record(record: dict[str, Any]) -> None:
    """Append a record to crashes.jsonl. Swallows all errors."""
    try:
        CRASHES_DIR.mkdir(parents=True, exist_ok=True)
        with open(CRASHES_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


# -------------------------------------------------------------------
# Session summary
# -------------------------------------------------------------------

def print_session_summary(session_id: str) -> int:
    """
    Check crashes.jsonl for records matching this session_id.
    Print a summary and return the count.
    """
    if not CRASHES_FILE.exists():
        return 0

    crashes: list[dict[str, Any]] = []
    try:
        with open(CRASHES_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    if record.get("session_id") == session_id:
                        crashes.append(record)
                except (json.JSONDecodeError, KeyError):
                    continue
    except OSError:
        return 0

    if not crashes:
        return 0

    short_id = session_id[:8]
    print(
        f"\n[gb run] Session {short_id} — {len(crashes)} crash(es) captured:",
        file=sys.stderr,
    )
    for i, crash in enumerate(crashes, 1):
        lang = crash.get("language", "?")
        exc = crash.get("exception", {})
        exc_type = exc.get("type", "?")
        exc_msg = exc.get("message", "")
        # Truncate long messages
        if len(exc_msg) > 60:
            exc_msg = exc_msg[:57] + "..."

        # Try to get the first relevant frame location
        frames = crash.get("frames", [])
        location = ""
        if frames:
            f = frames[0]
            fname = os.path.basename(f.get("file", ""))
            fline = f.get("line", "?")
            if fname:
                location = f" ({fname}:{fline})"

        # Con el prefijo `[gb run]`, como TODO lo que escribe el envolvente. Sin
        # el, esta linea se mezclaba con el stderr del programa y no habia forma
        # de distinguirla de algo que hubiera escrito el: cualquiera que compare
        # la salida contra una ejecucion sin envolvente ve una diferencia y no
        # sabe de quien es. El envolvente ya no es transparente por definicion,
        # pero al menos todo lo suyo lleva su firma (19-ago-2026).
        print(f"[gb run]   {i}. {lang}: {exc_type} — {exc_msg}{location}", file=sys.stderr)

    return len(crashes)


# -------------------------------------------------------------------
# Determine if stderr wrapping is needed
# -------------------------------------------------------------------

def needs_stderr_capture(cmd_name: str, detected: list[str] | None = None) -> bool:
    """Return True if the command should have its stderr captured for crash detection.

    Historia (19-ago-2026): esto miraba SOLO el nombre del comando, asi que
    `gb-run.py cargo run` capturaba y `gb-run.py ./mi_binario` no — y lanzar el
    binario ya compilado es lo normal, no la excepcion. El envolvente decia
    "stderr capture active" y luego no miraba nada: peor que no capturar,
    porque el usuario cree que si.

    Ahora manda tambien el PROYECTO: si en el directorio hay go o rust, lo que
    corra ahi puede panicar y su stderr se lee.
    """
    base = os.path.basename(cmd_name).lower()
    # Strip .exe on Windows
    if base.endswith(".exe"):
        base = base[:-4]
    if base in ("go", "cargo", "rustc", "dart", "elixir", "mix", "iex"):
        return True
    return any(lang in ("go", "rust", "dart", "elixir") for lang in (detected or ()))


# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------

def main() -> int:
    if len(sys.argv) < 2:
        print(
            "Usage: python gb-run.py <command> [args...]\n"
            "\n"
            "Examples:\n"
            "  python gb-run.py node app.js\n"
            "  python gb-run.py python main.py\n"
            "  python gb-run.py go run ./cmd\n",
            file=sys.stderr,
        )
        return 2

    child_argv = sys.argv[1:]
    cmd_name = child_argv[0]

    # Verify hooks directory exists
    if not HOOKS_DIR.is_dir():
        print(
            f"[gb run] ERROR: hooks directory not found: {HOOKS_DIR}",
            file=sys.stderr,
        )
        return 2

    # Generate session ID
    session_id = str(uuid.uuid4())

    # Detect languages in the current directory
    cwd = os.getcwd()
    detected = detect_languages(cwd)

    # Set up environment
    env = os.environ.copy()
    activated = setup_env(detected, session_id, env)

    # El envolvente TAMBIEN entra en el trace. Sin esto, `_trace_vigente()` leia
    # su propio entorno —donde no habia TRACEPARENT, porque solo se pone en el
    # del hijo— y los registros de go, rust y dart salian sin trace: capturados y
    # sueltos, otra vez.
    if env.get("TRACEPARENT"):
        os.environ["TRACEPARENT"] = env["TRACEPARENT"]

    # Also set GB_PPID for cross-language correlation
    env["GB_PPID"] = str(os.getpid())

    # Print detection results
    short_id = session_id[:8]
    print(f"[gb run] Session {short_id}", file=sys.stderr)
    if detected:
        print(f"[gb run] Detected languages: {', '.join(detected)}", file=sys.stderr)
    else:
        print("[gb run] No language markers found in current directory", file=sys.stderr)

    for msg in activated:
        print(f"[gb run]   + {msg}", file=sys.stderr)

    print(f"[gb run] Running: {' '.join(child_argv)}", file=sys.stderr)
    print(file=sys.stderr)

    # C en Windows no tiene nada que se herede: su unica via es el envolvente
    # depurador, y en `--arbol` cubre tambien a los nietos. Sin esto, en un repo
    # mixto un binario de C llamado por otro programa se queda sin consola — y
    # el resto del arbol si la tiene, que es la peor mezcla: parece que cubres
    # todo. Solo se mete si el proyecto TIENE C y el envolvente esta construido.
    if "c" in detected and sys.platform == "win32":
        envolvente_c = HOOKS_DIR / "c" / "gb-run.exe"
        if envolvente_c.is_file() and os.path.basename(child_argv[0]).lower() != "gb-run.exe":
            child_argv = [str(envolvente_c), "--arbol"] + child_argv
            print("[gb run]   + c: envolvente depurador sobre todo el arbol", file=sys.stderr)

    # Decide whether to capture stderr (for Go/Rust crash detection)
    capture_stderr = needs_stderr_capture(cmd_name, detected)

    # Run the command
    try:
        if capture_stderr:
            # Capture stderr for Go/Rust crash pattern detection
            proc = subprocess.Popen(
                child_argv,
                stdout=sys.stdout,
                stderr=subprocess.PIPE,
                env=env,
            )

            # Tee stderr: print it and collect it
            stderr_chunks: list[str] = []
            assert proc.stderr is not None
            try:
                for raw_line in proc.stderr:
                    line = raw_line.decode("utf-8", errors="replace")
                    sys.stderr.write(line)
                    sys.stderr.flush()
                    stderr_chunks.append(line)
            except Exception:
                pass

            proc.wait()
            exit_code = proc.returncode

            # Attempt crash detection on stderr
            if exit_code != 0:
                full_stderr = "".join(stderr_chunks)
                # TODOS los detectores, no el primero que acierte. En un repo
                # mixto el stderr que llega aqui es el del ARBOL entero: si go,
                # rust y dart revientan en la misma cadena, quedarse con el
                # primero tira dos crashes reales a la basura. Se vio en el
                # experimento poliglota (19-ago-2026): go tapaba a rust y dart.
                for crash in detect_stderr_crashes(full_stderr):
                    record = build_stderr_record(
                        crash, session_id, child_argv, proc.pid,
                    )
                    write_record(record)

        else:
            # Pass through — the language hooks handle crash capture internally
            proc = subprocess.Popen(
                child_argv,
                stdout=sys.stdout,
                stderr=sys.stderr,
                env=env,
            )
            proc.wait()
            exit_code = proc.returncode

    except FileNotFoundError:
        print(
            f"[gb run] ERROR: command not found: {cmd_name}",
            file=sys.stderr,
        )
        return 127
    except OSError as e:
        print(
            f"[gb run] ERROR: could not start process: {e}",
            file=sys.stderr,
        )
        return 126

    # Print session summary
    print_session_summary(session_id)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
