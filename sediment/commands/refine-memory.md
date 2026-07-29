---
description: Scan past Claude Code sessions (all projects by default) for friction and suggest CLAUDE.md diffs. Flags: --project <name>, --since <date>, --dev (plugin development only).
---

Invoke the `friction-miner` skill (Skill tool, `skill: "friction-miner"`) and
pass `$ARGUMENTS` through as-is via the `args` parameter. The skill parses
the flags itself — do not attempt to parse `$ARGUMENTS` here.
