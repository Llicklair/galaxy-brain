// Regression suite for scripts/test-guard.js (v2.0: the toolchain verifies itself).
// Pins the gaming-detection contract over a real git range:
//   1. a gaming commit (deleted test, weakened asserts, added skip) raises signals → exit 1.
//   2. a legitimate test addition raises nothing → exit 0.
//
// Run: node --test scripts/tests/*.test.js
const { test } = require("node:test");
const assert = require("node:assert");
const { execFileSync } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const SCRIPT = path.join(__dirname, "..", "test-guard.js");

function git(dir, args) {
  return execFileSync("git", ["-C", dir, ...args], { encoding: "utf8" });
}
function commit(dir, msg) {
  git(dir, ["add", "-A"]);
  git(dir, ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", msg]);
  return git(dir, ["rev-parse", "--short", "HEAD"]).trim();
}
function run(range, dir) {
  try {
    return { code: 0, stdout: execFileSync("node", [SCRIPT, range, "--repo", dir], { encoding: "utf8" }) };
  } catch (e) {
    return { code: e.status, stdout: (e.stdout || "").toString(), stderr: (e.stderr || "").toString() };
  }
}
function repo() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "gb-tg-"));
  git(dir, ["init", "-q"]);
  fs.mkdirSync(path.join(dir, "tests"));
  fs.writeFileSync(
    path.join(dir, "tests", "test_calc.py"),
    "def test_add():\n    assert add(2, 3) == 5\n    assert add(-1, 1) == 0\n\ndef test_sub():\n    assert sub(5, 3) == 2\n"
  );
  return dir;
}

test("a gaming commit (delete + weaken + skip) is flagged, exit 1", () => {
  const dir = repo();
  const base = commit(dir, "base");
  // Delete test_sub, weaken test_add's assertion, add an xfail marker.
  fs.writeFileSync(
    path.join(dir, "tests", "test_calc.py"),
    "import pytest\n\n@pytest.mark.xfail(reason='flaky')\ndef test_add():\n    assert add(2, 3) == pytest.approx(5.1, rel=0.5)\n"
  );
  const head = commit(dir, "make it green");
  const r = run(base + ".." + head, dir);
  assert.strictEqual(r.code, 1, "gaming must be flagged");
  assert.match(r.stdout, /TEST_REMOVED|ASSERT_REMOVED|SKIP_ADDED|WEAKENER_ADDED/);
});

test("a legitimate test addition raises no signals, exit 0", () => {
  const dir = repo();
  const base = commit(dir, "base");
  fs.writeFileSync(
    path.join(dir, "tests", "test_new.py"),
    "def test_mul():\n    assert mul(2, 3) == 6\n    assert mul(0, 9) == 0\n"
  );
  const head = commit(dir, "add coverage");
  const r = run(base + ".." + head, dir);
  assert.strictEqual(r.code, 0, "adding a strong test is not gaming");
  assert.match(r.stdout, /no gaming signals/);
});
