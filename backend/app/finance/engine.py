"""Deterministic buy-to-let analysis engine.

``analyse_deal`` turns validated :class:`DealInputs` into a :class:`DealAnalysis`.
Every headline figure is emitted as a :class:`Metric` that carries the formula,
the inputs used, and whether the figure is a calculation on user inputs or an
estimate that depends on rules and assumptions (e.g. tax).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from .inputs import DealInputs
from .irr import irr
from .mortgage import amortisation_by_year, monthly_payment
from .sdlt import estimate_transaction_tax
from .tax import TAX_RULES_REVIEWED_ON, capital_gains_tax, rental_income_tax

ENGINE_VERSION = "1.0.0"

Unit = Literal["gbp", "gbp_month", "percent", "ratio", "multiple"]
Basis = Literal["calculated", "estimate"]


class Metric(BaseModel):
    key: str
    label: str
    value: float | None
    unit: Unit
    formula: str
    inputs: dict[str, Any]
    basis: Basis = "calculated"
    note: str | None = None


class TaxBandLine(BaseModel):
    lower: float
    upper: float | None
    rate_pct: float
    taxable_amount: float
    tax: float


class TransactionTaxSummary(BaseModel):
    name: str
    total: float
    effective_rate_pct: float
    overridden: bool
    bands: list[TaxBandLine]
    surcharge_total: float
    assumptions: list[str]
    source_url: str
    rules_reviewed_on: str


class ProjectionYear(BaseModel):
    year: int
    gross_rent: float
    collected_rent: float
    operating_expenses: float
    net_operating_income: float
    debt_service: float
    interest: float
    principal_repaid: float
    pre_tax_cash_flow: float
    tax: float
    after_tax_cash_flow: float
    property_value: float
    loan_balance: float
    equity: float


class SaleSummary(BaseModel):
    year: int
    sale_price: float
    selling_costs: float
    loan_repayment: float
    base_cost: float
    gain: float
    capital_gains_tax: float
    cgt_formula: str
    net_sale_proceeds: float


class ReturnsSummary(BaseModel):
    total_cash_invested: float
    total_cash_flow: float
    net_sale_proceeds: float
    total_profit: float
    equity_multiple: float | None
    irr_pct: float | None
    cash_flows: list[float]


class DealAnalysis(BaseModel):
    engine_version: str = ENGINE_VERSION
    inputs: DealInputs
    metrics: list[Metric]
    transaction_tax: TransactionTaxSummary
    tax_formula: str
    projection: list[ProjectionYear]
    sale: SaleSummary
    returns: ReturnsSummary
    assumptions: list[str]
    warnings: list[str]
    tax_rules_reviewed_on: str = TAX_RULES_REVIEWED_ON

    def metric(self, key: str) -> Metric:
        for m in self.metrics:
            if m.key == key:
                return m
        raise KeyError(key)

    def value(self, key: str) -> float | None:
        return self.metric(key).value


def _pct(numerator: float, denominator: float) -> float | None:
    return numerator / denominator * 100 if denominator else None


def _r(x: float | None, places: int = 2) -> float | None:
    return None if x is None else round(x, places)


class _Year1(BaseModel):
    """Year-one figures; also used by the fast paths in scenarios and sensitivity."""

    deposit: float
    loan: float
    ltv_pct: float
    tax_total: float
    purchase_costs: float
    upfront_fee: float
    initial_cash: float
    gross_rent: float
    vacancy_loss: float
    collected_rent: float
    management: float
    maintenance: float
    fixed_costs: float
    operating_expenses: float
    noi: float
    monthly_payment: float
    debt_service: float
    interest: float
    pre_tax_cash_flow: float


def year_one(inp: DealInputs) -> _Year1:
    price = inp.purchase_price
    mortgaged = inp.is_mortgaged
    deposit = price * inp.deposit_pct / 100 if mortgaged else price
    loan_base = price - deposit
    fee = inp.mortgage_fee if mortgaged else 0.0
    loan = loan_base + (fee if inp.add_fee_to_loan else 0.0)
    upfront_fee = 0.0 if inp.add_fee_to_loan else fee

    if inp.transaction_tax_override is not None:
        tax_total = inp.transaction_tax_override
    else:
        tax_total = estimate_transaction_tax(price, inp.region, inp.buyer_type, inp.non_resident).total
    purchase_costs = tax_total + inp.legal_fees + inp.survey_fees + inp.other_purchase_costs
    initial_cash = deposit + purchase_costs + inp.refurbishment_costs + upfront_fee

    gross_rent = inp.monthly_rent * 12
    vacancy_loss = gross_rent * inp.vacancy_pct / 100
    collected = gross_rent - vacancy_loss
    management = collected * inp.management_pct / 100
    maintenance = collected * inp.maintenance_pct / 100
    fixed = inp.insurance_annual + inp.ground_rent_service_annual + inp.other_costs_annual
    opex = management + maintenance + fixed
    noi = collected - opex

    payment = monthly_payment(loan, inp.interest_rate_pct, inp.term_years, inp.mortgage_type) if loan > 0 else 0.0
    sched = (
        amortisation_by_year(loan, inp.interest_rate_pct, inp.term_years, inp.mortgage_type, 1)[0] if loan > 0 else None
    )
    debt_service = sched.payments if sched else 0.0
    interest = sched.interest if sched else 0.0

    return _Year1(
        deposit=deposit,
        loan=loan,
        ltv_pct=loan / price * 100,
        tax_total=tax_total,
        purchase_costs=purchase_costs,
        upfront_fee=upfront_fee,
        initial_cash=initial_cash,
        gross_rent=gross_rent,
        vacancy_loss=vacancy_loss,
        collected_rent=collected,
        management=management,
        maintenance=maintenance,
        fixed_costs=fixed,
        operating_expenses=opex,
        noi=noi,
        monthly_payment=payment,
        debt_service=debt_service,
        interest=interest,
        pre_tax_cash_flow=noi - debt_service,
    )


def analyse_deal(inp: DealInputs) -> DealAnalysis:
    y1 = year_one(inp)
    price = inp.purchase_price
    warnings: list[str] = []
    assumptions: list[str] = [
        "Rent, costs and growth rates are user-supplied assumptions, not verified market data.",
        f"Void allowance of {inp.vacancy_pct:g}% of gross rent is deducted before percentage-based costs.",
        "Management and maintenance are charged as a percentage of collected rent; fixed costs "
        f"inflate at {inp.cost_inflation_pct:g}% a year.",
        f"Property value grows at {inp.capital_growth_pct:g}% a year and rent at "
        f"{inp.rent_growth_pct:g}% a year, compounded annually.",
        f"The property is sold at the end of year {inp.holding_years} with selling costs of "
        f"{inp.selling_costs_pct:g}% of the sale price, and any outstanding loan is repaid.",
        "Refurbishment costs are treated as capital improvements (added to the CGT base cost).",
        "Cash flows are annual and undiscounted except in the IRR.",
    ]

    # --- transaction tax --------------------------------------------------
    tt = estimate_transaction_tax(price, inp.region, inp.buyer_type, inp.non_resident)
    overridden = inp.transaction_tax_override is not None
    tt_summary = TransactionTaxSummary(
        name=tt.tax_name,
        total=y1.tax_total,
        effective_rate_pct=round(y1.tax_total / price * 100, 3),
        overridden=overridden,
        bands=[
            TaxBandLine(
                lower=b.lower,
                upper=b.upper,
                rate_pct=round(b.rate * 100, 3),
                taxable_amount=round(b.taxable_amount, 2),
                tax=round(b.tax, 2),
            )
            for b in tt.bands
        ],
        surcharge_total=round(tt.surcharge_total, 2),
        assumptions=(["A user-supplied transaction tax figure replaces the estimate."] if overridden else [])
        + tt.assumptions,
        source_url=tt.source_url,
        rules_reviewed_on=tt.rules_reviewed_on,
    )

    # --- projection --------------------------------------------------------
    mortgaged = y1.loan > 0
    schedule = (
        amortisation_by_year(y1.loan, inp.interest_rate_pct, inp.term_years, inp.mortgage_type, inp.holding_years)
        if mortgaged
        else []
    )
    projection: list[ProjectionYear] = []
    tax_formula = ""
    first_tax_warnings: list[str] = []
    for year in range(1, inp.holding_years + 1):
        rent_factor = (1 + inp.rent_growth_pct / 100) ** (year - 1)
        cost_factor = (1 + inp.cost_inflation_pct / 100) ** (year - 1)
        gross = y1.gross_rent * rent_factor
        collected = gross * (1 - inp.vacancy_pct / 100)
        opex = collected * (inp.management_pct + inp.maintenance_pct) / 100 + y1.fixed_costs * cost_factor
        noi = collected - opex
        s = schedule[year - 1] if mortgaged else None
        debt = s.payments if s else 0.0
        interest = s.interest if s else 0.0
        balance = s.closing_balance if s else 0.0
        pre_tax = noi - debt
        tax = rental_income_tax(
            ownership=inp.ownership,
            rental_income=collected,
            allowable_expenses=opex,
            finance_costs=interest,
            tax_band=inp.tax_band,
            income_tax_rate_override_pct=inp.income_tax_rate_override_pct,
        )
        if year == 1:
            tax_formula = tax.formula
            first_tax_warnings = tax.warnings
            year1_tax = tax.tax
        value = price * (1 + inp.capital_growth_pct / 100) ** year
        projection.append(
            ProjectionYear(
                year=year,
                gross_rent=round(gross, 2),
                collected_rent=round(collected, 2),
                operating_expenses=round(opex, 2),
                net_operating_income=round(noi, 2),
                debt_service=round(debt, 2),
                interest=round(interest, 2),
                principal_repaid=round(s.principal if s else 0.0, 2),
                pre_tax_cash_flow=round(pre_tax, 2),
                tax=round(tax.tax, 2),
                after_tax_cash_flow=round(pre_tax - tax.tax, 2),
                property_value=round(value, 2),
                loan_balance=round(balance, 2),
                equity=round(value - balance, 2),
            )
        )
    warnings.extend(first_tax_warnings)

    # --- sale ---------------------------------------------------------------
    last = projection[-1]
    sale_price = last.property_value
    selling_costs = sale_price * inp.selling_costs_pct / 100
    base_cost = price + y1.purchase_costs + inp.refurbishment_costs
    gain = sale_price - selling_costs - base_cost
    if inp.include_cgt:
        cgt, cgt_formula, cgt_warnings = capital_gains_tax(ownership=inp.ownership, gain=gain, tax_band=inp.tax_band)
        warnings.extend(cgt_warnings)
    else:
        cgt, cgt_formula = 0.0, "Capital gains tax excluded by user."
    net_sale = sale_price - selling_costs - last.loan_balance - cgt
    sale = SaleSummary(
        year=inp.holding_years,
        sale_price=round(sale_price, 2),
        selling_costs=round(selling_costs, 2),
        loan_repayment=last.loan_balance,
        base_cost=round(base_cost, 2),
        gain=round(gain, 2),
        capital_gains_tax=round(cgt, 2),
        cgt_formula=cgt_formula,
        net_sale_proceeds=round(net_sale, 2),
    )

    # --- returns ------------------------------------------------------------
    flows = [-y1.initial_cash] + [p.after_tax_cash_flow for p in projection]
    flows[-1] += net_sale
    total_cf = sum(p.after_tax_cash_flow for p in projection)
    total_profit = total_cf + net_sale - y1.initial_cash
    irr_value = irr(flows) if y1.initial_cash > 0 else None
    returns = ReturnsSummary(
        total_cash_invested=round(y1.initial_cash, 2),
        total_cash_flow=round(total_cf, 2),
        net_sale_proceeds=round(net_sale, 2),
        total_profit=round(total_profit, 2),
        equity_multiple=_r((total_cf + net_sale) / y1.initial_cash, 3) if y1.initial_cash > 0 else None,
        irr_pct=_r(irr_value * 100 if irr_value is not None else None),
        cash_flows=[round(f, 2) for f in flows],
    )

    # --- headline metrics -------------------------------------------------------
    total_cost = price + y1.purchase_costs + inp.refurbishment_costs
    stress_interest = y1.loan * inp.stress_rate_pct / 100
    icr = (y1.gross_rent / stress_interest * 100) if stress_interest > 0 else None
    max_loan_icr = (
        y1.gross_rent / (inp.required_icr_pct / 100 * inp.stress_rate_pct / 100) if inp.stress_rate_pct > 0 else None
    )
    after_tax_y1 = y1.pre_tax_cash_flow - year1_tax

    m = [
        Metric(
            key="initial_cash_required",
            label="Initial cash required",
            value=_r(y1.initial_cash),
            unit="gbp",
            formula="deposit + transaction tax + legal + survey + other purchase costs "
            "+ refurbishment + mortgage fee (if paid upfront)",
            inputs={
                "deposit": _r(y1.deposit),
                "transaction_tax": _r(y1.tax_total),
                "legal_fees": inp.legal_fees,
                "survey_fees": inp.survey_fees,
                "other_purchase_costs": inp.other_purchase_costs,
                "refurbishment_costs": inp.refurbishment_costs,
                "mortgage_fee_upfront": _r(y1.upfront_fee),
            },
            basis="estimate" if not overridden else "calculated",
            note="Includes an estimated transaction tax." if not overridden else None,
        ),
        Metric(
            key="deposit",
            label="Deposit",
            value=_r(y1.deposit),
            unit="gbp",
            formula="purchase price × deposit %" if mortgaged else "purchase price (cash purchase)",
            inputs={"purchase_price": price, "deposit_pct": inp.deposit_pct if mortgaged else 100},
        ),
        Metric(
            key="transaction_tax",
            label=tt.tax_name,
            value=_r(y1.tax_total),
            unit="gbp",
            formula="sum over bands of (portion of price in band × band rate) plus surcharges",
            inputs={
                "purchase_price": price,
                "region": inp.region,
                "buyer_type": inp.buyer_type,
                "non_resident": inp.non_resident,
            },
            basis="calculated" if overridden else "estimate",
            note="User-supplied figure." if overridden else "Estimate - see band breakdown.",
        ),
        Metric(
            key="loan_amount",
            label="Mortgage amount",
            value=_r(y1.loan),
            unit="gbp",
            formula="purchase price - deposit (+ mortgage fee if added to the loan)",
            inputs={
                "purchase_price": price,
                "deposit": _r(y1.deposit),
                "fee_added": inp.mortgage_fee if (mortgaged and inp.add_fee_to_loan) else 0,
            },
        ),
        Metric(
            key="ltv",
            label="Loan to value",
            value=_r(y1.ltv_pct),
            unit="percent",
            formula="mortgage amount ÷ purchase price",
            inputs={"loan_amount": _r(y1.loan), "purchase_price": price},
        ),
        Metric(
            key="monthly_mortgage_payment",
            label="Monthly mortgage payment",
            value=_r(y1.monthly_payment),
            unit="gbp_month",
            formula="P × r ÷ 12 (interest-only)"
            if inp.mortgage_type == "interest_only"
            else "P × r(1+r)^n ÷ ((1+r)^n - 1), r = monthly rate, n = months",
            inputs={
                "principal": _r(y1.loan),
                "annual_rate_pct": inp.interest_rate_pct,
                "term_years": inp.term_years,
                "mortgage_type": inp.mortgage_type,
            },
        ),
        Metric(
            key="annual_rent",
            label="Annual gross rent",
            value=_r(y1.gross_rent),
            unit="gbp",
            formula="monthly rent × 12",
            inputs={"monthly_rent": inp.monthly_rent},
        ),
        Metric(
            key="collected_rent",
            label="Annual collected rent (after voids)",
            value=_r(y1.collected_rent),
            unit="gbp",
            formula="annual gross rent × (1 - vacancy %)",
            inputs={"annual_rent": _r(y1.gross_rent), "vacancy_pct": inp.vacancy_pct},
        ),
        Metric(
            key="operating_expenses",
            label="Annual operating expenses",
            value=_r(y1.operating_expenses),
            unit="gbp",
            formula="collected rent × (management % + maintenance %) + insurance "
            "+ ground rent/service charge + other costs",
            inputs={
                "management": _r(y1.management),
                "maintenance": _r(y1.maintenance),
                "insurance": inp.insurance_annual,
                "ground_rent_service": inp.ground_rent_service_annual,
                "other_costs": inp.other_costs_annual,
            },
        ),
        Metric(
            key="gross_yield",
            label="Gross rental yield",
            value=_r(_pct(y1.gross_rent, price)),
            unit="percent",
            formula="annual gross rent ÷ purchase price",
            inputs={"annual_rent": _r(y1.gross_rent), "purchase_price": price},
        ),
        Metric(
            key="net_yield",
            label="Net rental yield",
            value=_r(_pct(y1.noi, price)),
            unit="percent",
            formula="(collected rent - operating expenses) ÷ purchase price",
            inputs={"net_operating_income": _r(y1.noi), "purchase_price": price},
            note="Before mortgage costs and tax.",
        ),
        Metric(
            key="net_yield_on_cost",
            label="Net yield on total cost",
            value=_r(_pct(y1.noi, total_cost)),
            unit="percent",
            formula="net operating income ÷ (price + purchase costs + refurbishment)",
            inputs={"net_operating_income": _r(y1.noi), "total_cost": _r(total_cost)},
        ),
        Metric(
            key="noi_annual",
            label="Cash flow before financing (annual)",
            value=_r(y1.noi),
            unit="gbp",
            formula="collected rent - operating expenses",
            inputs={
                "collected_rent": _r(y1.collected_rent),
                "operating_expenses": _r(y1.operating_expenses),
            },
        ),
        Metric(
            key="monthly_cash_flow",
            label="Monthly cash flow after financing (pre-tax)",
            value=_r(y1.pre_tax_cash_flow / 12),
            unit="gbp_month",
            formula="(net operating income - annual mortgage payments) ÷ 12",
            inputs={"net_operating_income": _r(y1.noi), "debt_service": _r(y1.debt_service)},
        ),
        Metric(
            key="annual_cash_flow",
            label="Annual cash flow after financing (pre-tax)",
            value=_r(y1.pre_tax_cash_flow),
            unit="gbp",
            formula="net operating income - annual mortgage payments",
            inputs={"net_operating_income": _r(y1.noi), "debt_service": _r(y1.debt_service)},
        ),
        Metric(
            key="annual_tax",
            label="Estimated tax on rental profit (year 1)",
            value=_r(year1_tax),
            unit="gbp",
            formula=tax_formula,
            inputs={
                "ownership": inp.ownership,
                "tax_band": inp.tax_band,
                "collected_rent": _r(y1.collected_rent),
                "operating_expenses": _r(y1.operating_expenses),
                "mortgage_interest": _r(y1.interest),
            },
            basis="estimate",
            note="Simplified scenario - not tax advice.",
        ),
        Metric(
            key="monthly_cash_flow_after_tax",
            label="Monthly cash flow after tax",
            value=_r(after_tax_y1 / 12),
            unit="gbp_month",
            formula="(annual pre-tax cash flow - estimated tax) ÷ 12",
            inputs={"annual_cash_flow": _r(y1.pre_tax_cash_flow), "annual_tax": _r(year1_tax)},
            basis="estimate",
        ),
        Metric(
            key="cash_on_cash",
            label="Cash-on-cash return (pre-tax)",
            value=_r(_pct(y1.pre_tax_cash_flow, y1.initial_cash)) if y1.initial_cash > 0 else None,
            unit="percent",
            formula="annual pre-tax cash flow ÷ initial cash required",
            inputs={
                "annual_cash_flow": _r(y1.pre_tax_cash_flow),
                "initial_cash_required": _r(y1.initial_cash),
            },
        ),
        Metric(
            key="icr",
            label="Interest cover ratio (lender stress test)",
            value=_r(icr),
            unit="percent",
            formula="annual gross rent ÷ (mortgage amount × stress rate)",
            inputs={
                "annual_rent": _r(y1.gross_rent),
                "loan_amount": _r(y1.loan),
                "stress_rate_pct": inp.stress_rate_pct,
                "required_icr_pct": inp.required_icr_pct,
            },
            basis="estimate",
            note="Lenders' criteria vary; 125% (basic-rate) and 145% (higher-rate) at a ~5.5% "
            "stress rate are common benchmarks.",
        ),
        Metric(
            key="max_loan_by_icr",
            label="Maximum loan supported by rent (ICR)",
            value=_r(max_loan_icr),
            unit="gbp",
            formula="annual gross rent ÷ (required ICR × stress rate)",
            inputs={
                "annual_rent": _r(y1.gross_rent),
                "required_icr_pct": inp.required_icr_pct,
                "stress_rate_pct": inp.stress_rate_pct,
            },
            basis="estimate",
        ),
        Metric(
            key="irr",
            label=f"Annualised return (IRR, {inp.holding_years} years, after tax)",
            value=returns.irr_pct,
            unit="percent",
            formula="discount rate at which NPV of [-initial cash, annual after-tax cash flows, "
            "net sale proceeds] equals zero",
            inputs={"cash_flows": returns.cash_flows},
            basis="estimate",
            note="Depends heavily on growth and exit assumptions.",
        ),
        Metric(
            key="total_profit",
            label=f"Total profit over {inp.holding_years} years",
            value=returns.total_profit,
            unit="gbp",
            formula="sum of after-tax cash flows + net sale proceeds - initial cash",
            inputs={
                "total_cash_flow": returns.total_cash_flow,
                "net_sale_proceeds": returns.net_sale_proceeds,
                "initial_cash_required": returns.total_cash_invested,
            },
            basis="estimate",
        ),
        Metric(
            key="equity_multiple",
            label="Equity multiple",
            value=returns.equity_multiple,
            unit="multiple",
            formula="(sum of after-tax cash flows + net sale proceeds) ÷ initial cash",
            inputs={
                "total_cash_flow": returns.total_cash_flow,
                "net_sale_proceeds": returns.net_sale_proceeds,
                "initial_cash_required": returns.total_cash_invested,
            },
            basis="estimate",
        ),
    ]

    # --- warnings ------------------------------------------------------------
    if inp.monthly_rent == 0:
        warnings.insert(0, "Monthly rent is zero - yield and cash flow figures reflect costs only.")
    if y1.pre_tax_cash_flow < 0:
        warnings.insert(
            0,
            f"The property is cash-flow negative before tax by £{-y1.pre_tax_cash_flow / 12:,.0f} a month in year one.",
        )
    if icr is not None and icr < inp.required_icr_pct:
        warnings.insert(
            0,
            f"Interest cover of {icr:.0f}% is below the {inp.required_icr_pct:g}% many lenders "
            "require; the loan may not be available at this size.",
        )
    if mortgaged and inp.holding_years > inp.term_years:
        warnings.append(
            "The holding period is longer than the mortgage term. No payments are modelled after "
            "the term ends; an interest-only balance would have to be repaid or refinanced."
        )
    if mortgaged and inp.mortgage_type == "interest_only":
        assumptions.append("Interest-only mortgage: the full loan is repaid from the sale proceeds.")
    if y1.ltv_pct > 85:
        warnings.append(f"An LTV of {y1.ltv_pct:.0f}% is above what most buy-to-let lenders offer.")
    if inp.capital_growth_pct > 6:
        warnings.append(
            "Capital growth above 6% a year is an optimistic assumption; returns are highly sensitive to it."
        )
    if irr_value is None and y1.initial_cash > 0:
        warnings.append("An IRR could not be calculated for this cash-flow pattern.")

    return DealAnalysis(
        inputs=inp,
        metrics=m,
        transaction_tax=tt_summary,
        tax_formula=tax_formula,
        projection=projection,
        sale=sale,
        returns=returns,
        assumptions=assumptions,
        warnings=warnings,
    )
