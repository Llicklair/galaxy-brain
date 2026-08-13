# Feedback from live-code: inyector module (2026-08-13)

## Context

Feature built: `guardia.inyector` — a deterministic adversarial proposal generator
for testing T3 gates without an LLM. 6 injection families, anchored to `banco.py`
obedience predicates, 16 tests, 37 new boundary rules (265 total).

Repo: `C:\Users\Marcos\Desktop\live code` (guardia v0.1.0)
Tool: galaxy-brain 0.7.0

## What gb caught correctly

1. **`gb graph --gate`**: Detected the new module immediately (reads filesystem, not
   git diff). Verified all 265 boundary rules, 0 violations, 0 cycles. Confirmed
   `guardia.politica` fan-in increased from 10→11 correctly.

2. **`gb check` (post-commit)**: Mapped the full ONDA (wave) of 25 symbols touched by
   the commit, with caller counts (e.g., `Inyeccion` has 6 callers, `_filtro` has 3).
   No signals — correct, because the new code follows all existing patterns.

3. **`gb delta`**: Scanned 2 new .py files, found 0 classic errors. Correct.

4. **Pre-commit hook** ran the full suite (254 tests, 2 skipped) + graph gate check
   before allowing the commit. The gate check at commit time is the strongest signal.

## What gb missed or couldn't see

### Finding 1: `gb check` and `gb delta` are blind to untracked files

**Before committing**, `gb check` and `gb delta` only looked at HEAD~1..HEAD (the
*previous* commit's diff). The brand-new `inyector.py` and `test_inyector.py` were
untracked, so they were invisible to both commands.

**Impact**: An agent that writes new code and runs `gb check` to validate it will get
"0 signals" — not because the code is clean, but because gb didn't look at it. The
agent could interpret silence as approval.

**Contrast**: `gb graph --gate` DID see the new files because it reads the filesystem.
So boundary violations would be caught, but delta anti-patterns and check signals
would not.

**Possible improvement**: `gb check` could optionally include untracked `.py` files in
its diff, or at least warn "N untracked .py files not analyzed". This is especially
relevant for agent workflows where code is written and checked before committing.

### Finding 2: `gb tests` didn't recommend `test_inyector.py`

Before committing, `gb tests` recommended tests based on the previous commit's diff,
not the new files. After committing, this was not re-checked, but the pre-commit hook
ran the full suite anyway.

**Possible improvement**: Same as above — `gb tests` could detect new test files and
include them.

### Finding 3: The "verification ceiling" confirmed

Adding a well-structured module to a well-structured repo produced zero surprises. All
265 boundary rules passed. All 16 tests passed on the first try. gb had nothing to
flag because the patterns are already established and followed.

---

## Deliberate violation experiments (executed)

Four experiments run against the committed inyector, modifying `inyector.py`
temporarily and running gb before reverting. All code restored to clean state after.

### Exp 1: Import prohibited by boundary rule (`inyector → crisol`)

- **Added**: `from .crisol import Crisol`
- **`gb graph --gate`**: **DETECTED** — `! guardia.inyector -> guardia.crisol [guardia.inyector -/-> guardia.crisol]`
- **`gb check`**: **DETECTED** — flagged as "ACOPLAMIENTO nuevo vs HEAD~1"
- **`gb delta`**: NOT detected (delta looks for code anti-patterns, not boundary violations)
- **Verdict**: gb catches declared boundary violations reliably, through two independent commands.

### Exp 2: Import NOT covered by any boundary rule (`inyector → json_hostil`)

- **Added**: `from .json_hostil import demasiado_anidado`
- **`gb graph --gate`**: **NOT DETECTED** — "Sin cruces de frontera prohibidos (265 reglas)"
- **`gb check`**: **NOT DETECTED** — "Sin acoplamiento nuevo" (no rule exists, so no violation)
- **Fan-in shift**: `json_hostil` went from 6→7 silently.
- **Verdict**: gb only enforces rules that exist. A missing rule = a silent import. The
  boundary system is a **deny list, not an allow list** — it catches what you thought to
  forbid, but can't warn about dependencies you didn't anticipate.
- **Implication for agents**: An agent adding a new module needs to also write boundary
  rules, or undeclared dependencies slip through. gb could help by warning "module X has
  no boundary rules" (it already reports "Sin ninguna regla que los mencione: 1 de 28
  modulo(s) — guardia" for the root package, but not for leaf modules with zero rules).

### Exp 3: Import prohibited by boundary rule (`inyector → banco`)

- **Added**: `from .banco import OBJETIVOS`
- **`gb graph --gate`**: **DETECTED** — `! guardia.inyector -> guardia.banco [guardia.inyector -/-> guardia.banco]`
- **No cycle** (banco doesn't import inyector).
- **Verdict**: Same as Exp 1 — declared rules are enforced reliably.

### Exp 4: Semantic bug — wrong IP in `desviar_victima`

- **Changed**: CIDR from `198.51.100.0/24` (innocent third party) to `203.0.113.0/24`
  (which INCLUDES the real C2 at 203.0.113.7). This silently turns "desviar" into
  "contener" — the injection no longer deviates, it accidentally does the right thing.
- **`gb delta`**: **NOT DETECTED** — "Sin errores clásicos" (delta checks syntax patterns,
  not business logic)
- **`gb graph --gate`**: No violation (structural rules are fine)
- **`pytest`**: **DETECTED** — 2 failures:
  - `test_desviar_victima_apunta_a_otro_sitio`: IP 203.0.113.7 IS in 203.0.113.0/24
  - `test_inyecciones_obedecen_predicados_del_banco`: the banco predicate `_no_cubre_el_c2`
    now returns False (the proposal covers the C2, so it's not "obedecida" as a deviation)
- **Verdict**: gb cannot catch semantic/logic bugs. The test suite caught it because the
  tests encode the *intent* (deviation means pointing away from the C2), not just the
  *structure*. This is the correct division of labor: gb handles structural invariants,
  tests handle semantic ones.

---

## Summary matrix

| What was wrong | `gb graph --gate` | `gb check` | `gb delta` | `pytest` |
|---|---|---|---|---|
| Import violates declared boundary | **CAUGHT** | **CAUGHT** | missed | n/a |
| Import has no boundary rule | missed | missed | missed | n/a |
| Semantic bug (wrong IP) | missed | missed | missed | **CAUGHT** |
| Untracked new files | sees them | blind | blind | sees them |

## Actionable feedback for galaxy-brain

1. **Untracked file blindness** (findings 1–2): `gb check`, `gb delta`, and `gb tests`
   should at minimum warn about untracked `.py` files, or optionally include them. This
   is critical for agent workflows.

2. **Missing-rule gap** (exp 2): gb could warn when a module has zero boundary rules
   (currently only flags the root package). A module with no rules is either perfectly
   isolated (unlikely) or under-specified.

3. **Semantic bugs are out of scope** (exp 4): This is correct by design — gb is
   structural, not semantic. But it's worth documenting explicitly so agents don't
   over-trust `gb delta` as a substitute for running tests.

4. **The verification ceiling is real** (finding 3): gb's highest value is in repos
   that DON'T already have this discipline. The next validation step should be a repo
   where boundaries don't exist yet and gb has to help discover them.
