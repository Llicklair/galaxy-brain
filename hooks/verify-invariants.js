#!/usr/bin/env node
// galaxy-brain — verification invariants as hooks (ARCHITECTURE design rule 9).
// Blocks, mechanically and prompt-independently, the two invariants a shell command can violate:
//   1. NEVER AUTO-MERGE — the human merges, the loop never does (design rule 5).
//   2. Snapshot baselines are human/evaluator-approval events, never a silent agent update.
// Exit 2 + stderr = deny (PreToolUse contract). Anything unparseable exits 0: this hook must
// never break unrelated commands, and the final gate lives outside the agent anyway
// (branch protection / CI — see ARCHITECTURE rule 9).

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

  if (AUTO_MERGE.some((re) => re.test(command))) {
    deny(
      "galaxy-brain invariant: NEVER auto-merge. The loop judges and proposes; the human merges. " +
        "If the user truly wants this merged, they run it themselves in their own terminal."
    );
  }
  if (SNAPSHOT_UPDATE.some((re) => re.test(command))) {
    deny(
      "galaxy-brain invariant: snapshot baselines are approval events, not fixes. A changed baseline " +
        "is an observable behavior change — attach evidence and let the evaluator/human approve it. " +
        "Do not re-run with --update-snapshots/-u."
    );
  }
  process.exit(0);
});
