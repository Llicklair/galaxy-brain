# galaxy-brain — Scope

## Vision

**One install, any project.** galaxy-brain turns a stock Claude Code into a verification-first
engineering harness for *whatever* repo it lands on — ERP backend, CLI tool, frontend, monorepo —
with zero per-project configuration: the loops detect the project's real gates, stack and tools
instead of assuming them.

"Super Claude Code" here does NOT mean more commands, more personas, more tools. The evidence
(see [docs/research-report.md](docs/research-report.md)) says elaborate scaffolds add little and burn
context. It means one thing done properly: **nothing ships unverified** — deterministic gates first,
an adversarial evaluator on a different model second, and a human merging at the end. Always.

## What galaxy-brain IS

- A **Claude Code plugin** (skills + agents), installable in two commands, portable across projects.
- A **review loop** (`/forja`) that sweeps an existing codebase: discovers by execution flows,
  writes tests/repros first, fixes in isolated worktrees, verifies adversarially, opens PRs.
- A **build pipeline** (`/construye`) that grafts the same verification engine onto GitHub Spec Kit's
  spec-driven phases: acceptance-test-first implementation with generator ≠ evaluator.
- A **bootstrap** (`/galaxy-brain:setup`) that installs companions by reference — official installers,
  auto-detected, gracefully optional. No vendored third-party code, ever.

## What galaxy-brain is NOT (anti-goals)

These are permanent, not "later":

- **Not a toolbox.** No command packs, no persona armies, no 20 MCP servers. Every added tool must
  pay its context cost (research H9). Framework bloat is the #1 failure mode of this product category.
- **Not a swarm.** Subagents isolate context; they do not parallel-code. Multi-agent coding is a poor
  fit today (research H4) — we don't sell what doesn't work.
- **No auto-merge. Ever.** Not behind a flag, not with "high confidence". The human merges.
- **No vendoring.** Companions (GitNexus, context-mode, Spec Kit) are install links + detection,
  never copied code.
- **No vector memory.** File-based memory only (research H5).
- **Not a Spec Kit reimplementation.** Spec Kit is the spec pipeline; we plug verification into its
  extension points.

## Roadmap

| Version | Codename | Scope | Done when (objective gate) |
|---------|----------|-------|----------------------------|
| **v0.1** | smooth brain | Forge loop as installable plugin: `/forja`, 4 `loop-*` agents, `/galaxy-brain:setup`, docs (README, ARCHITECTURE, SCOPE) | Fresh machine → 2 install commands → `/forja` completes one full pass on a repo it has never seen, delivering a verified PR, with zero manual config |
| **v0.5** | big brain | Spec-driven build: `/construye` + Spec Kit bootstrap + `.specify/extensions.yml` hook wiring | One feature goes constitution→spec→plan→implement with the acceptance test written before the code and evaluator sign-off, on a clean sample repo |
| **v1.0** | galaxy brain | Full harness: critical invariants moved from prompts to **hooks**, with final enforcement outside the agent (branch protection / CI); file-based memory for loop insights; context protection integration | The never-auto-merge and full-suite invariants hold even if the skill prompts are deleted; loop survives a 100+ turn session without context exhaustion |
| **v2.0** | universe brain | TBD — decided from v1.0 field experience, not speculation | TBD |

Each release gate is the *stopping criterion* for polishing that version: when the gate passes, ship
and move on — further polish goes to the next version.

## Differentiation

The ecosystem scan lives in [docs/ecosystem-ideas.md](docs/ecosystem-ideas.md) — what neighboring
projects (adversarial-review, autonomous-dev, SuperClaude, claude-flow, BMAD, Spec Kit…) do well,
which ideas we adopt **with attribution**, and which patterns we deliberately reject. Summary:

- vs. **native `/code-review`**: we add adversarial cross-model verification, test-first repros and
  an auto-fix loop under never-auto-merge — review that *ships fixes*, not only findings.
- vs. **command/persona frameworks** (SuperClaude-style): they add surface area; we add verification
  depth. Minimal context footprint is a feature.
- vs. **swarm orchestrators** (claude-flow-style): deterministic phases beat open autonomy on
  real-code benchmarks (research H10); we optimize for verified output, not agent count.
- vs. **adversarial-review / autonomous-dev**: closest relatives, validated our thesis independently.
  We differentiate on portability (any repo, zero config), test-first sweeps, Spec Kit integration
  and the continuous loop cadence.
