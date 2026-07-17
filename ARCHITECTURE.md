# IELTS MemoryCoach — Architecture

## The Agent Loop

MemoryCoach implements a full **perceive → remember → reason → act**
agent loop that runs after every practice session.

```mermaid
graph LR
    A[PERCEIVE\nPractice attempt\nASR transcription\nImage extraction] -->
    B[REMEMBER\nCoach Agent gathers evidence\nClassifies skills via tools\nExtracts + updates memories]
    B --> C[REASON\nFind weakest skill\nBuild band-aware context\nCross-section insights]
    C --> D[ACT\nTutor Agent opens session\nCalls tools mid-conversation\nDrills targeted weakness]
    D --> A
```

---

## System Architecture

```mermaid
graph TD
    Browser["🌐 React Frontend\nVite + Tailwind CSS"] -->|JWT + REST + SSE| Nginx

    subgraph ECS ["Alibaba Cloud ECS — Singapore"]
        Nginx["Nginx\nPort 80\nSSE-aware proxy"] -->|/api/*| FastAPI
        Nginx -->|/*| Static["React Static Files\n/var/www/html"]
        FastAPI["FastAPI\nPort 8000\n2 uvicorn workers"] --> Services
        Services["Python Services\ncoach, tutor, scoring,\nmemory, tts, asr, vision"]
        Services --> SQLite["SQLite\nDocker Volume\nPersists across restarts"]
    end

    FastAPI -->|MCP protocol| MCP["MCP Server\n/mcp-server/mcp\n7 tools"]
    MCP --> SQLite

    Services -->|text + vision generation| ModelStudio["Alibaba Cloud\nModel Studio\nqwen-plus + qwen-turbo + qwen-vl-plus\nSingapore workspace"]
    Services -->|speech-to-text| ASR["DashScope ASR\nqwen3-asr-flash"]
    Services -->|text-to-speech| TTS["DashScope TTS\nqwen3-tts-flash\nCherry voice"]
    TTS -->|audio upload| OSS["Alibaba Cloud OSS\nielts-memorycoach-audio\nSingapore"]
    OSS -->|proxied stream| Browser
```

---

## Coach / Tutor Agent Architecture

MemoryCoach implements two distinct AI agents with a clean boundary:
the Coach writes learner data, the Tutor reads it.

```mermaid
graph TD
    subgraph COACH ["Coach Agent (app/services/coach_service.py)"]
        C1[get_skill_rank] -->|reads| DB
        C2[get_learner_memories] -->|reads| DB
        C3[get_recent_attempt] -->|reads| DB
        C4[submit_classification] -->|triggers| ENGINE
        C5[write_memory] -->|writes| DB
        C6[update_memory] -->|writes| DB
    end

    subgraph ENGINE ["Deterministic Rank Engine"]
        E1[clean_streak += 1\non strength]
        E2[clean_streak = 0\non weakness]
        E3[rank up when\nstreak >= 3]
    end

    subgraph TUTOR ["Tutor Agent (app/services/chat_coach_service.py)"]
        T1[get_coaching_context] -->|reads| DB
        T2[get_learner_weaknesses] -->|reads| DB
        T3[get_recent_attempts] -->|reads| DB
        T4[get_skill_ranks] -->|reads| DB
    end

    ENGINE --> DB[("SQLite\nlearner_skill_ranks\nlearner_memories")]

    note1["Coach WRITES — evaluates\npractice, classifies skills,\nextracts memories"]
    note2["Tutor READS — personalises\nteaching, runs drills,\nqueries live data mid-session"]
```

**Tool definitions** live in `app/services/agent_tools.py` as
OpenAI-compatible function schemas, executed by `execute_coach_tool()`
and `execute_tutor_tool()`. Qwen's function calling API decides when
to call each tool based on the conversation context.

---

## Memory Lifecycle

```mermaid
flowchart TD
    A[Practice attempt submitted] --> B[Coach Agent gathers evidence\nvia tool calls]
    B --> C[submit_classification tool\ntriggers deterministic engine]
    C --> D[write_memory tool\nsaves new observation]
    D --> E{Memory exists\nfor this skill?}

    E -->|No| F[INSERT new memory\nconfidence 0.5-0.7]
    E -->|Yes| G[update_memory tool]

    G -->|Confirms| H[STRENGTHEN\nconfidence += 0.05-0.15]
    G -->|Contradicts| I[WEAKEN\nconfidence -= 0.10-0.20]
    G -->|Mastery detected| J[ARCHIVE\nstatus = archived]

    F --> K[Memory active\nin coaching context]
    H --> K
    I --> L{confidence < 0.1?}
    L -->|Yes| M[RETIRE memory]
    L -->|No| K
    J --> N[Archived — shown\nin Memory Timeline]

    K --> O[Spaced repetition retrieval\nrecency × confidence weighted]
    O --> P[Tutor Agent reads via\nget_learner_weaknesses tool]
```

**Spaced repetition weighting:** `get_relevant_memories()` scores each
memory as `confidence × recency_weight` where recency decays from 1.0
(updated within 7 days) to 0.4 (older than 90 days). Recent evidence
outweighs stale evidence regardless of confidence level.

---

## Writing Submission — Coach Agent Pipeline

The old three-call chain (evaluate → classify → extract) is now
orchestrated by the Coach agent, which gathers evidence via tools
before making classification and memory decisions.

```mermaid
sequenceDiagram
    participant R as React
    participant F as FastAPI
    participant VL as qwen-vl-plus
    participant Q1 as qwen-plus
    participant CA as Coach Agent
    participant DB as SQLite

    Note over R,F: Option A — typed essay
    R->>F: POST /writing/submit/stream
    F->>Q1: SSE streaming evaluation
    Q1-->>R: tokens stream (first token ~1-2s)
    Q1-->>F: full response

    Note over R,F: Option B — handwritten image
    R->>F: POST /writing/submit/image (multipart)
    F->>VL: extract_text_from_image()
    VL-->>F: extracted essay text + confidence
    F->>Q1: evaluate_writing(extracted_text)
    Q1-->>F: scores + feedback

    F->>DB: save_attempt()
    F-->>R: result (+ extraction_confidence if image)

    Note over F,DB: BackgroundTask — Coach Agent
    F->>CA: coach_writing_submission()
    CA->>DB: get_learner_memories [tool]
    CA->>DB: get_recent_attempt [tool]
    CA->>DB: submit_classification [tool] → rank engine
    CA->>DB: write_memory [tool] × 1-3
```

---

## Adaptive Content Selection

All four sections select content matched to the learner's
current band level, avoiding content already seen.

```mermaid
flowchart TD
    A[Learner requests content] --> B[get_adaptive_difficulty\nlearner_id + section]
    B --> C[get_all_skill_ranks\nfor this section]
    C --> D{Any skills\nassessed?}
    D -->|No| E[Return 'intermediate'\ndefault]
    D -->|Yes| F[Calculate average band\nfrom assessed skills]
    F --> G{Band threshold}
    G -->|< 5.5| H[beginner]
    G -->|5.5 - 6.9| I[intermediate]
    G -->|>= 7.0| J[advanced]
    H --> K[_get_unseen_or_cycle\nfiltered by difficulty]
    I --> K
    J --> K
    K --> L{Unseen items\navailable?}
    L -->|Yes| M[Return random unseen item]
    L -->|No — all seen| N[Reset cycle\nReturn any item]
    M --> O[mark_content_seen\nlearner_seen_content table]
```

---

## Band Estimation System

IELTS band estimates (4.0–8.5) replace the internal 1-5 rank
for all learner-facing displays. The rank engine is unchanged —
bands are derived at read time from rank + streak.

```
Rank 1, streak 0 → Band 4.0   Rank 1, streak 1+ → Band 4.5
Rank 2, streak 0 → Band 5.0   Rank 2, streak 1+ → Band 5.5
Rank 3, streak 0 → Band 6.0   Rank 3, streak 1+ → Band 6.5
Rank 4, streak 0 → Band 7.0   Rank 4, streak 1+ → Band 7.5
Rank 5, streak 0 → Band 8.0   Rank 5, streak 1+ → Band 8.5

No band shown until total_evidence > 0 (first practice session)
A weakness resets streak to 0, dropping band back to base within
the rank — providing realistic downward movement without touching
the underlying rank engine.
```

Section band = average of all assessed skill bands for that section.
Overall band = average of all section bands with any evidence.

---

## Specialist Tutor State Machine

Each of the 4 specialist tutors follows the same state machine.
The Tutor is now a tool-calling agent — it can query live learner
data mid-conversation rather than relying solely on static context.

```mermaid
stateDiagram-v2
    [*] --> introduction : startChat(section)

    introduction --> explaining : Learner engages
    explaining --> explaining : Follow-up questions\n[Tutor may call get_learner_weaknesses]
    explaining --> drilling : Learner ready to practise

    drilling --> drilling : More drills needed\n[Tutor may call get_recent_attempts\nor get_skill_ranks mid-drill]
    drilling --> bridge_to_practice : Coach satisfied

    bridge_to_practice --> [*] : extract_chat_memories()\nMicro-memories saved to DB

    note right of introduction
        Tutor opens by calling
        get_coaching_context tool —
        live data, not stale session cache
    end note

    note right of bridge_to_practice
        Chat memories extracted and
        saved — closes the agent loop
        so tutoring feeds back into
        the Coach's evidence base
    end note
```

---

## Cross-Section Insights

```mermaid
flowchart TD
    A[GET /progress/insights] --> B[get_cross_section_insights\nlearner_id]
    B --> C[Collect weakness memories\nfrom all 4 sections]
    C --> D[Map skill labels to themes\ninference / vocabulary /\ngrammar / organization etc.]
    D --> E{Theme appears\nin 2+ sections?}
    E -->|Yes| F[Cross-section pattern\nseverity: high if 3+ sections]
    E -->|No| G[Section-specific — skip]
    F --> H[Generate targeted\nrecommendation per theme]
    H --> I[Surface in Dashboard\nand Chat Coach context]
```

---

## OSS Audio Architecture

Listening track audio is generated once globally and
proxied to the browser via FastAPI (direct redirect cannot
be used because browsers reject cross-origin redirects
when an Authorization header is present).

```mermaid
sequenceDiagram
    participant U1 as User A (first ever)
    participant F as FastAPI
    participant TTS as DashScope TTS
    participant OSS as Alibaba Cloud OSS
    participant U2 as User B (all future)

    U1->>F: GET /listening/audio/track_1 (with auth)
    F->>OSS: Check if track_1.wav exists
    OSS-->>F: 404 Not Found

    F->>TTS: Generate WAV via HTTP POST\n/api/v1/multimodal-generation
    TTS-->>F: audio bytes

    F->>OSS: PUT track_1.wav
    OSS-->>F: 200 OK

    F->>OSS: GET signed URL (1 hour expiry)
    OSS-->>F: signed URL
    F->>OSS: Proxy GET (fetch bytes)
    OSS-->>F: audio bytes
    F-->>U1: StreamingResponse (wav)

    Note over U2,OSS: All future requests — zero TTS cost

    U2->>F: GET /listening/audio/track_1 (with auth)
    F->>OSS: Check if track_1.wav exists
    OSS-->>F: 200 OK (exists)
    F->>OSS: GET signed URL + proxy bytes
    F-->>U2: StreamingResponse (instant)
```

TTS quota consumed **once per track** for all users for all time.
Currently 9 tracks = 9 TTS calls total regardless of user count.

---

## MCP Server

The memory layer is exposed as an MCP server — any
MCP-compatible agent can query learner coaching data.
The Tutor agent also calls these tools internally via
OpenAI function calling (not MCP protocol).

```mermaid
graph LR
    A["Tutor Agent\n(internal)"] -->|function calling| TOOLS
    B["External tutoring\nplatform"] -->|MCP protocol| MCP
    C["School dashboard\next. system"] -->|MCP protocol| MCP
    D["Research tool"] -->|MCP protocol| MCP

    TOOLS["agent_tools.py\nOpenAI function schemas"]
    MCP["MCP Server\n/mcp-server/mcp\nFastMCP 3.4.3"]

    TOOLS --> DB
    MCP --> DB[("SQLite\nlearner_memories\nlearner_skill_ranks\npractice_attempts\nlearner_seen_content")]
```

**Available tools:**
- `get_coaching_context` — full context bundle (primary tool for AI agents)
- `get_learner_weaknesses` — active weakness memories with confidence
- `get_learner_strengths` — active strength memories
- `get_skill_ranks` — all skill ranks with band estimates and streak data
- `get_weakest_skill_for_learner` — single weakest skill + rank definitions
- `get_recent_attempts` — attempt history with score summaries
- `get_learner_memory_stats` — memory profile statistics

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

learner_memories              ← The Coach Agent's core evidence store
  memory_id, learner_id, section, skill
  memory_type (weakness/strength)
  memory_text, confidence (0.0-1.0)
  evidence_count, status (active/archived)
  created_at, updated_at
  ← Retrieval weighted by recency × confidence (spaced repetition)

learner_skill_ranks           ← Deterministic rank engine store
  rank_id, learner_id, section, skill_id
  current_rank (1-5), clean_streak (0-2)
  total_evidence, last_classification
  created_at, updated_at
  ← Band (4.0-8.5) derived at read time from rank + streak

learner_seen_content          ← Adaptive content deduplication
  seen_id, learner_id, section
  content_id (passage_id / prompt_id / track_id)
  seen_at
  ← Ensures adaptive selection serves unseen content first;
    cycles back only when all items at current difficulty exhausted

mastery_scores
  Section-level score history

session_summaries
  Session-level summaries
```

---

## Key Design Decisions

### 1. Coach/Tutor separation
Two agents with a clean boundary: **Coach writes, Tutor reads**.
The Coach evaluates practice submissions, classifies skills via
`submit_classification`, and writes memories via `write_memory`.
The Tutor reads learner data via read-only tools and never writes
ranks or memories directly. This boundary is enforced by separate
tool schemas (`COACH_TOOL_SCHEMAS` vs `TUTOR_TOOL_SCHEMAS`).

### 2. Deterministic rank engine beneath the Coach agent
The Coach agent makes AI judgements (classify this skill as
strength/weakness), but rank changes are always decided by the
deterministic engine (3 consecutive strengths = rank up). The AI
judges the evidence; the engine enforces the rules. Rank changes
are fully auditable — inspect `learner_skill_ranks` to see exactly
why any rank moved.

### 3. Three separate Qwen calls per Writing submission
Isolation by design. Essay evaluation (qwen-plus), skill
classification (qwen-turbo), and memory extraction (qwen-plus)
are separate. Long feedback contains apostrophes that break JSON
parsing; short classification responses are reliable. One failure
cannot cascade.

### 4. Task-tiered model routing
```
qwen-plus     → complex reasoning (essay evaluation, memory
                 extraction, Coach agent, Tutor agent)
qwen-turbo    → structured output (skill classification,
                 JSON repair) — faster, cheaper, sufficient
qwen-vl-plus  → vision (handwritten essay image extraction)
```

### 5. OSS for audio
Listening track audio is generated once globally.
Every learner gets it proxied from Alibaba Cloud OSS instantly.
TTS quota consumed exactly once per track for all users for all time.

### 6. MCP as the memory API
The memory layer is infrastructure, not just an app feature.
Any MCP-compatible agent can query learner coaching history via
standard protocol. Internally, the Tutor agent uses the same
functions via OpenAI function calling rather than MCP protocol —
same data, two consumption patterns.

### 7. SSE streaming for essay feedback
The learner sees the first feedback token in ~1-2 seconds
instead of waiting 15-20 seconds. FastAPI StreamingResponse
with Nginx `proxy_buffering off` ensures tokens flow
through to the browser without buffering.

### 8. Adaptive content with seen-content deduplication
All four sections select content matched to the learner's average
band. `learner_seen_content` tracks which items have been served
so the same passage/prompt/track is never repeated until all
items at the current difficulty level have been exhausted.

### 9. Spaced repetition in memory retrieval
`get_relevant_memories()` weights memories by `confidence ×
recency_weight`. A memory updated last week outranks a
higher-confidence memory from three months ago — matching
the spaced repetition principle that recent evidence is more
predictive of current ability.
