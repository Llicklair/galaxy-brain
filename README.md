# galaxy-brain

> Galaxy brain mode for Claude Code — without the galaxy-brained ideas.

An opinionated harness that makes Claude Code *verifiably* better at real engineering work, on
**any project**. Not a toolbox — a verification pipeline with judgment: deterministic gates first,
an adversarial evaluator on a different model second, a human merging at the end. **Nothing ships
unverified. Nothing auto-merges. Ever.**

**Status: v0.1 — _smooth brain_ (packaging).** Battle-tested on a production ERP; docs and polish in progress.

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
| `hooks/` | Verification invariants enforced *mechanically*, not by prompt: agents cannot merge PRs or update snapshot baselines — the block holds even if every skill prompt is deleted. |
| `scripts/evidence.js` | Red→green evidence bundle: proof the failing test existed *before* the fix and was never weakened (SHA-256-pinned), plus full-suite result and evaluator verdict — attached to every PR. |

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
| [CLAUDE.md](CLAUDE.md) | Rules for developing galaxy-brain itself |

## Roadmap

| Version | Codename | Scope | Shipped when |
|---------|----------|-------|--------------|
| v0.1 | smooth brain | Forge loop as installable plugin + setup + docs | 2 commands on a fresh machine → `/forja` completes a verified pass on an unseen repo, zero config |
| v0.5 | big brain | Spec-driven build pipeline wired into Spec Kit's extension points | constitution→implement with acceptance test written before the code, evaluator sign-off |
| v1.0 | galaxy brain | Full harness: invariants as hooks, file-based loop memory, context protection | never-auto-merge holds even with skill prompts deleted |
| v2.0 | universe brain | TBD — decided from v1.0 field experience | TBD |

Full scope per version, with objective gates, in [SCOPE.md](SCOPE.md).

---

*Documentación en español: los docs canónicos son en inglés; la versión ES se genera por release (ver CLAUDE.md).*
