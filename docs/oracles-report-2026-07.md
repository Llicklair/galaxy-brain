# Deterministic Verification Oracles Beyond the Unit-Test Suite
Research report for galaxy-brain — July 2026. Each tool: what it is, evidence with coding agents, by-reference integration, cost, verdict.

---

## 1. Browser / E2E verification (priority topic)

### Playwright test framework + generated committed test files — **ADOPT**
- **What**: Cross-browser test runner (`@playwright/test`); tests are committed `.spec.ts` files run with `npx playwright test`, deterministic exit codes.
- **Evidence**: Playwright now ships **official Test Agents** — planner (explores app, writes Markdown plan), generator (turns plan into spec files, verifying selectors/assertions live), healer (runs suite, repairs failures). Installed per-harness with `npx playwright init-agents --loop=claude` (also vscode/codex/opencode). https://playwright.dev/docs/test-agents . Practitioner reports confirm the pattern works end-to-end with Claude Code: https://dev.to/debs_obrien/letting-playwright-mcp-explore-your-site-and-write-your-tests-mf1 , https://www.awesome-testing.com/2025/10/playwright-agents , https://shipyard.build/blog/test-first-development-playwright-mcp/ .
- **By reference**: detect `playwright.config.{ts,js}` or `@playwright/test` in package.json; official installer `npm init playwright@latest`; verify `npx playwright --version` + browsers via `npx playwright install --with-deps`.
- **Cost**: zero context cost at run time (it's a shell command); suite runtime minutes-scale; browser download ~400MB one-time.
- **Verdict**: **ADOPT** — this is the durable browser oracle. Caveat for galaxy-brain: the **healer** agent "repairs" failing tests, which can weaken assertions to make red go green — healer output must pass the adversarial evaluator (generator≠evaluator applies to test repair too).

### Playwright MCP server (`@playwright/mcp`, Microsoft) — **ADOPT, constrained to the evaluator phase**
- **What**: Official MCP server giving the agent live browser control via the accessibility tree (semantic element refs, not pixels). https://playwright.dev/mcp/introduction , https://github.com/microsoft/playwright-mcp . Official Claude plugin exists: https://claude.com/plugins/playwright .
- **Evidence it verifies agent UI work**: standard 2026 workflow is "point Claude at localhost, ask it to verify the change by driving the real page" — https://www.builder.io/blog/playwright-mcp-server-claude-code , https://testquality.com/claude-code-playwright-mcp-ai-test-automation/ . Anthropic's own best-practices doc frames it as closing the pass/fail loop, and warns screenshots are token-expensive — https://code.claude.com/docs/en/best-practices .
- **Interactive MCP vs committed test files**: the consensus split:
  - MCP = *exploration and grounding*: validate each step against the live app before writing the corresponding test line (prevents hallucinated selectors) — https://dev.to/yerac/from-acceptance-criteria-to-playwright-tests-with-mcp-4ka6 .
  - Committed spec files = *the durable oracle*: replayable, deterministic, zero marginal context, reviewable in the PR. Generated specs must then pass the repo's formatter, typechecker and `npx playwright test`.
  - Practitioners explicitly warn that letting one agent discover behavior, define expectations AND validate them "collapses intent and verification into a single feedback loop… like marking your own homework" — https://shipyard.build/blog/test-first-development-playwright-mcp/ (this is galaxy-brain's generator≠evaluator rule, independently rediscovered).
- **Context cost (measured, 2026)**: a full MCP-driven test run ≈ **114K tokens vs ~27K** for a CLI/skill-based flow — https://scrolltest.medium.com/playwright-mcp-burns-114k-tokens-per-test-the-new-cli-uses-27k-heres-when-to-use-each-65dabeaac7a0 . Snapshots range ~3.8K tokens (simple login form) to **10–50K per snapshot** on enterprise pages, and accumulate un-deduped across turns — https://provar.com/blog/thought-leadership/the-114k-token-problem-why-playwright-mcp-burns-your-ai-coding-agents-control-on-salesforce/ . A single full-page screenshot has been measured at **232K tokens** — https://medium.com/@7003425114klp/one-screenshot-232-000-tokens-0b37783438c7 . Open upstream issue to omit snapshots: https://github.com/microsoft/playwright-mcp/issues/1216 .
- **By reference**: `claude mcp add playwright npx @playwright/mcp@latest` (or the official plugin); detect with `claude mcp list`.
- **Verdict**: **ADOPT with hard constraints**: (a) enable only inside the verification/evaluator subagent, never resident in the main loop; (b) accessibility snapshots, screenshots only for final visual confirmation; (c) every MCP session must end by emitting/updating a committed Playwright spec so the knowledge survives the session. Best practice for a verification harness: **generated committed test files are the oracle; MCP is the grounding instrument used to write them and the evaluator's eyes for acceptance checks.**

### Chrome DevTools MCP (Google) — **WATCH** (adopt only as the perf/debug alternative)
- **What**: Official Google MCP server exposing DevTools to agents: 26+ tools — input (10), navigation (6), console, network waterfalls, screenshots/snapshots, `performance_start_trace`, Lighthouse-style audits, memory. https://github.com/ChromeDevTools/chrome-devtools-mcp (47.5K stars), https://developer.chrome.com/blog/chrome-devtools-mcp .
- **Evidence**: detailed practitioner comparison (July 2026): models use its tool surface competently; richest debugging depth; but **parallel agents fight over browser control** — centralize browser verification into one orchestrator/review pass — https://www.huuhka.net/browser-verification-for-coding-agents-chrome-devtools-mcp-vs-agent-browser/ . Perf-trace-driven optimization loop documented by Addy Osmani: https://addyosmani.com/blog/devtools-mcp/ .
- **By reference**: `claude mcp add chrome-devtools --scope user npx chrome-devtools-mcp@latest`; also ships a Claude Code plugin (`.claude-plugin/` in repo) with skills.
- **Verdict**: **WATCH** — overlaps Playwright MCP for verification; its unique value (perf traces, network, console) is diagnostic, not an oracle (no committed artifact, no exit code). Pick ONE browser MCP; Playwright MCP wins for a verify loop because it leads to committed tests.

---

## 2. Mutation testing (priority topic) — **ADOPT (per-PR, incremental, diff-scoped)**

### Evidence it matters specifically for AGENT-written tests
- AI suites reach high line coverage while killing few mutants ("perpetually green" tests with no real assertions) — mutation score is the counter-signal: https://www.augmentcode.com/guides/mutation-testing-ai-generated-code , https://dev.to/rsri/mutation-testing-the-missing-safety-net-for-ai-generated-code-54kn .
- **Industry scale**: Google "Mutagenesis": ~17M mutants across 760K code changes, 2M surfaced in code review, 24K+ developers — devs on mutation-tested projects write more tests. **Meta** ran LLM-based mutation testing across FB/IG/WhatsApp (Oct–Dec 2024); privacy engineers accepted 73% of generated tests. **Atlassian** Rovo Dev CLI writes tests from mutation reports. (All: Augment guide above.)
- Thoughtworks Radar lists mutation testing as a technique with renewed relevance for AI-generated code: https://www.thoughtworks.com/radar/techniques/mutation-testing .
- People are already packaging this as Claude Code skills that gate agent tests: https://tessl.io/registry/skills/github/secondsky/claude-skills/mutation-testing , https://smithery.ai/skills/cskiro/mutation-testing ; and wiring Stryker+mutmut into agent-codebase CI: https://github.com/aws-samples/sample-autonomous-cloud-coding-agents/issues/255 .
- Detailed practitioner report (Jan 2026): Stryker on a real repo = 394 mutants / 184 tests, ~91% score, minutes-scale; where Stryker is unsupported (Vitest browser mode) the author uses **Claude as a manual mutation tester** with a prioritized operator skill (boundaries → boolean logic → return values → statement removal), and explicitly concludes: *deterministic tools for CI gates, agent-driven mutation only for spot checks* — https://alexop.dev/posts/mutation-testing-ai-agents-vitest-browser-mode/ .

### Tools
| Tool | Ecosystem | Incremental / diff-scoped | Gate mechanism | Sources |
|---|---|---|---|---|
| **StrykerJS** | JS/TS | `--incremental` (since 6.2); per-PR runs reported at **1–5 min** | `thresholds.break` → exit 1 | https://stryker-mutator.io/docs/stryker-js/incremental/ , https://stryker-mutator.io/blog/announcing-incremental-mode/ |
| **mutmut** | Python | remembers prior runs; pytest-based | `--CI` flag | https://mutmut.readthedocs.io/ |
| **cargo-mutants** | Rust | `--in-diff` tests only PR-changed code | non-zero exit on missed mutants | https://mutants.rs/pr-diff.html |
| **pitest (PIT)** | JVM | history files (`--historyInputLocation`); coverage-targeted test selection | `<mutationThreshold>` | https://pitest.org/quickstart/maven |

- **By reference**: detect `stryker.config.*` / `stryker.conf.*`, `[tool.mutmut]` in pyproject.toml, `cargo mutants --version`, pitest in pom/gradle. Installers: `npm i -D @stryker-mutator/core`, `pip install mutmut`, `cargo install cargo-mutants`, Maven/Gradle plugin.
- **Cost / cadence**: full runs are minutes-to-hours — **not viable per loop iteration**. Incremental/diff-scoped runs (Stryker incremental, cargo-mutants --in-diff, PIT history) are viable **per PR / per forja pass**. Zero context cost (CLI + exit code); surviving-mutant lists are ideal, compact prompt input for the next test-writing iteration.
- **Verdict**: **ADOPT** — as the test-QUALITY gate on agent-written tests, run diff-scoped at PR-assembly time, never inside the inner edit loop. Surviving mutants feed back to the generator as targeted instructions.

---

## 3. Property-based testing — **WATCH**
- **Tools**: Hypothesis (Python), fast-check (JS/TS), proptest (Rust) — all detectable via dependency manifests; installers `pip install hypothesis`, `npm i -D fast-check`, crate `proptest`.
- **Evidence**: Research supports PBT as an LLM validation bridge — the Property-Generated Solver decouples a Generator agent from a Tester agent that validates via properties (independently mirrors generator≠evaluator): https://arxiv.org/html/2506.18315v1 . PropTest (visual programming) similar: https://arxiv.org/html/2403.16921v2 . BUT surveyed evidence says LLM-written properties are "frequently trivial or incorrect": https://arxiv.org/pdf/2505.23549 . No production harness found gating on PBT.
- **Cost**: deterministic with fixed seed; runtime seconds-to-minutes; shrinking can be slow.
- **Verdict**: **WATCH** — instruct generators to use PBT libs *when already present in the repo*; do not add a PBT gate (trivial-property risk means it would measure little).

---

## 4. Static analysis / semantic gates
- **Ruff** (Python lint+format, Rust-speed, ms-scale) — **ADOPT** when `ruff.toml`/`[tool.ruff]` detected; `pip install ruff`. Part of the Astral toolchain: https://pydevtools.com/handbook/reference/ty/ .
- **Biome** (JS/TS lint+format, Rust) — **ADOPT** when `biome.json` detected; `npm i -D @biomejs/biome`.
- **pyright / ty**: pyright is today's default typecheck gate. Astral's **ty** hit beta Dec 16 2025, 1.0 targeted 2026; 10–100x faster than mypy/pyright, incremental edits 4.7ms vs pyright 386ms on PyTorch — https://byteiota.com/astrals-ty-type-checker-beta-80x-faster-than-pyright/ , https://pydevtools.com/blog/ty-beta/ . **ADOPT pyright now (if configured), WATCH ty until stable** (conformance still <60%).
- **Semgrep** — CI scans ~10s; custom YAML rules writable in minutes; standard pattern is Semgrep as fast PR gate: https://appsecsanta.com/sast-tools/semgrep-vs-codeql , https://dev.to/rahulxsingh/semgrep-vs-codeql-lightweight-patterns-vs-semantic-analysis-for-sast-2026-412k . **ADOPT** when `.semgrep.yml`/`semgrep.yml` present (`pip install semgrep`, gate: `semgrep ci` exit code).
- **CodeQL** — DB extraction 15–45 min on medium repos (same sources). **REJECT as loop gate** (fine as nightly CI, outside galaxy-brain's loop).
- **ast-grep** — Rust AST pattern engine, much faster than Semgrep CLI (https://ast-grep.github.io/advanced/tool-comparison.html); first-class LLM support (llms.txt, AI-generated rules): https://ast-grep.github.io/blog/more-llm-support.html , http://astgrep.com/blog/ast-grep-agent.html ; used by CodeRabbit for AI-native linting: https://www.coderabbit.ai/blog/ai-native-universal-linter-ast-grep-llm . **ADOPT**: (a) as a gate when target repo has `sgconfig.yml`; (b) for galaxy-brain itself — encode invariants like "no `--auto-merge`/`gh pr merge` in skill-generated commands" as mechanical `ast-grep scan` rules over generated code. Detect `sgconfig.yml`; install `npm i -g @ast-grep/cli` or `cargo install ast-grep`.
- **Supporting evidence for mechanical invariants over agent codebases**: Phoebe enforces architecture on an agent-driven codebase via Bazel's strict dependency graph after custom static analysis proved fragile — "encode invariants in the build and surface violations deterministically": https://www.phoebe.work/blog/enforcing-architecture-in-an-agent-driven-codebase . Academic support: "A Deterministic Control Plane for LLM Coding Agents" (June 2026) argues governance of the agent layer "must be deterministic and tool-agnostic — not delegated to further LLM orchestration": https://arxiv.org/html/2606.26924v1 .

---

## 5. Visual regression — **ADOPT Playwright's built-in; REJECT the rest for v-next**
- **Playwright `toHaveScreenshot()`** — built into the runner: first run saves baseline, later runs pixel-diff via pixelmatch; baselines committed to repo; fully local/free, no SaaS: https://testquality.com/playwright-visual-regression-guide/ , https://bug0.com/knowledge-base/playwright-visual-regression-testing , https://testdino.com/blog/playwright-visual-testing . **ADOPT** — free once Playwright is the detected E2E stack; the harness must forbid agents from blindly running `--update-snapshots` to silence diffs (same hazard as snapshot `-u`).
- **BackstopJS** — mature (decade of use) but hand-written JS scenario configs, separate runner: https://lastest.cloud/blog/best-open-source-visual-regression-playwright . **REJECT** — duplicate surface once Playwright is adopted.
- **Lost Pixel** — OSS engine still maintained but the company is "sunsetting the product and building what's next": https://github.com/lost-pixel/lost-pixel , https://www.lost-pixel.com/ . **REJECT** (uncertain future).
- **Percy/Chromatic** — SaaS accounts/secrets, review UI in cloud. **REJECT** for a by-reference local gate (violates "works on any repo without accounts").

---

## 6. Runtime / trace oracles
- **Pact (contract testing)** — consumer tests generate pact JSON; provider CI replays and fails deterministically if the real API diverges: https://docs.pact.io/ , https://devblogs.microsoft.com/ise/pact-contract-testing-because-not-everything-needs-full-integration-tests/ . No agent-harness usage evidence found. **WATCH**: if a repo already contains `pacts/` or pact deps, run provider verification as a gate; never introduce Pact into a repo that lacks it.
- **API/response snapshot testing** (Jest/Vitest snapshots, Syrupy) — deterministic, but agents can trivially "fix" failures by regenerating snapshots; Pact's own docs warn exact snapshots are brittle: https://docs.pact.io/consumer . **WATCH** — if present, gate must forbid `-u`/`--update` flags in the loop; snapshot updates are evaluator-approval events.
- **Replay/trace testing** — no mature, generic, auto-detectable OSS tool surfaced that fits any repo. **WATCH**.

---

## Recommendations for galaxy-brain (synthesis)
1. **Web-project gate chain** (auto-detected): lint/format (Ruff|Biome) → typecheck (pyright|tsc) → unit suite → `npx playwright test` (incl. `toHaveScreenshot` if baselines exist) → diff-scoped mutation score at PR time.
2. **Playwright integration by reference**: detect config → offer `npm init playwright@latest` and `npx playwright init-agents --loop=claude` → Playwright MCP enabled ONLY in the evaluator subagent, snapshots-not-screenshots, every session must end in committed spec files. This preserves both hard rules: durable oracle + generator≠evaluator (healer output is evaluated too).
3. **Mutation score is the test-quality oracle** the evaluator cites; surviving mutants become next-iteration instructions. Per-PR incremental only.
4. **ast-grep for self-enforcement**: galaxy-brain's own hard rules ("never auto-merge") become mechanical scan rules — evidence-backed by the deterministic-control-plane literature.
