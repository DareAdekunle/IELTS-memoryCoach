"""
app/mcp/memory_server.py — IELTS MemoryCoach MCP Server

Exposes the MemoryCoach learner memory and skill ranking system
as an MCP (Model Context Protocol) server.

This means any MCP-compatible AI agent — Claude, a Qwen agent,
a school's tutoring bot, or a custom dashboard — can query a
learner's coaching history without direct database access.

Tools exposed:
  get_learner_weaknesses    — active weakness memories for a learner
  get_learner_strengths     — active strength memories for a learner
  get_skill_ranks           — all 13 writing skill rank levels
  get_weakest_skill         — single weakest skill for targeting
  get_recent_attempts       — recent attempt history by section
  get_memory_stats          — memory profile statistics
  get_coaching_context      — full context bundle for AI tutoring agents

Usage:
  Run standalone:
    python app/mcp/memory_server.py

  Or mount into FastAPI (see api/main.py):
    from app.mcp.memory_server import mcp
    app.mount("/mcp", mcp.get_asgi_app())
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from fastmcp import FastMCP
from app.db.database import SessionLocal
from app.db.models import LearnerMemory, PracticeAttempt, LearnerSkillRank
from app.services.memory_service import (
    get_relevant_memories,
    get_all_memories,
    get_memory_stats,
    get_weakest_skill,
    get_all_skill_ranks,
    get_skill_progress_summary
)
from app.services.skill_taxonomy_service import get_skill_by_id, get_rank_name

# ─── MCP Server definition ────────────────────────────────────────────────────

mcp = FastMCP(
    name="IELTS MemoryCoach",
    instructions=(
        "This server exposes learner coaching data from IELTS MemoryCoach. "
        "Use it to query a learner's weaknesses, skill ranks, and recent "
        "attempts to personalise tutoring, generate targeted practice, "
        "or build progress reports. All tools require a learner_id. "
        "Learner IDs can be found via the /progress/profile API endpoint."
    )
)


# ─── Tool 1: Get learner weaknesses ───────────────────────────────────────────

@mcp.tool()
def get_learner_weaknesses(
    learner_id: str,
    section: str = "Writing",
    limit: int = 5
) -> dict:
    """
    Returns the most relevant active weakness memories for a learner
    in a given IELTS section.

    These are specific, evidence-based observations extracted by the
    AI coach after each practice attempt — not generic feedback.

    Args:
        learner_id: The learner's unique ID
        section:    IELTS section — Writing, Reading, Speaking, Listening
        limit:      Maximum number of memories to return (default 5)

    Returns:
        A dict with 'weaknesses' list, each containing:
        - skill: the skill area (e.g. "Thesis Clarity")
        - memory_text: specific observation about the learner
        - confidence: how confident the coach is (0.0-1.0)
        - evidence_count: how many attempts support this memory
    """
    memories = get_relevant_memories(
        learner_id=learner_id,
        section=section,
        limit=limit
    )

    weaknesses = [
        {
            "skill": m["skill"],
            "memory_text": m["memory_text"],
            "confidence": m["confidence"],
            "evidence_count": m["evidence_count"]
        }
        for m in memories
        if m["memory_type"] == "weakness"
    ]

    return {
        "learner_id": learner_id,
        "section": section,
        "weaknesses": weaknesses,
        "count": len(weaknesses)
    }


# ─── Tool 2: Get learner strengths ────────────────────────────────────────────

@mcp.tool()
def get_learner_strengths(
    learner_id: str,
    section: str = "Writing",
    limit: int = 5
) -> dict:
    """
    Returns the most relevant active strength memories for a learner.

    Args:
        learner_id: The learner's unique ID
        section:    IELTS section — Writing, Reading, Speaking, Listening
        limit:      Maximum number of memories to return (default 5)

    Returns:
        A dict with 'strengths' list, each containing skill,
        memory_text, confidence, and evidence_count.
    """
    memories = get_relevant_memories(
        learner_id=learner_id,
        section=section,
        limit=limit
    )

    strengths = [
        {
            "skill": m["skill"],
            "memory_text": m["memory_text"],
            "confidence": m["confidence"],
            "evidence_count": m["evidence_count"]
        }
        for m in memories
        if m["memory_type"] == "strength"
    ]

    return {
        "learner_id": learner_id,
        "section": section,
        "strengths": strengths,
        "count": len(strengths)
    }


# ─── Tool 3: Get skill ranks ───────────────────────────────────────────────────

@mcp.tool()
def get_skill_ranks(
    learner_id: str,
    section: str = "Writing"
) -> dict:
    """
    Returns the learner's mastery rank on all 13 IELTS Writing
    sub-skills derived from the official Band Descriptors.

    Ranks range from 1 (Beginner) to 5 (Advanced) and are updated
    deterministically after each essay submission using a clean-streak
    rule engine — 3 consecutive demonstrated strengths = rank up.

    Args:
        learner_id: The learner's unique ID
        section:    Currently only "Writing" has a full taxonomy

    Returns:
        A dict with 'skills' list grouped by category, each containing:
        - skill_id, skill_name, category_name
        - current_rank (1-5), rank_name (Beginner→Advanced)
        - clean_streak: consecutive strengths toward next rank
        - total_evidence: total times this skill was assessed
    """
    all_ranks = get_all_skill_ranks(learner_id, section)
    summary = get_skill_progress_summary(learner_id, section)

    return {
        "learner_id": learner_id,
        "section": section,
        "skills": all_ranks,
        "summary": {
            "total_skills": summary["total_skills"],
            "average_rank": summary["average_rank"],
            "skills_at_advanced": summary["skills_at_max"],
            "skills_untouched": summary["skills_untouched"]
        }
    }


# ─── Tool 4: Get weakest skill ────────────────────────────────────────────────

@mcp.tool()
def get_weakest_skill_for_learner(learner_id: str, section: str = "Writing") -> dict:
    """
    Identifies the single skill most in need of attention for a learner.

    Priority order:
    1. Lowest current rank (rank 1 before rank 3)
    2. Among tied ranks: lowest total evidence (least known about)
    3. Among tied evidence: most recent demonstrated_weakness

    This is the same logic used by the Chat Coach to decide which
    skill to focus a tutoring session on.

    Args:
        learner_id: The learner's unique ID
        section:    IELTS section

    Returns:
        A dict with the weakest skill's full details including
        rank definitions for current and next level — useful for
        generating targeted teaching content.
    """
    weakest = get_weakest_skill(learner_id, section)

    if not weakest:
        return {
            "learner_id": learner_id,
            "has_data": False,
            "message": "No skill data yet — learner needs to submit essays first"
        }

    skill_def = get_skill_by_id(weakest["skill_id"], section)
    current_rank = weakest["current_rank"]
    next_rank = min(current_rank + 1, 5)

    current_rank_text = ""
    next_rank_text = ""
    if skill_def and "ranks" in skill_def:
        current_rank_text = skill_def["ranks"].get(str(current_rank), "")
        next_rank_text = skill_def["ranks"].get(str(next_rank), "")

    return {
        "learner_id": learner_id,
        "has_data": True,
        "skill_id": weakest["skill_id"],
        "skill_name": weakest["skill_name"],
        "category_name": weakest["category_name"],
        "current_rank": current_rank,
        "rank_name": get_rank_name(current_rank),
        "clean_streak": weakest["clean_streak"],
        "total_evidence": weakest["total_evidence"],
        "current_rank_definition": current_rank_text,
        "next_rank_definition": next_rank_text,
        "sessions_to_rank_up": max(0, 3 - weakest["clean_streak"])
    }


# ─── Tool 5: Get recent attempts ──────────────────────────────────────────────

@mcp.tool()
def get_recent_attempts(
    learner_id: str,
    section: str = "Writing",
    limit: int = 5
) -> dict:
    """
    Returns the learner's most recent practice attempts in a section.

    Args:
        learner_id: The learner's unique ID
        section:    IELTS section — Writing, Reading, Speaking, Listening
        limit:      Number of attempts to return (default 5, max 20)

    Returns:
        A dict with 'attempts' list, each containing:
        - attempt_id, section, task_type
        - prompt: the question/task the learner responded to
        - score_summary: key scores from the attempt
        - created_at: timestamp
    """
    limit = min(limit, 20)

    db = SessionLocal()
    try:
        attempts = db.query(PracticeAttempt).filter(
            PracticeAttempt.learner_id == learner_id,
            PracticeAttempt.section == section
        ).order_by(
            PracticeAttempt.created_at.desc()
        ).limit(limit).all()

        result = []
        for a in attempts:
            score_summary = {}
            if a.score_json:
                import json
                try:
                    score_data = json.loads(a.score_json) if isinstance(
                        a.score_json, str
                    ) else a.score_json
                    score_summary = score_data.get("scores", {})
                except Exception:
                    pass

            result.append({
                "attempt_id": a.attempt_id,
                "section": a.section,
                "task_type": a.task_type,
                "prompt": a.prompt[:200] + "..." if len(
                    a.prompt or ""
                ) > 200 else a.prompt,
                "score_summary": score_summary,
                "created_at": str(a.created_at)
            })

        return {
            "learner_id": learner_id,
            "section": section,
            "attempts": result,
            "count": len(result)
        }

    finally:
        db.close()


# ─── Tool 6: Get memory stats ─────────────────────────────────────────────────

@mcp.tool()
def get_learner_memory_stats(learner_id: str) -> dict:
    """
    Returns a statistical summary of a learner's memory profile.

    Args:
        learner_id: The learner's unique ID

    Returns:
        A dict with counts of active/archived memories, average
        confidence, and breakdown by memory type (weakness/strength).
    """
    stats = get_memory_stats(learner_id)
    return {
        "learner_id": learner_id,
        **stats
    }


# ─── Tool 7: Get full coaching context ───────────────────────────────────────

@mcp.tool()
def get_coaching_context(
    learner_id: str,
    section: str = "Writing"
) -> dict:
    """
    Returns a complete coaching context bundle for a learner.

    This is the primary tool for AI tutoring agents that need a
    full picture of a learner before generating personalised content.
    It combines weaknesses, strengths, skill ranks, weakest skill,
    and memory stats into a single call.

    Args:
        learner_id: The learner's unique ID
        section:    IELTS section to focus on

    Returns:
        A comprehensive dict suitable for injecting directly into
        an AI tutor's system prompt or context window.
    """
    weaknesses = get_learner_weaknesses(learner_id, section, limit=3)
    strengths = get_learner_strengths(learner_id, section, limit=3)
    weakest = get_weakest_skill_for_learner(learner_id, section)
    skill_summary = get_skill_progress_summary(learner_id, section)
    stats = get_memory_stats(learner_id)

    has_history = (
        weakest.get("has_data", False) or
        len(weaknesses.get("weaknesses", [])) > 0
    )

    return {
        "learner_id": learner_id,
        "section": section,
        "has_history": has_history,
        "weakest_skill": weakest if has_history else None,
        "top_weaknesses": weaknesses.get("weaknesses", []),
        "top_strengths": strengths.get("strengths", []),
        "skill_progress": {
            "average_rank": skill_summary.get("average_rank", 0),
            "skills_at_advanced": skill_summary.get("skills_at_max", 0),
            "total_skills": skill_summary.get("total_skills", 0)
        },
        "memory_profile": {
            "active_memories": stats.get("active_count", 0),
            "archived_memories": stats.get("archived_count", 0),
            "avg_confidence": stats.get("avg_confidence", 0)
        }
    }


# ─── Run standalone ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Starting IELTS MemoryCoach MCP Server...")
    print("Tools available:")
    print("  - get_learner_weaknesses")
    print("  - get_learner_strengths")
    print("  - get_skill_ranks")
    print("  - get_weakest_skill_for_learner")
    print("  - get_recent_attempts")
    print("  - get_learner_memory_stats")
    print("  - get_coaching_context")
    mcp.run()
