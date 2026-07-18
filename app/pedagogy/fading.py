"""
app/pedagogy/fading.py

Deterministic support-fading rules.

Support fades only when there is sufficient evidence; it is restored
immediately on regression. The Coach agent may REQUEST a support
change, but these rules decide whether the change is allowed —
the AI judges the evidence, the engine enforces the rules.
"""

from app.pedagogy.stages import SupportLevel, reduce_support, restore_support

# Evidence thresholds (spec §21)
REDUCE_MIN_SUCCESSES = 3
REDUCE_MAX_AVG_HINT = 1.0
REDUCE_MIN_ACCURACY = 0.8

RESTORE_FAILURE_THRESHOLD = 2   # consecutive failures after a reduction


def should_reduce_support(
    recent_successes: int,
    average_hint_level: float,
    independent_accuracy: float,
) -> bool:
    """
    Support may fade one step only when the learner has repeatedly
    succeeded with weak hints and high independent accuracy.
    """
    return (
        recent_successes >= REDUCE_MIN_SUCCESSES
        and average_hint_level <= REDUCE_MAX_AVG_HINT
        and independent_accuracy >= REDUCE_MIN_ACCURACY
    )


def should_restore_support(
    recent_failures: int,
    last_support_change: str | None,
) -> bool:
    """
    Regression rule: if performance drops after a support reduction,
    restore the previous support level and collect more evidence.
    Never reduce the learner's rank for this.
    """
    return (
        last_support_change == "reduced"
        and recent_failures >= RESTORE_FAILURE_THRESHOLD
    )


def evaluate_support_change(
    current_level: SupportLevel,
    requested_level: SupportLevel,
    recent_successes: int,
    average_hint_level: float,
    independent_accuracy: float,
    recent_failures: int,
    last_support_change: str | None,
) -> dict:
    """
    Guardrail for the Coach's update_criterion_state tool.

    Returns {"allowed": bool, "final_level": str, "reason": str}.
    Only one step of change is ever allowed at a time, and only
    when the evidence rules permit it.
    """
    order = [SupportLevel.FULL, SupportLevel.PARTIAL,
             SupportLevel.MINIMAL, SupportLevel.NONE]
    cur_idx = order.index(current_level)
    req_idx = order.index(requested_level)

    if req_idx == cur_idx:
        return {
            "allowed": True,
            "final_level": current_level.value,
            "reason": "no change requested",
        }

    # Reduction (less support) — must earn it
    if req_idx > cur_idx:
        if not should_reduce_support(
            recent_successes, average_hint_level, independent_accuracy
        ):
            return {
                "allowed": False,
                "final_level": current_level.value,
                "reason": (
                    f"insufficient evidence to reduce support "
                    f"(need >={REDUCE_MIN_SUCCESSES} successes, "
                    f"avg hint <={REDUCE_MAX_AVG_HINT}, "
                    f"accuracy >={REDUCE_MIN_ACCURACY})"
                ),
            }
        final = reduce_support(current_level)  # one step only
        return {
            "allowed": True,
            "final_level": final.value,
            "reason": "evidence supports one-step support reduction",
        }

    # Restoration (more support) — always allowed, one step
    final = restore_support(current_level)
    return {
        "allowed": True,
        "final_level": final.value,
        "reason": "support restored one step (regression or Coach judgement)",
    }
