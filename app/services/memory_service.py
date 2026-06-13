import os
import sys
import uuid
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.db.database import SessionLocal
from app.db.models import PracticeAttempt, LearnerMemory, MasteryScore
from app.services.qwen_service import call_qwen_for_json
from app.utils.json_utils import safe_parse_json, extract_json_from_text

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
        print(f"✅ {len(saved_memories)} memories saved for learner {learner_id}")

    except Exception as e:
        db.rollback()
        print(f"⚠️ Error saving memories: {e}")

    finally:
        db.close()

    return saved_memories


# ─── RETRIEVE MEMORIES ────────────────────────────────────────────────────────

def get_relevant_memories(learner_id: str, section: str, limit: int = 5) -> list:
    """
    Retrieves the most relevant active memories for a learner.
    Ordered by confidence so the strongest memories come first.

    This is what gets shown to the learner at the start of each session
    and passed to Qwen as context when scoring.
    """
    db = SessionLocal()

    try:
        memories = db.query(LearnerMemory).filter(
            LearnerMemory.learner_id == learner_id,
            LearnerMemory.section == section,
            LearnerMemory.status == "active"
        ).order_by(
            LearnerMemory.confidence.desc()
        ).limit(limit).all()

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
            for m in memories
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
    Used by the Progress Dashboard.

    Returns:
    - List of attempts with scores over time
    - Best and worst scoring skills
    - Score trend per skill across attempts
    - Total attempts count
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
                "best_skill": None,
                "worst_skill": None,
                "latest_scores": {}
            }

        # Parse scores from each attempt
        attempt_data = []
        for i, a in enumerate(attempts):
            scores = json.loads(a.score_json) if a.score_json else {}
            actual_scores = scores.get("scores", {})
            attempt_data.append({
                "attempt_number": i + 1,
                "attempt_id": a.attempt_id,
                "scores": actual_scores,
                "feedback": a.feedback,
                "created_at": str(a.created_at)
            })

        # Build skill trends — one list of scores per skill across all attempts
        skill_keys = [
            "thesis_clarity", "organization",
            "grammar", "vocabulary", "idea_development"
        ]

        skill_trends = {}
        for skill in skill_keys:
            skill_trends[skill] = [
                a["scores"].get(skill, 0) for a in attempt_data
            ]

        # Calculate average score per skill across all attempts
        skill_averages = {}
        for skill in skill_keys:
            values = [v for v in skill_trends[skill] if v > 0]
            skill_averages[skill] = round(sum(values) / len(values), 2) if values else 0

        # Find best and worst skills
        if skill_averages:
            best_skill = max(skill_averages, key=skill_averages.get)
            worst_skill = min(skill_averages, key=skill_averages.get)
        else:
            best_skill = None
            worst_skill = None

        # Get latest scores for the summary metrics
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
    