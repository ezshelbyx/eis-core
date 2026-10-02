# Developer Guide

This document explains how E.I.S. Core is structured, the conventions every module follows, and
how to add your own tools. Read it end-to-end once before your first PR.

## Project layout

```
eis/
├── app.py               # EISApp dashboard shell: section navigation, result pump
├── core/                # infrastructure shared by everything
│   ├── settings.py      # JSON-backed settings (DEFAULTS merged over user file)
│   ├── safety.py        # command classification + path guards (fail closed)
│   ├── command_runner.py# run_command / run_powershell / run_cmd (never raises)
│   ├── privilege.py     # admin detection / elevation requests
│   ├── paths.py         # workspace paths + command history recorder
│   ├── logging_config.py# logging setup, runtime dir creation
│   └── utils.py         # small shared helpers (format_bytes, …)
├── database/            # SQLite layer
│   ├── connection.py    # connection factory (WAL, foreign keys)
│   ├── schema.py        # migration runner; migrations/001_initial.sql
│   ├── repository.py    # generic CRUD repository
│   ├── customers.py / jobs.py / history.py   # domain repositories
│   └── service.py       # DatabaseService facade owning all repositories
├── modules/             # pure logic, NO tkinter imports allowed
│   ├── system/ windows/ network/ android/ files/ knowledge/ reports/
└── ui/                  # tkinter presentation layer
    ├── app.py theme.py widgets.py
    └── views/           # one file per dashboard section
```

**The one rule that keeps this clean:** `eis/modules/*` and `eis/database/*` must never import
tkinter or touch the UI. They return plain dicts; the views render them. This is what makes the
150-test suite fast, headless and reliable.

## Non-negotiable conventions

### 1. Threading — the queue pattern

Long operations **must** run in a worker thread. Views use `Section.run_in_thread()` (in
`eis/ui/widgets.py`), which executes a callable off-thread and queues its result. The main loop
pumps those queues: `EISApp._pump_results()` runs every 100 ms via `after()` and calls each
view's `pump_results()`.

```python
self.run_in_thread(lambda: system_info.collect(), on_done=self._render)
```

**Never call `self.after()`, `self.update()` or touch widgets from a worker thread** — Tkinter
raises `RuntimeError: main thread is not in main loop`. If you need the UI updated, queue a
result.

### 2. Command execution — always through the runner

Never call `subprocess` directly. Use `run_command(argv, timeout=…)`, `run_powershell(script)` or
`run_cmd(line)`. The runner:

- consults the safety engine (blocked patterns fail closed),
- returns a `CommandResult` dict (`ok`, `stdout`, `stderr`, `returncode`, `blocked`, `timeout`,
  `not_found`) instead of raising,
- decodes Windows console output UTF-8-first.

Internal read-only lookups may pass `check_safety=False`, but only for known-safe argv lists.

### 3. Safety first

Any destructive action goes through `SafetyEngine.classify_command()`; any user-chosen scan or
delete root goes through `guard_scan_root()`. Blocked patterns (`format`, `diskpart`,
`shutdown`, `fastboot flashing unlock`, `adb shell su`, …) are not configurable. When adding a
destructive tool, require an explicit `confirmed=True` parameter in the module API and a UI
confirmation dialog.

### 4. Results are dicts

Module functions return plain dicts with an `"ok"` key plus `"error"` on failure — never custom
exceptions across module boundaries, never UI objects.

### 5. Settings

Read settings via `get_settings().get("key", default)`. Add new defaults to `DEFAULTS` in
`eis/core/settings.py`; user files are merged over defaults, so missing keys are safe. Values
needing shape guarantees belong in `_normalize()`.

## Adding a tool (checklist)

1. **Module** — add the logic under the right `eis/modules/<area>/` file. Pure dict in / dict out.
2. **Safety** — classify the action; add `confirm_delete`/`confirmed` gates for anything
   destructive; extend `BLOCKED_PATTERNS` only for genuinely irreversible dangers.
3. **View** — add a control in the relevant `eis/ui/views/<section>_view.py`, run via
   `run_in_thread`, render in `pump_results` callback. Keep long outputs in `Text` widgets with
   scrollbar; keep status in the StatusBar.
4. **Tests** — add/extend a file in `tests/`. Tests must not require admin rights, internet, or
   an Android device. Parse-heavy logic should be tested with synthetic input (see
   `tests/test_android_modules.py::TestApkAnalyzer` building an APK in `tmp_path`).
5. **Docs** — one line in the README feature map if user-visible.

## Database changes

Schema evolution is migration-based: add `eis/database/migrations/002_your_change.sql`, and bump
`SCHEMA_VERSION` in `eis/database/schema.py`. Migrations run in order inside a transaction; the
`user_version` pragma tracks progress. Repositories extend `Repository` (generic
`create/get/update/delete/search/count`) — add domain-specific queries to the subclass.

## Running and writing tests

```bat
python -m pytest tests/ -q              # whole suite (~3 min on low-end hardware)
python -m pytest tests/test_core_safety.py -q
python -m pytest tests/ -q -k "duplicate"
```

- Shared fixtures live in `tests/conftest.py` (`tmp_db`, `db`, `safety_engine`, `sample_job`).
- Tests that scan `tmp_path` with guarded tools must monkeypatch the safety engine (see
  `_AllowScanRoots` in `tests/test_files_tools.py`) — real `tmp_path` sits inside the protected
  user profile, by design.
- Slow external processes (PowerShell cold start) get generous timeouts rather than sleeps.

## Code style

- Python 3.10+ syntax; type hints on public functions; docstrings on modules and classes.
- Standard library only in `eis/`; optional third-party imports go through a bridge module
  (see `psutil_bridge.py`) and must degrade gracefully.
- Line length ≤ 100; no unused imports; `from __future__ import annotations` at the top of
  every module.
- Commit messages follow Conventional Commits (`feat(android): …`, `fix(ui): …`,
  `test: …`, `docs: …`).
