# IELTS MemoryCoach — Architecture

## Overview

IELTS MemoryCoach is a full-stack AI coaching web application built on
Alibaba Cloud infrastructure. It combines persistent learner memory,
deterministic skill ranking, and specialist AI tutors to deliver
personalised IELTS coaching across all four exam sections.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        ALIBABA CLOUD                            │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    ECS Instance                          │   │
│  │                                                          │   │
│  │  ┌─────────────┐    ┌──────────────────────────────┐     │   │
│  │  │    Nginx    │    │        FastAPI Backend       │     │   │
│  │  │  Port 80    │───▶│         Port 8000            │     │   │
│  │  │             │    │                              │     │   │
│  │  │  /* →       │    │  /auth    /writing /reading  │     │   │
│  │  │  React      │    │  /speaking /listening /chat  │     │   │
│  │  │  static     │    │  /progress /memory /skills   │     │   │
│  │  │             │    │  /mcp-server (MCP endpoint)  │     │   │
│  │  └─────────────┘    └──────────────┬───────────────┘     │   │
│  │                                    │                     │   │
│  │                     ┌──────────────▼───────────────┐     │   │
│  │                     │      Python Services         │     │   │
│  │                     │  scoring, memory, taxonomy,  │     │   │
│  │                     │  chat_coach, tts, asr, mcp   │     │   │
│  │                     └──────────────┬───────────────┘     │   │
│  │                                    │                     │   │
│  │                     ┌──────────────▼───────────────┐     │   │
│  │                     │   SQLite (Docker volume)     │     │   │
│  │                     │   Persists across restarts   │     │   │
│  │                     └──────────────────────────────┘     │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌───────────────────────────┐  ┌──────────────────────────┐    │
│  │   Model Studio            │  │   OSS (Audio Cache)      │    │
│  │   Singapore workspace     │  │   TTS audio files        │    │
│  │   qwen-plus (essays)      │  │   Listening tracks       │    │
│  │   qwen-turbo (classify)   │  └──────────────────────────┘    │
│  └───────────────────────────┘                                  │
│                                                                 │
│  ┌───────────────────────────┐                                  │
│  │   DashScope API           │                                  │
│  │   qwen3-asr-flash (ASR)   │                                  │
│  │   qwen3-tts-flash (TTS)   │                                  │
│  └───────────────────────────┘                                  │
└─────────────────────────────────────────────────────────────────┘

Browser (React + Vite + Tailwind)
  ↕ HTTPS / HTTP (axios + JWT)
Nginx reverse proxy
  /api/* → FastAPI port 8000
  /*     → React static files
```

---

## Request Flow

### Essay Submission (Writing Coach)

```
React (WritingCoach.jsx)
  │  POST /writing/submit { prompt, essay, task_type }
  │  Authorization: Bearer <JWT>
  ▼
FastAPI (api/routes/writing.py)
  │  1. Validate JWT → get User → get learner_id
  │  2. Fetch active memories for context
  ▼
Call 1: evaluate_writing() — qwen-plus
  │  System prompt: writing_evaluator_prompt.txt
  │  Context: {prompt} + {essay} + {memories}
  │  Returns: scores (5 criteria) + feedback + strengths/weaknesses
  ▼
save_attempt() → practice_attempts table
  ▼
Response returned to React immediately (< 3s)
  ▼
BackgroundTasks (run after response):
  │
  ├── Call 2: classify_writing_skills() — qwen-turbo
  │     Fixed-list prompt → 13 skill_ids × 3-way classification
  │     → apply_skill_classifications_batch()
  │     → learner_skill_ranks table updated
  │
  └── Call 3: extract_and_save_memories() — qwen-plus
        Memory extractor prompt → free-text observations
        → update_memories() → learner_memories table
```

### Chat Coach Session

```
React (ChatCoach.jsx)
  │  GET /chat/start?section=Writing
  ▼
FastAPI (api/routes/chat.py)
  │  build_chat_coach_context(learner_id, section)
  │    ├── get_weakest_skill() from learner_skill_ranks
  │    ├── find_evidence_memory_for_skill() from learner_memories
  │    └── find_recent_essay_excerpt() from practice_attempts
  │
  │  load specialist tutor prompt (writing_tutor_prompt.txt)
  │  inject context_brief into system prompt
  ▼
call_qwen(opening_instruction, system_message=specialist_prompt)
  │  Returns opening message with [STATE: introduction] tag
  │  parse_state_tag() strips tag, returns (message, state)
  ▼
React renders message, caches session in sessionStorage
  │
  │  [subsequent turns]
  │  POST /chat/continue { system_prompt, history, message }
  ▼
client.chat.completions.create(full_messages_with_history)
  │  Returns reply with [STATE: xxx] tag
  ▼
React updates chat, updates sessionStorage cache
```

---

## Memory System

The MemoryAgent is the core innovation. It maintains a persistent,
evolving model of each learner across all sessions.

```
MEMORY LIFECYCLE
────────────────

After each practice attempt:

1. EXTRACT
   Qwen reads the attempt result and generates free-text
   observations per skill:
   e.g. "Learner demonstrates clear thesis but fails to
         maintain position in body paragraphs"

2. COMPARE
   New observation compared against existing memories
   for the same learner + section + skill

3. UPDATE (one of four outcomes):
   STRENGTHEN  → confidence += 0.05 to 0.15
                 (new evidence confirms existing pattern)
   WEAKEN      → confidence -= 0.10 to 0.20
                 (new evidence contradicts existing pattern)
   ARCHIVE     → status = "archived"
                 (mastery detected — weakness overcome)
   NEW         → insert new memory record
                 (first time this pattern observed)

4. PERSIST
   learner_memories table — survives sessions, logins,
   device changes. Every coaching interaction reads
   active memories as context before generating feedback.
```

---

## Skill Mastery System

A deterministic rank engine layered on top of the memory system.
All ranking decisions are made by code, not by AI.

```
TAXONOMY (per section)
──────────────────────
Writing   — 13 sub-skills across 4 IELTS criteria
Reading   — 10 sub-skills across 4 reading skill areas
Speaking  — 10 sub-skills across 4 IELTS speaking criteria
Listening — 10 sub-skills across 4 listening skill areas

Each skill has 5 rank levels with definitions grounded in
the official IELTS Band Descriptors.

RANK ENGINE (deterministic)
────────────────────────────

After each essay, a separate qwen-turbo call classifies
every skill_id using a fixed-list prompt:

  Input:  essay text + fixed list of skill_ids
  Output: { skill_id: "demonstrated_strength" |
                      "demonstrated_weakness"  |
                      "not_applicable" }

Rule engine (no AI involved):
  "demonstrated_strength"  → clean_streak += 1
  "demonstrated_weakness"  → clean_streak = 0  (full reset)
  "not_applicable"         → no change

  clean_streak reaches 3   → current_rank += 1
                             clean_streak = 0
                             (rank capped at 5, never decreases)

This means rank changes are fully auditable — inspect
learner_skill_ranks to see exactly why any rank moved.

WHY TWO SEPARATE QWEN CALLS?
─────────────────────────────
Essay evaluation (qwen-plus) produces long, conversational
feedback that frequently contains apostrophes in example
text. These break JSON parsing. By keeping classification
(qwen-turbo) as a short, strictly structured call, one
call can fail gracefully without affecting the other.
```

---

## MCP Server

The MemoryCoach memory layer is exposed as an MCP
(Model Context Protocol) server at `/mcp-server/mcp`.

Any MCP-compatible AI agent can query learner coaching
data without direct database access.

```
Available tools:
  get_learner_weaknesses(learner_id, section, limit)
    → Active weakness memories with confidence scores

  get_learner_strengths(learner_id, section, limit)
    → Active strength memories with confidence scores

  get_skill_ranks(learner_id, section)
    → All skill ranks with streak data and rank definitions

  get_weakest_skill_for_learner(learner_id, section)
    → Single weakest skill with current/next rank definitions
      and sessions_to_rank_up count

  get_recent_attempts(learner_id, section, limit)
    → Recent attempt history with score summaries

  get_learner_memory_stats(learner_id)
    → Statistical summary of the learner's memory profile

  get_coaching_context(learner_id, section)
    → Complete context bundle — weaknesses + strengths +
      skill ranks + weakest skill + memory stats.
      Primary tool for AI tutoring agents.

Use cases:
  - School dashboard querying student progress
  - External AI tutor consuming learner history
  - Analytics pipeline processing learning patterns
  - The MemoryCoach Chat Coach itself uses this context
    internally to open personalised sessions
```

---

## Specialist AI Tutors

Four specialist tutors, each with section-specific knowledge:

```
┌─────────────────┬────────────────────────────────────────────┐
│ Tutor           │ Specialist Knowledge                        │
├─────────────────┼────────────────────────────────────────────┤
│ Writing Tutor   │ IELTS Band Descriptors, task types,         │
│                 │ thesis structure, cohesion, register        │
├─────────────────┼────────────────────────────────────────────┤
│ Reading Tutor   │ T/F/NG strategy, skimming, scanning,        │
│                 │ paraphrase recognition, question types      │
├─────────────────┼────────────────────────────────────────────┤
│ Speaking Tutor  │ Part 1/2/3 strategies, OREO structure,      │
│                 │ discourse markers, circumlocution           │
├─────────────────┼────────────────────────────────────────────┤
│ Listening Tutor │ Prediction, distractor resistance,          │
│                 │ form completion, note-taking strategies     │
└─────────────────┴────────────────────────────────────────────┘

Each tutor session:
  1. Calls get_coaching_context() for the learner + section
  2. Injects context into specialist system prompt
  3. Opens with personalised message citing real evidence
  4. Follows state machine: introduction → explaining →
     drilling → bridge_to_practice
  5. Emits hidden [STATE: xxx] tags for UI state tracking
  6. Session cached in sessionStorage — no redundant API calls
     on navigation away and back
```

---

## Authentication

```
Two methods supported:
  1. Username + password (bcrypt, 72-byte truncation)
  2. Google OAuth 2.0 (Authlib, Singapore-region redirect)

JWT tokens:
  - 7-day expiry (stay logged in across sessions)
  - Stored in localStorage
  - Attached via axios interceptor to every request
  - 401 response → auto-clear token + redirect to /login

User ↔ Learner separation:
  users table      → authentication identity
  learners table   → coaching profile
  users.learner_id → foreign key linking them
  Reason: OAuth users may not have a learner profile yet
  (onboarding creates the learner profile post-login)
```

---

## Task-Tiered Model Routing

```
qwen-plus  (via Alibaba Cloud Model Studio, Singapore)
  Used for:
  - Essay evaluation (complex reasoning, rich feedback)
  - Memory extraction (nuanced pattern recognition)
  - Chat coaching (multi-turn conversation)
  - Speaking evaluation (examiner-grade assessment)

qwen-turbo (via Alibaba Cloud Model Studio, Singapore)
  Used for:
  - Skill classification (constrained 3-way output)
  - JSON repair (self-healing fallback)
  Reason: faster, cheaper, sufficient for structured output

DashScope SDK (separate from Model Studio)
  Used for:
  - ASR: qwen3-asr-flash (speech-to-text)
  - TTS: qwen3-tts-flash-2025-11-27 Cherry voice
  Reason: ASR/TTS not available via OpenAI-compatible endpoint
```

---

## Database Schema

```
users
  user_id, email, username, password_hash
  google_id, auth_provider, learner_id
  is_active, created_at, last_login

learners
  learner_id, name, target_score
  test_date, current_focus

practice_attempts
  attempt_id, learner_id, section, task_type
  prompt, learner_response, score_json
  feedback, created_at

learner_memories
  memory_id, learner_id, section, skill
  memory_type (weakness/strength)
  memory_text, confidence (0.0-1.0)
  evidence_count, status (active/archived)
  created_at, updated_at

learner_skill_ranks
  rank_id, learner_id, section, skill_id
  current_rank (1-5), clean_streak (0-2)
  total_evidence, last_classification
  created_at, updated_at

mastery_scores
  section-level score history

session_summaries
  session-level summaries
```

---

## Key Design Decisions

### 1. No agent framework
LangChain, LlamaIndex and similar frameworks were evaluated
and rejected. All orchestration is hand-rolled Python.
Rationale: every pipeline in this app is a fixed, known
sequence — there is no dynamic tool selection or
multi-agent routing. A framework would add abstraction
cost (debugging, version coupling, breaking changes)
without removing any actual complexity.

### 2. Deterministic rank engine
Skill rank changes are never decided by AI. The AI
classifies (strength/weakness/not_applicable); Python
code counts and applies the rules. This means rank
changes are auditable, reproducible and tamper-proof.

### 3. Background tasks for memory
Memory extraction and skill classification run as FastAPI
BackgroundTasks — after the response is sent. The learner
sees feedback in ~3 seconds; the memory system updates
in the background over the next 10-20 seconds. This
separation means memory failures never block feedback.

### 4. Session caching for Chat Coach
Chat sessions are cached in sessionStorage keyed by
section. Navigating away and back restores the
conversation instantly without a new Qwen API call.
sessionStorage clears on tab close — intentional, so
stale conversations don't persist across days.

### 5. Three separate Qwen calls per Writing submission
Essay evaluation (qwen-plus), skill classification
(qwen-turbo), and memory extraction (qwen-plus) are
separate calls by design. Long essay feedback contains
apostrophes that break JSON parsing. Short classification
responses are reliable. Keeping them separate means
one failure cannot cascade to the others.
