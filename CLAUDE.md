# galaxy-brain — Project Rules

Rules for developing galaxy-brain itself. The product's design law lives in [ARCHITECTURE.md](ARCHITECTURE.md);
vision and anti-goals in [SCOPE.md](SCOPE.md); evidence in [docs/research-report.md](docs/research-report.md).

## Core principles

- **Simplicity first.** Smallest change that works. This harness competes on verification depth,
  not surface area — every addition must justify its context cost.
- **Evidence over folklore.** New features cite a finding (H1–H11) or bring new evidence to
  `docs/`. "Other frameworks do it" is not a reason (see anti-goals in SCOPE.md).
- **The skills ARE the product.** A SKILL.md or agent .md edit is a *behavior change*: treat it like
  code, not documentation. Exercise it on a real repo before committing.
- **Inspiration with attribution.** Ideas from the ecosystem are adopted openly and credited in
  `docs/ecosystem-ideas.md` — we differentiate, we don't imitate.

## Hard rules (REJECT in review if violated)

1. **The autonomous loops never merge** — forja/construye deliver a PR and stop; while a pass runs
   they set a loop-active marker and `hooks/verify-invariants.js` blocks any merge. What is absolute,
   no exceptions: no loop, skill, or agent merges *on its own*. A merge a human explicitly directs in
   an interactive session is a human decision, not auto-merge — that is allowed (owner decision, 2026-07).
2. **Generator ≠ evaluator** — verification always runs on a different model than generation.
3. **No vendoring** — external tools (GitNexus, context-mode, Spec Kit) integrate by reference:
   detection + official installer + verification. Copying their code here is forbidden.
4. **Nothing project-specific** — skills must work on any repo. Hardcoded paths, stacks, or gate
   commands are bugs; everything is detected at runtime.
5. **Canonical source is THIS repo** — skills/agents are edited here and installed via the plugin,
   never edited in `~/.claude/` copies.

## Workflow

- Before touching `skills/` or `agents/`: state which ARCHITECTURE design rule motivates the change.
- Before committing: `claude plugin validate .` must pass clean.
- On release: bump `version` in `.claude-plugin/plugin.json`; the release is done when its
  SCOPE.md gate passes — then stop polishing and move to the next version.
- Docs are bilingual-ready: English is canonical; Spanish mirrors are generated per release, not per commit.

## Commit discipline

- Format: `type: short description` (`feat`, `fix`, `refactor`, `docs`, `chore`).
- One logical change per commit. Skill behavior changes and doc changes commit separately.
