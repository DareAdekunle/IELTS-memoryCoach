"""
Which method produced a score.

Every scored attempt records an assessment version: the section, the method
(an LLM evaluator or a deterministic answer key), the model, and content
digests of the prompt / rubric / answer key used. When any of those change,
new attempts get a new version, so scores from different methods are never
silently mixed (e.g. when the Writing scorer is replaced).
"""
import hashlib
import json
import os

from sqlalchemy.exc import IntegrityError

from app.db.database import SessionLocal
from app.db.models import AssessmentVersion

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_known: set[str] = set()


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:10]


def file_digest(relative_path: str) -> str:
    with open(os.path.join(APP_DIR, relative_path), encoding="utf-8") as f:
        return digest(f.read())


def register(section: str, method: str, model: str | None, components: dict) -> str:
    """Returns the version id for this scoring setup, recording it on first use."""
    descriptor = {"section": section, "method": method, "model": model or "", "components": components}
    version_id = digest(json.dumps(descriptor, sort_keys=True))
    if version_id in _known:
        return version_id
    db = SessionLocal()
    try:
        if not db.get(AssessmentVersion, version_id):
            db.add(AssessmentVersion(
                version_id=version_id, section=section, method=method, model=model,
                components_json=json.dumps(components, sort_keys=True),
            ))
            db.commit()
    except IntegrityError:  # registered concurrently by another worker
        db.rollback()
    finally:
        db.close()
    _known.add(version_id)
    return version_id


def llm_version(section: str, model: str, prompt_file: str, **extra: str) -> str:
    return register(section, "llm", model, {"prompt": file_digest(f"prompts/{prompt_file}"), **extra})


def answer_key_version(section: str, data_file: str) -> str:
    return register(section, "answer_key", None, {
        "answer_key": file_digest(f"data/{data_file}"),
        "matcher": file_digest("services/answer_matching.py"),
    })
