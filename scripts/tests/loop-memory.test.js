// Regression suite for scripts/loop-memory.js (v2.0: the toolchain verifies itself).
// Integration-style: drives the real CLI against a temp store, so what we test is exactly
// what the loop runs. Pins the two bugs the manual exercise caught before wiring:
//   1. dedup by id (type:key), NOT key — a verdict must coexist with its finding.
//   2. an explicit --tags/--text filter excludes zero-score records (no recency fallback).
//
// Run: node --test scripts/tests/*.test.js   (the directory form breaks on Node 24 + Windows)
const { test } = require("node:test");
const assert = require("node:assert");
const { execFileSync } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const SCRIPT = path.join(__dirname, "..", "loop-memory.js");

function tmpStore() {
  return path.join(fs.mkdtempSync(path.join(os.tmpdir(), "gb-mem-")), "memory.jsonl");
}
function run(args) {
  try {
    const stdout = execFileSync("node", [SCRIPT, ...args], { encoding: "utf8" });
    return { code: 0, stdout };
  } catch (e) {
    return { code: e.status, stdout: (e.stdout || "").toString(), stderr: (e.stderr || "").toString() };
  }
}
function seed(store) {
  run(["append", "--store", store, "--type", "finding", "--key", "auth.py:42:bare-except",
    "--title", "except pass swallows DB error", "--tags", "security,error-handling", "--severity", "high", "--ts", "1000"]);
  run(["append", "--store", store, "--type", "verdict", "--key", "auth.py:42:bare-except",
    "--title", "confirmed real", "--verdict", "real", "--ts", "2000"]);
  run(["append", "--store", store, "--type", "finding", "--key", "api.py:10:no-timeout",
    "--title", "httpx call without timeout", "--tags", "perf,resources", "--severity", "medium", "--ts", "1500"]);
}

test("verdict and finding with the same key coexist (dedup by id, not key)", () => {
  const store = tmpStore();
  seed(store);
  const stats = JSON.parse(run(["stats", "--store", store, "--json"]).stdout);
  assert.strictEqual(stats.unique, 3, "finding+verdict share a key but are distinct observations");
  assert.strictEqual(stats.byType.finding, 2);
  assert.strictEqual(stats.byType.verdict, 1);
});

test("tag query returns only real matches, never a recency fallback", () => {
  const store = tmpStore();
  seed(store);
  const rows = JSON.parse(run(["query", "--store", store, "--tags", "security", "--json"]).stdout);
  assert.strictEqual(rows.length, 1, "only the security-tagged finding matches");
  assert.strictEqual(rows[0].key, "auth.py:42:bare-except");
});

test("no filter falls back to recency order (most recent first)", () => {
  const store = tmpStore();
  seed(store);
  const rows = JSON.parse(run(["query", "--store", store, "--type", "finding", "--json"]).stdout);
  assert.strictEqual(rows.length, 2);
  assert.strictEqual(rows[0].key, "api.py:10:no-timeout", "ts=1500 is more recent than ts=1000");
});

test("seen: exit 0 for a stored key (across types), exit 1 for a new key", () => {
  const store = tmpStore();
  seed(store);
  assert.strictEqual(run(["seen", "--store", store, "--key", "auth.py:42:bare-except"]).code, 0);
  assert.strictEqual(run(["seen", "--store", store, "--key", "nope:1:x"]).code, 1);
});

test("append rejects an unknown type", () => {
  const store = tmpStore();
  const r = run(["append", "--store", store, "--type", "guess", "--key", "k", "--title", "t"]);
  assert.strictEqual(r.code, 2, "unknown type must be a hard error, not a silent write");
});

test("a corrupt line never crashes recall", () => {
  const store = tmpStore();
  fs.mkdirSync(path.dirname(store), { recursive: true });
  fs.writeFileSync(store, '{"broken\nnot json at all\n', "utf8");
  run(["append", "--store", store, "--type", "finding", "--key", "ok:1:x", "--title", "valid one", "--ts", "1"]);
  const rows = JSON.parse(run(["query", "--store", store, "--type", "finding", "--json"]).stdout);
  assert.strictEqual(rows.length, 1, "skip corrupt lines, keep the valid observation");
});

test("query on an empty/absent store returns nothing without error", () => {
  const store = tmpStore();
  const r = run(["query", "--store", store, "--json"]);
  assert.strictEqual(r.code, 0);
  assert.deepStrictEqual(JSON.parse(r.stdout), []);
});
