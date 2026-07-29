import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cluster_friction import cluster


def test_rule_in_three_projects_is_global():
    rules = [
        {"project_path": "/repo/a", "rule": "Always activate venv before running Python commands"},
        {"project_path": "/repo/b", "rule": "Always activate venv before running Python commands"},
        {"project_path": "/repo/c", "rule": "Always activate venv before running Python commands"},
    ]
    result = cluster(rules)
    assert len(result["global"]) == 1
    assert set(result["global"][0]["projects"]) == {"/repo/a", "/repo/b", "/repo/c"}
    assert result["local"] == {}


def test_rule_in_exactly_two_projects_is_global():
    rules = [
        {"project_path": "/repo/a", "rule": "Use ruff for linting"},
        {"project_path": "/repo/b", "rule": "Use ruff for linting"},
    ]
    result = cluster(rules)
    assert len(result["global"]) == 1
    assert set(result["global"][0]["projects"]) == {"/repo/a", "/repo/b"}
    assert result["local"] == {}


def test_fuzzy_matching_across_reworded_phrasings():
    rules = [
        {"project_path": "/repo/a", "rule": "Always activate venv before running Python commands"},
        {"project_path": "/repo/b", "rule": "Always activate the venv before running Python commands"},
        {"project_path": "/repo/c", "rule": "Activate venv first, always, before Python commands"},
    ]
    result = cluster(rules)
    assert len(result["global"]) == 1
    assert set(result["global"][0]["projects"]) == {"/repo/a", "/repo/b", "/repo/c"}


def test_unrelated_rule_stays_in_own_group():
    rules = [
        {"project_path": "/repo/a", "rule": "Always activate venv before running Python commands"},
        {"project_path": "/repo/b", "rule": "Always activate venv before running Python commands"},
        {"project_path": "/repo/c", "rule": "Always activate venv before running Python commands"},
        {"project_path": "/repo/svdoc", "rule": "Use pyslang, not a hand-rolled parser, for SystemVerilog"},
    ]
    result = cluster(rules)
    assert len(result["global"]) == 1
    assert "/repo/svdoc" in result["local"]
    assert result["local"]["/repo/svdoc"] == ["Use pyslang, not a hand-rolled parser, for SystemVerilog"]


def test_single_rule_single_project_is_local():
    rules = [{"project_path": "/repo/a", "rule": "Use ruff for linting"}]
    result = cluster(rules)
    assert result["global"] == []
    assert result["local"] == {"/repo/a": ["Use ruff for linting"]}
