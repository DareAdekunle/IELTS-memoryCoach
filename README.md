# 🎯 IELTS MemoryCoach

An AI-powered IELTS coaching web application with persistent memory,
skill-level tracking, and a conversational AI tutor.

Built with React, FastAPI, Qwen AI (text, ASR and TTS), SQLite and Docker.

---

## What it does

IELTS MemoryCoach is a full-stack web app that remembers learners across
sessions. Unlike a simple quiz tool, it tracks weaknesses, monitors
improvement, personalises feedback over time using a MemoryAgent system,
and actively teaches learners through a conversational AI coach — across
all four IELTS skills.

**Core features:**
- Google OAuth and username/password authentication with JWT sessions
- Real IELTS practice content for Writing, Reading, Speaking and Listening
- AI-powered scoring using official IELTS rubrics and band descriptors
- Live speech-to-text (ASR) and text-to-speech (TTS) for Speaking
  and Listening modules
- Persistent memory that extracts coaching insights after every attempt
- Memory that strengthens, weakens and archives based on new evidence
- Granular skill taxonomy (13 sub-skills for Writing) grounded in the
  official IELTS Task 2 Band Descriptors (British Council / IDP / Cambridge)
- Deterministic skill ranking (5 levels per skill, evidence-count based)
- Conversational AI Chat Coach that teaches the learner's weakest skill,
  quoting their actual essay and real memory evidence
- Progress dashboard showing score trends across all four skills
- Memory dashboard showing everything the coach knows about the learner

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React (Vite) + Tailwind CSS |
| Backend API | FastAPI (Python) |
| AI / LLM | Qwen API (OpenAI-compatible SDK for text) |
| Speech-to-Text | qwen3-asr-flash (DashScope SDK) |
| Text-to-Speech | qwen3-tts-flash-2025-11-27 (DashScope SDK) |
| Auth | JWT + Google OAuth (Authlib) |
| Database | SQLite via SQLAlchemy |
| Audio recording | Browser MediaRecorder API |
| Audio processing | pydub + ffmpeg |
| Containerisation | Docker + Docker Compose |
| Reverse proxy | Nginx |

**No agent framework** (no LangChain, LlamaIndex, etc.) — all
orchestration is hand-rolled Python. All ranking logic is deterministic.

---

## Getting started

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/IELTS-memorycoach.git
cd IELTS-memorycoach
```

### 2. Configure environment variables

Create a `.env` file in the project root:

```
DASHSCOPE_API_KEY=your_dashscope_key_here
GOOGLE_CLIENT_ID=your_google_oauth_client_id
GOOGLE_CLIENT_SECRET=your_google_oauth_client_secret
JWT_SECRET=a_long_random_secret_string
FRONTEND_URL=http://localhost:5173
```

Get your DashScope API key from: https://dashscope-intl.aliyuncs.com
Set up Google OAuth at: https://console.cloud.google.com

### 3. Run with Docker (recommended)

```bash
docker compose up --build
```

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API docs: http://localhost:8000/docs

### 4. Run for development (two terminals)

**Terminal 1 — FastAPI backend:**
```bash
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000
```

**Terminal 2 — React frontend:**
```bash
cd frontend
npm install
npm run dev
```

### 5. First time setup

1. Go to http://localhost:5173
2. Register an account or sign in with Google
3. Complete the onboarding form to create your learner profile
4. Start with Writing Coach to build your memory profile
5. Use Chat Coach after a few essays for personalised tutoring

---

## IELTS Modules

### ✍️ Writing Coach
- 7 academic writing prompts (beginner → advanced)
- Task types: Academic Discussion, Agree or Disagree, Problem and Solution
- AI evaluation against 5 official IELTS writing rubric categories
- Skill taxonomy classification — each essay updates 13 granular
  sub-skill ranks (Beginner → Developing → Intermediate → Proficient →
  Advanced) using a deterministic rule engine
- Full memory lifecycle: extract → retrieve → update → archive

### 📖 Reading Coach
- 3 full reading passages (beginner → advanced)
- 10 questions per passage: Multiple Choice, True/False/Not Given,
  Short Answer
- Objective questions checked instantly against answer key
- Short answers evaluated by Qwen for partial credit
- Full memory lifecycle

### 🎤 Speaking Coach
- 15 prompt sets (beginner → advanced)
- All 3 IELTS Speaking parts in one structured session
- Browser microphone recording or audio file upload
- qwen3-asr-flash transcribes spoken responses in real time
- Qwen evaluates all three parts together as a real examiner
- qwen3-tts-flash (Cherry voice) reads examiner feedback aloud
- Band scores (1-9): Fluency, Lexical Resource, Grammar, Pronunciation
- Full memory lifecycle

### 🎧 Listening Coach
- 4 tracks covering all 4 IELTS Listening parts
- Audio generated on demand — Cherry reads scripts via TTS
- Exam conditions: questions previewed first while audio generates
  in background, audio plays once, learner answers while listening
- Question types: Multiple Choice, Form Completion, Short Answer
- Fuzzy answer matching handles spelling/number/phrasing variations
- Full memory lifecycle

### 💬 Chat Coach
- Conversational AI tutor identifying the learner's weakest writing
  sub-skill from the 13-skill taxonomy
- Opens by quoting specific sentences from the learner's own essays
  and real memory evidence — not generic advice
- Internal state machine (introduction → explaining → drilling →
  bridge to practice) behind a natural chat UI
- Inline drills generated on demand, personalised to the learner
- Politely redirects off-topic questions back to IELTS coaching
- Session-only conversation history; only extracted memories persist

---

## Skill Mastery System (Writing)

### Taxonomy — 13 sub-skills derived from IELTS Band Descriptors

| Category | Sub-skills |
|---|---|
| Task Response | Full Task Coverage, Clarity of Position, Idea Development, Conclusion Synthesis |
| Coherence & Cohesion | Logical Progression, Paragraphing, Cohesive Devices |
| Lexical Resource | Vocabulary Range, Word Choice Precision, Spelling & Word Formation |
| Grammatical Range & Accuracy | Sentence Variety, Grammatical Accuracy, Punctuation Control |

### Rank-up rule (deterministic)

```
After each Writing essay, a second Qwen call classifies
every skill_id using a fixed-list prompt:

  "demonstrated_strength" → clean_streak += 1
  "demonstrated_weakness" → clean_streak = 0 (full reset)
  "not_applicable"        → no change

clean_streak reaches 3 → current_rank += 1 (max 5)
Rank NEVER decreases automatically.
```

---

## API reference

The FastAPI backend exposes a full REST API at `/docs` (Swagger UI).

| Prefix | Description |
|---|---|
| `/auth` | Register, login, Google OAuth, JWT management |
| `/writing` | Prompts, essay submission, attempts |
| `/reading` | Passages, answer submission, attempts |
| `/speaking` | Prompt sets, ASR transcription, TTS, evaluation |
| `/listening` | Tracks, TTS audio generation, answer submission |
| `/chat` | Chat session start and continuation |
| `/progress` | Summary, per-section trends, skill ranks |
| `/memory` | Active and archived coaching memories |

---

## Project structure

```
IELTS-memorycoach/
├── api/                                 # FastAPI backend
│   ├── main.py                          # App entry point, CORS, middleware
│   ├── dependencies.py                  # JWT auth, DB session dependencies
│   ├── auth/
│   │   ├── router.py                    # /auth routes + Google OAuth
│   │   ├── models.py                    # User SQLAlchemy model
│   │   ├── schemas.py                   # Pydantic request/response schemas
│   │   └── utils.py                     # JWT creation, bcrypt hashing
│   └── routes/
│       ├── writing.py
│       ├── reading.py
│       ├── speaking.py
│       ├── listening.py
│       ├── chat.py
│       ├── progress.py
│       └── memory.py
│
├── app/                                 # Python services (used by FastAPI)
│   ├── services/                        # All AI/business logic
│   ├── prompts/                         # Qwen prompt templates
│   ├── data/                            # IELTS content JSON files
│   ├── db/                              # SQLAlchemy models and init
│   └── utils/                           # JSON parser, score helpers
│
├── frontend/                            # React application
│   ├── src/
│   │   ├── api/                         # Axios API clients per module
│   │   ├── components/                  # AppShell, ProtectedRoute
│   │   ├── context/                     # AuthContext (JWT state)
│   │   └── pages/                       # One file per page/module
│   ├── tailwind.config.js
│   └── vite.config.js
│
├── Dockerfile                           # FastAPI + React build
├── docker-compose.yml                   # Full stack orchestration
├── nginx.conf                           # Reverse proxy config
├── requirements.txt                     # Python deps (hand-maintained)
├── CLAUDE.md                            # Agent build harness
└── .env                                 # Secrets (never committed)
```

---

## Database schema

| Table | Purpose |
|---|---|
| users | Auth accounts (local + Google OAuth) |
| learners | Learner profiles and IELTS goals |
| practice_attempts | Every attempt across all 4 sections |
| learner_memories | Free-text coaching memories per skill |
| mastery_scores | Section-level score history |
| session_summaries | Session summaries |
| learner_skill_ranks | 13-skill granular ranks with clean_streak |

---

## Deployment (Alibaba Cloud ECS)

### Architecture (single server, hackathon scale)

```
Internet
    ↓
ECS Instance (Ubuntu 22.04)
    ↓
Nginx (port 80/443)
    ├── /api/* → FastAPI (port 8000, uvicorn)
    └── /* → React static files
    ↓
SQLite database (Docker volume, persists across restarts)
```

### Security Group rules

| Port | Source | Purpose |
|---|---|---|
| 22 | Your IP only | SSH management |
| 80 | 0.0.0.0/0 | HTTP |
| 443 | 0.0.0.0/0 | HTTPS (when domain added) |

### Deploy steps

```bash
# On the ECS instance:
git clone https://github.com/yourusername/IELTS-memorycoach.git
cd IELTS-memorycoach
cp .env.example .env   # fill in your keys
docker compose up -d --build
```

App is live at: http://YOUR_ECS_IP

---

## Roadmap

- [x] Auth — Google OAuth + username/password + JWT
- [x] Writing Coach with full memory cycle + skill taxonomy
- [x] Reading Coach with full memory cycle
- [x] Speaking Coach with ASR + TTS + full memory cycle
- [x] Listening Coach with TTS-generated audio + full memory cycle
- [x] Chat Coach — conversational AI tutor
- [x] Writing skill taxonomy (13 sub-skills, IELTS band descriptors)
- [x] Deterministic skill ranking system
- [x] React frontend with full auth flow
- [x] FastAPI REST backend
- [ ] Extend skill taxonomy to Reading, Speaking, Listening
- [ ] Skill mastery dashboard page
- [ ] HTTPS with Let's Encrypt
- [ ] PostgreSQL upgrade for multi-server scale
- [ ] Teacher / admin dashboard
- [ ] Cloud deployment (Alibaba Cloud ECS)