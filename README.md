# 🎯 IELTS MemoryCoach

An AI-powered IELTS writing coach with persistent memory.
Built with Streamlit, Qwen AI, SQLite and Docker.

---

## What it does

IELTS MemoryCoach is a local coaching app that remembers learners
across sessions. Unlike a simple essay grader, it tracks weaknesses,
monitors improvement and personalises feedback over time using a
MemoryAgent system.

**Core features:**
- Real IELTS writing prompts with difficulty levels
- AI-powered essay scoring using the official IELTS rubric
- Persistent memory that extracts coaching insights after each attempt
- Memory that strengthens, weakens and archives based on new evidence
- Progress dashboard showing score trends across attempts
- Memory dashboard showing everything the coach knows about the learner

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | Streamlit |
| AI / LLM | Qwen API (via OpenAI-compatible SDK) |
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
>>> DASHSCOPE_API_KEY=your_key_here

Get your free API key from: https://www.qwencloud.com/

### 3. Run with Docker

```bash
docker compose up --build
```

Open your browser at: **http://localhost:8501**

### 4. First time setup

1. Click **Profile** in the sidebar
2. Create your learner profile
3. Go to **Writing Coach** and submit your first essay
4. Check **Progress** and **Memory** dashboards after your attempt

---

## Project structure

IELTS-memorycoach/

├── app/
│   ├── main.py                  # Home page
│   ├── pages/                   # Streamlit pages
│   ├── services/                # Business logic
│   ├── prompts/                 # Qwen prompt templates
│   ├── data/                    # IELTS content (JSON)
│   ├── db/                      # Database layer
│   └── utils/                   # Helper utilities
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env                         # Not committed to Git

---

## How the memory system works

Attempt submitted
↓
Qwen scores the essay
↓
Memories extracted from feedback
↓
Existing memories compared with new evidence
↓
Memories strengthened / weakened / archived
↓
Next session coach uses memories as context
↓
Feedback becomes more personalised over time

---

## Roadmap

- [x] Writing Coach with memory
- [ ] Reading Coach
- [ ] Speaking Coach
- [ ] Listening Coach
- [ ] Teacher / admin dashboard
- [ ] FastAPI backend upgrade
- [ ] PostgreSQL upgrade
- [ ] Cloud deployment