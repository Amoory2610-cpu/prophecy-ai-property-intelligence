"""Validated inputs for a buy-to-let deal analysis.

All percentages are expressed as percentage points (``5.5`` means 5.5%).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .mortgage import MortgageType
from .sdlt import BuyerType, Region
from .tax import Ownership, TaxBand


class DealInputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Acquisition
    purchase_price: float = Field(gt=0, le=100_000_000, description="Agreed purchase price (£)")
    region: Region = "england"
    buyer_type: BuyerType = "additional_property"
    non_resident: bool = False
    transaction_tax_override: float | None = Field(
        default=None, ge=0, description="Use a known SDLT/LBTT/LTT figure instead of the estimate"
    )
    legal_fees: float = Field(default=1_800, ge=0)
    survey_fees: float = Field(default=600, ge=0)
    refurbishment_costs: float = Field(default=0, ge=0)
    other_purchase_costs: float = Field(default=0, ge=0)

    # Financing
    financing: Literal["mortgage", "cash"] = "mortgage"
    deposit_pct: float = Field(default=25, ge=0, le=100)
    mortgage_type: MortgageType = "interest_only"
    interest_rate_pct: float = Field(default=5.0, ge=0, le=25)
    term_years: int = Field(default=25, ge=1, le=40)
    mortgage_fee: float = Field(default=1_000, ge=0)
    add_fee_to_loan: bool = False
    stress_rate_pct: float = Field(default=5.5, ge=0, le=25)
    required_icr_pct: float = Field(default=125, ge=100, le=300)

    # Income
    monthly_rent: float = Field(ge=0, le=1_000_000)
    vacancy_pct: float = Field(default=4, ge=0, le=100)

    # Operating expenses
    management_pct: float = Field(default=10, ge=0, le=50, description="% of collected rent")
    maintenance_pct: float = Field(default=5, ge=0, le=50, description="% of collected rent")
    insurance_annual: float = Field(default=350, ge=0)
    ground_rent_service_annual: float = Field(default=0, ge=0)
    other_costs_annual: float = Field(
        default=400, ge=0, description="Safety certificates, licensing, accountancy, etc."
    )

    # Holding period and exit
    holding_years: int = Field(default=10, ge=1, le=40)
    capital_growth_pct: float = Field(default=3.0, ge=-20, le=20)
    rent_growth_pct: float = Field(default=2.5, ge=-20, le=20)
    cost_inflation_pct: float = Field(default=3.0, ge=-20, le=20)
    selling_costs_pct: float = Field(default=2.0, ge=0, le=15)

    # Tax scenario
    ownership: Ownership = "individual"
    tax_band: TaxBand = "higher"
    income_tax_rate_override_pct: float | None = Field(default=None, ge=0, le=100)
    include_cgt: bool = True

    @model_validator(mode="after")
    def _check_consistency(self) -> DealInputs:
        if self.management_pct + self.maintenance_pct >= 100:
            raise ValueError("management and maintenance percentages must total less than 100%")
        return self

    @property
    def is_mortgaged(self) -> bool:
        return self.financing == "mortgage" and self.deposit_pct < 100
