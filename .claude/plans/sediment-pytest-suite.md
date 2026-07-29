# Sediment — Add a pytest suite for the 4 scripts

## Context

The `friction-miner` skill's 4 scripts (`discover_sessions.py`,
`heuristic_filter.py`, `cluster_friction.py`, `render_report.py`) each
have a single `--self-check` smoke test today - useful as a quick sanity
check, but coarse: one `assert` block per script, not per-behavior, and
not runnable via a standard `pytest` invocation. Today's provenance fix
(removing `reverted_edit`, adding `_is_human_turn()`) needed two rounds
of manual re-verification against real transcripts precisely because
there was no fine-grained regression coverage - a proper suite should
make that kind of change safe to verify locally without re-running
against real session data every time.

The judge (`friction-judge` subagent) and apply step (Edit tool +
AskUserQuestion confirmation) require a live interactive Claude Code
session and cannot be unit-tested outside one - confirmed acceptable by
the user, scope stays to the 4 scripts. Verifying those two steps
continues to mean a manual `--dev` run before a push, as established
today.

Per your CLAUDE.md: Python work needs a venv, never raw `python3`/`pip3`
outside one. No venv exists in this repo yet.

## What changes

New files:
- `.venv/` at repo root (created via `python3 -m venv`, gitignored -
  `tmp/` is already gitignored via `.gitignore`; add `.venv/` alongside
  it).
- `requirements-dev.txt` at repo root - just `pytest`, since the plugin's
  actual scripts are stdlib-only by design (no runtime deps to declare).
- `sediment/skills/friction-miner/scripts/tests/` - one test file per
  script:
  - `test_discover_sessions.py`
  - `test_heuristic_filter.py`
  - `test_cluster_friction.py`
  - `test_render_report.py`
  - `conftest.py` only if a shared fixture turns out to be worth it
    (e.g. a tmp_path-based JSONL-writer helper) - not scaffolded
    speculatively, add only if duplicated across 2+ test files.

No changes to the 4 scripts' actual logic - this is pure test coverage
addition. The existing `--self-check` blocks in each script stay as-is
(they're also the mechanism `SKILL.md`/this session used for quick
manual verification during today's work) - not removed, since removing
a working thing nobody asked to remove isn't in scope.

- `sediment/README.md` - add a short "Development" section: venv setup,
  `pip install -r requirements-dev.txt`, `pytest` invocation, and the
  note that judge/apply steps need a manual `--dev` session run instead.

## Design: what each test file covers

Each script already exposes pure, side-effect-free functions
(`discover()`, `find_candidates()`, `cluster()`, `render()`) separate
from their CLI `main()` - tests import and call these directly, no
subprocess invocation needed. `main()`/argparse plumbing itself is not
separately tested (thin wrapper, low value, per the ladder - one
`--self-check`-style CLI smoke assertion per script is enough given the
core logic is otherwise fully covered).

**`test_discover_sessions.py`** (`discover()` from `discover_sessions.py`):
- empty/missing history file → `{}`
- single project, single session
- multiple projects, multiple sessions
- duplicate session_id for the same project → not double-counted
  (existing self-check case, promoted to a real test)
- entries missing `project` or `session_id` → skipped, not KeyError

**`test_heuristic_filter.py`** (`find_candidates()` from
`heuristic_filter.py`) - the largest file, given today's fix:
- `correction` pattern match on a real human turn → 1 candidate
- `explicit_rule` pattern match on a real human turn → 1 candidate
- a turn matching neither pattern → 0 candidates
- **provenance gate**, one test per rejection path (this is the part
  that took two iterations to get right today, so it gets the most
  granular coverage):
  - `isMeta: true` turn with rule-shaped text → 0 candidates
  - `attributionSkill`/`attributionPlugin` set → 0 candidates
  - `origin.kind` present and not `"human"` → 0 candidates
  - plain turn with no `origin`/`isMeta`/attribution fields (the common
    case, matches real non-hook transcripts) → still detected normally
- `repeated_question` structural match (two similar assistant questions
  above the similarity threshold) → 1 candidate
- two dissimilar assistant questions → 0 `repeated_question` candidates
- context window is exactly ±2 turns around the match (boundary check
  at the start/end of a short transcript, not just the happy path)

**`test_cluster_friction.py`** (`cluster()` from `cluster_friction.py`):
- a rule appearing in exactly 3 distinct projects → tagged GLOBAL
- a rule appearing in only 2 distinct projects → tagged LOCAL to both
- fuzzy-matching across reworded phrasings of the same rule (the
  transitive-grouping fix from Phase 1 - promoted from the existing
  self-check into an explicit regression test so it can't silently
  regress)
- an unrelated rule → stays in its own group, never merged in
- single rule, single project → LOCAL, not GLOBAL

**`test_render_report.py`** (`render()` from `render_report.py`):
- GLOBAL section renders with the `(seen in: ...)` project list
- LOCAL section renders grouped per project
- both GLOBAL and LOCAL present in one report
- empty input (`{"global": [], "local": {}}`) → "No friction candidates
  found." (existing self-check case, promoted to a real test)

## Verification

- `python3 -m venv .venv`, `.venv/bin/pip install -r requirements-dev.txt`,
  `.venv/bin/pytest sediment/skills/friction-miner/scripts/tests/ -v` -
  all tests pass.
- Confirm the provenance tests actually fail if `_is_human_turn()`'s
  guard is temporarily removed (sanity-check the tests aren't
  vacuously true) - not committing that regression, just confirming
  test validity during implementation.
- Re-run each script's existing `--self-check` too - confirm both the
  old smoke tests and the new pytest suite agree, no drift introduced.
- `git status`-equivalent check that `.venv/` doesn't end up tracked
  (add to `.gitignore` before creating it).

## Explicitly not doing

- No tests for `friction-judge` or the apply step - needs a live
  session, stays manual (`--dev` run), per the user's explicit scope
  call.
- No CI/GitHub Actions wiring - user confirmed this is a pre-push local
  check, not an automated pipeline, for now.
- No refactor of the 4 scripts' CLI/main() boundary - already clean
  enough to test around as-is.
- No pyproject.toml - plain requirements-dev.txt is enough for one dev
  dependency; revisit only if the repo grows more Python tooling later.
