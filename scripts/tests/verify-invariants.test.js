// Regression suite for hooks/verify-invariants.js (v2.0: the toolchain verifies itself).
// Pins the refined policy: the merge/snapshot block applies ONLY while a loop-active marker is
// present. Interactive (no marker) → the human directs, nothing is blocked. Loop (marker) → an
// autonomous merge or snapshot-update is denied (exit 2). Unrelated commands always pass, and a
// plain `git merge` must never be mistaken for a PR merge.
//
// Run: node --test scripts/tests/*.test.js
const { test } = require("node:test");
const assert = require("node:assert");
const { execFileSync } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const HOOK = path.join(__dirname, "..", "..", "hooks", "verify-invariants.js");

// Run the hook with a command and a chosen loop state; return its exit code.
function run(command, { loop } = { loop: false }) {
  const marker = path.join(fs.mkdtempSync(path.join(os.tmpdir(), "gb-hook-")), "loop-active");
  if (loop) fs.writeFileSync(marker, "");
  try {
    execFileSync("node", [HOOK], {
      input: JSON.stringify({ tool_input: { command } }),
      encoding: "utf8",
      env: { ...process.env, GALAXY_BRAIN_LOOP_MARKER: marker, GALAXY_BRAIN_LOOP: "" },
    });
    return 0;
  } catch (e) {
    return e.status;
  }
}

test("interactive (no marker): a human-directed gh pr merge is allowed", () => {
  assert.strictEqual(run("gh pr merge 1 --squash", { loop: false }), 0);
});

test("interactive (no marker): --update-snapshots is allowed", () => {
  assert.strictEqual(run("npx vitest run -u", { loop: false }), 0);
});

test("loop active (marker): gh pr merge is denied (exit 2)", () => {
  assert.strictEqual(run("gh pr merge 1 --squash", { loop: true }), 2);
});

test("loop active (marker): REST/GraphQL merge and --auto-merge are denied", () => {
  assert.strictEqual(run("gh api -X PUT repos/o/r/pulls/12/merge", { loop: true }), 2);
  assert.strictEqual(run("gh pr merge --auto 5", { loop: true }), 2);
});

test("loop active (marker): a snapshot-update is denied", () => {
  assert.strictEqual(run("npx playwright test --update-snapshots", { loop: true }), 2);
  assert.strictEqual(run("npx jest --updateSnapshot", { loop: true }), 2);
});

test("loop active (marker): unrelated commands still pass", () => {
  assert.strictEqual(run("git status", { loop: true }), 0);
  assert.strictEqual(run("npx vitest run", { loop: true }), 0);
});

test("a plain `git merge` is never mistaken for a PR merge, loop or not", () => {
  assert.strictEqual(run("git merge origin/main", { loop: true }), 0);
  assert.strictEqual(run("git merge origin/main", { loop: false }), 0);
});

test("malformed hook input never blocks (exit 0)", () => {
  let code = 0;
  try {
    execFileSync("node", [HOOK], { input: "not-json", encoding: "utf8" });
  } catch (e) {
    code = e.status;
  }
  assert.strictEqual(code, 0);
});
