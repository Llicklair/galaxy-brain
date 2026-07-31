"""galaxy-brain — memoria permanente cross-repo (H5 file-based, H6 finite-context).

La memoria per-proyecto de Claude es un silo: un hecho aprendido en un repo nunca llega a
otro. Esto es el vault compartido — notas markdown durables y editables a mano con
[[wikilinks]] (abre la carpeta en Obsidian para el grafo) que afloran en CUALQUIER
proyecto vía el hook SessionStart.

Lo difícil NO es guardar (markdown basta) — es recordar SIN inflar el contexto. Por eso el
payload de SessionStart es deliberadamente magro: el índice compacto de una línea por nota,
más el texto COMPLETO solo de las notas `always` y las del proyecto actual. El resto se trae
a demanda con `recall <query>`. Nunca se vuelca el vault entero.

Reimplementado en Python desde la versión Node original, al unificar en una sola superficie:
mismo vault, mismo formato, misma salida — las notas existentes siguen valiendo sin tocarlas.

Vault: ~/.claude/memory-global/  (override con GALAXY_BRAIN_MEMORY_DIR para tests)
  <name>.md    una nota: frontmatter (name/description/type/scope/tags) + cuerpo con [[links]]
  MEMORY.md    índice regenerado, una línea por nota
scope: always (identidad/prefs, se inyecta siempre) | project:<name> | general (solo recall)
"""

from __future__ import annotations

import os
import re
from pathlib import Path

TOP_K = 6
_FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.DOTALL)
_KV = re.compile(r"^([a-z]+):\s*(.*)$", re.IGNORECASE)


def vault_dir() -> Path:
    """Dónde vive el vault. GALAXY_BRAIN_MEMORY_DIR lo mueve (tests); por defecto ~/.claude/memory-global."""
    override = os.environ.get("GALAXY_BRAIN_MEMORY_DIR")
    if override:
        return Path(override)
    return Path.home() / ".claude" / "memory-global"


class Note:
    __slots__ = ("name", "description", "type", "scope", "tags", "body", "file")

    def __init__(self, name, description, type, scope, tags, body, file):
        self.name = name
        self.description = description
        self.type = type
        self.scope = scope
        self.tags = tags
        self.body = body
        self.file = file


def parse_note(path: Path) -> Note:
    raw = path.read_text(encoding="utf-8", errors="replace")
    meta: dict[str, str] = {}
    body = raw
    m = _FRONTMATTER.match(raw)
    if m:
        body = m.group(2).strip()
        for line in m.group(1).splitlines():
            kv = _KV.match(line)
            if kv:
                meta[kv.group(1).lower()] = kv.group(2).strip()
    tags = [t.strip() for t in re.sub(r"[\[\]]", "", meta.get("tags", "")).split(",") if t.strip()]
    return Note(
        name=meta.get("name") or path.stem,
        description=meta.get("description", ""),
        type=meta.get("type", "reference"),
        scope=meta.get("scope", "general"),
        tags=tags,
        body=body,
        file=path.name,
    )


def all_notes() -> list[Note]:
    d = vault_dir()
    if not d.is_dir():
        return []
    notes = [parse_note(p) for p in d.iterdir() if p.suffix == ".md" and p.name != "MEMORY.md"]
    notes.sort(key=lambda n: n.name)
    return notes


def write_index(notes: list[Note]) -> None:
    lines = ["# Global memory index (cross-repo, galaxy-brain)", ""]
    for n in notes:
        lines.append(f"- [{n.name}]({n.file}) [{n.scope}] — {n.description}")
    (vault_dir() / "MEMORY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _score(note: Note, terms: list[str]) -> int:
    # El índice (nombre/descripción/tags) pesa doble: una descripción que casa
    # exacta debe ganar a un cuerpo largo que solo roza la query.
    meta = (note.name + " " + note.description + " " + " ".join(note.tags)).lower()
    body = note.body.lower()
    return sum(2 if t in meta else 1 if t in body else 0 for t in terms)


def add(name, description, type="reference", scope="general", tags="", body="") -> Path:
    d = vault_dir()
    d.mkdir(parents=True, exist_ok=True)
    fm = "\n".join(
        [
            "---",
            "name: " + name,
            "description: " + description,
            "type: " + type,
            "scope: " + scope,
            "tags: [" + tags + "]",
            "---",
            "",
            body or "(no body)",
            "",
        ]
    )
    path = d / (name + ".md")
    path.write_text(fm, encoding="utf-8")
    write_index(all_notes())
    return path


def index_lines() -> list[str]:
    notes = all_notes()
    if not notes:
        return ["(global memory is empty — add notes with `gb memory add`)"]
    return [f"- {n.name} [{n.scope}] — {n.description}" for n in notes]


def recall(query: str) -> list[str]:
    terms = [t for t in query.lower().split() if t]
    if not terms:
        return []
    ranked = sorted(
        ((n, _score(n, terms)) for n in all_notes()),
        key=lambda x: x[1],
        reverse=True,
    )
    ranked = [n for n, s in ranked if s > 0][:TOP_K]
    if not ranked:
        return ["(no global memory matched: " + " ".join(terms) + ")"]
    out: list[str] = []
    for n in ranked:
        out.append(f"### {n.name}  [{n.type}/{n.scope}]")
        if n.tags:
            out.append("tags: " + ", ".join(n.tags))
        out.append(n.body + "\n")
    return out


def _current_project(explicit: str | None = None) -> str:
    if explicit:
        return explicit
    base = os.path.basename(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd() or "")
    return re.sub(r"^c--", "", base)


def context(project: str | None = None) -> str | None:
    """El payload de SessionStart — magro por diseño (H6). Índice compacto de todo; texto
    completo solo de las notas `always` y las del proyecto actual. None si el vault está vacío."""
    notes = all_notes()
    if not notes:
        return None
    proj = _current_project(project)
    full = [
        n
        for n in notes
        if n.scope == "always" or n.scope == "project:" + proj or (proj and proj in n.tags)
    ]
    out = [
        "# galaxy-brain global memory (cross-repo) — recall more with `gb memory recall <query>`",
        "",
        "Index (" + str(len(notes)) + " note(s)):",
    ]
    for n in notes:
        out.append(f"- {n.name} [{n.scope}] — {n.description}")
    if full:
        out.append("")
        out.append("Loaded in full (always + this project):")
        for n in full:
            out.append("")
            out.append(f"### {n.name}  [{n.type}/{n.scope}]")
            out.append(n.body)
    return "\n".join(out)
