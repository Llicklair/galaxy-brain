# /construye — v0.5 verified-build demonstration (2026-07-24)

First end-to-end exercise of galaxy-brain's **verified-implement engine** on a clean sample repo:
a spec becomes failing acceptance tests, code is written to green, and an independent cross-vendor
evaluator signs off — nothing merged. This is the load-bearing content of the v0.5 gate.

## What was built

A throwaway `moneylib` sample (fixture, like `eval/`): `cart_total(items, coupon_percent=0)` —
sum of `price × quantity` as a 2-decimal `Decimal`, optional percent coupon, `ValueError` on a
negative quantity.

## The chain, in order (every step ran a real galaxy-brain script)

1. **Constitution → mechanical law** (`constitution.js`): 3 principles compiled — LAW-001 "no `float()`
   on money" and LAW-002 "no `print()`" became **iron** ast-grep rules; LAW-003 "readable API" stayed
   **paper** (judged-only). Coverage report: 2 iron, 1 paper, 0 pending.
2. **Spec → acceptance criteria in EARS** (hand-written; see honest scope below) — 3 clauses.
3. **EARS → failing tests** (`ears.js` extract + scaffold): one ID-tagged stub per clause. Bodies were
   written from the criteria **before `cart.py` existed**.
4. **RED, anchored** (`evidence.js red`): acceptance suite failed (exit 2, no implementation) and the
   test file was SHA-256-pinned. Committed as `base`.
5. **Implement to green**: `cart.py` written (Decimal throughout, no float, no print).
6. **Deterministic gates, all green**: acceptance GREEN with the **hash-identical** test
   (`evidence.js green`), full suite green, `ears.js check` 1:1 clause↔test OK, `constitution.js check`
   LAW-001/002 clean, `test-guard.js base..HEAD` — 0 gaming signals (only production code added).
7. **Cross-vendor sign-off** (`gemini-cli`, Google — a different vendor than the Claude generator):
   adversarial verdict **PASS** on all three EARS criteria and the readability law; no tautology/bug
   found. Generator ≠ evaluator, across model families, for real.
8. **Evidence bundle** (`evidence.js bundle`): red(exit 2) → green(exit 0, same test hash) → full
   suite → PASS verdict. Machine-checkable proof, ready to attach to a PR. Nothing auto-merged.

## Honest scope — what this proves and what it doesn't

- **Proven**: galaxy-brain's own contribution — EARS acceptance criteria compiled to failing tests,
  test-first with a hash-pinned red→green chain, mechanical constitution enforcement, test-gaming
  detection, and an independent **cross-vendor** evaluator — works end-to-end and delivers an evidence
  bundle, on a repo built from nothing, with nothing merged.
- **NOT run here**: GitHub Spec Kit's front half (`/speckit-specify → clarify → plan → tasks`). That
  pipeline is adopted **by reference**; here the spec/EARS were hand-authored to exercise the verified
  engine without the extra LLM/install cost. The literal v0.5 gate ("constitution→spec→plan→implement"
  via Spec Kit) is therefore **not** fully closed — its verification half is.
- **Caveats**: the generator was the main Claude loop (not an isolated `loop-fixer` subagent) with
  Gemini as evaluator — valid for generator≠evaluator, but not the full subagent firewall; "blind"
  test authorship is enforced by sequence + hash, not by a sandbox. The sample is a disposable fixture.

## Verdict

The v0.5 **engine** is demonstrated and honest. Closing the gate *literally* needs one run through the
Spec Kit front half into this same verified implement — a quota step, launched only on explicit go.
