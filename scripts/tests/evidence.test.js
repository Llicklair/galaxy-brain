// Regression suite for scripts/evidence.js (v2.0: the toolchain verifies itself).
// Integration-style: drives the real CLI against a temp state dir + temp test files, so what
// we test is exactly what the loop runs. Pins the anti-gaming core:
//   1. red REFUSES a test that already passes (a green "before" proves nothing).
//   2. green REFUSES a test file edited since red (hash-pinned red→green chain).
//   3. bundle REFUSES an incomplete chain or a non-PASS verdict.
//
// Run: node --test scripts/tests/*.test.js
const { test } = require("node:test");
const assert = require("node:assert");
const { execFileSync } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const SCRIPT = path.join(__dirname, "..", "evidence.js");

function tmpdir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "gb-ev-"));
}
function run(args) {
  try {
    return { code: 0, stdout: execFileSync("node", [SCRIPT, ...args], { encoding: "utf8" }) };
  } catch (e) {
    return { code: e.status, stdout: (e.stdout || "").toString(), stderr: (e.stderr || "").toString() };
  }
}
// A command string (single post-`--` element) that exits with the given code, cross-platform.
function exitCmd(dir, code) {
  const f = path.join(dir, "exit" + code + ".js");
  fs.writeFileSync(f, "process.exit(" + code + ");\n");
  return 'node "' + f + '"';
}

test("red REFUSES a test that already passes", () => {
  const dir = tmpdir();
  const testfile = path.join(dir, "t.py");
  fs.writeFileSync(testfile, "def test_x():\n    assert True\n");
  const r = run(["red", "--id", "a", "--dir", dir, "--test", testfile, "--", exitCmd(dir, 0)]);
  assert.strictEqual(r.code, 1, "a passing red must be rejected");
  assert.match(r.stderr, /PASSED/);
});

test("green REFUSES a test file edited since red (hash chain broken)", () => {
  const dir = tmpdir();
  const testfile = path.join(dir, "t.py");
  fs.writeFileSync(testfile, "def test_x():\n    assert real_thing()\n");
  assert.strictEqual(run(["red", "--id", "a", "--dir", dir, "--test", testfile, "--", exitCmd(dir, 1)]).code, 0);
  fs.writeFileSync(testfile, "def test_x():\n    assert True  # weakened\n"); // tamper
  const g = run(["green", "--id", "a", "--dir", dir, "--", exitCmd(dir, 0)]);
  assert.strictEqual(g.code, 1, "editing the test between red and green must break the chain");
  assert.match(g.stderr, /CHANGED SINCE RED|chain/i);
});

test("full chain red→green→suite→verdict→bundle yields PASS bundle", () => {
  const dir = tmpdir();
  const testfile = path.join(dir, "t.py");
  fs.writeFileSync(testfile, "def test_x():\n    assert real_thing()\n");
  assert.strictEqual(run(["red", "--id", "a", "--dir", dir, "--test", testfile, "--", exitCmd(dir, 1)]).code, 0);
  assert.strictEqual(run(["green", "--id", "a", "--dir", dir, "--", exitCmd(dir, 0)]).code, 0);
  assert.strictEqual(run(["suite", "--id", "a", "--dir", dir, "--", exitCmd(dir, 0)]).code, 0);
  assert.strictEqual(run(["verdict", "--id", "a", "--dir", dir, "--by", "gemini", "--result", "PASS"]).code, 0);
  const b = run(["bundle", "--id", "a", "--dir", dir]);
  assert.strictEqual(b.code, 0);
  assert.match(b.stdout, /### Evidence/);
});

test("bundle REFUSES an incomplete chain", () => {
  const dir = tmpdir();
  const testfile = path.join(dir, "t.py");
  fs.writeFileSync(testfile, "def test_x():\n    assert real_thing()\n");
  run(["red", "--id", "a", "--dir", dir, "--test", testfile, "--", exitCmd(dir, 1)]);
  const b = run(["bundle", "--id", "a", "--dir", dir]);
  assert.strictEqual(b.code, 1, "a bundle with no green/suite/verdict must be refused");
  assert.match(b.stderr, /incomplete|missing/i);
});

test("bundle REFUSES a non-PASS verdict", () => {
  const dir = tmpdir();
  const testfile = path.join(dir, "t.py");
  fs.writeFileSync(testfile, "def test_x():\n    assert real_thing()\n");
  run(["red", "--id", "a", "--dir", dir, "--test", testfile, "--", exitCmd(dir, 1)]);
  run(["green", "--id", "a", "--dir", dir, "--", exitCmd(dir, 0)]);
  run(["suite", "--id", "a", "--dir", dir, "--", exitCmd(dir, 0)]);
  run(["verdict", "--id", "a", "--dir", dir, "--by", "gemini", "--result", "REJECT"]);
  const b = run(["bundle", "--id", "a", "--dir", dir]);
  assert.strictEqual(b.code, 1, "a REJECT verdict must not ship a bundle");
});
