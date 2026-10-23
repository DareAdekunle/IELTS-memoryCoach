"""
Writing assessment calibration: compare BandUp's band scorer with human raters.

    docker exec ielts-api-dev python scripts/eval_writing.py --data evaluation/writing/data
    docker exec ielts-api-dev python scripts/eval_writing.py --data evaluation/writing/data --split test
    docker exec ielts-api-dev python scripts/eval_writing.py --data evaluation/writing/data --raters-only

The data folder holds essays.csv and ratings.csv (templates and the rating
protocol are in evaluation/writing/). Model scores are cached in
<data>/model_scores.jsonl keyed by essay, model and prompt version, so
re-runs only pay for new essays or a changed prompt. Each run writes
report.md and per_essay.csv to <data>/results/<timestamp>_<split>/.

Tune prompts on the dev split only; report the test split.
"""
import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from statistics import mean

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from evaluation.metrics import inter_rater, summarise  # noqa: E402

CRITERIA = ["task_response", "coherence_cohesion", "lexical_resource", "grammatical_range_accuracy"]
CRITERION_NAMES = {
    "task_response": "Task Response",
    "coherence_cohesion": "Coherence & Cohesion",
    "lexical_resource": "Lexical Resource",
    "grammatical_range_accuracy": "Grammatical Range & Accuracy",
}
TARGET_WITHIN_HALF_BAND = 0.80
MIN_ITEMS_FOR_KAPPA = 5
BUCKETS = [("≤ 5.0", lambda b: b <= 5.0), ("5.5 – 6.5", lambda b: 5.5 <= b <= 6.5), ("≥ 7.0", lambda b: b >= 7.0)]


class DataError(ValueError):
    pass


# ─── Loading ──────────────────────────────────────────────────────────────────

def load_essays(path: str) -> dict:
    essays = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            essay_id = (row.get("essay_id") or "").strip()
            if not essay_id:
                continue
            if essay_id in essays:
                raise DataError(f"essays.csv: duplicate essay_id {essay_id}")
            if (row.get("writer_consent") or "").strip().lower() == "no":
                continue  # never evaluate an essay without the writer's consent
            split = (row.get("split") or "").strip().lower()
            if split not in ("dev", "test"):
                raise DataError(f"essays.csv: {essay_id} has split {split!r}; use dev or test")
            essays[essay_id] = {**row, "essay_id": essay_id, "split": split}
    return essays


def load_ratings(path: str, essays: dict) -> dict:
    """Returns {essay_id: {rater_id: {criterion: int band}}}."""
    ratings = defaultdict(dict)
    with open(path, newline="", encoding="utf-8") as f:
        for line, row in enumerate(csv.DictReader(f), start=2):
            essay_id = (row.get("essay_id") or "").strip()
            rater = (row.get("rater_id") or "").strip()
            if not essay_id:
                continue
            if essay_id not in essays:
                continue  # unknown or no-consent essay
            if not any((row.get(c) or "").strip() for c in CRITERIA):
                continue  # rater declined to score (unreadable / not a genuine attempt)
            bands = {}
            for c in CRITERIA:
                raw = (row.get(c) or "").strip()
                try:
                    band = float(raw)
                except ValueError:
                    raise DataError(f"ratings.csv line {line}: {c} = {raw!r} is not a number") from None
                if not band.is_integer() or not 0 <= band <= 9:
                    raise DataError(f"ratings.csv line {line}: {c} must be a whole band 0-9, got {raw}")
                bands[c] = int(band)
            if rater in ratings[essay_id]:
                raise DataError(f"ratings.csv line {line}: {rater} rated {essay_id} twice")
            ratings[essay_id][rater] = bands
    return dict(ratings)


# ─── Scoring (cached) ─────────────────────────────────────────────────────────

def _cache_key(essay_id: str, model: str, version: str) -> str:
    return f"{essay_id}|{model}|{version}"


def load_cache(path: str) -> dict:
    cache = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    entry = json.loads(line)
                    cache[_cache_key(entry["essay_id"], entry["model"], entry["prompt_version"])] = entry
    return cache


def score_essays(essays: list, cache_path: str, rescore: bool = False) -> tuple[dict, list]:
    from app.services import band_scoring_service as scorer

    version = scorer.prompt_version()
    cache = {} if rescore else load_cache(cache_path)
    scores, failures = {}, []
    for i, essay in enumerate(essays, 1):
        key = _cache_key(essay["essay_id"], scorer.QWEN_MODEL, version)
        if key in cache:
            scores[essay["essay_id"]] = cache[key]
            continue
        print(f"  scoring {i}/{len(essays)}: {essay['essay_id']}", flush=True)
        try:
            result = scorer.score_writing_bands(essay["prompt"], essay["essay"])
        except Exception as e:  # recorded and reported, never silently scored
            failures.append({"essay_id": essay["essay_id"], "error": str(e)[:200]})
            continue
        entry = {"essay_id": essay["essay_id"], **result}
        with open(cache_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        scores[essay["essay_id"]] = entry
    return scores, failures


# ─── Analysis ─────────────────────────────────────────────────────────────────

def reference_scores(ratings: dict) -> dict:
    """Mean of raters per criterion, plus the mean of each rater's task band."""
    from app.services.band_scoring_service import overall_band
    ref = {}
    for essay_id, by_rater in ratings.items():
        ref[essay_id] = {c: mean(r[c] for r in by_rater.values()) for c in CRITERIA}
        ref[essay_id]["overall"] = mean(overall_band(r) for r in by_rater.values())
        ref[essay_id]["raters"] = len(by_rater)
    return ref


def rater_agreement(ratings: dict) -> dict:
    from app.services.band_scoring_service import overall_band
    out = {}
    for field in CRITERIA + ["overall"]:
        by_rater = defaultdict(dict)
        for essay_id, raters in ratings.items():
            for rater, bands in raters.items():
                by_rater[rater][essay_id] = overall_band(bands) if field == "overall" else bands[field]
        out[field] = inter_rater(by_rater)
    return out


def model_agreement(model_scores: dict, ref: dict) -> dict:
    ids = sorted(set(model_scores) & set(ref))
    if not ids:
        return {}
    out = {}
    for field in CRITERIA + ["overall"]:
        predicted = [model_scores[i]["overall"] if field == "overall" else model_scores[i]["criteria"][field] for i in ids]
        out[field] = summarise(predicted, [ref[i][field] for i in ids])
    out["buckets"] = {}
    for label, test in BUCKETS:
        bucket = [i for i in ids if test(ref[i]["overall"])]
        if bucket:
            out["buckets"][label] = summarise([model_scores[i]["overall"] for i in bucket], [ref[i]["overall"] for i in bucket])
    return out


# ─── Report ───────────────────────────────────────────────────────────────────

def _pct(x):
    return f"{x * 100:.0f}%"


def _row(name, s):
    if not s or s.get("pairs") == 0:
        return f"| {name} | – | – | – | – | – | – |"
    qwk = f"{s['qwk']:.2f}" if s["n"] >= MIN_ITEMS_FOR_KAPPA else "–"  # kappa is noise on a handful of items
    return (f"| {name} | {s['n']} | {s['mae']:.2f} | {s['bias']:+.2f} | "
            f"{_pct(s['within_0.5'])} | {_pct(s['within_1.0'])} | {qwk} |")


def build_report(split, essays, ratings, raters, model, failures, model_scores, version, model_name) -> str:
    rated = [e for e in essays if e in ratings]
    lines = [
        f"# Writing calibration report — {split} split",
        "",
        f"Generated {datetime.now():%Y-%m-%d %H:%M}. "
        f"Essays: {len(essays)} · with ratings: {len(rated)} · "
        f"raters per essay: {mean(len(ratings[e]) for e in rated) if rated else 0:.1f}",
        "",
        "## Rater agreement (the ceiling)",
        "",
        "How closely the human raters agree with each other, averaged over rater pairs. "
        "BandUp cannot be held to a tighter standard than this.",
        "",
        "| Criterion | n | MAE | Bias | Within ±0.5 | Within ±1.0 | QWK |",
        "|---|---|---|---|---|---|---|",
    ]
    lines += [_row(CRITERION_NAMES.get(f, "Overall (task band)"), raters.get(f)) for f in CRITERIA + ["overall"]]

    if model is None:
        lines += ["", "_Model scoring skipped (--raters-only)._"]
        return "\n".join(lines) + "\n"

    lines += [
        "",
        f"## BandUp vs rater average — `{model_name}`, prompt `{version}`",
        "",
        "Bias > 0 means BandUp scores more generously than the raters.",
        "",
        "| Criterion | n | MAE | Bias | Within ±0.5 | Within ±1.0 | QWK |",
        "|---|---|---|---|---|---|---|",
    ]
    lines += [_row(CRITERION_NAMES.get(f, "Overall (task band)"), model.get(f)) for f in CRITERIA + ["overall"]]

    if model.get("overall"):
        hit = model["overall"]["within_0.5"]
        verdict = "PASS" if hit >= TARGET_WITHIN_HALF_BAND else "FAIL"
        note = "" if split == "test" else " _(dev split — tune here, report the test split)_"
        lines += ["", f"**Target:** overall within ±0.5 on ≥{_pct(TARGET_WITHIN_HALF_BAND)} → "
                      f"**{_pct(hit)} — {verdict}**{note}"]

    if model.get("buckets"):
        lines += ["", "### By reference band", "", "| Reference band | n | MAE | Bias | Within ±0.5 | Within ±1.0 | QWK |",
                  "|---|---|---|---|---|---|---|"]
        lines += [_row(label, s) for label, s in model["buckets"].items()]

    if failures:
        lines += ["", f"### Scoring failures ({len(failures)})", ""]
        lines += [f"- `{f['essay_id']}`: {f['error']}" for f in failures]

    return "\n".join(lines) + "\n"


def write_per_essay(path, essays, ref, model_scores):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["essay_id", "split", "raters", "ref_overall", "model_overall", "diff"]
                   + [f"ref_{c}" for c in CRITERIA] + [f"model_{c}" for c in CRITERIA])
        rows = []
        for e in essays:
            r, m = ref.get(e["essay_id"]), model_scores.get(e["essay_id"])
            diff = (m["overall"] - r["overall"]) if (r and m) else None
            rows.append((abs(diff) if diff is not None else -1, [
                e["essay_id"], e["split"], r["raters"] if r else 0,
                f"{r['overall']:.2f}" if r else "", m["overall"] if m else "",
                f"{diff:+.2f}" if diff is not None else "",
                *[f"{r[c]:.2f}" if r else "" for c in CRITERIA],
                *[m["criteria"][c] if m else "" for c in CRITERIA],
            ]))
        for _, row in sorted(rows, key=lambda x: -x[0]):  # biggest disagreements first
            w.writerow(row)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main(argv=None) -> str:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", required=True, help="folder with essays.csv and ratings.csv")
    parser.add_argument("--split", choices=["dev", "test", "all"], default="dev")
    parser.add_argument("--raters-only", action="store_true", help="report rater agreement only; no API calls")
    parser.add_argument("--rescore", action="store_true", help="ignore cached model scores")
    parser.add_argument("--limit", type=int, help="score at most N essays (cost control)")
    args = parser.parse_args(argv)

    all_essays = load_essays(os.path.join(args.data, "essays.csv"))
    ratings = load_ratings(os.path.join(args.data, "ratings.csv"), all_essays)
    essays = [e for e in all_essays.values() if args.split == "all" or e["split"] == args.split]
    essay_ids = {e["essay_id"] for e in essays}
    split_ratings = {k: v for k, v in ratings.items() if k in essay_ids}

    raters = rater_agreement(split_ratings)
    ref = reference_scores(split_ratings)

    model, failures, model_scores, version, model_name = None, [], {}, "", ""
    if not args.raters_only:
        from app.services import band_scoring_service as scorer
        version, model_name = scorer.prompt_version(), scorer.QWEN_MODEL
        to_score = [e for e in essays if e["essay_id"] in ref][: args.limit]
        print(f"Scoring {len(to_score)} rated essays ({args.split}) with {model_name}, prompt {version}")
        model_scores, failures = score_essays(to_score, os.path.join(args.data, "model_scores.jsonl"), args.rescore)
        model = model_agreement(model_scores, ref)

    report = build_report(args.split, essay_ids, split_ratings, raters, model, failures, model_scores, version, model_name)

    out_dir = os.path.join(args.data, "results", f"{datetime.now():%Y%m%d-%H%M%S}_{args.split}")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write(report)
    write_per_essay(os.path.join(out_dir, "per_essay.csv"), essays, ref, model_scores)
    print(report)
    print(f"Wrote {out_dir}/report.md and per_essay.csv")
    return out_dir


if __name__ == "__main__":
    try:
        main()
    except DataError as e:
        sys.exit(f"Data error: {e}")
