import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# ─── Alibaba Cloud Model Studio Configuration ─────────────────────────────────
# Text AI inference runs through Alibaba Cloud Model Studio.
# This keeps all AI logic within the Alibaba Cloud ecosystem,
# using the 70M+ free token allocation from Model Studio.
#
# Uses a dedicated Singapore-region workspace endpoint for low
# latency and network isolation within Alibaba Cloud infrastructure.
#
# The same DASHSCOPE_API_KEY is used for all three Qwen services:
#   - Text generation (this file, via OpenAI-compatible SDK)
#   - ASR speech-to-text (asr_service.py, via DashScope SDK)
#   - TTS text-to-speech (tts_service.py, via DashScope SDK)

_API_KEY = os.getenv("DASHSCOPE_API_KEY")

# Dedicated Singapore workspace endpoint
# Falls back to generic Model Studio endpoint if not set
_BASE_URL = os.getenv(
    "MODEL_STUDIO_ENDPOINT",
    "https://dashscope.aliyuncs.com/compatible-mode/v1"
)

client = OpenAI(
    api_key=_API_KEY,
    base_url=_BASE_URL
)

# ─── Task-tiered model routing ────────────────────────────────────────────────
# Different tasks require different model capabilities.
# Using the right model for each task reduces cost and latency
# without sacrificing output quality where it matters.
#
# qwen-plus  → complex reasoning tasks:
#              essay evaluation, chat coaching, memory extraction
#              (needs rich language understanding and generation)
#
# qwen-turbo → simple structured output tasks:
#              skill classification (3-way choice per skill_id)
#              (fast, cheap, sufficient for constrained output)

QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen-plus")
QWEN_TURBO_MODEL = os.getenv("QWEN_TURBO_MODEL", "qwen-turbo")


def call_qwen(
    prompt: str,
    system_message: str = None,
    temperature: float = 0.7,
    use_turbo: bool = False
) -> str:
    """
    Makes a single-turn text generation call to Qwen via Model Studio.

    Args:
        prompt:         The user message / task description
        system_message: Optional system prompt for role/context setting
        temperature:    Sampling temperature (0.0-1.0)
        use_turbo:      If True, uses qwen-turbo instead of qwen-plus.
                        Use for structured output tasks like classification.

    Returns:
        The model's response as a plain string.
        Raises on network or API errors (caller handles gracefully).
    """
    model = QWEN_TURBO_MODEL if use_turbo else QWEN_MODEL

    messages = []
    if system_message:
        messages.append({"role": "system", "content": system_message})
    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature
    )
    return response.choices[0].message.content


def call_qwen_for_json(
    prompt: str,
    system_message: str = None,
    temperature: float = 0.3,
    use_turbo: bool = False
) -> str:
    """
    Makes a Qwen call optimised for JSON output.
    Uses lower temperature for more deterministic structured responses.

    The raw string is returned — callers must parse via
    app/utils/json_utils.safe_parse_json() which handles
    markdown fences, smart quotes, and other common Qwen
    JSON formatting quirks.
    """
    return call_qwen(
        prompt=prompt,
        system_message=system_message,
        temperature=temperature,
        use_turbo=use_turbo
    )


def fix_broken_json(broken_json: str) -> str:
    """
    Asks Qwen to repair malformed JSON it produced.
    Used as a last-resort fallback when all local JSON parsing
    strategies fail (e.g. apostrophes inside long essay feedback).

    This is a self-healing pattern: Qwen repairs its own output
    rather than failing the entire request.
    """
    repair_prompt = (
        "The following is supposed to be valid JSON but contains "
        "syntax errors. Fix it and return ONLY the corrected JSON "
        "with no explanation, no markdown, no backticks:\n\n"
        f"{broken_json}"
    )
    return call_qwen(repair_prompt, temperature=0.1, use_turbo=True)
