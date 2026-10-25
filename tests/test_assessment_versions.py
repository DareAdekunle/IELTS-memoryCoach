"""Every scored attempt records how it was scored, and a new method gets a new version."""
import json
from pathlib import Path

import pytest

import app.services.assessment_versions as versions
from app.db.database import SessionLocal
from app.db.models import AssessmentVersion, PracticeAttempt
from app.services.memory_service import save_attempt, save_reading_attempt
from app.services.reading_service import evaluate_reading_attempt

PASSAGES = json.loads((Path(__file__).resolve().parents[1] / "app" / "data" / "reading_passages.json").read_text())


@pytest.fixture(autouse=True)
def fresh_registry():
    versions._known.clear()


def rows(model):
    db = SessionLocal()
    try:
        return db.query(model).all()
    finally:
        db.close()


def test_same_setup_registers_once():
    a = versions.register("Writing", "llm", "qwen-plus", {"prompt": "abc"})
    versions._known.clear()
    b = versions.register("Writing", "llm", "qwen-plus", {"prompt": "abc"})
    assert a == b and len(rows(AssessmentVersion)) == 1


@pytest.mark.parametrize("change", [
    {"model": "qwen3.5-plus"}, {"components": {"prompt": "xyz"}}, {"method": "answer_key"}, {"section": "Speaking"},
])
def test_any_change_in_method_gives_a_new_version(change):
    base = {"section": "Writing", "method": "llm", "model": "qwen-plus", "components": {"prompt": "abc"}}
    assert versions.register(**base) != versions.register(**{**base, **change})


def test_reading_attempt_records_its_answer_key_version():
    result = evaluate_reading_attempt(PASSAGES[0], {})
    attempt_id = save_reading_attempt("alice", result)

    attempt = next(a for a in rows(PracticeAttempt) if a.attempt_id == attempt_id)
    version = next(v for v in rows(AssessmentVersion) if v.version_id == attempt.assessment_version_id)
    assert (version.section, version.method, version.model) == ("Reading", "answer_key", None)
    assert set(json.loads(version.components_json)) == {"answer_key", "matcher"}


def test_writing_attempt_records_model_and_prompt(monkeypatch):
    import app.services.scoring_service as scoring
    reply = {"overall_feedback": "ok", "scores": {"grammar": 3}, "strengths": [], "weaknesses": [],
             "recommended_next_step": "practise"}
    monkeypatch.setattr(scoring, "call_qwen_for_json", lambda prompt: json.dumps(reply))

    result = scoring.evaluate_writing("Prompt", "Essay text")
    attempt_id = save_attempt("alice", "Writing", "Agree or Disagree", "Prompt", "Essay text", result, "ok")

    attempt = next(a for a in rows(PracticeAttempt) if a.attempt_id == attempt_id)
    version = next(v for v in rows(AssessmentVersion) if v.version_id == attempt.assessment_version_id)
    assert (version.section, version.method, version.model) == ("Writing", "llm", scoring.QWEN_MODEL)
    assert set(json.loads(version.components_json)) == {"prompt", "rubric"}
