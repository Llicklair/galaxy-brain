# galaxy-brain — Playbook: the working pipeline on any repo

How to actually work with galaxy-brain, from empty repo (or unknown brownfield) to a nightly
verified loop. Every phase reuses the same engine — deterministic gates, generator ≠ evaluator,
test-first, never auto-merge — entered through a different door.

Guiding correction that shapes this playbook: **documents that no gate reads are decoration**
(Spec Kit's own top criticism: specs "govern by convention"). Security and tech debt are therefore
not day-0 documents here — they are enforceable rules (constitution, CLAUDE.md, hooks) and
recurring forja lenses. A scalability doc for an empty repo is speculation; lens 6 sweeping every
night is surveillance.

## Phase 0 — Land: `/galaxy-brain:setup` (once per repo)

Detects and installs companions and stack oracles by reference — GitNexus (code graph), Spec Kit
(if you will build), context-mode, Playwright / `gh` CLI / mutation testing / schemathesis where
the stack warrants — and maps the repo's REAL gates (lint/typecheck/build/test). Everything else
works blind without this.

## Phase 1 — Idea → foundations (3 docs + 2 executable artifacts)

| Piece | What it is | Who reads it |
|---|---|---|
| README | what this is and why it exists | humans |
| ARCHITECTURE | how: design rules, each with its why | humans + the evaluator |
| SCOPE | vision, **anti-goals**, roadmap with objective release gates | humans (it stops scope creep) |
| **Constitution** (`/speckit-constitution`) | MUST-distillation of architecture + security — the law the evaluator enforces with REJECT | the evaluator, on every change |
| **CLAUDE.md** | the repo's red lines (protected zones, commit discipline) | every agent touching the repo |

Security lives as constitution MUST principles (enforceable) plus forja lens 2 (continuous).
Tech debt is not written down up front — it **emerges** in the forja inbox and ledger, where every
item carries a repro and a severity instead of rotting in a markdown file.

## Phase 2 — Build features: `/construye`

specify → clarify (**human gate**: you approve the spec; the loop never invents requirements) →
acceptance criteria in **EARS** (1 WHEN/SHALL clause = 1 acceptance test) → plan → tasks →
verified implement: acceptance test RED first (anchored with `scripts/evidence.js`), implementer,
evaluator on a different model, full suite, PR with evidence bundle. Your job: answer
clarifications, merge.

## Phase 3 — Review what exists: `/forja` (the nightly loop)

Code review is not a separate activity — it is `/loop forja` with the rotating lens:
1 correctness · **2 security** · 3 concurrency/idempotency · 4 error handling/edge cases ·
5 test-gaps · **6 performance/resources**. Finders → cross-model refutation → test-first repro →
fix in an isolated worktree → independent evaluator → PR with red→green evidence.
Point-in-time complement before a big release: Claude Code's native `/security-review`.

## Phase 4 — Incomplete features: `/speckit-converge`

Inside `/construye` brownfield: converge compares code vs spec **bound to the plan's file scope**,
appends gaps as Convergence phases (missing / partial / contradicts — delta style), and the
verified implement closes them. Loop implement → converge until "✅ Converged". Incompleteness
stops being a feeling and becomes a list with a closing criterion.

## Phase 5 — Tests: who writes them, with what

**Who**: `loop-tester`, always blind to the implementation (sees criteria, not fix code).
**With what** (detected, never imposed): the stack's suite (pytest/vitest/…) · **Playwright** for
E2E and visual regression (`toHaveScreenshot`) · **schemathesis** when an OpenAPI schema exists
(the spec is already an oracle) · property-based testing where the repo already uses it. Plus the
piece almost nobody has: **diff-scoped mutation testing at PR close** — the test of the tests,
catching always-green suites. Forja lens 5 hunts missing coverage continuously.

## Phase 6 — Understand and visualize the repo

**GitNexus** is the center: code graph, execution flows (`gitnexus-exploring` / `-debugging` /
`-impact-analysis` skills), blast-radius before touching anything, and repo **wiki generation**.
Complements: Claude Code's native LSP, context-mode so long sessions survive, and `/init` to seed
a CLAUDE.md where none exists.

## The cadence that ties it together (this is the real pipeline)

```
morning:  review inbox + PRs with evidence bundles (10–20 min) → YOU merge or reject
day:      /construye — new features (you: specs and clarifications)
night:    /loop forja — rotating lens over everything that exists
always:   hooks mechanically block auto-merge and test-gaming;
          the coverage map and ledger compound across passes
```

The human role reduces to the four decisions only a human should make: **the idea, the
clarifications, the inbox, and the merge**. Everything else runs under gates.
