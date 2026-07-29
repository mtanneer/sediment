# Friction patterns

Heuristic rules `heuristic_filter.py` matches against user turns in a
session transcript. Each match produces one candidate, bundled with ±2
turns of surrounding context.

## Correction phrases (regex, case-insensitive)

- `no,?\s+actually`
- `that'?s not what I`
- `I meant`
- `don'?t do that`
- `^stop\b`
- `undo that`
- `that'?s wrong`
- `not what I (asked|meant|wanted)`

## Explicit rule statements (regex, case-insensitive)

- `\balways\b`
- `\bnever\b`
- `from now on`
- `remember that`
- `don'?t ever`

These are the highest-value hits — the user is directly stating a durable
preference, not just reacting to one mistake.

## Provenance gate (structural, applies to both patterns above)

`explicit_rule`/`correction` only fire on turns that pass `_is_human_turn()` -
a `user`-role turn with `isMeta` not set (Stop-hook feedback is marked
`"isMeta": true`, confirmed from a real transcript), no
`attributionSkill`/`attributionPlugin` set, and no `origin.kind` other
than `"human"`. This excludes Stop-hook feedback and other synthetic
content that gets posted as a `user`-role message but was never actually
typed by the user - such content can contain rule-shaped words ("always",
"order matters") that would otherwise false-positive as a real user
preference.

Dropped: a prior "reverted tool calls" structural heuristic (same file
edited twice within N turns) produced zero real rules in testing (61 of
79 candidates in one real scan, 0 became a judged RULE) and had no way
to check whether a user or Claude's own tool-loop drove the re-edit -
removed rather than patched, since a purely structural signal like this
can't be given a meaningful provenance check without inventing an
unproven heuristic.

## Repeated clarifying questions (structural, not regex)

Two or more assistant turns in the same session whose text similarity
(`difflib.SequenceMatcher` ratio) exceeds 0.6, taken as Claude asking
essentially the same question twice — a sign the user's answer wasn't
captured as a rule anywhere.
