# galaxy-brain

> Galaxy brain mode for Claude Code — without the galaxy-brained ideas.

An opinionated harness that makes Claude Code *verifiably* better at real engineering work. Not a toolbox — a pipeline with judgment: the right tool activates at the right phase, and everything ships through adversarial verification (generator ≠ evaluator, test-first, full-suite gates, never auto-merge).

**Status: v0.1 — _smooth brain_ (packaging).** The forge loop and the spec-driven build are packaged as a Claude Code plugin. Battle-tested on a production ERP; docs and polish in progress.

## Install

```
/plugin marketplace add <path-or-github-url-to-this-repo>
/plugin install galaxy-brain
```

> If you had `forja`/`construye` as personal skills in `~/.claude/skills`, remove them after installing to avoid duplicates.

## What's inside (v0.1)

| Piece | What it does |
|-------|--------------|
| `/forja` | Autonomous review loop: discovers by execution flows (GitNexus if present), rotating lens, writes tests/repros first, fixes in isolated worktrees, verified by an independent adversarial evaluator. Never auto-merge. |
| `/construye` | Spec-driven build: GitHub Spec Kit for the front half (constitution→spec→clarify→plan→tasks), forge engine grafted into implement (acceptance test-first, generator ≠ evaluator, full-suite gate). Bootstraps Spec Kit itself if missing. |
| `loop-finder` / `loop-tester` / `loop-fixer` / `loop-evaluator` | The loop's agents: adversarial explorer, test/repro writer, single-fix generator, independent evaluator (different model — no inherited blind spots). |

**Recommended companions** (not bundled): [GitNexus](https://github.com/gitnexus) for code-graph impact analysis, context-mode for context-window protection. The loops detect and use them when present.

## Roadmap

| Version | Codename | Scope |
|---------|----------|-------|
| v0.1 | smooth brain | Forge loop: autonomous review with adversarial evaluator, packaged as a Claude Code plugin |
| v0.5 | big brain | Spec-driven build pipeline |
| v1.0 | galaxy brain | Full harness: routing, memory, context protection |
| v2.0 | universe brain | TBD |

---

*Proyecto en desarrollo. La documentación bilingüe (ES/EN) llegará con la v0.1.*
