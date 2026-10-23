"""
Shared test setup.

Every test runs against a throwaway SQLite file — never the real database —
and live Qwen calls are blocked; tests that need a model reply install a
FakeLLM. This module must configure the environment before any app import,
because app.db.database reads DATABASE_URL at import time.
"""
import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_db_file = tempfile.NamedTemporaryFile(prefix="bandup-test-", suffix=".db", delete=False)
os.environ["DATABASE_URL"] = f"sqlite:///{_db_file.name}"
os.environ["MCP_API_TOKEN"] = "test-mcp-token"
for key in ("DASHSCOPE_API_KEY", "MODEL_STUDIO_API_KEY", "JWT_SECRET"):
    os.environ.setdefault(key, "test-key")

import pytest  # noqa: E402

from app.db.database import Base, engine  # noqa: E402
import app.db.models  # noqa: E402,F401
import api.auth.models  # noqa: E402,F401

Base.metadata.create_all(bind=engine)


@pytest.fixture(autouse=True)
def block_live_llm(monkeypatch):
    """Fail loudly if code reaches the real Qwen API without a FakeLLM."""
    from openai.resources.chat.completions import Completions

    def _blocked(*args, **kwargs):
        raise RuntimeError("Live Qwen call attempted in a test — install a FakeLLM")

    monkeypatch.setattr(Completions, "create", _blocked)


@pytest.fixture(autouse=True)
def clean_db():
    yield
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())


# ─── Fake Qwen client ─────────────────────────────────────────────────────────

def tool_call(name: str, args: dict, call_id: str = "call_1"):
    return SimpleNamespace(
        id=call_id, type="function",
        function=SimpleNamespace(name=name, arguments=json.dumps(args)),
    )


def reply(content: str = "", tool_calls=None):
    message = SimpleNamespace(content=content, tool_calls=tool_calls or None, role="assistant")
    finish = "tool_calls" if tool_calls else "stop"
    return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason=finish)])


class FakeLLM:
    """Drop-in for an OpenAI client; returns scripted replies in order, then repeats the last."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]


@pytest.fixture
def make_user():
    def _make(learner_id: str, user_id: str | None = None):
        return SimpleNamespace(
            user_id=user_id or f"user-{learner_id}", learner_id=learner_id,
            email=f"{learner_id}@example.com", full_name=learner_id, username=learner_id,
        )
    return _make


@pytest.fixture
def api_client():
    """TestClient for the FastAPI app, without running its lifespan (no TTS warmup)."""
    from fastapi.testclient import TestClient
    from api.main import app
    from api.dependencies import get_current_user

    client = TestClient(app)
    client.login_as = lambda user: app.dependency_overrides.__setitem__(get_current_user, lambda: user)
    yield client
    app.dependency_overrides.clear()
