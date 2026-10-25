"""Reading/Listening marking is deterministic, and the answer keys are internally consistent."""
import json
import re
from pathlib import Path

import pytest

from app.services.answer_matching import check_answer, count_words, normalise_answer
from app.services.listening_service import evaluate_listening_attempt, public_track
from app.services.reading_service import evaluate_reading_attempt, public_passage

DATA = Path(__file__).resolve().parents[1] / "app" / "data"
PASSAGES = json.loads((DATA / "reading_passages.json").read_text())
TRACKS = json.loads((DATA / "listening_tracks.json").read_text())


GAP_TYPES = {"short_answer", "form_completion"}


def gap_questions(items, text_key):
    for item in items:
        for q in item["questions"]:
            if q["question_type"] in GAP_TYPES:
                yield item, q, item[text_key]


GAPS = list(gap_questions(PASSAGES, "passage")) + list(gap_questions(TRACKS, "script"))
IDS = [f"{item.get('passage_id') or item.get('track_id')}-{q['question_id']}" for item, q, _ in GAPS]


# ─── Matcher ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("response", ["peer-reviewed", "Peer reviewed", "PEER REVIEWED.", " peer  reviewed "])
def test_formatting_differences_are_accepted(response):
    assert check_answer(response, ["peer-reviewed"], 3)["is_correct"]


@pytest.mark.parametrize("response,expected", [("one hour", True), ("1 hour", True), ("an hour", False)])
def test_number_words_and_articles(response, expected):
    assert check_answer(response, ["one hour"], 2)["is_correct"] is expected


def test_no_partial_or_contains_matching():
    accepted = ["Michael Carter"]
    assert not check_answer("Carter", accepted, 3)["is_correct"]
    assert not check_answer("his name is Michael Carter", accepted, 10)["is_correct"]


def test_word_limit_is_enforced_even_if_answer_is_inside():
    result = check_answer("the library study room upstairs", ["library study room"], 3)
    assert not result["is_correct"] and result["over_limit"]


def test_numbers_do_not_count_towards_the_word_limit():
    assert count_words("18 to 254 days") == 2
    assert count_words("tree-lined streets") == 2
    assert check_answer("14 March 1988", ["14 March 1988"], 1)["is_correct"]


def test_empty_answer_is_wrong():
    assert check_answer("   ", ["anything"], 3) == {"is_correct": False, "matched_answer": "", "over_limit": False}


# ─── Answer key consistency ───────────────────────────────────────────────────

@pytest.mark.parametrize("item,q,text", GAPS, ids=IDS)
def test_every_gap_question_has_a_word_limit_its_answers_respect(item, q, text):
    assert isinstance(q.get("word_limit"), int) and 1 <= q["word_limit"] <= 3
    for answer in [q["answer"], *q.get("acceptable_answers", [])]:
        assert answer.strip(), "empty accepted answer"
        assert count_words(answer) <= q["word_limit"], f"{answer!r} exceeds the {q['word_limit']}-word limit"
        assert not re.search(r"\bany (one|two|three) of\b", answer, re.I), "list answers belong in acceptable_answers"


@pytest.mark.parametrize("item,q,text", GAPS, ids=IDS)
def test_answers_come_from_the_text(item, q, text):
    """
    IELTS gap answers are words from the passage/recording. Reading: every accepted
    answer must appear. Listening: the main key must have been said (variants may be
    legitimate spellings or abbreviations). Numbers/dates may be written differently
    from how they are spoken, so answers containing digits are skipped.
    """
    source = f" {normalise_answer(text)} "
    answers = [q["answer"], *q.get("acceptable_answers", [])] if "passage_id" in item else [q["answer"]]
    for answer in answers:
        if re.search(r"\d", answer):
            continue
        assert f" {normalise_answer(answer)} " in source, f"{answer!r} does not appear in the text"


# ─── Scoring + exposure ───────────────────────────────────────────────────────

def test_reading_short_answers_are_marked_without_a_model(monkeypatch):
    import app.services.qwen_service as qwen
    monkeypatch.setattr(qwen, "call_qwen_for_json", lambda *a, **k: pytest.fail("model called"))
    passage = next(p for p in PASSAGES if p["passage_id"] == "reading_007")
    answers = {"q8": "urgency", "q9": "sweet", "q10": "the colour blue is linked to trust"}

    result = evaluate_reading_attempt(passage, answers)

    by_id = {r["question_id"]: r for r in result["question_results"]}
    assert by_id["q8"]["is_correct"] and by_id["q8"]["max_score"] == 1
    assert not by_id["q9"]["is_correct"]
    assert not by_id["q10"]["is_correct"] and "longer than the limit" in by_id["q10"]["feedback"]


def test_listening_rejects_answers_that_merely_contain_the_key():
    track = next(t for t in TRACKS if t["track_id"] == "listening_003")
    result = evaluate_listening_attempt(track, {"q5": "we meet in the library study room on Friday"})
    q5 = next(r for r in result["question_results"] if r["question_id"] == "q5")
    assert not q5["is_correct"]


def test_answer_keys_and_transcript_are_not_sent_to_the_browser():
    passage, track = public_passage(PASSAGES[0]), public_track(TRACKS[0])
    for q in passage["questions"] + track["questions"]:
        assert not {"answer", "acceptable_answers", "explanation"} & set(q)
    assert "script" not in track
    assert passage["passage"] and track["questions"]
