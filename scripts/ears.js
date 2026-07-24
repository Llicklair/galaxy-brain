#!/usr/bin/env node
// galaxy-brain — EARS→acceptance-test compiler (ARCHITECTURE rules 2 & 3).
// The deterministic half of "every spec clause becomes an oracle":
//   extract  — parse EARS clauses (the 5 patterns) out of a spec, flag non-EARS SHALL lines
//              as needs-clarify, emit a manifest with stable IDs.
//   scaffold — one FAILING test stub per clause, ID-tagged. loop-tester fills the bodies,
//              blind to any implementation; the ID tag must survive.
//   check    — the 1:1 gate: every clause has a test, every ID'd test has a live clause.
//              Non-zero exit on any miss — evaluator/orchestrator runs this before implement
//              closes and at batch close.
// What this script deliberately does NOT do: write real test logic. Understanding the system
// under test needs the LLM; proving the mapping is complete does not.
//
// Usage:
//   ears.js extract  <spec.md> [--out <manifest.json>]
//   ears.js scaffold <manifest.json> --lang python|vitest [--out <dir>] [--force]
//   ears.js check    <manifest.json> --tests <dir>
// Exit codes: 0 ok · 1 gate/stage failure · 2 usage error.

const fs = require("fs");
const path = require("path");

function usage(msg) {
  process.stderr.write(msg + "\n");
  process.exit(2);
}
function fail(msg) {
  process.stderr.write("ears: " + msg + "\n");
  process.exit(1);
}

// The 5 EARS patterns. Keywords are the notation's fixed English markers; the surrounding
// prose may be any language. Order matters: IF...THEN before WHEN/WHILE prefix checks.
// Any SHALL is a requirement candidate; only well-formed EARS survives extraction. A weak
// "The list SHALL be sortable" must surface as needs-clarify, not slip by silently.
const SHALL = /\bSHALL\b/i;
const PATTERNS = [
  { name: "unwanted", re: /^IF\s+(.+?),?\s+THEN\s+THE\s+SYSTEM\s+SHALL\s+(.+)$/i },
  { name: "state", re: /^WHILE\s+(.+?),?\s+THE\s+SYSTEM\s+SHALL\s+(.+)$/i },
  { name: "event", re: /^WHEN\s+(.+?),?\s+THE\s+SYSTEM\s+SHALL\s+(.+)$/i },
  { name: "optional", re: /^WHERE\s+(.+?),?\s+THE\s+SYSTEM\s+SHALL\s+(.+)$/i },
  { name: "ubiquitous", re: /^THE\s+SYSTEM\s+SHALL\s+(.+)$/i },
];

function stripBullet(line) {
  return line.replace(/^\s*(?:[-*]|\d+[.)])?\s*/, "").trim();
}

function extract(specPath) {
  const lines = fs.readFileSync(specPath, "utf8").split(/\r?\n/);
  const clauses = [];
  const malformed = [];
  lines.forEach((rawLine, i) => {
    const line = stripBullet(rawLine);
    if (!SHALL.test(line)) return;
    for (const p of PATTERNS) {
      const m = line.match(p.re);
      if (m) {
        const id = "EARS-" + String(clauses.length + 1).padStart(3, "0");
        clauses.push({
          id,
          pattern: p.name,
          trigger: p.name === "ubiquitous" ? null : m[1].trim(),
          response: (p.name === "ubiquitous" ? m[1] : m[2]).trim(),
          raw: line,
          line: i + 1,
        });
        return;
      }
    }
    // Contains SHALL but fits no pattern: not testable as written → back to clarify.
    malformed.push({ line: i + 1, raw: line });
  });
  return { source: path.resolve(specPath), extractedAt: new Date().toISOString(), clauses, malformed };
}

function slug(text, max) {
  return text
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, max);
}

const TEMPLATES = {
  python: {
    file: "test_ears_acceptance.py",
    header: (src) =>
      // Raw docstring + forward slashes: a Windows path like C:\Users would otherwise be
      // parsed as a \U unicode escape and break collection with a SyntaxError.
      'r"""Acceptance tests compiled from EARS clauses (galaxy-brain ears.js).\n' +
      "Spec: " + src.replace(/\\/g, "/") + "\n" +
      "RULES: one clause = one test. Fill each body (arrange/act/assert against the REAL\n" +
      "acceptance criterion) but KEEP the EARS-### tag in the test name/docstring —\n" +
      "`ears.js check` enforces the 1:1 mapping. Stubs fail by design until implemented.\n" +
      '"""\nimport pytest\n',
    stub: (c) =>
      "\n\ndef test_" + c.id.toLowerCase().replace("-", "_") + "_" + slug(c.response, 40) + "():\n" +
      '    r"""' + c.id + " [" + c.pattern + "]: " + c.raw.replace(/"/g, "'") + '"""\n' +
      '    pytest.fail("' + c.id + ' not implemented yet: write the acceptance test body")\n',
  },
  vitest: {
    file: "ears.acceptance.test.js",
    header: (src) =>
      "// Acceptance tests compiled from EARS clauses (galaxy-brain ears.js).\n" +
      "// Spec: " + src + "\n" +
      "// RULES: one clause = one test; keep the EARS-### tag in the test title —\n" +
      "// `ears.js check` enforces the 1:1 mapping. Stubs fail by design until implemented.\n" +
      'import { describe, it } from "vitest";\n\ndescribe("EARS acceptance", () => {',
    stub: (c) =>
      "\n  it(" + JSON.stringify(c.id + " [" + c.pattern + "] " + c.raw) + ", () => {\n" +
      "    throw new Error(" + JSON.stringify(c.id + " not implemented yet") + ");\n  });\n",
    footer: "});\n",
  },
};

function scaffold(manifest, lang, outDir, force) {
  const t = TEMPLATES[lang];
  if (!t) usage("--lang must be python|vitest");
  if (!manifest.clauses.length) fail("manifest has 0 clauses — nothing to scaffold.");
  fs.mkdirSync(outDir, { recursive: true });
  const outFile = path.join(outDir, t.file);
  if (fs.existsSync(outFile) && !force)
    fail(outFile + " already exists (may contain filled test bodies). Use --force to overwrite.");
  let body = t.header(manifest.source);
  for (const c of manifest.clauses) body += t.stub(c);
  if (t.footer) body += t.footer;
  fs.writeFileSync(outFile, body);
  console.log("scaffolded " + manifest.clauses.length + " failing stub(s) → " + outFile);
}

function walk(dir, acc) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    if (e.name === "node_modules" || e.name.startsWith(".")) continue;
    const p = path.join(dir, e.name);
    if (e.isDirectory()) walk(p, acc);
    else if (/\.(py|js|ts|mjs|cjs)$/.test(e.name)) acc.push(p);
  }
  return acc;
}

function check(manifest, testsDir) {
  if (!fs.existsSync(testsDir)) fail("tests dir not found: " + testsDir);
  const files = walk(testsDir, []);
  const found = new Map(); // id → [files]
  const idRe = /EARS-\d{3}/g;
  for (const f of files) {
    const ids = new Set((fs.readFileSync(f, "utf8").match(idRe) || []));
    for (const id of ids) found.set(id, (found.get(id) || []).concat(f));
  }
  const missing = manifest.clauses.filter((c) => !found.has(c.id));
  const live = new Set(manifest.clauses.map((c) => c.id));
  const orphans = [...found.keys()].filter((id) => !live.has(id));
  const dupes = manifest.clauses.filter((c) => (found.get(c.id) || []).length > 1);
  for (const d of dupes)
    console.log("warn: " + d.id + " appears in " + found.get(d.id).length + " files (mapping should be 1:1)");
  if (missing.length || orphans.length) {
    if (missing.length)
      process.stderr.write(
        "MISSING TESTS (clause with no test): " + missing.map((c) => c.id + " (" + c.raw.slice(0, 60) + "…)").join("; ") + "\n"
      );
    if (orphans.length)
      process.stderr.write("ORPHAN IDS (test tag with no live clause — stale or invented): " + orphans.join(", ") + "\n");
    fail("1:1 clause↔test gate FAILED: " + manifest.clauses.length + " clauses, " + missing.length + " missing, " + orphans.length + " orphan(s).");
  }
  console.log("1:1 gate OK: " + manifest.clauses.length + " clause(s), each mapped to a test. " +
    (manifest.malformed.length ? "REMINDER — " + manifest.malformed.length + " malformed SHALL line(s) pending clarify." : ""));
}

// ---- arg parsing ----
const [cmd, target, ...rest] = process.argv.slice(2);
const opts = {};
for (let i = 0; i < rest.length; i++) {
  if (rest[i] === "--out") opts.out = rest[++i];
  else if (rest[i] === "--lang") opts.lang = rest[++i];
  else if (rest[i] === "--tests") opts.tests = rest[++i];
  else if (rest[i] === "--force") opts.force = true;
  else usage("unknown argument: " + rest[i]);
}

switch (cmd) {
  case "extract": {
    if (!target) usage("extract needs a spec file");
    const manifest = extract(target);
    const out = opts.out || path.join(path.dirname(target), "ears-manifest.json");
    fs.writeFileSync(out, JSON.stringify(manifest, null, 2));
    console.log(manifest.clauses.length + " EARS clause(s) → " + out);
    for (const m of manifest.malformed)
      console.log("NEEDS-CLARIFY (SHALL line that fits no EARS pattern) line " + m.line + ": " + m.raw.slice(0, 80));
    if (!manifest.clauses.length) fail("0 EARS clauses found — the spec's acceptance criteria are not testable as written.");
    break;
  }
  case "scaffold": {
    if (!target) usage("scaffold needs a manifest file");
    scaffold(JSON.parse(fs.readFileSync(target, "utf8")), opts.lang, opts.out || "tests/acceptance", opts.force);
    break;
  }
  case "check": {
    if (!target) usage("check needs a manifest file");
    if (!opts.tests) usage("check needs --tests <dir>");
    check(JSON.parse(fs.readFileSync(target, "utf8")), opts.tests);
    break;
  }
  default:
    usage("unknown command: " + (cmd || "(none)") + " — expected extract|scaffold|check");
}
