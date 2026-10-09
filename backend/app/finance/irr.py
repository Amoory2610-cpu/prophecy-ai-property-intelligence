"""Internal rate of return for annual cash flows."""

from __future__ import annotations

from collections.abc import Sequence


def npv(rate: float, cash_flows: Sequence[float]) -> float:
    return sum(cf / (1 + rate) ** t for t, cf in enumerate(cash_flows))


def irr(cash_flows: Sequence[float], low: float = -0.9999, high: float = 10.0) -> float | None:
    """Annual IRR found by bisection, or ``None`` when no unique sign change exists.

    Bisection is slower than Newton's method but always converges when the NPV
    changes sign across the bracket, which matters for unusual deals (e.g. negative
    cash flow throughout followed by a large sale).
    """
    if not cash_flows or all(cf >= 0 for cf in cash_flows) or all(cf <= 0 for cf in cash_flows):
        return None
    f_low, f_high = npv(low, cash_flows), npv(high, cash_flows)
    if f_low * f_high > 0:
        return None
    for _ in range(200):
        mid = (low + high) / 2
        f_mid = npv(mid, cash_flows)
        if abs(f_mid) < 1e-7 or (high - low) < 1e-10:
            return mid
        if f_low * f_mid < 0:
            high = mid
        else:
            low, f_low = mid, f_mid
    return (low + high) / 2
