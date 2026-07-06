# Contributing to IELTS MemoryCoach

IELTS MemoryCoach is designed for extensibility. The taxonomy-driven
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

`app/services/qwen_service.py` uses the OpenAI-compatible SDK.
Any provider supporting this interface can be swapped in by changing
two environment variables:

```
QWEN_BASE_URL=https://your-provider/v1
DASHSCOPE_API_KEY=your-provider-api-key
```

The rest of the system (services, prompts, routes) is entirely
provider-agnostic.

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

The MemoryCoach memory layer is exposed as an MCP server at
`app/mcp/memory_server.py`. Any MCP-compatible AI agent can query:

- `get_learner_weaknesses(learner_id)` — active weakness memories
- `get_skill_ranks(learner_id)` — all 13 skill rank levels
- `get_recent_attempts(learner_id, section, limit)` — attempt history
- `get_weakest_skill(learner_id)` — single weakest skill for targeting

This enables external tutoring systems, school dashboards, or other
agents to consume a learner's coaching history without direct DB access.

---

## Development setup

```bash
# Backend
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000

# Frontend
cd frontend && npm install && npm run dev

# Run both together
# Terminal 1: uvicorn api.main:app --reload --port 8000
# Terminal 2: cd frontend && npm run dev
```

Environment variables — copy `.env.example` and fill in your keys:

```bash
cp .env.example .env
```
