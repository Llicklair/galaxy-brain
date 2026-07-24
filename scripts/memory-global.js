#!/usr/bin/env node
// galaxy-brain — cross-repo permanent memory (research H5 file-based, H6 finite-context).
// The per-project Claude memory is a silo: a fact learned in one repo never reaches another. This
// is the shared vault — durable, human-editable markdown notes with [[wikilinks]] (open the folder
// in Obsidian for the graph), that surface in ANY project's session via a SessionStart hook.
//
// The hard part is NOT storage (markdown suffices) — it is recall WITHOUT context bloat. So the
// SessionStart payload is deliberately lean: the compact one-line index of every note, plus the
// FULL text of only `always`-scope notes and notes tagged for the current project. Everything else
// is pulled on demand with `recall <query>`. Never dump the whole vault.
//
// Vault: ~/.claude/memory-global/  (override with GALAXY_BRAIN_MEMORY_DIR for testing)
//   <name>.md         one note, frontmatter (name/description/type/scope/tags) + body with [[links]]
//   MEMORY.md         regenerated index, one line per note
//
// Usage:
//   memory-global.js add --name <slug> --description <d> [--type <t>] [--scope <s>] [--tags a,b] [--body <text>]
//                        (body may also be piped on stdin)
//   memory-global.js index                       # print the compact index
//   memory-global.js recall <query words...>     # full text of the most relevant notes
//   memory-global.js context [--project <name>]  # SessionStart payload: index + always/project notes
// scope: always (core identity/prefs, injected every session) | project:<name> | general (recall only)
// Exit 0 always for read commands (a memory tool must never break a session); 2 on usage error for `add`.

const fs = require("fs");
const os = require("os");
const path = require("path");

const DIR = process.env.GALAXY_BRAIN_MEMORY_DIR || path.join(os.homedir(), ".claude", "memory-global");
const INDEX = path.join(DIR, "MEMORY.md");
const TOP_K = 6;

function usage(m) {
  process.stderr.write(m + "\n");
  process.exit(2);
}
function arg(name, fb) {
  const i = process.argv.indexOf(name);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : fb;
}

function parseNote(file) {
  const raw = fs.readFileSync(file, "utf8");
  const m = raw.match(/^---\n([\s\S]*?)\n---\n?([\s\S]*)$/);
  const meta = {};
  let body = raw;
  if (m) {
    body = m[2].trim();
    for (const line of m[1].split(/\r?\n/)) {
      const kv = line.match(/^([a-z]+):\s*(.*)$/i);
      if (kv) meta[kv[1].toLowerCase()] = kv[2].trim();
    }
  }
  return {
    name: meta.name || path.basename(file, ".md"),
    description: meta.description || "",
    type: meta.type || "reference",
    scope: meta.scope || "general",
    tags: (meta.tags || "").replace(/[[\]]/g, "").split(",").map((s) => s.trim()).filter(Boolean),
    body,
    file: path.basename(file),
  };
}

function allNotes() {
  if (!fs.existsSync(DIR)) return [];
  return fs
    .readdirSync(DIR)
    .filter((f) => f.endsWith(".md") && f !== "MEMORY.md")
    .map((f) => parseNote(path.join(DIR, f)))
    .sort((a, b) => a.name.localeCompare(b.name));
}

function writeIndex(notes) {
  const lines = ["# Global memory index (cross-repo, galaxy-brain)", ""];
  for (const n of notes) lines.push(`- [${n.name}](${n.file}) [${n.scope}] — ${n.description}`);
  fs.writeFileSync(INDEX, lines.join("\n") + "\n");
}

function readStdin() {
  try {
    return fs.readFileSync(0, "utf8").trim();
  } catch {
    return "";
  }
}

function score(note, terms) {
  const hay = (note.name + " " + note.description + " " + note.tags.join(" ")).toLowerCase();
  return terms.reduce((s, t) => s + (hay.includes(t) ? 1 : 0), 0);
}

const cmd = process.argv[2];

if (cmd === "add") {
  const name = arg("--name");
  const description = arg("--description");
  if (!name || !description) usage("add needs --name and --description");
  const type = arg("--type", "reference");
  const scope = arg("--scope", "general");
  const tags = arg("--tags", "");
  const body = arg("--body") || readStdin() || "(no body)";
  fs.mkdirSync(DIR, { recursive: true });
  const fm = [
    "---",
    "name: " + name,
    "description: " + description,
    "type: " + type,
    "scope: " + scope,
    "tags: [" + tags + "]",
    "---",
    "",
    body,
    "",
  ].join("\n");
  fs.writeFileSync(path.join(DIR, name + ".md"), fm);
  writeIndex(allNotes());
  console.log("saved: " + name + " [" + scope + "] → " + path.join(DIR, name + ".md"));
} else if (cmd === "index") {
  const notes = allNotes();
  if (!notes.length) {
    console.log("(global memory is empty — add notes with memory-global.js add)");
  } else {
    for (const n of notes) console.log(`- ${n.name} [${n.scope}] — ${n.description}`);
  }
} else if (cmd === "recall") {
  const terms = process.argv.slice(3).join(" ").toLowerCase().split(/\s+/).filter(Boolean);
  if (!terms.length) usage("recall needs query words");
  const ranked = allNotes()
    .map((n) => ({ n, s: score(n, terms) }))
    .filter((x) => x.s > 0)
    .sort((a, b) => b.s - a.s)
    .slice(0, TOP_K);
  if (!ranked.length) {
    console.log("(no global memory matched: " + terms.join(" ") + ")");
  } else {
    for (const { n } of ranked) {
      console.log("### " + n.name + "  [" + n.type + "/" + n.scope + "]");
      if (n.tags.length) console.log("tags: " + n.tags.join(", "));
      console.log(n.body + "\n");
    }
  }
} else if (cmd === "context") {
  // The SessionStart payload — lean by design (H6). Compact index for everything; full text only for
  // `always` notes and notes tagged/scoped to the current project.
  // The SessionStart hook passes no --project; derive it from the project dir the harness exposes.
  const project =
    arg("--project") ||
    path.basename(process.env.CLAUDE_PROJECT_DIR || process.cwd() || "").replace(/^c--/, "");
  const notes = allNotes();
  if (!notes.length) process.exit(0); // nothing to inject; stay silent
  const full = notes.filter(
    (n) => n.scope === "always" || n.scope === "project:" + project || (project && n.tags.includes(project))
  );
  const out = ["# galaxy-brain global memory (cross-repo) — recall more with `memory-global.js recall <query>`", ""];
  out.push("Index (" + notes.length + " note(s)):");
  for (const n of notes) out.push(`- ${n.name} [${n.scope}] — ${n.description}`);
  if (full.length) {
    out.push("", "Loaded in full (always + this project):");
    for (const n of full) {
      out.push("", "### " + n.name + "  [" + n.type + "/" + n.scope + "]");
      out.push(n.body);
    }
  }
  console.log(out.join("\n"));
} else {
  usage("unknown command: " + (cmd || "(none)") + " — expected add|index|recall|context");
}
