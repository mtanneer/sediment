# Contributing

## Setup

```
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
```

## Tests

```
.venv/bin/pytest sediment/skills/friction-miner/scripts/tests/ -v
```

Single test:

```
.venv/bin/pytest sediment/skills/friction-miner/scripts/tests/test_heuristic_filter.py -v
```

Only the 4 pipeline scripts (`discover_sessions.py`, `heuristic_filter.py`,
`cluster_friction.py`, `render_report.py`) have unit tests — pure logic,
headless. The `friction-judge` subagent dispatch and the apply step
require a live interactive Claude Code session and can only be verified
manually via a `--dev` run of `/sediment:refine-memory` (see README).

## Branches

`<type>/<username>/<description>`, types: `feat|fix|chore|test|docs|refactor`.

## Versioning

`sediment/.claude-plugin/plugin.json`'s `version` must be valid,
strictly-increasing semver on any PR touching non-doc files. CI's
`version-check` job (`.github/workflows/ci.yml`) enforces this; docs-only
changes (`.md`, `.github/`, `ruff.toml`) are exempt.

## CI

Runs on every PR, in order: `version-check` → `lint` (ruff) →
`secret-scan` (gitleaks) → `unit-tests` (pytest). All must pass before
merge.

## Before a release

Run `/sediment:refine-memory --dev` at least once to verify the two
untestable pipeline steps (judge dispatch, apply) still work end-to-end.
