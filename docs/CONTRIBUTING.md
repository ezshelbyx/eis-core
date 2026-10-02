# Contributing to E.I.S. Core

Thanks for helping! E.I.S. Core is built by and for the technician community — every
contribution, from a one-line fix to a new module, matters.

## Ground rules

1. **Safety is a feature, not a setting.** Anything that can delete, overwrite or unlock gets a
   confirmation gate and a safety-engine review. If your tool changes state, it must fail closed.
2. **Stdlib only** in `eis/` (optional deps go through a bridge and must degrade gracefully).
3. **Modules stay UI-free.** Logic in `eis/modules/`, presentation in `eis/ui/`, dicts in between.
4. **Tests accompany changes.** Bug fixes get a regression test; features get coverage.

## Reporting bugs

Open an issue and include:

- E.I.S. Core version (Settings → About, or `git describe`)
- Windows version and architecture
- What you did, what you expected, what happened
- Relevant excerpt from `data/logs/` (**redact customer data** — never paste customer names,
  serials or files into an issue)

## Suggesting features

Open an issue tagged `feature` describing the *technician problem* it solves. Small, sharp tools
that fit the dashboard model are preferred over kitchen-sink integrations.

## Development workflow

```bat
git clone <repository-url>
cd EISTech
python -m pytest tests/ -q        # baseline: all green before you start
```

1. Create a branch: `git checkout -b feat/my-tool`
2. Follow [DEVELOPER.md](DEVELOPER.md) (threading pattern, dict results, safety gates).
3. Run the suite: `python -m pytest tests/ -q`
4. Commit with Conventional Commits: `feat(network): port scan history export`

## Pull requests

- Keep PRs focused — one tool/fix per PR.
- Update docs (README feature map, module docs) when behavior is user-visible.
- CI-style local checklist:
  - [ ] `python -m pytest tests/ -q` passes
  - [ ] No tkinter imports under `eis/modules/` or `eis/database/`
  - [ ] Destructive paths confirmed + safety-classified
  - [ ] New settings registered in `DEFAULTS`

A maintainer reviews for safety, architecture fit and test quality. Cosmetic-only changes are
welcome but may wait for batch merging.

## Adding knowledge-base entries

The KB lives in `eis/modules/knowledge/kb_data.py`. Each entry connects an error signature with
its cause, diagnostic steps and solution. PRs adding well-verified entries are merged quickly —
this is the single most valuable contribution type for the community.

## License

By contributing you agree your work is released under the project's MIT license.
