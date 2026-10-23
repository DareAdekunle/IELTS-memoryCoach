import json


def parse_tool_args(raw: str | None) -> dict:
    """Model-produced tool arguments; malformed or non-object JSON becomes {}."""
    try:
        args = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return args if isinstance(args, dict) else {}


def assistant_tool_message(message) -> dict:
    """
    The assistant turn to append before tool results.

    Arguments are re-serialised because Qwen rejects the next request with a
    400 if an echoed `function.arguments` is not valid JSON — which the model
    occasionally produces.
    """
    return {
        "role": "assistant",
        "content": message.content or "",
        "tool_calls": [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": json.dumps(parse_tool_args(tc.function.arguments)),
                },
            }
            for tc in message.tool_calls
        ],
    }
