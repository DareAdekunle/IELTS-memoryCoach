"""The skill rank-up rules (CLAUDE.md §5). Changing these needs a product decision."""
import pytest

from app.services.memory_service import apply_skill_classification, get_skill_rank
from app.services.skill_taxonomy_service import get_all_skill_ids

LEARNER = "learner-ranks"
SECTION = "Writing"

STRENGTH = "demonstrated_strength"
WEAKNESS = "demonstrated_weakness"
NOT_APPLICABLE = "not_applicable"


@pytest.fixture
def skill():
    return get_all_skill_ids(SECTION)[0]


def apply(skill, *classifications):
    for c in classifications:
        apply_skill_classification(LEARNER, SECTION, skill, c)
    return get_skill_rank(LEARNER, SECTION, skill)


def test_new_skill_starts_at_rank_1(skill):
    rank = get_skill_rank(LEARNER, SECTION, skill)
    assert (rank["current_rank"], rank["clean_streak"]) == (1, 0)


def test_three_consecutive_strengths_rank_up_and_reset_streak(skill):
    assert apply(skill, STRENGTH, STRENGTH)["current_rank"] == 1
    rank = apply(skill, STRENGTH)
    assert (rank["current_rank"], rank["clean_streak"]) == (2, 0)


def test_weakness_fully_resets_streak(skill):
    rank = apply(skill, STRENGTH, STRENGTH, WEAKNESS)
    assert (rank["current_rank"], rank["clean_streak"]) == (1, 0)
    # The streak restarts from zero: two more strengths are not enough.
    assert apply(skill, STRENGTH, STRENGTH)["current_rank"] == 1
    assert apply(skill, STRENGTH)["current_rank"] == 2


def test_not_applicable_changes_nothing(skill):
    before = apply(skill, STRENGTH, STRENGTH)
    after = apply(skill, NOT_APPLICABLE)
    assert (after["current_rank"], after["clean_streak"]) == (before["current_rank"], before["clean_streak"])


def test_rank_caps_at_5(skill):
    rank = apply(skill, *[STRENGTH] * 12)
    assert rank["current_rank"] == 5
    assert apply(skill, *[STRENGTH] * 3)["current_rank"] == 5


def test_rank_never_decreases(skill):
    assert apply(skill, STRENGTH, STRENGTH, STRENGTH)["current_rank"] == 2
    assert apply(skill, WEAKNESS, WEAKNESS, WEAKNESS)["current_rank"] == 2
