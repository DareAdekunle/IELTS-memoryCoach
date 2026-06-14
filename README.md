Open README.md and replace everything with this:
markdown# 🎯 IELTS MemoryCoach

An AI-powered IELTS coaching app with persistent memory.
Built with Streamlit, Qwen AI, SQLite and Docker.

---

## What it does

IELTS MemoryCoach is a local coaching app that remembers learners
across sessions. Unlike a simple essay grader or quiz tool, it tracks
weaknesses, monitors improvement and personalises feedback over time
using a MemoryAgent system.

**Core features:**
- Real IELTS writing prompts with difficulty levels
- Real IELTS reading passages with 10 questions per passage
- AI-powered scoring using official IELTS rubrics
- Persistent memory that extracts coaching insights after each attempt
- Memory that strengthens, weakens and archives based on new evidence
- Progress dashboard showing score trends across both Writing and Reading
- Memory dashboard showing everything the coach knows about the learner

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | Streamlit |
| AI / LLM | Qwen API (via OpenAI-compatible SDK + DashScope SDK) |
| Database | SQLite via SQLAlchemy |
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
DASHSCOPE_API_KEY=your_key_here

Get your free API key from: https://dashscope-intl.aliyuncs.com

### 3. Run with Docker

```bash
docker compose up --build
```

Open your browser at: **http://localhost:8501**

### 4. First time setup

1. Click **Profile** in the sidebar
2. Create your learner profile
3. Go to **Writing Coach** and submit your first essay
4. Go to **Reading Coach** and complete your first passage
5. Check **Progress** and **Memory** dashboards after each attempt

---

## IELTS Modules

### ✍️ Writing Coach
- 7 academic writing prompts across beginner, intermediate and advanced levels
- Task types: Academic Discussion, Agree or Disagree, Problem and Solution
- AI evaluation against 5 official IELTS writing criteria:
  - Thesis Clarity, Organization, Grammar, Vocabulary, Idea Development
- Scores out of 5 per skill with strengths and weaknesses breakdown
- Recommended next step after every attempt
- Full memory lifecycle: extract → retrieve → update → archive

### 📖 Reading Coach
- 3 full reading passages across beginner, intermediate and advanced levels
- Topics: Society and Culture, Health and Science, Technology and Economy
- 10 questions per passage in three formats:
  - Multiple Choice (3 questions) — checked instantly against answer key
  - True / False / Not Given (4 questions) — checked instantly against answer key
  - Short Answer (3 questions) — evaluated by Qwen AI for partial credit
- Skill tracking across: Main Idea, Detail Retrieval, Inference,
  Vocabulary in Context, True/False/NG accuracy
- Detailed question review with explanations for every wrong answer
- Full memory lifecycle: extract → retrieve → update → archive

---

## Project structure
IELTS-memorycoach/

├── app/

│   ├── main.py                        # Home page

│   ├── pages/

│   │   ├── 1_Profile.py               # Learner profile

│   │   ├── 2_Writing_Coach.py         # Writing practice

│   │   ├── 3_Reading_Coach.py         # Reading practice

│   │   ├── 4_Progress_Dashboard.py    # Score trends

│   │   └── 5_Memory_Dashboard.py      # Memory viewer

│   ├── services/

│   │   ├── agent_controller.py        # App coordinator

│   │   ├── qwen_service.py            # Qwen text API wrapper

│   │   ├── memory_service.py          # Memory lifecycle

│   │   ├── scoring_service.py         # Writing evaluator

│   │   ├── reading_service.py         # Reading evaluator

│   │   ├── practice_service.py        # Content loader

│   │   └── profile_service.py         # Learner profiles

│   ├── prompts/

│   │   ├── writing_evaluator_prompt.txt

│   │   ├── reading_evaluator_prompt.txt

│   │   ├── memory_extractor_prompt.txt

│   │   ├── reading_memory_extractor.txt

│   │   ├── memory_update_prompt.txt

│   │   └── coach_prompt.txt

│   ├── data/

│   │   ├── writing_prompts.json       # 7 writing prompts

│   │   ├── reading_passages.json      # 3 reading passages

│   │   └── rubrics.json               # Scoring rubrics

│   ├── db/

│   │   ├── database.py                # SQLite connection

│   │   ├── models.py                  # Table definitions

│   │   └── init_db.py                 # Database initialiser

│   └── utils/

│       ├── json_utils.py              # Safe JSON parser

│       └── scoring_utils.py           # Score helpers

├── Dockerfile

├── docker-compose.yml

├── requirements.txt

└── .env                               # Not committed to Git

---

## How the memory system works
Learner completes a Writing or Reading attempt

↓

Qwen evaluates the attempt against rubric criteria

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

### Memory lifecycle example
Attempt 1: "Learner writes essays without a clear thesis"

confidence: 0.65, evidence: 1
Attempt 2: Same weakness observed again

confidence: 0.80, evidence: 2
Attempt 3: Learner writes a strong thesis

confidence: 0.45, evidence: 3
Attempt 4: Consistent improvement confirmed

status: archived — skill considered mastered

---

## Database schema

| Table | Purpose |
|---|---|
| learners | Learner profiles and goals |
| practice_attempts | Every Writing and Reading attempt |
| learner_memories | Coaching memories per skill |
| mastery_scores | Current skill level per section |
| session_summaries | Session level summaries |

---

## Roadmap

- [x] Writing Coach with full memory cycle
- [x] Reading Coach with full memory cycle
- [ ] Speaking Coach with ASR and TTS
- [ ] Listening Coach
- [ ] Chat Coach (free conversation with AI tutor)
- [ ] Teacher / admin dashboard
- [ ] FastAPI backend upgrade
- [ ] PostgreSQL upgrade
- [ ] Cloud deployment