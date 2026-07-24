// Regression suite for scripts/memory-global.js (v2.0: the toolchain verifies itself).
// Pins the cross-repo memory contract:
//   1. add writes a note and (re)builds the index; re-adding a name overwrites, never duplicates.
//   2. recall returns the FULL body of notes whose description/tags match, and nothing else.
//   3. context (the SessionStart payload) is lean: index of everything, full text ONLY for
//      `always`-scope notes and notes for the current project. Empty vault → silent exit 0.
//
// Run: node --test scripts/tests/*.test.js
const { test } = require("node:test");
const assert = require("node:assert");
const { execFileSync } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const SCRIPT = path.join(__dirname, "..", "memory-global.js");

function vault() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "gb-mem-global-"));
}
function run(dir, args) {
  try {
    return { code: 0, stdout: execFileSync("node", [SCRIPT, ...args], {
      encoding: "utf8",
      env: { ...process.env, GALAXY_BRAIN_MEMORY_DIR: dir },
    }) };
  } catch (e) {
    return { code: e.status, stdout: (e.stdout || "").toString(), stderr: (e.stderr || "").toString() };
  }
}

test("add writes a note, builds the index, and dedups by name", () => {
  const dir = vault();
  run(dir, ["add", "--name", "toolchain", "--description", "gemini cli operativo", "--scope", "always", "--tags", "machine", "--body", "GEMINI_API_KEY set"]);
  assert.ok(fs.existsSync(path.join(dir, "toolchain.md")));
  assert.match(fs.readFileSync(path.join(dir, "MEMORY.md"), "utf8"), /toolchain/);
  run(dir, ["add", "--name", "toolchain", "--description", "gemini cli operativo (v2)", "--scope", "always", "--body", "updated"]);
  const files = fs.readdirSync(dir).filter((f) => f.startsWith("toolchain"));
  assert.strictEqual(files.length, 1, "re-adding a name overwrites, never duplicates");
  assert.match(fs.readFileSync(path.join(dir, "toolchain.md"), "utf8"), /updated/);
});

test("recall returns the full body of matching notes only", () => {
  const dir = vault();
  run(dir, ["add", "--name", "toolchain", "--description", "gemini evaluador cross-vendor", "--tags", "gemini,eval", "--body", "run gemini -p for verdicts"]);
  run(dir, ["add", "--name", "coffee", "--description", "prefers oat milk", "--tags", "personal", "--body", "irrelevant to eval"]);
  const hit = run(dir, ["recall", "gemini", "evaluador"]);
  assert.match(hit.stdout, /run gemini -p for verdicts/);
  assert.doesNotMatch(hit.stdout, /oat milk/, "an unrelated note must not surface");
  const miss = run(dir, ["recall", "kubernetes"]);
  assert.match(miss.stdout, /no global memory matched/);
});

test("context loads always-scope in full, general only in the index", () => {
  const dir = vault();
  run(dir, ["add", "--name", "rules", "--description", "ask before heavy machinery", "--scope", "always", "--body", "PROPOSE-THEN-ACT"]);
  run(dir, ["add", "--name", "trivia", "--description", "some general note", "--scope", "general", "--body", "SHOULD-NOT-LOAD-IN-FULL"]);
  const ctx = run(dir, ["context"]);
  assert.match(ctx.stdout, /PROPOSE-THEN-ACT/, "always-scope note loads in full");
  assert.match(ctx.stdout, /some general note/, "general note appears in the index line");
  assert.doesNotMatch(ctx.stdout, /SHOULD-NOT-LOAD-IN-FULL/, "general note body must NOT be injected");
});

test("context loads notes for the current project in full", () => {
  const dir = vault();
  run(dir, ["add", "--name", "erp-quirk", "--description", "the ERP uses X", "--scope", "general", "--tags", "myapp", "--body", "PROJECT-SPECIFIC-FACT"]);
  assert.doesNotMatch(run(dir, ["context", "--project", "other"]).stdout, /PROJECT-SPECIFIC-FACT/);
  assert.match(run(dir, ["context", "--project", "myapp"]).stdout, /PROJECT-SPECIFIC-FACT/);
});

test("context on an empty vault stays silent (exit 0, no output)", () => {
  const dir = vault();
  const r = run(dir, ["context"]);
  assert.strictEqual(r.code, 0);
  assert.strictEqual(r.stdout.trim(), "");
});
