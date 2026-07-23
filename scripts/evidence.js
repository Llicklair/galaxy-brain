#!/usr/bin/env node
// galaxy-brain — red→green evidence bundle (ARCHITECTURE design rule 10).
// "Verified" is an artifact, not a claim: this records the failing test BEFORE the fix,
// proves the same (hash-identical) test passes AFTER it, plus full-suite result and the
// evaluator's verdict, and emits a machine-checkable bundle for the PR body.
// The test-file hashes recorded at `red` MUST match at `green` — a weakened or edited
// test between red and green invalidates the chain (the loop's core anti-gaming primitive).
//
// Usage (run by the loop orchestrator, state lives OUTSIDE the target repo):
//   evidence.js red     --id <item> [--dir <state>] --test <file> [--test <file>...] -- <test command>
//   evidence.js green   --id <item> [--dir <state>] -- <same test command>
//   evidence.js suite   --id <item> [--dir <state>] -- <full-suite command>
//   evidence.js verdict --id <item> [--dir <state>] --by <model> --result PASS|REJECT|BLOCKER [--notes <text>]
//   evidence.js bundle  --id <item> [--dir <state>]     → prints the PR-body markdown, writes <id>.evidence.json
// Exit codes: 0 ok · 1 invalid chain / wrong stage outcome · 2 usage error.

const { spawnSync } = require("child_process");
const crypto = require("crypto");
const fs = require("fs");
const os = require("os");
const path = require("path");

const TAIL_LINES = 120;

function usage(msg) {
  process.stderr.write(msg + "\n");
  process.exit(2);
}

function parseArgs(argv) {
  const args = { tests: [], cmd: null };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--") {
      args.cmd = argv.slice(i + 1).join(" ");
      break;
    } else if (a === "--test") args.tests.push(argv[++i]);
    else if (a === "--dir") args.dir = argv[++i];
    else if (a === "--id") args.id = argv[++i];
    else if (a === "--by") args.by = argv[++i];
    else if (a === "--result") args.result = argv[++i];
    else if (a === "--notes") args.notes = argv[++i];
    else usage("unknown argument: " + a);
  }
  if (!args.id) usage("--id is required");
  if (!args.dir)
    args.dir = path.join(os.homedir(), ".claude", "galaxy-brain", "evidence", path.basename(process.cwd()));
  return args;
}

function statePath(args) {
  return path.join(args.dir, args.id + ".json");
}

function loadState(args) {
  try {
    return JSON.parse(fs.readFileSync(statePath(args), "utf8"));
  } catch {
    return { id: args.id, createdAt: new Date().toISOString() };
  }
}

function saveState(args, state) {
  fs.mkdirSync(args.dir, { recursive: true });
  fs.writeFileSync(statePath(args), JSON.stringify(state, null, 2));
}

function sha256(file) {
  // CRLF→LF before hashing: on Windows, git autocrlf rewrites line endings on checkout,
  // which would break the red→green chain without any semantic change to the test.
  const normalized = fs.readFileSync(file).toString("binary").replace(/\r\n/g, "\n");
  return crypto.createHash("sha256").update(Buffer.from(normalized, "binary")).digest("hex");
}

function gitHead() {
  const r = spawnSync("git", ["rev-parse", "HEAD"], { encoding: "utf8" });
  return r.status === 0 ? r.stdout.trim() : null;
}

function run(cmd) {
  const started = Date.now();
  const r = spawnSync(cmd, { shell: true, encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
  const out = ((r.stdout || "") + (r.stderr || "")).split(/\r?\n/);
  return {
    command: cmd,
    exitCode: r.status === null ? -1 : r.status,
    durationMs: Date.now() - started,
    outputTail: out.slice(-TAIL_LINES).join("\n"),
    at: new Date().toISOString(),
    commit: gitHead(),
  };
}

function fail(msg) {
  process.stderr.write("evidence: " + msg + "\n");
  process.exit(1);
}

function verifyHashes(recorded) {
  const mismatches = [];
  for (const [file, hash] of Object.entries(recorded)) {
    let now;
    try {
      now = sha256(file);
    } catch {
      mismatches.push(file + " (missing)");
      continue;
    }
    if (now !== hash) mismatches.push(file);
  }
  return mismatches;
}

const [stage, ...rest] = process.argv.slice(2);
const args = parseArgs(rest);
const state = loadState(args);

switch (stage) {
  case "red": {
    if (!args.cmd) usage("red needs a test command after --");
    if (!args.tests.length) usage("red needs at least one --test <file>");
    const hashes = {};
    for (const t of args.tests) {
      if (!fs.existsSync(t)) fail("test file not found: " + t);
      hashes[t] = sha256(t);
    }
    const result = run(args.cmd);
    if (result.exitCode === 0)
      fail("the red run PASSED (exit 0) — a test that does not fail before the fix proves nothing. Not recorded.");
    state.red = { ...result, testHashes: hashes };
    delete state.green; // a new red invalidates any earlier green
    saveState(args, state);
    console.log("red recorded: exit " + result.exitCode + ", " + args.tests.length + " test file(s) hashed");
    break;
  }
  case "green": {
    if (!args.cmd) usage("green needs a test command after --");
    if (!state.red) fail("no red run recorded for '" + args.id + "' — red must come first (test-first).");
    const mismatches = verifyHashes(state.red.testHashes);
    if (mismatches.length)
      fail(
        "TEST FILES CHANGED SINCE RED: " + mismatches.join(", ") +
          " — the red→green chain is broken (weakened/edited test?). Re-run red with the current test if the change is legitimate."
      );
    const result = run(args.cmd);
    if (result.exitCode !== 0) fail("the green run FAILED (exit " + result.exitCode + "). Not recorded.");
    state.green = result;
    saveState(args, state);
    console.log("green recorded: same test files, hash-verified, exit 0");
    break;
  }
  case "suite": {
    if (!args.cmd) usage("suite needs a command after --");
    const result = run(args.cmd);
    if (result.exitCode !== 0) fail("full suite FAILED (exit " + result.exitCode + "). Not recorded.");
    state.suite = result;
    saveState(args, state);
    console.log("suite recorded: exit 0");
    break;
  }
  case "verdict": {
    if (!args.by) usage("verdict needs --by <evaluator model>");
    if (!["PASS", "REJECT", "BLOCKER"].includes(args.result || ""))
      usage("verdict needs --result PASS|REJECT|BLOCKER");
    state.verdict = { by: args.by, result: args.result, notes: args.notes || "", at: new Date().toISOString() };
    saveState(args, state);
    console.log("verdict recorded: " + args.result + " by " + args.by);
    break;
  }
  case "bundle": {
    const missing = [];
    if (!state.red) missing.push("red run");
    if (!state.green) missing.push("green run");
    if (!state.suite) missing.push("full-suite run");
    if (!state.verdict) missing.push("evaluator verdict");
    if (missing.length) fail("incomplete chain — missing: " + missing.join(", "));
    if (state.verdict.result !== "PASS")
      fail("evaluator verdict is " + state.verdict.result + " — a bundle only ships on PASS.");
    const mismatches = verifyHashes(state.red.testHashes);
    if (mismatches.length) fail("test files changed after green: " + mismatches.join(", "));
    const bundle = { ...state, bundledAt: new Date().toISOString() };
    const outFile = path.join(args.dir, args.id + ".evidence.json");
    fs.writeFileSync(outFile, JSON.stringify(bundle, null, 2));
    const files = Object.keys(state.red.testHashes);
    console.log(
      [
        "### Evidence — " + args.id,
        "",
        "| Stage | Result | Commit |",
        "|---|---|---|",
        "| Red (before fix) | exit " + state.red.exitCode + " · " + state.red.at + " | `" + (state.red.commit || "n/a") + "` |",
        "| Green (after fix, hash-identical test) | exit 0 · " + state.green.at + " | `" + (state.green.commit || "n/a") + "` |",
        "| Full suite | exit 0 · " + state.suite.at + " | `" + (state.suite.commit || "n/a") + "` |",
        "| Evaluator | " + state.verdict.result + " (" + state.verdict.by + ") | |",
        "",
        "Test files (SHA-256 pinned at red, verified at green and bundle time):",
        ...files.map((f) => "- `" + f + "` `" + state.red.testHashes[f].slice(0, 16) + "…`"),
        "",
        "Full bundle: `" + outFile + "`",
      ].join("\n")
    );
    break;
  }
  default:
    usage("unknown stage: " + (stage || "(none)") + " — expected red|green|suite|verdict|bundle");
}
