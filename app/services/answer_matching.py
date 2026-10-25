"""
Deterministic marking for Reading and Listening gap-fill / short-answer items.

IELTS marks these right or wrong against an answer key: the response must
match an accepted answer and respect the word limit. Nothing here calls a
model — AI may explain an answer, never decide whether it is correct.
"""
import re

_NUMBER_WORDS = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
    "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10", "eleven": "11",
    "twelve": "12", "thirteen": "13", "fourteen": "14", "fifteen": "15", "sixteen": "16",
    "seventeen": "17", "eighteen": "18", "nineteen": "19", "twenty": "20", "thirty": "30",
    "forty": "40", "fifty": "50",
}

WORD_LIMIT_TEXT = {1: "ONE WORD", 2: "NO MORE THAN TWO WORDS", 3: "NO MORE THAN THREE WORDS"}


def normalise_answer(text: str) -> str:
    """Case, punctuation, hyphens (peer-reviewed = peer reviewed), number words and articles normalised."""
    text = (text or "").lower().strip().replace("-", " ")
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    for word, digit in _NUMBER_WORDS.items():
        text = re.sub(r"\b" + word + r"\b", digit, text)
    text = re.sub(r"\b(the|a|an)\b", "", text)
    return re.sub(r"\s+", " ", text).strip()


def count_words(text: str) -> int:
    """
    Words counted against an IELTS limit ("... AND/OR A NUMBER"): tokens that
    contain a digit are numbers and don't count; hyphenated words count once.
    """
    return sum(1 for token in (text or "").split() if not re.search(r"\d", token))


def check_answer(learner_answer: str, accepted: list[str], word_limit: int | None = None) -> dict:
    """
    Right only if the normalised response equals a normalised accepted answer
    and is within the word limit. No partial or "contains" matching.
    """
    if not (learner_answer or "").strip():
        return {"is_correct": False, "matched_answer": "", "over_limit": False}
    if word_limit is not None and count_words(learner_answer) > word_limit:
        return {"is_correct": False, "matched_answer": "", "over_limit": True}
    response = normalise_answer(learner_answer)
    for answer in accepted:
        if answer and normalise_answer(answer) == response:
            return {"is_correct": True, "matched_answer": answer, "over_limit": False}
    return {"is_correct": False, "matched_answer": "", "over_limit": False}


def limit_feedback(word_limit: int | None) -> str:
    return f"Your answer is longer than the limit ({WORD_LIMIT_TEXT.get(word_limit, f'{word_limit} WORDS')})."


_ANSWER_FIELDS = ("answer", "acceptable_answers", "explanation")


def public_questions(questions: list[dict]) -> list[dict]:
    """Questions as sent to the browser: no answer key or explanation."""
    return [{k: v for k, v in q.items() if k not in _ANSWER_FIELDS} for q in questions]
