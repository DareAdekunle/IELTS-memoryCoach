# 🎯 IELTS MemoryCoach

An AI-powered IELTS coaching app with persistent memory.
Built with Streamlit, Qwen AI (text, ASR and TTS), SQLite and Docker.

---

## What it does

IELTS MemoryCoach is a local coaching app that remembers learners
across sessions. Unlike a simple essay grader or quiz tool, it tracks
weaknesses, monitors improvement and personalises feedback over time
using a MemoryAgent system — across **all four IELTS skills**.

**Core features:**
- Real IELTS practice content for Writing, Reading, Speaking and Listening
- AI-powered scoring using official IELTS rubrics and band descriptors
- Live speech-to-text and text-to-speech for the Speaking and Listening modules
- Persistent memory that extracts coaching insights after every attempt
- Memory that strengthens, weakens and archives based on new evidence
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

---

## Getting started

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/IELTS-memorycoach.git
cd IELTS-memorycoach
```

### 2. Add your API key

Create a `.env` file in the root folder:

> DASHSCOPE_API_KEY=your_key_here

Get your API key from: https://dashscope-intl.aliyuncs.com

### 3. Run with Docker

```bash
docker compose up --build
```

Open your browser at: **http://localhost:8501**

### 4. First time setup

1. Click **Profile** in the sidebar and create your learner profile
2. Try each coaching module:
   - **Writing Coach** — submit an essay
   - **Reading Coach** — complete a passage
   - **Speaking Coach** — record or upload spoken responses
   - **Listening Coach** — listen to a generated track and answer
3. Check **Progress** and **Memory** dashboards after each attempt

---

## IELTS Modules

### ✍️ Writing Coach
- 7 academic writing prompts across beginner, intermediate and advanced levels
- Task types: Academic Discussion, Agree or Disagree, Problem and Solution
- AI evaluation against 5 official IELTS writing criteria:
  Thesis Clarity, Organization, Grammar, Vocabulary, Idea Development
- Scores out of 5 per skill with strengths, weaknesses and next steps
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
- **qwen3-asr-flash** transcribes every spoken response in real time
- Qwen evaluates all three parts together as a real examiner would,
  giving conversational feedback referencing actual things the learner said
- **qwen3-tts-flash** (Cherry voice) reads the examiner feedback aloud
- Band scores (1-9) across Fluency, Lexical Resource, Grammar, Pronunciation
- Full memory lifecycle: extract → retrieve → update → archive

### 🎧 Listening Coach
- 4 listening tracks covering all 4 IELTS Listening parts:
  Part 1 (social conversation), Part 2 (monologue), Part 3 (academic
  discussion), Part 4 (lecture)
- Audio is **generated on demand** — Cherry reads natural scripts aloud
  via TTS, no pre-recorded audio files needed
- Mirrors real exam conditions: questions previewed first, audio plays
  once, learner answers while listening
- Audio generates in the background while the learner reads questions
  so no time is wasted
- Question types: Multiple Choice, Form Completion, Short Answer
- Fuzzy answer matching handles spelling, number words and phrasing variations
- Full memory lifecycle: extract → retrieve → update → archive

---

## Project structure

IELTS-memorycoach/

├── app/

│   ├── main.py                          # Home page

│   ├── pages/

│   │   ├── 1_Profile.py                 # Learner profile

│   │   ├── 2_Writing_Coach.py           # Writing practice

│   │   ├── 3_Reading_Coach.py           # Reading practice

│   │   ├── 4_Progress_Dashboard.py      # Score trends, all 4 skills

│   │   ├── 5_Memory_Dashboard.py        # Memory viewer

│   │   ├── 6_Speaking_Coach.py          # Speaking practice (ASR + TTS)

│   │   └── 7_Listening_Coach.py         # Listening practice (TTS)

│   ├── services/

│   │   ├── qwen_service.py              # Qwen text API wrapper

│   │   ├── asr_service.py                # Speech-to-text wrapper

│   │   ├── tts_service.py                # Text-to-speech wrapper

│   │   ├── memory_service.py             # Memory lifecycle (all sections)

│   │   ├── scoring_service.py            # Writing evaluator

│   │   ├── reading_service.py            # Reading evaluator

│   │   ├── speaking_service.py           # Speaking prompt loader

│   │   ├── speaking_evaluator_service.py # Speaking examiner logic

│   │   ├── listening_service.py          # Listening audio + answer checking

│   │   ├── practice_service.py           # Writing content loader

│   │   └── profile_service.py            # Learner profiles

│   ├── prompts/

│   │   ├── writing_evaluator_prompt.txt

│   │   ├── reading_evaluator_prompt.txt

│   │   ├── speaking_evaluator_prompt.txt

│   │   ├── memory_extractor_prompt.txt

│   │   ├── reading_memory_extractor.txt

│   │   ├── speaking_memory_extractor.txt

│   │   ├── listening_memory_extractor.txt

│   │   └── memory_update_prompt.txt

│   ├── data/

│   │   ├── writing_prompts.json          # 7 writing prompts

│   │   ├── reading_passages.json         # 3 reading passages

│   │   ├── speaking_prompts.json         # 15 speaking prompt sets

│   │   ├── listening_tracks.json         # 4 listening tracks

│   │   └── rubrics.json                  # Scoring rubrics

│   ├── db/

│   │   ├── database.py                   # SQLite connection

│   │   ├── models.py                     # Table definitions

│   │   └── init_db.py                    # Database initialiser

│   └── utils/

│       ├── json_utils.py                 # Safe JSON parser

│       └── scoring_utils.py               # Score helpers

├── Dockerfile

├── docker-compose.yml

├── requirements.txt

└── .env                                   # Not committed to Git

---

## How the memory system works

Learner completes a Writing, Reading, Speaking or Listening attempt

↓

Qwen evaluates the attempt against rubric/examiner criteria

↓

Memories extracted from evaluation results

(weaknesses, strengths, patterns observed)

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

Over time: feedback becomes fully personalised

across all four skills

### Memory lifecycle example
Attempt 1: "Learner writes essays without a clear thesis"

confidence: 0.65, evidence: 1
Attempt 2: Same weakness observed again

confidence: 0.80, evidence: 2
Attempt 3: Learner writes a strong thesis

confidence: 0.45, evidence: 3
Attempt 4: Consistent improvement confirmed

status: archived — skill considered mastered

This exact lifecycle runs independently for Writing, Reading, Speaking
and Listening — each skill builds its own evolving memory profile.

---

## How Speaking and Listening use voice AI
SPEAKING                              LISTENING

─────────────────────                 ─────────────────────

Learner records/uploads audio         Learner reads questions

↓                                     ↓

qwen3-asr-flash transcribes           qwen3-tts-flash generates

↓                             audio from a written script

Qwen evaluates transcription                  ↓

as an IELTS examiner                  Cherry reads it aloud

↓                                     ↓

qwen3-tts-flash (Cherry)              Learner listens once and

speaks the feedback aloud             answers while listening

---

## Database schema

| Table | Purpose |
|---|---|
| learners | Learner profiles and goals |
| practice_attempts | Every attempt across all 4 sections |
| learner_memories | Coaching memories per skill per section |
| mastery_scores | Current skill level per section |
| session_summaries | Session level summaries |

---

## Roadmap

- [x] Writing Coach with full memory cycle
- [x] Reading Coach with full memory cycle
- [x] Speaking Coach with ASR, TTS and full memory cycle
- [x] Listening Coach with TTS-generated audio and full memory cycle
- [ ] Chat Coach (free conversation with AI tutor)
- [ ] Teacher / admin dashboard
- [ ] More content — additional prompts, passages and tracks
- [ ] FastAPI backend upgrade
- [ ] PostgreSQL upgrade
- [ ] Cloud deployment