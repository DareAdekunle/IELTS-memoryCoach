"""Band scorer validation, agreement metrics, and the calibration harness end to end."""
import csv
import json
import os
import shutil
import sys

import pytest

import app.services.band_scoring_service as scorer
from conftest import FakeLLM, reply
from evaluation.metrics import inter_rater, quadratic_weighted_kappa, summarise

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))
import eval_writing  # noqa: E402

EXAMPLES = os.path.join(os.path.dirname(os.path.dirname(__file__)), "evaluation", "writing", "examples")


def band_reply(tr=6, cc=6, lr=6, gra=6):
    return reply(json.dumps({
        "task_response": {"band": tr, "justification": "x"},
        "coherence_cohesion": {"band": cc, "justification": "x"},
        "lexical_resource": {"band": lr, "justification": "x"},
        "grammatical_range_accuracy": {"band": gra, "justification": "x"},
    }))


# ─── Scorer ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("value,expected", [(6.0, 6.0), (6.125, 6.0), (6.25, 6.5), (6.5, 6.5), (6.75, 7.0), (5.875, 6.0)])
def test_ielts_rounding(value, expected):
    assert scorer.ielts_round(value) == expected


def test_overall_band_is_rounded_mean():
    assert scorer.overall_band({"task_response": 6, "coherence_cohesion": 6,
                                "lexical_resource": 7, "grammatical_range_accuracy": 6}) == 6.5


def test_scorer_returns_bands_and_version(monkeypatch):
    fake = FakeLLM(band_reply(7, 6, 6, 5))
    monkeypatch.setattr(scorer, "client", fake)
    result = scorer.score_writing_bands("Prompt", "word " * 260)

    assert result["criteria"]["task_response"] == 7
    assert result["overall"] == 6.0
    assert result["prompt_version"] == scorer.prompt_version()
    assert fake.calls[0]["temperature"] == 0
    assert "260 words" in fake.calls[0]["messages"][0]["content"]


@pytest.mark.parametrize("bad", [10, -1, 6.5, "6", True, None])
def test_invalid_bands_are_rejected_not_guessed(bad):
    raw = json.loads(band_reply().choices[0].message.content)
    raw["lexical_resource"]["band"] = bad
    with pytest.raises(scorer.InvalidBandScore):
        scorer.parse_band_reply(json.dumps(raw))


def test_missing_criterion_is_rejected():
    raw = json.loads(band_reply().choices[0].message.content)
    del raw["task_response"]
    with pytest.raises(scorer.InvalidBandScore):
        scorer.parse_band_reply(json.dumps(raw))


def test_whole_number_floats_are_accepted():
    raw = json.loads(band_reply().choices[0].message.content)
    raw["task_response"]["band"] = 7.0
    assert scorer.parse_band_reply(json.dumps(raw))["criteria"]["task_response"] == 7


# ─── Metrics ──────────────────────────────────────────────────────────────────

def test_qwk_perfect_and_opposite():
    assert quadratic_weighted_kappa([5, 6, 7, 8], [5, 6, 7, 8]) == pytest.approx(1.0)
    assert quadratic_weighted_kappa([5, 6, 7, 8], [8, 7, 6, 5]) < 0


def test_summary_counts_tolerances_and_bias():
    s = summarise([6.0, 7.0, 5.0], [6.0, 6.5, 6.0])
    assert s["within_0.5"] == pytest.approx(2 / 3)
    assert s["within_1.0"] == pytest.approx(1.0)
    assert s["bias"] == pytest.approx((0 + 0.5 - 1) / 3)
    assert s["mae"] == pytest.approx(0.5)


def test_inter_rater_uses_only_shared_items():
    s = inter_rater({"R1": {"a": 6, "b": 7, "c": 5}, "R2": {"a": 6, "b": 7}})
    assert s["pairs"] == 1 and s["n"] == 2 and s["exact"] == 1.0


# ─── Harness ──────────────────────────────────────────────────────────────────

@pytest.fixture
def data_dir(tmp_path):
    for name in ("essays.csv", "ratings.csv"):
        shutil.copy(os.path.join(EXAMPLES, name), tmp_path / name)
    return tmp_path


def test_harness_end_to_end_and_caches_scores(data_dir, monkeypatch):
    fake = FakeLLM(band_reply(6, 6, 6, 6))
    monkeypatch.setattr(scorer, "client", fake)

    out = eval_writing.main(["--data", str(data_dir), "--split", "all"])
    report = open(os.path.join(out, "report.md")).read()
    rows = list(csv.DictReader(open(os.path.join(out, "per_essay.csv"))))

    assert "Rater agreement" in report and "BandUp vs rater average" in report
    assert "**Target:**" in report
    assert len(rows) == 3 and {r["model_overall"] for r in rows} == {"6.0"}
    assert len(fake.calls) == 3

    eval_writing.main(["--data", str(data_dir), "--split", "all"])
    assert len(fake.calls) == 3  # second run served entirely from the cache


def test_raters_only_makes_no_model_calls(data_dir, monkeypatch):
    monkeypatch.setattr(scorer, "client", FakeLLM(reply("should not be called")))
    out = eval_writing.main(["--data", str(data_dir), "--split", "all", "--raters-only"])
    assert "Model scoring skipped" in open(os.path.join(out, "report.md")).read()
    assert scorer.client.calls == []


def test_scoring_failures_are_reported_not_scored(data_dir, monkeypatch):
    monkeypatch.setattr(scorer, "client", FakeLLM(reply("not json at all")))
    out = eval_writing.main(["--data", str(data_dir), "--split", "all"])
    report = open(os.path.join(out, "report.md")).read()
    assert "Scoring failures (3)" in report


def test_no_consent_essays_and_their_ratings_are_skipped(data_dir):
    rows = list(csv.reader(open(data_dir / "essays.csv")))
    rows[1][7] = "no"
    csv.writer(open(data_dir / "essays.csv", "w", newline="")).writerows(rows)
    essays = eval_writing.load_essays(str(data_dir / "essays.csv"))
    ratings = eval_writing.load_ratings(str(data_dir / "ratings.csv"), essays)
    assert rows[1][0] not in essays and rows[1][0] not in ratings


def test_bad_rating_is_a_data_error(data_dir):
    with open(data_dir / "ratings.csv", "a", newline="") as f:
        csv.writer(f).writerow(["SYN-MID", "R3", 6.5, 6, 6, 6, "half band"])
    essays = eval_writing.load_essays(str(data_dir / "essays.csv"))
    with pytest.raises(eval_writing.DataError):
        eval_writing.load_ratings(str(data_dir / "ratings.csv"), essays)


def test_blank_rating_row_is_skipped(data_dir):
    with open(data_dir / "ratings.csv", "a", newline="") as f:
        csv.writer(f).writerow(["SYN-MID", "R3", "", "", "", "", "unreadable"])
    essays = eval_writing.load_essays(str(data_dir / "essays.csv"))
    assert "R3" not in eval_writing.load_ratings(str(data_dir / "ratings.csv"), essays)["SYN-MID"]
