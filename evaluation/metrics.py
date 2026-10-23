"""Agreement metrics for band scores (pure functions, no I/O)."""
from itertools import combinations
from statistics import mean


def mean_abs_error(predicted: list[float], reference: list[float]) -> float:
    return mean(abs(p - r) for p, r in zip(predicted, reference))


def bias(predicted: list[float], reference: list[float]) -> float:
    """Mean signed error: positive means scoring too generously."""
    return mean(p - r for p, r in zip(predicted, reference))


def within(predicted: list[float], reference: list[float], tolerance: float) -> float:
    """Share of items where |predicted - reference| <= tolerance."""
    return mean(abs(p - r) <= tolerance + 1e-9 for p, r in zip(predicted, reference))


def quadratic_weighted_kappa(a: list[float], b: list[float], step: float = 0.5) -> float:
    """
    Cohen's kappa with quadratic weights, on a band scale discretised by `step`.
    1.0 = perfect agreement, 0 = chance level. Returns 1.0 when both raters
    give one identical constant score (no disagreement to measure).
    """
    xs = [round(v / step) for v in a]
    ys = [round(v / step) for v in b]
    lo, hi = min(xs + ys), max(xs + ys)
    k = hi - lo + 1
    if k == 1:
        return 1.0
    n = len(xs)
    observed = [[0.0] * k for _ in range(k)]
    for x, y in zip(xs, ys):
        observed[x - lo][y - lo] += 1
    row = [sum(observed[i]) for i in range(k)]
    col = [sum(observed[i][j] for i in range(k)) for j in range(k)]
    num = den = 0.0
    for i in range(k):
        for j in range(k):
            w = (i - j) ** 2 / (k - 1) ** 2
            num += w * observed[i][j]
            den += w * row[i] * col[j] / n
    return 1.0 - num / den if den else 1.0


def summarise(predicted: list[float], reference: list[float], tolerances=(0.5, 1.0)) -> dict:
    out = {
        "n": len(predicted),
        "mae": mean_abs_error(predicted, reference),
        "bias": bias(predicted, reference),
        "exact": within(predicted, reference, 0),
        "qwk": quadratic_weighted_kappa(predicted, reference),
    }
    for t in tolerances:
        out[f"within_{t}"] = within(predicted, reference, t)
    return out


def inter_rater(scores_by_rater: dict[str, dict[str, float]], tolerances=(0.5, 1.0)) -> dict:
    """
    Pairwise agreement between raters on the items both rated.
    scores_by_rater: {rater_id: {item_id: score}}. Returns averages over pairs.
    """
    pairs = []
    for r1, r2 in combinations(sorted(scores_by_rater), 2):
        shared = sorted(set(scores_by_rater[r1]) & set(scores_by_rater[r2]))
        if len(shared) >= 2:
            a = [scores_by_rater[r1][i] for i in shared]
            b = [scores_by_rater[r2][i] for i in shared]
            pairs.append(summarise(a, b, tolerances))
    if not pairs:
        return {"pairs": 0}
    keys = [k for k in pairs[0] if k != "n"]
    return {"pairs": len(pairs), "n": sum(p["n"] for p in pairs), **{k: mean(p[k] for p in pairs) for k in keys}}
