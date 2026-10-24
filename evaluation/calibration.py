"""
Post-hoc calibration of model band scores (pure functions, no I/O).

The scorer ranks essays reasonably but compresses the scale (e.g. nothing
above 6.5). A calibration table maps each raw model score to the average
reference band seen for it on the dev split. Isotonic (monotonic) fitting
keeps the order the model produced: a higher raw score never maps lower.
"""


def fit_isotonic(raw: list[float], reference: list[float]) -> list[list[float]]:
    """
    Pool-adjacent-violators on the distinct raw values.
    Returns [[raw_value, calibrated_value], ...] sorted by raw_value.
    """
    groups: dict[float, list[float]] = {}
    for x, y in zip(raw, reference):
        groups.setdefault(x, []).append(y)
    # blocks: [x_values, sum_y, count]
    blocks = [[[x], sum(ys), len(ys)] for x, ys in sorted(groups.items())]
    i = 0
    while i < len(blocks) - 1:
        a, b = blocks[i], blocks[i + 1]
        if a[1] / a[2] > b[1] / b[2]:  # violates monotonicity -> merge
            blocks[i] = [a[0] + b[0], a[1] + b[1], a[2] + b[2]]
            del blocks[i + 1]
            i = max(i - 1, 0)
        else:
            i += 1
    return [[x, block[1] / block[2]] for block in blocks for x in block[0]]


def apply(table: list[list[float]], value: float) -> float:
    """Calibrated value; linear between known raw values, clamped at the ends."""
    xs = [x for x, _ in table]
    ys = [y for _, y in table]
    if value <= xs[0]:
        return ys[0]
    if value >= xs[-1]:
        return ys[-1]
    for (x0, y0), (x1, y1) in zip(table, table[1:]):
        if x0 <= value <= x1:
            return y0 if x1 == x0 else y0 + (y1 - y0) * (value - x0) / (x1 - x0)
    return value
