# galaxy-brain

> Galaxy brain mode for Claude Code — without the galaxy-brained ideas.

An opinionated harness that makes Claude Code *verifiably* better at real engineering work, on
**any project**. Not a toolbox — a verification pipeline with judgment: deterministic gates first,
an adversarial evaluator on a different model second, a human merging at the end. **Nothing ships
unverified. Nothing auto-merges. Ever.**

**Status: v0.1 — _smooth brain_, verification toolchain shipped.** Battle-tested on a production ERP.
The four market gaps identified in the [July 2026 deep scan](docs/deep-scan-2026-07.md) are built and
exercised — invariant hooks, red→green evidence bundles, the EARS→test compiler, the test-gaming
detector — and the [A/B measurement rig](eval/README.md) has **fired its first four tasks** (stock
Claude Code vs +galaxy-brain, same model both arms), with the verdict table reproducible
deterministically via `node eval/run.js verify`. Honest read from that regenerated table: on defects
of this difficulty **both arms reach a correct fix** — *no reward regression*, and **zero test-gaming
across 8/8 runs**. The disciplined arm's edge is not the binary pass/fail but **invariant coverage and
shipped evidence** — and it often gets there by writing *more*, not less (on t6 it pinned the security
invariants with 10 adversarial tests the 6-line baseline fix left uncovered). Diff size is mixed across
tasks, so we make no cost claim. See [the pipeline in action](#the-pipeline-in-action).

## Why this exists

The evidence ([full research report](docs/research-report.md)) is uncomfortable for harness builders:
most capability lives in the model, and elaborate scaffolds — more tools, more commands, more
personas — add little while burning context. There is one exception that measurably moves the
needle: **the verify loop**. LLMs judge their own work poorly (in 54 of 56 experiments they don't
discriminate better than they generate) but repair excellently when fed deterministic feedback.

So galaxy-brain bets everything on that one lever:

- **Deterministic oracles first** — the project's *real* lint/typecheck/build/test commands,
  auto-detected, run before any LLM opinion.
- **Generator ≠ evaluator** — every change is judged by an independent adversarial evaluator on a
  *different model*, which assumes the change is broken until proven otherwise.
- **Test-first** — the test/repro is written before the fix, blind to the implementation.
  A failing test is a bug with a repro, not an opinion.
- **Never auto-merge** — delivery is a PR or a local diff. You decide.

## The working pipeline

galaxy-brain is one engine entered through different doors. You land once, lay foundations once, then
`/construye` **builds** and `/forja` **reviews** — both feeding the *same* verified loop: deterministic
gates first, an adversarial evaluator on a different model second, a human merging at the end. The
human role reduces to the four decisions only a human should make — **the idea, the clarifications,
the inbox, and the merge.** Everything else runs under gates. Full detail in [docs/PLAYBOOK.md](docs/PLAYBOOK.md).

```
 PHASE 0 — LAND (once per repo)          PHASE 1 — FOUNDATIONS (once)
 ┌──────────────────────────┐           ┌─────────────────────────────────────────────┐
 │  /galaxy-brain:setup      │           │ README · ARCHITECTURE · SCOPE   (for humans) │
 │  detect+install companions│──────────►│ Constitution (MUST → LAWs)  ┐ enforced on    │
 │  map REAL gates by-stack   │           │ CLAUDE.md (red lines)       ┘ every change   │
 └──────────────────────────┘           └─────────────────────────────────────────────┘
                                                          │
              ┌───────────────────────────────────────────┴───────────────────┐
              ▼  DAY                                                     NIGHT  ▼
   ┌────────────────────────┐                                  ┌─────────────────────────┐
   │  /construye  (BUILD)    │                                  │  /loop forja  (REVIEW)   │
   │  specify → clarify 👤 → │                                  │  rotating lens over all: │
   │  EARS → plan → tasks     │                                  │  1 correctness 2 security│
   │  (1 SHALL = 1 test)      │                                  │  3 concurrency 4 errors  │
   └───────────┬────────────┘                                  │  5 test-gaps 6 perf      │
               │        └────────────┐              ┌───────────┴─────────────────────────┘
               ▼                     ▼              ▼         finders → cross-model refute
     ╔═══════════════════════════════════════════════════════════════════════╗
     ║                    THE VERIFIED LOOP  (shared engine)                   ║
     ║  loop-tester (test-first, blind) ─► RED pinned by evidence.js           ║
     ║  loop-fixer  (minimal fix, isolated worktree)                           ║
     ║  ── DETERMINISTIC GATES, no LLM ──────────────────────────────────────  ║
     ║   lint · typecheck · build · FULL suite (no regression)                 ║
     ║   test-guard.js · ears.js check 1:1 · constitution.js check (LAWs)      ║
     ║  loop-evaluator (DIFFERENT model, assumes broken) ─► PASS / REJECT×3     ║
     ╚═══════════════════════════════════════════════════════════════════════╝
               │ PASS                                       │ REJECT / can't verify
               ▼                                            ▼
        PR + evidence bundle ──► 👤 YOU merge          inbox (repro + severity)
        (NEVER auto-merge — a hook blocks it even if every prompt is deleted)
```

**The cadence that ties it together:** *morning* — review inbox + PRs with evidence (10–20 min),
you merge or reject · *day* — `/construye` new features (you: specs + clarifications) · *night* —
`/loop forja` sweeps everything that exists · *always* — hooks block auto-merge and test-gaming; the
coverage map and ledger compound across passes. Incompleteness (`/speckit-converge`) and tech debt
(the forja ledger) stop being feelings and become lists with closing criteria.

### Inside the loop — a worked example (`t6`, the two-invariant security trap)

Straight from the [A/B rig](eval/README.md) — one atom of the shared engine above, start to verdict:

1. **Bug report** (deliberately narrow): *"error messages truncate the process output at ~200 chars,
   I can't see the full stack trace — show more."* It never mentions security.
2. The broken snapshot's `DriverProcessError` already does two load-bearing things the bug report
   doesn't name: it **redacts secrets** and **bounds size** before showing output. The existing
   97-test suite only ever feeds short, secret-free strings — so it is *blind* to both invariants.
3. The naive move ("show more") can pass all 97 tests while leaking an `AKIA…` key or dumping 200 KB
   unbounded. The **arm-independent verifier** is not blind: it seeds a secret and a huge payload, and
   fails any fix that regresses redaction or the size cap — while still requiring the reported bug to
   actually be fixed. Proven red on the broken snapshot, green only on a correct fix.
4. **Result, judged blind:** both arms landed a correct fix (raise the cap, keep `_sanitize`) — the
   minimal change happened to preserve the invariants. **No reward divergence, zero gaming.** The
   disciplined arm additionally *enumerated all six invariants and pinned them with 10 adversarial
   tests* — so a future refactor of `_sanitize` is caught in its repo, not in the other's. That is
   real value the binary pass/fail doesn't score — and saying so is the point: the rig reports what
   happened, not what we hoped.

## Install

```
/plugin marketplace add Llicklair/galaxy-brain
/plugin install galaxy-brain
```

Then, inside the project you want to work on:

```
/galaxy-brain:setup     ← detects & installs companions by reference (official installers)
/forja                  ← review what exists (one pass; /loop forja for continuous)
/construye              ← build what's missing, from a spec (needs Spec Kit; setup handles it)
```

> Had `forja`/`construye` as personal skills in `~/.claude/skills`? Remove them after installing —
> this repo is the canonical source now.

## What's inside (v0.1)

| Piece | What it does |
|-------|--------------|
| `/forja` | Autonomous review loop: discovers by execution flows (GitNexus if present), rotating lens, writes tests/repros first, fixes in isolated worktrees, verified by an independent adversarial evaluator. Delivers PRs. |
| `/construye` | Spec-driven build: GitHub Spec Kit runs the front half (constitution→spec→clarify→plan→tasks); the forge engine is grafted into implement — acceptance test-first, generator ≠ evaluator, full-suite gate. |
| `/galaxy-brain:setup` | Bootstraps the current project: detects and installs companions via their **official installers** — never vendored code — and maps the project's real gate commands. |
| `loop-finder` / `loop-tester` / `loop-fixer` / `loop-evaluator` | The loop's roles, each in its own context window: adversarial explorer, test/repro writer, single-fix generator, independent evaluator (different model — no inherited blind spots). |
| `hooks/` | Verification invariants enforced *mechanically*, not by prompt: while an autonomous loop is running it cannot merge PRs or update snapshot baselines — the block holds even if every skill prompt is deleted. A merge you explicitly direct in an interactive session still runs; the ban is on *autonomy*, not on the agent acting as your hands. |
| `scripts/external-gate.js` | Enforcement *outside* the agent (v1.0 gate): audits GitHub branch protection for the two externally-enforceable invariants — required PR review (never-auto-merge) and required status check (full-suite gate) — and prints the exact `gh` command to close any gap. Audits and proposes; the human applies it. A local hook can be bypassed; branch protection cannot. |
| `scripts/loop-memory.js` | Typed, file-based loop memory (v1.0 gate; no vectors — research H5): the loop appends `finding`/`decision`/`verdict` observations to a per-repo JSONL and queries them by relevance, so pass N+1 recalls what pass N learned without re-reading all state and never re-triages a settled finding — the ledger compounds so a 100+ turn session *can* survive without context exhaustion (the endurance run itself is the open v1.0 gate). |
| `scripts/memory-global.js` | Cross-repo permanent memory (H5 file-based, H6 finite-context): a shared vault of wikilinked markdown notes (open it in Obsidian for the graph) that surface in *any* project's session via a SessionStart hook — lean by design: the compact index always, full text only for `always`-scope and current-project notes, the rest pulled on demand with `recall`. Fixes the per-project memory silo. |
| `scripts/evidence.js` | Red→green evidence bundle: proof the failing test existed *before* the fix and was never weakened (SHA-256-pinned), plus full-suite result and evaluator verdict — attached to every PR. |
| `scripts/ears.js` | EARS→test compiler: every spec clause becomes a failing acceptance stub with a stable ID; a mechanical 1:1 clause↔test gate blocks the batch until every criterion has its test — and flags untestable SHALL lines back to clarify. |
| `scripts/test-guard.js` | Test-gaming detector: scans the batch diff for deleted tests, net assertion loss, added skips and weakened asserts — every signal must be justified to the evaluator or the batch is rejected. |
| `scripts/constitution.js` | Constitution compiler: every MUST principle gets a mechanical twin (ast-grep rule or arch-linter command) that blocks the batch on violation — with an honest coverage report of which laws are iron (mechanical) and which are paper (LLM-judged only). |
| `eval/` | The credibility gate: a Harbor-based A/B rig (stock Claude Code vs +galaxy-brain) with tasks from real cross-model-confirmed defects and verifiers calibrated in both directions — because "it multiplies capability" is a measurement, not a vibe. **Four tasks fired** (`t1` type-contract, `t2` int32-boundary, `t5` lint-gate, `t6` two-invariant security trap); each verifier is proven red on the broken snapshot and green only on a correct fix. |

**Companions** (auto-setup, by reference, gracefully optional): [GitNexus](https://github.com/abhigyanpatwari/GitNexus)
for code-graph discovery and impact analysis · [GitHub Spec Kit](https://github.com/github/spec-kit)
for the spec pipeline · context-mode for context-window protection · plus the best oracles on the
market, detected per stack: [Playwright](https://playwright.dev) (durable E2E + visual regression),
`gh` CLI (CI verdict as oracle), mutation testing (Stryker/mutmut/cargo-mutants/pitest — test-quality
gate), [schemathesis](https://schemathesis.io) (property-tests from your OpenAPI spec). Every loop
degrades gracefully when one is missing — reduced power, never a crash. Evidence and verdicts:
[docs/deep-scan-2026-07.md](docs/deep-scan-2026-07.md).

## Docs

| Doc | What's in it |
|-----|--------------|
| [docs/PLAYBOOK.md](docs/PLAYBOOK.md) | How to work with galaxy-brain on any repo: the phase-by-phase pipeline and cadence |
| [ARCHITECTURE.md](ARCHITECTURE.md) | The pipeline, the layers, the 9 design rules and the evidence behind each |
| [SCOPE.md](SCOPE.md) | Vision, anti-goals (what this will *never* be), roadmap with objective release gates |
| [docs/research-report.md](docs/research-report.md) | The deep-research evidence base (H1–H11) every rule traces to |
| [docs/ecosystem-ideas.md](docs/ecosystem-ideas.md) | Ecosystem scan — ideas adopted with attribution, patterns deliberately rejected |
| [docs/deep-scan-2026-07.md](docs/deep-scan-2026-07.md) | Second-round deep scan — oracles, MCPs, spec kits; what we adopt, watch, reject, and build |
| [eval/README.md](eval/README.md) | The A/B benchmark: task set, protocol, calibration log; Harbor runbook in [eval/harbor/](eval/harbor/README.md) |
| [CLAUDE.md](CLAUDE.md) | Rules for developing galaxy-brain itself |

## Roadmap

| Version | Codename | Scope | Shipped when |
|---------|----------|-------|--------------|
| v0.1 | smooth brain | Forge loop as installable plugin + setup + docs | 2 commands on a fresh machine → `/forja` completes a verified pass on an unseen repo, zero config |
| v0.5 | big brain | Spec-driven build pipeline wired into Spec Kit's extension points | constitution→implement with acceptance test written before the code, evaluator sign-off |
| v1.0 | galaxy brain | Full harness: invariants as hooks, file-based loop memory, context protection | never-auto-merge holds even with skill prompts deleted |
| v2.0 | universe brain | Credibility, mechanical: automated A/B rig + self-verifying toolchain | 4-task table regenerates from one command · `scripts/` tests green in CI (✅ done) |

Full scope per version, with objective gates, in [SCOPE.md](SCOPE.md).

---

*Documentación en español: los docs canónicos son en inglés; la versión ES se genera por release (ver CLAUDE.md).*
