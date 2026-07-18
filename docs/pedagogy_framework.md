# Qonda IELTS — Pedagogical Framework

> Python selects the teaching method. Qwen delivers it. The learner never notices the seam.

This document explains the theory behind the Pedagogical Skill Layer, the design decisions made in adapting it to an AI-driven product, and how every concept maps to a specific file and function in the codebase.

---

## 1. The Core Insight

Most AI tutoring tools use the same strategy regardless of what the learner already knows. A Band 4 learner and a Band 7 learner get the same chat interface, the same hints, the same essay feedback format.

The Pedagogical Skill Layer fixes this. Before the AI Tutor says a single word, a deterministic planner has already decided:

- **What** to teach (the weakest assessed criterion, from the rank engine)
- **How** to teach it (framework chosen by stage and criterion, never by the AI)
- **How much support** to give (full scaffolding → partial → minimal → none, evidence-gated)
- **Under what conditions** (timed or untimed, replay limits, transcript access)
- **What success looks like** (exit criteria that tighten as the learner improves)

The AI Tutor carries out the plan. It does not set the plan. This distinction is the entire architecture.

---

## 2. Research Foundations

The layer draws on five bodies of evidence-based practice:

| Principle | Source insight | How it's applied |
|---|---|---|
| **Backward Design** (Wiggins & McTighe) | Start with the target performance, work backward to the lesson | Every session targets a specific IELTS band descriptor — the `target_descriptor` field drives all activities |
| **Zone of Proximal Development** (Vygotsky) | Learning happens at the edge of what the learner can do independently | Four stages map learners to their current ZPD; support fades as independence grows |
| **Dynamic Assessment** (Vygotsky / Lantolf) | Hints reveal learning potential; mediator gives weakest hint first | All hints logged with level 1–4; hint dependency measured per session |
| **Support Fading / Scaffolding** (Wood, Bruner, Ross) | Scaffolding is temporary — withdraw it as competence grows | `fading.py` enforces a 3-success, low-hint, high-accuracy gate before support reduces |
| **Feedback Triad** (Hattie & Timperley) | Feedback that names current position, the goal, and the next step has the highest effect size | Every significant feedback message must contain all three elements; validated by `spine.py` |

---

## 3. Learner Stages

Stages are tracked **per criterion**, not per section. A learner can be in Independent Control for Task Response while still in Foundations for Grammar — and each criterion gets the teaching approach it actually needs.

```
Foundations         band ≤ 5.5    bottleneck: knowledge
                                  the learner doesn't yet know what to do

Guided Control      band = 6.0    bottleneck: consistency
                                  the learner knows but doesn't apply it reliably

Independent Control band 6.5–7.0  bottleneck: control under exam conditions
                                  the learner can do it with time; needs exam pressure

Automatization      band ≥ 7.5    bottleneck: precision
                                  the basics are there; needs nuance and natural fluency
```

**Cold start:** A learner with no evidence defaults to Foundations — the safest assumption, corrected as soon as their first practice attempt is submitted.

**Stage is derived, never stored.** `stage_resolver.py` computes stage live from `learner_skill_ranks`. There is no `stage` column in the database. This means stage always reflects the most current evidence and cannot drift from the underlying rank.

```python
# app/pedagogy/stages.py
def band_to_stage(band: float | None) -> LearnerStage:
    if band is None:       return LearnerStage.FOUNDATIONS
    if band <= 5.5:        return LearnerStage.FOUNDATIONS
    if band <= 6.0:        return LearnerStage.GUIDED_CONTROL
    if band <= 7.0:        return LearnerStage.INDEPENDENT_CONTROL
    return                        LearnerStage.AUTOMATIZATION
```

---

## 4. The 16 Teaching Frameworks

Four frameworks per section. Each framework has a `roles_by_stage` table specifying whether it is **dominant**, **supporting**, **introduced**, **faded**, or **retired** at each stage. The Planner reads these from `app/data/pedagogical_frameworks.json` via the registry (`app/pedagogy/registry.py`).

### Writing (4 frameworks)

| Framework | Stage role | When it's used |
|---|---|---|
| **Genre-Based Pedagogy** | Dominant at Foundations | Learner doesn't understand the essay genre — deconstruct model texts, identify conventions |
| **Process Writing** | Dominant at Guided/Independent | Learner knows the genre but needs structured practice through drafting stages |
| **Focused Indirect Corrective Feedback** | Supporting from Foundations | Recurring grammar/lexical errors — highlight without correcting; learner self-repairs |
| **Scaffolding with Fading** | Supporting throughout | Sentence frames, paragraph templates, planning grids — removed as independence grows |

**Routing logic** (deterministic, `select_writing_framework`):
- Unfamiliar task type → Genre-Based Pedagogy (always)
- Grammar or Lexical criterion → Focused Indirect Corrective Feedback (always)
- Task Response or Coherence at Foundations → Genre-Based Pedagogy
- Task Response or Coherence at Guided+ → Process Writing

### Reading (4 frameworks)

| Framework | Stage role | When it's used |
|---|---|---|
| **Explicit Strategy Instruction** | Dominant at Foundations | Teach skimming, scanning, T/F/NG strategies explicitly before practice |
| **Text-Based Questioning** | Dominant at Guided | Move from strategy to application — use real passage questions with guided analysis |
| **Gradual Release of Responsibility** | Dominant at Independent | I do → We do → You do; timed sections with diminishing guidance |
| **Error-Driven Diagnosis** | Supporting at all stages | Pattern incorrect answers to find the underlying comprehension strategy failure |

**Routing:** Vocabulary gaps at Foundations/Guided → Explicit Strategy Instruction. Otherwise uses the dominant framework for the current stage.

### Listening (4 frameworks)

| Framework | Stage role | When it's used |
|---|---|---|
| **Micro-Listening & Dictation** | Dominant at Foundations | Decoding failures — slow-speed segment work, dictation drills to build phoneme-to-word mapping |
| **Process-Based Listening** | Dominant at Guided | Pre-listening prediction, while-listening focus, post-listening self-check cycle |
| **Metacognitive Cycle** | Dominant at Independent | Learner plans, monitors, and evaluates their own listening attention and strategy use |
| **Test Strategy Training** | Dominant at Automatization | Distractor resistance, time management, question-type pattern recognition under exam conditions |

**Routing:** Decoding criterion at Foundations → Micro-Listening & Dictation. Otherwise prefers Metacognitive Cycle when dominant; falls back to Process-Based.

### Speaking (4 frameworks)

| Framework | Stage role | When it's used |
|---|---|---|
| **Task-Based Language Teaching** | Dominant at Foundations/Guided | Meaning-focused tasks; fluency before accuracy; post-task analysis |
| **Oral Corrective Feedback** | Supporting at Guided/Independent | Grammar/pronunciation errors — recasts, prompts, explicit correction calibrated to stage |
| **4/3/2 Fluency Technique** | Supporting at Independent/Automatization | Same content, decreasing time → automatized delivery, natural chunking |
| **Reformulation** | Supporting at Independent/Automatization | Lexical range gaps — show the native-speaker version; learner notices and adopts |

**Routing:** Lexical criterion at Independent/Automatization → Reformulation. Grammar/Pronunciation at Guided → Oral Corrective Feedback. Otherwise uses the dominant TBLT framework.

---

## 5. The Shared Pedagogical Spine

Every Tutor reply at every stage must embody these four habits. They do not change with stage — the frameworks change, the spine does not.

```
1. Backward Design
   Every activity is anchored to the target band descriptor.
   The Tutor knows: "What evidence of Band 6.0 grammar am I looking for?"
   before asking the learner to attempt anything.

2. Feedback Triad
   Any significant feedback message must name:
     - GOAL: the target descriptor in plain language
     - CURRENT POSITION: what the learner is actually doing
     - NEXT STEP: one concrete thing to do differently, right now
   Validated softly by spine.py — one log-level nudge on failure, no hard rejection.

3. Dynamic Assessment
   Hints are a diagnostic, not a rescue.
   Level 1 = vague nudge ("look at the verb form")
   Level 2 = narrowed focus ("the subject is plural — what does that mean for the verb?")
   Level 3 = near-answer ("you need the present perfect here")
   Level 4 = full answer/explanation
   The Tutor NEVER skips levels. One level at a time.
   Every hint is recorded as [ACTION: hint level=N] and logged to hint_events.

4. Elicitation Before Telling
   The learner attempts, identifies, or repairs BEFORE any answer is revealed.
   A Tutor that explains before eliciting is teaching the wrong lesson.
```

---

## 6. Support Levels and Fading

Support describes **what resources the Tutor provides**, not what the learner can do.

```
FULL     — models, sentence frames, templates, direct explanation, examples
PARTIAL  — planning prompts, guided questions, selected hints (not answers)
MINIMAL  — vague prompts only; hints only after observable failure
NONE     — independent performance under exam-realistic conditions; no Tutor support
```

**Default support per stage** (the starting point, before evidence adjusts it):

```
Foundations         → FULL
Guided Control      → PARTIAL
Independent Control → MINIMAL
Automatization      → NONE
```

### Fading rules (deterministic, `app/pedagogy/fading.py`)

Support fades **one step at a time**, and only when all three conditions are met:

```
recent_successes  ≥ 3       (three consecutive successful attempts)
average_hint_level ≤ 1.0    (the learner isn't hint-dependent)
independent_accuracy ≥ 0.8  (80% of attempts succeed without help)
```

**Restoration is immediate** — if ≥2 consecutive failures occur after a recent support reduction, support is restored one step. Rank never decreases. The learner doesn't regress; we just hold them longer.

**The AI cannot override this.** The Coach agent may request a support change via the `update_criterion_state` tool, but `evaluate_support_change()` in `fading.py` is the final arbiter. An unearned reduction returns `allowed: False` and the current level is kept.

```python
# Example: earned reduction intercepted to enforce one-step-only rule
# Coach requests PARTIAL → NONE (two steps)
# Guardrail enforces PARTIAL → MINIMAL (one step)
r = evaluate_support_change(
    current_level=SupportLevel.PARTIAL,
    requested_level=SupportLevel.NONE,
    recent_successes=4, average_hint_level=0.5,
    independent_accuracy=0.9, ...
)
# r["allowed"] = True, r["final_level"] = "minimal"
```

---

## 7. Practice Conditions

Conditions are binary gates that **switch** at defined stage transitions. Unlike support levels (which fade gradually), conditions flip on/off — the Tutor cannot ease them, and the AI has no role in deciding them.

### Writing conditions

| Stage | Timed | Templates | Revision required |
|---|---|---|---|
| Foundations | No | Yes | No |
| Guided Control | No | Yes | Yes |
| Independent Control | 40 min | No | Yes |
| Automatization | 40 min | No | Yes + exam mode |

### Listening conditions

| Stage | Replay limit | Transcript |
|---|---|---|
| Foundations | Unlimited | During (read along while listening) |
| Guided Control | 2 replays | After (review only after attempt) |
| Independent Control | 1 play | Review only |
| Automatization | 1 play | Review only + exam mode |

### Reading conditions

| Stage | Timed | Time limit |
|---|---|---|
| Foundations | No | — |
| Guided Control | No | — |
| Independent Control | Yes | 20 min |
| Automatization | Yes | 20 min + exam mode |

### Speaking conditions

| Stage | Timed | Retries |
|---|---|---|
| Foundations | No | Yes |
| Guided Control | No | Yes |
| Independent Control | Yes | No |
| Automatization | Yes | No + exam mode |

---

## 8. The Evidence Loop

The pedagogical layer is not just a teaching system — it's a feedback loop that writes evidence back into the learner model.

```
Practice attempt submitted
        │
        ▼
Coach Agent evaluates + classifies → learner_skill_ranks updated
        │
        ▼
Stage Resolver derives per-criterion band + stage from ranks (live, never stored)
        │
        ▼
Pedagogy Planner builds deterministic session plan
  ├── Target: weakest assessed skill
  ├── Criterion: which rubric category that skill belongs to
  ├── Framework: selected by routing table (stage + criterion)
  ├── Support level: default for stage, adjusted by prior session evidence
  ├── Practice conditions: switched by stage gate
  └── Exit criteria: tightened by stage
        │
        ▼
Plan injected into Tutor system prompt as structured block
        │
        ▼
Tutor teaches — emits [ACTION: hint level=N] + [STATE: drilling] tags
        │
        ▼
Server parses tags → pedagogical_events + hint_events tables
        │
        ▼
At bridge_to_practice → Coach agent interprets session evidence
  ├── Reads hint records: average_hint_level, recent_successes
  ├── Evaluates support change via fading guardrail
  └── Calls update_criterion_state → learner_criterion_state updated
        │
        ▼
Next session: Stage Resolver re-derives stage from updated ranks
             (which now reflect the tutor session evidence too)
```

---

## 9. The ACTION Tag Protocol

The Tutor speaks in natural language. Evidence is captured in structured tags the learner never sees.

```
[ACTION: hint level=2]           — Tutor gave a level-2 hint
[ACTION: attempt result=success] — Learner's attempt succeeded
[ACTION: model_shown]            — Tutor showed a model/example answer
[ACTION: feedback_given]         — Tutor delivered a Feedback Triad message
[ACTION: independent_check]      — Tutor set an independent task (no help)
[ACTION: complete outcome=ready_for_reduced_support]  — session done
[STATE: drilling]                — existing state machine tag (unchanged)
```

Tags are parsed by `app/pedagogy/action_tags.py` using a whitespace-tolerant regex — Qwen sometimes emits `[ ACTION: hint level = 2 ]` with extra spaces, and the parser handles all variants.

**Tags are best-effort.** A missed tag loses one data point; it does not break the conversation. The system degrades gracefully — the teaching continues, the evidence record is just thinner.

**Tags are stripped before display.** The learner sees clean coaching text.

---

## 10. Exit Criteria

Session completion criteria tighten as the learner climbs stages.

| Stage | Min accuracy | Max hint level | Independent successes needed | Timed transfer |
|---|---|---|---|---|
| Foundations | 60% | Level 3 | 1 | No |
| Guided Control | 80% | Level 2 | 2 | No |
| Independent Control | 80% | Level 1 | 2 | Yes |
| Automatization | 90% | Level 1 | 3 | Yes |

The Tutor uses these as the target to aim for when deciding whether to emit `[ACTION: complete outcome=...]`. The Coach validates them when interpreting session evidence.

---

## 11. The Coach / Tutor Boundary

The Pedagogical Skill Layer reinforces the core architectural boundary:

| Role | Reads | Writes | Can do |
|---|---|---|---|
| **Tutor** | learner data, session plan | pedagogical_events, hint_events | Teach, drill, record evidence via tags |
| **Coach** | session evidence, hint records | learner_criterion_state, learner_skill_ranks, learner_memories | Interpret outcomes, update support levels, update ranks |

The Tutor **records what happened**. The Coach **decides what it means**. Neither can do the other's job. This boundary is enforced by separate tool schemas and a guard that blocks `submit_classification` inside `coach_tutor_session`.

---

## 12. File-by-File Map

```
app/pedagogy/
  stages.py               — LearnerStage, SupportLevel, band_to_stage(), fading helpers
  registry.py             — Loads pedagogical_frameworks.json; get_framework(),
                            get_dominant_frameworks(), get_shared_spine()
  descriptors.py          — Loads band_descriptors.json; get_descriptor(),
                            get_target_descriptor() → next 0.5 band target
  stage_resolver.py       — get_criterion_bands(), resolve_criterion(),
                            upsert_criterion_state(), get_all_criterion_stages()
  session_policy.py       — PracticeConditions, conditions_for() per section/stage
  planner.py              — select_framework() routing tables, exit_criteria_for(),
                            create_session_plan(), format_plan_block()
  action_tags.py          — ACTION_RE regex, parse_action_tags(), TAG_PROTOCOL_PROMPT
  fading.py               — should_reduce_support(), should_restore_support(),
                            evaluate_support_change() guardrail
  spine.py                — validate_spine(), Feedback Triad heuristic check

app/data/
  pedagogical_frameworks.json  — 16 frameworks (4/section) + 4-item shared spine
                                  each with roles_by_stage, procedure, constraints,
                                  evidence_of_progress, reactivation_triggers
  band_descriptors.json        — Per-criterion band descriptors (bands 4–9)
                                  for all 4 IELTS sections

app/db/models.py (pedagogy tables)
  TutorSession               — one per Tutor chat session; links to plans + events
  LearnerCriterionState      — support level + counters per learner/criterion
  TutorSessionPlan           — persisted PedagogyPlan; links to session
  PedagogicalEvent           — one row per [ACTION:] tag parsed from Tutor output
  HintEvent                  — one row per hint; level, self_corrected flag

app/services/
  pedagogical_event_service.py — CRUD for all 5 pedagogy tables; summarize_session_evidence()
  chat_coach_service.py        — start_chat_session() (creates plan, injects prompt block)
                                 continue_chat_session() (parses tags, records events)
                                 parse_state_tag() (whitespace-tolerant, whole-text scan)
  coach_service.py             — coach_tutor_session() (interprets evidence at session end)
  agent_tools.py               — update_criterion_state (Coach), get_pedagogical_context,
                                 get_current_session_plan (Tutor)

api/routes/
  pedagogy.py              — GET /pedagogy/criterion-stages, GET /pedagogy/frameworks
  chat.py                  — /chat/start returns session_id + pedagogy
                             /chat/continue triggers coach_tutor_session in background

frontend/src/
  api/pedagogy.js          — getCriterionStages(), getFrameworks()
  pages/ChatCoach.jsx      — Pedagogy strip (stage, framework, support, target descriptor)
  pages/SkillMastery.jsx   — "Learning stages" section with criterion cards

scripts/
  eval_pedagogy.py         — Offline behaviour eval: hint escalation, outcome coverage,
                             independent check before completion, evidence recorded
tests/
  test_pedagogy_registry.py    — 7 tests: stage boundaries, 16 frameworks, role tables,
                                  spine, support fade/restore, descriptors, targets
  test_pedagogy_planner.py     — 6 tests: routing (all 5 spec scenarios), exit criteria,
                                  condition gates, fading + guardrail, tag parser, spine
  test_pedagogy_integration.py — 6 integration tests: full session lifecycle, cold-start,
                                  events + hints, criterion state + guardrail, plan lifecycle
```

---

## 13. What the AI Controls vs. What Python Controls

This boundary is the most important design decision in the layer. Violations would make the system unpredictable and unauditable.

| Decision | Controlled by | Why |
|---|---|---|
| Which framework to use | Python (routing table) | Reproducible, auditable, can be unit-tested |
| Which stage the learner is in | Python (band_to_stage) | Always derived from rank engine, never drifts |
| Whether support can be reduced | Python (fading.py guardrail) | Unearned reductions would harm learning |
| Practice conditions (timing, replay limits) | Python (session_policy.py) | Must enforce exam-realistic conditions; AI would soften them |
| Hint escalation order | Python (exit criteria + tag protocol) | Must be weakest-first; AI would jump to strong hints |
| Whether a session is complete | Python (exit criteria) | AI optimism bias; it would exit too early |
| **What to say in a session** | Qwen (Tutor agent) | Natural language, empathy, contextual explanation — human-like delivery |
| **Which hints to give** | Qwen (within level constraints) | The content of a hint is creative; the level is mechanical |
| **When to emit an action tag** | Qwen (prompted by protocol) | The Tutor knows when it gave a hint; we ask it to self-report |
| **Whether a learner attempt succeeded** | Qwen (Tutor judgment) | Semantic correctness is a language task |
