"""
Pick reference ("anchor") essays for the band scorer prompt from the writing9 corpus.

Anchors are drawn from essays NOT in the evaluation sample, so the scorer is
never shown an essay it is later evaluated on. To limit label noise, only
essays whose four criterion bands are all within half a band of the overall
band are eligible; length is kept to 250-320 words to bound prompt size.

    python3 scripts/build_writing9_anchors.py \
      evaluation/writing/data/writing9/download/test.jsonl \
      evaluation/writing/data/writing9/essays.csv \
      evaluation/writing/data/writing9/anchors.json

Then score with: BAND_SCORER_ANCHORS=evaluation/writing/data/writing9/anchors.json
"""
import csv
import json
import random
import sys

ANCHOR_BANDS = [5.5, 6.5, 7.5, 8.5]
SUB_BANDS = {
    "task_response": "band_task",
    "coherence_cohesion": "band_coherence",
    "lexical_resource": "band_lexical",
    "grammatical_range_accuracy": "band_grammar",
}
SEED = 20261024


def consistent(row: dict) -> bool:
    return all(
        isinstance(row.get(f), (int, float)) and abs(row[f] - row["band_overall"]) <= 0.5
        for f in SUB_BANDS.values()
    )


def main(source: str, sample_csv: str, out_path: str) -> None:
    excluded = set()
    with open(sample_csv, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            excluded.add(row["essay"].strip())

    pools = {band: [] for band in ANCHOR_BANDS}
    with open(source, encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            band = row.get("band_overall")
            if (
                band in pools
                and row.get("task_type") == "essay"
                and 250 <= (row.get("word_count") or 0) <= 320
                and consistent(row)
                and row.get("essay", "").strip() not in excluded
            ):
                pools[band].append(row)

    rng = random.Random(SEED)
    anchors, used_types = [], set()
    for band in ANCHOR_BANDS:
        pool = sorted(pools[band], key=lambda r: r["id"])
        rng.shuffle(pool)
        # Prefer a question type not used yet, so anchors span task types
        pick = next((r for r in pool if r.get("question_type") not in used_types), pool[0])
        used_types.add(pick.get("question_type"))
        anchors.append({
            "id": pick["id"], "prompt": pick["question"].strip(), "essay": pick["essay"].strip(),
            "overall": band, "criteria": {c: pick[f] for c, f in SUB_BANDS.items()},
            "question_type": pick.get("question_type"), "source": "writing9.com",
        })
        print(f"band {band}: {pick['id']} ({pick.get('question_type')}, {pick['word_count']} words), "
              f"pool {len(pool)}")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(anchors, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(anchors)} anchors to {out_path}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
