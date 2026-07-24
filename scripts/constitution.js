#!/usr/bin/env node
// galaxy-brain — constitution compiler (ARCHITECTURE rules 2 & 9; sibling of ears.js).
// Moves architecture law UP the enforcement ladder: prompt → evaluator → MECHANICAL.
//   extract  — parse RFC-style principles (MUST / MUST NOT / SHALL / NEVER / NUNCA / PROHIBIDO,
//              capitals by convention) out of a constitution, assign stable LAW-### IDs,
//              hint a classification, emit a manifest.
//   scaffold — one JSON rule stub per law. The orchestrator (LLM) fills each stub with its
//              mechanical twin — an inline ast-grep rule or an arbitrary check command
//              (import-linter, dependency-cruiser, ArchUnit…) — and flips enforced:true.
//              Laws that cannot compile stay judged-only, HONESTLY labeled.
//   check    — run every enforced rule against the repo; any violation exits 1. Reports
//              coverage: how many laws are iron (mechanical) vs paper (judged-only/pending).
// What this deliberately does NOT do: invent the rules. Compiling a principle into a pattern
// needs judgment (the LLM); running the compiled law forever does not (this script).
//
// Usage:
//   constitution.js extract  <constitution.md> [--out <dir>]     (default out: ./law)
//   constitution.js scaffold <lawDir>
//   constitution.js check    <lawDir> --repo <dir>
// Exit codes: 0 ok · 1 violations or invalid stage · 2 usage error.

const { spawnSync } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");

function usage(m) {
  process.stderr.write(m + "\n");
  process.exit(2);
}
function fail(m) {
  process.stderr.write("constitution: " + m + "\n");
  process.exit(1);
}

const PRINCIPLE = /\b(MUST NOT|MUST|SHALL NOT|SHALL|NEVER|NUNCA|PROHIBIDO|JAMÁS)\b/;

function hint(text) {
  if (/import|layer|capa|depend|módulo|module boundar/i.test(text)) return "import-contract";
  if (/`[^`]+`|\b(print|console\.log|float|timeout|sql|password|secret|except|eval|exec)\b/i.test(text))
    return "ast-grep";
  if (/maintain|legib|clean|simple|coherent|claro|sencill|elegan/i.test(text)) return "judged-only";
  return "review";
}

function stripBullet(l) {
  return l.replace(/^\s*(?:[-*]|\d+[.)])?\s*/, "").trim();
}

function extract(specPath, outDir) {
  const lines = fs.readFileSync(specPath, "utf8").split(/\r?\n/);
  const laws = [];
  lines.forEach((raw, i) => {
    const line = stripBullet(raw);
    if (!PRINCIPLE.test(line) || line.startsWith("#")) return;
    laws.push({
      id: "LAW-" + String(laws.length + 1).padStart(3, "0"),
      text: line,
      line: i + 1,
      hint: hint(line),
    });
  });
  if (!laws.length)
    fail("0 principles found — constitution convention: normative words in CAPITALS (MUST / MUST NOT / NEVER / NUNCA / PROHIBIDO).");
  fs.mkdirSync(outDir, { recursive: true });
  const manifest = { source: path.resolve(specPath), extractedAt: new Date().toISOString(), laws };
  fs.writeFileSync(path.join(outDir, "manifest.json"), JSON.stringify(manifest, null, 2));
  console.log(laws.length + " principle(s) → " + path.join(outDir, "manifest.json"));
  for (const l of laws) console.log("  " + l.id + " [" + l.hint + "] " + l.text.slice(0, 80));
  return manifest;
}

const STUB_NOTE =
  "FILL ME: set type to 'ast-grep' (put the inline rule YAML in astgrep_yaml) or 'command' " +
  "(any deterministic check, exit 0 = compliant) and flip enforced:true — or set type " +
  "'judged-only' if this principle cannot compile to a mechanical check.";

function scaffold(lawDir) {
  const manifest = JSON.parse(fs.readFileSync(path.join(lawDir, "manifest.json"), "utf8"));
  const rulesDir = path.join(lawDir, "rules");
  fs.mkdirSync(rulesDir, { recursive: true });
  let created = 0;
  for (const l of manifest.laws) {
    const f = path.join(rulesDir, l.id.toLowerCase() + ".json");
    if (fs.existsSync(f)) continue; // never clobber a filled rule
    fs.writeFileSync(
      f,
      JSON.stringify(
        { id: l.id, principle: l.text, hint: l.hint, enforced: false, type: "pending", note: STUB_NOTE, astgrep_yaml: "", command: "" },
        null,
        2
      )
    );
    created++;
  }
  console.log("scaffolded " + created + " stub(s) in " + rulesDir + " (existing files untouched)");
}

function runAstGrep(yaml, repo) {
  // Rule goes through a temp FILE, and the call through a shell: npm ships ast-grep as a
  // .cmd shim on Windows (unspawnable without shell), and multiline YAML can't survive
  // cmd.exe argument quoting anyway.
  const tmp = path.join(os.tmpdir(), "gb-law-" + process.pid + "-" + Math.random().toString(36).slice(2) + ".yml");
  fs.writeFileSync(tmp, yaml);
  let r;
  try {
    r = spawnSync('ast-grep scan --rule "' + tmp + '" --json "' + path.resolve(repo) + '"', {
      shell: true,
      encoding: "utf8",
      maxBuffer: 64 * 1024 * 1024,
    });
  } finally {
    try { fs.unlinkSync(tmp); } catch {}
  }
  if (r.error || (r.status !== 0 && !r.stdout.trim()))
    return { error: "ast-grep failed: " + ((r.error && r.error.message) || r.stderr.split(/\r?\n/)[0] || ("exit " + r.status)) };
  let matches;
  try {
    matches = JSON.parse(r.stdout || "[]");
  } catch {
    return { error: "unparseable ast-grep output" };
  }
  return {
    violations: matches.map((m) => (m.file || "?") + ":" + ((m.range && m.range.start && m.range.start.line + 1) || "?")),
  };
}

function check(lawDir, repo) {
  const manifest = JSON.parse(fs.readFileSync(path.join(lawDir, "manifest.json"), "utf8"));
  const rulesDir = path.join(lawDir, "rules");
  const rows = [];
  let violations = 0;
  for (const l of manifest.laws) {
    const f = path.join(rulesDir, l.id.toLowerCase() + ".json");
    if (!fs.existsSync(f)) {
      rows.push([l.id, "NO-STUB", "run scaffold"]);
      continue;
    }
    const rule = JSON.parse(fs.readFileSync(f, "utf8"));
    if (rule.type === "judged-only") {
      rows.push([l.id, "JUDGED-ONLY", "paper law — the evaluator holds it"]);
      continue;
    }
    if (!rule.enforced || rule.type === "pending") {
      rows.push([l.id, "PENDING", "stub not filled yet"]);
      continue;
    }
    if (rule.type === "ast-grep") {
      const res = runAstGrep(rule.astgrep_yaml, repo);
      if (res.error) rows.push([l.id, "ERROR", res.error]);
      else if (res.violations.length) {
        violations += res.violations.length;
        rows.push([l.id, "VIOLATED", res.violations.slice(0, 5).join(" · ") + (res.violations.length > 5 ? " (+" + (res.violations.length - 5) + ")" : "")]);
      } else rows.push([l.id, "OK", "mechanical, clean"]);
    } else if (rule.type === "command") {
      const r = spawnSync(rule.command, { shell: true, cwd: repo, encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
      if (r.status === 0) rows.push([l.id, "OK", "mechanical (command), clean"]);
      else {
        violations++;
        rows.push([l.id, "VIOLATED", "command exit " + r.status + ": " + ((r.stdout + r.stderr).split(/\r?\n/).find(Boolean) || "").slice(0, 100)]);
      }
    } else rows.push([l.id, "ERROR", "unknown type: " + rule.type]);
  }
  for (const [id, st, detail] of rows) console.log(id.padEnd(9) + st.padEnd(13) + detail);
  const iron = rows.filter(([, s]) => s === "OK" || s === "VIOLATED").length;
  const paper = rows.filter(([, s]) => s === "JUDGED-ONLY").length;
  const pending = rows.filter(([, s]) => s === "PENDING" || s === "NO-STUB").length;
  const errs = rows.filter(([, s]) => s === "ERROR").length;
  console.log(
    "coverage: " + manifest.laws.length + " law(s) — " + iron + " iron (mechanical), " + paper + " paper (judged-only), " + pending + " pending" + (errs ? ", " + errs + " ERROR" : "")
  );
  if (errs) fail(errs + " rule(s) failed to execute — an unrunnable law is not a law.");
  if (violations) fail(violations + " violation(s) — the batch does not close over a broken law.");
}

const [cmd, target, ...rest] = process.argv.slice(2);
const opts = {};
for (let i = 0; i < rest.length; i++) {
  if (rest[i] === "--out") opts.out = rest[++i];
  else if (rest[i] === "--repo") opts.repo = rest[++i];
  else usage("unknown argument: " + rest[i]);
}

switch (cmd) {
  case "extract":
    if (!target) usage("extract needs a constitution file");
    extract(target, opts.out || "law");
    break;
  case "scaffold":
    if (!target) usage("scaffold needs the law dir");
    scaffold(target);
    break;
  case "check":
    if (!target) usage("check needs the law dir");
    if (!opts.repo) usage("check needs --repo <dir>");
    check(target, opts.repo);
    break;
  default:
    usage("unknown command: " + (cmd || "(none)") + " — expected extract|scaffold|check");
}
