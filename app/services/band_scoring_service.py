"""
IELTS Writing Task 2 band scorer on the four official criteria (0-9 bands).

Candidate scorer for assessment calibration (scripts/eval_writing.py). The
learner-facing Writing Coach still uses writing_evaluator_prompt.txt (five
custom 1-5 skills); switching production over is a separate decision once
calibration numbers exist.
"""
import hashlib
import math
import os

from app.pedagogy.descriptors import get_band_descriptors, get_criterion_ids, get_criterion_name
from app.services.qwen_service import QWEN_MODEL, client
from app.utils.json_utils import safe_parse_json

CRITERIA = ["task_response", "coherence_cohesion", "lexical_resource", "grammatical_range_accuracy"]

_PROMPT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts", "writing_band_scorer_prompt.txt")


class InvalidBandScore(ValueError):
    """The model's reply could not be read as four bands from 0 to 9."""


def _template() -> str:
    with open(_PROMPT_PATH, encoding="utf-8") as f:
        return f.read()


def prompt_version() -> str:
    """Changes whenever the prompt or descriptors change, so results are never mixed across versions."""
    return hashlib.sha256((_template() + _descriptor_block()).encode()).hexdigest()[:10]


def _descriptor_block() -> str:
    lines = []
    for cid in get_criterion_ids("Writing"):
        lines.append(f"### {get_criterion_name('Writing', cid)} ({cid})")
        for band, text in sorted(get_band_descriptors("Writing", cid).items()):
            lines.append(f"- Band {band}: {text}")
    return "\n".join(lines)


def ielts_round(value: float) -> float:
    """IELTS overall-band rounding: to the nearest half band, with .25 and .75 rounding up."""
    return math.floor(value * 2 + 0.5) / 2


def overall_band(criteria: dict) -> float:
    """Task band from the four criterion bands (mean, IELTS rounding)."""
    return ielts_round(sum(criteria[c] for c in CRITERIA) / len(CRITERIA))


def parse_band_reply(raw: str) -> dict:
    """Validates a scorer reply; raises InvalidBandScore rather than guessing."""
    try:
        data = safe_parse_json(raw)
    except ValueError as e:
        raise InvalidBandScore(f"Reply is not JSON: {e}") from e
    criteria, justifications = {}, {}
    for cid in CRITERIA:
        entry = data.get(cid)
        band = entry.get("band") if isinstance(entry, dict) else None
        if isinstance(band, float) and band.is_integer():
            band = int(band)
        if not isinstance(band, int) or isinstance(band, bool) or not 0 <= band <= 9:
            raise InvalidBandScore(f"{cid}: expected an integer band 0-9, got {band!r}")
        criteria[cid] = band
        justifications[cid] = str(entry.get("justification", ""))
    return {"criteria": criteria, "justifications": justifications}


def score_writing_bands(prompt: str, essay: str) -> dict:
    """
    Scores one Task 2 essay. Returns:
        criteria:       {criterion_id: int band 0-9}
        overall:        task band (float, nearest half)
        justifications: {criterion_id: str}
        model, prompt_version
    Raises InvalidBandScore if the reply can't be validated.
    """
    full_prompt = _template().format(
        prompt=prompt,
        essay=essay,
        word_count=len(essay.split()),
        descriptors=_descriptor_block(),
    )
    response = client.chat.completions.create(
        model=QWEN_MODEL,
        messages=[{"role": "user", "content": full_prompt}],
        temperature=0,
    )
    result = parse_band_reply(response.choices[0].message.content or "")
    result["overall"] = overall_band(result["criteria"])
    result["model"] = QWEN_MODEL
    result["prompt_version"] = prompt_version()
    return result
