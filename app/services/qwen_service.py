import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
)

# Using the model name from your Qwen dashboard
QWEN_MODEL = "qwen-plus"


def call_qwen(prompt: str, system_message: str = None, temperature: float = 0.3) -> str:
    """
    Sends a prompt to Qwen and returns the response as a string.

    temperature controls how creative vs precise the response is:
    - 0.0 to 0.3 = precise and consistent (good for scoring)
    - 0.7 to 1.0 = more creative (good for coaching chat)
    """
    messages = []

    if system_message:
        messages.append({"role": "system", "content": system_message})

    messages.append({"role": "user", "content": prompt})

    try:
        response = client.chat.completions.create(
            model=QWEN_MODEL,
            messages=messages,
            temperature=temperature
        )
        return response.choices[0].message.content

    except Exception as e:
        raise Exception(f"Qwen API call failed: {str(e)}")


def call_qwen_for_json(prompt: str, system_message: str = None) -> str:
    """
    Same as call_qwen but specifically for when we expect a JSON response.
    Uses very low temperature for maximum consistency.
    """
    json_system = "You are a precise IELTS evaluator. You must respond with valid JSON only. No explanations, no markdown, no code fences. Only the raw JSON object."

    if system_message:
        json_system = system_message + "\n\n" + json_system

    return call_qwen(prompt, system_message=json_system, temperature=0.1)

def fix_broken_json(broken_response: str) -> str:
    """
    If Qwen returns something that looks like JSON but fails to parse,
    we send it back to Qwen and ask it to fix the formatting.
    This is a last resort fallback.
    """
    fix_prompt = f"""The following text is supposed to be a valid JSON object but it has formatting errors.
Please fix it and return only the corrected valid JSON object with no other text.
Do not change any of the actual content or values — only fix the JSON syntax.

Broken JSON:
{broken_response}

Rules for fixing:
- Remove any apostrophes or single quotes inside string values
- Remove any unescaped special characters
- Make sure all strings use double quotes
- Return only the raw JSON object, nothing else
"""
    return call_qwen(fix_prompt, temperature=0.0)
