#!/usr/bin/env python3
"""Read ~/.claude/history.jsonl and list {project_path, session_ids[]}.

Uses history.jsonl as the authoritative index rather than decoding
~/.claude/projects/<encoded-path>/ folder names, which is lossy (hyphenated
directories collide - anthropics/claude-code#7009, #21085).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path


def discover(history_path: Path) -> dict[str, list[str]]:
    projects: dict[str, list[str]] = defaultdict(list)
    if not history_path.exists():
        return {}
    with history_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            project = (
                entry.get("project") or entry.get("cwd") or entry.get("project_path")
            )
            session_id = (
                entry.get("session_id") or entry.get("sessionId") or entry.get("id")
            )
            if project and session_id and session_id not in projects[project]:
                projects[project].append(session_id)
    return dict(projects)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--history",
        type=Path,
        default=Path.home() / ".claude" / "history.jsonl",
        help="Path to history.jsonl",
    )
    parser.add_argument("--project", help="Only include this project path")
    args = parser.parse_args()

    projects = discover(args.history)
    if args.project:
        projects = {k: v for k, v in projects.items() if args.project in k}

    print(
        json.dumps(
            [{"project_path": p, "session_ids": ids} for p, ids in projects.items()],
            indent=2,
        )
    )


def _self_check() -> None:
    import tempfile

    fixture = [
        {"project": "/repo/a", "session_id": "s1"},
        {"project": "/repo/a", "session_id": "s2"},
        {"project": "/repo/b", "session_id": "s3"},
        {
            "project": "/repo/a",
            "session_id": "s1",
        },  # duplicate, should not double-count
    ]
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
        for entry in fixture:
            f.write(json.dumps(entry) + "\n")
        path = Path(f.name)

    result = discover(path)
    path.unlink()

    assert result == {"/repo/a": ["s1", "s2"], "/repo/b": ["s3"]}, result
    print("discover_sessions self-check OK", file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--self-check":
        _self_check()
    else:
        main()
