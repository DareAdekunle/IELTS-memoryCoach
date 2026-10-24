# Writing assessment calibration

Measures how closely BandUp's band scorer (`app/services/band_scoring_service.py`)
agrees with qualified human raters on IELTS Writing Task 2. This is Sprint 1
in [`PLAN.md`](../../PLAN.md).

## Files

| File | Purpose |
|---|---|
| `essays.template.csv` | Column layout for essays |
| `ratings.template.csv` | Column layout for ratings (send to raters) |
| `RATER_GUIDE.md` | Rating protocol — send to every rater |
| `examples/` | Three **synthetic** essays with illustrative ratings, for trying the harness. Not evidence of anything. |
| `data/` | Your real essays, ratings and results. **Git-ignored** — it contains people's writing. |

## Free reference data (no recruiting)

Two sources can be built locally. Neither is a full substitute for blind,
calibrated raters, but together they give a usable signal:

| Set | Build | Reference | Caveats |
|---|---|---|---|
| **Official examiner scripts** (10 Task 2 scripts, bands 4–8.5) | Download the two `*-writing-sample-tasks-2023.pdf` files from ielts.org into `data/official/download/`, then `docker exec ielts-api-dev python scripts/build_official_samples.py evaluation/writing/data/official` | Published examiner band (overall only) | Handwritten → transcribed with the app's own vision model, which occasionally corrects a spelling; likely in the model's training data; too few for a pass/fail verdict |
| **writing9 corpus sample** (154 essays, 22 per band 5.0–8.0, dev/test split) | Download `data/test.jsonl` from huggingface.co/datasets/ndtran0101/writing9-ielts-essays into `data/writing9/download/`, then `python3 scripts/build_writing9_sample.py evaluation/writing/data/writing9/download/test.jsonl evaluation/writing/data/writing9` | writing9.com site/crowd scores (overall + criteria) | Not examiner marks; noisy at the extremes (most trustworthy around 5.5–6.0); licence unknown — internal research only, credit writing9.com |

Run the harness on each with `--data evaluation/writing/data/official` or
`.../writing9`. The scorer model can be switched with `BAND_SCORER_MODEL`
(e.g. `docker exec -e BAND_SCORER_MODEL=qwen-max ielts-api-dev python scripts/eval_writing.py ...`);
cached scores are kept per model and prompt version.

When budget allows, one qualified rater scoring 30–40 of the writing9 essays
with `RATER_GUIDE.md` turns this into a real measurement — no new writers needed.

## Running a pilot (20 essays, 2 raters)

1. **Collect essays.** Recruit ~10 writers to write 2 Task 2 essays each on
   the prompts in `app/data/writing_prompts.json`, under exam conditions
   (40 minutes, no AI tools), with written consent to use them for
   evaluation. Put them in `data/essays.csv` using the template columns:
   - `split`: `dev` (~40%, for tuning prompts) or `test` (~60%, locked away
     for the reported number). Assign before anyone looks at scores.
   - `source`: `recruited`, `published` or `community`. Use published
     examiner-rated samples only as rater calibration anchors, never in
     `test` — the model may have seen them during training.
   - `writer_consent`: `yes`, or `n/a` for published samples. Rows marked
     `no` are skipped.
2. **Get ratings.** Send each rater the essays, `RATER_GUIDE.md` and
   `ratings.template.csv`. Calibrate on 5–10 anchors first, then rate blind.
   Combine the returned sheets into `data/ratings.csv`.
3. **Check rater agreement** (no API cost):
   ```bash
   docker exec ielts-api-dev python scripts/eval_writing.py --data evaluation/writing/data --raters-only --split all
   ```
   Large disagreements → adjudicate or add a third rater before going on.
4. **Score and compare on dev** (live API; scores are cached):
   ```bash
   docker exec ielts-api-dev python scripts/eval_writing.py --data evaluation/writing/data --split dev
   ```
   Improve the prompt using the dev results and `per_essay.csv` (largest
   disagreements first). Every prompt change gets a new prompt version, so
   cached scores never mix versions.
5. **Report on test** once, when the prompt is frozen:
   ```bash
   docker exec ielts-api-dev python scripts/eval_writing.py --data evaluation/writing/data --split test
   ```

Try the harness on the synthetic examples (costs a fraction of a cent):

```bash
docker exec ielts-api-dev python scripts/eval_writing.py --data evaluation/writing/examples --split all
```

## What the report shows

- **Rater agreement** — the ceiling: BandUp can't be held to a tighter
  standard than the raters' agreement with each other.
- **BandUp vs rater average**, per criterion and overall:
  - MAE (average band error)
  - Bias (positive means BandUp scores generously)
  - Share within ±0.5 and ±1.0
  - Quadratic weighted kappa
- **Pass/fail** against the Sprint 1 target: overall within ±0.5 on ≥80%.
- **By reference band** — whether errors concentrate at low or high bands.

Overall task band = mean of the four criteria, rounded to the nearest half
band (.25 and .75 round up) — computed the same way for raters and BandUp.
