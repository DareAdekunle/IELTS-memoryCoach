import os
import sys
import json
import random
import io

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import dashscope
from dotenv import load_dotenv

from app.services.answer_matching import check_answer, limit_feedback, public_questions

load_dotenv()

dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")
dashscope.base_http_api_url = "https://dashscope-intl.aliyuncs.com/api/v1"

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

TTS_MODEL = "qwen3-tts-flash"
TTS_VOICE = "Cherry"


# ─── LOAD TRACKS ──────────────────────────────────────────────────────────────

def load_listening_tracks() -> list:
    """
    Loads all listening tracks from the JSON file.
    """
    path = os.path.join(DATA_DIR, "listening_tracks.json")
    with open(path, "r") as f:
        return json.load(f)


def get_all_tracks_summary() -> list:
    """
    Returns a lightweight summary of all tracks.
    Used on the selection screen.
    """
    tracks = load_listening_tracks()
    return [
        {
            "track_id": t["track_id"],
            "part": t["part"],
            "title": t["title"],
            "difficulty": t["difficulty"],
            "question_count": len(t["questions"]),
            "context": t["context"]
        }
        for t in tracks
    ]


def get_track_by_id(track_id: str) -> dict | None:
    """
    Returns a specific track by its ID.
    """
    tracks = load_listening_tracks()
    for t in tracks:
        if t["track_id"] == track_id:
            return t
    return None


def get_random_track(difficulty: str = None, part: int = None) -> dict:
    """
    Returns a random listening track.
    Optionally filtered by difficulty or part number.
    """
    tracks = load_listening_tracks()

    if difficulty:
        tracks = [t for t in tracks if t["difficulty"] == difficulty]
    if part:
        tracks = [t for t in tracks if t["part"] == part]

    if not tracks:
        raise ValueError(
            f"No tracks found for difficulty={difficulty} part={part}"
        )

    return random.choice(tracks)


# ─── GENERATE AUDIO ───────────────────────────────────────────────────────────

def generate_track_audio(track: dict) -> dict:
    """
    Generates audio for a listening track by sending the script
    to Qwen TTS and downloading the resulting audio.

    For scripts with multiple speakers we add speaker labels
    so Cherry reads them naturally with slight pauses between turns.

    Returns a dict with:
    - success (bool)
    - audio_bytes (bytes)
    - error (str)
    """
    script = track["script"]
    speakers = track.get("speakers", [])

    # Format the script for TTS
    # Replace speaker labels with natural pause indicators
    # so Cherry reads it smoothly
    tts_text = _format_script_for_tts(script, speakers)

    try:
        import urllib.request

        response = dashscope.audio.qwen_tts.SpeechSynthesizer.call(
            model=TTS_MODEL,
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            text=tts_text,
            voice=TTS_VOICE
        )

        if response.status_code != 200:
            return {
                "success": False,
                "audio_bytes": None,
                "error": f"TTS API error: {response.message}"
            }

        # Get the audio URL and download it
        audio = response.output.get("audio", {})
        audio_url = audio.get("url", "")

        if not audio_url:
            return {
                "success": False,
                "audio_bytes": None,
                "error": "No audio URL in TTS response"
            }

        # Download the audio
        with urllib.request.urlopen(audio_url, timeout=30) as resp:
            audio_bytes = resp.read()

        return {
            "success": True,
            "audio_bytes": audio_bytes,
            "error": ""
        }

    except Exception as e:
        return {
            "success": False,
            "audio_bytes": None,
            "error": f"Audio generation failed: {str(e)}"
        }


def _format_script_for_tts(script: str, speakers: list) -> str:
    """
    Formats a script for natural TTS reading.

    Converts speaker labels like "Receptionist: Good morning..."
    into a format that sounds natural when read aloud.

    For single speaker scripts (lectures) this just returns the
    script with speaker name stripped.

    For multi-speaker scripts this adds natural pause cues between
    speaker turns.
    """
    lines = script.split("\n")
    formatted_lines = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Check if this line starts with a speaker label
        speaker_found = False
        for speaker in speakers:
            if line.startswith(f"{speaker}:"):
                # Remove the speaker label and add the speech
                speech = line[len(speaker) + 1:].strip()

                if len(speakers) == 1:
                    # Single speaker — just add the text
                    formatted_lines.append(speech)
                else:
                    # Multiple speakers — add a natural pause between turns
                    formatted_lines.append(f"{speech}")

                speaker_found = True
                break

        if not speaker_found:
            formatted_lines.append(line)

    # Join with natural pauses between speaker turns
    if len(speakers) > 1:
        # Use double newlines between turns for natural pacing
        return "\n\n".join(formatted_lines)
    else:
        # Single speaker lecture — single newlines
        return "\n".join(formatted_lines)


# ─── CHECK ANSWERS ────────────────────────────────────────────────────────────

def evaluate_listening_attempt(
    track: dict,
    learner_answers: dict
) -> dict:
    """
    Evaluates a complete listening attempt.

    learner_answers maps question_id to the learner's answer string.

    Returns a structured result with scores and feedback
    for every question.
    """
    questions = track["questions"]
    results = []
    total_score = 0
    max_score = 0
    skill_scores = {}

    for question in questions:
        qid = question["question_id"]
        qtype = question["question_type"]
        learner_answer = learner_answers.get(qid, "").strip()
        correct_answer = question["answer"]
        acceptable = question.get("acceptable_answers", [])
        skill = question.get("skill", "detail_accuracy")

        max_score += 1

        if qtype == "multiple_choice":
            check_result = {
                "is_correct": learner_answer.strip().upper() == correct_answer.strip().upper(),
                "over_limit": False,
            }
        else:
            check_result = check_answer(learner_answer, [correct_answer, *acceptable], question.get("word_limit"))

        is_correct = check_result["is_correct"]
        score = 1 if is_correct else 0
        total_score += score

        # For multiple choice display the full option text
        display_answer = learner_answer
        if qtype == "multiple_choice" and learner_answer:
            options = question.get("options", {})
            option_text = options.get(learner_answer.upper(), "")
            if option_text:
                display_answer = f"{learner_answer.upper()}: {option_text}"

        results.append({
            "question_id": qid,
            "question_type": qtype,
            "question": question["question"],
            "options": question.get("options", {}),
            "learner_answer": display_answer,
            "correct_answer": correct_answer,
            "is_correct": is_correct,
            "score": score,
            "max_score": 1,
            "feedback": (
                "Correct!" if is_correct
                else limit_feedback(question.get("word_limit")) if check_result["over_limit"]
                else question["explanation"]
            ),
            "skill": skill
        })

        # Track skill performance
        if skill not in skill_scores:
            skill_scores[skill] = {"earned": 0, "possible": 0}
        skill_scores[skill]["earned"] += score
        skill_scores[skill]["possible"] += 1

    # Calculate percentage
    percentage = round(
        (total_score / max_score) * 100
    ) if max_score > 0 else 0

    # Build skill accuracy summary
    skill_accuracy = {}
    for skill, data in skill_scores.items():
        if data["possible"] > 0:
            skill_accuracy[skill] = round(
                (data["earned"] / data["possible"]) * 100
            )

    return {
        "track_id": track["track_id"],
        "track_title": track["title"],
        "part": track["part"],
        "difficulty": track["difficulty"],
        "total_score": total_score,
        "max_score": max_score,
        "percentage": percentage,
        "skill_accuracy": skill_accuracy,
        "question_results": results
    }

def get_adaptive_track(learner_id: str) -> dict:
    """
    Returns an unseen listening track matched to the learner's band level.
    Cycles back through seen tracks only when all at the level are exhausted.

    Band → difficulty mapping (same as all other sections):
      avg band < 5.5  → beginner
      avg band 5.5-6.9 → intermediate
      avg band 7.0+    → advanced
    """
    from app.services.practice_service import get_adaptive_difficulty, _get_unseen_or_cycle
    difficulty = get_adaptive_difficulty(learner_id, "Listening")
    tracks = load_listening_tracks()
    filtered = [t for t in tracks if t["difficulty"] == difficulty]
    if not filtered:
        filtered = tracks
    return _get_unseen_or_cycle(filtered, learner_id, "Listening", "track_id")


def public_track(track: dict | None) -> dict | None:
    """Track as sent to the browser before submission: no answer key, no transcript."""
    if track is None:
        return None
    out = {k: v for k, v in track.items() if k != "script"}
    out["questions"] = public_questions(track["questions"])
    return out
