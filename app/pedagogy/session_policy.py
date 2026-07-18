"""
app/pedagogy/session_policy.py

Practice conditions — the binary rules a learner performs under.

Methods fade (support levels, in stages.py); conditions SWITCH at
defined gates. These are enforced by application logic, never by
the language model.

Condition gates by stage:
  Writing:    revision required from Guided Control; timed from
              Independent Control; templates removed from Independent.
  Listening:  unlimited replay → 2 replays → single play;
              transcript during → after → review-only.
  Reading:    untimed → guided timing → full timed sections.
  Speaking:   prepared practice → uninterrupted tasks → strict timing.
"""

from dataclasses import dataclass, asdict

from app.pedagogy.stages import LearnerStage


@dataclass
class PracticeConditions:
    timed: bool = False
    time_limit_seconds: int | None = None
    replay_limit: int | None = None          # None = unlimited (Listening)
    transcript_policy: str = "during"        # during / after / review_only (Listening)
    revision_required: bool = False          # Writing
    templates_allowed: bool = True           # Writing
    retries_allowed: bool = True
    answer_reveal_policy: str = "after_attempt"
    exam_mode: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def conditions_for(section: str, stage: LearnerStage) -> PracticeConditions:
    """Deterministic condition gates per section and stage."""
    c = PracticeConditions()

    if section == "Writing":
        if stage == LearnerStage.FOUNDATIONS:
            pass  # untimed, templates allowed, revision encouraged not required
        elif stage == LearnerStage.GUIDED_CONTROL:
            c.revision_required = True
        elif stage == LearnerStage.INDEPENDENT_CONTROL:
            c.revision_required = True
            c.timed = True
            c.time_limit_seconds = 40 * 60
            c.templates_allowed = False
        else:  # AUTOMATIZATION
            c.timed = True
            c.time_limit_seconds = 40 * 60
            c.templates_allowed = False
            c.exam_mode = True

    elif section == "Listening":
        if stage == LearnerStage.FOUNDATIONS:
            c.replay_limit = None
            c.transcript_policy = "during"
        elif stage == LearnerStage.GUIDED_CONTROL:
            c.replay_limit = 2
            c.transcript_policy = "after"
        elif stage == LearnerStage.INDEPENDENT_CONTROL:
            c.replay_limit = 1
            c.transcript_policy = "review_only"
        else:
            c.replay_limit = 1
            c.transcript_policy = "review_only"
            c.exam_mode = True

    elif section == "Reading":
        if stage == LearnerStage.FOUNDATIONS:
            pass  # untimed
        elif stage == LearnerStage.GUIDED_CONTROL:
            pass  # guided, still untimed
        elif stage == LearnerStage.INDEPENDENT_CONTROL:
            c.timed = True
            c.time_limit_seconds = 20 * 60
        else:
            c.timed = True
            c.time_limit_seconds = 20 * 60
            c.exam_mode = True

    elif section == "Speaking":
        if stage == LearnerStage.FOUNDATIONS:
            c.retries_allowed = True
        elif stage == LearnerStage.GUIDED_CONTROL:
            c.retries_allowed = True   # uninterrupted tasks, post-task review
        elif stage == LearnerStage.INDEPENDENT_CONTROL:
            c.timed = True
            c.retries_allowed = False
        else:
            c.timed = True
            c.retries_allowed = False
            c.exam_mode = True

    return c
