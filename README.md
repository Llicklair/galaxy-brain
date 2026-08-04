<p align="center">
  <img src="assets/galaxia.svg" alt="galaxy-brain" width="100%">
</p>

# galaxy-brain

> **When something crashes, it tells you where and with what state — without you reproducing it by hand.**

That is the spine: an error console. Around it, the same discipline applied to other deterministic
facts about your code — what shape it has (`graph`/`symbols`/`calls`), what each change did to it
(`check`), what foundation it is missing (`floor`), what was learned across repos (`memory`).

**One tool, `gb`.** A single Python package, **zero model calls** on the hot path, **zero
dependencies** beyond the standard library. An exception is a fact; the state at the moment of
failure is a fact; the shape of the import graph is a fact. Reporting facts requires no judgment,
which is why it can be instant and cannot fail in expensive ways.

The scope is closed on purpose, and the list of what it does **not** do — the half that bears
weight — is written in [SCOPE.md](SCOPE.md). The design law lives in
[ARCHITECTURE.md](ARCHITECTURE.md).

<sub>443 tests · clean gate · ruff · Python ≥ 3.9 · zero runtime dependencies · CLI output is in Spanish today</sub>

---

## What it saves you

A traceback tells you **where**. This also tells you **with what**:

```
KeyError: 'empresa'
hace 1min · facturacion/precios.py:6 · mi-api

  facturacion/precios.py:6  in precio_total
         4 |
         5 | def precio_total(cliente, cupon=None):
   →     6 |     base = TARIFAS[cliente["plan"]]
         7 |     unidades = cliente["asientos"]
         8 |     return base * unidades

      cliente = {'nombre': 'Beto', 'plan': 'empresa', 'asientos': 12}
      cupon   = None
```

The step that disappears is relaunching the program with a `print` in it. The failure happens once,
often while you are not looking; reproduction is the expensive work this removes.

---

## Installation

```bash
pip install -e .     # from this repo
gb on                # enables capture in this Python environment
gb status            # verifies it stuck
```

`gb on` drops a `.pth` file into site-packages. From then on **there is nothing to remember**: every
Python process in that environment is covered, without touching any project's code.

Bringing it to another project is one command, with that project's venv active:

```bash
# bash / WSL
pip install -e <path-to-this-repo> && gb on && gb status

# Windows — instala.ps1 does exactly that, no paths to type (it locates itself)
powershell -ExecutionPolicy Bypass -File <path-to-this-repo>\instala.ps1
```

Coverage is **per Python environment, not per repo**. Being editable (`-e`), a `git pull` here
updates every environment with no reinstall. To remove it: `gb off` — one line, no residue. Cheap
removal is deliberate (rule 10: abandonment is data, not something to armor against).

---

## Day one

```bash
git init my-project && cd my-project
gb floor        # the floor: what is missing before you build, and why each piece matters
gb floor --init # drops the base documents — and the pre-commit hook
```

On a fresh git repo the session map suggests this path by itself — one line, only in the
unambiguous case (git present, no code, no floor docs), silence otherwise. `--init` leaves six
pieces, never overwriting anything: `AGENTS.md` (executable context in the cross-tool format read
by Claude Code, Codex, Cursor, Copilot and Aider — including the gb usage contract for agents),
`SCOPE.md`, `ARCHITECTURE.md`, an ADR folder, an evidence log, and `.githooks/pre-commit` with the
gate wired in ratchet mode — inherited debt does not block, only what is new does. Hook it once
with `git config core.hooksPath .githooks`.

One thing no tool can write for you, and gb says so out loud: the **done criterion** in SCOPE.md.
You write it before the first line of code.

---

## The error console

```bash
gb last              # this project's latest failure, with its state
gb last --full       # with every frame
gb list -n 20        # the history: what breaks, and how often
gb list --chrono     # the raw timeline, most recent first
gb show <id>         # one specific failure — the id comes in the capture notice
gb status            # what is active, and how many captures have been read
```

With no arguments, `gb last` and `gb list` filter by the repo you are standing in. And the failure
card ends **in the graph** — the crash anchored to the symbol whose body contains the line, with
its blast wave one command away:

```
en el grafo: lib.base · function · lib.py:5
  le llaman (1): lib.ayuda
```

The anchor is honest about time: it resolves against **today's** code, and if the file changed
after the capture it says so, with the exact commit — instead of silently pointing at whatever
occupies that line now.

**One failure type, three exit doors.** "Uncaught exception" is not a synonym for `sys.excepthook`:
the interpreter lets failures out through three doors, and all three are covered.

| Door | When | Status |
|---|---|---|
| `sys.excepthook` | The exception kills the main thread and the process | covered |
| `threading.excepthook` | It kills a `threading` thread; the process lives on | covered (`GB_NO_THREADS=1` opts out) |
| `sys.unraisablehook` | Python **could not** propagate it: `__del__`, weakrefs, GC | covered |

The third door was the only one that vanished **without a trace**: the interpreter prints it, the
process does not die, and nothing was left to show. None of the three costs anything while your
program works.

**What triggers a capture and what does not — executed, not documented:**

```bash
gb status --cobertura   # runs 8 real failure modes and shows which leave a record
```

```
LO QUE SI deja registro          LO QUE NO (y es correcto)
  + excepcion no capturada          - asyncio: tarea suelta que nadie espera
  + excepcion en un hilo            - sys.exit(1)
  + excepcion en __del__            - KeyboardInterrupt
  + asyncio fuera de run()          - excepcion atrapada por try/except
```

The boundary is not documented — documents age. It is **demonstrated** every time you run it.

---

## The map

<p align="center">
  <img src="assets/grafo.svg" alt="galaxy-brain's own module graph" width="100%">
</p>

The other half of the surface: what shape the project has and who calls whom. All deterministic,
zero models, zero dependencies — same facts, different views. **`graph --html` and `symbols --html`
lead to the same page**: modules, symbols, imports and calls on one navigable canvas.

```bash
gb graph src --gate         # import cycles + declared boundaries (.gb-boundaries); for pre-commit
gb graph src --gate --since HEAD   # ratchet: only NEW debt fails, inherited debt passes
gb symbols src              # the symbol graph: who calls whom, with its resolution coverage
gb symbols src --html m.html --open        # the interactive cloud (search, drag, focus)
gb symbols src --html m.html --watch       # the LIVE map: regenerates when any .py changes
gb symbols src --since HEAD~50             # what grew since that ref, marked apart
gb calls <symbol>           # who calls a symbol and whom it calls, with file:line
gb calls <symbol> --depth 2                # the wave: also who calls the callers
gb check --staged           # what a diff did to tests, coupling, and its wave (informs, never blocks)
gb floor                    # the floor: what is missing before you build
```

A symbol card carries everything an agent needs to **call code it has not read** — the signature
straight from the AST (args, defaults, `*`, `async`, the decorators that change the call), where it
lives, what it does (first docstring line), and who depends on it, with sources split from tests:

```
galaxybrain.store.parse_ts(value) · function · src\galaxybrain\store.py:270 — El `ts` de una entrada…
  le llaman (7 — 6 de src, 1 de tests):
```

Clicking a node answers with **facts**: its description (taken from the docstring, not from a
model), who calls it, whom it calls, what it imports, whether it sits in a cycle — plus the layers
of history: the error-cycle rings (captured → read → intervened → silent) and a halo on whatever is
**in progress**, uncommitted, right now. Imports are drawn differently from calls because **an
import is exact and a call is inferred** — merging them into one number would mean gating on a
proxy (rule 11).

Two honest numbers ship with every run: `gb symbols` **declares what it could not resolve**
(`object.method()` calls require type inference, and here nothing is guessed: a false edge gets
believed, a missing one gets noticed), and measured against an inference-based index (GitNexus) it
scores **93% recall** with zero dependencies. Details and the negative results live in
[docs/pruebas-de-uso.md](docs/pruebas-de-uso.md).

**Wired into the agent.** Three hooks make the graph ambient: at session start the compressed map
(~110 tokens, 162 ms) is injected, along with a count of unread captures when there are any; after
each edit, only what **changed** — or silence; and on every code search, the matching symbol cards
ride along (`gb calls --hook`: 430 ms on this repo, 330 ms on a 600-module synthetic one). The
agent asks the graph before opening files — and `gb symbols … --watch` keeps the human's map fresh
in the browser, atomically, with nothing but the filesystem.

---

## The gate is verified by breaking it

A gate degrades in silence: it keeps returning zero and stops looking at anything. Tests pin what
you already knew how to check; this pins that the detector still detects when a defect is put in
front of it.

```bash
gb graph --self-test        # injects 6 known defects and fails if the gate does NOT see them
gb graph src --self-test    # additionally: relations that must hold on YOUR code
```

The **metamorphic relations** are "these two ways of asking must agree", evaluated on your real
repo: the same folder spelled `c:` or `C:` yields the same shape; a cycle's imports are edges that
exist; `graph` and `symbols` see the same modules. That is where most of the real defects lived.

---

## Cross-repo memory

A fact learned in one repo should not die there. `gb memory` is a vault of durable markdown notes
(in `~/.claude/memory-global`, hand-editable, with `[[wikilinks]]` so Obsidian opens the graph)
that surface in **any** project via a `SessionStart` hook.

```bash
gb memory index              # the compact index, one line per note
gb memory recall <words>     # full text of the most relevant notes
gb memory context            # the session payload (what the SessionStart hook calls)
gb memory add --name x --description "..." --scope always
```

Lean by design (H6): session start injects the index of **all** notes but the full text only of
`always` notes and this project's; the rest is pulled on demand with `recall`. The vault is never
dumped whole.

---

## Cost, measured

Rule 4 of [ARCHITECTURE.md](ARCHITECTURE.md): the budget is measured, not estimated. Python 3.11,
Windows 10, median of 20 cold starts:

| | |
|---|---|
| Clean interpreter startup | 21.2 ms |
| With the hook installed | 27.7 ms |
| **Hook cost** | **6.4 ms** (A/B measured: 5.2 ms) |
| — of which, `import threading` | 5.2 ms |

**While your program works, the cost is zero.** Not "low": zero. The hooks only run once the
process has already failed. For a tiny CLI that never touches threads: `GB_NO_THREADS=1`.

Other measured numbers: session map ~110 tokens in 162 ms · `symbols` 93% recall · search hook
430 ms (this repo) / 330 ms (600 synthetic modules) · `gb show` with anchor 158 ms · ruff 130 ms ·
the suite in ~30 s, far under the 600 s DORA threshold.

---

## Settings

Everything via environment variables; there is no config file to maintain.

| Variable | Default | What it does |
|---|---|---|
| `GB_DISABLE` | off | Turns capture off without uninstalling anything |
| `GB_QUIET` | off | Silences the one-line notice printed after the traceback |
| `GB_HOME` | `~/.galaxy-brain` | Where the history lives |
| `GB_NO_THREADS` | off | Skip thread exceptions (saves 5.2 ms of startup) |
| `GB_ALL_FRAMES` | off | Also keep locals of library frames |
| `GB_MAX_FRAMES` | 20 | Frames kept (innermost survive) |
| `GB_CONTEXT_LINES` | 2 | Source lines around the failing one |
| `GB_OPEN_CMD` | browser | What opens the map (`--open`); receives the path as last argument |

`GB_OPEN_CMD` exists because gb **knows no editor** and will not maintain a list: rule 6 says a
hardwired command is a bug. Point the map wherever you want (`GB_OPEN_CMD="firefox --new-window"`).

---

## Secrets — redaction by name, with an honest residue

The state around a failure is exactly where credentials live. The console **redacts by name**
(`password`, `token`, `api_key`, `secret`, `auth`, `credential`, `session`, `cookie`…). The trigger
is always the **name**, never the content: guessing whether a string is a secret is expensive and
fallible; the name was written by a human, on purpose.

**The residue, said plainly:** a secret **without a sensitive name next to it** reaches disk — a
positional literal (`connect("hunter2")`), a password inside a URL (`user:pass@host`), a secret
value under an innocent name. Closing that would require content heuristics, which this project
rejects deliberately because they fail and sell false safety. That is why the golden rule does not
depend on redaction: **the history lives in your `$HOME` in plain text; treat it as sensitive and
upload it nowhere.**

---

## Known limits, stated up front

- **Uncaught exceptions only.** An `except: pass` that swallows the failure is invisible here — and
  rightly so: a handled exception is, by definition, one its author decided was not a failure.
- **Main thread, `threading` threads, and finalizers** (`__del__`, weakrefs, GC). **`asyncio` with
  stray tasks** nobody awaits stays out; if the exception propagates out of `asyncio.run()`, it is
  captured.
- **No source file, no code context.** `python -c`, `exec()` and the REPL keep type, message,
  frames and state, but not the surrounding lines (`gb list` sets them apart as ephemeral).
- **The state is the state at death**, not a time-travel debugger.
- **Unrepresentable objects are described, not reconstructed.** A `__repr__` that blows up leaves
  `<Type: repr() failed with X>` and does not take the rest of the frame down with it.
- **Non-Python deaths** — a segfault, an OOM kill, a `kill -9` — raise no exception, so no hook
  ever sees them.

---

## Development

```bash
python -m pytest tests/ -q          # the suite
python -m ruff check src tests      # lint (catches defects, holds no style opinions)
```

The pre-commit ([.githooks/pre-commit](.githooks/pre-commit)) runs lint + suite + gate in < 10 s;
hook it once with `git config core.hooksPath .githooks`. `git commit --no-verify` skips it — and
that skip is a datum, not a rule (rule 10: abandonment gets investigated, not armored against).

The console's layering rules live in [src/.gb-boundaries](src/.gb-boundaries): the core (capture,
store, analysis) does not import the presentation (`cli`, `render`, `viz`). A new crossing stops
the commit; a test-softening signal only informs.
