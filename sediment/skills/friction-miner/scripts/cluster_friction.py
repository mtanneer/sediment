#!/usr/bin/env python3
"""Cluster judged friction rules: fuzzy-dedupe, tag LOCAL vs GLOBAL.

Input: JSON list of {project_path, rule} (rule = one CLAUDE.md bullet,
produced by the friction-judge subagent - not by this script).

A rule appearing (fuzzy-matched) in 2+ distinct projects is tagged GLOBAL;
otherwise it stays LOCAL to each project it appeared in.
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path

SIMILARITY_THRESHOLD = 0.65
GLOBAL_PROJECT_COUNT = 2


def cluster(rules: list[dict]) -> dict:
    groups: list[dict] = []  # {"texts": [str], "projects": set[str]}

    for entry in rules:
        text, project = entry["rule"], entry["project_path"]
        match = next(
            (
                g
                for g in groups
                if any(
                    difflib.SequenceMatcher(None, seen, text).ratio()
                    > SIMILARITY_THRESHOLD
                    for seen in g["texts"]
                )
            ),
            None,
        )
        if match:
            match["texts"].append(text)
            match["projects"].add(project)
        else:
            groups.append({"texts": [text], "projects": {project}})

    global_rules = []
    local_rules: dict[str, list[str]] = {}
    for g in groups:
        if len(g["projects"]) >= GLOBAL_PROJECT_COUNT:
            global_rules.append(
                {"rule": g["texts"][0], "projects": sorted(g["projects"])}
            )
        else:
            for p in g["projects"]:
                local_rules.setdefault(p, []).append(g["texts"][0])

    return {"global": global_rules, "local": local_rules}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "rules_json", type=Path, help="Path to JSON list of {project_path, rule}"
    )
    args = parser.parse_args()

    rules = json.loads(args.rules_json.read_text())
    print(json.dumps(cluster(rules), indent=2))


def _self_check() -> None:
    rules = [
        {
            "project_path": "/repo/a",
            "rule": "Always activate venv before running Python commands",
        },
        {
            "project_path": "/repo/b",
            "rule": "Always activate the venv before running Python commands",
        },
        {
            "project_path": "/repo/c",
            "rule": "Activate venv first, always, before Python commands",
        },
        {
            "project_path": "/repo/svdoc",
            "rule": "Use pyslang, not a hand-rolled parser, for SystemVerilog",
        },
    ]
    result = cluster(rules)
    assert len(result["global"]) == 1, result
    assert set(result["global"][0]["projects"]) == {"/repo/a", "/repo/b", "/repo/c"}, (
        result
    )
    assert "/repo/svdoc" in result["local"], result
    print("cluster_friction self-check OK", file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--self-check":
        _self_check()
    else:
        main()
