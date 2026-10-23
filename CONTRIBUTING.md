# Contributing to BandUp IELTS

BandUp IELTS is designed for extensibility. The taxonomy-driven
architecture and modular service layer mean most new capabilities can
be added without touching existing code.

---

## Adding a new IELTS skill taxonomy

The Writing skill taxonomy (13 sub-skills, 5 ranks) is defined in
`app/data/skill_taxonomy_writing.json`. Adding taxonomies for Reading,
Speaking or Listening requires only:

1. Create `app/data/skill_taxonomy_<section>.json` following the
   existing schema (categories → skills → ranks)
2. Add entries to `SKILL_ID_TO_MEMORY_LABELS` in
   `app/services/skill_taxonomy_service.py`
3. Create a classifier prompt in `app/prompts/skill_classifier_<section>_prompt.txt`

The rank engine, memory system, progress dashboard, and Chat Coach
will work with the new taxonomy automatically — no UI changes needed.

---

## Adding a new AI provider

Text generation (`app/services/qwen_service.py`) uses the OpenAI-compatible
SDK, so another OpenAI-compatible provider can be used by setting
`MODEL_STUDIO_ENDPOINT` (base URL), `DASHSCOPE_API_KEY` and `QWEN_MODEL`.
Speech-to-text, text-to-speech and
embeddings call DashScope-specific endpoints (`asr_service.py`,
`tts_service.py`, `embedding_service.py`) and would each need their own
adapter.

---

## Adding a new coaching module

Each coaching module follows the same pattern:

```
Backend:
  api/routes/<section>.py              ← REST endpoints
  app/services/<section>_service.py    ← business logic
  app/prompts/<section>_evaluator.txt  ← Qwen prompt
  app/prompts/<section>_extractor.txt  ← memory extraction prompt
  Add to memory_service.py:
    extract_<section>_memories()
    save_<section>_attempt()

Frontend:
  src/api/<section>.js                 ← axios API client
  src/pages/<Section>Coach.jsx         ← React page
  Add to src/components/AppShell.jsx   ← sidebar nav entry
  Add tab to src/pages/ProgressDashboard.jsx
```

The Memory Dashboard shows all sections automatically without changes.

---

## MCP server integration

The coaching data layer is also exposed as an MCP server
(`app/mcp/memory_server.py`), mounted at `/mcp-server`. Its tools include
`get_learner_weaknesses`, `get_skill_ranks`, `get_recent_attempts`,
`get_coaching_context` and the study-schedule tools.

These tools accept any `learner_id`, so the endpoint is **admin-only**:
requests must send `Authorization: Bearer $MCP_API_TOKEN`, and the endpoint
rejects everything when `MCP_API_TOKEN` is unset. Learner-facing agents (the
Tutor and the chat coaches) call the same functions in-process, always as the
authenticated learner.

---

## Development setup

```bash
cp .env.example .env            # fill in your keys; each is described there
docker compose up -d --build    # Postgres + API (:8000) + Vite dev server (:5173)
docker exec ielts-api-dev python seed_demo.py   # optional demo learner
```

Backend and frontend source are mounted into the containers, so changes
reload automatically. After changing a database model, create a migration
and restart the API:

```bash
docker exec ielts-api-dev alembic revision --autogenerate -m "describe change"
docker restart ielts-api-dev
```

## Tests

```bash
docker exec ielts-api-dev pytest
```

The suite uses a throwaway SQLite database and blocks live Qwen calls —
mock model replies with `FakeLLM` from `tests/conftest.py`. New rules,
permissions and trust boundaries need a test. Scripts that call the live
API live in `scripts/manual_checks/` and are run by hand.

See `CLAUDE.md` for the conventions every change must follow.
