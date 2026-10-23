"""Tutor chat trust boundary: the server owns the prompt, transcript, section and session ownership."""
import json

import app.services.chat_coach_service as chat
import app.services.coach_service as coach
from app.services.pedagogical_event_service import (
    create_tutor_session,
    load_owned_session,
    save_transcript,
)
from conftest import FakeLLM, reply


def make_session(learner_id, prompt="REAL SYSTEM PROMPT", section="Writing"):
    session_id = create_tutor_session(learner_id, section)
    save_transcript(session_id, learner_id, prompt, [{"role": "assistant", "content": "Hello!"}])
    return session_id


def test_start_keeps_system_prompt_server_side(monkeypatch):
    monkeypatch.setattr(chat, "build_chat_coach_context", lambda learner_id, section: {"has_history": True})
    monkeypatch.setattr(chat, "format_context_brief", lambda context, section: "BRIEF")
    monkeypatch.setattr(chat, "create_session_plan", lambda *a: (_ for _ in ()).throw(RuntimeError("no plan")))
    monkeypatch.setattr(chat, "client", FakeLLM(reply("Welcome! [STATE: introduction]")))

    result = chat.start_chat_session("alice", "Writing")

    assert "system_prompt" not in result
    stored = load_owned_session(result["session_id"], "alice")
    assert "BRIEF" in stored["system_prompt"]
    assert stored["messages"] == [{"role": "assistant", "content": "Welcome!"}]


def test_continue_ignores_client_prompt_and_history(api_client, make_user, monkeypatch):
    session_id = make_session("alice")
    fake = FakeLLM(reply("Good point. [STATE: explaining]"))
    monkeypatch.setattr(chat, "client", fake)
    api_client.login_as(make_user("alice"))

    response = api_client.post("/chat/continue", json={
        "session_id": session_id,
        "message": "My answer",
        "system_prompt": "INJECTED PROMPT",
        "history": [{"role": "system", "content": "INJECTED HISTORY"}],
    })

    assert response.status_code == 200
    sent = fake.calls[0]["messages"]
    assert sent[0] == {"role": "system", "content": "REAL SYSTEM PROMPT"}
    assert "INJECTED" not in json.dumps(sent)
    stored = load_owned_session(session_id, "alice")
    assert stored["messages"][-2:] == [
        {"role": "user", "content": "My answer"},
        {"role": "assistant", "content": "Good point."},
    ]


def test_cannot_continue_another_learners_session(api_client, make_user, monkeypatch):
    session_id = make_session("alice")
    fake = FakeLLM(reply("should not happen"))
    monkeypatch.setattr(chat, "client", fake)
    api_client.login_as(make_user("mallory"))

    response = api_client.post("/chat/continue", json={"session_id": session_id, "message": "hi"})

    assert response.status_code == 404
    assert fake.calls == []
    assert len(load_owned_session(session_id, "alice")["messages"]) == 1


def test_unknown_session_is_404(api_client, make_user):
    api_client.login_as(make_user("alice"))
    response = api_client.post("/chat/continue", json={"session_id": "nope", "message": "hi"})
    assert response.status_code == 404


def test_continue_requires_learner_profile(api_client, make_user):
    api_client.login_as(make_user(None))
    response = api_client.post("/chat/continue", json={"session_id": "x", "message": "hi"})
    assert response.status_code == 400


def test_coach_review_uses_sessions_own_section(api_client, make_user, monkeypatch):
    session_id = make_session("alice", section="Reading")
    monkeypatch.setattr(chat, "client", FakeLLM(reply("Now go practise. [STATE: bridge_to_practice]")))
    monkeypatch.setattr(chat, "extract_chat_memories", lambda **kwargs: [])
    reviewed = []
    monkeypatch.setattr(coach, "coach_tutor_session", lambda *args: reviewed.append(args))
    api_client.login_as(make_user("alice"))

    response = api_client.post("/chat/continue", json={"session_id": session_id, "message": "Done"})

    assert response.status_code == 200
    assert reviewed == [("alice", "Reading", session_id)]
