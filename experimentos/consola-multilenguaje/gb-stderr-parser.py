#!/usr/bin/env python3
"""
gb-stderr-parser.py — Universal stderr crash parser for galaxy-brain (schema v2)

Runs a child process, tees its stderr, and detects language-specific crash
patterns.  Writes a schema-v2 JSON record to ~/.galaxy-brain/crashes.jsonl
when a crash is detected.

Usage:
    python gb-stderr-parser.py -- go run main.go
    python gb-stderr-parser.py -- ./my-binary --flag value

Go is the pilot language; the parser is extensible via LANGUAGE_DETECTORS.

Zero external dependencies — only Python 3 stdlib.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# -------------------------------------------------------------------
# Config
# -------------------------------------------------------------------

CRASHES_DIR  = Path.home() / ".galaxy-brain"
CRASHES_FILE = CRASHES_DIR / "crashes.jsonl"


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------


# --- Tipo derivado del mensaje ------------------------------------------------
#
# El primer banco concluyo que el tipo "no esta en stderr" porque exc_type valia
# "panic" en los 40 registros. Era cierto de la SALIDA, no del stderr: se estaba
# poniendo la constante sin mirar. Midiendo las formas reales aparece que Go SI
# lo dice en casi todas, y Rust dice la clase aunque no tenga tipos.
#
# Lo que NO se puede derivar sigue saliendo "panic" — declarado, no inventado
# (regla 9). Un tipo a ojo es peor que ninguno: manda a buscar el fallo que no es.

_GO_RUNTIME = (
    ("invalid memory address or nil pointer dereference", "nil pointer dereference"),
    ("index out of range", "index out of range"),
    ("integer divide by zero", "integer divide by zero"),
    ("slice bounds out of range", "slice bounds out of range"),
    ("close of closed channel", "close of closed channel"),
    ("send on closed channel", "send on closed channel"),
    ("assignment to entry in nil map", "nil map write"),
    ("interface conversion", "interface conversion"),
    ("stack overflow", "stack overflow"),
)

_RUST_CLASES = (
    ("called `Option::unwrap()` on a `None` value", "Option::unwrap on None"),
    ("called `Result::unwrap()` on an `Err` value", "Result::unwrap on Err"),
    ("called `Option::expect()` on a `None` value", "Option::expect on None"),
    ("index out of bounds", "index out of bounds"),
    ("attempt to divide by zero", "divide by zero"),
    ("attempt to subtract with overflow", "subtract with overflow"),
    ("attempt to add with overflow", "add with overflow"),
    ("slice index starts at", "slice index out of range"),
    ("capacity overflow", "capacity overflow"),
)


def tipo_go(mensaje):
    """El tipo de un panic de Go, o 'panic' si no se puede derivar.

    Formas medidas (Go 1.26):
      panic: runtime error: <clase>      -> la clase, que es lo accionable
      panic: (*main.MiError) 0x...       -> el tipo del valor, tal cual
      panic: codigo 42                   -> NO derivable: el valor implementa
                                            error/Stringer y Go imprime su texto
      panic: texto suelto                -> NO derivable: el valor es un string
    """
    m = (mensaje or "").strip()
    if m.startswith("runtime error:"):
        resto = m[len("runtime error:"):].strip()
        for aguja, nombre in _GO_RUNTIME:
            if aguja in resto:
                return "runtime error: " + nombre
        return "runtime error"
    if m.startswith("(") and ")" in m:
        tipo = m[1:m.index(")")].strip()
        # Solo si parece un tipo de Go (`*paquete.Tipo`), no una frase.
        if tipo and " " not in tipo and ("." in tipo or tipo.startswith("*")):
            return tipo
    return "panic"


def tipo_rust(mensaje):
    """La clase de un panic de Rust, o 'panic'.

    Rust no tiene excepciones tipadas: lo que hay es un mensaje. Pero los panics
    de la biblioteca estandar tienen texto fijo, y esa clase es exactamente lo
    que un humano usa para saber que ha pasado.
    """
    m = (mensaje or "").strip()
    for aguja, nombre in _RUST_CLASES:
        if aguja in m:
            return nombre
    return "panic"

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


def build_record(
    language: str,
    exc_type: str,
    exc_message: str,
    origin: str,
    frames: list[dict[str, Any]],
    raw_traceback: str,
    child_argv: list[str],
    child_pid: int | None,
) -> dict[str, Any]:
    """Construct a schema-v2 crash record."""
    cwd = os.getcwd()
    return {
        "schema": 2,
        "ts": datetime.now(timezone.utc).astimezone().isoformat(),
        "language": language,
        "exception": {
            "type": exc_type,
            "message": exc_message,
            "origin": origin,
        },
        "frames": frames,
        "process": {
            "cwd": cwd,
            "project": find_project_root(cwd),
            "argv_forma": redact_argv(child_argv),
            "runtime": f"python-parser {sys.version.split()[0]}",
            "pid": child_pid,
        },
        "traceback": raw_traceback,
        "capture_method": "stderr",
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
# Language-specific crash detectors
# -------------------------------------------------------------------
# Each detector receives the full stderr text and returns either a
# parsed crash dict or None.  The dict must contain:
#   language, exc_type, exc_message, origin, frames, traceback
#
# Add new languages by appending to LANGUAGE_DETECTORS.
# -------------------------------------------------------------------

def detect_go_crash(stderr: str) -> dict[str, Any] | None:
    """
    Detect a Go panic.  Go prints to stderr:

        goroutine N [running]:
        package.func(args)
            /path/to/file.go:42 +0x1a2
        ...

    And optionally a "panic: <message>" line before the goroutine dump.
    """
    # Look for the goroutine header.
    goroutine_match = re.search(
        r"goroutine\s+(\d+)\s+\[running\]:", stderr
    )
    if not goroutine_match:
        return None

    goroutine_id = int(goroutine_match.group(1))

    # Extract panic message (appears before the goroutine dump).
    panic_match = re.search(r"^panic:\s*(.+)$", stderr, re.MULTILINE)
    panic_message = panic_match.group(1).strip() if panic_match else "unknown panic"

    # Extract the runtime error if present (e.g., "runtime error: index out of range").
    runtime_err = re.search(r"^(runtime error:.+)$", stderr, re.MULTILINE)
    if runtime_err and not panic_match:
        panic_message = runtime_err.group(1).strip()

    # Parse frames.  Go stack trace alternates:
    #   line 1: package.function(args)
    #   line 2: \t/path/to/file.go:42 +0x...
    frames: list[dict[str, Any]] = []
    # Get everything after the goroutine header until the next blank line
    # or "goroutine N" header.
    block_start = goroutine_match.end()
    block_match = re.search(
        r"\n(?:goroutine \d+|\Z|\n\n)", stderr[block_start:]
    )
    block_end = block_start + block_match.start() if block_match else len(stderr)
    block = stderr[block_start:block_end]

    # Pattern for the file+line entries.
    frame_re = re.compile(r"^\t(.+):(\d+)\s", re.MULTILINE)
    func_re  = re.compile(r"^(\S+)\(", re.MULTILINE)

    func_names = func_re.findall(block)
    file_lines = frame_re.findall(block)

    for i, (file, line) in enumerate(file_lines):
        func_name = func_names[i] if i < len(func_names) else "<unknown>"
        frames.append({
            "file": file,
            "line": int(line),
            "column": 0,
            "function": func_name,
        })

    # Build the traceback: from "goroutine" to end-of-block (or panic line
    # onward if present).
    tb_start = panic_match.start() if panic_match else goroutine_match.start()
    traceback_text = stderr[tb_start:block_end].strip()

    return {
        "language": "go",
        "exc_type": tipo_go(panic_message),
        "exc_message": panic_message,
        "origin": f"goroutine-{goroutine_id}",
        "frames": frames,
        "traceback": traceback_text,
    }


def detect_python_crash(stderr: str) -> dict[str, Any] | None:
    """
    Detect a Python traceback in stderr.

        Traceback (most recent call last):
          File "foo.py", line 10, in <module>
            ...
        SomeError: message
    """
    tb_match = re.search(r"Traceback \(most recent call last\):", stderr)
    if not tb_match:
        return None

    traceback_text = stderr[tb_match.start():].strip()

    # Parse frames.
    frame_re = re.compile(
        r'^\s*File "(.+?)", line (\d+), in (.+)$', re.MULTILINE
    )
    frames = [
        {"file": m.group(1), "line": int(m.group(2)), "column": 0, "function": m.group(3)}
        for m in frame_re.finditer(traceback_text)
    ]

    # The last line(s) of a Python traceback contain the exception.
    lines = traceback_text.rstrip().split("\n")
    exc_line = lines[-1] if lines else "Unknown"
    colon_idx = exc_line.find(":")
    if colon_idx != -1:
        exc_type = exc_line[:colon_idx].strip()
        exc_message = exc_line[colon_idx + 1:].strip()
    else:
        exc_type = exc_line.strip()
        exc_message = ""

    return {
        "language": "python",
        "exc_type": exc_type,
        "exc_message": exc_message,
        "origin": "main",
        "frames": frames,
        "traceback": traceback_text,
    }


def detect_rust_crash(stderr: str) -> dict[str, Any] | None:
    """
    Detect a Rust panic.

        thread 'main' panicked at 'message', src/main.rs:10:5
        note: run with `RUST_BACKTRACE=1` ...
    """
    panic_match = re.search(
        r"thread '(.+?)'\s*(?:\(\d+\)\s*)?panicked at '(.+?)',\s*(.+?):(\d+):(\d+)",
        stderr,
    )
    if not panic_match:
        # Rust 1.73+ format: thread 'main' panicked at src/main.rs:10:5:\nmessage
        # (may include thread ID in parens, e.g. thread 'main' (13484) panicked at ...)
        panic_match2 = re.search(
            r"thread '(.+?)'\s*(?:\(\d+\)\s*)?panicked at (.+?):(\d+):(\d+):\n(.+)",
            stderr,
        )
        if not panic_match2:
            return None
        thread = panic_match2.group(1)
        file = panic_match2.group(2)
        line = int(panic_match2.group(3))
        col  = int(panic_match2.group(4))
        message = panic_match2.group(5).strip()
    else:
        thread  = panic_match.group(1)
        message = panic_match.group(2)
        file    = panic_match.group(3)
        line    = int(panic_match.group(4))
        col     = int(panic_match.group(5))

    # Parse RUST_BACKTRACE frames if present.
    frames = [{"file": file, "line": line, "column": col, "function": "<panic>"}]
    bt_re = re.compile(
        r"^\s*\d+:\s+(?:0x[0-9a-f]+ - )?(.+?)$", re.MULTILINE
    )
    for m in bt_re.finditer(stderr):
        fn_text = m.group(1).strip()
        if fn_text and "note:" not in fn_text:
            frames.append({
                "file": "",
                "line": 0,
                "column": 0,
                "function": fn_text,
            })

    return {
        "language": "rust",
        "exc_type": tipo_rust(message),
        "exc_message": message,
        "origin": f"thread-{thread}",
        "frames": frames,
        "traceback": stderr.strip(),
    }


def detect_java_crash(stderr: str) -> dict[str, Any] | None:
    """
    Detect a Java/JVM exception.

        Exception in thread "main" java.lang.NullPointerException: message
            at com.example.Main.method(Main.java:42)
    """
    exc_match = re.search(
        r'^(?:Exception in thread ".+?" )?(\S+(?:Exception|Error|Throwable)\S*):\s*(.*)$',
        stderr, re.MULTILINE,
    )
    if not exc_match:
        return None

    exc_type = exc_match.group(1)
    exc_message = exc_match.group(2).strip()

    frame_re = re.compile(r"^\s+at\s+(\S+)\((.+?):(\d+)\)$", re.MULTILINE)
    frames = [
        {"file": m.group(2), "line": int(m.group(3)), "column": 0, "function": m.group(1)}
        for m in frame_re.finditer(stderr)
    ]

    tb_text = stderr[exc_match.start():].strip()

    return {
        "language": "java",
        "exc_type": exc_type,
        "exc_message": exc_message,
        "origin": "main",
        "frames": frames,
        "traceback": tb_text,
    }


# Ordered list of detectors.  First match wins.
LANGUAGE_DETECTORS = [
    detect_go_crash,
    detect_python_crash,
    detect_rust_crash,
    detect_java_crash,
]


def detect_crash(stderr: str) -> dict[str, Any] | None:
    """Run all detectors; return the first match or None."""
    for detector in LANGUAGE_DETECTORS:
        try:
            result = detector(stderr)
            if result is not None:
                return result
        except Exception:
            continue
    return None


# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------

def build_env_for_command(argv: list[str]) -> dict[str, str]:
    """
    Return an augmented copy of os.environ with language-specific
    tracing env vars set.
    """
    env = os.environ.copy()

    # Detect Go command and set GOTRACEBACK.
    cmd_base = os.path.basename(argv[0]).lower() if argv else ""
    if cmd_base in ("go", "go.exe"):
        env.setdefault("GOTRACEBACK", "all")

    # Detect Rust and set RUST_BACKTRACE.
    # Heuristic: if the binary is in a cargo target dir, or the user
    # explicitly runs "cargo run", etc.
    if cmd_base in ("cargo", "cargo.exe"):
        env.setdefault("RUST_BACKTRACE", "1")

    return env


def main() -> int:
    # Parse our own arguments: everything after "--" is the child command.
    try:
        sep_idx = sys.argv.index("--")
    except ValueError:
        print(
            "Usage: python gb-stderr-parser.py -- <command> [args...]",
            file=sys.stderr,
        )
        return 2

    child_argv = sys.argv[sep_idx + 1 :]
    if not child_argv:
        print("Error: no command specified after '--'.", file=sys.stderr)
        return 2

    env = build_env_for_command(child_argv)

    # Run the child, capturing stderr while still printing it.
    try:
        proc = subprocess.Popen(
            child_argv,
            stdout=sys.stdout,       # stdout passes through untouched
            stderr=subprocess.PIPE,
            env=env,
        )
    except FileNotFoundError:
        print(f"Error: command not found: {child_argv[0]}", file=sys.stderr)
        return 127
    except OSError as e:
        print(f"Error starting process: {e}", file=sys.stderr)
        return 126

    # Read stderr incrementally, tee to our own stderr.
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

    # Only attempt crash detection if the process exited abnormally.
    if exit_code != 0:
        full_stderr = "".join(stderr_chunks)
        crash = detect_crash(full_stderr)

        if crash is not None:
            # Language-specific crash detected.
            record = build_record(
                language=crash["language"],
                exc_type=crash["exc_type"],
                exc_message=crash["exc_message"],
                origin=crash["origin"],
                frames=crash["frames"],
                raw_traceback=crash["traceback"],
                child_argv=child_argv,
                child_pid=proc.pid,
            )
            write_record(record)
        elif full_stderr.strip():
            # Generic fallback: no pattern matched but the process crashed.
            # Capture raw stderr and exit code as a minimal record.
            record = build_record(
                language="unknown",
                exc_type="ProcessCrash",
                exc_message=f"Process exited with code {exit_code}",
                origin="main",
                frames=[],
                raw_traceback=full_stderr.strip()[-4096:],  # cap at 4 KiB
                child_argv=child_argv,
                child_pid=proc.pid,
            )
            write_record(record)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
