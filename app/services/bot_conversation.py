"""
One conversation flow for every chat channel (Telegram, WhatsApp).

Routes handle transport (webhook parsing, verification, sending); this
module decides the reply: account linking, scope guardrails, history and
the Qwen agent.
"""
from collections import defaultdict

from app.services import channel_linking as links
from app.services.bot_guardrails import REFUSAL, is_blocked

HISTORY_LIMIT = 20
_history: dict[tuple[str, str], list] = defaultdict(list)

CHANNEL_NAMES = {"telegram": "Telegram", "whatsapp": "WhatsApp"}


def _run_agent(channel: str, **kwargs) -> str:
    if channel == "telegram":
        from app.services.telegram_service import run_qwen_agent
    else:
        from app.services.whatsapp_service import run_qwen_agent
    return run_qwen_agent(**kwargs)


def link_instructions(channel: str) -> str:
    name = CHANNEL_NAMES[channel]
    return (
        "👋 Hi! I'm BandUp, your AI IELTS coach.\n\n"
        f"To connect this {name} chat to your account, sign in to BandUp, open "
        f"Study Plan → Chat with your coach, tap Connect {name}, and send me the code shown there."
    )


def respond(channel: str, external_id: str, text: str) -> str:
    """Returns the reply to send for one incoming text message."""
    text = (text or "").strip()
    key = (channel, external_id)
    learner_id = links.learner_for(channel, external_id)

    code = links.extract_code(text)
    explicit = text.upper().startswith(("/START", "LINK"))
    # A linked learner's bare 8-letter word is just a message, not a code attempt.
    if code and (learner_id is None or explicit):
        if links.is_rate_limited(external_id):
            return "Too many incorrect codes. Please wait 15 minutes, then create a new code in BandUp."
        user = links.redeem_link_code(code, channel, external_id)
        if not user:
            return "That code is invalid or has expired. Create a new one in BandUp → Study Plan → Chat with your coach."
        _history.pop(key, None)
        first_name = (user.full_name or "").split(" ")[0] or "there"
        return (
            f"✅ You're connected, {first_name}! Ask me how you're doing, "
            "what to practise next, or to plan your study week."
        )

    if learner_id is None:
        return link_instructions(channel)

    if text.lower() in ("/start", "start"):
        _history.pop(key, None)
        text = "Hello, give me a quick coaching update"

    if is_blocked(text):
        return REFUSAL

    history = _history[key]
    reply = _run_agent(channel, user_message=text, learner_id=learner_id, conversation_history=list(history))
    history.extend([{"role": "user", "content": text}, {"role": "assistant", "content": reply}])
    del history[:-HISTORY_LIMIT]
    return reply
