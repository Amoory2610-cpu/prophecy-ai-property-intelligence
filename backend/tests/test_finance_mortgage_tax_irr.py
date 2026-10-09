import pytest

from app.finance.irr import irr, npv
from app.finance.mortgage import amortisation_by_year, monthly_payment
from app.finance.tax import capital_gains_tax, corporation_tax, rental_income_tax


class TestMonthlyPayment:
    def test_repayment_matches_standard_annuity(self):
        # Widely published figure: £200,000 over 25 years at 5% is £1,169.18 a month.
        assert monthly_payment(200_000, 5, 25, "repayment") == pytest.approx(1169.18, abs=0.01)

    def test_interest_only(self):
        assert monthly_payment(100_000, 6, 25, "interest_only") == pytest.approx(500)

    def test_zero_interest_repayment_is_straight_line(self):
        assert monthly_payment(120_000, 0, 10, "repayment") == pytest.approx(1000)

    def test_zero_interest_interest_only_is_free(self):
        assert monthly_payment(120_000, 0, 10, "interest_only") == 0

    def test_zero_principal(self):
        assert monthly_payment(0, 5, 25, "repayment") == 0

    @pytest.mark.parametrize(
        "args",
        [(-1, 5, 25, "repayment"), (1000, -0.1, 25, "repayment"), (1000, 5, 0, "repayment")],
    )
    def test_invalid_inputs(self, args):
        with pytest.raises(ValueError):
            monthly_payment(*args)


class TestAmortisation:
    def test_repayment_loan_is_fully_repaid_over_term(self):
        sched = amortisation_by_year(150_000, 4.5, 20, "repayment", 20)
        assert sched[-1].closing_balance == pytest.approx(0, abs=0.01)
        assert sum(y.principal for y in sched) == pytest.approx(150_000, abs=0.01)

    def test_interest_only_balance_constant(self):
        sched = amortisation_by_year(150_000, 5, 25, "interest_only", 5)
        assert all(y.closing_balance == 150_000 for y in sched)
        assert sched[0].interest == pytest.approx(7_500)

    def test_payments_stop_after_term(self):
        sched = amortisation_by_year(50_000, 5, 2, "repayment", 4)
        assert sched[2].payments == 0 and sched[3].payments == 0
        assert sched[1].closing_balance == pytest.approx(0, abs=0.01)

    def test_first_year_interest_declines_with_repayment(self):
        sched = amortisation_by_year(200_000, 5, 25, "repayment", 3)
        assert sched[0].interest > sched[1].interest > sched[2].interest


class TestIrr:
    def test_single_period(self):
        assert irr([-100, 110]) == pytest.approx(0.10, abs=1e-6)

    def test_two_periods(self):
        assert irr([-100, 0, 121]) == pytest.approx(0.10, abs=1e-6)

    def test_negative_return(self):
        assert irr([-100, 90]) == pytest.approx(-0.10, abs=1e-6)

    def test_npv_at_irr_is_zero(self):
        flows = [-50_000, 2_000, 2_100, 2_200, 2_300, 80_000]
        assert npv(irr(flows), flows) == pytest.approx(0, abs=1e-3)

    @pytest.mark.parametrize("flows", [[], [100, 10], [-100, -10]])
    def test_undefined(self, flows):
        assert irr(flows) is None


class TestTax:
    @pytest.mark.parametrize(
        ("profit", "expected"),
        [(0, 0), (-500, 0), (50_000, 9_500), (100_000, 22_750), (300_000, 75_000)],
    )
    def test_corporation_tax_with_marginal_relief(self, profit, expected):
        assert corporation_tax(profit) == pytest.approx(expected)

    def test_individual_section_24(self):
        t = rental_income_tax(
            ownership="individual",
            rental_income=15_000,
            allowable_expenses=5_000,
            finance_costs=6_000,
            tax_band="basic",
        )
        # 10,000 × 20% - 20% × 6,000
        assert t.tax == pytest.approx(800)
        assert t.warnings and "not personalised tax advice" in t.warnings[0]

    def test_section_24_credit_capped_at_profit(self):
        t = rental_income_tax(
            ownership="individual",
            rental_income=10_000,
            allowable_expenses=5_000,
            finance_costs=10_000,
            tax_band="basic",
        )
        assert t.tax == 0

    def test_higher_rate_taxpayer_pays_more_under_section_24(self):
        kw = dict(ownership="individual", rental_income=15_000, allowable_expenses=3_000, finance_costs=7_000)
        assert rental_income_tax(**kw, tax_band="higher").tax == pytest.approx(12_000 * 0.4 - 1_400)
        assert rental_income_tax(**kw, tax_band="additional").tax == pytest.approx(12_000 * 0.45 - 1_400)

    def test_rate_override(self):
        t = rental_income_tax(
            ownership="individual",
            rental_income=10_000,
            allowable_expenses=0,
            finance_costs=0,
            income_tax_rate_override_pct=22,
        )
        assert t.tax == pytest.approx(2_200)

    def test_company_deducts_interest(self):
        t = rental_income_tax(ownership="company", rental_income=15_000, allowable_expenses=5_000, finance_costs=6_000)
        assert t.tax == pytest.approx(4_000 * 0.19)

    def test_company_loss_pays_no_tax(self):
        t = rental_income_tax(ownership="company", rental_income=5_000, allowable_expenses=5_000, finance_costs=6_000)
        assert t.tax == 0

    def test_no_tax_scenario(self):
        t = rental_income_tax(ownership="none", rental_income=50_000, allowable_expenses=0, finance_costs=0)
        assert t.tax == 0

    def test_cgt_individual(self):
        tax, formula, warnings = capital_gains_tax(ownership="individual", gain=53_000, tax_band="higher")
        assert tax == pytest.approx(12_000)
        assert "annual exempt amount" in formula and warnings

    def test_cgt_basic_rate(self):
        tax, _, _ = capital_gains_tax(ownership="individual", gain=13_000, tax_band="basic")
        assert tax == pytest.approx(1_800)

    def test_cgt_no_gain(self):
        assert capital_gains_tax(ownership="individual", gain=-1_000)[0] == 0

    def test_cgt_company(self):
        assert capital_gains_tax(ownership="company", gain=40_000)[0] == pytest.approx(7_600)
