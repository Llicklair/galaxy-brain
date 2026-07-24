#!/usr/bin/env node
// galaxy-brain — verification invariants as hooks (ARCHITECTURE design rule 9).
// Blocks two things a shell command can do that must never happen INSIDE AN AUTONOMOUS LOOP:
//   1. AUTO-MERGE — an autonomous forja/construye pass must never merge; it proposes, the human
//      decides (design rule 5).
//   2. Snapshot baselines — a loop must never silently update a baseline (an approval event).
//
// Refined policy (2026-07-24, deliberate owner decision): "never auto-merge" means the AUTONOMOUS
// LOOP never merges — not that the agent may never run a merge a human explicitly directs in an
// interactive session. So the block is scoped to loop context: it applies only while a loop-active
// marker is present. The loops (forja/construye) create the marker at the start of a pass and
// remove it when the pass ends; interactive sessions have no marker, so a human-directed
// `gh pr merge` runs normally. The loop guarantee is defense-in-depth: the skills never call merge,
// AND this hook blocks it whenever the marker says a loop is running.
//
// Exit 2 + stderr = deny (PreToolUse contract). Anything unparseable exits 0: this hook must never
// break unrelated commands. This is defense INSIDE the agent's perimeter; the final, non-bypassable
// gate for teams still lives OUTSIDE it — GitHub branch protection (scripts/external-gate.js).

const fs = require("fs");
const os = require("os");
const path = require("path");

// A loop is active if it left a marker file, or explicitly set the env flag. The marker path is
// overridable (env) for testing; by default it lives outside any repo, with the loop state.
const MARKER =
  process.env.GALAXY_BRAIN_LOOP_MARKER ||
  path.join(os.homedir(), ".claude", "galaxy-brain", "loop-active");

function loopActive() {
  if (process.env.GALAXY_BRAIN_LOOP === "1") return true;
  try {
    return fs.existsSync(MARKER);
  } catch {
    return false;
  }
}

const AUTO_MERGE = [
  /\bgh\s+pr\s+merge\b/,
  /--auto-merge\b/,
  /enablePullRequestAutoMerge/,
  /\bgh\s+api\b[\s\S]*\/pulls\/\S*\/merge\b/,
];

const SNAPSHOT_UPDATE = [
  /--update-snapshots?\b/,
  /--updateSnapshot\b/,
  /\b(jest|vitest)\b[^|;&]*\s-u\b/,
];

function deny(reason) {
  process.stderr.write(reason + "\n");
  process.exit(2);
}

let raw = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk) => (raw += chunk));
process.stdin.on("end", () => {
  let command;
  try {
    const input = JSON.parse(raw);
    command = input && input.tool_input && input.tool_input.command;
  } catch {
    process.exit(0);
  }
  if (typeof command !== "string") process.exit(0);

  // Interactive session (no loop marker): the human directs; nothing here to enforce.
  if (!loopActive()) process.exit(0);

  if (AUTO_MERGE.some((re) => re.test(command))) {
    deny(
      "galaxy-brain invariant: an autonomous loop is running (marker present) and must NEVER merge — " +
        "it proposes, the human decides. If this is you merging by hand, the loop isn't done cleanly: " +
        "stop the pass first (the marker is removed at stop), or clear a stale marker with " +
        "`rm -f \"" + MARKER + "\"` if a loop crashed."
    );
  }
  if (SNAPSHOT_UPDATE.some((re) => re.test(command))) {
    deny(
      "galaxy-brain invariant: an autonomous loop must not silently update snapshot baselines — a " +
        "changed baseline is an observable behavior change to approve, not a fix. Clear a stale " +
        "marker with `rm -f \"" + MARKER + "\"` if no loop is running."
    );
  }
  process.exit(0);
});
