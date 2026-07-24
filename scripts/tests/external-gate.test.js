// Regression suite for scripts/external-gate.js (v2.0: the toolchain verifies itself).
// Unit-tests the invariant predicates (imported, no network) and the honesty contract:
//   1. never-auto-merge is covered only by a required PR review >= 1.
//   2. full-suite-gate is covered only by a required status check with >=1 context.
//   3. the CLI exits 2 (honest "unknown"), never a false green, where it can't determine.
//
// Run: node --test scripts/tests/*.test.js
const { test } = require("node:test");
const assert = require("node:assert");
const { execFileSync } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const SCRIPT = path.join(__dirname, "..", "external-gate.js");
const { INVARIANTS, printConfigCommand } = require(SCRIPT);
const byKey = Object.fromEntries(INVARIANTS.map((i) => [i.key, i]));

test("never-auto-merge: covered only by a required PR review >= 1", () => {
  const inv = byKey["never-auto-merge"];
  assert.strictEqual(inv.covered({ required_pull_request_reviews: { required_approving_review_count: 1 } }), true);
  assert.strictEqual(inv.covered({ required_pull_request_reviews: { required_approving_review_count: 0 } }), false);
  assert.strictEqual(inv.covered({}), false, "no protection is not enforced");
});

test("full-suite-gate: covered only by a required status check with a context", () => {
  const inv = byKey["full-suite-gate"];
  assert.strictEqual(inv.covered({ required_status_checks: { contexts: ["test"] } }), true);
  assert.strictEqual(inv.covered({ required_status_checks: { contexts: [] } }), false);
  assert.strictEqual(inv.covered({}), false);
});

test("printConfigCommand emits a gh api PUT for the given slug and branch", () => {
  const cmd = printConfigCommand("owner/repo", "main");
  assert.match(cmd, /gh api -X PUT repos\/owner\/repo\/branches\/main\/protection/);
  assert.match(cmd, /required_approving_review_count/);
});

test("the CLI exits 2 (honest unknown) outside any GitHub repo, never a false green", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "gb-eg-"));
  let code = 0;
  try {
    execFileSync("node", [SCRIPT, "check"], { cwd: dir, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
  } catch (e) {
    code = e.status;
  }
  assert.strictEqual(code, 2, "no GitHub remote resolvable → exit 2, not 0");
});
