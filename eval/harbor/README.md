# eval/harbor — Harbor glue for the A/B run

Runbook for executing the [eval/](../README.md) task set under Harbor (v0.20.x). Single source of
truth for prompts/verifiers is `eval/tasks/` — `prepare.sh` stages them (plus the private repo
snapshot) into each Harbor task dir; those staged files are **gitignored** here.

## Prereqs (once)

1. **WSL2** — Harbor's harness is POSIX-only on Windows (Docker Desktop's WSL2 backend is fine).
   Keep task dirs and the jobs cache on the WSL filesystem.
2. `uv tool install harbor` (Python ≥3.12) · `harbor --version`.
3. Credentials, either: `export ANTHROPIC_API_KEY=…` (auto-injected per-exec), or subscription:
   `export CLAUDE_CODE_OAUTH_TOKEN=$(claude setup-token); export CLAUDE_FORCE_OAUTH=1`.

## Stage inputs

```sh
./prepare.sh /mnt/d/consejo-7-sabios     # pins commit 4df1873 via git archive (no .git leaks)
```

Per task this creates `environment/repo/` (snapshot), `instruction.md` (from eval/tasks prompt)
and copies the pytest verifiers into `tests/`. The Dockerfile git-inits the snapshot and tags
`base` so the verifier can diff exactly what the agent changed.

## Arm A — baseline (runnable as-is)

```sh
harbor run --path tasks/t1-json-non-dict --agent claude-code \
  --model anthropic/claude-sonnet-5 --n-attempts 3 --n-concurrent 2 \
  --job-name a-t1 --ak max_budget_usd=5
# repeat per task (t2, t5), job names a-t2 / a-t5
```

## Arm B — with galaxy-brain (choose ONE route; verify live before trusting)

Harbor's claude-code agent has **no native plugin support**. Three routes, by increasing fidelity:

| Route | Carries | Caveat |
|---|---|---|
| `skills_dir` in task.toml | skills only | no hooks/scripts/agents — measures the prompt layer only |
| B-variant Dockerfile: bake plugin into image + `COPY galaxy-brain /opt/galaxy-brain` | skills + scripts on disk | agent runs with `CLAUDE_CONFIG_DIR=/logs/agent/sessions` — confirm the config dir picks the plugin up before claiming arm B ran with it |
| `--agent-import-path` subclass of ClaudeCode overriding `setup()` | full plugin | most work; the only route that provably installs hooks |

**Do not report arm-B results without confirming (in the trial transcript) that the plugin
actually loaded** — a silently-absent plugin turns the A/B into A/A and fakes a null result.

## Results

`~/.cache/harbor/jobs/<job-name>/` → per-trial `result.json` (tokens, cost_usd, timings,
verifier reward), `verifier/reward.txt`, `verifier/diff-stat.txt`, `verifier/test-guard.json`
(gaming signals over `base..HEAD`, written when node is available in the image), full agent
transcript. Browse with `harbor view`.

Success per eval/README.md: reward 1 AND no unjustified test-guard flag. Compare arms on:
success rate, tokens, cost_usd, wall time, diff size, gaming flags.

**The paid run launches only on explicit human approval.**
