#!/usr/bin/env node
// galaxy-brain — test-gaming detector over test-file diffs (feeds the evaluator; ARCHITECTURE
// rules 1 & 4, evidence: METR/EvilGenie reward-hacking findings in docs/deep-scan-2026-07.md).
// evidence.js already pins NEW tests between red and green; this guards the other cheat route:
// an agent "fixing" the suite by touching EXISTING tests. Four signal families over a git range:
//   TEST_REMOVED    — test definitions deleted
//   ASSERT_REMOVED  — net loss of assertion lines in a modified test file
//   SKIP_ADDED      — skip/xfail/todo markers added
//   WEAKENER_ADDED  — assertions replaced by weaker forms (approx, truthy, assert True, or True)
// High recall, modest precision BY DESIGN: exit 1 means "the evaluator must justify every flag
// or REJECT", never an automatic verdict — legitimate refactors trip it and that is fine.
//
// Usage: test-guard.js <base>..<head> [--repo <dir>] [--json]
// Exit codes: 0 no flags · 1 flags raised (evaluator must address) · 2 usage/git error.

const { spawnSync } = require("child_process");
const path = require("path");

function usage(msg) {
  process.stderr.write(msg + "\n");
  process.exit(2);
}

const TEST_FILE = /(^|[\\/])(tests?|__tests__|spec)([\\/]|$)|\.(test|spec)\.[jt]sx?$|(^|[\\/])test_[^\\/]+\.py$|_test\.(py|go|rb)$/i;

const TEST_DEF = [
  /^\s*def\s+test_\w+/, // pytest
  /^\s*(it|test)\s*\(/, // jest/vitest/mocha
  /^\s*func\s+Test\w+/, // go
  /^\s*(it|specify|scenario)\s+['"]/, // rspec
];
const ASSERTION = [
  /^\s*(assert\s|assert\()/, // python/generic
  /\bexpect\s*\(/, // jest/vitest/chai
  /\bassert(Equal|True|False|In|Is|Raises|AlmostEqual|Greater|Less|Regex)\w*\s*\(/, // unittest
  /^\s*\w*\.?(should|must)\b/, // should-style
  /\bt\.(is|deepEqual|truthy|falsy|throws)\(/, // ava/go-ish
];
const SKIP_ADDED = [
  /@pytest\.mark\.(skip|skipif|xfail)/,
  /@unittest\.skip/,
  /\b(it|test|describe)\.(skip|todo|failing)\s*\(/,
  /^\s*x(it|test|describe)\s*\(/,
  /pytest\.skip\s*\(/,
];
const WEAKENER = [
  /pytest\.approx\s*\(/,
  /assertAlmostEqual\s*\(/,
  /\.(toBeTruthy|toBeDefined|toBeInstanceOf)\s*\(/,
  /^\s*assert\s+(True|1)\b/,
  /\bor\s+True\b/,
  /\|\|\s*true\b/,
  /expect\s*\(\s*true\s*\)/i,
];

function matchAny(res, line) {
  return res.some((re) => re.test(line));
}

const args = process.argv.slice(2);
const range = args[0];
if (!range || !range.includes("..")) usage("first argument must be a git range: <base>..<head>");
let repo = process.cwd();
let asJson = false;
for (let i = 1; i < args.length; i++) {
  if (args[i] === "--repo") repo = args[++i];
  else if (args[i] === "--json") asJson = true;
  else usage("unknown argument: " + args[i]);
}

const diff = spawnSync("git", ["-C", repo, "diff", "--unified=0", range], {
  encoding: "utf8",
  maxBuffer: 64 * 1024 * 1024,
});
if (diff.status !== 0) usage("git diff failed: " + (diff.stderr || "").trim());

// Walk the unified diff; collect added/removed lines per test file.
const files = {};
let current = null;
for (const line of diff.stdout.split(/\r?\n/)) {
  const header = line.match(/^\+\+\+ b\/(.+)$/);
  if (header) {
    current = TEST_FILE.test(header[1]) ? (files[header[1]] = { added: [], removed: [] }) : null;
    continue;
  }
  if (!current) continue;
  if (/^\+[^+]/.test(line) || line === "+") current.added.push(line.slice(1));
  else if (/^-[^-]/.test(line) || line === "-") current.removed.push(line.slice(1));
}

const flags = [];
for (const [file, { added, removed }] of Object.entries(files)) {
  const removedDefs = removed.filter((l) => matchAny(TEST_DEF, l));
  const addedDefs = added.filter((l) => matchAny(TEST_DEF, l));
  if (removedDefs.length > addedDefs.length)
    flags.push({
      file,
      signal: "TEST_REMOVED",
      detail: removedDefs.length - addedDefs.length + " test definition(s) deleted",
      evidence: removedDefs.slice(0, 3).map((s) => s.trim()),
    });

  const removedAsserts = removed.filter((l) => matchAny(ASSERTION, l)).length;
  const addedAsserts = added.filter((l) => matchAny(ASSERTION, l)).length;
  if (removedAsserts > addedAsserts)
    flags.push({
      file,
      signal: "ASSERT_REMOVED",
      detail: "net assertion loss: -" + (removedAsserts - addedAsserts) + " (removed " + removedAsserts + ", added " + addedAsserts + ")",
      evidence: removed.filter((l) => matchAny(ASSERTION, l)).slice(0, 3).map((s) => s.trim()),
    });

  const skips = added.filter((l) => matchAny(SKIP_ADDED, l));
  if (skips.length)
    flags.push({ file, signal: "SKIP_ADDED", detail: skips.length + " skip/xfail/todo marker(s) added", evidence: skips.slice(0, 3).map((s) => s.trim()) });

  const weak = added.filter((l) => matchAny(WEAKENER, l));
  if (weak.length)
    flags.push({ file, signal: "WEAKENER_ADDED", detail: weak.length + " weakened assertion form(s) added", evidence: weak.slice(0, 3).map((s) => s.trim()) });
}

const report = { range, repo: path.resolve(repo), testFilesChanged: Object.keys(files).length, flags };
if (asJson) console.log(JSON.stringify(report, null, 2));
else if (!flags.length) console.log("test-guard OK: " + report.testFilesChanged + " test file(s) changed in " + range + ", no gaming signals.");
else {
  console.log("test-guard: " + flags.length + " signal(s) in " + range + " — the evaluator must justify each one or REJECT:");
  for (const f of flags) console.log("  [" + f.signal + "] " + f.file + " — " + f.detail + (f.evidence.length ? "  e.g. `" + f.evidence[0] + "`" : ""));
}
process.exit(flags.length ? 1 : 0);
