import pytest
from pydantic import ValidationError

from app.finance.engine import analyse_deal
from app.finance.inputs import DealInputs
from app.finance.insights import (
    ScenarioAdjustments,
    apply_adjustments,
    break_even,
    scenarios,
    sensitivity,
)
from app.finance.irr import npv


def deal(**kw) -> DealInputs:
    base = dict(purchase_price=200_000, monthly_rent=1_100)
    base.update(kw)
    return DealInputs(**base)


@pytest.fixture(scope="module")
def a():
    return analyse_deal(deal())


class TestHeadlineFigures:
    """Default buy-to-let: £200k, 25% deposit, 5% interest-only, £1,100 rent."""

    def test_acquisition(self, a):
        assert a.value("deposit") == 50_000
        assert a.value("loan_amount") == 150_000
        assert a.value("ltv") == 75
        assert a.value("transaction_tax") == 11_500
        # deposit + SDLT + legal 1,800 + survey 600 + upfront fee 1,000
        assert a.value("initial_cash_required") == 64_900

    def test_income_and_expenses(self, a):
        assert a.value("annual_rent") == 13_200
        assert a.value("collected_rent") == pytest.approx(12_672)  # 4% voids
        # 15% of collected + insurance 350 + other 400
        assert a.value("operating_expenses") == pytest.approx(12_672 * 0.15 + 750)

    def test_yields(self, a):
        assert a.value("gross_yield") == pytest.approx(6.6)
        assert a.value("net_yield") == pytest.approx((12_672 * 0.85 - 750) / 200_000 * 100, abs=0.01)

    def test_cash_flow_and_returns(self, a):
        assert a.value("monthly_mortgage_payment") == pytest.approx(625)
        noi = 12_672 * 0.85 - 750
        assert a.value("annual_cash_flow") == pytest.approx(noi - 7_500, abs=0.01)
        assert a.value("monthly_cash_flow") == pytest.approx((noi - 7_500) / 12, abs=0.01)
        assert a.value("cash_on_cash") == pytest.approx((noi - 7_500) / 64_900 * 100, abs=0.01)

    def test_year_one_tax_section_24(self, a):
        noi = 12_672 * 0.85 - 750
        assert a.value("annual_tax") == pytest.approx(noi * 0.40 - 0.20 * 7_500, abs=0.01)

    def test_icr(self, a):
        # 13,200 / (150,000 × 5.5%)
        assert a.value("icr") == pytest.approx(160)
        assert a.value("max_loan_by_icr") == pytest.approx(13_200 / (1.25 * 0.055), abs=0.01)

    def test_every_metric_is_explained(self, a):
        for m in a.metrics:
            assert m.formula, m.key
            assert m.inputs, m.key
            assert m.basis in ("calculated", "estimate")

    def test_tax_figures_are_labelled_estimates(self, a):
        assert a.metric("annual_tax").basis == "estimate"
        assert a.metric("transaction_tax").basis == "estimate"
        assert a.metric("gross_yield").basis == "calculated"

    def test_return_identities(self, a):
        r = a.returns
        assert r.total_profit == pytest.approx(
            r.total_cash_flow + r.net_sale_proceeds - r.total_cash_invested, abs=0.05
        )
        assert npv(r.irr_pct / 100, r.cash_flows) == pytest.approx(0, abs=1)
        for p in a.projection:
            assert p.equity == pytest.approx(p.property_value - p.loan_balance, abs=0.02)

    def test_sale(self, a):
        s = a.sale
        assert s.sale_price == pytest.approx(200_000 * 1.03**10, abs=0.01)
        assert s.loan_repayment == 150_000
        assert s.base_cost == pytest.approx(200_000 + 11_500 + 1_800 + 600)
        assert s.capital_gains_tax == pytest.approx((s.gain - 3_000) * 0.24, abs=0.02)


class TestEdgeCases:
    def test_cash_purchase(self):
        a = analyse_deal(deal(financing="cash"))
        assert a.value("loan_amount") == 0
        assert a.value("monthly_mortgage_payment") == 0
        assert a.value("icr") is None
        assert a.value("annual_cash_flow") == a.value("noi_annual")
        assert a.value("initial_cash_required") == pytest.approx(200_000 + 11_500 + 2_400)

    def test_hundred_percent_deposit_is_cash(self):
        a = analyse_deal(deal(deposit_pct=100))
        assert a.value("loan_amount") == 0

    def test_zero_deposit_full_loan(self):
        a = analyse_deal(deal(deposit_pct=0))
        assert a.value("ltv") == 100
        assert any("LTV" in w for w in a.warnings)

    def test_zero_interest_rate(self):
        a = analyse_deal(deal(interest_rate_pct=0, mortgage_type="repayment"))
        assert a.value("monthly_mortgage_payment") == pytest.approx(150_000 / 300)

    def test_fee_added_to_loan(self):
        a = analyse_deal(deal(add_fee_to_loan=True, mortgage_fee=2_000))
        assert a.value("loan_amount") == 152_000
        assert a.value("initial_cash_required") == pytest.approx(50_000 + 11_500 + 2_400)

    def test_zero_rent(self):
        a = analyse_deal(deal(monthly_rent=0))
        assert a.value("gross_yield") == 0
        assert a.value("annual_cash_flow") < 0
        assert any("rent is zero" in w for w in a.warnings)

    def test_negative_cash_flow_warning(self):
        a = analyse_deal(deal(interest_rate_pct=9))
        assert a.value("monthly_cash_flow") < 0
        assert "cash-flow negative" in a.warnings[0] or any("cash-flow negative" in w for w in a.warnings)

    def test_low_icr_warning(self):
        a = analyse_deal(deal(monthly_rent=700))
        assert any("Interest cover" in w for w in a.warnings)

    def test_no_initial_cash_means_no_cash_on_cash(self):
        a = analyse_deal(deal(deposit_pct=0, transaction_tax_override=0, legal_fees=0, survey_fees=0, mortgage_fee=0))
        assert a.value("initial_cash_required") == 0
        assert a.value("cash_on_cash") is None
        assert a.value("irr") is None

    def test_holding_longer_than_term(self):
        a = analyse_deal(deal(mortgage_type="repayment", term_years=5, holding_years=8))
        assert a.projection[-1].loan_balance == pytest.approx(0, abs=0.01)
        assert a.projection[6].debt_service == 0
        assert any("longer than the mortgage term" in w for w in a.warnings)

    def test_falling_prices(self):
        a = analyse_deal(deal(capital_growth_pct=-5))
        assert a.sale.gain < 0
        assert a.sale.capital_gains_tax == 0

    def test_transaction_tax_override(self):
        a = analyse_deal(deal(transaction_tax_override=9_999))
        assert a.value("transaction_tax") == 9_999
        assert a.transaction_tax.overridden
        assert a.metric("transaction_tax").basis == "calculated"

    def test_company_ownership_deducts_interest(self):
        a = analyse_deal(deal(ownership="company"))
        profit = (12_672 * 0.85 - 750) - 7_500
        assert a.value("annual_tax") == pytest.approx(profit * 0.19, abs=0.01)

    def test_regions_change_transaction_tax(self):
        assert analyse_deal(deal(region="scotland")).value("transaction_tax") == 17_100
        assert analyse_deal(deal(region="wales")).value("transaction_tax") == 10_700


class TestValidation:
    @pytest.mark.parametrize(
        "bad",
        [
            {"purchase_price": 0},
            {"purchase_price": -100_000},
            {"monthly_rent": -1},
            {"deposit_pct": 101},
            {"interest_rate_pct": -1},
            {"term_years": 0},
            {"vacancy_pct": 120},
            {"holding_years": 0},
            {"management_pct": 50, "maintenance_pct": 50},
            {"region": "atlantis"},
            {"unexpected_field": 1},
        ],
    )
    def test_rejects_invalid_inputs(self, bad):
        with pytest.raises(ValidationError):
            deal(**bad)

    def test_rent_is_required(self):
        with pytest.raises(ValidationError):
            DealInputs(purchase_price=100_000)


class TestInsights:
    def test_break_even_rent_gives_zero_cash_flow(self):
        inp = deal()
        be = {b.key: b for b in break_even(inp)}
        rent = be["break_even_rent"].value
        assert analyse_deal(deal(monthly_rent=rent)).value("monthly_cash_flow") == pytest.approx(0, abs=0.05)

    def test_break_even_rate_gives_zero_cash_flow(self):
        be = {b.key: b for b in break_even(deal())}
        rate = be["break_even_rate"].value
        assert analyse_deal(deal(interest_rate_pct=rate)).value("monthly_cash_flow") == pytest.approx(0, abs=0.5)

    def test_break_even_vacancy(self):
        be = {b.key: b for b in break_even(deal())}
        vac = be["break_even_vacancy"].value
        assert 0 < vac < 100
        assert analyse_deal(deal(vacancy_pct=vac)).value("monthly_cash_flow") == pytest.approx(0, abs=0.05)

    def test_price_for_target_yield(self):
        be = {b.key: b for b in break_even(deal(), target_gross_yield_pct=6.6)}
        assert be["price_for_target_yield"].value == 200_000

    def test_hopeless_deal_has_no_break_even_rate(self):
        be = {b.key: b for b in break_even(deal(monthly_rent=100, insurance_annual=5_000))}
        assert be["break_even_rate"].value is None

    def test_cash_deal_has_no_rate_break_even(self):
        keys = {b.key for b in break_even(deal(financing="cash"))}
        assert "break_even_rate" not in keys

    def test_sensitivity_directions(self):
        base, rows = sensitivity(deal())
        by = {r.driver: r for r in rows}
        assert (
            by["Interest rate"].low.monthly_cash_flow
            < base.monthly_cash_flow
            < by["Interest rate"].high.monthly_cash_flow
        )
        assert by["Rent"].low.monthly_cash_flow < base.monthly_cash_flow < by["Rent"].high.monthly_cash_flow
        # Capital growth doesn't affect year-one cash flow but does affect IRR.
        assert by["Capital growth"].cash_flow_swing == 0
        assert by["Capital growth"].low.irr_pct < by["Capital growth"].high.irr_pct
        assert rows == sorted(rows, key=lambda r: r.cash_flow_swing, reverse=True)

    def test_scenarios_order_and_drivers(self):
        base, opt, pess = scenarios(deal())
        assert pess.monthly_cash_flow < base.monthly_cash_flow < opt.monthly_cash_flow
        assert pess.irr_pct < base.irr_pct < opt.irr_pct
        assert base.drivers == []
        assert {d.assumption for d in pess.drivers} == {
            "Rent",
            "Mortgage rate",
            "Vacancy",
            "Capital growth",
            "Operating costs",
        }

    def test_adjustments_are_clamped(self):
        adjusted = apply_adjustments(deal(interest_rate_pct=1), ScenarioAdjustments(interest_rate_change_pp=-5))
        assert adjusted.interest_rate_pct == 0


def test_tax_caveats_are_separate_from_deal_warnings():
    a = analyse_deal(deal())
    assert any("not personalised tax advice" in n for n in a.tax_notes)
    assert not any("not personalised tax advice" in w for w in a.warnings)
    assert analyse_deal(deal(ownership="none")).tax_notes
