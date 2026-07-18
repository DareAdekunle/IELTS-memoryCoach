"""
app/pedagogy/stages.py

Core enums and stage mapping for the Pedagogical Skill Layer.

Four learner stages (per criterion, not per section):
  Foundations          <=5.5   bottleneck: knowledge
  Guided Control        6.0    bottleneck: consistency
  Independent Control  6.5-7.0 bottleneck: control under exam conditions
  Automatization        7.5+   bottleneck: precision

Support levels fade gradually (methods fade); practice conditions
switch at defined gates (conditions switch). See session_policy.py.
"""

from enum import Enum


class LearnerStage(str, Enum):
    FOUNDATIONS = "foundations"
    GUIDED_CONTROL = "guided_control"
    INDEPENDENT_CONTROL = "independent_control"
    AUTOMATIZATION = "automatization"


class SupportLevel(str, Enum):
    FULL = "full"
    PARTIAL = "partial"
    MINIMAL = "minimal"
    NONE = "none"


class FrameworkRole(str, Enum):
    DOMINANT = "dominant"
    SUPPORTING = "supporting"
    INTRODUCED = "introduced"
    FADED = "faded"
    RETIRED = "retired"


STAGE_LABELS = {
    LearnerStage.FOUNDATIONS: "Foundations",
    LearnerStage.GUIDED_CONTROL: "Guided Control",
    LearnerStage.INDEPENDENT_CONTROL: "Independent Control",
    LearnerStage.AUTOMATIZATION: "Automatization",
}

STAGE_BOTTLENECKS = {
    LearnerStage.FOUNDATIONS: "knowledge",
    LearnerStage.GUIDED_CONTROL: "consistency",
    LearnerStage.INDEPENDENT_CONTROL: "control under exam conditions",
    LearnerStage.AUTOMATIZATION: "precision",
}

# Default support level per stage — the starting point before the
# Coach adjusts it based on hint dependency and independent successes.
DEFAULT_SUPPORT_BY_STAGE = {
    LearnerStage.FOUNDATIONS: SupportLevel.FULL,
    LearnerStage.GUIDED_CONTROL: SupportLevel.PARTIAL,
    LearnerStage.INDEPENDENT_CONTROL: SupportLevel.MINIMAL,
    LearnerStage.AUTOMATIZATION: SupportLevel.NONE,
}

SUPPORT_ORDER = [
    SupportLevel.FULL,
    SupportLevel.PARTIAL,
    SupportLevel.MINIMAL,
    SupportLevel.NONE,
]


def band_to_stage(band: float | None) -> LearnerStage:
    """
    Maps an estimated band to a learner stage.

    Cold start: a learner with no evidence (band is None) defaults
    to Foundations — the safest assumption, corrected quickly once
    evidence arrives.
    """
    if band is None:
        return LearnerStage.FOUNDATIONS
    if band <= 5.5:
        return LearnerStage.FOUNDATIONS
    if band <= 6.0:
        return LearnerStage.GUIDED_CONTROL
    if band <= 7.0:
        return LearnerStage.INDEPENDENT_CONTROL
    return LearnerStage.AUTOMATIZATION


def reduce_support(level: SupportLevel) -> SupportLevel:
    """One step less support. NONE stays NONE."""
    idx = SUPPORT_ORDER.index(level)
    return SUPPORT_ORDER[min(idx + 1, len(SUPPORT_ORDER) - 1)]


def restore_support(level: SupportLevel) -> SupportLevel:
    """One step more support. FULL stays FULL."""
    idx = SUPPORT_ORDER.index(level)
    return SUPPORT_ORDER[max(idx - 1, 0)]


def next_target_band(band: float | None) -> float:
    """
    Backward Design target: the next 0.5 step above the current band.
    Cold start targets 5.0. Capped at 9.0.
    """
    if band is None:
        return 5.0
    return min(band + 0.5, 9.0)
