# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Sediment: a Claude Code plugin that mines friction (corrections, repeated
preferences) out of past Claude Code session transcripts across all
projects, and suggests CLAUDE.md diffs. Report-first, apply-per-rule with
confirmation — nothing auto-applies, nothing writes silently.

## Commands

```
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest sediment/skills/friction-miner/scripts/tests/ -v
```

Single test: `.venv/bin/pytest sediment/skills/friction-miner/scripts/tests/test_heuristic_filter.py -v`

Only the 4 pipeline scripts (`discover_sessions.py`, `heuristic_filter.py`,
`cluster_friction.py`, `render_report.py`) have unit tests — pure logic,
runs headless. The `friction-judge` subagent dispatch and the apply step
(Edit + user confirmation) require a live interactive Claude Code session
and can only be verified manually via a `--dev` run of
`/sediment:refine-memory`.

## Architecture

Plugin layout (see `plans/PLAN.md` for the full spec, including Phase
2/3 plans):

```
sediment/
├── .claude-plugin/plugin.json      # plugin manifest
├── commands/refine-memory.md       # /sediment:refine-memory — thin wrapper, invokes the skill
├── skills/friction-miner/
│   ├── SKILL.md                    # pipeline steps 1-6, argument parsing, dev-log spec
│   ├── scripts/                    # pure local processing, no network calls
│   │   ├── discover_sessions.py    # reads ~/.claude/history.jsonl
│   │   ├── heuristic_filter.py     # regex pass over one session JSONL
│   │   ├── cluster_friction.py     # fuzzy-dedupe + GLOBAL (2+ projects) vs LOCAL tagging
│   │   └── render_report.py        # formats the final diff-style report
│   └── references/friction-patterns.md
├── agents/friction-judge.md         # read-only subagent: judges one excerpt (RULE/SKIP/UNCLEAR)
└── README.md
```

Pipeline, run end-to-end by the `friction-miner` skill when
`/sediment:refine-memory` fires:

1. `discover_sessions.py` reads `~/.claude/history.jsonl` (the
   authoritative project→session index) → `{project_path, session_ids[]}`.
   Never decode `~/.claude/projects/<encoded-path>/` folder names directly —
   the `/`/`.`→`-` encoding is lossy and collides on hyphenated dirs.
2. `heuristic_filter.py` scans each session transcript JSONL for friction
   candidates (correction phrases, reverted edits, repeated questions,
   explicit "always/never" statements — patterns in
   `references/friction-patterns.md`), each bundled with ±2 turns of
   context. A missing transcript file (aged past the 30-day
   `cleanupPeriodDays` retention) is routine — the script skips it and
   exits 0, not an error.
3. Every candidate is dispatched to the `friction-judge` subagent via the
   Agent tool (never pre-filtered or triaged inline first). The subagent
   is read-only (`tools: Read, Grep, Glob`, no Write) and enforces a
   provenance check: a rule only counts if the *user* stated it — not
   Claude's own self-talk/lint-driven reasoning, even if the resulting
   rule sounds reasonable on its own.
4. `cluster_friction.py` groups the resulting `RULE:` outputs: fuzzy-dedupe
   within a project, tag GLOBAL if a similar rule appears in 2+ distinct
   projects else LOCAL. Also diffs each candidate against the target
   CLAUDE.md's current content to skip already-addressed rules.
5. `render_report.py` prints the final plain-text report.
6. Apply step walks the same clustered structure, resolving each rule's
   target file (GLOBAL → `~/.claude/CLAUDE.md`; LOCAL → project root
   `CLAUDE.md`, falling back to `.claude/CLAUDE.md`), confirming one rule
   (or one same-target batch) at a time via AskUserQuestion, and writing
   accepted rules under a `# Sediment suggestions` heading via Edit.

## Hard constraints (billing/auth — read before touching the pipeline)

Sediment must run entirely inside a live interactive Claude Code session
so model calls draw on the user's Pro/Max subscription, not a separate
API bill:

- No raw HTTP calls to `api.anthropic.com` from anything under `scripts/`.
- No shelling out to `claude -p` (headless) — as of 2026-06-15 this bills
  through a separate Agent SDK credit at standard API rates, not the
  subscription pool.
- The judgment pass must go through the Agent tool (`friction-judge`
  subagent) from within the session — this is the only model-invocation
  point in the whole pipeline. `scripts/` stays pure local processing
  (filesystem, regex, clustering) forever.
- If `ANTHROPIC_API_KEY` is set in the shell, subagent calls have been
  reported to silently reroute through it instead of subscription auth
  (anthropics/claude-code#39903, #37686) — check `echo $ANTHROPIC_API_KEY`
  and warn before a full scan; `/status` also shows active auth mode.

## `--dev` flag

`/sediment:refine-memory --dev` writes a full run trace (every heuristic
hit, every judge dispatch/verdict, cluster/render intermediates, every
apply decision) to `tmp/sediment-logs/<timestamp>.md` in *this plugin's
own repo* — never in the project being scanned. Off by default, never
changes pipeline behavior. Use it to validate a change to the pipeline
before a release, since steps 3 and 6 can't be unit-tested.
