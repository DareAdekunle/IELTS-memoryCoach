"""Agent tools must act for the authenticated learner, never a learner_id the model supplies."""
import json

import pytest

import app.mcp.memory_server as mcp_tools
import app.services.chat_coach_service as chat
import app.services.coach_service as coach
import app.services.telegram_service as telegram
import app.services.whatsapp_service as whatsapp
from app.services.pedagogical_event_service import create_tutor_session, save_transcript
from conftest import FakeLLM, reply, tool_call


def test_tutor_tools_run_for_session_owner(monkeypatch):
    session_id = create_tutor_session("alice", "Writing")
    save_transcript(session_id, "alice", "PROMPT", [{"role": "assistant", "content": "Hi"}])
    monkeypatch.setattr(chat, "client", FakeLLM(
        reply(tool_calls=[tool_call("get_skill_ranks", {"learner_id": "victim", "section": "Writing"})]),
        reply("Here are your ranks. [STATE: explaining]"),
    ))
    seen = []
    monkeypatch.setattr(chat, "execute_tutor_tool", lambda name, args: seen.append(args) or "{}")

    chat.continue_chat_session(session_id, "alice", "How close am I to ranking up?")

    assert seen and all(args["learner_id"] == "alice" for args in seen)


def test_coach_tools_run_for_submitting_learner(monkeypatch):
    monkeypatch.setattr(coach, "client", FakeLLM(
        reply(tool_calls=[tool_call("get_skill_rank", {"learner_id": "victim", "section": "Writing", "skill_id": "x"})]),
        reply("Evaluation complete."),
    ))
    seen = []
    monkeypatch.setattr(coach, "execute_coach_tool", lambda name, args: seen.append(args) or "{}")

    coach.run_coach_agent("alice", "Writing", {"prompt": "P", "essay": "E", "scores": {}, "feedback": ""})

    assert seen and all(args["learner_id"] == "alice" for args in seen)


def test_malformed_tool_arguments_are_not_echoed_back(monkeypatch):
    """Qwen 400s the next request if an echoed function.arguments isn't JSON."""
    broken = tool_call("get_skill_rank", {})
    broken.function.arguments = '{"section": "Writing", "skill_id": '
    fake = FakeLLM(reply(tool_calls=[broken]), reply("Evaluation complete."))
    monkeypatch.setattr(coach, "client", fake)
    monkeypatch.setattr(coach, "execute_coach_tool", lambda name, args: "{}")

    result = coach.run_coach_agent("alice", "Writing", {"prompt": "P", "essay": "E", "scores": {}, "feedback": ""})

    assert result["success"]
    echoed = [m for m in fake.calls[1]["messages"] if m.get("tool_calls")]
    for call in echoed[0]["tool_calls"]:
        json.loads(call["function"]["arguments"])


@pytest.mark.parametrize("bot", [telegram, whatsapp], ids=["telegram", "whatsapp"])
def test_bot_tools_ignore_model_learner_id(bot, monkeypatch):
    seen = []
    monkeypatch.setattr(mcp_tools, "get_study_schedule", lambda learner_id: seen.append(learner_id) or {})

    bot._execute_tool("get_study_schedule", {"learner_id": "victim"}, "alice")

    assert seen == ["alice"]


@pytest.mark.parametrize("bot", [telegram, whatsapp], ids=["telegram", "whatsapp"])
def test_bot_tools_refuse_unlinked_users(bot, monkeypatch):
    seen = []
    monkeypatch.setattr(mcp_tools, "get_study_schedule", lambda learner_id: seen.append(learner_id) or {})

    result = bot._execute_tool("get_study_schedule", {"learner_id": "victim"}, None)

    assert "error" in result and seen == []


@pytest.mark.parametrize("bot", [telegram, whatsapp], ids=["telegram", "whatsapp"])
def test_bots_cannot_look_up_learners_by_email(bot):
    assert "find_learner" not in {t["function"]["name"] for t in bot.TOOLS}
    assert "error" in bot._execute_tool("find_learner", {"email": "victim@example.com"}, "alice")
