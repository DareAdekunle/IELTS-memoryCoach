# Qonda IELTS

> *Grasp English. Retain for life.*
>
> An AI coach that truly comprehends each learner's weaknesses — and gets smarter with every session.

**Live Demo:** https://ielts.qonda.xyz  
**Demo Login:** demo@ieltscoach.com / demo1234  
**Telegram Bot:** [@qieltsbot](https://t.me/qieltsbot)

---

## The Problem

3.5 million people take IELTS every year. Most of them are not students — they are **working professionals** who need a Band 6.5 or 7.0 to unlock a visa, a job offer, or a university place. They study in stolen hours: on a commute, in a lunch break, after the kids are in bed.

Every existing prep tool has the same fundamental flaw: **it forgets you between sessions.** You get generic feedback today, generic feedback tomorrow, and no cumulative coaching intelligence. A tool that doesn't remember what you struggled with last week cannot make you better this week.

| Feature | Qonda | British Council | Magoosh | IELTS.org |
|---|---|---|---|---|
| Persistent memory across sessions | ✅ | ❌ | ❌ | ❌ |
| Granular skill rank engine | ✅ | ❌ | ❌ | ❌ |
| Specialist AI tutors per section | ✅ | ❌ | Partial | ❌ |
| MCP API for external agents | ✅ | ❌ | ❌ | ❌ |
| Telegram coaching bot (Qwen agent) | ✅ | ❌ | ❌ | ❌ |
| Study schedule + Google Calendar | ✅ | ❌ | ❌ | ❌ |
| All 4 IELTS skills | ✅ | ✅ | ✅ | ✅ |
| Built on Alibaba Cloud | ✅ | ❌ | ❌ | ❌ |

Qonda solves this with a **persistent AI memory layer** — every practice session extracts coaching insights that strengthen, weaken and archive over time, building an ever-richer model of each learner.

---

## Key innovation — structured evidence from freeform conversation

Every AI tutor in Qonda is a natural-language conversation. But conversations are opaque: how does the system know whether a hint was needed, whether the learner succeeded independently, or whether they're ready to reduce scaffolding?

**The ACTION tag protocol solves this.** The Tutor embeds hidden structured tags inline as events happen:

```
[ACTION: hint level=2]                          — hint given at level 2 of 4
[ACTION: attempt result=self_corrected]          — learner fixed it without help
[ACTION: complete outcome=ready_for_reduced_support]  — session evidence is strong
```

These tags are **stripped before display** — the learner sees natural coaching text. The server parses them into a structured evidence record. After each session, the Coach agent reads that record to decide whether support has been earned, update criterion states, and inform the next session's teaching plan.

The result: a closed evidence loop where every Tutor conversation, however freeform, feeds back into the deterministic coaching engine. **No competitor can replicate this without the accumulated data.**

---

## The Agent Architecture

Qonda implements a full **perceive → remember → reason → act** agent loop that runs after every practice session:

```
PERCEIVE   Essay submitted / audio recorded / passage answered
           ↓
           Qwen evaluates against official IELTS rubrics
           ASR transcribes spoken responses (qwen3-asr-flash)

REMEMBER   MemoryAgent extracts coaching observations
           Updates learner_memories with confidence scoring
           Strengthens confirmed patterns, weakens contradicted ones
           Archives mastered weaknesses permanently
           Updates learner_skill_ranks via deterministic rule engine

REASON     Specialist tutor builds session context:
           → Fetches weakest skill from learner_skill_ranks
           → Retrieves evidence memory for that skill
           → Pulls recent essay excerpt from practice_attempts
           → Assembles personalised context brief

ACT        Specialist AI tutor opens a targeted lesson
           References the learner's actual writing/speech
           Generates focused drills for the specific weakness
           Bridges back to practice when ready
```

This loop runs silently after every submission — the learner simply sees better and more personalised coaching with each session.

---

## Custom AI Skills

Qonda implements four **custom AI skills** — domain-specific agent configurations with specialist knowledge, teaching strategies, and internal state machines:

| Custom Skill | Specialist Knowledge | State Machine |
|---|---|---|
| Writing Tutor | IELTS Band Descriptors, task types, thesis structure, cohesion | introduction → explaining → drilling → bridge_to_practice |
| Reading Tutor | T/F/NG strategy, skimming, scanning, paraphrase recognition | introduction → explaining → drilling → bridge_to_practice |
| Speaking Tutor | Part 1/2/3 strategies, OREO structure, circumlocution | introduction → explaining → drilling → bridge_to_practice |
| Listening Tutor | Prediction, distractor resistance, form completion | introduction → explaining → drilling → bridge_to_practice |

Each skill uses hidden `[STATE: xxx]` tags for deterministic UI state tracking — the learner experiences natural conversation while the system reliably knows when to show the "Go practise" button.

### The Pedagogical Skill Layer

Every Tutor session now runs on an evidence-based **pedagogy engine** (`app/pedagogy/`). Before the Tutor says a word, a deterministic **Pedagogy Planner** builds a structured teaching plan:

- **16 research-backed frameworks** (4 per section — e.g. Genre-Based Pedagogy, Focused Indirect Corrective Feedback, Micro-Listening & Dictation, 4/3/2 Fluency), each dominant/supporting/faded/retired depending on the learner's stage
- **4 learner stages per criterion** — Foundations (≤5.5) → Guided Control (6.0) → Independent Control (6.5–7.0) → Automatization (7.5+) — derived live from skill ranks, so vocabulary can be independent while grammar still gets full scaffolding
- **A Shared Pedagogical Spine** in every reply: Backward Design (every activity targets a band descriptor), the Feedback Triad (goal → current position → next step), Dynamic Assessment (weakest hint first, every hint logged), and Elicitation Before Telling
- **Support that fades on evidence** — hidden `[ACTION: hint level=2]` tags record every hint and attempt; the Coach interprets the evidence after each session, and deterministic rules only allow support to fade after ≥3 low-hint successes at ≥80% accuracy — one step at a time, instantly restored on regression

> The learner model identifies **what** needs improvement. The Planner decides **how** to teach it. The Tutor records what happened. The Coach decides what it means.

---

## Screenshots

### Dashboard — overall band, cross-section insights, skill focus
![Dashboard](docs/screenshots/dashboard_landing_page.png)

### Writing Coach — adaptive prompts, streaming feedback, handwritten essay upload
![Writing Coach](docs/screenshots/writing_page.png)

### IELTS Tutor — specialist AI tutor grounded in real evidence
![IELTS Tutor](docs/screenshots/tutor.png)

### Skill Mastery — IELTS band estimates across all skills
![Skill Mastery](docs/screenshots/skill_mastery.png)

### Memory Timeline — the MemoryAgent's learning made visible
![Memory Timeline](docs/screenshots/memory.png)

### Progress Dashboard — score trends and skill improvements
![Progress](docs/screenshots/progress.png)

---

## What it does

Qonda IELTS is a full-stack AI coaching web application that remembers learners across sessions. Unlike static quiz tools, it tracks weaknesses, monitors improvement, personalises feedback over time, and actively teaches learners through specialist AI tutors grounded in their own practice evidence.

**Core features:**
- Google OAuth and username/password authentication with JWT sessions
- Real IELTS practice content for all four skills (9 reading passages,
  9 listening tracks, 15 speaking prompts, 7 writing prompts)
- **Adaptive content** — difficulty matched to learner's current band level
- **No-repeat selection** — seen content avoided until all exhausted
- AI-powered scoring using official IELTS rubrics and band descriptors
- Persistent memory with **spaced repetition weighting** — recency × confidence
- **Coach Agent** — evaluates practice via tool calls, classifies skills,
  writes memories; backed by deterministic rank engine
- **Tutor Agent** — calls live tools mid-conversation, extracts micro-memories
  at session end to close the agent loop
- **Cross-section insights** — identifies skill gaps that span multiple sections
- **IELTS band estimates (4.0–8.5)** per skill, updated after every session
- **Handwritten essay upload** — qwen-vl-plus extracts text from photos
- Skill taxonomy for all 4 sections: Writing (13), Reading (10),
  Speaking (9), Listening (8) sub-skills
- Memory layer exposed as **MCP server** (12 tools) for external agent consumption
- **Telegram coaching bot** — Qwen agent with tool-calling, same tool layer as MCP server
- **Study scheduler** — recurring study plan with Google Calendar integration
- Streaming essay feedback (SSE) — first token in ~1-2 seconds
- TTS audio cached in Alibaba Cloud OSS (generated once per track, served forever)
- Progress dashboard with score trends and band estimates across all four skills
- Memory timeline showing coaching intelligence evolution over time

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React (Vite) + Tailwind CSS |
| Backend API | FastAPI (Python) |
| AI text inference | Alibaba Cloud Model Studio (qwen-plus, qwen-turbo, qwen-vl-plus) |
| Speech-to-Text | DashScope qwen3-asr-flash |
| Text-to-Speech | DashScope qwen3-tts-flash (Cherry voice) |
| Text embeddings | DashScope text-embedding-v3 (1024-d) |
| Audio storage | Alibaba Cloud OSS (oss-ap-southeast-1) |
| Agent protocol | MCP (Model Context Protocol) via FastMCP |
| Messaging bot | Telegram Bot API + Qwen agent with tool-calling |
| Calendar | Google Calendar API (OAuth, recurring events) |
| Compute | Alibaba Cloud ECS (Singapore) |
| Auth | JWT + Google OAuth (Authlib) |
| Database | PostgreSQL 16 (Docker, persistent volume) |
| Containerisation | Docker + Docker Compose |
| Reverse proxy | Nginx |

**No agent framework** — all orchestration is hand-rolled Python with deterministic logic where it matters. The rank engine never uses AI for decisions.

---

## Alibaba Cloud services

```
Model Studio    — text + vision AI inference
                  qwen-plus  → essay evaluation, memory extraction,
                               Coach agent, Tutor agent
                  qwen-turbo → skill classification (fast, cheap)
                  qwen-vl-plus → handwritten essay image extraction
                  70M+ free tokens, Singapore region workspace

DashScope ASR   — qwen3-asr-flash, real-time speech transcription
                  Automatic compression + chunking for long recordings

DashScope TTS   — qwen3-tts-flash, Cherry voice
                  Listening track audio cached in OSS permanently

OSS             — ielts-memorycoach-audio bucket, Singapore
                  TTS audio generated once, served to all users forever
                  Zero DashScope cost after first generation per track

ECS             — ecs.e-c1m2.large, Singapore Zone A
                  Docker + Nginx, 2 vCPU 4GB RAM

VPC + Security  — isolated network, principle of least privilege
```

---

## IELTS modules

### ✍️ Writing Coach
- Adaptive prompts matched to learner's current band level
- **Handwritten essay upload** — photograph your essay, qwen-vl-plus
  extracts the text, same evaluation pipeline runs
- Evaluated against 5 official rubric criteria
- Coach Agent classifies 13 granular sub-skills via tool calls
- Streaming feedback via SSE (first token ~1-2s)
- Full memory lifecycle + skill rank updates

### 📖 Reading Coach
- 9 passages across 3 difficulty levels (3 per level)
- Adaptive selection — passage difficulty matched to current band
- Multiple Choice, True/False/Not Given, Short Answer
- Objective answers checked instantly, short answers via Qwen
- No-repeat selection — seen passages avoided until all exhausted
- Full memory lifecycle + Coach Agent skill classification

### 🎤 Speaking Coach
- 15 prompt sets (5 beginner, 6 intermediate, 4 advanced)
- Adaptive selection — prompt difficulty matched to current band
- Browser microphone recording or file upload
- qwen3-asr-flash transcription in real time
- Cherry reads examiner feedback aloud via TTS
- Band scores: Fluency, Lexical, Grammar, Pronunciation
- No-repeat selection — seen prompts avoided until all exhausted
- Coach Agent classifies 9 Speaking sub-skills after each session

### 🎧 Listening Coach
- 9 tracks across 3 difficulty levels (3 per level), all 4 IELTS parts
- Adaptive selection — track difficulty matched to current band
- Cherry generates audio on first request, cached in OSS permanently
- Audio proxied via FastAPI (handles auth + cross-origin correctly)
- Exam conditions: preview questions, play once, answer while listening
- Fuzzy answer matching for spelling/number variants
- No-repeat selection — seen tracks avoided until all exhausted
- Coach Agent classifies 8 Listening sub-skills after each session

### 🧑‍🏫 IELTS Tutor (Chat Coach)
- 4 specialist tutors — select your section
- **True agent loop** — Tutor calls live tools mid-conversation:
  get_learner_weaknesses, get_recent_attempts, get_skill_ranks
- Each tutor opens with live context from the Coach Agent, not
  stale session-start data
- When drilling concludes, micro-memories are extracted and saved —
  closing the agent loop so tutoring feeds back into future coaching
- Internal state machine behind natural conversation
- Session cached in browser — no redundant API calls on navigation

---

## Skill Mastery System

Skills are displayed as **IELTS band estimates (4.0–8.5)** rather than
internal ranks. Bands are derived from the rank engine at read time:
streak 0 = base band for that rank; streak 1+ = base band + 0.5.
A weakness (streak reset) drops the band back to base — realistic
downward movement without destabilising the underlying engine.
No band is shown until the learner completes their first practice session.

### 13 Writing sub-skills (Official IELTS Band Descriptors)

| Category | Sub-skills |
|---|---|
| Task Response | Full Task Coverage, Clarity of Position, Idea Development, Conclusion Synthesis |
| Coherence & Cohesion | Logical Progression, Paragraphing, Cohesive Devices |
| Lexical Resource | Vocabulary Range, Word Choice Precision, Spelling & Word Formation |
| Grammatical Range & Accuracy | Sentence Variety, Grammatical Accuracy, Punctuation Control |

### Rank engine (deterministic — no AI in rank decisions)

```
After each submission, the Coach Agent gathers evidence via tools,
then calls submit_classification for each skill in the taxonomy:

  "demonstrated_strength"  → clean_streak += 1
  "demonstrated_weakness"  → clean_streak = 0  (full reset)
  "not_applicable"         → no change

clean_streak reaches 3     → current_rank += 1 (max 5)
Band estimate derived at read time from rank + streak (4.0–8.5)
Rank NEVER decreases automatically.
All rank changes are auditable in learner_skill_ranks table.
Supported for all 4 sections: Writing (13), Reading (10),
Speaking (9), Listening (8) sub-skills.
```

---

## MCP Server

The Qonda backend is exposed as an MCP server at `/mcp-server/mcp`. Any MCP-compatible AI agent — Claude Desktop, custom agents, school platforms — can query learner coaching data and manage study schedules without direct database access.

```json
// Claude Desktop config (~/.config/Claude/claude_desktop_config.json)
{
  "mcpServers": {
    "qonda": {
      "url": "https://ielts.qonda.xyz/api/mcp-server"
    }
  }
}
```

**12 available tools:**

| Tool | Purpose |
|---|---|
| `find_learner` | Resolve learner_id from email — always call first |
| `get_coaching_context` | Full coaching overview in one call — start here |
| `get_learner_weaknesses` | Active weakness memories with confidence scores |
| `get_learner_strengths` | Active strength memories |
| `get_skill_ranks` | All skill ranks with band estimates and streak data |
| `get_weakest_skill_for_learner` | Single weakest skill + rank definitions |
| `get_recent_attempts` | Attempt history with score summaries |
| `get_learner_memory_stats` | Memory profile statistics |
| `get_study_schedule` | Current study schedule + Google Calendar status |
| `schedule_study_sessions` | Create or update recurring study schedule |
| `add_one_off_session` | Add a single extra session on a specific date |
| `cancel_study_schedule` | Cancel schedule and remove calendar events |

**The same tool layer powers the Telegram bot.** When a learner messages `@qieltsbot`, Qwen calls these same functions via tool-calling — one backend, two AI surfaces (MCP + Telegram).

---

## Telegram Coaching Bot

**[@qieltsbot](https://t.me/qieltsbot)** — Qwen-powered, available anywhere.

The Telegram bot brings Qonda's full coaching intelligence to any device without opening a browser. It uses the same Qwen model (qwen-plus with tool-calling) that drives the web app's Coach and Tutor agents.

**What it can do:**
- Answer coaching questions: *"What's my weakest IELTS skill?"*
- Give a full progress overview: *"How am I doing in Writing?"*
- Reschedule study sessions: *"Move my Wednesday session to Friday at 9am"* — Qwen calls `schedule_study_sessions`, updates the DB, patches Google Calendar
- Add one-off sessions: *"Add a 45-min session this Saturday at 10am"*

**Architecture:**
```
Telegram message → FastAPI /telegram/webhook
  → Qwen agent (qwen-plus, tool-calling)
  → same Python functions as MCP server
  → reply sent via Telegram Bot API
```

The Qwen agent loop runs up to 5 tool-call iterations per message — enough for chained queries like "What should I study, and when is my next scheduled session?" in a single reply.

---

## Study Scheduler + Google Calendar

Learners set a recurring study schedule (days, time, duration) during onboarding or from the **Study Plan** page. Qonda creates recurring events in Google Calendar so sessions sit alongside meetings and commutes — exactly where a working professional needs them.

- **2-step onboarding** — profile setup followed by study schedule
- **Recurring calendar events** — RRULE weekly recurrence, UNTIL = test date
- **Personalized descriptions** — event title includes the learner's weakest skill
- **Reminders** — email 60 min before, popup 10 min before
- **MCP + Telegram writable** — `schedule_study_sessions` and `add_one_off_session` update both the DB and Google Calendar from any interface

---

## Why Qonda wins — the moat

### The learner we're building for

There are 3.5 million IELTS test-takers every year. The majority are not full-time students — they are working professionals in Lagos, Nairobi, Manila, and Dhaka who need Band 6.5 or 7.0 to unlock a visa, a job offer, or a graduate place. They study in stolen windows: a 20-minute commute, a lunch break, the hour before midnight. Call them **jugglers** — every product decision in Qonda was made for them.

Existing tools fail jugglers in a specific way: they reset. Every session, you get the same generic feedback, the same rubric, the same advice. The tool has no memory of what you struggled with last week, no sense of whether you're improving, no way to pick up where you left off. You are permanently a stranger to your own coach.

### Five compounding advantages

**1. A data flywheel that only gets smarter**
Every practice session writes new coaching memories — specific observations about this exact learner's error patterns, which approaches worked, which didn't. Memories compound with confidence-weighted spaced repetition: a high-confidence weakness from last week outranks a medium-confidence one from three months ago. After 10 sessions, Qonda knows the learner better than any generic AI coach. After 30, switching to a competitor means returning to generic feedback from scratch. **That switching cost grows with every session.**

**2. Designed for the 20-minute window**
- No-repeat content selection: 9 reading passages, 9 listening tracks, 15 speaking prompts, 7 writing prompts always served fresh until exhausted — a short session is always a genuine new challenge.
- Adaptive difficulty: content matched to current band so no session is wasted on material that's too easy or too hard.
- Session continuity: a 5-day gap doesn't mean starting over — the coach resumes from the evidence, not from a blank slate.
- Cross-section insights: the only IELTS tool that identifies when a grammar gap in Writing and a fluency gap in Speaking share the same root cause, and surfaces it in the dashboard.

**3. A pedagogical layer that can't be copied without the research**
Other AI IELTS tools are chatbots with an IELTS system prompt. Qonda is the only one with a structured, research-backed teaching plan for every session — 16 evidence-based frameworks (Backward Design, Dynamic Assessment, Focused Indirect Corrective Feedback, 4/3/2 Fluency), deterministic stage routing, support that fades only when the evidence earns it. A competitor building this from scratch needs months of pedagogical research, not just API access.

**4. Semantic memory retrieval**
Every coaching memory is embedded using DashScope `text-embedding-v3` at write time. When the Tutor plans a session, the feedback priorities are retrieved not by recency alone but by **semantic relevance to the current session's target descriptor** — a memory about relative-clause verb agreement surfaces when the session targets grammar, even if it was written two months ago. Retrieval is a hybrid of semantic similarity and spaced-repetition scoring, combining the best of both.

**5. MCP as the infrastructure moat**
The memory layer is exposed via MCP protocol — any human tutor, school platform, or language app can query a learner's full coaching profile with consent. When the learner moves from the app to a human tutor, or from one platform to another, their coaching intelligence travels with them. Qonda becomes the coaching infrastructure layer of their entire IELTS journey, not just one more app on their phone.

---

## Getting started

### Prerequisites
- Docker + Docker Compose
- DashScope API key (https://dashscope-intl.aliyuncs.com)

### Run locally

```bash
git clone https://github.com/DareAdekunle/IELTS-memoryCoach.git
cd IELTS-memoryCoach
cp .env.example .env
# Fill in: DASHSCOPE_API_KEY, JWT_SECRET, GOOGLE_CLIENT_ID/SECRET,
#          POSTGRES_PASSWORD, TELEGRAM_BOT_TOKEN,
#          GOOGLE_CALENDAR_CLIENT_ID/SECRET, GOOGLE_CALENDAR_REDIRECT_URI
docker compose -f docker-compose.prod.yml up --build
```

Open http://localhost

### Migrate existing data from SQLite

If you have an existing `ielts_coach.db`, migrate it to PostgreSQL with:

```bash
# While containers are running:
python scripts/migrate_sqlite_to_postgres.py \
    --sqlite ./ielts_coach.db \
    --postgres "postgresql://ielts:YOUR_PASSWORD@localhost:5432/ielts_coach"
```

The script is idempotent — safe to run multiple times.

### Seed demo data

```bash
docker cp seed_demo.py ielts-memorycoach:/app/seed_demo.py
docker exec ielts-memorycoach python seed_demo.py
```

---

## Project structure

```
IELTS-memorycoach/
├── api/                    ← FastAPI backend
│   ├── auth/               ← JWT + Google OAuth
│   └── routes/             ← writing, reading, speaking,
│                              listening, chat, progress, memory,
│                              pedagogy, schedule, telegram
├── app/                    ← Python services (AI + business logic)
│   ├── pedagogy/           ← Pedagogical Skill Layer (deterministic)
│   │   ├── stages.py       ← LearnerStage, SupportLevel, band_to_stage()
│   │   ├── registry.py     ← 16 frameworks loaded from JSON
│   │   ├── descriptors.py  ← band descriptors + Backward Design targets
│   │   ├── stage_resolver.py ← live criterion stage + support lookup
│   │   ├── planner.py      ← deterministic routing + session plan builder
│   │   ├── session_policy.py ← practice condition gates per stage
│   │   ├── action_tags.py  ← [ACTION: hint level=N] parser
│   │   ├── fading.py       ← support-fading guardrail
│   │   └── spine.py        ← Feedback Triad soft validator
│   ├── data/               ← IELTS content, taxonomies, framework JSON
│   │   ├── pedagogical_frameworks.json  ← 16 frameworks + shared spine
│   │   └── band_descriptors.json        ← per-criterion band text (4–9)
│   ├── services/           ← scoring, memory, tts, asr, mcp,
│   │                          chat_coach, coach, pedagogical_event,
│   │                          telegram_service, calendar_service,
│   │                          schedule_service, embedding_service
│   ├── prompts/            ← Qwen prompt templates (4 tutor skills)
│   ├── db/                 ← SQLAlchemy models + session factory
│   ├── mcp/                ← MCP server (FastMCP)
│   └── utils/              ← JSON parser, logger, scoring helpers
├── frontend/               ← React app (Vite + Tailwind)
│   └── src/
│       ├── api/            ← axios clients per module
│       ├── components/     ← AppShell, ProtectedRoute
│       └── pages/          ← one page per module
├── scripts/
│   ├── db_backup.py        ← SQLite ↔ Alibaba Cloud OSS backup/restore
│   └── eval_pedagogy.py    ← offline pedagogy behaviour eval
├── tests/                  ← pedagogy test suites (registry, planner, integration)
├── docs/
│   └── pedagogy_framework.md ← full pedagogical design + code map
├── Dockerfile              ← multi-stage: React build + Python + Nginx
├── docker-compose.yml      ← local Docker development
├── docker-compose.prod.yml ← production orchestration (ECS)
├── nginx.conf              ← reverse proxy + SSE support
├── seed_demo.py            ← demo account seeder
├── ARCHITECTURE.md         ← system design + agent loop + DB schema
└── CLAUDE.md               ← agent build harness (read before coding)
```

---

## Who this is for

3.5 million people take IELTS every year. Most of them are not students — they are **working professionals** in Lagos, Nairobi, Manila, Dhaka, and dozens of other cities who need a Band 6.5 or 7.0 to unlock a visa, a job offer, or a university place in an English-speaking country.

They cannot attend classes. They study on their phone during a commute, in a lunch break, or at 10pm after the kids are in bed. Existing tools give them the same generic feedback every session with no memory of what they worked on last week. Qonda is built for them — an AI coach that learns who they are and gets smarter every time they practise, fitting around a full-time life rather than demanding they rearrange it.

## Productization roadmap

```
Phase 1 (current) — Solo practitioner web app
  ✅ All 4 IELTS skills with persistent AI memory
  ✅ Band estimates (4.0–8.5) per skill, updated after every session
  ✅ Adaptive content — difficulty matched to current band level
  ✅ Specialist AI tutors grounded in real practice evidence
  ✅ Cross-section insights — identifies core gaps across skills
  ✅ MCP server (12 tools) — memory + scheduling accessible to external agents
  ✅ Handwritten essay upload via qwen-vl
  ✅ Study scheduler — recurring sessions with Google Calendar integration
  ✅ Telegram bot — Qwen agent with tool-calling, coaching on any device

Phase 2 — Mobile-first consumer product
  ⬜ React Native app (same FastAPI backend, zero re-architecture)
  ⬜ Push notifications via Telegram: "You haven't practised Writing in 3 days"
  ⬜ Offline mode — download practice content, sync results later
  ⬜ Streak tracking and milestone celebrations
  ⬜ Voice selection for TTS — learners choose their examiner accent
     (British, American, Australian) to practise with the accent
     they will face in their actual test

Phase 3 — Freemium at scale
  ⬜ Free tier: 5 sessions/month, memory limited to last 3 sessions
  ⬜ Premium: $9.99/month — unlimited sessions, full persistent memory,
     all 4 sections, complete band history
  ⬜ Target price point is globally accessible — less than one prep book
  ⬜ PostgreSQL migration for multi-region scale
  ⬜ Payment via Stripe (card) + regional methods (M-Pesa, GCash, UPI)

Phase 4 — Community and accountability
  ⬜ Anonymous band leaderboards by target score and country
  ⬜ Study groups — 2-3 learners compare progress and hold each other
     accountable (the most powerful retention mechanism for adult learners)
  ⬜ Milestone sharing — "I just hit Band 6.5 on Writing 🎉"
  ⬜ Referral programme — one month free for each friend who reaches
     their target band

Phase 5 — Platform
  ⬜ Public MCP API — licensed IELTS tutors query a learner's full
     coaching profile (with consent) and pick up exactly where the
     app left off; Qonda becomes infrastructure for the broader
     IELTS prep ecosystem
  ⬜ Taxonomy contribution — community validates and extends skill
     definitions; open-source core, hosted service
  ⬜ Webhook system — notify integrations when a learner hits their
     target band
```

**Business model:** Freemium direct-to-consumer. Free tier drives acquisition at scale across emerging markets. Premium at $9.99/month converts the motivated — a learner spending $250 on an IELTS test fee will pay $10/month for a coach that actually remembers them. MCP API access for third-party tutoring platforms provides a B2B revenue layer without the complexity of institutional sales cycles.

---

## Key design decisions

**1. No agent framework** — LangChain/LlamaIndex were evaluated and rejected. Every pipeline is a fixed, known sequence. A framework adds abstraction cost with no benefit when there's no dynamic tool selection.

**2. Deterministic rank engine** — AI classifies (strength/weakness/not_applicable), Python counts to three and ranks up. Rank changes are auditable, tamper-proof and explainable.

**3. Three separate Qwen calls per Writing submission** — essay evaluation (qwen-plus), skill classification (qwen-turbo), memory extraction (qwen-plus) are separate by design. Long feedback responses contain apostrophes that break JSON parsing. Isolation means one failure cannot cascade to the others.

**4. OSS for audio** — Listening track audio is generated once globally and stored in Alibaba Cloud OSS. Every learner gets it from OSS instantly. The TTS quota is consumed exactly once per track for all users for all time — adding a new track costs one TTS call regardless of how many learners use it.

**5. MCP as the memory API** — exposing the memory layer as MCP means any compatible agent can query learner coaching history without database access. The Qonda memory becomes infrastructure, not just an app feature.

---

## Roadmap

- [x] Auth — Google OAuth + username/password + JWT
- [x] Writing Coach — essay, AI scoring, streaming SSE
- [x] Reading Coach — passages, questions, results
- [x] Speaking Coach — ASR + TTS + 3-part session, recording timer
- [x] Listening Coach — TTS audio + OSS caching
- [x] IELTS Tutor — 4 specialist AI tutors with pedagogical session plans
- [x] Writing skill taxonomy (13 sub-skills, Band Descriptors)
- [x] Deterministic rank engine
- [x] Memory Timeline visualization
- [x] Skill Mastery dedicated page with per-criterion stage display
- [x] MCP server (12 tools — memory, skills, scheduling)
- [x] Alibaba Cloud deployment (ECS + OSS + Model Studio)
- [x] Pedagogical Skill Layer — 16 frameworks, 4 stages, support fading
- [x] ACTION tag protocol — evidence loop closes after every tutor session
- [x] PostgreSQL 16 — persistent named volume, survives container rebuilds
- [x] Semantic memory embeddings — DashScope text-embedding-v3, hybrid retrieval
- [x] Study scheduler — recurring sessions with Google Calendar integration
- [x] Telegram bot — Qwen agent with tool-calling (@qieltsbot)
- [ ] Listening replay/transcript condition gates in frontend UI
- [ ] Extend skill taxonomy to Reading, Speaking, Listening (pending)
- [ ] Teacher / admin dashboard
- [ ] Video walkthrough
