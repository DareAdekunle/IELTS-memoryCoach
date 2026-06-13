import json
import re


def sanitise_json_string(text: str) -> str:
    """
    Cleans a raw string that is supposed to be JSON but may contain
    characters that break the parser.

    Handles:
    - Smart/curly quotes replaced with straight quotes
    - Apostrophes inside string values that break JSON
    - Trailing commas before closing brackets
    """
    # Replace smart quotes with straight quotes
    text = text.replace('\u2018', "'").replace('\u2019', "'")
    text = text.replace('\u201c', '"').replace('\u201d', '"')

    # Remove trailing commas before closing brackets or braces
    # e.g. [1, 2, 3,] becomes [1, 2, 3]
    text = re.sub(r',\s*([}\]])', r'\1', text)

    return text


def safe_parse_json(text: str) -> dict:
    """
    Safely parses a JSON string that may contain markdown formatting
    or minor formatting issues from Qwen.

    Attempts multiple strategies in order:
    1. Standard parse after stripping markdown
    2. Parse after sanitising special characters
    3. Extract JSON object using bracket matching
    """
    if not text:
        raise ValueError("Empty response received from Qwen")

    # Strip markdown code fences
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    text = text.strip()

    # Attempt 1 — standard parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Attempt 2 — sanitise then parse
    try:
        return json.loads(sanitise_json_string(text))
    except json.JSONDecodeError:
        pass

    # Attempt 3 — extract JSON block then parse
    try:
        extracted = extract_json_block(text)
        return json.loads(extracted)
    except (ValueError, json.JSONDecodeError):
        pass

    # Attempt 4 — extract then sanitise then parse
    try:
        extracted = extract_json_block(text)
        return json.loads(sanitise_json_string(extracted))
    except (ValueError, json.JSONDecodeError):
        pass

    # Attempt 5 — aggressive clean: remove all content inside
    # string values that contains unescaped single quotes
    try:
        cleaned = aggressive_clean(text)
        return json.loads(cleaned)
    except (ValueError, json.JSONDecodeError) as e:
        raise ValueError(
            f"Could not parse Qwen response as JSON after all attempts.\n"
            f"Final error: {e}\nRaw response:\n{text}"
        )


def extract_json_block(text: str) -> str:
    """
    Finds the outermost JSON object or array in a string
    using bracket matching and returns it as a string.
    """
    # Find first opening bracket
    for start_char, end_char in [('{', '}'), ('[', ']')]:
        start = text.find(start_char)
        if start == -1:
            continue

        depth = 0
        in_string = False
        escape_next = False
        end = -1

        for i, char in enumerate(text[start:], start=start):
            if escape_next:
                escape_next = False
                continue
            if char == '\\':
                escape_next = True
                continue
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
            if in_string:
                continue
            if char == start_char:
                depth += 1
            elif char == end_char:
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break

        if end != -1:
            return text[start:end]

    raise ValueError(f"No JSON object or array found in:\n{text}")


def aggressive_clean(text: str) -> str:
    """
    Last resort cleaner. Finds all JSON string values and removes
    any unescaped single quotes or parenthetical quote patterns
    that could be breaking the parser.
    """
    # Remove patterns like ('some text') and ("some text") inside strings
    text = re.sub(r"\('([^']*?)'\)", r'(\1)', text)
    text = re.sub(r'\("([^"]*?)"\)', r'(\1)', text)

    # Replace any remaining unescaped single quotes within
    # what appear to be JSON string values with nothing
    # This is aggressive but better than a total failure
    def clean_string_value(match):
        content = match.group(1)
        content = content.replace("'", "")
        return f'"{content}"'

    text = re.sub(r'"((?:[^"\\]|\\.)*)"', clean_string_value, text)

    return text


def extract_json_from_text(text: str) -> dict:
    """
    Public alias kept for backwards compatibility.
    Calls extract_json_block and parses the result.
    """
    block = extract_json_block(text)
    try:
        return json.loads(block)
    except json.JSONDecodeError:
        return json.loads(sanitise_json_string(block))
