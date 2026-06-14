import os
import sys
import json
import random

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.services.qwen_service import call_qwen_for_json
from app.utils.json_utils import safe_parse_json, extract_json_from_text

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")


# ─── LOAD PASSAGES ────────────────────────────────────────────────────────────

def load_reading_passages() -> list:
    """
    Loads all reading passages from the JSON file.
    """
    path = os.path.join(DATA_DIR, "reading_passages.json")
    with open(path, "r") as f:
        return json.load(f)


def get_random_passage(difficulty: str = None) -> dict:
    """
    Returns a random reading passage.
    If difficulty is provided, filters to that level only.

    difficulty options: 'beginner', 'intermediate', 'advanced'
    """
    passages = load_reading_passages()

    if difficulty:
        passages = [p for p in passages if p["difficulty"] == difficulty]

    if not passages:
        raise ValueError(f"No passages found for difficulty: {difficulty}")

    return random.choice(passages)


def get_passage_by_id(passage_id: str) -> dict | None:
    """
    Returns a specific passage by its ID.
    Used to reload a passage without changing it on page refresh.
    """
    passages = load_reading_passages()
    for p in passages:
        if p["passage_id"] == passage_id:
            return p
    return None


def get_all_passages_summary() -> list:
    """
    Returns a lightweight summary of all passages.
    Used to let the learner choose a passage by difficulty.
    """
    passages = load_reading_passages()
    return [
        {
            "passage_id": p["passage_id"],
            "title": p["title"],
            "difficulty": p["difficulty"],
            "topic": p["topic"]
        }
        for p in passages
    ]


# ─── CHECK OBJECTIVE ANSWERS ──────────────────────────────────────────────────

def check_multiple_choice(learner_answer: str, correct_answer: str) -> bool:
    """
    Checks a multiple choice answer.
    Both answers are stripped and uppercased before comparison
    so 'a', 'A', ' A ' all match correctly.
    """
    return learner_answer.strip().upper() == correct_answer.strip().upper()


def check_true_false_ng(learner_answer: str, correct_answer: str) -> bool:
    """
    Checks a True/False/Not Given answer.
    Handles common variations like 'not given', 'NG', 'Not Given'.
    """
    # Normalise both answers to lowercase for comparison
    learner = learner_answer.strip().lower()
    correct = correct_answer.strip().lower()

    # Handle Not Given variations
    ng_variations = ["not given", "ng", "not-given", "notgiven"]

    if correct in ng_variations:
        return learner in ng_variations

    return learner == correct


# ─── EVALUATE SHORT ANSWERS WITH QWEN ────────────────────────────────────────

def evaluate_short_answer(question: str, model_answer: str,
                           learner_answer: str, explanation: str) -> dict:
    """
    Sends a short answer question to Qwen for evaluation.

    Returns a dict with:
    - is_correct (bool)
    - partial_credit (bool)
    - score (0, 1 or 2)
    - feedback (string)
    - skill_demonstrated (string)
    """
    # Load the prompt template
    path = os.path.join(PROMPTS_DIR, "reading_evaluator_prompt.txt")
    with open(path, "r") as f:
        template = f.read()

    full_prompt = template.format(
        question=question,
        model_answer=model_answer,
        learner_answer=learner_answer,
        explanation=explanation
    )

    raw_response = call_qwen_for_json(full_prompt)

    try:
        result = safe_parse_json(raw_response)
    except ValueError:
        try:
            result = extract_json_from_text(raw_response)
        except ValueError:
            # If Qwen fails to return valid JSON, give 0 with a note
            return {
                "is_correct": False,
                "partial_credit": False,
                "score": 0,
                "feedback": "Could not evaluate this answer automatically. Please review manually.",
                "skill_demonstrated": "unknown"
            }

    return result


# ─── EVALUATE A FULL ATTEMPT ──────────────────────────────────────────────────

def evaluate_reading_attempt(passage: dict, learner_answers: dict) -> dict:
    """
    Evaluates a complete reading attempt.

    learner_answers is a dict mapping question_id to the learner's answer string:
    {
        "q1": "B",
        "q2": "C",
        "q4": "True",
        "q8": "Carnegie believed libraries helped poor people educate themselves"
    }

    Returns a structured result with scores and feedback for every question.
    """
    questions = passage["questions"]
    results = []

    total_score = 0
    max_score = 0

    # Track skill performance for memory extraction
    skill_scores = {}

    for question in questions:
        qid = question["question_id"]
        qtype = question["question_type"]
        learner_answer = learner_answers.get(qid, "").strip()
        correct_answer = question["answer"]
        skill = question.get("skill", "unknown")

        if qtype == "multiple_choice":
            max_score += 1
            is_correct = check_multiple_choice(learner_answer, correct_answer)
            score = 1 if is_correct else 0
            total_score += score

            results.append({
                "question_id": qid,
                "question_type": qtype,
                "question": question["question"],
                "learner_answer": learner_answer,
                "correct_answer": correct_answer,
                "is_correct": is_correct,
                "score": score,
                "max_score": 1,
                "feedback": question["explanation"] if not is_correct else "Correct!",
                "skill": skill
            })

        elif qtype == "true_false_ng":
            max_score += 1
            is_correct = check_true_false_ng(learner_answer, correct_answer)
            score = 1 if is_correct else 0
            total_score += score

            results.append({
                "question_id": qid,
                "question_type": qtype,
                "question": question["question"],
                "learner_answer": learner_answer,
                "correct_answer": correct_answer,
                "is_correct": is_correct,
                "score": score,
                "max_score": 1,
                "feedback": question["explanation"] if not is_correct else "Correct!",
                "skill": skill
            })

        elif qtype == "short_answer":
            max_score += 2

            if not learner_answer:
                # Learner left it blank
                results.append({
                    "question_id": qid,
                    "question_type": qtype,
                    "question": question["question"],
                    "learner_answer": "",
                    "correct_answer": correct_answer,
                    "is_correct": False,
                    "score": 0,
                    "max_score": 2,
                    "feedback": "No answer provided.",
                    "skill": skill
                })
            else:
                # Send to Qwen for evaluation
                eval_result = evaluate_short_answer(
                    question=question["question"],
                    model_answer=correct_answer,
                    learner_answer=learner_answer,
                    explanation=question["explanation"]
                )

                score = eval_result.get("score", 0)
                total_score += score

                results.append({
                    "question_id": qid,
                    "question_type": qtype,
                    "question": question["question"],
                    "learner_answer": learner_answer,
                    "correct_answer": correct_answer,
                    "is_correct": eval_result.get("is_correct", False),
                    "partial_credit": eval_result.get("partial_credit", False),
                    "score": score,
                    "max_score": 2,
                    "feedback": eval_result.get("feedback", ""),
                    "skill": skill
                })

        # Track skill performance
        if skill not in skill_scores:
            skill_scores[skill] = {"earned": 0, "possible": 0}

        q_result = results[-1]
        skill_scores[skill]["earned"] += q_result["score"]
        skill_scores[skill]["possible"] += q_result["max_score"]

    # Calculate percentage score
    percentage = round((total_score / max_score) * 100) if max_score > 0 else 0

    # Build skill accuracy summary
    skill_accuracy = {}
    for skill, data in skill_scores.items():
        if data["possible"] > 0:
            skill_accuracy[skill] = round(
                (data["earned"] / data["possible"]) * 100
            )

    return {
        "passage_id": passage["passage_id"],
        "passage_title": passage["title"],
        "difficulty": passage["difficulty"],
        "total_score": total_score,
        "max_score": max_score,
        "percentage": percentage,
        "skill_accuracy": skill_accuracy,
        "question_results": results
    }