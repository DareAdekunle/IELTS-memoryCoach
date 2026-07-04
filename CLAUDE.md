# CLAUDE.md — Agent Build Harness for IELTS MemoryCoach

This file is for Claude (or any agent) picking up work on this project in a
new session. Read this BEFORE making changes. It captures the build pattern,
conventions, and hard-won fixes from the original build so they are not
re-discovered (or re-broken) in future sessions.

For *what the product does*, read `README.md` first. This file is about
*how to keep building it correctly*.

---

## 1. Project status (update this section as you go)

```
✅ Phase 1-11  — Core MVP: Profile, DB, Docker, Writing Coach (full memory cycle)
✅ Reading Coach          — full memory cycle, dashboard integrated
✅ Speaking Coach         — full memory cycle, ASR + TTS, dashboard integrated
✅ Listening Coach        — full memory cycle, TTS-generated audio, dashboard integrated
✅ Skill Taxonomy         — 13 Writing sub-skills, official IELTS band descriptors,
                            5 ranks per skill, skill_taxonomy_writing.json
✅ Skill Ranking System   — learner_skill_ranks table, deterministic clean_streak
                            rule engine, rank-up/no-rank-down, capped at 5
✅ Skill Classifier       — separate Qwen call post-essay, fixed-list prompt,
                            applies_skill_classifications_batch() wired into
                            Writing Coach submit handler
✅ Chat Coach             — conversational tutor, explicit [STATE:] tag tracking,
                            grounded in real learner_memories + learner_skill_ranks,
                            profile-switch auto-reset, session-only history
⬜ Skill mastery dashboard (dedicated view for learner_skill_ranks progress)
⬜ Extend taxonomy to Reading, Speaking, Listening
⬜ Teacher / admin dashboard
⬜ FastAPI backend upgrade
⬜ PostgreSQL upgrade
⬜ Cloud deployment
```

**Always update this checklist when you complete a phase.** This is the
single source of truth for "what's done" — don't trust your own assumption,
check this list and the actual files.

---

## 2. The build pattern (follow this for ANY new module)

Every IELTS skill module (Writing, Reading, Speaking, Listening) was built
in the same five-phase pattern. If asked to add a new module or extend the
taxonomy to another section, follow this sequence:

```
Phase A — Content
  Create app/data/<module>_content.json
  Validate it loads and has the right shape via a quick python -c test
  before building anything on top of it

Phase B — Service layer
  Create app/services/<module>_service.py
  Pure logic: load content, evaluate/check answers, no Streamlit imports
  Test with a standalone script BEFORE touching the page

Phase C — Evaluator / prompt engineering (if it uses Qwen)
  Create app/prompts/<module>_evaluator_prompt.txt
  Create or extend a service that calls qwen_service.call_qwen / call_qwen_for_json
  Test the full prompt → parse → result chain standalone first

Phase D — Streamlit page
  Create app/pages/N_<Module>_Coach.py
  ALWAYS check learner_id in session_state first (see pattern below)
  Use st.session_state for ALL multi-step flow — never rely on local vars
    surviving a rerun

Phase E — Memory + Dashboard integration
  Create app/prompts/<module>_memory_extractor.txt
  Add extract_<module>_memories(), save_<module>_attempt(),
    get_<module>_progress_data() to memory_service.py
  Wire save → extract → update_memories() into the page's submit handler
  Add a new tab to app/pages/4_Progress_Dashboard.py
  Memory Dashboard (5_Memory_Dashboard.py) needs NO changes — it already
    reads all sections generically
```

**Do not skip phases or merge them.** Testing each phase standalone (via
`python -c "..."` or a throwaway test file) before wiring it into Streamlit
is what caught every bug in this project. Wiring straight into the UI and
debugging through Streamlit reruns is much slower.

---

## 3. Skill Mastery System — how it works (Writing only, for now)

This is a separate system layered on top of the existing memory system.
Read this before touching any skill ranking logic.

### Three separate Qwen calls per Writing essay submission

```
Call 1 — evaluate_writing()         → 5-score rubric + feedback + memories
Call 2 — classify_writing_skills()  → 13-skill fixed-list classification
Call 3 — extract_and_save_memories() → free-text memory extraction
```

These are intentionally separate calls. Call 1 is long and conversational
(the 5/5 essays trigger apostrophe JSON bugs). Call 2 is short and strict
(3-way classification per skill, must always parse cleanly). Do NOT merge
them to save API calls — the decoupling is the point.

### The rank-up rule (do not change without discussion)

```
On each essay:
  Qwen classifies each of the 13 skill_ids as one of:
    "demonstrated_strength"  → clean_streak += 1
    "demonstrated_weakness"  → clean_streak = 0 (FULL RESET, not decrement)
    "not_applicable"         → no change, record not even touched

clean_streak reaches 3 → current_rank += 1, clean_streak = 0
Rank is capped at MAX_RANK = 5
Rank NEVER decreases automatically (no rank-down, ever)
```

This is intentional and was explicitly locked. Do not add automatic
rank-down logic without reopening this design decision.

### Skill ID → memory label bridge

`learner_memories.skill` is free text Qwen chose itself ("Thesis Clarity").
`learner_skill_ranks.skill_id` is a fixed taxonomy key ("tr_position_clarity").
The bridge lives in `skill_taxonomy_service.SKILL_ID_TO_MEMORY_LABELS` — a
hand-authored dict mapping each skill_id to a list of memory label strings.
This is used by `find_evidence_memory_for_skill()` in memory_service.py to
find real quotable text for the Chat Coach. If you add new skill_ids (e.g.
when extending the taxonomy to Reading), add them to this dict too.

### Chat Coach state machine

The Chat Coach uses explicit state tracking, not implicit (Qwen infers).
Each Qwen reply ends with a hidden tag: `[STATE: introduction]` etc.
Valid states: `introduction`, `explaining`, `drilling`, `bridge_to_practice`.
`chat_coach_service.parse_state_tag()` strips the tag before display and
returns it for st.session_state storage. Default if tag is missing or
invalid: `"explaining"` (safe middle state, doesn't prematurely show
bridge button or restart introduction).

Profile-switch mid-session: tracked via `chat_learner_id` in session_state.
If `chat_learner_id != learner_id` on page load, `reset_chat()` is called
before anything renders. This was a real bug caught in testing.

---

## 4. Conventions — follow these exactly

### File naming
- Pages: `N_Title_Case_With_Underscores.py` (Streamlit sidebar order depends
  on the leading number)
- Services: `snake_case_service.py`
- Prompts: `snake_case_prompt.txt` or `snake_case_extractor.txt`
- Data: `snake_case_section.json`

### Session state
- Every page that requires a learner profile starts with:
  ```python
  if "learner_id" not in st.session_state or st.session_state["learner_id"] is None:
      st.warning("👈 Please create your **Learner Profile** first.")
      st.stop()
  ```
- Multi-step flows (Speaking, Listening, Chat Coach) use a `defaults` dict +
  a `reset_session()` / `reset_chat()` function. Copy this pattern exactly
  — don't invent a new state management approach.
- Track which learner a session was built for when the session holds learner-
  specific state (see `chat_learner_id` pattern in 8_Chat_Coach.py).

### Qwen calls
- Text generation/evaluation → `app/services/qwen_service.py` →
  `call_qwen()` / `call_qwen_for_json()` (uses OpenAI SDK,
  `DASHSCOPE_API_KEY`, base_url `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`)
- Speech-to-text → `app/services/asr_service.py` (uses **dashscope SDK**,
  `dashscope.MultiModalConversation.call()`, model `qwen3-asr-flash`)
- Text-to-speech → `app/services/tts_service.py` (uses **dashscope SDK**,
  `dashscope.audio.qwen_tts.SpeechSynthesizer.call()`, model
  `qwen3-tts-flash`, voice `Cherry`)
- Multi-turn chat → `chat_coach_service.continue_chat_session()` calls
  `client.chat.completions.create()` directly (imports `client` and
  `QWEN_MODEL` from qwen_service) — this is the only place in the codebase
  that builds a full multi-turn messages list rather than a single prompt

**These three are NOT interchangeable.** Text models use the OpenAI SDK.
ASR and TTS use the dashscope SDK directly. Do not try to call ASR/TTS
through the OpenAI-compatible endpoint — it returns 404 (confirmed by
testing).

### JSON parsing from Qwen
- Always go through `app/utils/json_utils.py` → `safe_parse_json()`
- Never call `json.loads()` directly on a raw Qwen response. Qwen
  responses can contain markdown fences, smart quotes, apostrophes inside
  string values, and trailing commas — `safe_parse_json` handles all of
  these with cascading fallback strategies.
- If `safe_parse_json` still fails, the next fallback is
  `qwen_service.fix_broken_json()` which asks Qwen to repair its own output.

### Memory system
- Every section ("Writing", "Reading", "Speaking", "Listening", "General")
  uses the exact same `learner_memories` table and lifecycle functions in
  `memory_service.py`.
- `update_memories()` is section-agnostic — just call it with the right
  `section` param and a dict shaped like
  `{"scores": {...}, "strengths": [...], "weaknesses": [...], "overall_feedback": "..."}`
- Confidence scale: 0.5–0.9 on extraction, can drop to 0.1 (weaken) or
  rise to 0.95 (strengthen), archived when mastery is detected.
- The skill ranking system (`learner_skill_ranks`) is SEPARATE from
  `learner_memories` — they run in parallel, serve different purposes, and
  must not be confused. Memories are free-text, confidence-weighted,
  section-level. Ranks are fixed-taxonomy, deterministic, skill-level.

### No frameworks
No LangChain, LlamaIndex, or agent orchestration library is used anywhere
in this codebase. All orchestration is plain Python. This is intentional —
do not introduce a framework dependency without a genuine architectural
reason (e.g. semantic search over a large corpus). The simplicity is a
feature, not an oversight.

---

## 5. Known gotchas (do not re-debug these)

1. **`requirements.txt` from `pip freeze` in a Conda env is poison.**
   It captures local Conda build paths that don't exist in Docker. Keep
   `requirements.txt` hand-maintained, not freeze-generated.

2. **Qwen ASR/TTS auth uses a different SDK from text models.** The
   `sk-ws-...` key style works fine for `MultiModalConversation` and
   `SpeechSynthesizer` — don't assume a 401 means the key is wrong; it
   more often means the wrong SDK/class was used (`Recognition` class
   fails; use `MultiModalConversation.call()` for ASR).

3. **TTS returns a `url` to a `.wav` file, not raw bytes.** The dict
   shape is `{"data": "", "expires_at": ..., "id": ..., "url": "http://..."}`.
   Always download from `url`. Never base64-decode `data` (empty) or `id`
   (a UUID string, not audio).

4. **`audio-recorder-streamlit` (not `streamlit-audio-recorder`) is the
   correct package.** Returns raw bytes directly.

5. **The recorder causes an infinite transcription loop without dedup.**
   `audio_recorder()` keeps returning the same bytes on every Streamlit
   rerun. Fix: hash audio bytes (md5, first 12 chars) and track processed
   hashes in `st.session_state[f"processed_audio_{key}"]`. Pattern is in
   `render_audio_input()` in `6_Speaking_Coach.py`.

6. **Qwen ASR has a file size limit (~10MB).** Fix: record at
   `sample_rate=16_000`, compress via pydub (mono 16kHz 16-bit) in
   `asr_service.compress_audio()`. Fallback: `transcribe_in_chunks()`
   splits into 60s segments. ffmpeg must be in the Docker image
   (`apt-get install ffmpeg`).

7. **IELTS Listening exam conditions are strict by design.** Questions
   previewed before audio plays. Audio plays once. No replay after
   answering begins. Do not revert these UX decisions.

8. **TTS audio generation takes 10-20s.** Use the `preview_and_load`
   state pattern (Listening Coach) for any TTS-dependent flow — generate
   audio in the background while the learner does something productive.

9. **Skill classification uses a SEPARATE Qwen call from essay scoring.**
   This is intentional (not an optimization opportunity). Long feedback
   from 5/5 essays breaks JSON parsing via apostrophes. Keeping calls
   separate means one can fail without breaking the other. Both are
   wrapped in try/except and degrade gracefully.

10. **Chat Coach session state is learner-specific.** Always track
    `chat_learner_id` and compare to `learner_id` on page load. If they
    differ, call `reset_chat()` before anything renders. Skipping this
    causes one learner to see another learner's conversation — a real
    bug found in testing.

11. **The skill rank-up rule is a full reset, not a decrement.** One
    `demonstrated_weakness` resets `clean_streak` to 0, not -1. This
    was an explicit design decision. Do not change to a decrement without
    reopening the design conversation.

---

## 6. Definition of done for any new feature

Before considering a phase/feature complete, confirm:

- [ ] Content validates standalone (`python -c "..."` test passes)
- [ ] Service logic tested standalone, not just through the UI
- [ ] Page checks for `learner_id` before anything else
- [ ] Page resets correctly on profile switch (if it holds learner-specific
      session state — see `chat_learner_id` pattern)
- [ ] Attempt saves to `practice_attempts` (verified in DB Browser)
- [ ] Memories extracted and saved to `learner_memories` with correct
      `section` value
- [ ] Memory panel on the page shows memories from a previous attempt
      on the second run
- [ ] `update_memories()` runs after extraction
- [ ] Progress Dashboard has a tab/section for this module
- [ ] Memory Dashboard shows this module's memories without code changes
- [ ] Docker rebuild (`docker compose up --build`) runs clean
- [ ] README.md updated to reflect the new module
- [ ] This CLAUDE.md checklist (§1) updated

---

## 7. Where to look first when something breaks

| Symptom | Likely cause | Look at |
|---|---|---|
| `JSONDecodeError` from Qwen response | Apostrophes/smart quotes in long feedback | `json_utils.py`, consider `fix_broken_json` |
| 404 on ASR/TTS call | Used OpenAI SDK instead of dashscope SDK | `asr_service.py` / `tts_service.py` imports |
| 401 Unauthorized on ASR/TTS | Wrong SDK class (e.g. `Recognition` vs `MultiModalConversation`) | §4 conventions, Qwen calls section |
| Infinite rerun / repeated transcription | Missing audio dedup hash | `render_audio_input()` in `6_Speaking_Coach.py` |
| "file size too large" from ASR | No compression before sending | `asr_service.compress_audio()` |
| TTS "works" but saved file won't play | Saved `data`/`id` field instead of downloading `url` | Gotcha #3 |
| New module memories don't show in Memory Dashboard | `section` string mismatch (case-sensitive) | Must be exactly "Writing"/"Reading"/"Speaking"/"Listening" |
| Docker build fails on `pip install` | `requirements.txt` was freeze-generated | Hand-edit to actual deps only |
| Chat Coach shows wrong learner's conversation | Missing `chat_learner_id` profile-switch check | Gotcha #10, `8_Chat_Coach.py` reset logic |
| Skill rank never moves despite many essays | `clean_streak` resetting every time | Check skill_classifier output in terminal logs — likely all `demonstrated_weakness` |
| Rank-up message shows but DB not updated | `apply_skill_classifications_batch()` not called or erroring silently | Check try/except in Writing Coach submit handler |
| Chat Coach [STATE:] tag leaks into UI | `parse_state_tag()` regex not matching | Check exact format `[STATE: word]` — space after colon required |

---

## 8. How to start a new session on this project

When starting a new Claude Desktop/Code session on this repo:

1. Read `README.md` for product scope and current feature set.
2. Read this file (`CLAUDE.md`) for build conventions and gotchas.
3. Check §1 status checklist against the actual file tree — things may
   have changed since last update. Trust the file tree, not the checklist.
4. If continuing an existing module: match the existing pattern in that
   module's service/page files exactly — don't introduce new state
   management or error-handling styles.
5. If building a new module: follow §2 exactly, phase by phase, testing
   standalone before wiring into Streamlit.
6. If extending the skill taxonomy to a new section: follow the Writing
   taxonomy pattern (skill_taxonomy_writing.json + SKILL_ID_TO_MEMORY_LABELS
   bridge + new classifier prompt) — don't modify the existing Writing
   taxonomy file, create a new section-specific one.
7. Update §1 and the README roadmap when a phase completes.  