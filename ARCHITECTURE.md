# galaxy-brain — Architecture

> Every rule here traces to evidence in [docs/research-report.md](docs/research-report.md) (H1–H11).
> If a change contradicts a rule, the change is wrong or the rule must be amended here first.

## Thesis

Most capability lives in the **model**, not the scaffold (H9: ~100-line scaffolds hit >74% SWE-bench Verified).
The one exception that measurably moves the needle: **deterministic verification + generator ≠ evaluator** (H1, H2).
Therefore galaxy-brain is not a toolbox. It is a **verification pipeline with judgment**:
deterministic oracles first, adversarial LLM evaluation second, context isolation throughout.

## The pipeline (core of everything)

```
                 ┌─────────────────────────────────────────────────┐
                 │              LOOP DRIVER (skill)                │
                 │   /forja (review)      /construye (build)       │
                 └──────┬──────────────────────────┬───────────────┘
                        │ discovers work           │ Spec Kit phases
                        ▼                          ▼ (constitution→spec→plan→tasks)
                 ┌────────────┐             ┌────────────┐
                 │ loop-finder│             │  implement │
                 │ (explorer) │             │  slot      │
                 └──────┬─────┘             └──────┬─────┘
                        ▼                          ▼
                 ┌────────────────────────────────────┐
                 │ loop-tester — writes the test FIRST│  ← spec-blind: sees criteria,
                 │ failing test = bug with repro      │    not the implementation
                 └──────┬─────────────────────────────┘
                        ▼
                 ┌────────────────────────────────────┐
                 │ loop-fixer — ONE fix, in worktree  │  ← commits to its branch, stops
                 └──────┬─────────────────────────────┘
                        ▼
                 ┌────────────────────────────────────┐
                 │ DETERMINISTIC GATES (no LLM)       │  ← lint · typecheck · build ·
                 │ project's real commands, detected  │    FULL test suite (no regression)
                 └──────┬─────────────────────────────┘
                        ▼
                 ┌────────────────────────────────────┐
                 │ loop-evaluator — DIFFERENT MODEL   │  ← assumes the change is BROKEN;
                 │ verdict: PASS | REJECT | BLOCKER   │    machine-parseable, no appeal
                 └──────┬─────────────────────────────┘
                        ▼
                 PR or local diff — the human merges. NEVER auto-merge.
```

## Layers

| Layer | Lives in | Role | Rule |
|-------|----------|------|------|
| **Loop drivers** | `skills/` (`forja`, `construye`) | Orchestration, cadence, delivery mode | Deterministic phases, not open autonomy (H10) |
| **Roles** | `agents/` (`loop-*`) | One job each, own context window | Main thread receives JSON/verdicts only, never raw stdout (H4) |
| **Gates** | detected per project | Deterministic verification before any LLM judgment | Read from CI/workflows/package scripts — never hardcoded (H1) |
| **State** | outside the target repo | Loop progress, per-lens coverage | The harness never dirties the project it works on |
| **Companions** | external installs | Code graph, context protection, spec pipeline | By reference, never vendored (see below) |

## Companions: by reference, never vendored

External tools are **install links that set themselves up**, not code copied into this repo.
Each companion ships as three things: a **detection**, an **official install command**, a **verification**.

| Companion | Detect | Install (official) | Gives the loops |
|-----------|--------|--------------------|-----------------|
| GitHub Spec Kit | `.specify/` exists | `uvx --from git+https://github.com/github/spec-kit.git specify init . --integration claude --script sh` | spec pipeline for `/construye` |
| GitNexus | `npx gitnexus status` | `npx gitnexus analyze` (+ MCP registration) | discovery by execution flows, impact analysis |
| context-mode | plugin installed | `/plugin` marketplace | context-window protection |
| Playwright (web repos) | `playwright.config.*` / `@playwright/test` | `npm init playwright@latest` | durable E2E oracle (`npx playwright test`) + local visual regression (`toHaveScreenshot`) |
| gh CLI | `gh auth status` | https://cli.github.com | CI verdict as oracle (`gh run watch` / `gh run view --log-failed`) |
| Mutation testing | Stryker / mutmut / cargo-mutants / pitest configs | each tool's official installer | diff-scoped test-QUALITY gate at batch close (kills "always-green" agent tests) |
| schemathesis | `openapi.{yaml,json}` / GraphQL schema | `pip install schemathesis` | auto property-tests FROM the API spec — the spec as executable oracle |

Verdicts and evidence for the July 2026 oracle additions: [docs/deep-scan-2026-07.md](docs/deep-scan-2026-07.md)
and [docs/oracles-report-2026-07.md](docs/oracles-report-2026-07.md).

Rules:
- **Degrade gracefully**: every loop works without its companions (forja falls back to file-tree
  discovery without GitNexus). Missing companion = reduced power, never a crash.
- **`/galaxy-brain:setup`** (`skills/setup/`) automates detect → install → verify for all of them.
- Replicating a companion's code into this repo is a REJECT in review. Version drift and
  double maintenance are exactly what by-reference avoids.

## Design rules (the law — evaluator enforces these)

1. **Generator ≠ evaluator, different model** — LLMs don't discriminate their own work better than
   they generate it (54/56 experiments, H2). Prefer a different model *family*: preference-leakage (H8).
2. **Deterministic feedback first** — lint/typecheck/build/test before any LLM verdict. LLMs repair
   excellently with deterministic feedback, judge poorly without it (H1).
3. **Test-first, spec-blind** — the test author sees acceptance criteria, not the implementation.
   A failing test is a bug with a repro; a passing test is coverage gained (H3).
4. **Full-suite gate, fix-iteration cap** — the complete suite must pass (no regression); capped
   fix iterations (default 2) so the loop can't grind a bad change into passing.
5. **Never auto-merge** — deliver as PR or local diff. The human decides. No exceptions, no flags.
6. **Subagents as context firewalls** — isolation is for *context*, not parallel coding
   ("most coding tasks are a poor fit for multi-agent", H4).
7. **Minimal, well-described tools** — no LSP/AST/vector stores unless they pay their context cost.
   Compete on the verification loop, not on tool count (H9).
8. **File-based memory, no vectors** — insights and decisions persist as files, recalled just-in-time (H5).
9. **Hooks over prompts for invariants** (v1.0 direction) — per-step prompt reliability compounds badly
   over multi-step pipelines; critical invariants belong in deterministic hooks (H11). And hooks are
   themselves bypassable: the *final* gate lives outside the agent — branch protection and CI make
   never-auto-merge a repository setting, not a promise (see ecosystem-ideas.md). First increment
   shipped: `hooks/verify-invariants.js` (PreToolUse) mechanically blocks PR merges and snapshot-baseline
   updates by agents, even if every skill prompt is deleted.
10. **Evidence bundle per delivery** — every PR/diff ships machine-checkable proof: the failing→passing
    test log, full-suite output, and the evaluator's verdict. "Verified" is an artifact, not a claim
    (pattern credited to Claude Code Harness, see ecosystem-ideas.md). Shipped as `scripts/evidence.js`:
    red→green chain with SHA-256-pinned test files — a test edited between red and green breaks the
    chain (the anti-gaming primitive), and `bundle` refuses incomplete or non-PASS chains.

## Repo layout

```
galaxy-brain/
├── .claude-plugin/
│   ├── plugin.json          # plugin manifest (version = release version)
│   └── marketplace.json     # this repo is its own marketplace
├── skills/
│   ├── forja/               # review loop driver
│   ├── construye/           # spec-driven build driver
│   └── setup/               # companion bootstrap (by-reference installs)
├── agents/                  # loop-finder / loop-tester / loop-fixer / loop-evaluator
├── hooks/
│   ├── hooks.json           # PreToolUse wiring (Bash|PowerShell)
│   └── verify-invariants.js # mechanical: no auto-merge, no agent snapshot updates (rule 9)
├── scripts/
│   ├── evidence.js          # red→green evidence bundle, hash-pinned tests (rule 10)
│   └── ears.js              # EARS→acceptance-test compiler: extract/scaffold/check 1:1 gate (rules 2, 3)
├── docs/
│   ├── research-report.md   # evidence base (H1–H11) — the "why" behind every rule
│   ├── ecosystem-ideas.md   # competitor scan: ideas adopted / rejected
│   ├── deep-scan-2026-07.md # second-round scan: oracles, MCPs, spec kits, build gaps
│   └── oracles-report-2026-07.md # per-tool oracle detail (integration, cost, sources)
├── ARCHITECTURE.md          # this file — the "how"
├── SCOPE.md                 # vision, roadmap, anti-goals — the "what"
└── CLAUDE.md                # rules for developing galaxy-brain itself
```

## Change protocol

The skills ARE the product — a SKILL.md edit is a behavior change, not a doc change.
Any change to `skills/` or `agents/` must: (1) state which design rule motivates it,
(2) be exercised on a real repo before merging, (3) bump `plugin.json` version on release.
