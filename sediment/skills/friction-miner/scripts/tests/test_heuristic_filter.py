import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from heuristic_filter import find_candidates

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "heuristic_filter.py"


def _user_turn(text, **extra):
    turn = {"message": {"role": "user", "content": text}}
    turn.update(extra)
    return turn


def _assistant_turn(text):
    return {"message": {"role": "assistant", "content": [{"type": "text", "text": text}]}}


def test_correction_pattern_on_human_turn_is_detected():
    turns = [_user_turn("no, actually put it in the navbar")]
    candidates = find_candidates(turns)
    assert len(candidates) == 1
    assert candidates[0]["kind"] == "correction"


def test_explicit_rule_pattern_on_human_turn_is_detected():
    turns = [_user_turn("always activate the venv before running python")]
    candidates = find_candidates(turns)
    assert len(candidates) == 1
    assert candidates[0]["kind"] == "explicit_rule"


def test_turn_matching_neither_pattern_produces_nothing():
    turns = [_user_turn("add a login button")]
    assert find_candidates(turns) == []


def test_ismeta_turn_is_rejected_even_with_rule_shaped_text():
    turns = [_user_turn("Stop hook feedback:\n\nalways run checks in order", isMeta=True)]
    assert find_candidates(turns) == []


def test_attribution_skill_turn_is_rejected():
    turns = [_user_turn("always rebuild the cache", attributionSkill="ralph-loop:ralph-loop")]
    assert find_candidates(turns) == []


def test_attribution_plugin_turn_is_rejected():
    turns = [_user_turn("never skip the lint step", attributionPlugin="ralph-loop")]
    assert find_candidates(turns) == []


def test_non_human_origin_kind_is_rejected():
    turns = [_user_turn("always run secret-scan first", origin={"kind": "hook"})]
    assert find_candidates(turns) == []


def test_plain_turn_with_no_provenance_fields_is_still_detected():
    turns = [_user_turn("never use any in typescript")]
    candidates = find_candidates(turns)
    assert len(candidates) == 1
    assert candidates[0]["kind"] == "explicit_rule"


def test_origin_kind_human_is_accepted():
    turns = [_user_turn("always run tests first", origin={"kind": "human"})]
    candidates = find_candidates(turns)
    assert len(candidates) == 1


def test_repeated_similar_assistant_questions_detected():
    turns = [
        _assistant_turn("Should I use React or Vue for this?"),
        _user_turn("React"),
        _assistant_turn("Should I use React or Vue for the component?"),
    ]
    candidates = find_candidates(turns)
    kinds = [c["kind"] for c in candidates]
    assert "repeated_question" in kinds


def test_dissimilar_assistant_questions_not_flagged():
    turns = [
        _assistant_turn("Should I use React or Vue for this?"),
        _user_turn("React"),
        _assistant_turn("What port should the server listen on?"),
    ]
    candidates = find_candidates(turns)
    assert not any(c["kind"] == "repeated_question" for c in candidates)


def test_context_window_is_plus_minus_two_turns():
    turns = [
        _user_turn("turn 0"),
        _user_turn("turn 1"),
        _user_turn("always do the thing"),
        _user_turn("turn 3"),
        _user_turn("turn 4"),
        _user_turn("turn 5"),
    ]
    candidates = find_candidates(turns)
    assert len(candidates) == 1
    # ±2 turns around index 2 => turns[0:5] => indices 0,1,2,3,4 (5 turns)
    assert len(candidates[0]["context"]) == 5


def test_context_window_clipped_at_transcript_start():
    turns = [
        _user_turn("always do the thing"),
        _user_turn("turn 1"),
    ]
    candidates = find_candidates(turns)
    assert len(candidates) == 1
    # no turns before index 0, so context is just turns[0:3]
    assert len(candidates[0]["context"]) == 2


def test_cli_missing_session_file_does_not_crash(tmp_path):
    # history.jsonl can reference session ids whose transcript already aged
    # out under Claude Code's default 30-day cleanupPeriodDays retention -
    # the CLI must skip gracefully (empty result, exit 0), not traceback.
    missing = tmp_path / "does-not-exist.jsonl"
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), str(missing)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "[]"
