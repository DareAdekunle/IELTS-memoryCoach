"""
app/services/whatsapp_service.py — Qwen-powered WhatsApp coaching agent

Qwen (qwen-plus) drives the conversation using tool-calling. The tools
are the same functions exposed by the MCP server, so the same backend
layer powers both Claude Desktop (via MCP) and WhatsApp (via Qwen agent).

Flow:
  Incoming WhatsApp message
    → resolve learner from whatsapp_number in DB
    → if unknown, ask for email → find_learner → store mapping
    → run Qwen agentic loop with tool-calling
    → send WhatsApp reply
"""

import os
import json
import httpx
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# ─── Qwen client (same config as qwen_service.py) ────────────────────────────

_client = OpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url=os.getenv(
        "MODEL_STUDIO_ENDPOINT",
        "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
)

QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen-plus")

# ─── WhatsApp Cloud API config ────────────────────────────────────────────────

WA_TOKEN    = os.getenv("WHATSAPP_TOKEN", "")
WA_PHONE_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
WA_API_URL  = f"https://graph.facebook.com/v19.0/{WA_PHONE_ID}/messages"

# ─── Qwen tool definitions (mirror the MCP server tools) ─────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "find_learner",
            "description": (
                "Look up a Qonda learner's ID using their email address. "
                "Call this when the user provides their email to link their account."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "email": {"type": "string", "description": "The learner's Qonda email address"}
                },
                "required": ["email"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_coaching_context",
            "description": (
                "Get a complete coaching overview for a learner — weaknesses, strengths, "
                "weakest skill, and skill progress. Call this before giving any advice or "
                "answering questions about the learner's IELTS preparation."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "learner_id": {"type": "string"},
                    "section": {
                        "type": "string",
                        "enum": ["Writing", "Reading", "Speaking", "Listening"],
                        "description": "IELTS section to focus on (default: Writing)"
                    }
                },
                "required": ["learner_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_study_schedule",
            "description": "Get the learner's current study schedule — days, time, duration, and whether Google Calendar is connected.",
            "parameters": {
                "type": "object",
                "properties": {
                    "learner_id": {"type": "string"}
                },
                "required": ["learner_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "schedule_study_sessions",
            "description": (
                "Create or update the learner's recurring study schedule. "
                "Use this when the learner wants to change their study days or time. "
                "This replaces any existing schedule."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "learner_id": {"type": "string"},
                    "days": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]},
                        "description": "Exact 3-letter day abbreviations e.g. ['Mon', 'Wed', 'Fri']"
                    },
                    "study_time": {
                        "type": "string",
                        "description": "Time in HH:MM 24-hour format e.g. '07:00'"
                    },
                    "duration_minutes": {
                        "type": "integer",
                        "enum": [15, 30, 45, 60],
                        "description": "Session length in minutes"
                    },
                    "timezone": {
                        "type": "string",
                        "description": "IANA timezone e.g. 'Africa/Lagos'. Use the learner's existing timezone if changing only days or time."
                    }
                },
                "required": ["learner_id", "days", "study_time"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_one_off_session",
            "description": (
                "Add a single extra study session on a specific date. "
                "Use when the learner wants to add a one-time session that is not part of their recurring schedule."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "learner_id": {"type": "string"},
                    "date_iso": {"type": "string", "description": "Date in YYYY-MM-DD format e.g. '2026-08-15'"},
                    "study_time": {"type": "string", "description": "Time in HH:MM 24-hour format"},
                    "duration_minutes": {"type": "integer", "description": "Session length in minutes"}
                },
                "required": ["learner_id", "date_iso", "study_time"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_study_schedule",
            "description": "Cancel the learner's study schedule and remove all recurring calendar events.",
            "parameters": {
                "type": "object",
                "properties": {
                    "learner_id": {"type": "string"}
                },
                "required": ["learner_id"]
            }
        }
    },
]

# ─── Tool execution (same functions as MCP server) ────────────────────────────

def _execute_tool(tool_name: str, args: dict) -> dict:
    """Execute a tool call by calling the same Python functions as the MCP server."""
    from app.mcp.memory_server import (
        find_learner,
        get_coaching_context,
        get_study_schedule,
        schedule_study_sessions,
        add_one_off_session,
        cancel_study_schedule,
    )
    dispatch = {
        "find_learner":           find_learner,
        "get_coaching_context":   get_coaching_context,
        "get_study_schedule":     get_study_schedule,
        "schedule_study_sessions": schedule_study_sessions,
        "add_one_off_session":    add_one_off_session,
        "cancel_study_schedule":  cancel_study_schedule,
    }
    fn = dispatch.get(tool_name)
    if not fn:
        return {"error": f"Unknown tool: {tool_name}"}
    try:
        return fn(**args)
    except Exception as e:
        return {"error": str(e)}


# ─── Qwen agentic loop ────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are Qonda, an AI IELTS study coach. You help learners track \
their progress, understand their weaknesses, and manage their study schedule — \
all via WhatsApp.

Rules:
- You are powered by Qwen, Alibaba Cloud's AI model.
- Keep replies SHORT — this is WhatsApp, not an essay. Max 3-4 sentences unless listing data.
- If you don't know who the user is, ask for their Qonda email to link their account.
- Once you have their email, always call find_learner first to get their learner_id.
- For any coaching question, call get_coaching_context before answering.
- For schedule changes, confirm the change with the user before calling schedule tools.
- Be warm, encouraging, and direct. Use their name when you know it.
- Format lists with simple dashes, not heavy markdown (WhatsApp renders text only)."""


def run_qwen_agent(user_message: str, learner_id: str | None, conversation_history: list) -> str:
    """
    Run the Qwen agentic loop for a single WhatsApp message.

    Args:
        user_message:         The incoming WhatsApp message text
        learner_id:           Known learner_id if account is already linked, else None
        conversation_history: Recent messages for context (list of {role, content})

    Returns:
        The final text reply to send back via WhatsApp
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Inject learner_id context if known
    if learner_id:
        messages.append({
            "role": "system",
            "content": f"[Context] This user's learner_id is: {learner_id}"
        })

    messages.extend(conversation_history[-6:])  # last 3 turns for context
    messages.append({"role": "user", "content": user_message})

    # Agentic loop — Qwen can call tools up to 5 times before forced reply
    for _ in range(5):
        response = _client.chat.completions.create(
            model=QWEN_MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.7,
        )

        choice = response.choices[0]

        # No tool call → final reply
        if choice.finish_reason != "tool_calls":
            return choice.message.content or "Sorry, I couldn't generate a response."

        # Execute each tool call and feed results back
        messages.append(choice.message)
        for tc in choice.message.tool_calls:
            args = json.loads(tc.function.arguments)
            result = _execute_tool(tc.function.name, args)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result),
            })

    # Fallback if loop exhausted
    final = _client.chat.completions.create(
        model=QWEN_MODEL,
        messages=messages,
        temperature=0.7,
    )
    return final.choices[0].message.content or "Something went wrong. Please try again."


# ─── WhatsApp API sender ──────────────────────────────────────────────────────

def send_whatsapp_message(to: str, text: str) -> bool:
    """Send a text message via WhatsApp Cloud API. Returns True on success."""
    if not WA_TOKEN or not WA_PHONE_ID:
        return False
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"preview_url": False, "body": text},
    }
    headers = {
        "Authorization": f"Bearer {WA_TOKEN}",
        "Content-Type": "application/json",
    }
    try:
        r = httpx.post(WA_API_URL, json=payload, headers=headers, timeout=10)
        return r.status_code == 200
    except Exception:
        return False


def send_whatsapp_template(to: str, template_name: str, params: list[str]) -> bool:
    """Send an approved WhatsApp template message (for proactive notifications)."""
    if not WA_TOKEN or not WA_PHONE_ID:
        return False
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": "en"},
            "components": [{
                "type": "body",
                "parameters": [{"type": "text", "text": p} for p in params]
            }]
        }
    }
    headers = {
        "Authorization": f"Bearer {WA_TOKEN}",
        "Content-Type": "application/json",
    }
    try:
        r = httpx.post(WA_API_URL, json=payload, headers=headers, timeout=10)
        return r.status_code == 200
    except Exception:
        return False
