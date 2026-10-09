"""Transaction tax estimates checked against hand-calculated band arithmetic."""

import pytest

from app.finance.sdlt import estimate_transaction_tax


@pytest.mark.parametrize(
    ("price", "buyer_type", "non_resident", "expected"),
    [
        # 125k @ 5% + 75k @ 7%
        (200_000, "additional_property", False, 11_500),
        # 125k @ 0% + 125k @ 2% + 45k @ 5%
        (295_000, "home_mover", False, 4_750),
        # Standard rates up to £2m: 0 + 2,500 + 33,750 + 57,500 + 60,000
        (2_000_000, "home_mover", False, 153_750),
        # First-time buyer: nil band to £300k
        (300_000, "first_time_buyer", False, 0),
        # First-time buyer: 150k @ 5%
        (450_000, "first_time_buyer", False, 7_500),
        # Relief lost above £500k: standard rates, rounded down to the pound
        (500_001, "first_time_buyer", False, 15_000),
        # Below £40k the additional-dwelling surcharge does not apply
        (39_999, "additional_property", False, 0),
        # Exactly £40k: surcharge applies at 5%
        (40_000, "additional_property", False, 2_000),
        # Non-resident additional: 125k @ 7% + 125k @ 9% + 50k @ 12%
        (300_000, "additional_property", True, 26_000),
        (0, "additional_property", False, 0),
    ],
)
def test_sdlt_england(price, buyer_type, non_resident, expected):
    result = estimate_transaction_tax(price, "england", buyer_type, non_resident)
    assert result.total == expected
    assert result.tax_name == "Stamp Duty Land Tax"


def test_northern_ireland_uses_sdlt():
    ni = estimate_transaction_tax(200_000, "northern_ireland", "additional_property")
    assert ni.total == 11_500
    assert ni.tax_name == "Stamp Duty Land Tax"


def test_sdlt_band_breakdown_sums_to_total():
    result = estimate_transaction_tax(640_000, "england", "additional_property")
    assert sum(b.tax for b in result.bands) == pytest.approx(result.total, abs=1)
    assert [b.rate for b in result.bands] == pytest.approx([0.05, 0.07, 0.10])
    assert result.surcharge_total == pytest.approx(640_000 * 0.05)


@pytest.mark.parametrize(
    ("price", "buyer_type", "expected"),
    [
        # LBTT 55k @ 2% + ADS 8% of 200k
        (200_000, "additional_property", 1_100 + 16_000),
        # First-time buyer nil band to £175k: 25k @ 2%
        (200_000, "first_time_buyer", 500),
        # 105k @ 2% + 75k @ 5% + 75k @ 10%
        (400_000, "home_mover", 2_100 + 3_750 + 7_500),
    ],
)
def test_lbtt_scotland(price, buyer_type, expected):
    assert estimate_transaction_tax(price, "scotland", buyer_type).total == expected


@pytest.mark.parametrize(
    ("price", "buyer_type", "expected"),
    [
        # Main rates: 75k @ 6%
        (300_000, "home_mover", 4_500),
        # Wales has no first-time buyer relief
        (300_000, "first_time_buyer", 4_500),
        # Higher rates: 180k @ 5% + 20k @ 8.5%
        (200_000, "additional_property", 10_700),
    ],
)
def test_ltt_wales(price, buyer_type, expected):
    assert estimate_transaction_tax(price, "wales", buyer_type).total == expected


def test_results_carry_assumptions_and_sources():
    result = estimate_transaction_tax(250_000, "england", "additional_property")
    assert result.source_url.startswith("https://www.gov.uk/")
    assert any("Higher rates" in a for a in result.assumptions)
    assert result.rules_reviewed_on


def test_negative_price_rejected():
    with pytest.raises(ValueError):
        estimate_transaction_tax(-1)
