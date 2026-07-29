#!/usr/bin/env python3
"""Scan a session for friction candidates. Accepts a session-archiver
archive file (~/.claude-archive/<project>/<session-id>.json) or, as a
fallback, a raw transcript (.jsonl). Archive files with a "subagents"
array (schema_version 2+) are scanned per-agent as well as the main
transcript; each candidate is tagged with its source "agent_id" (None
for the main session).

Matches patterns documented in references/friction-patterns.md:
correction phrases, explicit rule statements (user-authored turns only -
see _is_human_turn), and repeated clarifying questions (fuzzy match on
assistant turns).

Pure local processing - no network calls.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path

CORRECTION_PATTERNS = [
    r"no,?\s+actually",
    r"that'?s not what I",
    r"I meant",
    r"don'?t do that",
    r"^stop\b",
    r"undo that",
    r"that'?s wrong",
    r"not what I (asked|meant|wanted)",
]

RULE_PATTERNS = [
    r"\balways\b",
    r"\bnever\b",
    r"from now on",
    r"remember that",
    r"don'?t ever",
]

SIMILARITY_THRESHOLD = 0.6
CONTEXT_TURNS = 2


def _text_of(turn: dict) -> str:
    content = turn.get("message", {}).get("content", turn.get("content", ""))
    if isinstance(content, list):
        return " ".join(
            block.get("text", "") for block in content if isinstance(block, dict)
        )
    return content if isinstance(content, str) else ""


def _role_of(turn: dict) -> str:
    return turn.get("message", {}).get("role", turn.get("role", ""))


def _is_human_turn(turn: dict) -> bool:
    """True only for a turn the user actually typed - not Stop-hook
    feedback or other synthetic content injected as a user-role message.
    Real transcripts mark synthetic user-role turns with "isMeta": true
    (confirmed by inspecting a raw Stop-hook feedback line during review)
    and mark assistant turns driven by a skill/plugin with
    attributionSkill/attributionPlugin - reject either."""
    if _role_of(turn) != "user":
        return False
    if turn.get("isMeta"):
        return False
    if turn.get("attributionSkill") or turn.get("attributionPlugin"):
        return False
    origin = turn.get("origin")
    if origin is not None and origin.get("kind") != "human":
        return False
    return True


def load_transcripts(session_path: Path) -> list[tuple[str | None, list[dict]]]:
    """Read turns from either a raw transcript (.jsonl, line-per-turn) or a
    session-archiver archive file (.json, turns wrapped under "turns").

    Returns a list of (agent_id, turns) pairs: the main session first
    (agent_id None), followed by one entry per subagent run (schema_version
    2+ archives only - subagents get their own turn indices/context windows
    rather than being flattened into the main transcript)."""
    if session_path.suffix == ".json":
        archive = json.loads(session_path.read_text())
        transcripts = [(None, archive.get("turns", []))]
        for subagent in archive.get("subagents", []):
            transcripts.append((subagent.get("agent_id"), subagent.get("turns", [])))
        return transcripts

    turns = []
    with session_path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                turns.append(json.loads(line))
    return [(None, turns)]


def find_candidates(turns: list[dict]) -> list[dict]:
    candidates = []
    correction_re = re.compile("|".join(CORRECTION_PATTERNS), re.IGNORECASE)
    rule_re = re.compile("|".join(RULE_PATTERNS), re.IGNORECASE)

    for i, turn in enumerate(turns):
        text = _text_of(turn)

        if _is_human_turn(turn) and text:
            kind = None
            if rule_re.search(text):
                kind = "explicit_rule"
            elif correction_re.search(text):
                kind = "correction"
            if kind:
                lo, hi = (
                    max(0, i - CONTEXT_TURNS),
                    min(len(turns), i + CONTEXT_TURNS + 1),
                )
                candidates.append(
                    {
                        "kind": kind,
                        "turn_index": i,
                        "text": text,
                        "context": turns[lo:hi],
                    }
                )

    assistant_questions = [
        (i, text)
        for i, t in enumerate(turns)
        if _role_of(t) == "assistant" and (text := _text_of(t)).strip().endswith("?")
    ]
    for a in range(len(assistant_questions)):
        for b in range(a + 1, len(assistant_questions)):
            i1, t1 = assistant_questions[a]
            i2, t2 = assistant_questions[b]
            if difflib.SequenceMatcher(None, t1, t2).ratio() > SIMILARITY_THRESHOLD:
                lo, hi = (
                    max(0, i1 - CONTEXT_TURNS),
                    min(len(turns), i2 + CONTEXT_TURNS + 1),
                )
                candidates.append(
                    {
                        "kind": "repeated_question",
                        "turn_index": i1,
                        "text": t1,
                        "context": turns[lo:hi],
                    }
                )

    return candidates


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "session",
        type=Path,
        help="Path to a session archive (.json) or raw transcript (.jsonl)",
    )
    args = parser.parse_args()

    if not args.session.exists():
        # history.jsonl (per-prompt log, never pruned) can reference session
        # ids whose archive/transcript file doesn't exist yet or was pruned
        # before session-archiver's backfill ran - this is routine, not an error.
        print(
            f"skipping {args.session}: archive/transcript file not found",
            file=sys.stderr,
        )
        print(json.dumps([]))
        return

    candidates = []
    for agent_id, turns in load_transcripts(args.session):
        for candidate in find_candidates(turns):
            candidate["agent_id"] = agent_id
            candidates.append(candidate)
    print(json.dumps(candidates, indent=2))


def _self_check() -> None:
    import tempfile

    fixture = [
        {"message": {"role": "user", "content": "add a login button"}},
        {
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "Added it."}],
            }
        },
        {
            "message": {
                "role": "user",
                "content": "no, actually put it in the navbar, not the footer",
            }
        },
        {
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "Moved to navbar."}],
            }
        },
        {
            "message": {
                "role": "user",
                "content": "always run tests before committing from now on",
            }
        },
        {
            "message": {
                "role": "user",
                "content": "Stop hook feedback:\n\nalways run lint checks in this order, never skip ahead",
            },
            "isMeta": True,
        },
        {
            "message": {
                "role": "user",
                "content": "always rebuild the cache from now on",
            },
            "origin": {"kind": "hook"},
        },
    ]
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
        for entry in fixture:
            f.write(json.dumps(entry) + "\n")
        path = Path(f.name)

    turns = load_transcripts(path)[0][1]
    path.unlink()
    candidates = find_candidates(turns)

    kinds = {c["kind"] for c in candidates}
    assert "correction" in kinds, candidates
    assert "explicit_rule" in kinds, candidates
    assert not any("lint checks in this order" in c["text"] for c in candidates), (
        candidates
    )
    assert not any("rebuild the cache" in c["text"] for c in candidates), candidates
    print("heuristic_filter self-check OK", file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--self-check":
        _self_check()
    else:
        main()
