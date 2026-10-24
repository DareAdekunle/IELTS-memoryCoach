# BandUp IELTS — Plan

The single source of truth for what we're building next and what's done.
Update the checkboxes as work lands; keep finished sprints for history.

**Goal:** turn BandUp from a working prototype into a trustworthy, evidence-driven
IELTS coach — accurate scores first, then a stronger learner model, then scale.

**Principles**
- Fix what's broken before building new things.
- Validate assessment quality before rebuilding infrastructure around it.
- Deterministic code owns learner records (ranks, stages, permissions); the
  model interprets and teaches.
- Every sprint ends with tests passing (`docker exec ielts-api-dev pytest`) and
  the docs updated.

Related: [`README.md`](README.md) (what it is) ·
[`CLAUDE.md`](CLAUDE.md) (how to build it) ·
[`docs/product-strategy.md`](docs/product-strategy.md) (market + long-term phases)

---

## Status at a glance

| Sprint | Focus | Status |
|---|---|---|
| 0 | Stabilise — security, migrations, tests, costs, WhatsApp | ✅ Done |
| 1 | Assessment validity | ⬜ Next |
| 2 | Memory 2.0 | ⬜ |
| 3 | Diagnostic + adaptive planning | ⬜ |
| 4 | Durable agent workflows | ⬜ |
| 5 | UX, content, production hardening | ⬜ |
| 6 | Closed beta + launch | ⬜ |

---

## Open decisions

- [ ] **Hosting** — the Alibaba Cloud ECS server was shut down (Oct 2026) for
      cost; the app runs locally. Choose where the beta will run and its budget.
- [ ] **Premium price** — the landing page shows $12/month; older material said
      $9.99. Pick one.
- [ ] **Domain** — still `ielts.qonda.xyz`; decide on a BandUp domain.
- [ ] **WhatsApp go-live** — Meta Business verification + a public number.

---

## Sprint 0 — Stabilise ✅

Ship nothing new; fix what's broken.

- [x] Tutor system prompt and transcript held server-side; sessions owned by
      one learner (`tutor_session_transcripts`)
- [x] Agent tools always run as the authenticated learner (Coach, Tutor,
      Telegram, WhatsApp)
- [x] `/mcp-server` requires `MCP_API_TOKEN`
- [x] Alembic migrations; `scripts/migrate.py` runs before the API
- [x] Rename Qonda → BandUp (domain and internal names unchanged)
- [x] pytest suite: rank rules, trust boundaries, memory isolation, channels
- [x] Cost model — `scripts/cost_model.py` (~$0.80–1.20 per active learner/month)
- [x] WhatsApp parity: router registered, guardrails, background replies,
      duplicate filtering
- [x] Bot linking by one-time code; webhook verification for both bots
- [x] Fixed: Coach agent crashing on malformed tool arguments
- [x] Fixed: Speaking feedback audio (retired TTS model)
- [x] Local Docker setup works without production TLS
- [x] Hackathon material removed; README / CLAUDE.md / ARCHITECTURE updated
- [x] Removed dead code: `skill_classifier_service.py`, `agent_controller.py`,
      unused classifier prompts

---

## Sprint 1 — Assessment validity ⬜

The most important work: scores must be defensible before anything is built on them.

- [ ] Pilot first: 20 essays from ~10 writers, 2 raters (see
      `evaluation/writing/README.md`)
- [ ] Collect 50–100 Writing samples across Bands 5–8 with ratings from 2–3
      qualified IELTS raters; include borderline cases
- [ ] Collect 30–50 Speaking samples (audio) with ratings
- [x] Evaluation harness — `scripts/eval_writing.py`: rater agreement, then
      BandUp vs rater average (MAE, bias, within ±0.5/±1.0, QWK), cached
      scores; templates + rater protocol in `evaluation/writing/`
- [x] Candidate band scorer on the four official criteria —
      `app/services/band_scoring_service.py` (not yet used by the app)
- [ ] **Decide:** switch the Writing Coach to official-criteria bands. Today it
      scores five custom skills on 1–5, so no essay gets an IELTS band
- [ ] Unify the two Writing scoring paths (typed essays use the streaming
      route's prompt; handwritten essays use `evaluate_writing()` with a
      different rubric)
- [x] Free reference data: 10 official examiner scripts (ielts.org samples)
      + 154 writing9 essays (crowd/site labels, dev/test) — no recruiting
- [x] Scorer experiments on dev (Oct 2026): `qwen3.5-plus` beat `qwen-plus`
      (within ±0.5: 35% → 52%); anchor essays and isotonic calibration gave
      no measurable gain and were not adopted
- [x] **Result on unseen data** (`qwen3.5-plus`, plain prompt `cab6bb5a07`):
      writing9 test 44% within ±0.5 / 69% within ±1.0; examiner scripts 50% /
      60%. Mid bands good (5.5–6.5: 69% / 87%); scores pulled toward 6 —
      band 7+ scripts ~1–2 bands low, ≤5 ~1 band high. **Below target**
- [ ] **Decide:** keep precise bands out of the app for now, or show a range
      (e.g. "Band 6–7")
- [ ] Trustworthy reference for the high bands: one qualified rater scores
      30–40 writing9 essays with `RATER_GUIDE.md` (~$100)
- [ ] Separate Task 1 (Academic / General) and Task 2 scoring logic
- [ ] Fix the weakest criteria first (typically Task Response, Coherence)
- [ ] Speaking: separate transcript-based criteria from pronunciation; test
      across accents and recording quality
- [ ] Reading/Listening: explicit answer keys with accepted variants and word
      limits; AI explains, never decides correctness
- [ ] `assessment_versions` table — record model, prompt and rubric version per score
- [ ] Label all scores as estimates in the UI

**Exit:** Writing within ±0.5 band on ≥80% of the held-out set; scores
labelled as estimates.

---

## Sprint 2 — Memory 2.0 ⬜

Make every memory traceable and trustworthy.

- [ ] Link each memory to the attempt/session that produced it (`memory_evidence`)
- [ ] De-duplicate near-identical memories before insert
- [ ] Detect contradictions; lower confidence on reliable counter-evidence
- [ ] Separate episodic (this session) from stable pattern memories
- [ ] Generate embeddings on every memory write path
- [ ] Hybrid keyword + semantic retrieval, constrained by section and skill
- [ ] Memory audit log
- [ ] Retrieval evaluation set — measure before adding infrastructure (e.g. pgvector)

**Exit:** every active memory traces to a source; repeated similar
submissions don't create duplicates.

---

## Sprint 3 — Diagnostic + adaptive planning ⬜

- [ ] Initial diagnostic: 2 Writing tasks + 1 Reading passage + a Speaking
      sample → estimated band per section
- [ ] Learning planner — deterministic prioritisation (weakest skill, target
      band, test date, available time); model writes only the explanation
- [ ] `learning_objectives` and `learning_plan_items` tables
- [ ] Spaced review intervals built on `clean_streak` history
- [ ] Planner proposes the schedule in the existing Study Scheduler

**Exit:** a new learner has an explainable study plan within 10 minutes of joining.

---

## Sprint 4 — Durable agent workflows ⬜

Now that we know what assessment should produce, make it reliable.

- [ ] Model abstraction layer (one place for clients, retries, timeouts, usage)
- [ ] Coach workflow on a durable, checkpointed workflow engine (Writing first)
- [ ] Idempotent submissions — retries never double-count ranks or memories
- [ ] Tutor workflow with checkpointed sessions; resume interrupted lessons
- [ ] Tracing for model calls, tool calls and retries
- [ ] Pedagogy rules stay deterministic Python — they do not move into the engine

**Exit:** interrupted runs recover; no duplicate rank/memory writes on replay.

---

## Sprint 5 — UX, content, production hardening ⬜

- [ ] Writing editor: autosave, word count, timer, feedback highlighted in text
- [ ] Speaking mock-exam mode, separate from tutoring mode
- [ ] Progress dashboard: band trajectory, criterion trends
- [ ] Listening replay/transcript limits in the UI
- [ ] Versioned content with review status (passages, tracks, prompts)
- [ ] Dev / staging / production environments
- [ ] Tested database backup + restore
- [ ] Rate limiting and request-size limits
- [ ] Retention, export and deletion for learner data
- [ ] Security review before public beta

---

## Sprint 6 — Closed beta + launch ⬜

- [ ] Hosting live (see Open decisions); bots reachable with webhook secrets set
- [ ] Closed beta: 20–50 learners across three proficiency levels
- [ ] Measure 7-day retention, plan adherence and score change over 4 weeks
- [ ] Fix the top 10 friction points from beta feedback
- [ ] Staged public launch

---

## Backlog (not scheduled)

- [ ] Teacher / admin dashboard
- [ ] Full practice sessions inside Telegram/WhatsApp (see product strategy)
- [ ] Optimise Coach agent cost (largest variable AI cost)
- [ ] `scripts/eval_pedagogy.py` on real tutor sessions (tag reliability)
