"""
store_universal.py — Language-agnostic crash record store for galaxy-brain.

Reads/writes universal crash records (schema v2) to ~/.galaxy-brain/.
No external dependencies beyond Python stdlib.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GALAXY_DIR = Path.home() / ".galaxy-brain"
SCHEMA_VERSION = 2

VALID_LANGUAGES = frozenset(
    ["python", "js", "ts", "go", "rust", "java", "kotlin", "swift",
     "ruby", "php", "lua", "scala", "elixir", "csharp", "c", "dart"]
)

VALID_ORIGINS = frozenset(
    ["main", "thread", "unraisable", "promise", "goroutine",
     "coroutine", "task", "signal", "process"]
)

VALID_CAPTURE_METHODS = frozenset(["hook", "stderr", "wrapper"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sanitize_project_name(project: str) -> str:
    """Turn a project path/name into a safe filename component."""
    name = os.path.basename(project.rstrip("/\\"))
    return re.sub(r"[^\w\-.]", "_", name) or "unknown"


def _jsonl_path(project: Optional[str]) -> Path:
    """Return the JSONL file path for a given project."""
    if project:
        slug = _sanitize_project_name(project)
    else:
        slug = "_global"
    return GALAXY_DIR / f"{slug}.crashes.jsonl"


def detect_project(cwd: str) -> Optional[str]:
    """Walk up from *cwd* looking for a .git directory. Return the project
    root or None."""
    current = Path(cwd).resolve()
    for parent in [current, *current.parents]:
        if (parent / ".git").exists():
            return str(parent)
    return None


# ---------------------------------------------------------------------------
# Validation (lightweight, no jsonschema dependency)
# ---------------------------------------------------------------------------

class ValidationError(Exception):
    """Raised when a crash record fails basic schema checks."""


def _check_type(value, expected, path: str):
    """Assert *value* matches *expected* (a Python type or a list of types
    including None)."""
    if isinstance(expected, list):
        # nullable union, e.g. [str, None]
        allowed = tuple(t for t in expected if t is not None)
        if value is None:
            return
        if not isinstance(value, allowed):
            raise ValidationError(f"{path}: expected {expected}, got {type(value).__name__}")
    else:
        if not isinstance(value, expected):
            raise ValidationError(f"{path}: expected {expected.__name__}, got {type(value).__name__}")


def _validate_exception(exc: dict, path: str = "exception"):
    """Validate the exception sub-object."""
    for key in ("type", "message"):
        if key not in exc:
            raise ValidationError(f"{path}: missing required field '{key}'")
    _check_type(exc["type"], str, f"{path}.type")
    _check_type(exc["message"], str, f"{path}.message")

    if "module" in exc:
        _check_type(exc["module"], [str, None], f"{path}.module")
    if "origin" in exc and exc["origin"] is not None:
        if exc["origin"] not in VALID_ORIGINS:
            raise ValidationError(f"{path}.origin: invalid value '{exc['origin']}'")
    if "chain" in exc and exc["chain"] is not None:
        if not isinstance(exc["chain"], list):
            raise ValidationError(f"{path}.chain: expected list")
        for i, chained in enumerate(exc["chain"]):
            _validate_exception(chained, f"{path}.chain[{i}]")


def _validate_frame(frame: dict, path: str):
    """Validate a single stack frame."""
    for key in ("file", "line", "function"):
        if key not in frame:
            raise ValidationError(f"{path}: missing required field '{key}'")
    _check_type(frame["file"], str, f"{path}.file")
    _check_type(frame["line"], int, f"{path}.line")
    _check_type(frame["function"], str, f"{path}.function")
    if "column" in frame:
        _check_type(frame["column"], [int, None], f"{path}.column")
    if "source" in frame:
        _check_type(frame["source"], [str, None], f"{path}.source")
    if "locals" in frame:
        if frame["locals"] is not None and not isinstance(frame["locals"], dict):
            raise ValidationError(f"{path}.locals: expected object or null")


def _validate_process(proc: dict, path: str = "process"):
    """Validate the process sub-object."""
    for key in ("cwd", "project"):
        if key not in proc:
            raise ValidationError(f"{path}: missing required field '{key}'")
    _check_type(proc["cwd"], str, f"{path}.cwd")
    _check_type(proc["project"], [str, None], f"{path}.project")
    if "argv_forma" in proc:
        _check_type(proc["argv_forma"], [str, None], f"{path}.argv_forma")
    if "runtime" in proc:
        _check_type(proc["runtime"], [str, None], f"{path}.runtime")
    if "pid" in proc:
        _check_type(proc["pid"], [int, None], f"{path}.pid")


def validate(record: dict) -> None:
    """Validate a crash record against schema v2 (basic checks).

    Raises ValidationError on failure.
    """
    required_top = ("schema", "ts", "language", "exception", "frames", "process")
    for key in required_top:
        if key not in record:
            raise ValidationError(f"missing required top-level field '{key}'")

    if record["schema"] != SCHEMA_VERSION:
        raise ValidationError(f"schema: expected {SCHEMA_VERSION}, got {record['schema']}")

    _check_type(record["ts"], str, "ts")
    _check_type(record["language"], str, "language")
    if record["language"] not in VALID_LANGUAGES:
        raise ValidationError(f"language: invalid value '{record['language']}'")

    if not isinstance(record["exception"], dict):
        raise ValidationError("exception: expected object")
    _validate_exception(record["exception"])

    if not isinstance(record["frames"], list):
        raise ValidationError("frames: expected array")
    for i, frame in enumerate(record["frames"]):
        if not isinstance(frame, dict):
            raise ValidationError(f"frames[{i}]: expected object")
        _validate_frame(frame, f"frames[{i}]")

    if not isinstance(record["process"], dict):
        raise ValidationError("process: expected object")
    _validate_process(record["process"])

    if "traceback" in record:
        _check_type(record["traceback"], [str, None], "traceback")

    if "capture_method" in record:
        if record["capture_method"] not in VALID_CAPTURE_METHODS:
            raise ValidationError(
                f"capture_method: invalid value '{record['capture_method']}'"
            )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def append_record(record: dict) -> Path:
    """Validate *record* against schema v2 and append it to the project's
    JSONL file under ``~/.galaxy-brain/``.

    Returns the path to the JSONL file written.
    Raises ``ValidationError`` if validation fails.
    """
    validate(record)

    project = record.get("process", {}).get("project")
    path = _jsonl_path(project)

    GALAXY_DIR.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
        fh.write("\n")

    return path


def _iter_records(project: Optional[str] = None) -> list[dict]:
    """Load all records from the relevant JSONL file(s).

    If *project* is given, only that file is read. Otherwise all
    ``*.crashes.jsonl`` files are read.
    """
    records: list[dict] = []

    if project:
        paths = [_jsonl_path(project)]
    else:
        if not GALAXY_DIR.exists():
            return records
        paths = sorted(GALAXY_DIR.glob("*.crashes.jsonl"))

    for path in paths:
        if not path.exists():
            continue
        with open(path, "r", encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    # Skip malformed lines silently.
                    pass

    return records


def list_records(
    project: Optional[str] = None,
    lang: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """Return the most recent crash records, newest first.

    Parameters
    ----------
    project : str, optional
        Filter to a specific project root path.
    lang : str, optional
        Filter to a specific language (e.g. ``"js"``, ``"go"``).
    limit : int
        Maximum number of records to return (default 20).
    """
    records = _iter_records(project)

    if lang:
        records = [r for r in records if r.get("language") == lang]

    # Sort by timestamp descending (lexicographic on ISO-8601 works).
    records.sort(key=lambda r: r.get("ts", ""), reverse=True)

    return records[:limit]


def last(
    project: Optional[str] = None,
    lang: Optional[str] = None,
) -> Optional[dict]:
    """Return the single most recent crash record, or ``None``.

    Parameters
    ----------
    project : str, optional
        Filter to a specific project root path.
    lang : str, optional
        Filter to a specific language.
    """
    results = list_records(project=project, lang=lang, limit=1)
    return results[0] if results else None
