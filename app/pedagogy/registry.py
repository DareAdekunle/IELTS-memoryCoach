"""
app/pedagogy/registry.py

Pedagogical Skill Registry — loads the 16 section frameworks and the
4-part Shared Pedagogical Spine from app/data/pedagogical_frameworks.json
and answers role/eligibility questions deterministically.

The registry is data, not behaviour: Python selects the teaching
method; Qwen generates and delivers the teaching.
"""

import os
import json
from functools import lru_cache

from app.pedagogy.stages import LearnerStage, FrameworkRole

DATA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "data",
    "pedagogical_frameworks.json"
)


@lru_cache(maxsize=1)
def _load() -> dict:
    with open(DATA_PATH, "r") as f:
        return json.load(f)


def get_framework(framework_id: str) -> dict | None:
    """Returns the full framework definition, or None."""
    for fw in _load()["frameworks"]:
        if fw["id"] == framework_id:
            return fw
    return None


def get_frameworks_for_section(section: str) -> list:
    """All framework definitions for one IELTS section."""
    return [fw for fw in _load()["frameworks"] if fw["section"] == section]


def get_framework_role(framework_id: str, stage: LearnerStage) -> FrameworkRole:
    """The role a framework plays at a given learner stage."""
    fw = get_framework(framework_id)
    if not fw:
        return FrameworkRole.RETIRED
    role = fw["roles_by_stage"].get(stage.value, "retired")
    return FrameworkRole(role)


def get_role_weight(role: FrameworkRole) -> float:
    return _load()["role_weights"].get(role.value, 0.0)


def get_dominant_frameworks(section: str, stage: LearnerStage) -> list:
    """Framework ids that are dominant for this section at this stage."""
    return [
        fw["id"] for fw in get_frameworks_for_section(section)
        if fw["roles_by_stage"].get(stage.value) == "dominant"
    ]


def get_supporting_frameworks(section: str, stage: LearnerStage) -> list:
    """Framework ids that are supporting (or introduced) at this stage."""
    return [
        fw["id"] for fw in get_frameworks_for_section(section)
        if fw["roles_by_stage"].get(stage.value) in ("supporting", "introduced")
    ]


def get_shared_spine() -> list:
    """The four permanent teaching habits — active at every stage."""
    return _load()["shared_spine"]


def get_all_framework_ids() -> list:
    return [fw["id"] for fw in _load()["frameworks"]]
