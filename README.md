# 🎯 IELTS MemoryCoach

An AI-powered IELTS coaching app with persistent memory, skill-level
tracking, and a conversational AI tutor.
Built with Streamlit, Qwen AI (text, ASR and TTS), SQLite and Docker.

---

## What it does

IELTS MemoryCoach is a local coaching app that remembers learners across
sessions. Unlike a simple essay grader or quiz tool, it tracks weaknesses,
monitors improvement, personalises feedback over time using a MemoryAgent
system — across all four IELTS skills — and now actively teaches learners
through a conversational AI coach grounded in official IELTS rubric criteria.

**Core features:**
- Real IELTS practice content for Writing, Reading, Speaking and Listening
- AI-powered scoring using official IELTS rubrics and band descriptors
- Live speech-to-text and text-to-speech for Speaking and Listening modules
- Persistent memory that extracts coaching insights after every attempt
- Memory that strengthens, weakens and archives based on new evidence
- Granular skill taxonomy (13 sub-skills for Writing) grounded in the
  official IELTS Task 2 Band Descriptors (British Council / IDP / Cambridge)
- Deterministic skill ranking (5 levels per skill, evidence-count based)
- Conversational AI Chat Coach that teaches the learner's weakest skill
  with drills, referencing their actual essay and real memory evidence
- Progress dashboard showing trends across all four skills
- Memory dashboard showing everything the coach knows about the learner

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | Streamlit |
| AI / LLM | Qwen API (OpenAI-compatible SDK for text, DashScope SDK for ASR/TTS) |
| Speech-to-Text | qwen3-asr-flash |
| Text-to-Speech | qwen3-tts-flash (Cherry voice) |
| Database | SQLite via SQLAlchemy |
| Audio recording | audio-recorder-streamlit |
| Audio processing | pydub + ffmpeg |
| Containerisation | Docker + Docker Compose |

**No agent framework used** (no LangChain, LlamaIndex, etc.) — all
orchestration is hand-rolled Python, which keeps the stack transparent
and debuggable.

---

## Getting started

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/IELTS-memorycoach.git
cd IELTS-memorycoach
```

### 2. Add your API key

Create a `.env` file in the root folder:

```
DASHSCOPE_API_KEY=your_key_here
```

Get your API key from: https://dashscope-intl.aliyuncs.com

### 3. Run with Docker

```bash
docker compose up --build
```

Open your browser at: **http://localhost:8501**

### 4. First time setup

1. Click **Profile** in the sidebar and create your learner profile
2. Try each coaching module:
   - **Writing Coach** — submit an essay to start building your skill profile
   - **Reading Coach** — complete a passage
   - **Speaking Coach** — record or upload spoken responses
   - **Listening Coach** — listen to a generated track and answer questions
   - **Chat Coach** — talk to your AI tutor about your weakest skill
3. Check **Progress** and **Memory** dashboards after each attempt

---

## IELTS Modules

### ✍️ Writing Coach
- 7 academic writing prompts across beginner, intermediate and advanced levels
- Task types: Academic Discussion, Agree or Disagree, Problem and Solution
- AI evaluation against 5 official IELTS writing rubric categories:
  Thesis Clarity, Organization, Grammar, Vocabulary, Idea Development
- **Skill taxonomy classification**: after every essay, a second focused
  Qwen call maps the attempt to 13 granular sub-skills derived from the
  official IELTS Task 2 Band Descriptors, updating the learner's rank on
  each skill (5 levels: Beginner → Developing → Intermediate → Proficient
  → Advanced), using a deterministic rule engine — no AI judgement in
  rank decisions, only a clean_streak counter
- Full memory lifecycle: extract → retrieve → update → archive

### 📖 Reading Coach
- 3 full reading passages across beginner, intermediate and advanced levels
- 10 questions per passage: Multiple Choice, True/False/Not Given, Short Answer
- Objective questions checked instantly; short answers evaluated by Qwen
- Skill tracking: Main Idea, Detail Retrieval, Inference, Vocabulary in Context
- Full memory lifecycle: extract → retrieve → update → archive

### 🎤 Speaking Coach
- 15 prompt sets across beginner, intermediate and advanced levels
- Covers all 3 IELTS Speaking parts in one structured session:
  Part 1 (personal questions), Part 2 (long turn with cue card),
  Part 3 (abstract discussion)
- Learner responds by microphone recording or audio file upload
- **qwen3-asr-flash** transcribes every spoken response in real time,
  with automatic compression and chunking for long recordings
- Qwen evaluates all three parts together as a real examiner giving
  conversational feedback referencing the learner's actual words
- **qwen3-tts-flash** (Cherry voice) reads examiner feedback aloud
- Band scores (1-9) across Fluency, Lexical Resource, Grammar, Pronunciation
- Full memory lifecycle: extract → retrieve → update → archive

### 🎧 Listening Coach
- 4 listening tracks covering all 4 IELTS Listening parts:
  Part 1 (social conversation), Part 2 (monologue),
  Part 3 (academic discussion), Part 4 (lecture)
- Audio generated on demand — Cherry reads natural scripts aloud via TTS
- Mirrors real exam conditions: questions previewed first while audio
  generates in the background, audio plays once, learner answers
  while listening (no replay after answering begins)
- Question types: Multiple Choice, Form Completion, Short Answer
- Fuzzy answer matching handles spelling, number words and phrasing variants
- Full memory lifecycle: extract → retrieve → update → archive

### 💬 Chat Coach
- A conversational AI tutor powered by the same Qwen text model
- Automatically identifies the learner's weakest skill across all 13 Writing
  sub-skills using the skill ranking data from Writing Coach sessions
- Opens by quoting specific evidence from the learner's own essays and
  learner_memories — not generic advice
- Follows a structured internal teaching sequence (introduction →
  explaining → drilling → bridge to practice) while sounding like a
  natural conversation, using explicit [STATE: x] tags for reliable
  UI state tracking without exposing them to the learner
- Generates focused drills inline, personalised to the specific skill and
  the learner's actual writing patterns
- Politely redirects off-topic questions back to IELTS coaching
- Brand-new learners with no essay history get a warm welcome and are
  directed to Writing Coach first before skill-specific coaching begins
- Session-only: conversation history lives in st.session_state, only
  extracted memories persist across sessions
- Auto-resets when learner profile switches mid-browser-session

---

## Skill Mastery System (Writing)

The skill mastery system adds a layer of granular, progressive skill
tracking beneath the existing 5-rubric Writing scoring.

### Taxonomy

13 sub-skills derived from the official IELTS Task 2 Band Descriptors:

| Category | Sub-skills |
|---|---|
| Task Response | Full Task Coverage, Clarity of Position, Idea Development, Conclusion Synthesis |
| Coherence & Cohesion | Logical Progression, Paragraphing, Cohesive Devices |
| Lexical Resource | Vocabulary Range, Word Choice Precision, Spelling & Word Formation |
| Grammatical Range & Accuracy | Sentence Variety, Grammatical Accuracy, Punctuation Control |

### Rank levels (per skill)

```
1 — Beginner
2 — Developing
3 — Intermediate
4 — Proficient
5 — Advanced
```

### Rank-up rule (deterministic, no AI judgement)

```
On each Writing attempt, a second Qwen call classifies the essay
against every skill_id using a fixed-list prompt:
  "demonstrated_strength" → clean_streak += 1
  "demonstrated_weakness" → clean_streak = 0 (full reset)
  "not_applicable"        → no change

clean_streak reaches 3 → current_rank += 1 (capped at 5)
Streak resets to 0 on rank-up.
Rank NEVER decreases automatically.
```

This means rank changes are fully auditable — you can inspect
`learner_skill_ranks` in DB Browser and see exactly why any rank moved.

---

## Project structure

```
IELTS-memorycoach/
├── app/
│   ├── main.py                              # Home page
│   ├── pages/
│   │   ├── 1_Profile.py                     # Learner profile
│   │   ├── 2_Writing_Coach.py               # Writing practice + skill ranking
│   │   ├── 3_Reading_Coach.py               # Reading practice
│   │   ├── 4_Progress_Dashboard.py          # Score trends, all 4 skills
│   │   ├── 5_Memory_Dashboard.py            # Memory viewer
│   │   ├── 6_Speaking_Coach.py              # Speaking practice (ASR + TTS)
│   │   ├── 7_Listening_Coach.py             # Listening practice (TTS)
│   │   └── 8_Chat_Coach.py                  # Conversational AI tutor
│   ├── services/
│   │   ├── qwen_service.py                  # Qwen text API wrapper
│   │   ├── asr_service.py                   # Speech-to-text (dashscope)
│   │   ├── tts_service.py                   # Text-to-speech (dashscope)
│   │   ├── memory_service.py                # Memory lifecycle + skill ranking
│   │   ├── scoring_service.py               # Writing evaluator
│   │   ├── skill_classifier_service.py      # 13-skill taxonomy classifier
│   │   ├── skill_taxonomy_service.py        # Taxonomy loader + rank helpers
│   │   ├── chat_coach_service.py            # Chat session management
│   │   ├── reading_service.py               # Reading evaluator
│   │   ├── speaking_service.py              # Speaking prompt loader
│   │   ├── speaking_evaluator_service.py    # Speaking examiner logic
│   │   ├── listening_service.py             # Listening audio + answer checking
│   │   ├── practice_service.py              # Writing content loader
│   │   └── profile_service.py              # Learner profiles
│   ├── prompts/
│   │   ├── writing_evaluator_prompt.txt     # Rubric scoring + memory context
│   │   ├── skill_classifier_prompt.txt      # Fixed-list 13-skill classifier
│   │   ├── chat_coach_prompt.txt            # Conversational tutor (history learner)
│   │   ├── chat_coach_welcome_prompt.txt    # Welcome message (new learner)
│   │   ├── reading_evaluator_prompt.txt
│   │   ├── speaking_evaluator_prompt.txt
│   │   ├── memory_extractor_prompt.txt
│   │   ├── reading_memory_extractor.txt
│   │   ├── speaking_memory_extractor.txt
│   │   ├── listening_memory_extractor.txt
│   │   └── memory_update_prompt.txt
│   ├── data/
│   │   ├── skill_taxonomy_writing.json      # 13 sub-skills, 5 ranks each
│   │   ├── writing_prompts.json             # 7 writing prompts
│   │   ├── reading_passages.json            # 3 reading passages
│   │   ├── speaking_prompts.json            # 15 speaking prompt sets
│   │   ├── listening_tracks.json            # 4 listening tracks
│   │   └── rubrics.json                     # Scoring rubrics
│   ├── db/
│   │   ├── database.py                      # SQLite connection
│   │   ├── models.py                        # Table definitions (6 tables)
│   │   └── init_db.py                       # Database initialiser
│   └── utils/
│       ├── json_utils.py                    # Safe JSON parser (5 fallbacks)
│       └── scoring_utils.py                 # Score helpers
├── Dockerfile                               # ffmpeg + Python 3.11 + pip install
├── docker-compose.yml
├── requirements.txt                         # Hand-maintained (not pip freeze)
├── CLAUDE.md                                # Agent build harness
└── .env                                     # Not committed to Git
```

---

## Database schema

| Table | Purpose |
|---|---|
| learners | Learner profiles and goals |
| practice_attempts | Every attempt across all 4 sections |
| learner_memories | Free-text coaching memories per skill per section |
| mastery_scores | Legacy section-level scores |
| session_summaries | Session-level summaries |
| learner_skill_ranks | Granular 13-skill ranks with clean_streak counter |

---

## How the memory system works

```
Learner completes a Writing, Reading, Speaking or Listening attempt
        ↓
Qwen evaluates the attempt against rubric/examiner criteria
        ↓
Memories extracted from evaluation results
(free-text: weaknesses, strengths, patterns observed)
        ↓
New memories compared against existing memories
        ↓
Existing memories strengthened, weakened or archived
based on new evidence
        ↓
Next session: coach retrieves memories before evaluating
        ↓
Feedback directly references the learner's history
        ↓
[Writing only] A second Qwen call classifies the essay against
13 fixed skill_ids → updates learner_skill_ranks deterministically
        ↓
Chat Coach reads learner_skill_ranks + learner_memories to open
a targeted teaching session on the weakest skill
```

---

## How Speaking and Listening use voice AI

```
SPEAKING                                LISTENING
──────────────────────────              ────────────────────────────
Learner records/uploads audio           Learner reads questions first
        ↓                               while Cherry generates audio
qwen3-asr-flash transcribes             in background
(compress → chunk if needed)                    ↓
        ↓                               Cherry reads script once
Qwen evaluates transcription            (exam conditions, no replay)
as IELTS examiner                               ↓
        ↓                               Learner answers while listening
qwen3-tts-flash (Cherry)
speaks feedback aloud
```

---

## Roadmap

- [x] Writing Coach with full memory cycle
- [x] Reading Coach with full memory cycle
- [x] Speaking Coach with ASR, TTS and full memory cycle
- [x] Listening Coach with TTS-generated audio and full memory cycle
- [x] Writing skill taxonomy (13 sub-skills, official IELTS band descriptors)
- [x] Deterministic skill ranking system (5 levels, clean_streak rule engine)
- [x] Chat Coach — conversational AI tutor grounded in real skill evidence
- [ ] Extend skill taxonomy to Reading, Speaking and Listening
- [ ] Skill mastery dashboard (dedicated view of 13-skill progress)
- [ ] Teacher / admin dashboard
- [ ] More content — additional prompts, passages and tracks
- [ ] FastAPI backend upgrade
- [ ] PostgreSQL upgrade
- [ ] Cloud deployment