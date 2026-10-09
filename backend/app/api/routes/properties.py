from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, or_, select

from app.api.deps import DB, CurrentUser
from app.models import Analysis, Property
from app.schemas import (
    AnalysisCreate,
    AnalysisOut,
    PropertyCreate,
    PropertyOut,
    PropertyPage,
    PropertyUpdate,
)
from app.services import deals, market

router = APIRouter(prefix="/properties", tags=["properties"])

SortKey = Literal["newest", "price_asc", "price_desc", "yield_desc", "rent_desc"]


def _out(p: Property) -> PropertyOut:
    o = PropertyOut.model_validate(p)
    o.gross_yield_pct = round(p.estimated_monthly_rent * 12 / p.asking_price * 100, 2) if p.asking_price else None
    return o


@router.get("", response_model=PropertyPage)
def list_properties(
    user: CurrentUser,
    db: DB,
    q: str | None = Query(default=None, max_length=100),
    region: str | None = None,
    property_type: str | None = None,
    min_price: float | None = Query(default=None, ge=0),
    max_price: float | None = Query(default=None, ge=0),
    min_bedrooms: int | None = Query(default=None, ge=0),
    min_yield: float | None = Query(default=None, ge=0, le=100),
    demo: bool | None = None,
    sort: SortKey = "newest",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    gross_yield = Property.estimated_monthly_rent * 12 * 100 / Property.asking_price
    stmt = select(Property).where(Property.owner_id == user.id)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Property.title).like(like),
                func.lower(Property.town).like(like),
                func.lower(func.coalesce(Property.postcode, "")).like(like),
                func.lower(Property.address_line).like(like),
            )
        )
    if region:
        stmt = stmt.where(Property.region == region)
    if property_type:
        stmt = stmt.where(Property.property_type == property_type)
    if min_price is not None:
        stmt = stmt.where(Property.asking_price >= min_price)
    if max_price is not None:
        stmt = stmt.where(Property.asking_price <= max_price)
    if min_bedrooms is not None:
        stmt = stmt.where(Property.bedrooms >= min_bedrooms)
    if min_yield is not None:
        stmt = stmt.where(gross_yield >= min_yield)
    if demo is not None:
        stmt = stmt.where(Property.is_demo.is_(demo))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    order = {
        "newest": Property.created_at.desc(),
        "price_asc": Property.asking_price.asc(),
        "price_desc": Property.asking_price.desc(),
        "yield_desc": gross_yield.desc(),
        "rent_desc": Property.estimated_monthly_rent.desc(),
    }[sort]
    rows = db.scalars(stmt.order_by(order, Property.id).offset((page - 1) * page_size).limit(page_size)).all()
    return PropertyPage(items=[_out(p) for p in rows], total=total, page=page, page_size=page_size)


@router.post("", response_model=PropertyOut, status_code=201)
def create_property(body: PropertyCreate, user: CurrentUser, db: DB):
    p = Property(owner_id=user.id, data_source="manual", **body.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    return _out(p)


@router.post("/demo", response_model=list[PropertyOut], status_code=201)
def load_demo(user: CurrentUser, db: DB):
    return [_out(p) for p in deals.load_demo_portfolio(db, user)]


@router.delete("/demo", status_code=204)
def remove_demo(user: CurrentUser, db: DB):
    for p in db.scalars(select(Property).where(Property.owner_id == user.id, Property.is_demo.is_(True))):
        db.delete(p)
    db.commit()


@router.get("/{property_id}", response_model=PropertyOut)
def get_property(property_id: uuid.UUID, user: CurrentUser, db: DB):
    return _out(deals.get_owned(db, Property, property_id, user))


@router.patch("/{property_id}", response_model=PropertyOut)
def update_property(property_id: uuid.UUID, body: PropertyUpdate, user: CurrentUser, db: DB):
    p = deals.get_owned(db, Property, property_id, user)
    changes = body.model_dump(exclude_unset=True)
    for required in ("title", "asking_price", "estimated_monthly_rent", "region", "property_type", "tenure"):
        if required in changes and changes[required] is None:
            raise HTTPException(status_code=422, detail=f"{required} cannot be null")
    for k, v in changes.items():
        setattr(p, k, v if k != "assumption_overrides" else (v or {}))
    db.commit()
    db.refresh(p)
    return _out(p)


@router.delete("/{property_id}", status_code=204)
def delete_property(property_id: uuid.UUID, user: CurrentUser, db: DB):
    db.delete(deals.get_owned(db, Property, property_id, user))
    db.commit()


@router.get("/{property_id}/market")
def property_market(property_id: uuid.UUID, user: CurrentUser, db: DB, months: int = Query(default=24, ge=3, le=120)):
    p = deals.get_owned(db, Property, property_id, user)
    comps = market.comparables(db, p.postcode, p.property_type, months=months)
    return {
        "comparables": comps,
        "valuation": market.valuation(comps, p.asking_price),
        "coverage_note": "Land Registry Price Paid Data covers England and Wales only."
        if p.region in ("scotland", "northern_ireland")
        else None,
    }


@router.post("/{property_id}/analyses", response_model=AnalysisOut, status_code=201)
def analyse_property(property_id: uuid.UUID, body: AnalysisCreate, user: CurrentUser, db: DB):
    p = deals.get_owned(db, Property, property_id, user)
    inputs = deals.build_inputs(p, deals.profile_values(db, user), body.overrides)
    row = deals.save_analysis(db, user, p, inputs, body.name)
    out = AnalysisOut.model_validate(row)
    out.headline = deals.headline(row.results)
    return out


@router.get("/{property_id}/analyses", response_model=list[AnalysisOut])
def property_analyses(property_id: uuid.UUID, user: CurrentUser, db: DB):
    deals.get_owned(db, Property, property_id, user)
    rows = db.scalars(
        select(Analysis)
        .where(Analysis.property_id == property_id, Analysis.owner_id == user.id)
        .order_by(Analysis.created_at.desc())
        .limit(20)
    ).all()
    outs = []
    for r in rows:
        o = AnalysisOut.model_validate(r)
        o.headline = deals.headline(r.results)
        outs.append(o)
    return outs
