"""One learner's memories must never appear in another learner's results."""
import uuid

import pytest

from app.db.database import SessionLocal
from app.db.models import LearnerMemory
from app.services.memory_service import get_all_memories, get_relevant_memories


def add_memory(learner_id, text, section="Writing", memory_type="weakness"):
    db = SessionLocal()
    try:
        db.add(LearnerMemory(
            memory_id=str(uuid.uuid4()), learner_id=learner_id, section=section,
            skill="Cohesion", memory_type=memory_type, memory_text=text, confidence=0.9,
        ))
        db.commit()
    finally:
        db.close()


@pytest.fixture
def two_learners():
    add_memory("alice", "ALICE overuses 'moreover'")
    add_memory("bob", "BOB SECRET skips conclusions")
    add_memory("bob", "BOB SECRET strong vocabulary", memory_type="strength")


def texts(memories):
    return " ".join(m["memory_text"] for m in memories)


def test_relevant_memories_are_learner_scoped(two_learners):
    result = texts(get_relevant_memories("alice", "Writing", limit=10))
    assert "ALICE" in result and "BOB" not in result


def test_dashboard_memories_are_learner_scoped(two_learners):
    grouped = get_all_memories("alice")
    result = texts(grouped["active"] + grouped["archived"])
    assert "ALICE" in result and "BOB" not in result


@pytest.mark.parametrize("path", ["/memory/all", "/memory/active", "/memory/timeline"])
def test_memory_api_only_returns_callers_memories(two_learners, api_client, make_user, path):
    api_client.login_as(make_user("alice"))
    response = api_client.get(path)
    assert response.status_code == 200
    assert "BOB SECRET" not in response.text


def test_memory_api_without_profile_returns_nothing(two_learners, api_client, make_user):
    api_client.login_as(make_user(None))
    assert api_client.get("/memory/all").json() == {"active": [], "archived": [], "stats": {}}
