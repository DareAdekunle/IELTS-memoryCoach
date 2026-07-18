"""
app/services/telegram_service.py — Qwen-powered Telegram coaching agent

Qwen (qwen-plus) drives the conversation using tool-calling. The tools
are the same functions exposed by the MCP server, so the same backend
layer powers Claude Desktop (via MCP) and Telegram (via Qwen agent).

Telegram Bot API is simpler than WhatsApp — no business verification,
no 24-hour window, no template approval. Any message anytime.
"""

import os
import json
import httpx
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# ─── Qwen client ─────────────────────────────────────────────────────────────

_client = OpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url=os.getenv(
        "MODEL_STUDIO_ENDPOINT",
        "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
)

QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen-plus")

# ─── Telegram Bot API ─────────────────────────────────────────────────────────

TG_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN", "")
TG_API_URL = f"https://api.telegram.org/bot{TG_TOKEN}"


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
                "Use when the learner wants to change their study days or time. "
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
                        "description": "IANA timezone e.g. 'Africa/Lagos'. Use the learner's existing timezone if only changing days or time."
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
                "Use when the learner wants a one-time session outside their recurring schedule."
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
            "description": "Cancel the learner's study schedule and remove all recurring Google Calendar events.",
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
    from app.mcp.memory_server import (
        find_learner,
        get_coaching_context,
        get_study_schedule,
        schedule_study_sessions,
        add_one_off_session,
        cancel_study_schedule,
    )
    dispatch = {
        "find_learner":            find_learner,
        "get_coaching_context":    get_coaching_context,
        "get_study_schedule":      get_study_schedule,
        "schedule_study_sessions": schedule_study_sessions,
        "add_one_off_session":     add_one_off_session,
        "cancel_study_schedule":   cancel_study_schedule,
    }
    fn = dispatch.get(tool_name)
    if not fn:
        return {"error": f"Unknown tool: {tool_name}"}
    try:
        return fn(**args)
    except Exception as e:
        return {"error": str(e)}


# ─── Qwen agentic loop ────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are Qonda, an AI IELTS study coach built on Qwen by Alibaba Cloud.
You help learners track their progress, understand their weaknesses, and manage their \
study schedule — via Telegram.

Rules:
- Keep replies SHORT and conversational. Max 3-4 sentences unless listing data.
- If you don't know who the user is, ask for their Qonda email to link their account.
- Once you have their email, call find_learner first to get their learner_id.
- For any coaching question, call get_coaching_context before answering.
- For schedule changes, confirm the intent before calling schedule tools.
- Be warm, encouraging, and direct. Use their name when you know it.
- You can use Telegram markdown: *bold*, _italic_, `code`. Use sparingly."""


def run_qwen_agent(user_message: str, learner_id: str | None, conversation_history: list) -> str:
    """
    Run the Qwen agentic loop for a single Telegram message.

    Args:
        user_message:         The incoming message text
        learner_id:           Known learner_id if account is linked, else None
        conversation_history: Recent messages [{role, content}]

    Returns:
        The reply text to send back via Telegram
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if learner_id:
        messages.append({
            "role": "system",
            "content": f"[Context] This user's Qonda learner_id is: {learner_id}"
        })

    messages.extend(conversation_history[-6:])
    messages.append({"role": "user", "content": user_message})

    for _ in range(5):
        response = _client.chat.completions.create(
            model=QWEN_MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.7,
        )

        choice = response.choices[0]

        if choice.finish_reason != "tool_calls":
            return choice.message.content or "Sorry, I couldn't generate a response."

        messages.append(choice.message)
        for tc in choice.message.tool_calls:
            args = json.loads(tc.function.arguments)
            result = _execute_tool(tc.function.name, args)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result),
            })

    final = _client.chat.completions.create(
        model=QWEN_MODEL,
        messages=messages,
        temperature=0.7,
    )
    return final.choices[0].message.content or "Something went wrong. Please try again."


# ─── Telegram sender ──────────────────────────────────────────────────────────

def send_message(chat_id: int | str, text: str, parse_mode: str = "Markdown") -> bool:
    """Send a text message via Telegram Bot API."""
    if not TG_TOKEN:
        return False
    try:
        r = httpx.post(
            f"{TG_API_URL}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": parse_mode},
            timeout=10,
        )
        return r.status_code == 200
    except Exception:
        return False


def send_typing(chat_id: int | str) -> None:
    """Show typing indicator while Qwen is thinking."""
    if not TG_TOKEN:
        return
    try:
        httpx.post(
            f"{TG_API_URL}/sendChatAction",
            json={"chat_id": chat_id, "action": "typing"},
            timeout=5,
        )
    except Exception:
        pass
