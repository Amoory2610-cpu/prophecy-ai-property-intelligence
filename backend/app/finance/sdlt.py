"""Property transaction tax estimates for residential purchases in the UK.

Three regimes are modelled:

* Stamp Duty Land Tax (SDLT) - England and Northern Ireland (HMRC)
* Land and Buildings Transaction Tax (LBTT) - Scotland (Revenue Scotland)
* Land Transaction Tax (LTT) - Wales (Welsh Revenue Authority)

The rates below are the rates as understood at ``RULES_REVIEWED_ON``. Tax rules
change frequently, and the figures produced here are *estimates* that ignore many
reliefs and special cases (mixed-use property, multiple dwellings relief
replacement rules, linked transactions, companies buying dwellings above
£500,000, shared ownership, leases with rent, etc.). Every result carries these
assumptions so the UI can present them alongside the figure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Region = Literal["england", "northern_ireland", "scotland", "wales"]
BuyerType = Literal["additional_property", "first_time_buyer", "home_mover"]

RULES_REVIEWED_ON = "2026-10-09"

# (upper bound of band in £ or None for "no upper limit", marginal rate as a fraction)
Bands = list[tuple[float | None, float]]

# --- England & Northern Ireland: SDLT, residential rates from 1 April 2025 ---
SDLT_STANDARD: Bands = [
    (125_000, 0.00),
    (250_000, 0.02),
    (925_000, 0.05),
    (1_500_000, 0.10),
    (None, 0.12),
]
# First-time buyer relief from 1 April 2025: only available up to £500,000.
SDLT_FTB: Bands = [
    (300_000, 0.00),
    (500_000, 0.05),
]
SDLT_FTB_MAX_PRICE = 500_000
# Higher rates for additional dwellings: +5 percentage points from 31 October 2024.
SDLT_ADDITIONAL_SURCHARGE = 0.05
# Non-UK-resident surcharge: +2 percentage points from 1 April 2021.
SDLT_NON_RESIDENT_SURCHARGE = 0.02
# Additional-dwelling and LBTT ADS / LTT higher rates do not apply below £40,000.
ADDITIONAL_DWELLING_MIN_PRICE = 40_000

# --- Scotland: LBTT residential rates ---
LBTT_STANDARD: Bands = [
    (145_000, 0.00),
    (250_000, 0.02),
    (325_000, 0.05),
    (750_000, 0.10),
    (None, 0.12),
]
LBTT_FTB: Bands = [
    (175_000, 0.00),
    (250_000, 0.02),
    (325_000, 0.05),
    (750_000, 0.10),
    (None, 0.12),
]
# Additional Dwelling Supplement: 8% of the total price from 5 December 2024.
LBTT_ADS_RATE = 0.08

# --- Wales: LTT residential rates ---
LTT_MAIN: Bands = [
    (225_000, 0.00),
    (400_000, 0.06),
    (750_000, 0.075),
    (1_500_000, 0.10),
    (None, 0.12),
]
# Higher residential rates from 11 December 2024.
LTT_HIGHER: Bands = [
    (180_000, 0.05),
    (250_000, 0.085),
    (400_000, 0.10),
    (750_000, 0.125),
    (1_500_000, 0.15),
    (None, 0.17),
]

SOURCES: dict[str, str] = {
    "england": "https://www.gov.uk/stamp-duty-land-tax/residential-property-rates",
    "northern_ireland": "https://www.gov.uk/stamp-duty-land-tax/residential-property-rates",
    "scotland": "https://revenue.scot/taxes/land-buildings-transaction-tax/residential-property",
    "wales": "https://www.gov.wales/land-transaction-tax-rates-and-bands",
}


@dataclass
class BandCharge:
    lower: float
    upper: float | None
    rate: float
    taxable_amount: float
    tax: float


@dataclass
class TransactionTaxResult:
    tax_name: str
    region: Region
    buyer_type: BuyerType
    price: float
    total: float
    bands: list[BandCharge]
    surcharge_total: float = 0.0
    assumptions: list[str] = field(default_factory=list)
    source_url: str = ""
    rules_reviewed_on: str = RULES_REVIEWED_ON

    @property
    def effective_rate(self) -> float:
        return self.total / self.price if self.price else 0.0


def _progressive(price: float, bands: Bands, uplift: float = 0.0) -> list[BandCharge]:
    """Apply marginal ``bands`` to ``price``, adding ``uplift`` to every band's rate."""
    charges: list[BandCharge] = []
    lower = 0.0
    for upper, rate in bands:
        top = price if upper is None else min(price, upper)
        if top > lower:
            taxable = top - lower
            applied = rate + uplift
            charges.append(BandCharge(lower, upper, applied, taxable, taxable * applied))
        if upper is None or price <= upper:
            break
        lower = upper
    return charges


def _round_down_pound(value: float) -> float:
    # The authorities calculate tax due to the whole pound, rounding down.
    return float(int(value + 1e-9))


def estimate_transaction_tax(
    price: float,
    region: Region = "england",
    buyer_type: BuyerType = "additional_property",
    non_resident: bool = False,
) -> TransactionTaxResult:
    """Estimate the residential transaction tax for a single-dwelling purchase."""
    if price < 0:
        raise ValueError("price must not be negative")

    assumptions = [
        "Single residential dwelling bought freehold or on an existing long lease.",
        "No reliefs or exemptions other than those named are applied.",
        f"Rates as understood on {RULES_REVIEWED_ON}; check the official source before relying on this figure.",
    ]

    if region in ("england", "northern_ireland"):
        return _sdlt(price, region, buyer_type, non_resident, assumptions)
    if region == "scotland":
        return _lbtt(price, buyer_type, non_resident, assumptions)
    if region == "wales":
        return _ltt(price, buyer_type, non_resident, assumptions)
    raise ValueError(f"unsupported region: {region}")


def _sdlt(price, region, buyer_type, non_resident, assumptions) -> TransactionTaxResult:
    surcharge = 0.0
    if buyer_type == "first_time_buyer" and price <= SDLT_FTB_MAX_PRICE:
        bands = SDLT_FTB
        assumptions.append("First-time buyer relief applied (price at or below £500,000).")
    else:
        bands = SDLT_STANDARD
        if buyer_type == "first_time_buyer":
            assumptions.append("First-time buyer relief is not available above £500,000; standard rates applied.")
    if buyer_type == "additional_property":
        if price >= ADDITIONAL_DWELLING_MIN_PRICE:
            surcharge += SDLT_ADDITIONAL_SURCHARGE
            assumptions.append(
                "Higher rates for additional dwellings applied (+5 percentage points on every band), "
                "as is typical for buy-to-let purchases by someone who already owns a home."
            )
        else:
            assumptions.append("Higher rates do not apply to purchases below £40,000.")
    if non_resident:
        surcharge += SDLT_NON_RESIDENT_SURCHARGE
        assumptions.append("Non-UK-resident surcharge applied (+2 percentage points on every band).")

    charges = _progressive(price, bands, surcharge)
    base = sum(c.taxable_amount * (c.rate - surcharge) for c in charges)
    total = _round_down_pound(sum(c.tax for c in charges))
    return TransactionTaxResult(
        tax_name="Stamp Duty Land Tax",
        region=region,
        buyer_type=buyer_type,
        price=price,
        total=total,
        bands=charges,
        surcharge_total=max(0.0, total - base),
        assumptions=assumptions,
        source_url=SOURCES[region],
    )


def _lbtt(price, buyer_type, non_resident, assumptions) -> TransactionTaxResult:
    bands = LBTT_FTB if buyer_type == "first_time_buyer" else LBTT_STANDARD
    if buyer_type == "first_time_buyer":
        assumptions.append("LBTT first-time buyer relief applied (nil-rate band raised to £175,000).")
    charges = _progressive(price, bands)
    surcharge = 0.0
    if buyer_type == "additional_property":
        if price >= ADDITIONAL_DWELLING_MIN_PRICE:
            surcharge = price * LBTT_ADS_RATE
            assumptions.append("Additional Dwelling Supplement applied at 8% of the total price.")
        else:
            assumptions.append("The Additional Dwelling Supplement does not apply below £40,000.")
    if non_resident:
        assumptions.append("Scotland has no non-resident surcharge; the flag has no effect.")
    total = _round_down_pound(sum(c.tax for c in charges) + surcharge)
    return TransactionTaxResult(
        tax_name="Land and Buildings Transaction Tax",
        region="scotland",
        buyer_type=buyer_type,
        price=price,
        total=total,
        bands=charges,
        surcharge_total=surcharge,
        assumptions=assumptions,
        source_url=SOURCES["scotland"],
    )


def _ltt(price, buyer_type, non_resident, assumptions) -> TransactionTaxResult:
    higher = buyer_type == "additional_property" and price >= ADDITIONAL_DWELLING_MIN_PRICE
    bands = LTT_HIGHER if higher else LTT_MAIN
    if higher:
        assumptions.append("LTT higher residential rates applied (additional dwelling).")
    if buyer_type == "first_time_buyer":
        assumptions.append("Wales has no first-time buyer relief; main rates applied.")
    if non_resident:
        assumptions.append("Wales has no non-resident surcharge; the flag has no effect.")
    charges = _progressive(price, bands)
    total = _round_down_pound(sum(c.tax for c in charges))
    surcharge = 0.0
    if higher:
        surcharge = max(0.0, total - sum(c.tax for c in _progressive(price, LTT_MAIN)))
    return TransactionTaxResult(
        tax_name="Land Transaction Tax",
        region="wales",
        buyer_type=buyer_type,
        price=price,
        total=total,
        bands=charges,
        surcharge_total=surcharge,
        assumptions=assumptions,
        source_url=SOURCES["wales"],
    )
