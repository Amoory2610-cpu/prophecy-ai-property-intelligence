"""Mortgage maths: monthly payments and amortisation schedules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

MortgageType = Literal["repayment", "interest_only"]


def monthly_payment(principal: float, annual_rate_pct: float, term_years: int, mortgage_type: MortgageType) -> float:
    """Contractual monthly payment.

    Repayment (annuity): ``M = P * r * (1 + r)^n / ((1 + r)^n - 1)`` with ``r`` the
    monthly rate and ``n`` the number of monthly payments. At 0% interest this
    reduces to ``P / n``.

    Interest-only: ``M = P * r``; the full principal is owed at the end of the term.
    """
    if principal < 0:
        raise ValueError("principal must not be negative")
    if annual_rate_pct < 0:
        raise ValueError("interest rate must not be negative")
    if term_years <= 0:
        raise ValueError("term must be at least one year")
    if principal == 0:
        return 0.0
    r = annual_rate_pct / 100 / 12
    n = term_years * 12
    if mortgage_type == "interest_only":
        return principal * r
    if r == 0:
        return principal / n
    growth = (1 + r) ** n
    return principal * r * growth / (growth - 1)


@dataclass
class AmortisationYear:
    year: int
    payments: float
    interest: float
    principal: float
    closing_balance: float


def amortisation_by_year(
    principal: float,
    annual_rate_pct: float,
    term_years: int,
    mortgage_type: MortgageType,
    years: int,
) -> list[AmortisationYear]:
    """Yearly totals of a monthly amortisation schedule for the first ``years`` years.

    Payments stop once the term ends. For interest-only loans the balance stays
    constant and is repaid from sale proceeds (or refinanced) - it is *not* repaid
    here at the end of the term, which is flagged by the engine as a warning.
    """
    payment = monthly_payment(principal, annual_rate_pct, term_years, mortgage_type)
    r = annual_rate_pct / 100 / 12
    balance = principal
    out: list[AmortisationYear] = []
    for year in range(1, years + 1):
        paid = interest_total = principal_total = 0.0
        for month in range(12):
            month_index = (year - 1) * 12 + month
            if month_index >= term_years * 12 or balance <= 1e-9:
                break
            interest = balance * r
            if mortgage_type == "interest_only":
                principal_part = 0.0
                pay = interest
            else:
                pay = min(payment, balance + interest)
                principal_part = pay - interest
            balance -= principal_part
            paid += pay
            interest_total += interest
            principal_total += principal_part
        out.append(AmortisationYear(year, paid, interest_total, principal_total, max(balance, 0.0)))
    return out
