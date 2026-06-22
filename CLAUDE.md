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
✅ Reading Coach    — full memory cycle, dashboard integrated
✅ Speaking Coach   — full memory cycle, ASR + TTS, dashboard integrated
✅ Listening Coach  — full memory cycle, TTS-generated audio, dashboard integrated
⬜ Chat Coach (free conversation)
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
in the same five-phase pattern. If asked to add a new module (e.g. a "Chat
Coach" or a 5th skill), follow this exact sequence:

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

## 3. Conventions — follow these exactly

### File naming
- Pages: `N_Title_Case_With_Underscores.py` (Streamlit sidebar order depends
  on the leading number)
- Services: `snake_case_service.py`
- Prompts: `snake_case_prompt.txt` or `snake_case_extractor.txt`

### Session state
- Every page that requires a learner profile starts with:
  ```python
  if "learner_id" not in st.session_state or st.session_state["learner_id"] is None:
      st.warning("👈 Please create your **Learner Profile** first.")
      st.stop()
  ```
- Multi-step flows (Speaking, Listening) use a `defaults` dict + a
  `reset_session()` function. Copy this pattern exactly — don't invent a
  new state management approach.

### Qwen calls
- Text generation/evaluation → `app/services/qwen_service.py` →
  `call_qwen()` / `call_qwen_for_json()` (uses OpenAI SDK,
  `DASHSCOPE_API_KEY`, base_url `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`)
- Speech-to-text → `app/services/asr_service.py` (uses **dashscope SDK**,
  `dashscope.MultiModalConversation.call()`, model `qwen3-asr-flash`)
- Text-to-speech → `app/services/tts_service.py` (uses **dashscope SDK**,
  `dashscope.audio.qwen_tts.SpeechSynthesizer.call()`, model
  `qwen3-tts-flash`, voice `Cherry`)

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
  `qwen_service.fix_broken_json()` which asks Qwen to repair its own
  output. This was added because long, detail-rich feedback (5/5 essays
  especially) tends to contain apostrophes that break naive JSON parsing.

### Memory system
- Every section ("Writing", "Reading", "Speaking", "Listening") uses the
  exact same `learner_memories` table and the exact same lifecycle
  functions in `memory_service.py`:
  `extract_and_save_memories` (or section-specific variant) →
  `get_relevant_memories` → `update_memories`
- `update_memories()` is section-agnostic — it takes a `section` param.
  Don't write a new version of this function for a new module; just call
  the existing one with scores reshaped to look like
  `{"scores": {...}, "strengths": [...], "weaknesses": [...], "overall_feedback": "..."}`
- Confidence scale: 0.5–0.9 on extraction, can drop to 0.1 (weaken) or
  rise to 0.95 (strengthen), archived when mastery is detected.

---

## 4. Known gotchas (do not re-debug these)

1. **`requirements.txt` from `pip freeze` in a Conda env is poison.**
   It captures local Conda build paths that don't exist in Docker. Keep
   `requirements.txt` hand-maintained, not freeze-generated.

2. **Qwen ASR/TTS auth uses a different key format check than text
   models.** The `sk-ws-...` key style works fine for
   `MultiModalConversation` and `SpeechSynthesizer` — don't assume a 401
   means the key is wrong; it more often means the wrong SDK/class was
   used (`Recognition` class fails; use `MultiModalConversation.call()`
   for ASR).

3. **TTS returns a `url` to a `.wav` file, not raw bytes, and not in the
   `data` field.** The dict shape is
   `{"data": "", "expires_at": ..., "id": ..., "url": "http://..."}`.
   Always download from `url`, never try to base64-decode `data` (it's
   empty) or `id` (it's a UUID string, not audio).

4. **`audio-recorder-streamlit` (not `streamlit-audio-recorder`) is the
   correct package.** It returns raw bytes directly — no pydub
   conversion needed for the recorder itself.

5. **The recorder causes an infinite transcription loop if you don't
   deduplicate.** `audio_recorder()` keeps returning the same bytes on
   every Streamlit rerun. Fix: hash the audio bytes (md5, first 12 chars
   is enough) and track processed hashes in
   `st.session_state[f"processed_audio_{key}"]`. Only transcribe if the
   hash hasn't been seen. This pattern is in
   `render_audio_input()` in `6_Speaking_Coach.py` — copy it for any new
   audio input UI.

6. **Qwen ASR has a file size limit (~10MB) and the default recorder
   sample rate produces large files.** Fix: record at `sample_rate=16_000`
   in `audio_recorder()`, and compress via `pydub` (mono, 16kHz, 16-bit)
   in `asr_service.compress_audio()` before sending. For very long
   recordings (Part 2 monologues), `transcribe_in_chunks()` splits into
   60-second segments as a fallback. ffmpeg must be installed in the
   Docker image (`apt-get install ffmpeg`) for pydub to work.

7. **IELTS Listening exam logic: questions are previewed BEFORE audio
   plays, audio plays ONCE, no replay.** This was a deliberate UX
   correction mid-build — don't revert to "audio hidden after listening"
   or "audio available on loop" patterns; both are wrong relative to the
   real exam and were explicitly fixed.

8. **TTS audio generation takes 10-20s.** The Listening Coach generates
   audio in the background while the learner previews questions
   (`preview_and_load` state) rather than showing a blocking spinner with
   nothing to do. Keep this pattern for any future TTS-dependent flow.

---

## 5. Definition of done for any new feature

Before considering a phase/feature complete, confirm:

- [ ] Content validates standalone (`python -c "..."` test passes)
- [ ] Service logic tested standalone, not just through the UI
- [ ] Page checks for `learner_id` before anything else
- [ ] Attempt saves to `practice_attempts` (verified in DB Browser)
- [ ] Memories extracted and saved to `learner_memories` with correct
      `section` value
- [ ] Memory panel on the page shows memories from a previous attempt
      on the second run
- [ ] `update_memories()` runs after extraction (check terminal logs for
      "Memory update complete")
- [ ] Progress Dashboard has a tab/section for this module
- [ ] Memory Dashboard shows this module's memories without code changes
      (if it doesn't, something is wrong with the `section` value)
- [ ] Docker rebuild (`docker compose up --build`) runs clean start to
      finish
- [ ] README.md updated to reflect the new module
- [ ] This CLAUDE.md checklist (§1) updated

---

## 6. Where to look first when something breaks

| Symptom | Likely cause | Look at |
|---|---|---|
| `JSONDecodeError` from Qwen response | Apostrophes/smart quotes in long feedback | `json_utils.py`, consider `fix_broken_json` |
| 404 on ASR/TTS call | Used OpenAI SDK instead of dashscope SDK | `asr_service.py` / `tts_service.py` imports |
| 401 Unauthorized on ASR/TTS | Wrong SDK class used (e.g. `Recognition` vs `MultiModalConversation`) | Compare against working pattern in this file §3 |
| Infinite rerun / repeated transcription | Missing audio dedup hash | `render_audio_input()` pattern in §4.5 |
| "file size too large" from ASR | No compression before sending | `asr_service.compress_audio()` |
| TTS "works" but saved file won't play | Saved `data` or `id` field instead of downloading from `url` | §4.3 |
| New module's memories don't show in Memory Dashboard | `section` string mismatch (case-sensitive) | Check exact string matches "Writing"/"Reading"/"Speaking"/"Listening" pattern |
| Docker build fails on `pip install` | `requirements.txt` was freeze-generated in Conda | Hand-edit to only actual deps |

---

## 7. How to start a new session on this project

When starting a new Claude Desktop/Code session on this repo:

1. Read `README.md` for product scope.
2. Read this file (`CLAUDE.md`) for build conventions and gotchas.
3. Check §1 status checklist against the actual file tree to confirm
   it's accurate (things may have changed since last update).
4. If continuing an existing module: follow the existing pattern in that
   module's service/page files — don't introduce a new state management
   or error-handling style.
5. If building a new module: follow §2 exactly, phase by phase, testing
   standalone before wiring into Streamlit.
6. Update §1 and the README roadmap when a phase completes.