# eval/ — galaxy-brain's own A/B measurement rig (Harbor)

The SCOPE credibility gate: measure whether galaxy-brain actually improves outcomes, or we are
telling ourselves a story. Two arms on identical tasks — **A: stock Claude Code** · **B: Claude
Code + galaxy-brain** — inside Harbor containers, judged by objective verifiers that are
arm-independent.

This directory is galaxy-brain's own development tooling, not shipped skill behavior — hard rule 4
("nothing project-specific") applies to `skills/`, not to our measurement rig. Tasks currently
target a pinned commit of `consejo-7-sabios` (private repo, runs locally in Docker only).

## Where the tasks come from — and the honesty caveat

Tasks T1/T2 are real defects found by a galaxy-brain forja pass on 2026-07-24 and **confirmed by
cross-model refutation with executed repros** (see the forja state ledger). Because galaxy-brain
sourced them, this is a **fix benchmark, not a discovery benchmark**: both arms receive the same
bug report, so the measured delta is fix quality + verification honesty, NOT galaxy-brain's
discovery advantage. A discovery benchmark would need independently-sourced tasks (future work).

## Task set (v1)

| Task | Prompt gives | Verifier (arm-independent) |
|---|---|---|
| `t1-json-non-dict` | crash symptom + traceback shape, no file | `verify_t1_test.py`: `_extract_json_object` raises `json.JSONDecodeError` on valid non-object JSON, returns dict on objects; full suite green |
| `t2-signed-int32` | observed wrong diagnostic value | `verify_t2_test.py`: `DriverProcessError(returncode=2**31)` message contains `signed=-2147483648`; full suite green |
| `t5-ruff-gate` | "lint gate is red (11 errors), make it green" | `verify.sh`: `ruff check .` exit 0 AND `pytest -q` all green |

Designed but **verifier pending** (needs a careful repro against the consensus API — do not invent):
T3 no-op-amend-blocks-convergence, T4 stale-signature backport. They join v2.

## Universal post-checks (both arms, every trial)

1. Full suite green (`pytest -q`) — no regression.
2. `scripts/test-guard.js <base>..HEAD` clean or every flag human-reviewed — did the agent buy
   green by touching existing tests? This metric is the point: success WITH gaming is failure.
3. Diff size (lines touched) — smaller fix, same verifier result = better.

## Protocol

- **Trials**: 3 per task per arm (v1: 3 tasks × 2 arms × 3 = 18 runs).
- **Metrics per run**: verifier pass/fail · suite green · test-guard flags · tokens · wall time · diff lines.
- **Caps**: 30 min timeout per run; fixed model for both arms; temperature/model pinned identical.
- **Repo state**: pinned commit `4df1873` of consejo-7-sabios (pre-forja-fixes: all bugs present,
  ruff red) mounted fresh per trial.
- **Success definition**: verifier green AND suite green AND no unjustified test-guard flag.
- **Verifier calibration (2026-07-24, against the pinned broken state)**: t1+t2 verifiers run red
  exactly where they must — 7 failed (broken contract) / 4 passed (good-behavior anchors) — so a
  green verifier after an agent run means the bug is actually fixed, not that the test never bit.

Harbor wiring lives in [harbor/](harbor/README.md) — task configs, Dockerfiles, reward-contract
verifiers and the `prepare.sh` staging script (private inputs never enter git).
**The paid run is launched only on explicit human approval.**

## Status log

- **2026-07-24 — rig ready to fire.** End-to-end smoke WITHOUT any LLM: t1 image builds, the
  target suite runs green in-container (97 tests), and both controls calibrate — broken repo →
  `reward=0`, known-good patch → `reward=1`. The positive control caught (and we fixed) an
  over-strict t1 verifier that would have failed legitimate fixes. Dev-machine prereqs verified:
  Harbor 0.20.0 under WSL2 Ubuntu, Docker Desktop WSL integration enabled, daemon reachable from
  the distro. **Remaining before the run**: credentials (`ANTHROPIC_API_KEY` or
  `claude setup-token`) + explicit go. Arm A commands in [harbor/README.md](harbor/README.md);
  arm B requires the agent-subclass route with plugin-load confirmation in the transcript.
