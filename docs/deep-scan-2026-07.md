# Deep scan — July 2026: oracles, MCPs, spec kits, and what to build

Second-round ecosystem research (follow-up to [ecosystem-ideas.md](ecosystem-ideas.md)), run as four
parallel research passes: verification oracles, MCP servers, spec-driven kits, and gap analysis.
Every verdict below traces to H1–H11 in [research-report.md](research-report.md) or brings new
cited evidence. Full per-tool oracle detail (integration commands, costs, sources) in
[oracles-report-2026-07.md](oracles-report-2026-07.md).

**Headline: the ecosystem converged on galaxy-brain's thesis during 2026.** Microsoft steers agents
from Playwright MCP to CLI+skills ([README](https://github.com/microsoft/playwright-mcp)); Anthropic
publishes [code-execution-over-MCP guidance](https://www.anthropic.com/engineering/advanced-tool-use)
(98.7% token cut); practitioner consensus is "verification capacity, not generation, is the
bottleneck" ([HN roundup](https://www.developersdigest.tech/blog/what-hacker-news-gets-right-about-ai-coding-agents-2026));
and a fresh paper — [Proof-or-Stop, arXiv 2607.14890](https://arxiv.org/abs/2607.14890) — shows the
*gate*, not the reviewer, drives the gain ("zero false-DONE"). Our niche (trust tooling) is validated
and still mostly empty.

## ADOPT — by reference (detection + official installer + verify)

| What | Role in the loop | Evidence / integration |
|---|---|---|
| **Playwright committed test files** (`npx playwright test`) | THE durable browser oracle for web repos (H1). Deterministic exit code, replayable, reviewable in PR. | Official [Test Agents](https://playwright.dev/docs/test-agents) (`npx playwright init-agents --loop=claude`). Detect `playwright.config.*`; install `npm init playwright@latest`. Caveat: the **healer** agent can weaken assertions to go green — healer output must pass our evaluator (H2 applies to test repair too). |
| **Playwright MCP — evaluator-only** | Grounding instrument (live selectors/assertions) + the evaluator's eyes for acceptance checks. Never resident in the main loop. | Measured: MCP-driven run ≈ [114K tokens vs 27K CLI](https://scrolltest.medium.com/playwright-mcp-burns-114k-tokens-per-test-the-new-cli-uses-27k-heres-when-to-use-each-65dabeaac7a0); one screenshot [232K tokens](https://medium.com/@7003425114klp/one-screenshot-232-000-tokens-0b37783438c7). Rules: snapshots not screenshots; every session ends by emitting a committed spec. |
| **Visual regression via `toHaveScreenshot()`** | Pixel-diff oracle, local/free, baselines in repo. | Built into Playwright. Hook must forbid agent-run `--update-snapshots` (same hazard as snapshot `-u`). Rejected: BackstopJS (duplicate), Lost Pixel (sunsetting), Percy/Chromatic (SaaS accounts). |
| **CI verdict via `gh` CLI** | Highest-value forja addition: agent opens PR → `gh run watch` → `gh run view --log-failed` → fix. CI as external oracle (H1 + H3). | [Field pattern](https://blink.new/blog/claude-code-github-actions). Detect `gh auth status`. Mandate `gh run watch`, never polling loops ([rate-limit issue](https://github.com/anthropics/claude-code/issues/65985)). GitHub MCP rejected: [~55K tokens / 93 schemas](https://getunblocked.com/blog/github-mcp-token-cost/). |
| **Mutation testing, diff-scoped per PR** | The test-QUALITY oracle — counters "perpetually green" agent tests and is the anti-gaming measure (H3, H8). | StrykerJS `--incremental` (1–5 min/PR), cargo-mutants `--in-diff`, mutmut `--CI`, pitest history. Evidence: Google Mutagenesis (17M mutants, 24K devs), Meta 73% acceptance ([guide](https://www.augmentcode.com/guides/mutation-testing-ai-generated-code)). Per-PR only, never inner-loop; surviving mutants = next-iteration prompt input. |
| **Fast static gates when configured** | Pre-suite gates: Ruff, Biome, pyright, Semgrep (`semgrep ci`, ~10s). | Detect configs at runtime (rule 4). CodeQL rejected as loop gate (15–45 min builds; fine as nightly CI). Watch Astral's `ty` until stable. |
| **ast-grep — dual use** | (a) repo gate when `sgconfig.yml` present; (b) **self-enforcement**: encode our own invariants ("no auto-merge") as mechanical scan rules. | [LLM-first tooling](https://ast-grep.github.io/blog/more-llm-support.html); backed by [Deterministic Control Plane, arXiv 2606.26924](https://arxiv.org/html/2606.26924v1). |
| **EARS notation for acceptance criteria** | /construye: every criterion written as `WHEN [trigger] THE SYSTEM SHALL [response]` → maps 1:1 to one acceptance test. Public notation (Rolls-Royce origin), zero vendoring. | [Fowler/Böckeler](https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html), [EARS guide](https://kiro.directory/tips/ears-format). Kiro itself rejected (closed AWS IDE; auto-firing hooks near auto-merge territory). |
| **OpenSpec-style delta specs** | /speckit-converge brownfield: spec the *change* (ADDED/MODIFIED/REMOVED), not the world. | [OpenSpec](https://github.com/Fission-AI/OpenSpec) (~54k stars). Adopt the concept; keep Spec Kit as the horse (2x adoption, GitHub-backed, extension channel). |
| **schemathesis when OpenAPI detected** | The spec that already IS an executable oracle: auto property-tests from `openapi.yaml`. | [Used by Netflix/SAP/IBM](https://schemathesis.io/). Detect schema file at runtime; conditional gate. |
| **Cross-vendor evaluator via vendor CLIs** | H2 maximized: evaluate on a different *vendor* (Codex/Gemini CLI), detect → official installer → shell out. No router to build. | [gemini-plugin-cc](https://github.com/sakibsadmanshajib/gemini-plugin-cc), [orchestration guide](https://halallens.no/en/blog/agentic-coding-in-2026-the-complete-guide-to-plugins-multi-model-orchestration-and-ai-agent-teams). |
| **Harbor for measuring ourselves** | A/B galaxy-brain on/off against custom tasks with custom verifiers — our credibility gate. | [Harbor](https://harbor-framework-harbor.mintlify.app/introduction) (terminal-bench team). |

## WATCH

- **Chrome DevTools MCP** — richest debug surface (perf traces, network, console); diagnostic, not an
  oracle; parallel agents fight over the browser. Evaluator-only on frontend repos if at all;
  Claude Code's native sandboxed browser (v2.1.202+) covers part of it.
- **Sentry MCP** — production errors as forja discovery input; only when `SENTRY_DSN` present. Its own
  Seer autofix merge rate (41–46%) empirically validates never-auto-merge.
- **Tessl** — spec-as-source engine still private beta after ~9 months; MDD-repeat risk
  ([Böckeler](https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html)).
- **Property-based testing** — encourage when Hypothesis/fast-check/proptest already in repo; no gate
  (LLM-written properties "frequently trivial or incorrect", [survey](https://arxiv.org/pdf/2505.23549)).
- **Pact / snapshot testing** — run if already present; snapshot `-u` is an evaluator-approval event.
- **Spec Kit "spec-driven testing" roadmap item** — the one upstream move that could overlap us.
- **GSD** (61k stars) — closest competitor philosophically (fresh-context verifier agents) but no
  enforced cross-model generator≠evaluator. Watch as competitor, compose don't adopt.

## REJECT

Playwright MCP as a general tool (context burn; stale-snapshot hallucinations), GitHub MCP,
Serena/LSP MCPs (native LSP + GitNexus cover it; 4x cost on simple retrieval), database MCPs
(same gate achievable via CLI in throwaway container), browser-use/agent-browser (autonomy, not
verification), Kiro-the-tool, BMAD (re-confirmed), CodeQL-as-loop-gate, building a model router,
SaaS visual regression.

## BUILD — the empty niches (ranked by differentiation × feasibility)

1. **Verification-invariant hook pack** (v1.0 roadmap, now evidence-backed). PreToolUse/Stop hooks
   that *mechanically* block: auto-merge, weakening a test after it went red, `--update-snapshots`,
   PR without evaluator sign-off. PreToolUse fires before permission checks, even under
   `--dangerously-skip-permissions`. Prior art to credit: [TDD Guard](https://github.com/nizos/tdd-guard)
   (blocks implementation without failing test); security packs exist, **verification packs don't**.
   [Proof-or-Stop's ablation](https://arxiv.org/abs/2607.14890): the gate drives the gain.
2. **Red→green evidence bundle** — hash-bound proof that the failing test existed before the fix +
   full-suite result + evaluator verdict, attached to every PR, signed via
   [GitHub artifact attestations](https://docs.github.com/en/actions/concepts/security/artifact-attestations);
   interoperable with [Agent-Gate](https://github.com/sjh9714/Agent-Gate) (CI-side). Nobody captures
   this from inside the harness. Turns "verified" from a claim into an artifact.
3. **Test-gaming detector** — test-diff heuristics (deleted asserts, weakened comparisons,
   special-casing) + mutation-on-changed-tests + cross-vendor judge. METR: frontier agents
   reward-hack in >30% of runs; [EvilGenie](https://arxiv.org/abs/2511.21654) shows LLM judges beat
   held-out tests at detection. Research-rich, tool-empty.
4. **EARS→failing-acceptance-test compiler** (/construye's holy grail). No shipping general-purpose
   tool compiles spec criteria → failing acceptance tests before implement (Tessl not GA, Kiro
   closed, CodeMySpec Elixir-only). One EARS clause = one committed failing test, blind to the
   implementation. Distribute as a **Spec Kit community extension** (70+ exist, [catalog](https://github.github.io/spec-kit/community/extensions.html))
   for reach.

## Platform redundancy check (don't build what Anthropic shipped)

2026 native: agent teams (Feb), native LSP (Dec 2025, maturing), sandboxed Bash, in-app sandboxed
browser (July, v2.1.202+), MCP Tool Search (~95% startup-token cut — softens but doesn't void the
schema-cost argument). None of it covers the four BUILD items above.
