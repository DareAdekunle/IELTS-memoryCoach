"""
Measure real Qwen usage per learner workflow and estimate cost per session.

Runs each workflow once through the real API routes (FastAPI TestClient,
background tasks included) against a THROWAWAY SQLite copy of the demo
account, recording the token usage Qwen reports. Live API calls — costs a
few US cents per run.

    docker exec ielts-api-dev python scripts/cost_model.py

Not measured live (computed instead): speech-to-text is billed per audio
second; text-to-speech is billed per character and is stubbed to count only.
"""
import collections
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
_db = tempfile.NamedTemporaryFile(prefix="bandup-cost-", suffix=".db", delete=False)
os.environ["DATABASE_URL"] = f"sqlite:///{_db.name}"

# USD. Per 1M tokens unless noted. Model Studio international (Singapore), Oct 2026.
PRICES = {
    "qwen-plus":         {"in": 0.40, "out": 1.20},
    "qwen-turbo":        {"in": 0.05, "out": 0.20},   # official list price is CNY 0.367 / 1.468
    "qwen3-vl-plus":     {"in": 0.20, "out": 1.60},
    "text-embedding-v3": {"in": 0.07, "out": 0.0},
}
ASR_PER_SECOND = 0.000035      # qwen3-asr-flash
TTS_PER_CHAR = 0.10 / 10_000   # qwen3-tts-flash
SPEAKING_AUDIO_SECONDS = 8 * 60  # learner speech in a full Part 1-3 test (~11-14 min incl. examiner)

usage = collections.defaultdict(collections.Counter)
workflow = ["setup"]


def record(model, tokens_in, tokens_out):
    u = usage[workflow[0]]
    u[(model, "in")] += tokens_in
    u[(model, "out")] += tokens_out
    u[(model, "calls")] += 1


# ─── Instrument the SDKs ─────────────────────────────────────────────────────

from openai.resources.chat.completions import Completions  # noqa: E402

_create = Completions.create


def _instrumented_create(self, *args, **kwargs):
    model = kwargs.get("model", "?")
    if kwargs.get("stream"):
        kwargs["stream_options"] = {"include_usage": True}
        stream = _create(self, *args, **kwargs)

        def chunks():
            for chunk in stream:
                if chunk.usage:
                    record(model, chunk.usage.prompt_tokens, chunk.usage.completion_tokens)
                if chunk.choices:  # hide the usage-only final chunk from callers
                    yield chunk
        return chunks()
    response = _create(self, *args, **kwargs)
    if response.usage:
        record(model, response.usage.prompt_tokens, response.usage.completion_tokens)
    return response


Completions.create = _instrumented_create

import dashscope  # noqa: E402

_embed = dashscope.TextEmbedding.call


def _instrumented_embed(*args, **kwargs):
    response = _embed(*args, **kwargs)
    tokens = (getattr(response, "usage", None) or {}).get("total_tokens", 0)
    record("text-embedding-v3", tokens, 0)
    return response


dashscope.TextEmbedding.call = _instrumented_embed

# ─── App + throwaway demo learner ────────────────────────────────────────────

from app.db.database import Base, SessionLocal, engine  # noqa: E402
import app.db.models  # noqa: E402,F401
from api.auth.models import User  # noqa: E402

Base.metadata.create_all(bind=engine)
import seed_demo  # noqa: E402

seed_demo.seed_demo()

from fastapi.testclient import TestClient  # noqa: E402
from api.dependencies import get_current_user  # noqa: E402
from api.main import app  # noqa: E402

db = SessionLocal()
user = db.query(User).filter(User.email == seed_demo.DEFAULT_EMAIL).first()
db.close()
app.dependency_overrides[get_current_user] = lambda: user
api = TestClient(app)

ESSAY = (
    "Some people believe that governments should invest more in public transport, while others "
    "argue that building new roads is the better option. In my opinion, public transport deserves "
    "greater investment, although roads remain necessary in some areas.\n\n"
    "On the one hand, expanding roads can reduce congestion in the short term. Rural communities in "
    "particular depend on cars because buses and trains rarely reach them. Moreover, businesses rely "
    "on roads to deliver goods quickly, which supports the wider economy.\n\n"
    "On the other hand, public transport moves far more people using less space and energy. A single "
    "train can replace hundreds of cars, which lowers pollution and makes cities more pleasant to live "
    "in. Furthermore, affordable buses give students and low-income workers access to jobs and "
    "education that they could not otherwise reach. Research also suggests that new roads quickly "
    "fill with extra traffic, so the benefit of building them does not last.\n\n"
    "In conclusion, while roads are still important for rural areas and trade, I believe governments "
    "should prioritise public transport because it serves more people and protects the environment."
)
TUTOR_TURNS = [
    "Yes, I'm ready. Where should I start?",
    "So I should use a linking phrase that shows the relationship, like 'As a result'?",
    "Here's my attempt: 'Cars are convenient. As a result, many families own two of them.'",
    "Okay, let me try a concession: 'Although roads help trade, they increase pollution.'",
]


def run(name, fn):
    workflow[0] = name
    print(f"→ {name} ...", flush=True)
    fn()


def writing_submission():
    prompt = api.get("/writing/prompt").json()
    with api.stream("POST", "/writing/submit/stream", json={
        "prompt": prompt["prompt"], "task_type": prompt["task_type"],
        "essay": ESSAY, "prompt_id": prompt["prompt_id"],
    }) as response:
        for _ in response.iter_lines():
            pass


tutor_turn_count = [0]


def tutor_session_start():
    tutor_session_start.session_id = api.get("/chat/start", params={"section": "Writing"}).json()["session_id"]


def tutor_turns():
    for message in TUTOR_TURNS:
        api.post("/chat/continue", json={"session_id": tutor_session_start.session_id, "message": message})
        tutor_turn_count[0] += 1


tts_chars = [0]


def speaking_evaluation():
    p = api.get("/speaking/prompt/random").json()["prompt"]
    answer = ("I think this is an interesting question. Personally I use technology every day, mainly "
              "for work and keeping in touch with my family, although I try to limit my screen time.")
    body = {
        "prompt_set_id": p["prompt_set_id"],
        "part1_responses": {q: answer for q in p["part1"]["questions"]},
        "part2_response": " ".join([answer] * 6),
        "part3_responses": {q: answer for q in p["part3"]["questions"]},
    }
    result = api.post("/speaking/evaluate", json=body).json()
    tts_chars[0] = len(result.get("feedback_text", ""))


def reading_submission():
    passage = api.get("/reading/passage/random").json()
    passage = passage.get("passage", passage)
    answers = {str(q.get("id", i)): "A" for i, q in enumerate(passage.get("questions", []))}
    api.post("/reading/submit", json={"passage_id": passage["passage_id"], "answers": answers})


def listening_submission():
    track = api.get("/listening/track/random").json()
    track = track.get("track", track)
    answers = {str(q.get("id", i)): "A" for i, q in enumerate(track.get("questions", []))}
    api.post("/listening/submit", json={"track_id": track["track_id"], "answers": answers})


def telegram_message():
    from app.services.telegram_service import run_qwen_agent
    run_qwen_agent("How am I doing in Writing, and what should I practise next?", user.learner_id, [])


run("writing_submission", writing_submission)
run("tutor_start", tutor_session_start)
run("tutor_turns", tutor_turns)
run("speaking_evaluation", speaking_evaluation)
run("reading_submission", reading_submission)
run("listening_submission", listening_submission)
run("telegram_message", telegram_message)

# ─── Report ──────────────────────────────────────────────────────────────────


def cost_of(counter):
    total = 0.0
    for (model, kind), n in counter.items():
        if kind in ("in", "out"):
            total += n / 1_000_000 * PRICES.get(model, PRICES["qwen-plus"])[kind]
    return total


costs = {name: cost_of(c) for name, c in usage.items()}
per_turn = costs.get("tutor_turns", 0) / max(tutor_turn_count[0], 1)
asr = SPEAKING_AUDIO_SECONDS * ASR_PER_SECOND
tts = tts_chars[0] * TTS_PER_CHAR

print("\nMeasured usage per workflow")
print(f"{'workflow':22} {'calls':>5} {'tokens in':>10} {'tokens out':>10} {'USD':>9}")
for name, c in usage.items():
    if name == "setup":
        continue
    calls = sum(n for (_, k), n in c.items() if k == "calls")
    tin = sum(n for (_, k), n in c.items() if k == "in")
    tout = sum(n for (_, k), n in c.items() if k == "out")
    print(f"{name:22} {calls:5d} {tin:10d} {tout:10d} {costs[name]:9.5f}")
    for (model, kind), n in sorted(c.items()):
        if kind == "calls":
            print(f"   {model:19} x{n}")

sessions = {
    "Writing essay (scored + coached)": costs.get("writing_submission", 0),
    "Tutor session, 8 turns": costs.get("tutor_start", 0) + 8 * per_turn,
    "Speaking test (8 min audio)": costs.get("speaking_evaluation", 0) + asr + tts,
    "Reading passage": costs.get("reading_submission", 0),
    "Listening track (audio cached)": costs.get("listening_submission", 0),
    "Telegram message": costs.get("telegram_message", 0),
}
print("\nEstimated cost per session (USD)")
for name, usd in sessions.items():
    print(f"  {name:34} ${usd:.4f}")
print(f"\n  tutor: start ${costs.get('tutor_start', 0):.4f}, then ${per_turn:.4f}/turn")
print(f"  speaking: LLM ${costs.get('speaking_evaluation', 0):.4f} + ASR ${asr:.4f} + TTS ${tts:.4f} ({tts_chars[0]} chars)")

json.dump({"per_workflow": costs, "per_session": sessions, "tutor_per_turn": per_turn,
           "raw": {k: {f"{m}|{t}": n for (m, t), n in v.items()} for k, v in usage.items()}},
          open(os.path.join(tempfile.gettempdir(), "bandup_cost_model.json"), "w"), indent=2)
