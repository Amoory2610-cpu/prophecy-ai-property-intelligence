"""Glue between stored records and the finance engine."""

from __future__ import annotations

import uuid
from typing import Any, TypeVar

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.finance.engine import analyse_deal
from app.finance.inputs import DealInputs
from app.finance.insights import break_even, scenarios, sensitivity
from app.models import Analysis, AssumptionProfile, Property, User
from app.schemas import ASSUMPTION_FIELDS

M = TypeVar("M")

DEFAULT_ASSUMPTIONS: dict[str, Any] = {
    name: field.default for name, field in DealInputs.model_fields.items() if name in ASSUMPTION_FIELDS
}


def get_owned(db: Session, model: type[M], obj_id: uuid.UUID, user: User) -> M:
    """Fetch a row owned by ``user`` or raise 404 (never 403, to avoid leaking existence)."""
    obj = db.get(model, obj_id)
    if obj is None or getattr(obj, "owner_id", None) != user.id:
        raise HTTPException(status_code=404, detail=f"{model.__name__} not found")
    return obj


def get_profile(db: Session, user: User) -> AssumptionProfile | None:
    return db.scalar(
        select(AssumptionProfile).where(AssumptionProfile.owner_id == user.id, AssumptionProfile.is_default.is_(True))
    )


def profile_values(db: Session, user: User) -> dict[str, Any]:
    p = get_profile(db, user)
    return dict(p.values) if p else {}


def build_inputs(prop: Property, profile: dict[str, Any], overrides: dict[str, Any] | None = None) -> DealInputs:
    """Precedence: request overrides > property overrides > user profile > engine defaults.

    Purchase price defaults to the asking price and rent to the property's estimate.
    """
    data: dict[str, Any] = {
        **profile,
        "purchase_price": prop.asking_price,
        "monthly_rent": prop.estimated_monthly_rent,
        "region": prop.region,
        **(prop.assumption_overrides or {}),
        **(overrides or {}),
    }
    return DealInputs.model_validate(data)


def full_analysis(inputs: DealInputs) -> dict[str, Any]:
    analysis = analyse_deal(inputs)
    base, rows = sensitivity(inputs)
    return {
        **analysis.model_dump(mode="json"),
        "break_even": [b.model_dump(mode="json") for b in break_even(inputs)],
        "sensitivity": {
            "base": base.model_dump(mode="json"),
            "rows": [r.model_dump(mode="json") for r in rows],
        },
        "scenarios": [s.model_dump(mode="json") for s in scenarios(inputs)],
    }


HEADLINE_KEYS = ("gross_yield", "net_yield", "monthly_cash_flow", "cash_on_cash", "irr", "initial_cash_required")


def headline(results: dict[str, Any]) -> dict[str, float | None]:
    metrics = {m["key"]: m["value"] for m in results.get("metrics", [])}
    return {k: metrics.get(k) for k in HEADLINE_KEYS}


def property_facts(prop: Property) -> dict[str, Any]:
    """Property details safe to pass to an explanation provider."""
    return {
        "title": prop.title,
        "town": prop.town,
        "postcode_district": (prop.postcode or "").split(" ")[0] or None,
        "region": prop.region,
        "property_type": prop.property_type,
        "tenure": prop.tenure,
        "bedrooms": prop.bedrooms,
        "asking_price": prop.asking_price,
        "estimated_monthly_rent": prop.estimated_monthly_rent,
        "rent_source": prop.rent_source,
        "data_source": prop.data_source,
        "is_demo": prop.is_demo,
    }


def save_analysis(db: Session, user: User, prop: Property | None, inputs: DealInputs, name: str | None) -> Analysis:
    results = full_analysis(inputs)
    row = Analysis(
        owner_id=user.id,
        property_id=prop.id if prop else None,
        name=name or (f"{prop.title} analysis" if prop else "Ad-hoc analysis"),
        inputs=inputs.model_dump(mode="json"),
        results=results,
        engine_version=results["engine_version"],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


DEMO_PROPERTIES: list[dict[str, Any]] = [
    dict(
        title="Two-bed terrace, Fallowfield",
        town="Manchester",
        postcode="M14 6SZ",
        property_type="terraced",
        tenure="freehold",
        bedrooms=2,
        bathrooms=1,
        asking_price=205_000,
        estimated_monthly_rent=1_250,
    ),
    dict(
        title="Three-bed terrace, Headingley",
        town="Leeds",
        postcode="LS6 4AN",
        property_type="terraced",
        tenure="freehold",
        bedrooms=3,
        bathrooms=1,
        asking_price=245_000,
        estimated_monthly_rent=1_450,
    ),
    dict(
        title="Two-bed terrace, Lenton",
        town="Nottingham",
        postcode="NG7 2BU",
        property_type="terraced",
        tenure="freehold",
        bedrooms=2,
        bathrooms=1,
        asking_price=145_000,
        estimated_monthly_rent=950,
    ),
    dict(
        title="Three-bed terrace, Wavertree",
        town="Liverpool",
        postcode="L15 4HX",
        property_type="terraced",
        tenure="freehold",
        bedrooms=3,
        bathrooms=1,
        asking_price=168_000,
        estimated_monthly_rent=1_050,
    ),
    dict(
        title="One-bed city-centre flat",
        town="Manchester",
        postcode="M1 4AB",
        property_type="flat",
        tenure="leasehold",
        bedrooms=1,
        bathrooms=1,
        asking_price=210_000,
        estimated_monthly_rent=1_150,
        assumption_overrides={"ground_rent_service_annual": 1_800},
    ),
    dict(
        title="Two-bed terrace, Cathays",
        town="Cardiff",
        postcode="CF24 2DN",
        region="wales",
        property_type="terraced",
        tenure="freehold",
        bedrooms=2,
        bathrooms=1,
        asking_price=230_000,
        estimated_monthly_rent=1_300,
    ),
    dict(
        title="Two-bed flat, Byker",
        town="Newcastle upon Tyne",
        postcode="NE6 1RJ",
        property_type="flat",
        tenure="leasehold",
        bedrooms=2,
        bathrooms=1,
        asking_price=115_000,
        estimated_monthly_rent=725,
        assumption_overrides={"ground_rent_service_annual": 1_200},
    ),
]

DEMO_NOTE = (
    "Demonstration record. The asking price and rent are illustrative figures chosen for the demo, "
    "not a real listing or market evidence. The postcode is used only to look up real Land Registry "
    "comparable sales in the area."
)


def load_demo_portfolio(db: Session, user: User) -> list[Property]:
    existing = db.scalars(select(Property).where(Property.owner_id == user.id, Property.is_demo.is_(True))).all()
    if existing:
        return list(existing)
    created = []
    for spec in DEMO_PROPERTIES:
        p = Property(
            owner_id=user.id,
            address_line="Demonstration property - no real address",
            rent_source="demo",
            data_source="demo",
            is_demo=True,
            notes=DEMO_NOTE,
            region=spec.get("region", "england"),
            **{k: v for k, v in spec.items() if k != "region"},
        )
        db.add(p)
        created.append(p)
    db.commit()
    return created
