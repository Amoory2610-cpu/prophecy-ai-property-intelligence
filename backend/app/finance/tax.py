"""Simplified rental income and capital gains tax scenarios.

These are illustrative scenarios, not tax calculations for a real person. They
ignore the personal allowance, the interaction with other income, losses brought
forward, the property allowance, replacement of domestic items relief, Scottish
income tax bands, National Insurance, dividend extraction from a company and
more. Every scenario returns warnings that the UI must display.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Ownership = Literal["individual", "company", "none"]
TaxBand = Literal["basic", "higher", "additional"]

TAX_RULES_REVIEWED_ON = "2026-10-09"

# Income tax rates applied to rental profit for an individual (rest of UK bands).
INCOME_TAX_RATES: dict[TaxBand, float] = {"basic": 0.20, "higher": 0.40, "additional": 0.45}
# Section 24: finance costs are not deductible; a basic-rate tax reduction is given instead.
FINANCE_COST_CREDIT_RATE = 0.20
# Residential property CGT rates from 6 April 2024.
CGT_RATES: dict[TaxBand, float] = {"basic": 0.18, "higher": 0.24, "additional": 0.24}
CGT_ANNUAL_EXEMPT_AMOUNT = 3_000
# Corporation tax: small profits rate, main rate and marginal relief limits.
CT_SMALL_RATE = 0.19
CT_MAIN_RATE = 0.25
CT_LOWER_LIMIT = 50_000
CT_UPPER_LIMIT = 250_000
CT_MARGINAL_FRACTION = 3 / 200

GENERAL_WARNINGS = [
    "Simplified illustration only - this is not personalised tax advice. Consult a qualified "
    "tax adviser about your own circumstances.",
    "UK tax rules change frequently. The UK government announced in the Autumn Budget 2025 "
    "that separate property income tax rates (2 percentage points above the ordinary rates) "
    "are planned from April 2027; check current rules and override the rate if needed.",
]


@dataclass
class IncomeTaxScenario:
    ownership: Ownership
    taxable_profit: float
    tax_before_credits: float
    finance_cost_credit: float
    tax: float
    rate_used: float
    formula: str
    warnings: list[str] = field(default_factory=list)


def corporation_tax(profit: float) -> float:
    """Corporation tax on ``profit`` with marginal relief between £50k and £250k.

    Assumes a 12-month accounting period and no associated companies.
    """
    if profit <= 0:
        return 0.0
    if profit <= CT_LOWER_LIMIT:
        return profit * CT_SMALL_RATE
    tax = profit * CT_MAIN_RATE
    if profit < CT_UPPER_LIMIT:
        tax -= (CT_UPPER_LIMIT - profit) * CT_MARGINAL_FRACTION
    return tax


def rental_income_tax(
    *,
    ownership: Ownership,
    rental_income: float,
    allowable_expenses: float,
    finance_costs: float,
    tax_band: TaxBand = "higher",
    income_tax_rate_override_pct: float | None = None,
) -> IncomeTaxScenario:
    if ownership == "none":
        return IncomeTaxScenario(
            ownership="none",
            taxable_profit=0.0,
            tax_before_credits=0.0,
            finance_cost_credit=0.0,
            tax=0.0,
            rate_used=0.0,
            formula="Tax not modelled (pre-tax figures only).",
            warnings=["Tax has been excluded from this analysis; figures are pre-tax."],
        )

    if ownership == "individual":
        rate = (
            income_tax_rate_override_pct / 100
            if income_tax_rate_override_pct is not None
            else INCOME_TAX_RATES[tax_band]
        )
        # Section 24: mortgage interest is not deducted from rental profit.
        profit = rental_income - allowable_expenses
        tax_before = max(profit, 0.0) * rate
        credit = FINANCE_COST_CREDIT_RATE * min(finance_costs, max(profit, 0.0))
        credit = min(credit, tax_before)
        warnings = list(GENERAL_WARNINGS) + [
            "Personal allowance and other income are ignored; the whole rental profit is taxed at "
            f"the selected {tax_band}-rate ({rate:.0%}).",
            "Mortgage interest is not deductible for individuals (Section 24); a 20% tax reduction "
            "on finance costs is applied instead. Unused finance costs carried forward are not modelled.",
        ]
        return IncomeTaxScenario(
            ownership="individual",
            taxable_profit=profit,
            tax_before_credits=tax_before,
            finance_cost_credit=credit,
            tax=max(tax_before - credit, 0.0),
            rate_used=rate,
            formula=(
                "tax = max(rent - allowable expenses, 0) × income tax rate - 20% × min(finance costs, rental profit)"
            ),
            warnings=warnings,
        )

    # Limited company: interest is deductible, corporation tax with marginal relief.
    profit = rental_income - allowable_expenses - finance_costs
    tax = corporation_tax(profit)
    return IncomeTaxScenario(
        ownership="company",
        taxable_profit=profit,
        tax_before_credits=tax,
        finance_cost_credit=0.0,
        tax=tax,
        rate_used=(tax / profit) if profit > 0 else 0.0,
        formula=(
            "tax = corporation tax on (rent - allowable expenses - mortgage interest); "
            "19% up to £50k, 25% above £250k, marginal relief between"
        ),
        warnings=list(GENERAL_WARNINGS[:1])
        + [
            "Assumes the company has no other profits or associated companies.",
            "Tax on extracting profits (dividends or salary) is not modelled.",
            "Company buy-to-let mortgages are usually priced differently from personal ones.",
        ],
    )


def capital_gains_tax(
    *,
    ownership: Ownership,
    gain: float,
    tax_band: TaxBand = "higher",
) -> tuple[float, str, list[str]]:
    """Return ``(tax, formula, warnings)`` for a gain on disposal of a residential property."""
    if ownership == "none" or gain <= 0:
        reason = "No gain" if gain <= 0 else "Tax not modelled"
        return 0.0, f"{reason}: no capital gains tax estimated.", []
    if ownership == "company":
        return (
            corporation_tax(gain),
            "tax = corporation tax on the chargeable gain (no indexation allowance)",
            ["Assumes the gain is the company's only profit in that accounting period."],
        )
    rate = CGT_RATES[tax_band]
    taxable = max(gain - CGT_ANNUAL_EXEMPT_AMOUNT, 0.0)
    return (
        taxable * rate,
        f"tax = max(gain - £{CGT_ANNUAL_EXEMPT_AMOUNT:,} annual exempt amount, 0) × {rate:.0%}",
        [
            "Assumes the whole gain falls in one rate band and the annual exempt amount is unused.",
            "Residential CGT must normally be reported and paid within 60 days of completion.",
            "Assumes rates at the date of review remain in force at the time of sale.",
        ],
    )
