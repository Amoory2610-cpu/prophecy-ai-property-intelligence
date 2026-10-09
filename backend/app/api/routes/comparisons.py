from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.finance.engine import analyse_deal
from app.models import Comparison, ComparisonItem, Property, Report
from app.schemas import ComparisonCreate, ComparisonOut, ComparisonUpdate, ReportOut
from app.services import deals, reports

router = APIRouter(prefix="/comparisons", tags=["comparisons"])

# Overrides that describe the property itself and so stay per-property in a comparison.
PROPERTY_SPECIFIC = ("purchase_price", "ground_rent_service_annual", "insurance_annual", "refurbishment_costs")

# (metric key, label, unit, higher_is_better)
COMPARE_METRICS = [
    ("gross_yield", "Gross yield", "percent", True),
    ("net_yield", "Net yield", "percent", True),
    ("monthly_cash_flow", "Monthly cash flow (pre-tax)", "gbp_month", True),
    ("monthly_cash_flow_after_tax", "Monthly cash flow (after tax)", "gbp_month", True),
    ("cash_on_cash", "Cash-on-cash return", "percent", True),
    ("initial_cash_required", "Initial cash required", "gbp", False),
    ("ltv", "Loan to value", "percent", False),
    ("icr", "Interest cover", "percent", True),
    ("irr", "Annualised return (IRR)", "percent", True),
    ("total_profit", "Total profit", "gbp", True),
]


def _out(c: Comparison) -> ComparisonOut:
    return ComparisonOut(
        id=c.id,
        name=c.name,
        assumptions=c.assumptions,
        property_ids=[i.property_id for i in c.items],
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


def _owned_properties(db, user, ids: list[uuid.UUID]) -> list[Property]:
    props = db.scalars(select(Property).where(Property.id.in_(ids), Property.owner_id == user.id)).all()
    by_id = {p.id: p for p in props}
    missing = [str(i) for i in ids if i not in by_id]
    if missing:
        raise HTTPException(status_code=404, detail=f"Property not found: {', '.join(missing)}")
    return [by_id[i] for i in ids]


def compute(db, user, props: list[Property], shared: dict[str, Any]) -> dict[str, Any]:
    profile = deals.profile_values(db, user)
    rows: list[dict[str, Any]] = []
    for p in props:
        specific = {k: v for k, v in (p.assumption_overrides or {}).items() if k in PROPERTY_SPECIFIC}
        inputs = deals.DealInputs.model_validate(
            {
                **profile,
                **shared,
                "purchase_price": p.asking_price,
                "monthly_rent": p.estimated_monthly_rent,
                "region": p.region,
                **specific,
            }
        )
        a = analyse_deal(inputs)
        row = {
            "property_id": str(p.id),
            "title": p.title,
            "town": p.town,
            "is_demo": p.is_demo,
            "purchase_price": inputs.purchase_price,
            "monthly_rent": inputs.monthly_rent,
            "transaction_tax": a.value("transaction_tax"),
            "monthly_mortgage_payment": a.value("monthly_mortgage_payment"),
            "property_specific_overrides": specific,
            "warnings": a.warnings[:3],
        }
        for key, *_ in COMPARE_METRICS:
            row[key] = a.returns.total_profit if key == "total_profit" else a.value(key)
        rows.append(row)

    leaders: dict[str, dict[str, Any]] = {}
    for key, label, unit, higher in COMPARE_METRICS:
        vals = [(r[key], r) for r in rows if r[key] is not None]
        if len(vals) < 2:
            continue
        best = max(vals, key=lambda v: v[0]) if higher else min(vals, key=lambda v: v[0])
        worst = min(vals, key=lambda v: v[0]) if higher else max(vals, key=lambda v: v[0])
        leaders[key] = {
            "label": label,
            "unit": unit,
            "best_property_id": best[1]["property_id"],
            "worst_property_id": worst[1]["property_id"],
            "higher_is_better": higher,
        }

    return {
        "rows": rows,
        "metrics": [{"key": k, "label": label, "unit": u, "higher_is_better": h} for k, label, u, h in COMPARE_METRICS],
        "leaders": leaders,
        "tradeoffs": tradeoffs(rows, leaders),
        "shared_assumptions": {**deals.DEFAULT_ASSUMPTIONS, **profile, **shared},
        "note": "All properties use the same financing, cost and growth assumptions. Only purchase price, "
        "rent, region and property-specific costs (service charge, insurance, refurbishment) differ. "
        "No single property is ranked best overall - the right choice depends on your goals.",
    }


def tradeoffs(rows: list[dict[str, Any]], leaders: dict[str, dict[str, Any]]) -> list[str]:
    by_id = {r["property_id"]: r for r in rows}
    out: list[str] = []

    def name(pid: str) -> str:
        return by_id[pid]["title"]

    pairs = [
        ("gross_yield", "irr", "the highest gross yield", "the highest estimated annualised return"),
        ("monthly_cash_flow", "irr", "the strongest monthly cash flow", "the highest estimated annualised return"),
        ("initial_cash_required", "irr", "the lowest cash requirement", "the highest estimated annualised return"),
        (
            "monthly_cash_flow",
            "initial_cash_required",
            "the strongest monthly cash flow",
            "the lowest cash requirement",
        ),
    ]
    for a, b, a_text, b_text in pairs:
        if a in leaders and b in leaders and leaders[a]["best_property_id"] != leaders[b]["best_property_id"]:
            out.append(
                f"{name(leaders[a]['best_property_id'])} has {a_text}, while "
                f"{name(leaders[b]['best_property_id'])} has {b_text}."
            )
    negative = [r["title"] for r in rows if (r["monthly_cash_flow"] or 0) < 0]
    if negative:
        out.append(f"Cash-flow negative before tax on these assumptions: {', '.join(negative)}.")
    low_icr = [r["title"] for r in rows if r["icr"] is not None and r["icr"] < 125]
    if low_icr:
        out.append(f"May fail a 125% lender stress test: {', '.join(low_icr)}.")
    if "irr" in leaders:
        out.append(
            "Annualised returns depend on the shared capital-growth assumption; properties with lower "
            "yields rely more on growth to deliver their return."
        )
    return list(dict.fromkeys(out))


@router.get("", response_model=list[ComparisonOut])
def list_comparisons(user: CurrentUser, db: DB):
    rows = db.scalars(select(Comparison).where(Comparison.owner_id == user.id).order_by(Comparison.updated_at.desc()))
    return [_out(c) for c in rows]


@router.post("", response_model=ComparisonOut, status_code=201)
def create_comparison(body: ComparisonCreate, user: CurrentUser, db: DB):
    _owned_properties(db, user, body.property_ids)
    c = Comparison(owner_id=user.id, name=body.name, assumptions=body.assumptions)
    c.items = [ComparisonItem(property_id=pid, position=i) for i, pid in enumerate(body.property_ids)]
    db.add(c)
    db.commit()
    db.refresh(c)
    return _out(c)


@router.get("/{comparison_id}", response_model=ComparisonOut)
def get_comparison(comparison_id: uuid.UUID, user: CurrentUser, db: DB):
    return _out(deals.get_owned(db, Comparison, comparison_id, user))


@router.patch("/{comparison_id}", response_model=ComparisonOut)
def update_comparison(comparison_id: uuid.UUID, body: ComparisonUpdate, user: CurrentUser, db: DB):
    c = deals.get_owned(db, Comparison, comparison_id, user)
    if body.name is not None:
        c.name = body.name
    if body.assumptions is not None:
        c.assumptions = body.assumptions
    if body.property_ids is not None:
        if len(set(body.property_ids)) != len(body.property_ids):
            raise HTTPException(status_code=422, detail="property_ids must be unique")
        _owned_properties(db, user, body.property_ids)
        c.items.clear()
        db.flush()
        c.items = [ComparisonItem(property_id=pid, position=i) for i, pid in enumerate(body.property_ids)]
    db.commit()
    db.refresh(c)
    return _out(c)


@router.delete("/{comparison_id}", status_code=204)
def delete_comparison(comparison_id: uuid.UUID, user: CurrentUser, db: DB):
    db.delete(deals.get_owned(db, Comparison, comparison_id, user))
    db.commit()


@router.get("/{comparison_id}/results")
def comparison_results(comparison_id: uuid.UUID, user: CurrentUser, db: DB):
    c = deals.get_owned(db, Comparison, comparison_id, user)
    props = _owned_properties(db, user, [i.property_id for i in c.items])
    return {"comparison": _out(c).model_dump(mode="json"), **compute(db, user, props, c.assumptions)}


@router.post("/{comparison_id}/export", response_model=ReportOut, status_code=201)
def export_comparison(comparison_id: uuid.UUID, user: CurrentUser, db: DB):
    c = deals.get_owned(db, Comparison, comparison_id, user)
    props = _owned_properties(db, user, [i.property_id for i in c.items])
    result = compute(db, user, props, c.assumptions)
    flat = [
        {k: v for k, v in r.items() if k not in ("warnings", "property_specific_overrides")} for r in result["rows"]
    ]
    content = reports.comparison_csv(c.name, flat, c.assumptions)
    r = Report(
        owner_id=user.id,
        comparison_id=c.id,
        kind="csv",
        title=f"{c.name} - comparison",
        filename=f"comparison-{c.id.hex[:8]}.csv",
        content_type="text/csv",
        size_bytes=len(content),
        content=content,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


@router.get("/{comparison_id}/export.csv")
def export_comparison_direct(comparison_id: uuid.UUID, user: CurrentUser, db: DB):
    c = deals.get_owned(db, Comparison, comparison_id, user)
    props = _owned_properties(db, user, [i.property_id for i in c.items])
    result = compute(db, user, props, c.assumptions)
    flat = [
        {k: v for k, v in r.items() if k not in ("warnings", "property_specific_overrides")} for r in result["rows"]
    ]
    return Response(
        reports.comparison_csv(c.name, flat, c.assumptions),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="comparison-{c.id.hex[:8]}.csv"'},
    )
