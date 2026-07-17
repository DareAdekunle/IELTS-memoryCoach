import os
import sys
import json
import random

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.services.qwen_service import call_qwen_for_json
from app.utils.json_utils import safe_parse_json, extract_json_from_text

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")


def load_reading_passages() -> list:
    path = os.path.join(DATA_DIR, "reading_passages.json")
    with open(path, "r") as f:
        return json.load(f)


def get_random_passage(difficulty: str = None) -> dict:
    """Returns a random reading passage, optionally filtered by difficulty."""
    passages = load_reading_passages()
    if difficulty:
        passages = [p for p in passages if p["difficulty"] == difficulty]
    if not passages:
        raise ValueError(f"No passages found for difficulty: {difficulty}")
    return random.choice(passages)


def get_adaptive_passage(learner_id: str) -> dict:
    """
    Returns an unseen reading passage matched to the learner's band level.
    Cycles back through seen passages only when all at the level are exhausted.
    """
    from app.services.practice_service import get_adaptive_difficulty, _get_unseen_or_cycle
    difficulty = get_adaptive_difficulty(learner_id, "Reading")
    passages = load_reading_passages()
    filtered = [p for p in passages if p["difficulty"] == difficulty]
    if not filtered:
        filtered = passages
    return _get_unseen_or_cycle(filtered, learner_id, "Reading", "passage_id")


def get_passage_by_id(passage_id: str) -> dict | None:
    passages = load_reading_passages()
    for p in passages:
        if p["passage_id"] == passage_id:
            return p
    return None


def get_all_passages_summary() -> list:
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


def check_multiple_choice(learner_answer: str, correct_answer: str) -> bool:
    return learner_answer.strip().upper() == correct_answer.strip().upper()


def check_true_false_ng(learner_answer: str, correct_answer: str) -> bool:
    learner = learner_answer.strip().lower()
    correct = correct_answer.strip().lower()
    ng_variations = ["not given", "ng", "not-given", "notgiven"]
    if correct in ng_variations:
        return learner in ng_variations
    return learner == correct


def evaluate_short_answer(question: str, model_answer: str,
                          learner_answer: str, explanation: str) -> dict:
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
            return {
                "is_correct": False,
                "partial_credit": False,
                "score": 0,
                "feedback": "Could not evaluate this answer automatically.",
                "skill_demonstrated": "unknown"
            }

    return result


def evaluate_reading_attempt(passage: dict, learner_answers: dict) -> dict:
    questions = passage["questions"]
    results = []
    total_score = 0
    max_score = 0
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

        if skill not in skill_scores:
            skill_scores[skill] = {"earned": 0, "possible": 0}
        q_result = results[-1]
        skill_scores[skill]["earned"] += q_result["score"]
        skill_scores[skill]["possible"] += q_result["max_score"]

    percentage = round((total_score / max_score) * 100) if max_score > 0 else 0

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
