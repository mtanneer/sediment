import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from render_report import render


def test_global_section_renders_with_seen_in_list():
    clustered = {
        "global": [{"rule": "Always activate venv first", "projects": ["/repo/a", "/repo/b", "/repo/c"]}],
        "local": {},
    }
    out = render(clustered)
    assert "=== GLOBAL suggestions (~/.claude/CLAUDE.md) ===" in out
    assert "+ Always activate venv first" in out
    assert "(seen in: a, b, c)" in out


def test_local_section_renders_grouped_per_project():
    clustered = {"global": [], "local": {"/repo/svdoc": ["Use pyslang for parsing"]}}
    out = render(clustered)
    assert "=== svdoc ===" in out
    assert "+ Use pyslang for parsing" in out


def test_both_global_and_local_present():
    clustered = {
        "global": [{"rule": "Always activate venv first", "projects": ["/repo/a", "/repo/b", "/repo/c"]}],
        "local": {"/repo/svdoc": ["Use pyslang for parsing"]},
    }
    out = render(clustered)
    assert "GLOBAL suggestions" in out
    assert "=== svdoc ===" in out


def test_empty_input_reports_no_candidates():
    clustered = {"global": [], "local": {}}
    out = render(clustered)
    assert out.strip() == "No friction candidates found."
