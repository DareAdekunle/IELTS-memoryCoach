"""
app/pedagogy/descriptors.py

Band descriptor lookups for Backward Design.

Every Tutor activity must anchor to a band descriptor — this module
answers "what does the learner's current band look like?" and
"what does the next band look like?" for any criterion.
"""

import os
import json
import math
from functools import lru_cache

DATA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "data",
    "band_descriptors.json"
)


@lru_cache(maxsize=1)
def _load() -> dict:
    with open(DATA_PATH, "r") as f:
        return json.load(f)


def get_criterion_ids(section: str) -> list:
    """Criterion ids for a section (matches taxonomy category_ids)."""
    return [k for k in _load().get(section, {}).keys()]


def get_criterion_name(section: str, criterion_id: str) -> str:
    entry = _load().get(section, {}).get(criterion_id)
    return entry["criterion_name"] if entry else criterion_id


def get_descriptor(section: str, criterion_id: str, band: float | None) -> str:
    """
    Descriptor text for the integer band at or below the given band.
    Cold start (band None) returns the band-4 descriptor.
    """
    entry = _load().get(section, {}).get(criterion_id)
    if not entry:
        return ""
    b = 4 if band is None else max(4, min(9, math.floor(band)))
    return entry["descriptors"].get(str(b), "")


def get_target_descriptor(
    section: str,
    criterion_id: str,
    current_band: float | None
) -> tuple:
    """
    The Backward Design target: (target_band, descriptor_text) for
    the next integer band above the learner's current band.
    """
    entry = _load().get(section, {}).get(criterion_id)
    if not entry:
        return (5.0, "")
    if current_band is None:
        target = 5
    else:
        target = max(5, min(9, math.floor(current_band) + 1))
    return (float(target), entry["descriptors"].get(str(target), ""))
