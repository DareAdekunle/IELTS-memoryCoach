# CLAUDE.md — Agent Build Harness for BandUp IELTS

Read this BEFORE making any changes. It captures build patterns,
conventions, and hard-won fixes so they are not re-discovered.

For *what the product does*, read `README.md` first.
This file is about *how to keep building it correctly*.

---

## 1. Project status (update this section as you go)

What's next and what's left lives in [`PLAN.md`](PLAN.md) — update its
checkboxes as work lands. This section is the feature inventory.

```
RUNTIME
  ⬜ Hosting — the Alibaba Cloud ECS server was shut down (Oct 2026);
               the app runs locally only: docker compose up -d
  ✅ Model Studio (Qwen) + OSS — still live, used from local

ARCHITECTURE
  ✅ FastAPI backend          — api/ folder, all routes wired
  ✅ React frontend           — frontend/ folder, Vite + Tailwind
  ✅ Auth                     — JWT + Google OAuth + bcrypt passwords
  ✅ PostgreSQL 16 + Alembic  — scripts/migrate.py runs before the API
  ✅ Docker Compose           — dev (docker-compose.yml) + prod image with Nginx

IELTS MODULES
  ✅ Writing Coach            — streamed evaluation, Coach agent, image upload
  ✅ Reading Coach            — passages, questions, answer-key marking
  ✅ Speaking Coach           — 3-part session, ASR, Cherry TTS feedback
  ✅ Listening Coach          — question preview, cached TTS audio, answers
  ✅ IELTS Tutor              — 4 specialist tutors with pedagogy plans

SKILL MASTERY SYSTEM
  ✅ Taxonomy                 — Writing (13), Reading (10), Speaking (9),
                                Listening (8) — 40 sub-skills
  ✅ Ranking engine           — learner_skill_ranks, clean_streak
  ✅ Classification           — Coach agent submit_classification tool
  ✅ Context builder          — build_chat_coach_context() in memory_service

PEDAGOGICAL SKILL LAYER
  ✅ Framework registry       — 16 frameworks + 4-habit spine (app/pedagogy/)
  ✅ Band descriptors         — band_descriptors.json, all 4 sections
  ✅ Stage resolver           — per-criterion bands/stages, derived live
  ✅ Pedagogy Planner         — deterministic routing, all 4 sections
  ✅ Session plans + evidence — tutor_sessions/plans/events/hints tables
  ✅ Action tag protocol      — [ACTION: hint level=N] parsed server-side
  ✅ Coach interpretation     — coach_tutor_session() at bridge_to_practice
  ✅ Support fading rules     — earned reduction, one step, guarded tool
  ✅ Pedagogy API + UI        — /pedagogy/*, Tutor strip, Skill Mastery stages
  ⬜ Condition-gate UI        — Listening replay/transcript limits in React
  ⬜ Live tag-reliability eval — scripts/eval_pedagogy.py needs real sessions

DASHBOARDS
  ✅ Progress Dashboard       — per-section tabs + Skill Ranks tab
  ✅ Memory Dashboard         — active/archived memories with confidence

STUDY SCHEDULER + GOOGLE CALENDAR
  ✅ study_schedules table    — days/time/duration/timezone + Google tokens
  ✅ calendar_service.py      — OAuth (PKCE), create/delete recurring events
  ✅ /schedule/* API routes   — setup, get, cancel, calendar connect/disconnect
  ✅ Onboarding (2-step)      — profile step 1, study schedule step 2
  ✅ Study Plan page          — schedule, Google Calendar, chat-coach linking

CHAT COACHES
  ✅ Telegram + WhatsApp      — shared flow in app/services/bot_conversation.py
  ✅ Account linking          — one-time codes (/channels/*, Study Plan card)
  ✅ Webhook verification     — Telegram secret token, WhatsApp HMAC
  ⬜ Live again               — needs hosting (or a tunnel) + webhook secrets

QUALITY + OPERATIONS
  ✅ pytest suite             — docker exec ielts-api-dev pytest
  ✅ Cost model               — scripts/cost_model.py (live; a few cents per run)
  ✅ Writing calibration      — scripts/eval_writing.py + evaluation/writing/
                                (band_scoring_service = candidate, not in app yet)
  ✅ Security boundaries      — server-held tutor transcripts, tools bound to
                                the authenticated learner, MCP token-gated

UPCOMING (see README roadmap)
  ⬜ Assessment validity      — calibrate scores against human-rated samples
  ⬜ Memory 2.0               — evidence-linked, de-duplicated memories
  ⬜ Diagnostic + planning    — initial diagnostic, adaptive study plan
  ⬜ Durable agent workflows  — recoverable Coach/Tutor orchestration
  ⬜ Teacher / admin dashboard
```

---

## 2. Architecture overview

```
frontend/ (React, port 5173 in dev)
    ↓ axios HTTP calls (JWT)
api/ (FastAPI, port 8000)
    ↓ imports from
app/ (Python services, pedagogy, prompts, data)
    ↓ reads/writes
PostgreSQL 16 (Docker volume postgres_data; schema via Alembic)
    ↓ external calls
Qwen (Model Studio) + Alibaba Cloud OSS + Google Calendar
Telegram / WhatsApp webhooks → api/routes → app/services/bot_conversation.py
```

**The `app/` folder is backend-only.** It is never imported by React.
React only talks to `api/` via HTTP. `api/` calls `app/` services.

**Streamlit is removed.** `app/pages/` and `app/main.py` no longer exist.
If you see references to them, they are stale and should be deleted.

---

## 3. Adding a new feature — the pattern

### New API route

1. Create `api/routes/<name>.py` with an `APIRouter`
2. Import and register in `api/main.py`:
   ```python
   from api.routes.<name> import router as <name>_router
   app.include_router(<name>_router)
   ```
3. All routes use `Depends(get_current_user)` for auth
4. All routes check `current_user.learner_id` before calling services

### New React page

1. Create `src/pages/<Name>.jsx`
2. Create `src/api/<name>.js` with axios calls
3. Add import + route in `src/App.jsx`:
   ```jsx
   import <Name> from './pages/<Name>'
   <Route path="/<name>" element={<ProtectedShell><Name /></ProtectedShell>} />
   ```
4. Add to `navItems` in `src/components/AppShell.jsx`

### New IELTS module (full pattern)

```
Backend:
  api/routes/<section>.py          ← REST endpoints; on submit:
                                     save_<section>_attempt(), then a
                                     BackgroundTask running
                                     coach_<section>_submission()
  app/prompts/<section>_evaluator_prompt.txt
  app/prompts/<section>_tutor_prompt.txt
  app/data/<section> content + skill taxonomy (the Coach agent
    classifies against the taxonomy via format_skill_list_for_prompt)
  coach_service.py: coach_<section>_submission() → run_coach_agent()
  memory_service.py: save_<section>_attempt(), get_<section>_progress_data()

Frontend:
  src/api/<section>.js
  src/pages/<Section>Coach.jsx
  add tab to src/pages/ProgressDashboard.jsx
  add to AppShell navItems
```

---

## 4. Conventions — follow these exactly

### Auth pattern in every API route

```python
@router.get("/something")
async def my_route(current_user: User = Depends(get_current_user)):
    if not current_user.learner_id:
        raise HTTPException(status_code=400, detail="Please create a learner profile first")
    # ... rest of route
```

Never skip the `learner_id` check on routes that access learner data.

### Identity always comes from the server

- Web: the learner is `current_user.learner_id` from the JWT. Never accept a
  `learner_id`, system prompt or conversation history from the client.
- Agents: every tool executor overwrites `args["learner_id"]` with the
  authenticated learner before running a tool — never trust the model's value.
- Tutor chat: the system prompt and turns live in `tutor_session_transcripts`;
  the client sends only `session_id` + `message`, and `load_owned_session()`
  enforces ownership.
- Echo tool calls back to Qwen with `assistant_tool_message()` from
  `app/utils/tool_calls.py` — Qwen rejects the next request if an echoed
  `function.arguments` is not valid JSON.

### React protected pages

All coaching pages use `ProtectedShell` in App.jsx:
```jsx
<Route path="/writing" element={
  <ProtectedShell><WritingCoach /></ProtectedShell>
} />
```

`ProtectedShell` = `ProtectedRoute` (JWT check) wrapping `AppShell`
(sidebar layout). Onboarding uses `ProtectedRoute` alone (no sidebar).

### JWT token flow

```
Login/Register → FastAPI returns access_token
→ React stores in localStorage('token')
→ axios interceptor attaches to every request header
→ FastAPI dependency get_current_user() validates and returns User
→ 401 response → axios interceptor clears token + redirects to /login
```

Never store sensitive data in localStorage beyond the JWT token.
Never bypass `get_current_user` for protected routes.

### Marking rules

- **Reading/Listening are marked by answer key only** (`app/services/answer_matching.py`):
  exact match after normalisation, IELTS word limits, no partial matching, no
  model. Gap questions need `word_limit` and answers that fit it; Reading
  answers must appear in the passage — `tests/test_answer_keys.py` enforces this.
- **Never send answer keys to the browser.** GET passage/track routes return
  `public_passage()` / `public_track()` (no `answer`, `acceptable_answers`,
  `explanation`, or listening `script`).
- **Every scorer stamps `assessment_version`** on its result
  (`app/services/assessment_versions.py`); save functions store it on
  `practice_attempts`. A new scorer must do the same.
- Writing and Speaking scores are AI estimates — label them as such in the UI
  (`EstimateNote`).

### Qwen calls — which client for which job

```
Text generation    → OpenAI SDK, compatible-mode endpoint
                     base_url: dashscope-intl.aliyuncs.com/compatible-mode/v1
                     models: qwen-plus (main), qwen-turbo (JSON repair),
                             qwen3-vl-plus (handwriting; https URLs only;
                             override with VL_MODEL env)

ASR (speech→text)  → asr_service.py → HTTP POST to the workspace
                     multimodal-generation endpoint, base64 audio data URI
                     model: qwen3-asr-flash

TTS (text→speech)  → tts_service.py → HTTP POST to the same endpoint
                     model: qwen3-tts-flash (override with TTS_MODEL env)
                     voice: Cherry; returns an audio URL, not bytes

Embeddings         → embedding_service.py → dashscope.TextEmbedding
                     model: text-embedding-v3 (1024-d)
```

Do NOT use the OpenAI SDK for ASR/TTS — it returns 404.

### TTS model selection

Use `qwen3-tts-flash`. Dated snapshots get retired — as of Oct 2026
`qwen3-tts-flash-2025-11-27` returns 404 "Model not exist". Beyond the
free quota it is billed at $0.10 per 10k characters. To switch models,
set `TTS_MODEL` in `.env`; the API call structure is identical.

### JSON parsing from Qwen

Always use `safe_parse_json()` from `app/utils/json_utils.py`.
Never call `json.loads()` directly on raw Qwen responses (tool-call
arguments: use `parse_tool_args()` from `app/utils/tool_calls.py`).
If `safe_parse_json` fails → `fix_broken_json()` asks Qwen to repair.
Long feedback contains apostrophes that break JSON — which is why
evaluation and skill classification never share one response.

### React JSX — oxc parser rules

Vite uses the oxc parser which is stricter than Babel.
Never write multiline expressions inside JSX attributes:

```jsx
// WRONG — breaks oxc parser
<button disabled={
  Object.keys(responses).length <
  prompt.questions.length
}>

// RIGHT — pre-compute as a variable
const isDone = Object.keys(responses).length === prompt.questions.length
<button disabled={!isDone}>
```

Always pre-compute complex boolean conditions outside JSX.
Use string concatenation instead of template literals in className:
```jsx
// SAFER
className={'base-class ' + (condition ? 'active' : 'inactive')}
```

### Database — PostgreSQL + Alembic

PostgreSQL runs as a separate Docker service (`postgres:16-alpine`).
Data persists on the `postgres_data` named volume across container rebuilds.
Connection string: `postgresql://ielts:<POSTGRES_PASSWORD>@postgres:5432/ielts_coach`
(`app/db/database.py` pins the psycopg2 driver — SQLAlchemy 2.1+ defaults
to psycopg v3, which is not installed).

SQLite still works for local-only development — set `DATABASE_URL` to a
`sqlite:///...` path and `connect_args` are set automatically.

**Schema changes go through Alembic** (`migrations/`). Never call
`Base.metadata.create_all` from app code. To change the schema:
1. Edit the model in `app/db/models.py` (or `api/auth/models.py`)
2. `docker exec ielts-api-dev alembic revision --autogenerate -m "describe change"`
3. Review the generated file in `migrations/versions/`, then
   `docker restart ielts-api-dev` — `scripts/migrate.py` runs
   `alembic upgrade head` before uvicorn starts (uvicorn's auto-reload does not).

To migrate existing SQLite data to Postgres:
  `python scripts/migrate_sqlite_to_postgres.py --sqlite ./ielts_coach.db --postgres <url>`

The `learner_skill_ranks` table is separate from `learner_memories`.
Do not confuse them — they serve different purposes:
- `learner_memories`: free-text, confidence-weighted, section-level, with embeddings
- `learner_skill_ranks`: fixed taxonomy, deterministic, skill-level

---

## 5. Skill Mastery System

### Submission pipeline (all sections)

```
1. Evaluate      → scores + feedback (Writing streams it via SSE)
2. Save attempt  → practice_attempts — the learner's result is now safe
3. Coach agent   → BackgroundTask: coach_<section>_submission()
                   → run_coach_agent(): reads evidence via tools,
                     submit_classification (rank engine), write/update memory
```

Keep evaluation and classification in separate model calls, and keep the
Coach agent in the background — a coaching failure must never lose a score.

### Rank-up rule (never change without discussion)

```
"demonstrated_strength"  → clean_streak += 1
"demonstrated_weakness"  → clean_streak = 0  (FULL RESET, not decrement)
"not_applicable"         → no change, record not touched

clean_streak reaches 3 → current_rank += 1 (max 5), streak resets to 0
Rank NEVER decreases automatically.
```

These rules are pinned by `tests/test_rank_rules.py`.

### Tutor state machine

States: `introduction` → `explaining` → `drilling` → `bridge_to_practice`

Qwen emits `[STATE: xxx]` at end of every reply.
`parse_state_tag()` in `chat_coach_service.py` strips it before display.
Default if tag missing or invalid: `"explaining"` (safe middle state).

### Pedagogical Skill Layer (never violate these)

1. **Python selects the teaching method; Qwen delivers it.** The model
   never controls stage transitions, framework eligibility, hint
   escalation order, condition gates, or support-level changes.
2. **Bands/stages are DERIVED, never stored.** `stage_resolver.py`
   aggregates `learner_skill_ranks` per criterion live. Only
   pedagogy-only state (support level, counters) lives in
   `learner_criterion_state`. Do not add a stored stage column.
3. **The Tutor records what happened; the Coach decides what it
   means.** Tutor writes only events (via [ACTION:] tags parsed
   server-side). Coach alone calls `update_criterion_state`, which is
   guarded by `fading.evaluate_support_change` — unearned support
   reductions are vetoed, changes are one step at a time.
4. **[ACTION:] tags** are best-effort evidence — a missed tag loses a
   data point, never breaks the chat. Never make tag parsing a hard
   gate on the conversation.
5. **Spine validation is SOFT** — one regeneration retry, then
   log-only. Never reject Tutor replies outright.
6. **No classifications from tutoring.** `submit_classification` is
   blocked inside `coach_tutor_session` — skill ranks move only from
   practice submissions.

Tutor sessions are cached in the browser's sessionStorage under a key that
includes the user id (`chat_session_<userId>_<section>`), so switching
accounts never shows another user's session. A 404 from `/chat/continue`
clears the stale cache.

---

## 6. Known gotchas

1. **`requirements.txt` must be hand-maintained**, never `pip freeze`
   in a Conda env — it captures local Conda paths Docker can't find.
   Test-only packages go in `requirements-dev.txt` (installed in the dev
   image via the `INSTALL_DEV` build arg).

2. **ASR/TTS 401 or 404 errors** usually mean the wrong endpoint or SDK
   class, not a wrong key. Both use HTTP POST to the workspace
   multimodal-generation endpoint (see §4).

3. **TTS returns a URL, not bytes.** `output.audio.url` → download → store.
   A 404 "Model not exist" means the configured TTS snapshot was retired.

4. **Audio recorder dedup** — the recorder can return the same bytes on
   re-render. Hash audio bytes (md5) and skip if already processed.
   Pattern in `SpeakingCoach.jsx` `handleAudioBlob`.

5. **ASR file size limit ~10MB.** Compress via pydub (mono 16kHz 16-bit)
   in `asr_service.compress_audio()` before sending. ffmpeg required in
   Docker image.

6. **oxc parser is strict.** Multiline JSX attribute expressions cause
   parse errors. Pre-compute all conditions as variables before JSX.

7. **Google OAuth test mode** — only emails listed as test users in
   Google Cloud Console can sign in while the app is in testing mode.
   Locally, `http://localhost:8000/auth/google/callback` and
   `http://localhost:8000/schedule/calendar/callback` must be authorised
   redirect URIs.

8. **learner_id vs user_id** — these are different things.
   `user_id` is the auth identity (users table).
   `learner_id` is the coaching profile (learners table).
   They are linked by `users.learner_id`.
   Users created before onboarding have `learner_id = null` —
   they must complete onboarding before using coaching features.

9. **Tutor opens with no history** for users who haven't practised yet.
   The welcome path (`has_history: False`) directs them to a Coach first.
   This is correct behaviour.

10. **The dev compose file must bypass `docker-entrypoint.sh`.** That
    script starts Nginx with the production TLS config, which fails
    locally with a missing Let's Encrypt certificate. `docker-compose.yml`
    sets `entrypoint: []` and runs `migrate.py` + uvicorn directly.

11. **Chat coaches link only by one-time code.** Never link a chat by
    email. Webhooks fail closed: Telegram needs `TELEGRAM_WEBHOOK_SECRET`
    (pass it as `secret_token` to setWebhook), WhatsApp needs
    `WHATSAPP_APP_SECRET`. Both channels share
    `app/services/bot_conversation.py` — change behaviour there, not in one
    route. Register the Telegram webhook with:
    `curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook?url=<public-url>/telegram/webhook&secret_token=$TELEGRAM_WEBHOOK_SECRET"`
    (`<public-url>` is `/api`-prefixed behind Nginx). Locally, the bots need
    a tunnel (e.g. ngrok) to receive messages.

12. **`/mcp-server` is admin-only.** Requests need
    `Authorization: Bearer $MCP_API_TOKEN`; if the env var is unset,
    every request gets 401. Its tools accept any `learner_id`, so never
    expose it without the token.

---

## 7. Definition of done for any new feature

Tests: `docker exec ielts-api-dev pytest` (throwaway SQLite DB; live Qwen
calls are blocked — mock with `FakeLLM` from `tests/conftest.py`).
`scripts/manual_checks/` holds scripts that hit the LIVE Qwen API — run by
hand only.

- [ ] `pytest` passes; new rules/permissions have a test in `tests/`
- [ ] Schema changes have an Alembic revision
- [ ] API route tested in `/docs` Swagger UI with real JWT
- [ ] React page loads without console errors
- [ ] Auth check present — route returns 400 if no learner_id
- [ ] Attempt saves to `practice_attempts`
- [ ] Memories saved with the correct `section` value
- [ ] Memory panel shows memories from previous attempt on second run
- [ ] Progress Dashboard has a tab for this module
- [ ] Memory Dashboard shows this module's memories automatically
- [ ] Docker rebuild runs clean (`docker compose up -d --build`)
- [ ] README.md updated
- [ ] CLAUDE.md §1 checklist updated

---

## 8. Starting a new session on this project

1. Read `README.md` — product scope and current features
2. Read this file — conventions and gotchas
   Then `PLAN.md` — the current sprint and what's left
3. Check §1 status checklist against actual file tree
4. Start the stack: `docker compose up -d`; seed a demo learner with
   `docker exec ielts-api-dev python seed_demo.py` if the DB is empty
5. **Do not re-add Streamlit** — `app/pages/` and `app/main.py`
   are intentionally deleted. The app is React + FastAPI only.
6. For new API routes: follow §4 auth + identity patterns exactly
7. For new React pages: follow §4 ProtectedShell pattern
8. For JSX: pre-compute all complex conditions as variables (§6 gotcha 6)
9. Update §1 and README when a phase completes
