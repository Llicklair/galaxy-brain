// Regression suite for scripts/constitution.js (v2.0: the toolchain verifies itself).
// Pins the law-compiler contract (requires ast-grep on PATH):
//   1. extract parses MUST/NEVER principles into LAW-### with a classification hint.
//   2. check runs an enforced ast-grep rule: VIOLATED → exit 1, clean → exit 0.
//   3. coverage reports iron (mechanical) vs paper (judged-only) honestly.
//
// Run: node --test scripts/tests/*.test.js
const { test } = require("node:test");
const assert = require("node:assert");
const { execFileSync, execSync } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const SCRIPT = path.join(__dirname, "..", "constitution.js");

let AST_GREP = true;
try {
  execSync("ast-grep --version", { stdio: "ignore" });
} catch {
  AST_GREP = false;
}

function run(args) {
  try {
    return { code: 0, stdout: execFileSync("node", [SCRIPT, ...args], { encoding: "utf8" }) };
  } catch (e) {
    return { code: e.status, stdout: (e.stdout || "").toString(), stderr: (e.stderr || "").toString() };
  }
}
function stage() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "gb-law-"));
  fs.writeFileSync(
    path.join(dir, "constitution.md"),
    ["# Constitución", "- El código MUST NOT usar `print(` en producción", "- El código MUST ser mantenible y legible"].join("\n")
  );
  fs.mkdirSync(path.join(dir, "repo", "src"), { recursive: true });
  const lawDir = path.join(dir, "law");
  return { dir, constitution: path.join(dir, "constitution.md"), lawDir, repo: path.join(dir, "repo") };
}
function fillRules(lawDir) {
  // LAW-001 = mechanical ast-grep (print ban); LAW-002 = judged-only (paper).
  const r1 = path.join(lawDir, "rules", "law-001.json");
  const j1 = JSON.parse(fs.readFileSync(r1, "utf8"));
  j1.type = "ast-grep";
  j1.enforced = true;
  j1.astgrep_yaml = "id: law-001\nlanguage: python\nseverity: error\nmessage: no print\nrule:\n  pattern: print($$$A)\n";
  fs.writeFileSync(r1, JSON.stringify(j1));
  const r2 = path.join(lawDir, "rules", "law-002.json");
  const j2 = JSON.parse(fs.readFileSync(r2, "utf8"));
  j2.type = "judged-only";
  fs.writeFileSync(r2, JSON.stringify(j2));
}

test("extract parses MUST principles into LAW-### ids", () => {
  const s = stage();
  const r = run(["extract", s.constitution, "--out", s.lawDir]);
  assert.strictEqual(r.code, 0);
  assert.match(r.stdout, /2 principle/);
  const m = JSON.parse(fs.readFileSync(path.join(s.lawDir, "manifest.json"), "utf8"));
  assert.strictEqual(m.laws.length, 2);
  assert.strictEqual(m.laws[0].id, "LAW-001");
});

test("extract exits 1 when no principles are present", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "gb-law-"));
  fs.writeFileSync(path.join(dir, "c.md"), "# solo prosa, nada normativo\n");
  assert.strictEqual(run(["extract", path.join(dir, "c.md"), "--out", path.join(dir, "law")]).code, 1);
});

test("check flags a mechanical violation and reports iron/paper coverage", { skip: !AST_GREP ? "ast-grep not installed" : false }, () => {
  const s = stage();
  run(["extract", s.constitution, "--out", s.lawDir]);
  run(["scaffold", s.lawDir]);
  fillRules(s.lawDir);
  fs.writeFileSync(path.join(s.repo, "src", "pay.py"), 'def pay():\n    print("cobrando")\n    return 1\n');
  const bad = run(["check", s.lawDir, "--repo", s.repo]);
  assert.strictEqual(bad.code, 1, "a print() violation must fail the gate");
  assert.match(bad.stdout, /VIOLATED/);
  assert.match(bad.stdout, /iron.*paper|paper.*iron|judged-only/);
});

test("check passes once the violation is removed", { skip: !AST_GREP ? "ast-grep not installed" : false }, () => {
  const s = stage();
  run(["extract", s.constitution, "--out", s.lawDir]);
  run(["scaffold", s.lawDir]);
  fillRules(s.lawDir);
  fs.writeFileSync(path.join(s.repo, "src", "pay.py"), "def pay():\n    return 1\n");
  assert.strictEqual(run(["check", s.lawDir, "--repo", s.repo]).code, 0, "clean repo must pass");
});
