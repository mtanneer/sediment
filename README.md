# Sediment

![version](https://img.shields.io/badge/dynamic/json?url=https://raw.githubusercontent.com/mtanneer/sediment/main/sediment/.claude-plugin/plugin.json&query=%24.version&label=version)

A Claude Code plugin that mines friction — corrections, repeated
preferences — out of your past Claude Code sessions across *all*
projects, and suggests CLAUDE.md diffs. Report-first, apply per-rule with
confirmation. Nothing auto-applies, nothing writes silently, nothing
calls out to the network beyond your own Claude Code session's model
calls.

Named for what settles out after the fact: the useful residue of
corrections and repeated preferences a session leaves behind, once you
filter out the noise.

## Install

Sediment depends on
[**session-archiver**](https://github.com/mtanneer/claude-session-db), a
separate plugin/marketplace that archives session transcripts into a
durable local store outside Claude Code's own 30-day retention. Add both
marketplaces — Claude Code auto-installs the dependency once both are
known:

```
/plugin marketplace add mtanneer/claude-session-db
/plugin marketplace add mtanneer/sediment
/plugin install sediment
```

If you skip the first `marketplace add`, install fails with "Dependency
session-archiver is not installed" — just run it and retry.

## Why

If you correct Claude the same way in 3+ different repos — "always
activate venv first", "don't use `any` in TypeScript" — that's signal
for your *global* `~/.claude/CLAUDE.md`, not a one-off patch to whichever
project you happened to be in when you said it. Friction that only shows
up in one project stays scoped to that project's CLAUDE.md. Sediment
scans your session transcripts for that signal, prints a plain-text
report grouped GLOBAL vs. per-project, then walks each suggested rule and
asks before writing it.

```
=== GLOBAL suggestions (~/.claude/CLAUDE.md) ===
+ Always activate venv before running Python commands
  (seen in: svdoc, rental-autopilot, home-ai-agent)

=== svdoc ===
+ Use pyslang, not a hand-rolled parser, for SystemVerilog tokenization
```

## Usage

```
/sediment:refine-memory
/sediment:refine-memory --project my-repo
/sediment:refine-memory --since 2026-06-01
```

With no flags, it scans every project Claude Code has session history
for.

## How it works

1. **Discover** — reads `~/.claude/history.jsonl` (the authoritative
   project→session index; folder-name decoding is never used, it's lossy
   on hyphenated paths).
2. **Filter** — regex/pattern pass per session transcript for correction
   phrases, reverted edits, repeated clarifying questions, and explicit
   "always/never" statements, each bundled with ±2 turns of context.
3. **Judge** — every candidate is dispatched to the `friction-judge`
   subagent (read-only, no Write) via the Agent tool. It enforces
   provenance: a rule only counts if *you* said it, not Claude's own
   self-talk, however reasonable that self-talk sounds.
4. **Cluster** — fuzzy-dedupes within a project; a similar rule seen in
   2+ distinct projects gets tagged GLOBAL, otherwise LOCAL. Diffs
   against your CLAUDE.md's current content so already-addressed rules
   don't get re-suggested.
5. **Report** — plain-text diff-style output, GLOBAL first, then
   per-project.
6. **Apply** — walks the same clustered rules, confirms one rule (or one
   same-target batch) at a time via a prompt, writes accepted rules under
   a `# Sediment suggestions` heading. Nothing is written without your
   say-so.

## Running interactively

Sediment must run inside a live, interactive Claude Code session so its
model calls draw on your existing Pro/Max subscription. The judgment pass
is dispatched as a subagent via the Agent tool from within your session —
it never shells out to `claude -p` (headless) or makes raw API calls,
both of which bill differently (a separate Agent SDK credit, at standard
API rates) instead of your subscription.

If `ANTHROPIC_API_KEY` is set in your shell environment, subagent calls
have been reported to route through it instead of subscription auth
(anthropics/claude-code#39903, #37686) — the skill checks for this and
warns before a full scan, but worth confirming yourself with `/status` if
in doubt.

## `--dev` flag (plugin development only)

```
/sediment:refine-memory --dev --project my-repo
```

Writes a full trace of the run — every heuristic hit, every
`friction-judge` dispatch/verdict, cluster/render intermediates, every
apply decision — to a timestamped markdown file under `tmp/sediment-logs/`
in *this plugin's own repo*, never the project being scanned. Off by
default, never changes pipeline behavior. This is a debugging aid for
developing Sediment itself, not an end-user feature.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, test commands, and PR
conventions.

## Architecture

```
sediment/
├── .claude-plugin/plugin.json      # plugin manifest
├── commands/refine-memory.md       # /sediment:refine-memory — thin wrapper, invokes the skill
├── skills/friction-miner/
│   ├── SKILL.md                    # pipeline steps 1-6, argument parsing, dev-log spec
│   ├── scripts/                    # pure local processing, no network calls
│   │   ├── discover_sessions.py
│   │   ├── heuristic_filter.py
│   │   ├── cluster_friction.py
│   │   └── render_report.py
│   └── references/friction-patterns.md
├── agents/friction-judge.md         # read-only subagent: judges one excerpt
└── README.md
```

## Status

Phase 1 (MVP): working end-to-end pipeline, manual invocation only,
report followed by a per-rule confirmed apply step. See
[`plans/PLAN.md`](plans/PLAN.md) for the full spec, including Phase 2
(smarter clustering) and Phase 3 (marketplace publish, optional
session-end hook), and a comparison against Anthropic's official
`claude-md-management` plugin (complementary, not competing — static
rubric on the CLAUDE.md file itself vs. friction mined from session
transcripts).

## Relationship to session-archiver

Sediment's own `friction-miner` skill hit a real gap while being built:
session transcripts get pruned after 30 days with no reconciliation
against the prompt-only `history.jsonl` index. That gap was split out
into its own plugin,
[claude-session-db](https://github.com/mtanneer/claude-session-db)
(`session-archiver`), which Sediment declares as a dependency (see
Install above). Sediment doesn't yet read from the archive instead of
raw transcripts — that switch is tracked as follow-up work in this
plugin's own `plans/PLAN.md`.
