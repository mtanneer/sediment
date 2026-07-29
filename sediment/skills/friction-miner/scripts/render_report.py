#!/usr/bin/env python3
"""Render the clustered friction output (from cluster_friction.py) as a
plain-text diff-style report."""
import argparse
import json
import sys
from pathlib import Path


def render(clustered: dict) -> str:
    lines = []

    if clustered.get("global"):
        lines.append("=== GLOBAL suggestions (~/.claude/CLAUDE.md) ===")
        for entry in clustered["global"]:
            projects = ", ".join(Path(p).name for p in entry["projects"])
            lines.append(f"+ {entry['rule']}")
            lines.append(f"  (seen in: {projects})")
        lines.append("")

    for project, rules in clustered.get("local", {}).items():
        lines.append(f"=== {Path(project).name} ===")
        for rule in rules:
            lines.append(f"+ {rule}")
        lines.append("")

    if not clustered.get("global") and not clustered.get("local"):
        lines.append("No friction candidates found.")

    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("clustered_json", type=Path, help="Path to cluster_friction.py output")
    args = parser.parse_args()

    clustered = json.loads(args.clustered_json.read_text())
    sys.stdout.write(render(clustered))


def _self_check() -> None:
    clustered = {
        "global": [{"rule": "Always activate venv before running Python commands",
                     "projects": ["/repo/svdoc", "/repo/rental-autopilot", "/repo/home-ai-agent"]}],
        "local": {"/repo/svdoc": ["Use pyslang, not a hand-rolled parser, for SystemVerilog tokenization"]},
    }
    out = render(clustered)
    assert "=== GLOBAL suggestions" in out, out
    assert "svdoc, rental-autopilot, home-ai-agent" in out, out
    assert "=== svdoc ===" in out, out
    print("render_report self-check OK", file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--self-check":
        _self_check()
    else:
        main()
