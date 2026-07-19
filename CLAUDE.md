# CLAUDE.md — Agent Build Harness for Qonda IELTS

Read this BEFORE making any changes. It captures build patterns,
conventions, and hard-won fixes so they are not re-discovered.

For *what the product does*, read `README.md` first.
This file is about *how to keep building it correctly*.

---

## 1. Project status (update this section as you go)

```
ARCHITECTURE
  ✅ FastAPI backend          — api/ folder, all routes wired
  ✅ React frontend           — frontend/ folder, Vite + Tailwind
  ✅ Auth                     — JWT + Google OAuth + bcrypt passwords
  ✅ Docker Compose           — needs nginx.conf for production build

IELTS MODULES (all complete)
  ✅ Writing Coach            — essay, AI scoring, skill classification
  ✅ Reading Coach            — passage, questions, short answer eval
  ✅ Speaking Coach           — 3-part session, ASR, Cherry TTS
  ✅ Listening Coach          — question preview, TTS audio, answers
  ✅ Chat Coach               — memory-grounded conversational tutor

SKILL MASTERY SYSTEM
  ✅ Taxonomy                 — all 4 sections: Writing (13), Reading (10),
                                Speaking (9), Listening (8) — 40 sub-skills total
  ✅ Ranking engine           — learner_skill_ranks table, clean_streak
  ✅ Classifier               — skill_classifier_service.py
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
  ✅ Progress Dashboard       — Writing, Reading tabs + Skill Ranks tab
  ✅ Memory Dashboard         — active/archived memories with confidence

STUDY SCHEDULER + GOOGLE CALENDAR
  ✅ study_schedules table    — days/time/duration/timezone + Google tokens
  ✅ calendar_service.py      — OAuth flow, create/delete recurring events
  ✅ schedule_service.py      — schedule CRUD, weakest-skill event description
  ✅ /schedule/* API routes   — setup, get, cancel, calendar connect/disconnect
  ✅ Onboarding (2-step)      — profile step 1, study schedule step 2
  ✅ Study Plan page          — /study-plan, view/edit schedule + Google connect
  ✅ MCP scheduling tools     — schedule_study_sessions, get_study_schedule,
                                add_one_off_session, cancel_study_schedule

DEPLOYMENT
  ✅ Nginx config             — nginx.conf, SSE-aware proxy
  ✅ Production Dockerfile    — multi-stage React build + Python + Nginx
  ✅ Alibaba Cloud ECS        — deployed at ielts.qonda.xyz
  ✅ HTTPS / domain           — Let's Encrypt, docker-compose.prod.yml
  ✅ Google OAuth             — button on Login + Register pages, callback handler
  ✅ Data persistence         — PostgreSQL in Docker (postgres_data volume)
  ✅ OSS DB backup            — scripts/db_backup.py (SQLite fallback legacy)
  ✅ SQLite → PostgreSQL      — scripts/migrate_sqlite_to_postgres.py

DOCS
  ✅ README.md                — current features, roadmap, architecture
  ✅ ARCHITECTURE.md          — system diagrams, DB schema, agent loops
  ✅ docs/pedagogy_framework.md — full pedagogical design + code map

UPCOMING
  ⬜ Listening replay/transcript condition gates in frontend UI
  ⬜ Extend taxonomy to Reading, Speaking, Listening
  ⬜ Teacher / admin dashboard
  ⬜ Production: add GOOGLE_CALENDAR_REDIRECT_URI to .env on ECS server
  ⬜ Google Cloud Console: add production callback URI to OAuth app
```

---

## 2. Architecture overview

```
frontend/ (React, port 5173 in dev)
    ↓ axios HTTP calls
api/ (FastAPI, port 8000)
    ↓ imports from
app/ (Python services — unchanged from Streamlit era)
    ↓ reads/writes
SQLite (ielts_coach.db via Docker volume)
    ↓ external calls
Qwen API (text via OpenAI SDK, ASR/TTS via DashScope SDK)
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
  api/routes/<section>.py          ← REST endpoints
  app/prompts/<section>_evaluator_prompt.txt
  app/prompts/<section>_memory_extractor.txt
  add to memory_service.py:
    extract_<section>_memories()
    save_<section>_attempt()
    get_<section>_progress_data()

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

### Qwen calls — three separate SDKs, never mix them

```
Text generation    → qwen_service.py → OpenAI SDK
                     base_url: dashscope-intl.aliyuncs.com/compatible-mode/v1
                     model: qwen-plus

ASR (speech→text)  → asr_service.py → dashscope SDK
                     dashscope.MultiModalConversation.call()
                     model: qwen3-asr-flash

TTS (text→speech)  → tts_service.py → dashscope SDK
                     dashscope.audio.qwen_tts.SpeechSynthesizer.call()
                     model: qwen3-tts-flash-2025-11-27
                     voice: Cherry
```

Do NOT use the OpenAI SDK for ASR/TTS — it returns 404.
Do NOT use the dashscope SDK for text generation.

### TTS model selection

`qwen3-tts-flash` has limited free quota (nearly exhausted).
Use `qwen3-tts-flash-2025-11-27` which has 100% free quota remaining.
If that runs out, check dashboard for other `qwen3-tts-*` variants
with remaining quota. The API call structure is identical — just
change `TTS_MODEL` in `tts_service.py`.

### JSON parsing from Qwen

Always use `safe_parse_json()` from `app/utils/json_utils.py`.
Never call `json.loads()` directly on raw Qwen responses.
If `safe_parse_json` fails → `fix_broken_json()` asks Qwen to repair.
Long feedback (5/5 essays) contains apostrophes that break JSON —
this is why skill classification is a SEPARATE Qwen call from scoring.

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

### Database — PostgreSQL + Docker volume

PostgreSQL runs as a separate Docker service (`postgres:16-alpine`).
Data persists on the `postgres_data` named volume across container rebuilds.
Connection string: `postgresql://ielts:<POSTGRES_PASSWORD>@postgres:5432/ielts_coach`

SQLite is still supported for local-only development — set `DATABASE_URL` to a
`sqlite:///...` path and the `connect_args` are set automatically in `database.py`.

To migrate existing SQLite data to Postgres:
  `python scripts/migrate_sqlite_to_postgres.py --sqlite ./ielts_coach.db --postgres <url>`

The `learner_skill_ranks` table is separate from `learner_memories`.
Do not confuse them — they serve different purposes:
- `learner_memories`: free-text, confidence-weighted, section-level, now with embeddings
- `learner_skill_ranks`: fixed taxonomy, deterministic, skill-level

---

## 5. Skill Mastery System

### Three Qwen calls per Writing submission (never merge)

```
Call 1: evaluate_writing()          → rubric scores + feedback + memories
Call 2: classify_writing_skills()   → 13-skill fixed-list classification
Call 3: extract_and_save_memories() → free-text memory extraction
```

### Rank-up rule (never change without discussion)

```
"demonstrated_strength"  → clean_streak += 1
"demonstrated_weakness"  → clean_streak = 0  (FULL RESET, not decrement)
"not_applicable"         → no change, record not touched

clean_streak reaches 3 → current_rank += 1 (max 5), streak resets to 0
Rank NEVER decreases automatically.
```

### Chat Coach state machine

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

Profile-switch detection: `chat_learner_id` in React localStorage.
If user changes account, chat session resets automatically.
This is handled in `src/pages/ChatCoach.jsx` — don't remove it.

---

## 6. Known gotchas

1. **`requirements.txt` must be hand-maintained**, never `pip freeze`
   in a Conda env — it captures local Conda paths Docker can't find.

2. **ASR 401 errors** usually mean wrong SDK class used, not wrong key.
   Use `MultiModalConversation.call()` not `Recognition.call()`.

3. **TTS returns a URL, not bytes.**
   `response.output["audio"]["url"]` → download from URL → save as WAV.
   `data` field is always empty string. `id` is a UUID string, not audio.

4. **Audio recorder dedup** — `audio_recorder()` returns same bytes on
   every Streamlit/React rerender. Hash audio bytes (md5) and skip if
   already processed. Pattern in `SpeakingCoach.jsx` `handleAudioBlob`.

5. **ASR file size limit ~10MB.** Compress via pydub (mono 16kHz 16-bit)
   in `asr_service.compress_audio()` before sending. ffmpeg required in
   Docker image.

6. **oxc parser is strict.** Multiline JSX attribute expressions cause
   parse errors. Pre-compute all conditions as variables before JSX.

7. **Google OAuth test mode** — only emails listed as test users in
   Google Cloud Console can sign in while app is in testing mode.
   Add judge/reviewer emails as test users before the demo.

8. **learner_id vs user_id** — these are different things.
   `user_id` is the auth identity (users table).
   `learner_id` is the coaching profile (learners table).
   They are linked by `users.learner_id` foreign key.
   Users created before onboarding have `learner_id = null` —
   they must complete onboarding before using coaching features.

9. **Chat Coach opens with no history** for users who haven't submitted
   any essays. The welcome path (`has_history: False`) shows a generic
   message directing them to Writing Coach. This is correct behavior.

10. **TTS quota** — `qwen3-tts-flash` is nearly exhausted.
    Use `qwen3-tts-flash-2025-11-27` instead. Change `TTS_MODEL`
    in `app/services/tts_service.py`.

---

## 7. Definition of done for any new feature

- [ ] API route tested in `/docs` Swagger UI with real JWT
- [ ] React page loads without console errors
- [ ] Auth check present — route returns 400 if no learner_id
- [ ] Attempt saves to `practice_attempts` (verified in DB Browser)
- [ ] Memories extracted and saved with correct `section` value
- [ ] Memory panel shows memories from previous attempt on second run
- [ ] Progress Dashboard has a tab for this module
- [ ] Memory Dashboard shows this module's memories automatically
- [ ] Docker rebuild runs clean (`docker compose up --build`)
- [ ] README.md updated
- [ ] CLAUDE.md §1 checklist updated

---

## 8. Starting a new session on this project

1. Read `README.md` — product scope and current features
2. Read this file — conventions and gotchas
3. Check §1 status checklist against actual file tree
4. **Do not re-add Streamlit** — `app/pages/` and `app/main.py`
   are intentionally deleted. The app is now React + FastAPI only.
5. For new API routes: follow §4 auth pattern exactly
6. For new React pages: follow §4 ProtectedShell pattern
7. For JSX: pre-compute all complex conditions as variables (§6 gotcha 6)
8. Update §1 and README when a phase completes