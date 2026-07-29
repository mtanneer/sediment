# PLAN.md — Sediment Plugin Build Spec

## What this is

**Sediment** — a Claude Code plugin that mines friction out of your past
Claude Code sessions — across ALL projects, not just the current one — and
prints suggested CLAUDE.md diffs for you to review and apply manually.
Nothing auto-applies. Nothing calls out to the network beyond the Anthropic
API for the judgment pass.

Named for what settles out after the fact: the useful residue of corrections
and repeated preferences that a session leaves behind, once you filter out
the noise.

Inspired by the gap between `/memory` (manual editing only) and tools like
Claude Chronicle (session curation, but no memory-refinement angle).

## Relationship to Anthropic's official `claude-md-management` plugin

Anthropic ships an official plugin (`claude-md-management`, in
`anthropics/claude-plugins-official`) that audits existing CLAUDE.md files
against a static quality rubric (commands/workflows, architecture clarity,
conciseness, currency, actionability) and proposes targeted fixes — always
with a report-first, approve-before-write flow.

Sediment is **complementary, not competing**:

| | `claude-md-management` | Sediment |
|---|---|---|
| Input | The CLAUDE.md file itself | Session transcripts (JSONL history) |
| Method | Static quality rubric | Friction mining (corrections, reverted edits, repeated rules) |
| Scope | Single project / monorepo | Cross-project, with global vs. local clustering |
| Output | Quality score + targeted fixes | Suggested diff, categorized by project vs. global |

Where useful, Sediment can shell out to or reuse `claude-md-management`'s
quality-report step rather than reinventing it — worth revisiting once
Phase 1 is working, not a blocker for now.

## Billing/auth constraint (important — read before building)

Sediment must run entirely through an **interactive Claude Code session**,
so all model calls draw on your existing Pro/Max subscription. This rules
out a few implementation patterns that would silently switch billing:

- **No raw API calls** from `scripts/` (e.g. a Python script doing
  `requests.post("https://api.anthropic.com/v1/messages", ...)`). That
  requires an API key and always bills to whichever Console/API account
  owns it — not your subscription.
- **No `claude -p` (headless) invocations.** As of June 15, 2026, headless
  and Agent SDK usage no longer draws from the Pro/Max subscription pool at
  all — it's billed through a separate Agent SDK credit at standard API
  rates, even for subscribers.
- **Do it via the Agent tool, interactively.** The judgment pass (heuristic
  candidates → "is this a real rule?") must be dispatched as a subagent
  (`agents/friction-judge.md`) from within a live `claude` session you're
  running yourself, typed as `/sediment:refine-memory`. Subagents dispatched
  this way inherit your subscription auth like any other Claude Code
  subagent — no key required.
- **Known gotcha to check first**: if `ANTHROPIC_API_KEY` is set in your
  shell environment (e.g. left over from another project), subagents have
  been reported to silently route through that key instead of the
  subscription (anthropics/claude-code#39903, #37686). Before running a
  full scan: `echo $ANTHROPIC_API_KEY` to confirm it's unset, or check
  `/status` inside the session to confirm subscription auth is active.
- `scripts/` (`discover_sessions.py`, `heuristic_filter.py`,
  `cluster_friction.py`, `render_report.py`) should stay pure local
  processing only — filesystem reads, regex, clustering math. No network
  calls, no model invocation. The model-judgment step is Claude's own
  reasoning inside the session/subagent, not something the scripts call out
  to.

## Core value prop

Cross-project pattern detection. If you correct Claude the same way in 3+
different repos ("no, always activate venv first", "don't use `any` in
TypeScript", etc.), that's a candidate for your GLOBAL `~/.claude/CLAUDE.md`,
not a one-off patch to a single project's file. Single-project friction stays
scoped to that project's CLAUDE.md.

## Architecture

```
sediment/
├── .claude-plugin/
│   └── plugin.json                     # required manifest
├── commands/
│   └── refine-memory.md                # /sediment:refine-memory — thin wrapper, invokes the skill below
├── skills/
│   └── friction-miner/
│       ├── SKILL.md                    # main logic: pipeline steps, judgment prompt
│       ├── scripts/
│       │   ├── discover_sessions.py    # reads ~/.claude/history.jsonl
│       │   ├── heuristic_filter.py     # regex/pattern pass over JSONL
│       │   ├── cluster_friction.py     # groups candidates, tags local vs global
│       │   └── render_report.py        # formats final diff report
│       └── references/
│           └── friction-patterns.md    # the heuristic rule list (correction phrases, etc.)
├── agents/
│   └── friction-judge.md               # subagent for Phase 2 (isolated context)
├── hooks/                              # Phase 3 only — session-end auto-trigger
│   └── hooks.json
└── README.md                           # required documentation
```

Note: no `marketplace.json` inside the plugin itself — that manifest belongs
to a *marketplace repo* (which can list one or many plugins). For solo
distribution, this repo is installable directly via
`/plugin marketplace add <git-url>` once `.claude-plugin/plugin.json` exists,
no separate marketplace file needed. Only add a `marketplace.json` if you
later want to bundle Sediment alongside other plugins you publish.

## Data sources (ground truth, verified against Claude Code docs)

- **`~/.claude/history.jsonl`** — master index mapping project paths to
  sessions. USE THIS, not folder-name decoding.
  - Do NOT decode `~/.claude/projects/<encoded-path>/` folder names yourself.
    The `/` and `.` → `-` encoding is lossy (hyphenated directories collide —
    see anthropics/claude-code#7009 and #21085). history.jsonl is authoritative.
- **`~/.claude/projects/<encoded-path>/*.jsonl`** — one file per session,
  contains the full turn-by-turn transcript (Human/Assistant roles, tool
  calls, tool results).
- **CLAUDE.md locations per project**: check repo root first, then
  `.claude/CLAUDE.md`. Global file is always `~/.claude/CLAUDE.md`.

## Phase 1 — MVP

**Command**: `/sediment:refine-memory` — global scan is the DEFAULT (no flag needed).

Flags:
- `--project <name>` — scope to one project only
- `--since <date>` — limit lookback (default: since last CLAUDE.md git commit
  in each project, fall back to 30 days if not a git repo)

**Pipeline** (implemented as the `friction-miner` skill, invoked by the
`/sediment:refine-memory` command):

1. `discover_sessions.py` reads `history.jsonl`, builds a list of
   `{project_path, session_ids[]}`.
2. For each session, `heuristic_filter.py` scans the JSONL transcript for
   friction candidates using regex/pattern rules (see
   `references/friction-patterns.md` for the full list):
   - Correction phrases: "no, actually", "that's not what I", "I meant",
     "don't do that", "stop", "undo that"
   - Reverted tool calls: an edit/write immediately followed by another
     edit to the same file within N turns
   - Repeated clarifying questions: same/similar question asked by Claude
     more than once in a session (simple fuzzy string match)
   - Explicit rule statements: "always", "never", "from now on", "remember
     that" — these are gold, they're the user directly stating a preference
   Each hit gets bundled with ±2 turns of surrounding context (not the full
   session — keep the judgment pass cheap).
3. Candidates get handed to Claude's own reasoning within the session —
   dispatched to the `friction-judge` subagent via the Agent tool (see
   Billing/auth constraint above; NOT a script-level API call) — with a
   prompt like: "Here's a friction excerpt from a coding session. Is this
   (a) a real, generalizable preference/rule, (b) a one-off correction not
   worth capturing, or (c) unclear? If (a), phrase it as a single CLAUDE.md
   bullet."
4. `cluster_friction.py` groups the resulting rules:
   - Fuzzy-dedupe similar rules within a project
   - If a semantically similar rule appears in 2+ distinct projects →
     tag as GLOBAL candidate
   - Otherwise → tag as LOCAL to that project
5. `render_report.py` prints:
   ```
   === GLOBAL suggestions (~/.claude/CLAUDE.md) ===
   + Always activate venv before running Python commands
     (seen in: svdoc, rental-autopilot, home-ai-agent)

   === svdoc ===
   + Use pyslang, not a hand-rolled parser, for SystemVerilog tokenization

   === PlaneChat ===
   + BLE gossip mesh is the only viable transport — don't re-litigate WiFi Direct
   ```
   Plain text diff-style output. No auto-apply. No file writes in Phase 1.

## Phase 2

- Refine subagent context handling — Phase 1 already dispatches
  `friction-judge` via the Agent tool, so Phase 2 is about tightening what
  gets loaded into its context (only the ±2-turn excerpts, not full
  sessions) and batching multiple candidates per dispatch to cut overhead.
- Smarter clustering (embedding-based similarity instead of fuzzy string
  match, if it's worth the complexity — evaluate after Phase 1 shows real
  output quality).

## Phase 3

- Publish to a Git-based marketplace repo (separate `marketplace.json`,
  not inside this plugin) so it's installable via `claude plugin install`.
- Add `hooks/hooks.json` for an optional session-end auto-trigger of the
  scan (still print-only, never auto-apply).
- `--dry-run-verbose` flag to show which heuristic matched each candidate,
  for debugging false positives.

## Non-goals (for now)

- No auto-apply of diffs, ever, without an explicit future opt-in.
- No cloud sync / shared team memory — this is single-user, local-only.
- No attempt to fix the path-encoding collision bug itself — just avoid
  relying on it as a data source.

## Open questions to resolve during Phase 1 build

- What's a reasonable token budget per judgment call? (Keep excerpts short —
  ±2 turns, not full sessions.)
- Rate-limit / batch size for scanning dozens of projects' worth of JSONL —
  may need a progress indicator for a first-run full scan.
- Should CLAUDE.md's own git history (if present) be used to detect what's
  ALREADY been addressed, so we don't re-suggest rules you already added?
  (Recommended: yes, diff current CLAUDE.md content against candidate rules
  before including them in the report — skip near-duplicates.)