"""
app/services/agent_tools.py

Single source of truth for all Coach and Tutor agent tool definitions.

Two tool sets:
  COACH_TOOLS — read + write. Used by the Coach agent after every
                practice submission. Coach gathers evidence then
                makes classification decisions.

  TUTOR_TOOLS — read only. Used by the Tutor agent mid-conversation.
                Tutor can query live learner data but never writes
                ranks or memories directly.

Each tool set has two parts:
  1. SCHEMAS  — OpenAI-compatible function definitions passed to
                client.chat.completions.create(tools=...)
  2. EXECUTOR — execute_coach_tool() / execute_tutor_tool()
                Called when Qwen returns a tool_call. Runs the
                actual Python function and returns the result.

The deterministic rank engine (apply_skill_classifications_batch)
is never called directly by AI — only via submit_classification,
which enforces the clean_streak rule unchanged.
"""

import os
import sys
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.services.memory_service import (
    get_relevant_memories,
    get_all_skill_ranks,
    get_skill_rank,
    get_weakest_skill,
    get_skill_progress_summary,
    extract_and_save_memories,
    update_memories,
    apply_skill_classifications_batch,
    get_attempts,
)
from app.services.skill_taxonomy_service import get_skill_by_id, get_rank_name


# ─── COACH TOOL SCHEMAS ───────────────────────────────────────────────────────
# Read + write tools. Coach uses these to gather evidence before
# making classification and memory decisions.

COACH_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_skill_rank",
            "description": (
                "Read the learner's current rank and streak for a specific skill. "
                "Call this before classifying a skill so you know the current state."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "learner_id": {"type": "string", "description": "Learner's unique ID"},
                    "section": {"type": "string", "description": "IELTS section: Writing, Reading, Speaking, Listening"},
                    "skill_id": {"type": "string", "description": "Skill ID from the taxonomy e.g. tr_full_coverage"}
                },
                "required": ["learner_id", "section", "skill_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_learner_memories",
            "description": (
                "Retrieve active coaching memories for a learner in a section. "
                "Use this to understand existing patterns before extracting new memories."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "learner_id": {"type": "string"},
                    "section": {"type": "string"},
                    "limit": {"type": "integer", "description": "Max memories to return (default 5)"}
                },
                "required": ["learner_id", "section"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_attempt",
            "description": (
                "Retrieve the learner's most recent practice attempt in a section. "
                "Use this to reference their actual work when extracting memories."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "learner_id": {"type": "string"},
                    "section": {"type": "string"}
                },
                "required": ["learner_id", "section"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "submit_classification",
            "description": (
                "Submit a skill classification after evaluating the learner's attempt. "
                "This triggers the deterministic rank engine which applies clean_streak "
                "rules — 3 consecutive strengths = rank up. "
                "You must classify EVERY skill in the section taxonomy. "
                "Valid values: demonstrated_strength, demonstrated_weakness, not_applicable."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "learner_id": {"type": "string"},
                    "section": {"type": "string"},
                    "classifications": {
                        "type": "object",
                        "description": (
                            "Dict of skill_id → classification. "
                            "e.g. {\"tr_full_coverage\": \"demonstrated_strength\", "
                            "\"cc_logical_progression\": \"demonstrated_weakness\"}"
                        )
                    }
                },
                "required": ["learner_id", "section", "classifications"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_memory",
            "description": (
                "Save a new coaching observation to the learner's memory profile. "
                "Write one memory per distinct skill observation. "
                "Be specific — reference what the learner actually did, not generic feedback."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "learner_id": {"type": "string"},
                    "section": {"type": "string"},
                    "skill": {"type": "string", "description": "Short skill label e.g. 'cohesive devices'"},
                    "memory_type": {"type": "string", "description": "weakness or strength"},
                    "memory_text": {"type": "string", "description": "Specific evidence-based observation (1-2 sentences)"},
                    "confidence": {"type": "number", "description": "0.5-0.8 for new memories"}
                },
                "required": ["learner_id", "section", "skill", "memory_type", "memory_text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_memory",
            "description": (
                "Update the confidence of an existing memory based on new evidence. "
                "Use strengthen when new attempt confirms the pattern. "
                "Use weaken when new attempt contradicts it. "
                "Use archive when the learner has clearly mastered this skill."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "memory_id": {"type": "string"},
                    "action": {"type": "string", "description": "strengthen, weaken, or archive"},
                    "new_confidence": {"type": "number", "description": "Updated confidence 0.0-1.0"},
                    "reason": {"type": "string", "description": "Why you're making this change"}
                },
                "required": ["memory_id", "action", "new_confidence"]
            }
        }
    }
]


# ─── TUTOR TOOL SCHEMAS ───────────────────────────────────────────────────────
# Read-only tools. Tutor uses these mid-conversation to stay
# grounded in live learner data rather than stale session-start context.

TUTOR_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_coaching_context",
            "description": (
                "Get the full coaching context for a learner in a section. "
                "Returns weakest skill, top weaknesses, top strengths, and skill progress. "
                "Call this at session start or when you need a full picture."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "learner_id": {"type": "string"},
                    "section": {"type": "string"}
                },
                "required": ["learner_id", "section"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_learner_weaknesses",
            "description": (
                "Get the learner's active weakness memories for a section. "
                "Call this mid-conversation when you need to reference "
                "specific patterns the Coach has observed."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "learner_id": {"type": "string"},
                    "section": {"type": "string"},
                    "limit": {"type": "integer"}
                },
                "required": ["learner_id", "section"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_attempts",
            "description": (
                "Get the learner's recent practice attempts. "
                "Call this when you want to reference their actual work "
                "in a drill or explanation — e.g. 'in your last essay you wrote...'"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "learner_id": {"type": "string"},
                    "section": {"type": "string"},
                    "limit": {"type": "integer", "description": "Default 3"}
                },
                "required": ["learner_id", "section"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_skill_ranks",
            "description": (
                "Get all skill ranks for a learner in a section. "
                "Call this when you want to acknowledge progress during "
                "drilling or tell the learner how close they are to ranking up."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "learner_id": {"type": "string"},
                    "section": {"type": "string"}
                },
                "required": ["learner_id", "section"]
            }
        }
    }
]


# ─── COACH TOOL EXECUTOR ─────────────────────────────────────────────────────

def execute_coach_tool(tool_name: str, args: dict) -> str:
    """
    Executes a Coach tool call and returns the result as a JSON string.
    Called by the Coach agent loop when Qwen returns a tool_call.
    """
    try:
        if tool_name == "get_skill_rank":
            result = get_skill_rank(
                learner_id=args["learner_id"],
                section=args["section"],
                skill_id=args["skill_id"]
            )

        elif tool_name == "get_learner_memories":
            memories = get_relevant_memories(
                learner_id=args["learner_id"],
                section=args["section"],
                limit=args.get("limit", 5)
            )
            result = {"memories": memories, "count": len(memories)}

        elif tool_name == "get_recent_attempt":
            attempts = get_attempts(
                learner_id=args["learner_id"],
                section=args["section"]
            )
            result = attempts[0] if attempts else {"message": "No attempts yet"}

        elif tool_name == "submit_classification":
            classifications = args["classifications"]
            rank_results = apply_skill_classifications_batch(
                learner_id=args["learner_id"],
                section=args["section"],
                classifications=classifications
            )
            ranked_up = [r for r in rank_results if r.get("ranked_up")]
            result = {
                "processed": len(rank_results),
                "ranked_up": ranked_up,
                "rank_ups_count": len(ranked_up)
            }

        elif tool_name == "write_memory":
            import uuid
            from app.db.database import SessionLocal
            from app.db.models import LearnerMemory

            db = SessionLocal()
            try:
                memory_id = str(uuid.uuid4())[:12]
                memory = LearnerMemory(
                    memory_id=memory_id,
                    learner_id=args["learner_id"],
                    section=args["section"],
                    skill=args["skill"],
                    memory_type=args["memory_type"],
                    memory_text=args["memory_text"],
                    confidence=float(args.get("confidence", 0.65)),
                    evidence_count=1,
                    status="active"
                )
                db.add(memory)
                db.commit()
                result = {"memory_id": memory_id, "saved": True}
            except Exception as e:
                db.rollback()
                result = {"saved": False, "error": str(e)}
            finally:
                db.close()

        elif tool_name == "update_memory":
            from app.db.database import SessionLocal
            from app.db.models import LearnerMemory

            db = SessionLocal()
            try:
                memory = db.query(LearnerMemory).filter(
                    LearnerMemory.memory_id == args["memory_id"]
                ).first()

                if not memory:
                    result = {"updated": False, "error": "Memory not found"}
                else:
                    action = args["action"]
                    new_confidence = float(args["new_confidence"])

                    if action == "strengthen":
                        memory.confidence = min(new_confidence, 0.95)
                        memory.evidence_count += 1
                    elif action == "weaken":
                        memory.confidence = max(new_confidence, 0.1)
                        memory.evidence_count += 1
                    elif action == "archive":
                        memory.status = "archived"
                        memory.confidence = new_confidence

                    db.commit()
                    result = {"updated": True, "action": action, "memory_id": args["memory_id"]}
            except Exception as e:
                db.rollback()
                result = {"updated": False, "error": str(e)}
            finally:
                db.close()

        else:
            result = {"error": f"Unknown tool: {tool_name}"}

    except Exception as e:
        result = {"error": str(e)}

    return json.dumps(result)


# ─── TUTOR TOOL EXECUTOR ─────────────────────────────────────────────────────

def execute_tutor_tool(tool_name: str, args: dict) -> str:
    """
    Executes a Tutor tool call and returns the result as a JSON string.
    All Tutor tools are read-only — no writes to DB.
    """
    try:
        if tool_name == "get_coaching_context":
            weaknesses = get_relevant_memories(
                learner_id=args["learner_id"],
                section=args["section"],
                limit=3
            )
            weakest = get_weakest_skill(args["learner_id"], args["section"])
            summary = get_skill_progress_summary(args["learner_id"], args["section"])

            skill_def = None
            if weakest:
                skill_def = get_skill_by_id(weakest["skill_id"], args["section"])

            result = {
                "weakest_skill": {
                    "skill_id": weakest["skill_id"],
                    "skill_name": weakest["skill_name"],
                    "current_rank": weakest["current_rank"],
                    "rank_name": get_rank_name(weakest["current_rank"]),
                    "clean_streak": weakest["clean_streak"],
                    "sessions_to_rank_up": max(0, 3 - weakest["clean_streak"])
                } if weakest else None,
                "skill_definition": skill_def,
                "top_weaknesses": [
                    m for m in weaknesses if m["memory_type"] == "weakness"
                ],
                "skill_progress": {
                    "average_rank": summary.get("average_rank", 0),
                    "total_skills": summary.get("total_skills", 0),
                    "skills_at_max": summary.get("skills_at_max", 0)
                }
            }

        elif tool_name == "get_learner_weaknesses":
            memories = get_relevant_memories(
                learner_id=args["learner_id"],
                section=args["section"],
                limit=args.get("limit", 5)
            )
            result = {
                "weaknesses": [m for m in memories if m["memory_type"] == "weakness"]
            }

        elif tool_name == "get_recent_attempts":
            attempts = get_attempts(
                learner_id=args["learner_id"],
                section=args["section"]
            )
            limit = args.get("limit", 3)
            result = {
                "attempts": [
                    {
                        "attempt_id": a["attempt_id"],
                        "prompt": a["prompt"][:300],
                        "feedback": a["feedback"],
                        "created_at": a["created_at"]
                    }
                    for a in attempts[:limit]
                ]
            }

        elif tool_name == "get_skill_ranks":
            all_ranks = get_all_skill_ranks(
                args["learner_id"],
                args["section"]
            )
            result = {
                "skills": all_ranks,
                "section": args["section"]
            }

        else:
            result = {"error": f"Unknown tool: {tool_name}"}

    except Exception as e:
        result = {"error": str(e)}

    return json.dumps(result)
