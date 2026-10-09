"""Break-even analysis, sensitivity testing and scenario comparison.

Everything here is derived by re-running the deterministic engine with modified
inputs, so it is fully reproducible and never relies on outside data.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field

from .engine import analyse_deal, year_one
from .inputs import DealInputs

# Field bounds used to clamp adjusted inputs so a scenario never produces an invalid deal.
_BOUNDS: dict[str, tuple[float, float]] = {
    "interest_rate_pct": (0, 25),
    "vacancy_pct": (0, 100),
    "capital_growth_pct": (-20, 20),
    "rent_growth_pct": (-20, 20),
    "cost_inflation_pct": (-20, 20),
    "deposit_pct": (0, 100),
    "management_pct": (0, 50),
    "maintenance_pct": (0, 50),
    "monthly_rent": (0, 1_000_000),
    "purchase_price": (1, 100_000_000),
}


def adjust(inp: DealInputs, **changes: Any) -> DealInputs:
    data = inp.model_dump()
    for key, value in changes.items():
        if key in _BOUNDS:
            lo, hi = _BOUNDS[key]
            value = min(max(value, lo), hi)
        data[key] = value
    return DealInputs.model_validate(data)


def _bisect(f: Callable[[float], float], lo: float, hi: float, iterations: int = 80) -> float:
    """Root of a monotonic ``f`` within ``[lo, hi]``; assumes a sign change exists."""
    f_lo = f(lo)
    for _ in range(iterations):
        mid = (lo + hi) / 2
        f_mid = f(mid)
        if (f_mid > 0) == (f_lo > 0):
            lo, f_lo = mid, f_mid
        else:
            hi = mid
    return (lo + hi) / 2


class BreakEven(BaseModel):
    key: str
    label: str
    value: float | None
    unit: str
    current: float
    explanation: str


def break_even(inp: DealInputs, target_gross_yield_pct: float = 7.0) -> list[BreakEven]:
    def cf(**kw: Any) -> float:
        return year_one(adjust(inp, **kw)).pre_tax_cash_flow

    out: list[BreakEven] = []

    # Rent needed for zero pre-tax cash flow (cash flow increases with rent).
    if cf(monthly_rent=0) >= 0:
        rent = 0.0
    else:
        hi = max(inp.monthly_rent, 100.0)
        while cf(monthly_rent=hi) < 0 and hi < 1_000_000:
            hi = min(hi * 2, 1_000_000)
        rent = _bisect(lambda r: cf(monthly_rent=r), 0, hi) if cf(monthly_rent=hi) >= 0 else None
    out.append(
        BreakEven(
            key="break_even_rent",
            label="Monthly rent needed to break even",
            value=None if rent is None else round(rent, 2),
            unit="gbp_month",
            current=inp.monthly_rent,
            explanation="Rent at which year-one cash flow after mortgage payments (before tax) is zero.",
        )
    )

    # Highest interest rate that keeps cash flow non-negative.
    if inp.is_mortgaged:
        if cf(interest_rate_pct=0) < 0:
            rate = None
            expl = "Cash flow is negative even at a 0% interest rate."
        elif cf(interest_rate_pct=25) >= 0:
            rate = 25.0
            expl = "Cash flow stays positive at interest rates up to 25%."
        else:
            rate = _bisect(lambda r: cf(interest_rate_pct=r), 0, 25)
            expl = "Mortgage rate at which year-one pre-tax cash flow falls to zero."
        out.append(
            BreakEven(
                key="break_even_rate",
                label="Maximum mortgage rate for break-even",
                value=None if rate is None else round(rate, 3),
                unit="percent",
                current=inp.interest_rate_pct,
                explanation=expl,
            )
        )

    # Highest vacancy rate that keeps cash flow non-negative.
    if cf(vacancy_pct=0) < 0:
        vac, expl = None, "Cash flow is negative even with no void periods."
    elif cf(vacancy_pct=100) >= 0:
        vac, expl = 100.0, "Cash flow stays positive at any vacancy level."
    else:
        vac = _bisect(lambda v: cf(vacancy_pct=v), 0, 100)
        expl = "Share of the year the property can sit empty before cash flow turns negative."
    out.append(
        BreakEven(
            key="break_even_vacancy",
            label="Maximum vacancy for break-even",
            value=None if vac is None else round(vac, 2),
            unit="percent",
            current=inp.vacancy_pct,
            explanation=expl,
        )
    )

    # Highest price (all else equal) that keeps cash flow non-negative.
    price = inp.purchase_price
    if cf(purchase_price=1) < 0:
        max_price, expl = None, "Cash flow is negative regardless of price (costs exceed rent)."
    else:
        hi = min(price * 2, 100_000_000)
        while cf(purchase_price=hi) >= 0 and hi < 100_000_000:
            hi = min(hi * 2, 100_000_000)
        max_price = _bisect(lambda p: cf(purchase_price=p), 1, hi)
        expl = (
            "Purchase price at which year-one pre-tax cash flow is zero, keeping the deposit "
            "percentage, rate and rent unchanged."
        )
    out.append(
        BreakEven(
            key="max_price_break_even",
            label="Maximum price for break-even cash flow",
            value=None if max_price is None else round(max_price, -2),
            unit="gbp",
            current=price,
            explanation=expl,
        )
    )

    out.append(
        BreakEven(
            key="price_for_target_yield",
            label=f"Price for a {target_gross_yield_pct:g}% gross yield",
            value=round(inp.monthly_rent * 12 / (target_gross_yield_pct / 100), -2),
            unit="gbp",
            current=price,
            explanation=f"annual gross rent ÷ {target_gross_yield_pct:g}%",
        )
    )
    return out


class SensitivityPoint(BaseModel):
    label: str
    monthly_cash_flow: float
    irr_pct: float | None
    net_yield_pct: float | None


class SensitivityRow(BaseModel):
    driver: str
    description: str
    low: SensitivityPoint
    high: SensitivityPoint
    cash_flow_swing: float


def _point(label: str, inp: DealInputs) -> SensitivityPoint:
    a = analyse_deal(inp)
    return SensitivityPoint(
        label=label,
        monthly_cash_flow=a.value("monthly_cash_flow") or 0.0,
        irr_pct=a.value("irr"),
        net_yield_pct=a.value("net_yield"),
    )


def sensitivity(inp: DealInputs) -> tuple[SensitivityPoint, list[SensitivityRow]]:
    base = _point("Base case", inp)
    variants: list[tuple[str, str, dict, str, dict, str]] = [
        (
            "Interest rate",
            "Mortgage rate ±1 percentage point",
            {"interest_rate_pct": inp.interest_rate_pct + 1},
            f"{inp.interest_rate_pct + 1:g}%",
            {"interest_rate_pct": inp.interest_rate_pct - 1},
            f"{max(inp.interest_rate_pct - 1, 0):g}%",
        ),
        (
            "Rent",
            "Monthly rent ±10%",
            {"monthly_rent": inp.monthly_rent * 0.9},
            f"£{inp.monthly_rent * 0.9:,.0f}",
            {"monthly_rent": inp.monthly_rent * 1.1},
            f"£{inp.monthly_rent * 1.1:,.0f}",
        ),
        (
            "Vacancy",
            "Void allowance +4 / -2 percentage points",
            {"vacancy_pct": inp.vacancy_pct + 4},
            f"{min(inp.vacancy_pct + 4, 100):g}%",
            {"vacancy_pct": inp.vacancy_pct - 2},
            f"{max(inp.vacancy_pct - 2, 0):g}%",
        ),
        (
            "Purchase price",
            "Purchase price ±5%",
            {"purchase_price": inp.purchase_price * 1.05},
            f"£{inp.purchase_price * 1.05:,.0f}",
            {"purchase_price": inp.purchase_price * 0.95},
            f"£{inp.purchase_price * 0.95:,.0f}",
        ),
        (
            "Capital growth",
            "Annual capital growth ±2 percentage points",
            {"capital_growth_pct": inp.capital_growth_pct - 2},
            f"{inp.capital_growth_pct - 2:g}%",
            {"capital_growth_pct": inp.capital_growth_pct + 2},
            f"{inp.capital_growth_pct + 2:g}%",
        ),
    ]
    rows: list[SensitivityRow] = []
    for driver, desc, low_change, low_label, high_change, high_label in variants:
        low = _point(low_label, adjust(inp, **low_change))
        high = _point(high_label, adjust(inp, **high_change))
        rows.append(
            SensitivityRow(
                driver=driver,
                description=desc,
                low=low,
                high=high,
                cash_flow_swing=round(abs(high.monthly_cash_flow - low.monthly_cash_flow), 2),
            )
        )
    rows.sort(key=lambda r: r.cash_flow_swing, reverse=True)
    return base, rows


class ScenarioAdjustments(BaseModel):
    rent_change_pct: float = Field(default=0, ge=-90, le=200)
    interest_rate_change_pp: float = Field(default=0, ge=-25, le=25)
    vacancy_change_pp: float = Field(default=0, ge=-100, le=100)
    capital_growth_change_pp: float = Field(default=0, ge=-30, le=30)
    expense_change_pct: float = Field(default=0, ge=-90, le=200)
    purchase_price_change_pct: float = Field(default=0, ge=-90, le=200)


DEFAULT_OPTIMISTIC = ScenarioAdjustments(
    rent_change_pct=5,
    interest_rate_change_pp=-0.75,
    vacancy_change_pp=-2,
    capital_growth_change_pp=1.5,
    expense_change_pct=-10,
)
DEFAULT_PESSIMISTIC = ScenarioAdjustments(
    rent_change_pct=-7.5,
    interest_rate_change_pp=1.5,
    vacancy_change_pp=4,
    capital_growth_change_pp=-2.5,
    expense_change_pct=20,
)

_ADJUSTMENT_LABELS = {
    "rent_change_pct": "Rent",
    "interest_rate_change_pp": "Mortgage rate",
    "vacancy_change_pp": "Vacancy",
    "capital_growth_change_pp": "Capital growth",
    "expense_change_pct": "Operating costs",
    "purchase_price_change_pct": "Purchase price",
}


def apply_adjustments(inp: DealInputs, adj: ScenarioAdjustments) -> DealInputs:
    cost_factor = 1 + adj.expense_change_pct / 100
    return adjust(
        inp,
        monthly_rent=inp.monthly_rent * (1 + adj.rent_change_pct / 100),
        interest_rate_pct=inp.interest_rate_pct + adj.interest_rate_change_pp,
        vacancy_pct=inp.vacancy_pct + adj.vacancy_change_pp,
        capital_growth_pct=inp.capital_growth_pct + adj.capital_growth_change_pp,
        management_pct=inp.management_pct * cost_factor,
        maintenance_pct=inp.maintenance_pct * cost_factor,
        insurance_annual=inp.insurance_annual * cost_factor,
        ground_rent_service_annual=inp.ground_rent_service_annual * cost_factor,
        other_costs_annual=inp.other_costs_annual * cost_factor,
        purchase_price=inp.purchase_price * (1 + adj.purchase_price_change_pct / 100),
    )


class ScenarioDriver(BaseModel):
    assumption: str
    change: float
    monthly_cash_flow_impact: float
    irr_impact_pp: float | None


class ScenarioResult(BaseModel):
    name: str
    adjustments: ScenarioAdjustments
    monthly_cash_flow: float
    annual_cash_flow: float
    net_yield_pct: float | None
    cash_on_cash_pct: float | None
    irr_pct: float | None
    total_profit: float
    initial_cash_required: float
    drivers: list[ScenarioDriver]


def _summarise(name: str, inp: DealInputs, adj: ScenarioAdjustments, base_inp: DealInputs | None):
    a = analyse_deal(inp)
    drivers: list[ScenarioDriver] = []
    if base_inp is not None:
        base = analyse_deal(base_inp)
        for field_name, label in _ADJUSTMENT_LABELS.items():
            change = getattr(adj, field_name)
            if change == 0:
                continue
            solo = analyse_deal(apply_adjustments(base_inp, ScenarioAdjustments(**{field_name: change})))
            b_irr, s_irr = base.value("irr"), solo.value("irr")
            drivers.append(
                ScenarioDriver(
                    assumption=label,
                    change=change,
                    monthly_cash_flow_impact=round(
                        (solo.value("monthly_cash_flow") or 0) - (base.value("monthly_cash_flow") or 0),
                        2,
                    ),
                    irr_impact_pp=None if b_irr is None or s_irr is None else round(s_irr - b_irr, 2),
                )
            )
        drivers.sort(key=lambda d: (abs(d.irr_impact_pp or 0), abs(d.monthly_cash_flow_impact)), reverse=True)
    return ScenarioResult(
        name=name,
        adjustments=adj,
        monthly_cash_flow=a.value("monthly_cash_flow") or 0.0,
        annual_cash_flow=a.value("annual_cash_flow") or 0.0,
        net_yield_pct=a.value("net_yield"),
        cash_on_cash_pct=a.value("cash_on_cash"),
        irr_pct=a.value("irr"),
        total_profit=a.returns.total_profit,
        initial_cash_required=a.returns.total_cash_invested,
        drivers=drivers,
    )


def scenarios(
    inp: DealInputs,
    optimistic: ScenarioAdjustments = DEFAULT_OPTIMISTIC,
    pessimistic: ScenarioAdjustments = DEFAULT_PESSIMISTIC,
) -> list[ScenarioResult]:
    """Base, optimistic and pessimistic cases with one-at-a-time driver attribution.

    Driver impacts are measured by applying each adjustment on its own to the base
    case; because effects interact, they need not sum exactly to the combined change.
    """
    return [
        _summarise("Base", inp, ScenarioAdjustments(), None),
        _summarise("Optimistic", apply_adjustments(inp, optimistic), optimistic, inp),
        _summarise("Pessimistic", apply_adjustments(inp, pessimistic), pessimistic, inp),
    ]
