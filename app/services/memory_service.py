import os
import sys
import uuid
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from datetime import datetime, timezone
from app.db.database import SessionLocal
from app.db.models import PracticeAttempt, LearnerMemory, MasteryScore
from app.services.qwen_service import call_qwen_for_json
from app.utils.json_utils import safe_parse_json, extract_json_from_text
from app.services.embedding_service import embed_text, serialise, deserialise, cosine_similarity

PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")


# ─── SAVE ATTEMPT ─────────────────────────────────────────────────────────────

def save_attempt(learner_id: str, section: str, task_type: str,
                 prompt: str, learner_response: str,
                 score_json: dict, feedback: str) -> str:
    """
    Saves a completed practice attempt to the database.
    Returns the attempt_id.

    We convert score_json to a string for storage because SQLite
    stores it as text — we parse it back to a dict when we need it.
    """
    db = SessionLocal()

    try:
        attempt_id = str(uuid.uuid4())[:12]

        attempt = PracticeAttempt(
            attempt_id=attempt_id,
            learner_id=learner_id,
            section=section,
            task_type=task_type,
            prompt=prompt,
            learner_response=learner_response,
            score_json=json.dumps(score_json),
            feedback=feedback
        )

        db.add(attempt)
        db.commit()

        print(f"✅ Attempt saved: {attempt_id}")
        return attempt_id

    except Exception as e:
        db.rollback()
        raise e

    finally:
        db.close()


def get_attempts(learner_id: str, section: str = None) -> list:
    """
    Returns all attempts for a learner, optionally filtered by section.
    Parses score_json back to a dict for each attempt.
    """
    db = SessionLocal()

    try:
        query = db.query(PracticeAttempt).filter(
            PracticeAttempt.learner_id == learner_id
        )

        if section:
            query = query.filter(PracticeAttempt.section == section)

        attempts = query.order_by(PracticeAttempt.created_at.desc()).all()

        return [
            {
                "attempt_id": a.attempt_id,
                "section": a.section,
                "task_type": a.task_type,
                "prompt": a.prompt,
                "learner_response": a.learner_response,
                "scores": json.loads(a.score_json) if a.score_json else {},
                "feedback": a.feedback,
                "created_at": str(a.created_at)
            }
            for a in attempts
        ]

    finally:
        db.close()


# ─── EXTRACT AND SAVE MEMORIES ────────────────────────────────────────────────

def load_prompt_template(filename: str) -> str:
    path = os.path.join(PROMPTS_DIR, filename)
    with open(path, "r") as f:
        return f.read()


def extract_and_save_memories(learner_id: str, section: str,
                               prompt: str, score_result: dict) -> list:
    """
    Sends the evaluation results to Qwen and asks it to extract
    coaching memories. Saves each memory to the database.

    Returns the list of memories that were saved.
    """

    # Build the memory extraction prompt
    template = load_prompt_template("memory_extractor_prompt.txt")

    scores_text = "\n".join([
        f"  {skill.replace('_', ' ').title()}: {score}/5"
        for skill, score in score_result.get("scores", {}).items()
    ])

    full_prompt = template.format(
        section=section,
        prompt=prompt,
        scores=scores_text,
        strengths="\n".join([f"  - {s}" for s in score_result.get("strengths", [])]),
        weaknesses="\n".join([f"  - {w}" for w in score_result.get("weaknesses", [])]),
        overall_feedback=score_result.get("overall_feedback", "")
    )

    # Call Qwen to extract memories
    raw_response = call_qwen_for_json(full_prompt)

    # Parse the response
    try:
        memories = safe_parse_json(raw_response)
    except ValueError:
        try:
            memories = extract_json_from_text(raw_response)
        except ValueError as e:
            print(f"⚠️ Could not extract memories: {e}")
            return []

    # Make sure we got a list
    if not isinstance(memories, list):
        print("⚠️ Memory extraction did not return a list")
        return []

    # Save each memory to the database
    saved_memories = []
    db = SessionLocal()

    try:
        for mem in memories:
            # Validate required fields exist
            if not all(k in mem for k in ["memory_type", "section", "skill", "memory_text"]):
                continue

            memory_id = str(uuid.uuid4())[:12]
            text = mem["memory_text"]
            emb = embed_text(text)  # None on failure — stored as NULL, no crash

            memory = LearnerMemory(
                memory_id=memory_id,
                learner_id=learner_id,
                section=mem["section"],
                skill=mem["skill"],
                memory_type=mem["memory_type"],
                memory_text=text,
                confidence=float(mem.get("confidence", 0.6)),
                evidence_count=1,
                status="active",
                embedding=serialise(emb) if emb else None,
            )

            db.add(memory)
            saved_memories.append(mem)

        db.commit()
        print(f"✅ {len(saved_memories)} memories saved for learner {learner_id}")

    except Exception as e:
        db.rollback()
        print(f"⚠️ Error saving memories: {e}")

    finally:
        db.close()

    return saved_memories


# ─── RETRIEVE MEMORIES ────────────────────────────────────────────────────────

def get_relevant_memories(
    learner_id: str,
    section: str,
    limit: int = 5,
    context: str | None = None,
) -> list:
    """
    Retrieves the most relevant active memories for a learner.

    When `context` is provided (e.g. the current session's target skill
    description or the learner's most recent attempt), memories are ranked
    by a hybrid score combining semantic similarity with spaced repetition:

        score = 0.45 × semantic_similarity + 0.55 × spaced_repetition

    This means memories that are *topically relevant to the current session*
    rise to the top, while the spaced-repetition principle (recent evidence is
    more predictive than old) remains in play.

    Without `context`, the pure spaced-repetition scorer is used:
        score = confidence × recency_weight + weakness_boost

    Spaced-repetition recency weights:
      ≤7 days → 1.0 | ≤30 days → 0.8 | ≤90 days → 0.6 | older → 0.4
    """
    db = SessionLocal()

    try:
        memories = db.query(LearnerMemory).filter(
            LearnerMemory.learner_id == learner_id,
            LearnerMemory.section == section,
            LearnerMemory.status == "active"
        ).all()

        now = datetime.now(timezone.utc)

        def spaced_repetition_score(m) -> float:
            confidence = m.confidence or 0.5
            updated = m.updated_at
            if updated is None:
                days_old = 999
            else:
                if hasattr(updated, "tzinfo") and updated.tzinfo is None:
                    updated = updated.replace(tzinfo=timezone.utc)
                days_old = max(0, (now - updated).days)

            if days_old <= 7:
                recency = 1.0
            elif days_old <= 30:
                recency = 0.8
            elif days_old <= 90:
                recency = 0.6
            else:
                recency = 0.4

            type_boost = 0.05 if m.memory_type == "weakness" else 0.0
            return (confidence * recency) + type_boost

        # Semantic re-ranking when context provided and embeddings exist
        context_emb = None
        if context:
            context_emb = embed_text(context)

        def hybrid_score(m) -> float:
            sr = spaced_repetition_score(m)
            if context_emb and m.embedding:
                mem_emb = deserialise(m.embedding)
                if mem_emb:
                    sem = cosine_similarity(context_emb, mem_emb)
                    # Normalise: cosine is [-1,1] but embeddings are positive → [0,1]
                    return 0.45 * sem + 0.55 * sr
            return sr

        sorted_memories = sorted(memories, key=hybrid_score, reverse=True)

        return [
            {
                "memory_id": m.memory_id,
                "section": m.section,
                "skill": m.skill,
                "memory_type": m.memory_type,
                "memory_text": m.memory_text,
                "confidence": m.confidence,
                "evidence_count": m.evidence_count,
                "status": m.status
            }
            for m in sorted_memories[:limit]
        ]

    finally:
        db.close()


def get_all_memories(learner_id: str) -> dict:
    """
    Returns all memories for a learner grouped by status.
    Used by the Memory Dashboard.
    """
    db = SessionLocal()

    try:
        memories = db.query(LearnerMemory).filter(
            LearnerMemory.learner_id == learner_id
        ).order_by(
            LearnerMemory.confidence.desc()
        ).all()

        active = []
        archived = []

        for m in memories:
            entry = {
                "memory_id": m.memory_id,
                "section": m.section,
                "skill": m.skill,
                "memory_type": m.memory_type,
                "memory_text": m.memory_text,
                "confidence": m.confidence,
                "evidence_count": m.evidence_count,
                "status": m.status,
                "updated_at": str(m.updated_at)
            }
            if m.status == "active":
                active.append(entry)
            else:
                archived.append(entry)

        return {"active": active, "archived": archived}

    finally:
        db.close()


# ─── UPDATE AND FORGET MEMORIES ───────────────────────────────────────────────

def update_memories(learner_id: str, section: str, score_result: dict) -> dict:
    """
    Reviews existing memories against new attempt results and updates them.

    This is what makes the MemoryAgent intelligent over time:
    - Persistent weaknesses gain higher confidence
    - Improving skills lose confidence
    - Mastered skills get archived

    Returns a summary of what changed.
    """
    # Step 1: Get existing active memories
    existing_memories = get_relevant_memories(learner_id, section=section, limit=10)

    # If no memories exist yet there is nothing to update
    if not existing_memories:
        print("No existing memories to update")
        return {"updated": 0, "archived": 0, "strengthened": 0, "weakened": 0}

    # Step 2: Build the update prompt
    template = load_prompt_template("memory_update_prompt.txt")

    # Format existing memories for the prompt
    memory_lines = []
    for mem in existing_memories:
        memory_lines.append(
            f"  memory_id: {mem['memory_id']}\n"
            f"  type: {mem['memory_type']}\n"
            f"  skill: {mem['skill']}\n"
            f"  memory_text: {mem['memory_text']}\n"
            f"  current_confidence: {mem['confidence']}\n"
            f"  evidence_count: {mem['evidence_count']}\n"
        )
    existing_memories_text = "\n---\n".join(memory_lines)

    # Format new scores
    scores_text = "\n".join([
        f"  {skill.replace('_', ' ').title()}: {score}/5"
        for skill, score in score_result.get("scores", {}).items()
    ])

    full_prompt = template.format(
        existing_memories=existing_memories_text,
        section=section,
        new_scores=scores_text,
        new_strengths="\n".join([f"  - {s}" for s in score_result.get("strengths", [])]),
        new_weaknesses="\n".join([f"  - {w}" for w in score_result.get("weaknesses", [])]),
        overall_feedback=score_result.get("overall_feedback", "")
    )

    # Step 3: Call Qwen for update instructions
    raw_response = call_qwen_for_json(full_prompt)

    try:
        updates = safe_parse_json(raw_response)
    except ValueError:
        try:
            updates = extract_json_from_text(raw_response)
        except ValueError as e:
            print(f"⚠️ Could not parse memory update response: {e}")
            return {"updated": 0, "archived": 0, "strengthened": 0, "weakened": 0}

    if not isinstance(updates, list):
        print("⚠️ Memory update response was not a list")
        return {"updated": 0, "archived": 0, "strengthened": 0, "weakened": 0}

    # Step 4: Apply updates to the database
    summary = {"updated": 0, "archived": 0, "strengthened": 0, "weakened": 0}
    db = SessionLocal()

    try:
        for update in updates:
            memory_id = update.get("memory_id")
            action = update.get("action")
            new_confidence = float(update.get("new_confidence", 0.5))

            if not memory_id or not action:
                continue

            # Find the memory in the database
            memory = db.query(LearnerMemory).filter(
                LearnerMemory.memory_id == memory_id
            ).first()

            if not memory:
                continue

            if action == "archive":
                memory.status = "archived"
                memory.confidence = new_confidence
                summary["archived"] += 1
            elif action == "strengthen":
                memory.confidence = min(new_confidence, 0.95)
                memory.evidence_count += 1
                summary["strengthened"] += 1
            elif action == "weaken":
                memory.confidence = max(new_confidence, 0.1)
                memory.evidence_count += 1
                summary["weakened"] += 1
            elif action == "keep":
                # No change needed but we still count it
                pass

            summary["updated"] += 1

        db.commit()
        print(f"✅ Memory update complete: {summary}")

    except Exception as e:
        db.rollback()
        print(f"⚠️ Error applying memory updates: {e}")

    finally:
        db.close()

    return summary


def get_memory_stats(learner_id: str) -> dict:
    """
    Returns a summary of memory statistics for a learner.
    Used by the Memory Dashboard in Phase 10.
    """
    db = SessionLocal()

    try:
        all_memories = db.query(LearnerMemory).filter(
            LearnerMemory.learner_id == learner_id
        ).all()

        active = [m for m in all_memories if m.status == "active"]
        archived = [m for m in all_memories if m.status == "archived"]

        weaknesses = [m for m in active if m.memory_type == "weakness"]
        strengths = [m for m in active if m.memory_type == "strength"]

        return {
            "total_memories": len(all_memories),
            "active_count": len(active),
            "archived_count": len(archived),
            "weakness_count": len(weaknesses),
            "strength_count": len(strengths),
            "avg_confidence": round(
                sum(m.confidence for m in active) / len(active), 2
            ) if active else 0
        }

    finally:
        db.close()


def get_progress_data(learner_id: str, section: str = "Writing") -> dict:
    """
    Pulls together all progress data for a learner in one place.

    Handles both Writing and Reading sections correctly since
    they store scores in different formats.

    Writing scores: individual skill scores out of 5
    Reading scores: skill accuracy percentages stored in score_json
    """
    db = SessionLocal()

    try:
        attempts = db.query(PracticeAttempt).filter(
            PracticeAttempt.learner_id == learner_id,
            PracticeAttempt.section == section
        ).order_by(PracticeAttempt.created_at.asc()).all()

        if not attempts:
            return {
                "total_attempts": 0,
                "attempts": [],
                "skill_trends": {},
                "skill_averages": {},
                "best_skill": None,
                "worst_skill": None,
                "latest_scores": {}
            }

        attempt_data = []
        for i, a in enumerate(attempts):
            raw = json.loads(a.score_json) if a.score_json else {}

            if section == "Writing":
                # Writing stores scores directly in score_json
                actual_scores = raw.get("scores", {})
            elif section == "Reading":
                # Reading stores full attempt result in score_json
                # skill_accuracy contains percentage scores per skill
                skill_accuracy = raw.get("skill_accuracy", {})
                # Convert percentage accuracy to a score out of 5
                # so both sections use the same scale on the dashboard
                actual_scores = {
                    skill: round((acc / 100) * 5, 1)
                    for skill, acc in skill_accuracy.items()
                }
            else:
                actual_scores = raw.get("scores", {})

            attempt_data.append({
                "attempt_number": i + 1,
                "attempt_id": a.attempt_id,
                "scores": actual_scores,
                "feedback": a.feedback,
                "created_at": str(a.created_at),
                # Reading-specific extras
                "total_score": raw.get("total_score"),
                "max_score": raw.get("max_score"),
                "percentage": raw.get("percentage"),
                "passage_title": raw.get("passage_title", "")
            })

        # Build skill keys from all attempts combined
        # (different attempts may test different skills)
        all_skill_keys = set()
        for a in attempt_data:
            all_skill_keys.update(a["scores"].keys())

        # Build skill trends
        skill_trends = {}
        for skill in all_skill_keys:
            skill_trends[skill] = [
                a["scores"].get(skill, 0) for a in attempt_data
            ]

        # Calculate average score per skill
        skill_averages = {}
        for skill in all_skill_keys:
            values = [v for v in skill_trends[skill] if v > 0]
            skill_averages[skill] = round(
                sum(values) / len(values), 2
            ) if values else 0

        # Find best and worst skills
        if skill_averages:
            best_skill = max(skill_averages, key=skill_averages.get)
            worst_skill = min(skill_averages, key=skill_averages.get)
        else:
            best_skill = None
            worst_skill = None

        latest_scores = attempt_data[-1]["scores"] if attempt_data else {}

        return {
            "total_attempts": len(attempt_data),
            "attempts": attempt_data,
            "skill_trends": skill_trends,
            "skill_averages": skill_averages,
            "best_skill": best_skill,
            "worst_skill": worst_skill,
            "latest_scores": latest_scores
        }

    finally:
        db.close()


def extract_reading_memories(learner_id: str, attempt_result: dict) -> list:
    """
    Extracts coaching memories from a completed reading attempt.
    Works the same as extract_and_save_memories but uses the
    reading-specific prompt and formats reading results correctly.
    """
    # Load the reading memory extractor prompt
    path = os.path.join(PROMPTS_DIR, "reading_memory_extractor.txt")
    with open(path, "r") as f:
        template = f.read()

    # Format skill accuracy for the prompt
    skill_accuracy_lines = []
    for skill, accuracy in attempt_result.get("skill_accuracy", {}).items():
        label = skill.replace("_", " ").title()
        skill_accuracy_lines.append(f"  {label}: {accuracy}%")
    skill_accuracy_text = "\n".join(skill_accuracy_lines)

    # Format question summary for the prompt
    question_lines = []
    for q in attempt_result.get("question_results", []):
        status = "✓ Correct" if q["is_correct"] else "✗ Incorrect"
        if q.get("partial_credit"):
            status = "~ Partial"
        question_lines.append(
            f"  {q['question_id'].upper()} [{q['question_type']}] "
            f"[{q['skill']}] — {status} "
            f"({q['score']}/{q['max_score']})"
        )
    question_summary_text = "\n".join(question_lines)

    # Fill the prompt template
    full_prompt = template.format(
        passage_title=attempt_result.get("passage_title", "Unknown"),
        difficulty=attempt_result.get("difficulty", "Unknown"),
        total_score=attempt_result.get("total_score", 0),
        max_score=attempt_result.get("max_score", 0),
        percentage=attempt_result.get("percentage", 0),
        skill_accuracy=skill_accuracy_text,
        question_summary=question_summary_text
    )

    # Call Qwen to extract memories
    raw_response = call_qwen_for_json(full_prompt)

    try:
        memories = safe_parse_json(raw_response)
    except ValueError:
        try:
            memories = extract_json_from_text(raw_response)
        except ValueError as e:
            print(f"Could not extract reading memories: {e}")
            return []

    if not isinstance(memories, list):
        print("Reading memory extraction did not return a list")
        return []

    # Save each memory to the database
    saved_memories = []
    db = SessionLocal()

    try:
        for mem in memories:
            if not all(k in mem for k in ["memory_type", "section", "skill", "memory_text"]):
                continue

            memory_id = str(uuid.uuid4())[:12]
            memory = LearnerMemory(
                memory_id=memory_id,
                learner_id=learner_id,
                section=mem["section"],
                skill=mem["skill"],
                memory_type=mem["memory_type"],
                memory_text=mem["memory_text"],
                confidence=float(mem.get("confidence", 0.6)),
                evidence_count=1,
                status="active"
            )

            db.add(memory)
            saved_memories.append(mem)

        db.commit()
        print(f"Saved {len(saved_memories)} reading memories for {learner_id}")

    except Exception as e:
        db.rollback()
        print(f"Error saving reading memories: {e}")

    finally:
        db.close()

    return saved_memories


def save_reading_attempt(learner_id: str, attempt_result: dict) -> str:
    """
    Saves a completed reading attempt to the practice_attempts table.
    Returns the attempt_id.
    """
    db = SessionLocal()

    try:
        attempt_id = str(uuid.uuid4())[:12]

        attempt = PracticeAttempt(
            attempt_id=attempt_id,
            learner_id=learner_id,
            section="Reading",
            task_type=attempt_result.get("difficulty", "").title(),
            prompt=attempt_result.get("passage_title", ""),
            learner_response=f"Completed {attempt_result.get('max_score', 0)} question reading attempt",
            score_json=json.dumps(attempt_result),
            feedback=(
                f"Score: {attempt_result.get('total_score', 0)} / "
                f"{attempt_result.get('max_score', 0)} "
                f"({attempt_result.get('percentage', 0)}%)"
            )
        )

        db.add(attempt)
        db.commit()
        print(f"Reading attempt saved: {attempt_id}")
        return attempt_id

    except Exception as e:
        db.rollback()
        raise e

    finally:
        db.close()


def extract_speaking_memories(learner_id: str, attempt_result: dict) -> list:
    """
    Extracts coaching memories from a completed speaking attempt.
    Uses the speaking-specific memory extractor prompt and formats
    speaking evaluation results correctly for memory extraction.
    """
    # Load the speaking memory extractor prompt
    path = os.path.join(PROMPTS_DIR, "speaking_memory_extractor.txt")
    with open(path, "r") as f:
        template = f.read()

    scores = attempt_result.get("scores", {})

    # Format strengths and weaknesses for the prompt
    strengths_text = "\n".join([
        f"  - {s}" for s in scores.get("strengths", [])
    ])
    weaknesses_text = "\n".join([
        f"  - {w}" for w in scores.get("weaknesses", [])
    ])

    full_prompt = template.format(
        topic=attempt_result.get("topic", "Unknown"),
        overall_band=scores.get("overall_band", "?"),
        fluency_coherence=scores.get("fluency_coherence", "?"),
        lexical_resource=scores.get("lexical_resource", "?"),
        grammatical_range=scores.get("grammatical_range", "?"),
        pronunciation_clarity=scores.get("pronunciation_clarity", "?"),
        strengths=strengths_text if strengths_text else "  None noted",
        weaknesses=weaknesses_text if weaknesses_text else "  None noted",
        part1_comment=scores.get("part1_comment", "No comment"),
        part2_comment=scores.get("part2_comment", "No comment"),
        part3_comment=scores.get("part3_comment", "No comment")
    )

    # Call Qwen to extract memories
    raw_response = call_qwen_for_json(full_prompt)

    try:
        memories = safe_parse_json(raw_response)
    except ValueError:
        try:
            memories = extract_json_from_text(raw_response)
        except ValueError as e:
            print(f"Could not extract speaking memories: {e}")
            return []

    if not isinstance(memories, list):
        print("Speaking memory extraction did not return a list")
        return []

    # Save each memory to the database
    saved_memories = []
    db = SessionLocal()

    try:
        for mem in memories:
            if not all(k in mem for k in [
                "memory_type", "section", "skill", "memory_text"
            ]):
                continue

            memory_id = str(uuid.uuid4())[:12]
            memory = LearnerMemory(
                memory_id=memory_id,
                learner_id=learner_id,
                section=mem["section"],
                skill=mem["skill"],
                memory_type=mem["memory_type"],
                memory_text=mem["memory_text"],
                confidence=float(mem.get("confidence", 0.6)),
                evidence_count=1,
                status="active"
            )

            db.add(memory)
            saved_memories.append(mem)

        db.commit()
        print(
            f"Saved {len(saved_memories)} speaking memories "
            f"for learner {learner_id}"
        )

    except Exception as e:
        db.rollback()
        print(f"Error saving speaking memories: {e}")

    finally:
        db.close()

    return saved_memories


def save_speaking_attempt(learner_id: str, attempt_result: dict) -> str:
    """
    Saves a completed speaking attempt to the practice_attempts table.
    Returns the attempt_id.

    Speaking attempts store the full evaluation result in score_json
    including band scores, feedback text and part comments.
    """
    db = SessionLocal()

    try:
        attempt_id = str(uuid.uuid4())[:12]

        scores = attempt_result.get("scores", {})
        overall_band = scores.get("overall_band", "?")

        attempt = PracticeAttempt(
            attempt_id=attempt_id,
            learner_id=learner_id,
            section="Speaking",
            task_type=attempt_result.get("difficulty", "").title(),
            prompt=attempt_result.get("topic", "Speaking Practice"),
            learner_response=(
                f"Completed 3-part speaking session on: "
                f"{attempt_result.get('topic', 'Unknown topic')}"
            ),
            score_json=json.dumps({
                "scores": scores,
                "feedback_text": attempt_result.get("feedback_text", ""),
                "topic": attempt_result.get("topic", ""),
                "difficulty": attempt_result.get("difficulty", ""),
                "overall_band": overall_band
            }),
            feedback=(
                f"Overall Band: {overall_band} | "
                f"Fluency: {scores.get('fluency_coherence', '?')}/9 | "
                f"Lexical: {scores.get('lexical_resource', '?')}/9 | "
                f"Grammar: {scores.get('grammatical_range', '?')}/9 | "
                f"Pronunciation: {scores.get('pronunciation_clarity', '?')}/9"
            )
        )

        db.add(attempt)
        db.commit()
        print(f"Speaking attempt saved: {attempt_id}")
        return attempt_id

    except Exception as e:
        db.rollback()
        raise e

    finally:
        db.close()


def get_speaking_progress_data(learner_id: str) -> dict:
    """
    Pulls together speaking progress data for the dashboard.

    Speaking uses band scores out of 9 rather than skill scores
    out of 5 like Writing and Reading.
    """
    db = SessionLocal()

    try:
        attempts = db.query(PracticeAttempt).filter(
            PracticeAttempt.learner_id == learner_id,
            PracticeAttempt.section == "Speaking"
        ).order_by(PracticeAttempt.created_at.asc()).all()

        if not attempts:
            return {
                "total_attempts": 0,
                "attempts": [],
                "band_trends": {},
                "latest_scores": {},
                "best_criterion": None,
                "worst_criterion": None
            }

        attempt_data = []
        for i, a in enumerate(attempts):
            raw = json.loads(a.score_json) if a.score_json else {}
            scores = raw.get("scores", {})

            attempt_data.append({
                "attempt_number": i + 1,
                "attempt_id": a.attempt_id,
                "topic": raw.get("topic", "Unknown"),
                "difficulty": raw.get("difficulty", ""),
                "overall_band": scores.get("overall_band", 0),
                "fluency_coherence": scores.get("fluency_coherence", 0),
                "lexical_resource": scores.get("lexical_resource", 0),
                "grammatical_range": scores.get("grammatical_range", 0),
                "pronunciation_clarity": scores.get("pronunciation_clarity", 0),
                "feedback": a.feedback,
                "created_at": str(a.created_at)
            })

        # Build band score trends
        criteria = [
            "fluency_coherence",
            "lexical_resource",
            "grammatical_range",
            "pronunciation_clarity"
        ]

        band_trends = {}
        for criterion in criteria:
            band_trends[criterion] = [
                a[criterion] for a in attempt_data
            ]

        # Overall band trend
        band_trends["overall_band"] = [
            a["overall_band"] for a in attempt_data
        ]

        # Calculate averages
        criterion_averages = {}
        for criterion in criteria:
            values = [
                v for v in band_trends[criterion] if v and v > 0
            ]
            criterion_averages[criterion] = round(
                sum(values) / len(values), 1
            ) if values else 0

        # Best and worst criteria
        if criterion_averages:
            best = max(criterion_averages, key=criterion_averages.get)
            worst = min(criterion_averages, key=criterion_averages.get)
        else:
            best = None
            worst = None

        latest = attempt_data[-1] if attempt_data else {}

        return {
            "total_attempts": len(attempt_data),
            "attempts": attempt_data,
            "band_trends": band_trends,
            "criterion_averages": criterion_averages,
            "latest_scores": latest,
            "best_criterion": best,
            "worst_criterion": worst
        }

    finally:
        db.close()


def extract_listening_memories(learner_id: str, attempt_result: dict) -> list:
    """
    Extracts coaching memories from a completed listening attempt.
    Uses the listening-specific memory extractor prompt and formats
    listening results correctly for memory extraction.
    """
    path = os.path.join(PROMPTS_DIR, "listening_memory_extractor.txt")
    with open(path, "r") as f:
        template = f.read()

    # Format skill accuracy for the prompt
    skill_accuracy_lines = []
    for skill, accuracy in attempt_result.get("skill_accuracy", {}).items():
        label = skill.replace("_", " ").title()
        skill_accuracy_lines.append(f"  {label}: {accuracy}%")
    skill_accuracy_text = "\n".join(skill_accuracy_lines)

    # Format question summary for the prompt
    question_lines = []
    for q in attempt_result.get("question_results", []):
        status = "Correct" if q["is_correct"] else "Incorrect"
        question_lines.append(
            f"  {q['question_id'].upper()} "
            f"[{q['question_type']}] "
            f"[{q['skill']}] — {status} "
            f"({q['score']}/{q['max_score']})"
        )
    question_summary_text = "\n".join(question_lines)

    full_prompt = template.format(
        track_title=attempt_result.get("track_title", "Unknown"),
        part=attempt_result.get("part", "Unknown"),
        difficulty=attempt_result.get("difficulty", "Unknown"),
        total_score=attempt_result.get("total_score", 0),
        max_score=attempt_result.get("max_score", 0),
        percentage=attempt_result.get("percentage", 0),
        skill_accuracy=skill_accuracy_text,
        question_summary=question_summary_text
    )

    raw_response = call_qwen_for_json(full_prompt)

    try:
        memories = safe_parse_json(raw_response)
    except ValueError:
        try:
            memories = extract_json_from_text(raw_response)
        except ValueError as e:
            print(f"Could not extract listening memories: {e}")
            return []

    if not isinstance(memories, list):
        print("Listening memory extraction did not return a list")
        return []

    saved_memories = []
    db = SessionLocal()

    try:
        for mem in memories:
            if not all(k in mem for k in [
                "memory_type", "section", "skill", "memory_text"
            ]):
                continue

            memory_id = str(uuid.uuid4())[:12]
            memory = LearnerMemory(
                memory_id=memory_id,
                learner_id=learner_id,
                section=mem["section"],
                skill=mem["skill"],
                memory_type=mem["memory_type"],
                memory_text=mem["memory_text"],
                confidence=float(mem.get("confidence", 0.6)),
                evidence_count=1,
                status="active"
            )

            db.add(memory)
            saved_memories.append(mem)

        db.commit()
        print(
            f"Saved {len(saved_memories)} listening memories "
            f"for learner {learner_id}"
        )

    except Exception as e:
        db.rollback()
        print(f"Error saving listening memories: {e}")

    finally:
        db.close()

    return saved_memories


def save_listening_attempt(learner_id: str, attempt_result: dict) -> str:
    """
    Saves a completed listening attempt to the practice_attempts table.
    Returns the attempt_id.
    """
    db = SessionLocal()

    try:
        attempt_id = str(uuid.uuid4())[:12]

        attempt = PracticeAttempt(
            attempt_id=attempt_id,
            learner_id=learner_id,
            section="Listening",
            task_type=f"Part {attempt_result.get('part', '?')}",
            prompt=attempt_result.get("track_title", "Listening Practice"),
            learner_response=(
                f"Completed Part {attempt_result.get('part', '?')} "
                f"listening attempt: "
                f"{attempt_result.get('track_title', 'Unknown')}"
            ),
            score_json=json.dumps(attempt_result),
            feedback=(
                f"Score: {attempt_result.get('total_score', 0)} / "
                f"{attempt_result.get('max_score', 0)} "
                f"({attempt_result.get('percentage', 0)}%)"
            )
        )

        db.add(attempt)
        db.commit()
        print(f"Listening attempt saved: {attempt_id}")
        return attempt_id

    except Exception as e:
        db.rollback()
        raise e

    finally:
        db.close()


def get_listening_progress_data(learner_id: str) -> dict:
    """
    Pulls together listening progress data for the dashboard.
    Returns attempt history and skill accuracy trends over time.
    """
    db = SessionLocal()

    try:
        attempts = db.query(PracticeAttempt).filter(
            PracticeAttempt.learner_id == learner_id,
            PracticeAttempt.section == "Listening"
        ).order_by(PracticeAttempt.created_at.asc()).all()

        if not attempts:
            return {
                "total_attempts": 0,
                "attempts": [],
                "skill_trends": {},
                "skill_averages": {},
                "best_skill": None,
                "worst_skill": None
            }

        attempt_data = []
        for i, a in enumerate(attempts):
            raw = json.loads(a.score_json) if a.score_json else {}
            skill_accuracy = raw.get("skill_accuracy", {})

            attempt_data.append({
                "attempt_number": i + 1,
                "attempt_id": a.attempt_id,
                "track_title": raw.get("track_title", "Unknown"),
                "part": raw.get("part", "?"),
                "difficulty": raw.get("difficulty", ""),
                "total_score": raw.get("total_score", 0),
                "max_score": raw.get("max_score", 0),
                "percentage": raw.get("percentage", 0),
                "skill_accuracy": skill_accuracy,
                "feedback": a.feedback,
                "created_at": str(a.created_at)
            })

        # Build skill trends across attempts
        all_skills = set()
        for a in attempt_data:
            all_skills.update(a["skill_accuracy"].keys())

        skill_trends = {}
        for skill in all_skills:
            skill_trends[skill] = [
                a["skill_accuracy"].get(skill, 0)
                for a in attempt_data
            ]

        # Calculate averages
        skill_averages = {}
        for skill in all_skills:
            values = [
                v for v in skill_trends[skill] if v > 0
            ]
            skill_averages[skill] = round(
                sum(values) / len(values), 1
            ) if values else 0

        # Overall percentage trend
        skill_trends["overall"] = [
            a["percentage"] for a in attempt_data
        ]

        best_skill = max(
            skill_averages, key=skill_averages.get
        ) if skill_averages else None
        worst_skill = min(
            skill_averages, key=skill_averages.get
        ) if skill_averages else None

        return {
            "total_attempts": len(attempt_data),
            "attempts": attempt_data,
            "skill_trends": skill_trends,
            "skill_averages": skill_averages,
            "best_skill": best_skill,
            "worst_skill": worst_skill
        }

    finally:
        db.close()


# ─── CHAT COACH MEMORY EXTRACTION ─────────────────────────────────────────────

def extract_chat_memories(learner_id: str, section: str,
                          conversation_history: list) -> list:
    """
    Extracts coaching memories from a Chat Coach drilling session.

    Unlike practice-based memory extraction (which uses scores and
    feedback), this extracts observations from the tutor's interaction
    with the learner — capturing understanding gaps, breakthroughs,
    and drill performance that only surface in conversation.

    These micro-memories complete the agent loop: the tutor teaches,
    observes the learner's responses during drills, and records what
    it learned back into the memory system for future sessions.
    """
    # Build a condensed transcript of the conversation
    transcript_lines = []
    for msg in conversation_history[-10:]:  # Last 10 exchanges max
        role = "Tutor" if msg["role"] == "assistant" else "Learner"
        content = msg["content"][:500]  # Truncate long messages
        transcript_lines.append(f"{role}: {content}")
    transcript = "\n\n".join(transcript_lines)

    prompt = f"""You are a coaching memory extractor for an IELTS {section} tutoring session.

Below is a conversation between a specialist {section} tutor and a learner.
The tutor was drilling the learner on specific skills.

Extract 1-3 coaching observations that should be remembered for future sessions.
Focus on what the LEARNER demonstrated during drilling:
- Did they grasp the concept? Partially? Not at all?
- Did they make specific types of errors during drills?
- Did they show unexpected strengths?
- What should the next session focus on?

Return a JSON array. Each item must have:
- "memory_type": "weakness" or "strength"
- "section": "{section}"
- "skill": a short label for the skill area (e.g. "cohesive devices", "inference skills")
- "memory_text": a specific, evidence-based observation (1-2 sentences)
- "confidence": 0.5 to 0.7 (these are initial observations from drilling, not scored practice)

Return ONLY the JSON array, no other text.

CONVERSATION:
{transcript}"""

    raw_response = call_qwen_for_json(prompt)

    try:
        memories = safe_parse_json(raw_response)
    except ValueError:
        try:
            memories = extract_json_from_text(raw_response)
        except ValueError as e:
            print(f"Could not extract chat memories: {e}")
            return []

    if not isinstance(memories, list):
        print("Chat memory extraction did not return a list")
        return []

    saved_memories = []
    db = SessionLocal()

    try:
        for mem in memories:
            if not all(k in mem for k in [
                "memory_type", "section", "skill", "memory_text"
            ]):
                continue

            memory_id = str(uuid.uuid4())[:12]
            memory = LearnerMemory(
                memory_id=memory_id,
                learner_id=learner_id,
                section=mem["section"],
                skill=mem["skill"],
                memory_type=mem["memory_type"],
                memory_text=mem["memory_text"],
                confidence=float(mem.get("confidence", 0.55)),
                evidence_count=1,
                status="active"
            )
            db.add(memory)
            saved_memories.append(mem)

        db.commit()
        print(
            f"✅ Saved {len(saved_memories)} chat memories "
            f"for learner {learner_id} ({section})"
        )
    except Exception as e:
        db.rollback()
        print(f"⚠️ Error saving chat memories: {e}")
    finally:
        db.close()

    return saved_memories


# ─── SKILL RANKING SYSTEM ─────────────────────────────────────────────────────

from app.db.models import LearnerSkillRank
from app.services.skill_taxonomy_service import (
    get_all_skill_ids,
    get_skill_by_id,
    get_rank_name,
    get_skills_flat,
    get_band_estimate,
    format_band,
    get_band_label
)

RANK_UP_THRESHOLD = 3  # consecutive clean attempts needed to rank up
MAX_RANK = 5
MIN_RANK = 1


def get_skill_rank(learner_id: str, section: str, skill_id: str) -> dict:
    """
    Returns the learner's current rank record for one skill.

    If no record exists yet, returns a default starting state
    (rank 1, no evidence) WITHOUT creating a database row —
    the row is only created on the first actual classification.
    """
    db = SessionLocal()

    try:
        record = db.query(LearnerSkillRank).filter(
            LearnerSkillRank.learner_id == learner_id,
            LearnerSkillRank.section == section,
            LearnerSkillRank.skill_id == skill_id
        ).first()

        if record is None:
            return {
                "skill_id": skill_id,
                "current_rank": 1,
                "clean_streak": 0,
                "total_evidence": 0,
                "last_classification": None,
                "exists": False,
                "band": None,
                "band_display": "No band yet",
                "band_label": "Complete a practice session to see your band"
            }

        band = get_band_estimate(
            current_rank=record.current_rank,
            clean_streak=record.clean_streak,
            total_evidence=record.total_evidence
        )
        return {
            "skill_id": record.skill_id,
            "current_rank": record.current_rank,
            "clean_streak": record.clean_streak,
            "total_evidence": record.total_evidence,
            "last_classification": record.last_classification,
            "exists": True,
            "band": band,
            "band_display": format_band(band),
            "band_label": get_band_label(band)
        }

    finally:
        db.close()


def get_all_skill_ranks(learner_id: str, section: str = "Writing") -> list:
    """
    Returns the learner's rank record for EVERY skill in the
    taxonomy, including skills that have never been assessed yet
    (which default to rank 1 with no evidence).

    This is what powers "find the weakest skill" and the skill
    dashboard — it always returns the full taxonomy, not just
    skills with existing database rows.
    """
    all_skills = get_skills_flat(section)
    results = []

    for skill in all_skills:
        rank_data = get_skill_rank(
            learner_id, section, skill["skill_id"]
        )
        band = get_band_estimate(
            current_rank=rank_data["current_rank"],
            clean_streak=rank_data["clean_streak"],
            total_evidence=rank_data["total_evidence"]
        )
        results.append({
            **rank_data,
            "skill_name": skill["skill_name"],
            "category_name": skill["category_name"],
            "rank_name": get_rank_name(rank_data["current_rank"]),
            "band": band,
            "band_display": format_band(band),
            "band_label": get_band_label(band)
        })

    return results


def apply_skill_classification(
    learner_id: str,
    section: str,
    skill_id: str,
    classification: str
) -> dict:
    """
    Applies ONE skill classification from a single attempt to the
    learner's rank record. This is the rule engine — deterministic,
    no AI judgement happens here, only counting.

    classification must be one of:
      "demonstrated_strength"  -> clean_streak += 1
      "demonstrated_weakness"  -> clean_streak = 0
      "not_applicable"         -> no change at all, not even evidence count

    Rank increases by 1 when clean_streak reaches RANK_UP_THRESHOLD,
    then clean_streak resets to 0. Rank never decreases automatically.
    Rank is capped at MAX_RANK.

    Returns a dict describing what happened, including whether a
    rank-up occurred — used by the page to show a celebration message.
    """
    if classification not in (
        "demonstrated_strength",
        "demonstrated_weakness",
        "not_applicable"
    ):
        raise ValueError(f"Invalid classification: {classification}")

    # not_applicable means this skill was not relevant to this prompt
    # We do not touch the record at all -- no evidence, no streak change
    if classification == "not_applicable":
        return {
            "skill_id": skill_id,
            "changed": False,
            "ranked_up": False,
            "current_rank": None,
            "clean_streak": None
        }

    db = SessionLocal()

    try:
        record = db.query(LearnerSkillRank).filter(
            LearnerSkillRank.learner_id == learner_id,
            LearnerSkillRank.section == section,
            LearnerSkillRank.skill_id == skill_id
        ).first()

        if record is None:
            # First time this skill has ever been assessed for this learner
            record = LearnerSkillRank(
                rank_id=str(uuid.uuid4())[:12],
                learner_id=learner_id,
                section=section,
                skill_id=skill_id,
                current_rank=1,
                clean_streak=0,
                total_evidence=0,
                last_classification=None
            )
            db.add(record)

        ranked_up = False

        record.total_evidence += 1
        record.last_classification = classification

        if classification == "demonstrated_strength":
            record.clean_streak += 1
            if (record.clean_streak >= RANK_UP_THRESHOLD
                    and record.current_rank < MAX_RANK):
                record.current_rank += 1
                record.clean_streak = 0
                ranked_up = True

        elif classification == "demonstrated_weakness":
            record.clean_streak = 0

        db.commit()

        return {
            "skill_id": skill_id,
            "changed": True,
            "ranked_up": ranked_up,
            "current_rank": record.current_rank,
            "clean_streak": record.clean_streak
        }

    except Exception as e:
        db.rollback()
        raise e

    finally:
        db.close()


def apply_skill_classifications_batch(
    learner_id: str,
    section: str,
    classifications: dict
) -> list:
    """
    Applies a full set of skill classifications from one attempt
    (one Writing essay typically touches multiple skills at once).

    classifications is a dict like:
      {
        "tr_full_coverage": "demonstrated_strength",
        "tr_conclusion_synthesis": "demonstrated_weakness",
        "gra_punctuation": "not_applicable",
        ...
      }

    Returns a list of result dicts, one per skill, in the same
    shape as apply_skill_classification. Skills with a "changed"
    result are the ones the page should report on.
    """
    results = []
    for skill_id, classification in classifications.items():
        result = apply_skill_classification(
            learner_id=learner_id,
            section=section,
            skill_id=skill_id,
            classification=classification
        )
        results.append(result)
    return results


def get_weakest_skill(learner_id: str, section: str = "Writing") -> dict | None:
    """
    Finds the single skill most in need of attention.

    Priority order:
    1. Lowest current_rank first (rank 1 skills beat rank 3 skills)
    2. Among skills tied on rank, the one with the LOWEST
       total_evidence is prioritised (we know least about it,
       or it has never been assessed -- worth surfacing)
    3. Among skills tied on both, the one with the most recent
       "demonstrated_weakness" classification is prioritised

    Returns None only if the taxonomy itself is empty (should
    never happen in practice).
    """
    all_ranks = get_all_skill_ranks(learner_id, section)

    if not all_ranks:
        return None

    def sort_key(skill):
        # Lower rank = higher priority (sorts first)
        # Lower evidence = higher priority (sorts first)
        # weakness more recent = higher priority -> use 0 if weakness, 1 otherwise
        weakness_priority = (
            0 if skill["last_classification"] == "demonstrated_weakness"
            else 1
        )
        return (
            skill["current_rank"],
            skill["total_evidence"],
            weakness_priority
        )

    sorted_skills = sorted(all_ranks, key=sort_key)
    return sorted_skills[0]


def get_skill_progress_summary(learner_id: str, section: str = "Writing") -> dict:
    """
    Returns a summary of the learner's overall skill progress —
    used by both the Progress Dashboard and the future coaching
    hub to show "how far along is this learner overall".
    """
    all_ranks = get_all_skill_ranks(learner_id, section)

    if not all_ranks:
        return {
            "total_skills": 0,
            "average_rank": 0,
            "skills_at_max": 0,
            "skills_untouched": 0,
            "weakest_skill": None
        }

    total = len(all_ranks)
    avg_rank = round(
        sum(s["current_rank"] for s in all_ranks) / total, 2
    )
    at_max = len([s for s in all_ranks if s["current_rank"] == MAX_RANK])
    untouched = len([s for s in all_ranks if s["total_evidence"] == 0])

    weakest = get_weakest_skill(learner_id, section)

    return {
        "total_skills": total,
        "average_rank": avg_rank,
        "skills_at_max": at_max,
        "skills_untouched": untouched,
        "weakest_skill": weakest
    }


# ─── CHAT COACH CONTEXT BUILDER ────────────────────────────────────────────────

def find_evidence_memory_for_skill(
    learner_id: str,
    skill_id: str,
    section: str = "Writing"
) -> dict | None:
    """
    Finds the single most relevant existing memory that gives
    concrete evidence of a learner's standing on a given skill_id.

    Searches learner_memories using the label bridge in
    skill_taxonomy_service, prioritising:
      1. Active weaknesses (most useful for "here's what to fix")
      2. Most recent if multiple match

    Returns None if no matching memory exists yet -- this is
    expected for a learner who hasn't been assessed on this skill.

    BUG FIX: Previously hardcoded to section="Writing", now
    accepts section parameter so Chat Coach works for all sections.
    """
    from app.services.skill_taxonomy_service import get_memory_labels_for_skill

    labels = get_memory_labels_for_skill(skill_id)
    if not labels:
        return None

    db = SessionLocal()

    try:
        # Prefer an active weakness first
        memory = db.query(LearnerMemory).filter(
            LearnerMemory.learner_id == learner_id,
            LearnerMemory.section == section,
            LearnerMemory.skill.in_(labels),
            LearnerMemory.memory_type == "weakness",
            LearnerMemory.status == "active"
        ).order_by(
            LearnerMemory.updated_at.desc()
        ).first()

        # Fall back to any memory on this skill, regardless of type/status
        # -- better to show something true than nothing at all
        if memory is None:
            memory = db.query(LearnerMemory).filter(
                LearnerMemory.learner_id == learner_id,
                LearnerMemory.section == section,
                LearnerMemory.skill.in_(labels)
            ).order_by(
                LearnerMemory.updated_at.desc()
            ).first()

        if memory is None:
            return None

        return {
            "memory_text": memory.memory_text,
            "memory_type": memory.memory_type,
            "skill_label": memory.skill,
            "status": memory.status
        }

    finally:
        db.close()


def find_recent_essay_excerpt(learner_id: str, section: str = "Writing") -> dict | None:
    """
    Returns the learner's most recent essay attempt -- prompt and
    full response text -- so the Chat Coach can reference their
    actual writing directly, not just a memory summary.

    Returns None if the learner has no attempts yet.
    """
    db = SessionLocal()

    try:
        attempt = db.query(PracticeAttempt).filter(
            PracticeAttempt.learner_id == learner_id,
            PracticeAttempt.section == section
        ).order_by(
            PracticeAttempt.created_at.desc()
        ).first()

        if attempt is None:
            return None

        return {
            "prompt": attempt.prompt,
            "essay": attempt.learner_response,
            "created_at": str(attempt.created_at)
        }

    finally:
        db.close()


def build_chat_coach_context(learner_id: str, section: str = "Writing") -> dict:
    """
    Assembles everything the Chat Coach needs to open a session
    intelligently. This is the single entry point the Chat Coach
    page/service calls before generating its first message.

    Returns one of two shapes:

    NEW LEARNER (no skill evidence at all):
      {
        "has_history": False
      }

    RETURNING LEARNER:
      {
        "has_history": True,
        "weakest_skill": {... from get_weakest_skill() ...},
        "skill_definition": {... from get_skill_by_id() ...},
        "current_rank_text": "the rank 1 definition for this skill",
        "next_rank_text": "the rank 2 definition for this skill",
        "evidence_memory": {... from find_evidence_memory_for_skill()
                             or None ...},
        "recent_essay": {... from find_recent_essay_excerpt()
                          or None ...}
      }

    "has_history" is False specifically when the weakest skill has
    zero total_evidence AND there is no fallback memory evidence
    either -- meaning this learner has genuinely never been
    assessed on anything yet. This matches the locked design
    decision: brand new learners get a general welcome, not a
    forced skill focus.
    """
    from app.services.skill_taxonomy_service import (
        get_skill_by_id,
        get_rank_definition
    )

    weakest = get_weakest_skill(learner_id, section)

    evidence = None
    if weakest is not None:
        evidence = find_evidence_memory_for_skill(
            learner_id, weakest["skill_id"], section
        )

    # No history at all: the weakest skill has never been assessed
    # AND there's no memory evidence to fall back on either
    no_evidence_at_all = (
        weakest is None
        or (weakest["total_evidence"] == 0 and evidence is None)
    )

    if no_evidence_at_all:
        return {"has_history": False}

    skill_definition = get_skill_by_id(weakest["skill_id"], section)
    current_rank = weakest["current_rank"]
    next_rank = min(current_rank + 1, 5)

    current_rank_text = get_rank_definition(
        weakest["skill_id"], current_rank, section
    )
    next_rank_text = get_rank_definition(
        weakest["skill_id"], next_rank, section
    )

    recent_essay = find_recent_essay_excerpt(learner_id, section)

    return {
        "has_history": True,
        "weakest_skill": weakest,
        "skill_definition": skill_definition,
        "current_rank_text": current_rank_text,
        "next_rank_text": next_rank_text,
        "evidence_memory": evidence,
        "recent_essay": recent_essay
    }
