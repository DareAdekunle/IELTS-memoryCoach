# BandUp IELTS

> *Grasp English. Retain for life.*

BandUp is an AI IELTS coach that remembers each learner across sessions. Every
practice attempt is scored against the official IELTS criteria, turned into
coaching memories and skill ranks, and used to plan the next lesson — so the
coaching gets more specific the more someone practises.

**Status:** beta. The app currently runs locally with Docker Compose; it was
previously hosted on Alibaba Cloud ECS at `ielts.qonda.xyz`. AI inference uses
Alibaba Cloud Model Studio (Qwen) and Alibaba Cloud OSS.

For the market, positioning and business model see
[`docs/product-strategy.md`](docs/product-strategy.md).

---

## What it does

- **All four IELTS skills** — Writing, Reading, Speaking and Listening, with
  real practice content (7 writing prompts, 9 reading passages, 15 speaking
  prompt sets, 9 listening tracks).
- **Scoring against official rubrics** — Writing and Speaking are scored per
  IELTS criterion; Reading and Listening answers are checked deterministically
  (short answers and spelling variants via Qwen / fuzzy matching).
- **Persistent learner memory** — coaching observations are strengthened,
  weakened and archived over time, with semantic + spaced-repetition retrieval.
- **Skill mastery** — 40 sub-skills (Writing 13, Reading 10, Speaking 9,
  Listening 8), each with a deterministic rank and an IELTS band estimate
  (4.0–8.5).
- **Specialist AI tutors** — one per section, teaching from a structured,
  research-backed lesson plan and the learner's own work.
- **Adaptive content** — difficulty matched to the learner's band; seen items
  are not repeated until the pool is exhausted.
- **Handwritten essays** — photograph an essay; `qwen3-vl-plus` extracts the text.
- **Study scheduler** — recurring study plan synced to Google Calendar.
- **Telegram and WhatsApp coaches** — ask about progress or reschedule study
  sessions from a chat app.
- **Dashboards** — progress trends, band estimates, memory timeline,
  cross-section insights.

## Screenshots

### Dashboard — overall band, cross-section insights, skill focus
![Dashboard](docs/screenshots/dashboard_landing_page.png)

### Writing Coach — adaptive prompts, streaming feedback, handwritten essay upload
![Writing Coach](docs/screenshots/writing_page.png)

### IELTS Tutor — specialist AI tutor grounded in the learner's evidence
![IELTS Tutor](docs/screenshots/tutor.png)

### Skill Mastery — IELTS band estimates across all skills
![Skill Mastery](docs/screenshots/skill_mastery.png)

### Memory Timeline — how the learner model changes over time
![Memory Timeline](docs/screenshots/memory.png)

### Progress Dashboard — score trends and skill improvements
![Progress](docs/screenshots/progress.png)

---

## How it works

### The coaching loop

```
PERCEIVE   Essay submitted / audio recorded / passage answered
           → scored against IELTS criteria (qwen-plus); speech transcribed
             (qwen3-asr-flash); handwriting extracted (qwen3-vl-plus)

REMEMBER   Coach agent gathers evidence with tool calls, then
           → classifies each sub-skill (strength / weakness / not applicable)
           → deterministic rank engine updates learner_skill_ranks
           → writes / updates coaching memories with confidence + embeddings

REASON     Tutor builds the session context
           → weakest skill, relevant memories, recent work, criterion stage
           → Pedagogy Planner chooses the teaching method (deterministic)

ACT        Specialist Tutor teaches, referencing the learner's own writing
           or speech; records hints and attempts as structured evidence
```

### Two agents: the Coach writes, the Tutor reads

- **Coach agent** (`app/services/coach_service.py`) runs in the background
  after every submission. It reads ranks, memories and the attempt via tools,
  calls `submit_classification` (which triggers the rank engine) and writes
  memories.
- **Tutor agent** (`app/services/chat_coach_service.py`) runs the chat lesson.
  Its tools are read-only; it cannot change ranks.

### Deterministic rank engine

AI classifies; Python decides. Rank changes are auditable in
`learner_skill_ranks`.

```
"demonstrated_strength"  → clean_streak += 1
"demonstrated_weakness"  → clean_streak = 0   (full reset)
"not_applicable"         → no change

clean_streak reaches 3   → current_rank += 1 (max 5), streak resets
Rank never decreases automatically.
Band estimate (4.0–8.5) is derived at read time from rank + streak.
```

### Pedagogy layer

Before the Tutor says a word, a deterministic **Pedagogy Planner**
(`app/pedagogy/`) builds a teaching plan:

- **16 research-backed frameworks** (4 per section — e.g. Genre-Based
  Pedagogy, Focused Indirect Corrective Feedback, Micro-Listening & Dictation,
  4/3/2 Fluency), each dominant / supporting / faded / retired by stage.
- **4 learner stages per criterion** — Foundations (≤5.5) → Guided Control
  (6.0) → Independent Control (6.5–7.0) → Automatization (7.5+), derived live
  from skill ranks.
- **A shared pedagogical spine** in every reply — Backward Design, the Feedback
  Triad (goal → current position → next step), Dynamic Assessment (weakest hint
  first) and Elicitation Before Telling.
- **Support that fades on evidence** — support is reduced only after ≥3
  low-hint successes at ≥80% accuracy, one step at a time, and restored
  immediately on regression.

> The learner model identifies **what** needs improvement. The Planner decides
> **how** to teach it. The Tutor records what happened. The Coach decides what
> it means.

### Structured evidence from free-form chat

The Tutor embeds hidden tags as things happen:

```
[ACTION: hint level=2]                               — hint given at level 2 of 4
[ACTION: attempt result=self_corrected]              — learner fixed it unaided
[ACTION: complete outcome=ready_for_reduced_support] — session evidence is strong
```

Tags are stripped before display and parsed server-side into
`pedagogical_events` / `hint_events`. When the lesson reaches
`bridge_to_practice`, the Coach reads that evidence to decide whether support
has been earned. A `[STATE: …]` tag drives each tutor's state machine:
`introduction → explaining → drilling → bridge_to_practice`.

Full design: [`docs/pedagogy_framework.md`](docs/pedagogy_framework.md) ·
System design: [`ARCHITECTURE.md`](ARCHITECTURE.md)

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React (Vite) + Tailwind CSS |
| Backend API | FastAPI (Python 3.11) |
| Text + vision AI | Alibaba Cloud Model Studio — `qwen-plus`, `qwen3-vl-plus` (`qwen-turbo` for JSON repair) |
| Speech-to-text | `qwen3-asr-flash` |
| Text-to-speech | `qwen3-tts-flash` (Cherry voice) |
| Embeddings | `text-embedding-v3` (1024-d) |
| Object storage | Alibaba Cloud OSS — listening audio cache, essay-image hand-off, backups |
| Database | PostgreSQL 16; schema managed by Alembic |
| Auth | JWT + Google OAuth (Authlib) |
| Calendar | Google Calendar API (OAuth with PKCE) |
| Chat channels | Telegram Bot API, WhatsApp Cloud API |
| Containers | Docker + Docker Compose; Nginx in the production image |
| Tests | pytest |

No agent framework: orchestration is plain Python, with deterministic code
wherever a decision affects learner records.

---

## Getting started

### Prerequisites
- Docker + Docker Compose
- An Alibaba Cloud Model Studio (DashScope) API key; OSS credentials for audio

### Run locally

```bash
git clone https://github.com/DareAdekunle/IELTS-memoryCoach.git
cd IELTS-memoryCoach
cp .env.example .env        # fill in the values; each one is described there
docker compose up -d --build
```

- App: http://localhost:5173
- API docs: http://localhost:8000/docs

The API container runs database migrations before it starts. Source folders
are mounted, so backend and frontend changes reload without a rebuild.

### Demo data

```bash
docker exec ielts-api-dev python seed_demo.py
```

Creates `demo@ieltscoach.com` / `demo1234` with a realistic history (essays,
reading attempts, memories and near-rank-up skills).

### Tests

```bash
docker exec ielts-api-dev pytest
```

Tests run against a throwaway SQLite database and block live Qwen calls.
Scripts that hit the live API are in `scripts/manual_checks/` and are run by
hand.

### Database migrations

The schema is managed by Alembic (`migrations/`). After changing a model:

```bash
docker exec ielts-api-dev alembic revision --autogenerate -m "describe change"
docker restart ielts-api-dev     # scripts/migrate.py applies it on start
```

To import data from a legacy SQLite database:

```bash
python scripts/migrate_sqlite_to_postgres.py \
    --sqlite ./ielts_coach.db \
    --postgres "postgresql://ielts:YOUR_PASSWORD@localhost:5432/ielts_coach"
```

### Production image

`docker-compose.prod.yml` builds one image with the React build, FastAPI and
Nginx. `nginx.conf` expects Let's Encrypt certificates for the configured
domain, so use the dev compose file for local work.

---

## Chat coaches (Telegram & WhatsApp)

Learners can ask *"What's my weakest skill?"*, *"How am I doing in
Writing?"* or *"Move my Wednesday session to Friday at 9am"* — the coach calls
the same backend functions as the web app and updates Google Calendar.

**Connecting an account:** in the web app open **Study Plan → Chat with your
coach**, choose *Connect Telegram* or *Connect WhatsApp*, and send the one-time
code to the bot. Codes expire after 10 minutes, are single-use and stored only
as a hash.

```
Message → /telegram/webhook (secret-token header) or /whatsapp/webhook (Meta signature)
  → 200 returned immediately; reply built in the background
  → link-code check (unlinked chats get instructions, no LLM call)
  → keyword pre-filter (off-topic / abuse blocked without an LLM call)
  → Qwen agent (qwen-plus, tool-calling) — tools run as the linked learner
  → reply sent via Telegram Bot API / WhatsApp Cloud API
```

Both channels share one conversation flow (`app/services/bot_conversation.py`).
To receive messages the API must be reachable publicly (a tunnel such as ngrok
works locally) and `TELEGRAM_WEBHOOK_SECRET` / `WHATSAPP_APP_SECRET` must be
set — webhooks reject everything otherwise.

---

## Study scheduler + Google Calendar

Learners set a recurring schedule (days, time, duration) during onboarding or
on the **Study Plan** page; BandUp creates recurring Google Calendar events.

- Weekly recurrence until the test date; reminders 60 and 10 minutes before
- Event descriptions name the learner's current weakest skill
- The chat coaches can change the schedule and patch the calendar
- OAuth uses PKCE; the verifier travels in the `state` parameter, so the
  callback stays stateless

---

## Security model

- **Identity comes from the server.** Learner IDs come from the validated JWT
  (web) or the linked chat (bots). Agent tool calls always run as that learner,
  whatever `learner_id` the model supplies.
- **Tutor prompts stay server-side.** The system prompt and transcript live in
  `tutor_session_transcripts`; the browser sends only a session ID and the next
  message, and sessions belonging to another learner return 404.
- **Bots link by one-time code**, never by email address. Webhooks are verified
  (Telegram secret token, WhatsApp HMAC signature) and fail closed.
- **Scope guardrails** — a keyword pre-filter plus non-negotiable scope rules
  in every coach, tutor and bot prompt keep conversations to IELTS.
- **`/mcp-server` is admin-only** — it requires `MCP_API_TOKEN`; unset means
  disabled.

---

## Running costs

Measured with `scripts/cost_model.py` (Model Studio international list
prices, October 2026):

| Session | Approx. cost (USD) |
|---|---|
| Writing essay, scored + coached | $0.013 (up to ~$0.04 on long Coach runs) |
| Reading passage | $0.005–0.026 |
| Listening track (audio cached) | $0.005 |
| Speaking test (8 min of audio) | $0.036 |
| Tutor session, 8 turns | $0.019 |
| Chat-coach message | $0.0013 |

A typical active learner costs roughly **$0.80–1.20 per month** in AI usage.
The Coach agent's multi-step tool use is the largest variable cost.

---

## Project structure

```
IELTS-memoryCoach/
├── api/                    ← FastAPI app
│   ├── auth/               ← JWT + Google OAuth, user + link-code models
│   └── routes/             ← writing, reading, speaking, listening, chat,
│                             progress, memory, pedagogy, schedule,
│                             channels, telegram, whatsapp
├── app/                    ← services (AI + business logic)
│   ├── pedagogy/           ← deterministic pedagogy layer (planner, stages,
│   │                         fading, action tags, spine)
│   ├── services/           ← coach, chat_coach (tutor), scoring, memory,
│   │                         asr, tts, embedding, calendar, schedule,
│   │                         bot_conversation, channel_linking, …
│   ├── prompts/            ← Qwen prompt templates
│   ├── data/               ← IELTS content, taxonomies, frameworks, descriptors
│   ├── db/                 ← SQLAlchemy models + session factory
│   ├── mcp/                ← MCP server (FastMCP), admin-only
│   └── utils/              ← JSON parsing, tool-call helpers, logging
├── frontend/               ← React app (Vite + Tailwind)
├── migrations/             ← Alembic migrations
├── scripts/
│   ├── migrate.py          ← runs before the API: alembic upgrade head
│   ├── cost_model.py       ← measures live Qwen cost per session
│   ├── eval_writing.py     ← Writing scores vs human raters
│   ├── manual_checks/      ← live-API smoke scripts (run by hand)
│   ├── migrate_sqlite_to_postgres.py
│   ├── db_backup.py        ← OSS backup/restore (legacy SQLite)
│   └── eval_pedagogy.py    ← offline pedagogy behaviour eval
├── tests/                  ← pytest suite
├── evaluation/             ← assessment calibration: metrics, rating templates,
│                             rater guide (real data git-ignored)
├── docs/                   ← pedagogy design, product strategy, screenshots
├── docker-compose.yml      ← local development
├── docker-compose.prod.yml ← production (single image + Nginx)
├── seed_demo.py            ← demo account seeder
├── ARCHITECTURE.md         ← system design, agent loops, DB schema
└── CLAUDE.md               ← conventions for anyone (or any agent) changing the code
```

---

## Key design decisions

1. **Deterministic where it matters.** The model classifies evidence and
   writes teaching; Python owns ranks, stages, support levels and permissions.
2. **Evaluation and coaching are separate steps.** The essay score streams to
   the learner first (first token in ~1–2 s); the Coach agent classifies skills
   and writes memories in the background, so a coaching failure never loses
   the score.
3. **Audio is generated once.** Listening audio is cached in OSS, so each track
   costs one TTS call for all learners.
4. **Embeddings without a vector database.** 1024-d vectors are stored as JSON
   and ranked in Python with `0.45 × similarity + 0.55 × spaced-repetition
   score` — ample at 20–200 memories per learner.
5. **Pre-signed URLs for vision.** Qwen-VL only accepts `https://` image URLs,
   so essay photos go to a private OSS object with a 5-minute signed URL and are
   deleted afterwards.

More in [`ARCHITECTURE.md`](ARCHITECTURE.md#key-design-decisions).

---

## Roadmap

Near-term engineering work:

- [x] Stabilise: security boundaries, Alembic, pytest suite, cost model,
      WhatsApp parity
- [ ] **Assessment validity** — calibrate Writing and Speaking scores against
      human-rated samples; Task 1 / Task 2 specific scoring
- [ ] **Memory 2.0** — link every memory to its source attempt; de-duplicate
      and reconcile contradictions
- [ ] **Diagnostic + adaptive planning** — initial diagnostic and a study plan
      built from it
- [ ] **Durable agent workflows** — move Coach/Tutor orchestration to a
      persistent, recoverable workflow engine
- [ ] Listening replay/transcript limits in the UI
- [ ] Teacher / admin dashboard
- [ ] Hosting for the beta

The detailed sprint plan and checklist is in [`PLAN.md`](PLAN.md).
Longer-term product phases are in
[`docs/product-strategy.md`](docs/product-strategy.md).
