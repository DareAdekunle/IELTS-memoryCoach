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
