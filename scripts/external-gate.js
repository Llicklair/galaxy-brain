#!/usr/bin/env node
// galaxy-brain — external gate verifier (ARCHITECTURE design rule 9, v1.0 gate).
//
// The local hook (hooks/verify-invariants.js) blocks auto-merge *inside* the agent's
// perimeter — but a hook can be bypassed by a subagent, and settings can be edited by
// the model (ecosystem-ideas.md #37). The invariant only truly holds when the FINAL gate
// lives OUTSIDE the agent: GitHub branch protection. This script does not trust prompts.
//
// It VERIFIES what protection a branch already has and maps it to galaxy-brain's two
// externally-enforceable invariants, then PRINTS the exact `gh` command to close any gap.
// It never applies protection itself: changing a remote repo's settings is outward-facing
// and requires explicit human action (run the printed command in your own terminal).
//
// Usage:
//   node external-gate.js check [--branch <name>] [--json]   # audit current protection
//   node external-gate.js print-config [--branch <name>]      # emit the gh command to fix gaps
//
// Exit codes: 0 = both invariants enforced externally · 1 = a gap exists · 2 = cannot determine
// (no gh, not a GitHub remote, no auth). Exit 2 is honest "unknown", never a false green.

const { execFileSync } = require("node:child_process");

const INVARIANTS = [
  {
    key: "never-auto-merge",
    label: "NEVER auto-merge (a human must approve the PR)",
    // required_pull_request_reviews with >=1 approving review means the loop cannot merge
    // its own PR — approval is a human/second-party event outside the agent.
    covered: (p) =>
      !!p.required_pull_request_reviews &&
      (p.required_pull_request_reviews.required_approving_review_count || 0) >= 1,
  },
  {
    key: "full-suite-gate",
    label: "Full-suite gate outside the agent (CI must pass before merge)",
    covered: (p) =>
      !!p.required_status_checks &&
      Array.isArray(p.required_status_checks.contexts || p.required_status_checks.checks) &&
      ((p.required_status_checks.contexts || p.required_status_checks.checks || []).length > 0),
  },
];

function arg(name, fallback) {
  const i = process.argv.indexOf(name);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
}
const hasFlag = (name) => process.argv.includes(name);

function sh(file, args) {
  return execFileSync(file, args, { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] }).trim();
}

function ghAvailable() {
  try {
    sh("gh", ["auth", "status"]);
    return true;
  } catch {
    return false;
  }
}

function repoSlug() {
  // gh resolves the current directory's origin remote to owner/repo.
  try {
    return sh("gh", ["repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"]);
  } catch {
    return null;
  }
}

function defaultBranch() {
  try {
    return sh("gh", ["repo", "view", "--json", "defaultBranchRef", "-q", ".defaultBranchRef.name"]);
  } catch {
    return "main";
  }
}

function fetchProtection(slug, branch) {
  // Returns the protection object, or null if the branch is unprotected (gh exits non-zero).
  try {
    const out = sh("gh", ["api", `repos/${slug}/branches/${branch}/protection`]);
    return JSON.parse(out);
  } catch {
    return null;
  }
}

function printConfigCommand(slug, branch) {
  // The minimal branch-protection payload that enforces both invariants. The user runs this
  // themselves — we print, we do not apply. `<your-ci-check>` is left as a placeholder because
  // the required check name is the repo's own CI job (detected/named per project, never hardcoded).
  const lines = [
    `# Run this yourself to move the invariants OUTSIDE the agent (one time, needs admin on the repo):`,
    `gh api -X PUT repos/${slug}/branches/${branch}/protection \\`,
    `  -H "Accept: application/vnd.github+json" \\`,
    `  -f "required_pull_request_reviews[required_approving_review_count]=1" \\`,
    `  -f "required_status_checks[strict]=true" \\`,
    `  -f "required_status_checks[contexts][]=<your-ci-check>" \\`,
    `  -F "enforce_admins=true" \\`,
    `  -F "restrictions=null"`,
    `# Replace <your-ci-check> with the CI job name that runs your full suite (e.g. "test").`,
  ];
  return lines.join("\n");
}

function main() {
  const mode = process.argv[2];
  const json = hasFlag("--json");

  if (!ghAvailable()) {
    const msg = "gh CLI not found or not authenticated — cannot verify external enforcement.";
    if (json) console.log(JSON.stringify({ status: "unknown", reason: msg }));
    else console.error(msg + "\n(Install: https://cli.github.com, then `gh auth login`.)");
    process.exit(2);
  }

  const slug = repoSlug();
  if (!slug) {
    const msg = "No GitHub remote resolved for this directory — external gate does not apply.";
    if (json) console.log(JSON.stringify({ status: "unknown", reason: msg }));
    else console.error(msg);
    process.exit(2);
  }

  const branch = arg("--branch", defaultBranch());

  if (mode === "print-config") {
    console.log(printConfigCommand(slug, branch));
    process.exit(0);
  }

  // mode === "check" (default)
  const protection = fetchProtection(slug, branch) || {};
  const results = INVARIANTS.map((inv) => ({
    key: inv.key,
    label: inv.label,
    enforced: !!inv.covered(protection),
  }));
  const allEnforced = results.every((r) => r.enforced);

  if (json) {
    console.log(JSON.stringify({ status: allEnforced ? "enforced" : "gap", repo: slug, branch, invariants: results }));
  } else {
    console.log(`External gate — ${slug} @ ${branch}:`);
    for (const r of results) console.log(`  ${r.enforced ? "✅" : "❌"} ${r.label}`);
    if (!allEnforced) {
      console.log("\nA gap exists. To close it (run it yourself — this changes remote settings):\n");
      console.log(printConfigCommand(slug, branch));
    }
  }
  process.exit(allEnforced ? 0 : 1);
}

// Guard so the module can be imported by the regression suite without running the CLI;
// behavior when invoked directly (node external-gate.js …) is unchanged.
if (require.main === module) main();

module.exports = { INVARIANTS, printConfigCommand };
