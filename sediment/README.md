# Sediment

A Claude Code plugin that mines friction out of your past Claude Code
sessions - across all projects, not just the current one - and updates
CLAUDE.md files for you, one suggestion at a time. Every write is
confirmed before it happens - nothing is ever applied silently or in
bulk. Nothing calls out to the network beyond your own Claude Code
session's model calls.

Named for what settles out after the fact: the useful residue of
corrections and repeated preferences a session leaves behind, once you
filter out the noise.

## What it does

If you correct Claude the same way in 3+ different repos ("always activate
venv first", "don't use `any` in TypeScript"), that's a candidate for your
global `~/.claude/CLAUDE.md`. Friction that only shows up in one project
stays scoped to that project's CLAUDE.md. Sediment mines your session
transcripts for that signal, prints a plain-text report, then walks each
suggested rule and asks before writing it to the right CLAUDE.md.

## Install

Sediment depends on **session-archiver**
([claude-session-db](https://github.com/mtanneer/claude-session-db)), a
separate plugin in a separate repo/marketplace that archives session
transcripts into a durable local store outside Claude Code's own 30-day
retention. Add both marketplaces before installing - Claude Code
auto-installs the dependency once both are known:

```
/plugin marketplace add mtanneer/claude-session-db
/plugin marketplace add <git-url-of-this-repo>
/plugin install sediment
```

If you skip the first `marketplace add`, install will fail with
"Dependency session-archiver is not installed" - just run it and retry.

## Usage

```
/sediment:refine-memory
/sediment:refine-memory --project my-repo
/sediment:refine-memory --since 2026-06-01
```

With no flags, it scans every project Claude Code has session history for.

## `--dev` flag (plugin development only)

```
/sediment:refine-memory --dev --project my-repo
```

Writes a full trace of the run - every heuristic hit, every
`friction-judge` dispatch and verdict, cluster/render intermediate
output, and every apply decision - to a timestamped markdown file under
`tmp/sediment-logs/` in this plugin's own repo. This is a debugging aid
for developing Sediment itself, not a feature for end users: it's off by
default, never changes judgment/clustering/apply behavior, and never
writes outside the plugin repo's gitignored `tmp/`.

## Important: run this interactively

Sediment must run inside a live, interactive Claude Code session so its
model calls draw on your existing Pro/Max subscription. The judgment pass
is dispatched as a subagent (`friction-judge`) via the Agent tool from
within your session - it never shells out to `claude -p` (headless) or
makes raw API calls, both of which bill differently (a separate Agent SDK
credit, at standard API rates) rather than your subscription.

If `ANTHROPIC_API_KEY` is set in your shell environment, subagent calls
have been reported to route through it instead of subscription auth
(anthropics/claude-code#39903, #37686) - the skill checks for this and
warns you before a full scan, but worth confirming yourself with `/status`
if in doubt.

## Development

The 4 pipeline scripts (`discover_sessions.py`, `heuristic_filter.py`,
`cluster_friction.py`, `render_report.py`) have a pytest suite:

```
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest sediment/skills/friction-miner/scripts/tests/ -v
```

This covers the pipeline's pure logic (candidate detection, provenance
filtering, clustering, rendering) and can run headless, pre-push, with
no live session required.

The `friction-judge` subagent dispatch and the apply step (Edit tool +
user confirmation) both require a live interactive Claude Code session
and can't be unit-tested outside one - verify those manually with a
`--dev` run (see above) before a release.

## Status

Phase 1 (MVP): working end-to-end pipeline, manual invocation only,
report followed by a per-rule confirmed apply step. See `../plans/PLAN.md`
for the full spec, including Phase 2 (smarter clustering) and Phase 3
(marketplace publish, optional session-end hook) plans.
