"""
Build an indicative Writing calibration set from the writing9 corpus.

Source: https://huggingface.co/datasets/ndtran0101/writing9-ielts-essays
(essays and scores from writing9.com — credit them). Labels are crowd/site
scores, not examiner marks, and the licence is unknown: internal research use
only, never redistribute. Results from this set are indicative, not proof of
accuracy.

    curl -L -o evaluation/writing/data/writing9/download/test.jsonl \
      https://huggingface.co/datasets/ndtran0101/writing9-ielts-essays/resolve/main/data/test.jsonl
    python3 scripts/build_writing9_sample.py \
      evaluation/writing/data/writing9/download/test.jsonl evaluation/writing/data/writing9

Writes essays.csv and ratings.csv (rater_id "writing9") in the harness format.
"""
import csv
import json
import os
import random
import sys
from collections import defaultdict

BANDS = [5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0]
PER_BAND = 22
DEV_SHARE = 0.4
MIN_WORDS = 150
SEED = 20261024
SUB_BANDS = {
    "task_response": "band_task",
    "coherence_cohesion": "band_coherence",
    "lexical_resource": "band_lexical",
    "grammatical_range_accuracy": "band_grammar",
}


def _is_half_band(value) -> bool:
    return isinstance(value, (int, float)) and 0 <= value <= 9 and float(value * 2).is_integer()


def eligible(row: dict) -> bool:
    return (
        row.get("task_type") == "essay"
        and (row.get("word_count") or 0) >= MIN_WORDS
        and (row.get("question") or "").strip()
        and (row.get("essay") or "").strip()
        and row.get("band_overall") in BANDS
        and all(_is_half_band(row.get(field)) for field in SUB_BANDS.values())
    )


def main(source: str, out_dir: str) -> None:
    by_band = defaultdict(list)
    seen = set()
    with open(source, encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            key = (row.get("question", "").strip(), row.get("essay", "").strip())
            if eligible(row) and key not in seen:
                seen.add(key)
                by_band[row["band_overall"]].append(row)

    rng = random.Random(SEED)
    essays, ratings = [], []
    for band in BANDS:
        pool = sorted(by_band[band], key=lambda r: r["id"])
        picked = rng.sample(pool, min(PER_BAND, len(pool)))
        n_dev = round(len(picked) * DEV_SHARE)
        for i, row in enumerate(picked):
            essay_id = f"W9-{row['id'][-10:]}"
            essays.append({
                "essay_id": essay_id, "split": "dev" if i < n_dev else "test", "task": "task2",
                "task_type": row.get("question_type") or "", "prompt": row["question"].strip(),
                "essay": row["essay"].strip(), "source": "writing9", "writer_consent": "n/a",
                "notes": f"writing9 site score {band}; crowd label, indicative only",
            })
            ratings.append({
                "essay_id": essay_id, "rater_id": "writing9",
                **{c: row[field] for c, field in SUB_BANDS.items()},
                "overall": row["band_overall"],
                "justification": "writing9.com site score",
            })

    os.makedirs(out_dir, exist_ok=True)
    for name, rows in (("essays.csv", essays), ("ratings.csv", ratings)):
        with open(os.path.join(out_dir, name), "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    dev = sum(e["split"] == "dev" for e in essays)
    print(f"Wrote {len(essays)} essays ({dev} dev, {len(essays) - dev} test) to {out_dir}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
