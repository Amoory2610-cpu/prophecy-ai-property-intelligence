"""Request/response schemas for the HTTP API."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.finance.inputs import DealInputs
from app.services import postcodes

PropertyType = Literal["detached", "semi_detached", "terraced", "flat", "bungalow", "other"]
Tenure = Literal["freehold", "leasehold", "share_of_freehold"]
RentSource = Literal["user_estimate", "agent_quote", "current_tenancy", "demo"]
RegionT = Literal["england", "northern_ireland", "scotland", "wales"]

# Deal inputs that describe financing/operating assumptions rather than the property itself.
ASSUMPTION_FIELDS = frozenset(DealInputs.model_fields) - {"purchase_price", "monthly_rent", "region"}


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- auth & users ---------------------------------------------------------------


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    full_name: str = Field(default="", max_length=120)

    @field_validator("password")
    @classmethod
    def _strength(cls, v: str) -> str:
        has_letter = any(c.isalpha() for c in v)
        has_other = any(not c.isalpha() for c in v)
        if not (has_letter and has_other):
            raise ValueError("password must mix letters with numbers or symbols")
        return v


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(ORM):
    id: uuid.UUID
    email: str
    full_name: str
    is_admin: bool
    created_at: datetime


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=120)
    email: EmailStr | None = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10, max_length=128)


class AccountDelete(BaseModel):
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# --- properties -------------------------------------------------------------------


def _check_postcode(v: str | None) -> str | None:
    if v is None or not v.strip():
        return None
    pc = postcodes.normalise(v)
    if not pc:
        raise ValueError("not a valid UK postcode")
    return pc


def _check_url(v: str | None) -> str | None:
    if v and not v.startswith(("http://", "https://")):
        raise ValueError("listing URL must start with http:// or https://")
    return v or None


class PropertyBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    address_line: str = Field(default="", max_length=300)
    town: str = Field(default="", max_length=120)
    postcode: str | None = Field(default=None, max_length=10)
    region: RegionT = "england"
    property_type: PropertyType = "flat"
    tenure: Tenure = "leasehold"
    bedrooms: int | None = Field(default=None, ge=0, le=50)
    bathrooms: int | None = Field(default=None, ge=0, le=50)
    floor_area_sqm: float | None = Field(default=None, gt=0, le=10_000)
    asking_price: float = Field(gt=0, le=100_000_000)
    estimated_monthly_rent: float = Field(ge=0, le=1_000_000)
    rent_source: RentSource = "user_estimate"
    listing_url: str | None = Field(default=None, max_length=500)
    notes: str = Field(default="", max_length=5_000)
    assumption_overrides: dict[str, Any] = Field(default_factory=dict)

    @field_validator("postcode")
    @classmethod
    def _postcode(cls, v: str | None) -> str | None:
        return _check_postcode(v)

    @field_validator("listing_url")
    @classmethod
    def _url(cls, v: str | None) -> str | None:
        return _check_url(v)

    @field_validator("assumption_overrides")
    @classmethod
    def _overrides(cls, v: dict[str, Any]) -> dict[str, Any]:
        return validate_assumptions(v, allow_price=True)


class PropertyCreate(PropertyBase):
    pass


class PropertyUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    address_line: str | None = Field(default=None, max_length=300)
    town: str | None = Field(default=None, max_length=120)
    postcode: str | None = Field(default=None, max_length=10)
    region: RegionT | None = None
    property_type: PropertyType | None = None
    tenure: Tenure | None = None
    bedrooms: int | None = Field(default=None, ge=0, le=50)
    bathrooms: int | None = Field(default=None, ge=0, le=50)
    floor_area_sqm: float | None = Field(default=None, gt=0, le=10_000)
    asking_price: float | None = Field(default=None, gt=0, le=100_000_000)
    estimated_monthly_rent: float | None = Field(default=None, ge=0, le=1_000_000)
    rent_source: RentSource | None = None
    listing_url: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=5_000)
    assumption_overrides: dict[str, Any] | None = None

    @field_validator("postcode")
    @classmethod
    def _postcode(cls, v: str | None) -> str | None:
        return _check_postcode(v)

    @field_validator("listing_url")
    @classmethod
    def _url(cls, v: str | None) -> str | None:
        return _check_url(v)

    @field_validator("assumption_overrides")
    @classmethod
    def _overrides(cls, v):
        return None if v is None else validate_assumptions(v, allow_price=True)


class PropertyOut(ORM):
    id: uuid.UUID
    title: str
    address_line: str
    town: str
    postcode: str | None
    region: str
    property_type: str
    tenure: str
    bedrooms: int | None
    bathrooms: int | None
    floor_area_sqm: float | None
    asking_price: float
    estimated_monthly_rent: float
    rent_source: str
    listing_url: str | None
    notes: str
    data_source: str
    import_id: uuid.UUID | None
    is_demo: bool
    assumption_overrides: dict[str, Any]
    gross_yield_pct: float | None = None
    created_at: datetime
    updated_at: datetime


class PropertyPage(BaseModel):
    items: list[PropertyOut]
    total: int
    page: int
    page_size: int


def validate_assumptions(values: dict[str, Any], allow_price: bool = False) -> dict[str, Any]:
    """Validate a partial set of DealInputs fields by merging them onto a valid base deal."""
    allowed = set(ASSUMPTION_FIELDS) | ({"purchase_price"} if allow_price else set())
    unknown = set(values) - allowed
    if unknown:
        raise ValueError(f"unknown assumption fields: {', '.join(sorted(unknown))}")
    probe = {"purchase_price": 100_000, "monthly_rent": 500, **values}
    DealInputs.model_validate(probe)  # raises ValidationError with field detail
    return values


class AssumptionsIn(BaseModel):
    values: dict[str, Any]

    @field_validator("values")
    @classmethod
    def _v(cls, v):
        return validate_assumptions(v)


class AssumptionsOut(BaseModel):
    values: dict[str, Any]
    effective: dict[str, Any]
    updated_at: datetime | None


# --- analyses -----------------------------------------------------------------------


class AnalysisCreate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    overrides: dict[str, Any] = Field(default_factory=dict)

    @field_validator("overrides")
    @classmethod
    def _o(cls, v):
        allowed = set(DealInputs.model_fields)
        unknown = set(v) - allowed
        if unknown:
            raise ValueError(f"unknown fields: {', '.join(sorted(unknown))}")
        return v


class AnalysisSummary(ORM):
    id: uuid.UUID
    property_id: uuid.UUID | None
    name: str
    engine_version: str
    created_at: datetime
    headline: dict[str, float | None] = {}


class AnalysisOut(AnalysisSummary):
    inputs: dict[str, Any]
    results: dict[str, Any]


class ExplanationOut(ORM):
    id: uuid.UUID
    analysis_id: uuid.UUID
    provider: str
    model: str
    content: dict[str, Any]
    created_at: datetime


class CalculateOut(BaseModel):
    analysis: dict[str, Any]
    break_even: list[dict[str, Any]]
    sensitivity: dict[str, Any]


# --- comparisons and watchlists ---------------------------------------------------------


class ComparisonCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    property_ids: list[uuid.UUID] = Field(min_length=2, max_length=6)
    assumptions: dict[str, Any] = Field(default_factory=dict)

    @field_validator("assumptions")
    @classmethod
    def _a(cls, v):
        return validate_assumptions(v)

    @field_validator("property_ids")
    @classmethod
    def _unique(cls, v):
        if len(set(v)) != len(v):
            raise ValueError("property_ids must be unique")
        return v


class ComparisonUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    property_ids: list[uuid.UUID] | None = Field(default=None, min_length=2, max_length=6)
    assumptions: dict[str, Any] | None = None

    @field_validator("assumptions")
    @classmethod
    def _a(cls, v):
        return None if v is None else validate_assumptions(v)


class ComparisonOut(ORM):
    id: uuid.UUID
    name: str
    assumptions: dict[str, Any]
    property_ids: list[uuid.UUID]
    created_at: datetime
    updated_at: datetime


class WatchlistCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2_000)


class WatchlistUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2_000)


class WatchlistItemIn(BaseModel):
    property_id: uuid.UUID
    note: str = Field(default="", max_length=2_000)


class WatchlistItemOut(ORM):
    id: uuid.UUID
    property_id: uuid.UUID
    note: str
    added_at: datetime
    property: PropertyOut


class WatchlistOut(ORM):
    id: uuid.UUID
    name: str
    description: str
    created_at: datetime
    items: list[WatchlistItemOut]


# --- imports, market, reports ---------------------------------------------------------


class ImportOut(ORM):
    id: uuid.UUID
    kind: str
    status: str
    filename: str
    sha256: str
    rows_total: int
    rows_imported: int
    rows_rejected: int
    errors: list[dict[str, Any]]
    source_name: str
    source_url: str | None
    licence: str | None
    attribution: str | None
    data_from: date | None
    data_to: date | None
    created_at: datetime
    completed_at: datetime | None


class ReportOut(ORM):
    id: uuid.UUID
    analysis_id: uuid.UUID | None
    comparison_id: uuid.UUID | None
    kind: str
    title: str
    filename: str
    content_type: str
    size_bytes: int
    created_at: datetime
