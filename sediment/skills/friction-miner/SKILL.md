---
name: friction-miner
description: Mines friction (corrections, repeated rules) out of past Claude Code sessions across all projects and prints suggested CLAUDE.md diffs. Use when the user runs /sediment:refine-memory or asks to refine/audit their CLAUDE.md based on past session history.
---

# friction-miner

Cross-project pattern detection over past Claude Code session transcripts.
Prints a plain-text diff-style report of suggested CLAUDE.md changes, then
walks the suggestions one at a time and asks before writing each one.
**Never bulk-applies or writes silently** - every edit is confirmed
per-rule.

## Billing/auth constraint - read first

This skill's judgment pass MUST run via the **Agent tool** (dispatching
`friction-judge`), inside this live interactive session. Do not:

- Make raw HTTP calls to `api.anthropic.com` from any script.
- Shell out to `claude -p` (headless). As of 2026-06-15, headless and Agent
  SDK usage bill through a separate Agent SDK credit at standard API rates,
  not the Pro/Max subscription pool.

Before a full (multi-project) scan, check for a stray API key that could
silently reroute subagent billing:

```
echo $ANTHROPIC_API_KEY
```

If set, warn the user before proceeding - subagents have been reported to
route through it instead of subscription auth (anthropics/claude-code#39903,
#37686). `/status` also shows which auth mode is active.

All scripts under `scripts/` are pure local processing (filesystem + regex
+ stdlib clustering) - no network calls. The model-judgment step is the
`friction-judge` subagent's own reasoning, not a script.

## Argument parsing

`$ARGUMENTS` arrives as a raw string. Parse it yourself:

- `--project <name>` - scope the scan to one project only (substring match
  against project path).
- `--since <date>` - limit lookback to sessions after this date (ISO
  format). Default: since the last `git log -1 --format=%ad -- CLAUDE.md`
  commit touching that project's CLAUDE.md, or 30 days back if the project
  isn't a git repo or CLAUDE.md has no history.
- `--dev` - **plugin-development-only** debug mode. Writes a full trace
  of this run to a local markdown log under `tmp/sediment-logs/` in
  *this plugin's own repo* (not the scanned project) - every heuristic
  hit, every judge dispatch and verdict, cluster/render intermediate
  output, and every apply decision. Never enabled by default, never
  affects judgment/clustering/apply behavior - purely additive logging
  for whoever is developing Sediment itself. See "Dev logging" below.
- No flags → full scan, all projects, default lookback per project.

## Dev logging (`--dev` only)

If `--dev` was passed, before step 1: `mkdir -p tmp/sediment-logs` in
*this plugin's own repo* (the sediment plugin's source checkout, not the
project being scanned - if unsure of the path, it's the directory
containing this skill's `.claude-plugin/plugin.json` or `sediment/`
root), then create `tmp/sediment-logs/<ISO-8601-timestamp>.md` via Write
with a `# Sediment dev log - <timestamp>` header plus the parsed flags
(`--project`, `--since`, resolved lookback date).

Append to this file inline as each pipeline step below runs (don't
buffer to the end - a run that errors partway should still leave a
useful partial log):
- After step 1: the raw discover output.
- After step 2, per session: session id + the full heuristic_filter.py
  JSON (every candidate, including ones later judged SKIP).
- After each step 3 dispatch: the excerpt sent to `friction-judge` and
  its verbatim response.
- After step 4: the `rules.json` built, cluster_friction.py's output,
  and the result of the dedup-against-existing-CLAUDE.md check (which
  rules were dropped as already-present, and where).
- After step 5: the exact rendered report text.
- After each step 6 sub-step: target file resolved, the confirm prompt
  shown, the answer given, and whether a write happened.
- After step 6's summary line: append it as the log's footer too.

If `--dev` was not passed, skip all of the above - no file is created,
no behavior changes. This log may contain real excerpts from the user's
own past sessions and real CLAUDE.md paths - it stays local under
`tmp/` (already gitignored) and is never uploaded, published, or part of
what a normal plugin install does; it exists only to help whoever is
developing Sediment itself review a run afterward.

## Pipeline

1. **Discover sessions**
   ```
   python3 ${CLAUDE_SKILL_DIR}/scripts/discover_sessions.py [--project <name>]
   ```
   Reads `~/.claude/history.jsonl` (never decode
   `~/.claude/projects/<encoded-path>/` folder names yourself - lossy,
   collides on hyphenated dirs). Outputs `{project_path, session_ids[]}`.

2. **Heuristic filter** - for each session, prefer the durable archive
   written by the `session-archiver` plugin over the raw transcript:
   ```
   python3 ${CLAUDE_SKILL_DIR}/scripts/heuristic_filter.py <archive-or-transcript-path>
   ```
   Resolve the path per session id as follows:
   - Archive path: `~/.claude-archive/<encoded-project-path>/<session-id>.json`,
     where `<encoded-project-path>` is `project_path` with every
     non-alphanumeric character replaced by `-` (same lossy scheme Claude
     Code itself uses - collisions don't matter here since the archive
     file's own body carries the uncorrupted `project_path`, and you
     already know it from `discover_sessions.py`'s output).
   - If that archive file doesn't exist (session-archiver isn't installed,
     or backfill hasn't run yet), fall back to the raw transcript path
     `~/.claude/projects/<encoded-project-path>/<session-id>.jsonl`.

   `heuristic_filter.py` accepts either shape (archive `.json`, wrapped
   under `turns`, or raw `.jsonl`, one turn per line) and picks based on
   file extension. For an archive with a `subagents` array
   (`schema_version` 2+), it scans each subagent's own turns in addition
   to the main transcript - so corrections/rules stated to a delegated
   agent are caught too, not just ones in the main conversation. Each
   candidate carries an `agent_id` field (`null` for the main session,
   the subagent's id otherwise).

   Matches patterns from `${CLAUDE_SKILL_DIR}/references/friction-patterns.md`
   (correction phrases, explicit rules, repeated questions - all gated by
   a provenance check, see the file for details). Outputs a JSON list of
   candidates, each with ±2-turn context.

   `discover_sessions.py`'s session ids come from `history.jsonl`, which
   logs every prompt and is never pruned - but a raw transcript
   (`~/.claude/projects/.../<session-id>.jsonl`) is deleted automatically
   once it ages past Claude Code's default 30-day `cleanupPeriodDays`
   retention, and won't exist for an old session if session-archiver
   never archived it. A missing file (of either kind) for a given session
   id is routine, not a bug: `heuristic_filter.py` skips it (prints a note
   to stderr, outputs `[]`, exits 0) rather than erroring - don't treat a
   "skipping ... archive/transcript file not found" line as a failure.

3. **Judge each candidate** - dispatch **every** candidate `heuristic_filter.py`
   returned to the `friction-judge` subagent via the Agent tool, one call
   per candidate (or small batch), passing only the candidate's `context`
   excerpt - not the full session. Collect `RULE: ...` responses; drop
   `SKIP`/`UNCLEAR`.

   Do not pre-filter, triage, or skip candidates yourself before
   dispatch, even if a candidate looks like noise (a task-notification
   dump, a self-driven debug loop, an unrelated tool-output blob) - that
   judgment call belongs to `friction-judge`, not to inline guessing in
   this session. If `heuristic_filter.py` returns zero candidates, there's
   nothing to judge and step 3-5 produce an empty report; if it returns
   any candidates, all of them go to the judge, no exceptions.

   Do not write ad-hoc Python (`python3 -c`, scratch scripts) to inspect
   or filter candidate JSON - `heuristic_filter.py`'s output is
   already the exact shape the judge needs (`kind`, `text`, `context`,
   `agent_id`). Pipe it to the judge directly.

4. **Cluster**
   ```
   python3 ${CLAUDE_SKILL_DIR}/scripts/cluster_friction.py <rules.json>
   ```
   Input: JSON list of `{project_path, rule}` built from step 3's `RULE:`
   outputs. Dedupes fuzzy-similar rules; tags a rule GLOBAL if it appears
   in 2+ distinct projects, else LOCAL to each project it appeared in.

   Before finalizing, diff each candidate rule against that project's
   *current* CLAUDE.md content (and the global `~/.claude/CLAUDE.md`) -
   skip near-duplicates of rules already present, so already-addressed
   friction isn't re-suggested.

5. **Render**
   ```
   python3 ${CLAUDE_SKILL_DIR}/scripts/render_report.py <clustered.json>
   ```
   Prints the final report. Show it to the user as-is.

6. **Apply** - walk the same `clustered.json` structure just rendered
   (global rules, then local rules per project) and, for each rule:

   a. **Resolve target file**:
      - GLOBAL rule → `~/.claude/CLAUDE.md`.
      - LOCAL rule → that project's CLAUDE.md. Check repo root
        `CLAUDE.md` first, then `.claude/CLAUDE.md`. If neither exists,
        target the repo root path and create it on first accepted rule.

   b. **Confirm** - use AskUserQuestion (or a plain "apply this? y/n"
      prompt if unavailable) showing the rule text and target file. Ask
      one rule, or a small batch of rules sharing the same target file,
      at a time - never bulk-confirm the whole run upfront. On no, skip
      and move on; don't re-ask in this run.

   c. **Write** - on yes, use the Edit tool to append the rule as a
      bullet under a clearly marked section (use an existing
      `# Sediment suggestions` heading if the file already has one, else
      create it) so sediment-written rules are easy to spot and prune
      later. Don't touch any other part of the file.

   d. After the loop, print a one-line summary: rules applied vs.
      skipped, per target file.

## Notes

- Large scans (dozens of projects) take a while - give the user a brief
  progress indicator (e.g. "scanning project 4/12...") rather than going
  silent.
- Keep judgment-pass context small: ±2 turns per candidate, never a full
  session transcript.
