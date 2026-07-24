// Regression suite for scripts/ears.js (v2.0: the toolchain verifies itself).
// Pins the spec→oracle contract:
//   1. extract finds the 5 EARS patterns and flags a SHALL line that fits none as needs-clarify.
//   2. scaffold emits one ID-tagged stub per clause and refuses to clobber without --force.
//   3. check enforces 1:1 — a missing test OR an orphan ID both fail the gate.
//
// Run: node --test scripts/tests/*.test.js
const { test } = require("node:test");
const assert = require("node:assert");
const { execFileSync } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const SCRIPT = path.join(__dirname, "..", "ears.js");

function tmpdir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "gb-ears-"));
}
function run(args) {
  try {
    return { code: 0, stdout: execFileSync("node", [SCRIPT, ...args], { encoding: "utf8" }) };
  } catch (e) {
    return { code: e.status, stdout: (e.stdout || "").toString(), stderr: (e.stderr || "").toString() };
  }
}
const SPEC = [
  "# Feature",
  "- WHEN el usuario borra una factura pagada THE SYSTEM SHALL responder 409",
  "- IF el numero ya existe, THEN THE SYSTEM SHALL rechazar el alta",
  "- WHILE la exportacion esta en curso, THE SYSTEM SHALL bloquear nuevas exportaciones",
  "- WHERE el modulo fiscal esta activo, THE SYSTEM SHALL incluir el IVA",
  "- THE SYSTEM SHALL numerar las facturas de forma correlativa",
  "- The list SHALL be sortable", // weak: SHALL but no EARS pattern → needs-clarify
  "Texto normal.",
].join("\n");

function stage() {
  const dir = tmpdir();
  const spec = path.join(dir, "spec.md");
  fs.writeFileSync(spec, SPEC);
  const manifest = path.join(dir, "m.json");
  const testsDir = path.join(dir, "acc");
  return { dir, spec, manifest, testsDir };
}

test("extract finds 5 EARS clauses and flags the weak SHALL as needs-clarify", () => {
  const s = stage();
  const r = run(["extract", s.spec, "--out", s.manifest]);
  assert.strictEqual(r.code, 0);
  assert.match(r.stdout, /5 EARS clause/);
  assert.match(r.stdout, /NEEDS-CLARIFY/);
  const m = JSON.parse(fs.readFileSync(s.manifest, "utf8"));
  assert.strictEqual(m.clauses.length, 5);
  assert.strictEqual(m.malformed.length, 1);
});

test("extract exits 1 on a spec with zero EARS clauses", () => {
  const dir = tmpdir();
  const spec = path.join(dir, "s.md");
  fs.writeFileSync(spec, "# just prose, nothing normative here\n");
  assert.strictEqual(run(["extract", spec, "--out", path.join(dir, "m.json")]).code, 1);
});

test("scaffold emits ID-tagged stubs and refuses to clobber without --force", () => {
  const s = stage();
  run(["extract", s.spec, "--out", s.manifest]);
  assert.strictEqual(run(["scaffold", s.manifest, "--lang", "python", "--out", s.testsDir]).code, 0);
  const files = fs.readdirSync(s.testsDir);
  const body = fs.readFileSync(path.join(s.testsDir, files[0]), "utf8");
  assert.match(body, /EARS-001/);
  assert.match(body, /EARS-005/);
  assert.strictEqual(run(["scaffold", s.manifest, "--lang", "python", "--out", s.testsDir]).code, 1, "must not overwrite filled tests");
  assert.strictEqual(run(["scaffold", s.manifest, "--lang", "python", "--out", s.testsDir, "--force"]).code, 0);
});

test("check passes when every clause maps 1:1", () => {
  const s = stage();
  run(["extract", s.spec, "--out", s.manifest]);
  run(["scaffold", s.manifest, "--lang", "python", "--out", s.testsDir]);
  assert.strictEqual(run(["check", s.manifest, "--tests", s.testsDir]).code, 0);
});

test("check fails on a missing test (clause with no EARS-### tag)", () => {
  const s = stage();
  run(["extract", s.spec, "--out", s.manifest]);
  run(["scaffold", s.manifest, "--lang", "python", "--out", s.testsDir]);
  const f = path.join(s.testsDir, fs.readdirSync(s.testsDir)[0]);
  fs.writeFileSync(f, fs.readFileSync(f, "utf8").replace(/EARS-003/g, "EARSX003")); // drop LAW-003 mapping
  const r = run(["check", s.manifest, "--tests", s.testsDir]);
  assert.strictEqual(r.code, 1);
  assert.match(r.stderr, /MISSING/);
});

test("check fails on an orphan ID (test tag with no live clause)", () => {
  const s = stage();
  run(["extract", s.spec, "--out", s.manifest]);
  run(["scaffold", s.manifest, "--lang", "python", "--out", s.testsDir]);
  const f = path.join(s.testsDir, fs.readdirSync(s.testsDir)[0]);
  fs.appendFileSync(f, "\ndef test_invented():\n    pass  # EARS-099\n");
  const r = run(["check", s.manifest, "--tests", s.testsDir]);
  assert.strictEqual(r.code, 1);
  assert.match(r.stderr, /ORPHAN/);
});
