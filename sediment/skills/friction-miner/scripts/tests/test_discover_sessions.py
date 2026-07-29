import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from discover_sessions import discover


def _write_history(tmp_path, entries):
    path = tmp_path / "history.jsonl"
    with path.open("w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")
    return path


def test_missing_history_file_returns_empty(tmp_path):
    assert discover(tmp_path / "does-not-exist.jsonl") == {}


def test_single_project_single_session(tmp_path):
    path = _write_history(tmp_path, [{"project": "/repo/a", "session_id": "s1"}])
    assert discover(path) == {"/repo/a": ["s1"]}


def test_multiple_projects_multiple_sessions(tmp_path):
    path = _write_history(
        tmp_path,
        [
            {"project": "/repo/a", "session_id": "s1"},
            {"project": "/repo/a", "session_id": "s2"},
            {"project": "/repo/b", "session_id": "s3"},
        ],
    )
    assert discover(path) == {"/repo/a": ["s1", "s2"], "/repo/b": ["s3"]}


def test_duplicate_session_id_not_double_counted(tmp_path):
    path = _write_history(
        tmp_path,
        [
            {"project": "/repo/a", "session_id": "s1"},
            {"project": "/repo/a", "session_id": "s1"},
        ],
    )
    assert discover(path) == {"/repo/a": ["s1"]}


def test_entries_missing_project_or_session_id_are_skipped(tmp_path):
    path = _write_history(
        tmp_path,
        [
            {"project": "/repo/a"},
            {"session_id": "s1"},
            {"project": "/repo/b", "session_id": "s2"},
        ],
    )
    assert discover(path) == {"/repo/b": ["s2"]}
