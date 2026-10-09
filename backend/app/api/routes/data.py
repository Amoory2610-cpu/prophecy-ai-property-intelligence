"""Imports, market analytics, reports and the dashboard summary."""

from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy import func, or_, select

from app.api.deps import DB, AdminUser, CurrentUser, SettingsDep
from app.models import AIExplanation, Analysis, Comparison, DataImport, Property, Report, Watchlist
from app.schemas import ImportOut, ReportOut
from app.services import deals, market, reports
from app.services.imports import ppd, properties_csv

router = APIRouter(tags=["data"])

_CSV_TYPES = {"text/csv", "application/vnd.ms-excel", "application/octet-stream", "text/plain", ""}


async def _save_upload(upload: UploadFile, limit_bytes: int) -> tuple[Path, int]:
    if not (upload.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=415, detail="Only .csv files are accepted")
    if (upload.content_type or "") not in _CSV_TYPES:
        raise HTTPException(status_code=415, detail=f"Unsupported content type {upload.content_type}")
    fd, name = tempfile.mkstemp(suffix=".csv")
    size = 0
    with os.fdopen(fd, "wb") as out:
        while chunk := await upload.read(1 << 20):
            size += len(chunk)
            if size > limit_bytes:
                out.close()
                os.unlink(name)
                raise HTTPException(status_code=413, detail=f"File exceeds the {limit_bytes // (1 << 20)} MB limit")
            out.write(chunk)
    return Path(name), size


# --- imports --------------------------------------------------------------------------


@router.get("/imports", response_model=list[ImportOut])
def list_imports(user: CurrentUser, db: DB):
    """The user's own imports plus shared market-data imports (visible to everyone)."""
    rows = db.scalars(
        select(DataImport)
        .where(or_(DataImport.owner_id == user.id, DataImport.kind == "land_registry_ppd"))
        .order_by(DataImport.created_at.desc())
        .limit(100)
    ).all()
    return rows


@router.get("/imports/templates/properties.csv", response_class=PlainTextResponse)
def properties_template():
    return PlainTextResponse(
        properties_csv.TEMPLATE,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="prophecy-properties-template.csv"'},
    )


@router.get("/imports/{import_id}", response_model=ImportOut)
def get_import(import_id: uuid.UUID, user: CurrentUser, db: DB):
    row = db.get(DataImport, import_id)
    if row is None or (row.kind != "land_registry_ppd" and row.owner_id != user.id):
        raise HTTPException(status_code=404, detail="Import not found")
    return row


@router.post("/imports/properties", response_model=ImportOut, status_code=201)
async def import_properties(user: CurrentUser, db: DB, settings: SettingsDep, file: UploadFile = File(...)):
    path, _ = await _save_upload(file, min(settings.max_upload_mb, 10) << 20)
    try:
        return properties_csv.import_properties_csv(db, path.read_bytes(), file.filename or "upload.csv", user.id)
    finally:
        path.unlink(missing_ok=True)


@router.post("/imports/land-registry", response_model=ImportOut, status_code=201)
async def import_land_registry(user: AdminUser, db: DB, settings: SettingsDep, file: UploadFile = File(...)):
    """Admin only: Land Registry data is shared reference data visible to every user."""
    path, _ = await _save_upload(file, settings.max_upload_mb << 20)
    try:
        return ppd.import_price_paid(db, path, file.filename or "pp.csv", owner_id=user.id)
    except ppd.DuplicateImportError as e:
        raise HTTPException(status_code=409, detail=f"This file was already imported ({e.existing.id})") from None
    finally:
        path.unlink(missing_ok=True)


# --- market analytics ---------------------------------------------------------------


@router.get("/market/coverage")
def market_coverage(user: CurrentUser, db: DB):
    return ppd.coverage(db)


@router.get("/market/areas")
def market_areas(user: CurrentUser, db: DB, q: str = Query(min_length=2, max_length=60)):
    return market.search_areas(db, q)


def _area(db, area: str) -> market.Area:
    resolved = market.resolve_area(db, area)
    if resolved is None:
        raise HTTPException(status_code=404, detail=f"No imported Land Registry data matches '{area}'")
    return resolved


def _ppd_type(t: str | None) -> str | None:
    if t and t not in market.PPD_TYPES:
        raise HTTPException(status_code=422, detail="property_type must be one of D, S, T, F, O")
    return t


@router.get("/market/summary")
def market_summary(
    user: CurrentUser,
    db: DB,
    area: str = Query(min_length=1, max_length=60),
    property_type: str | None = None,
    months: int = Query(default=12, ge=1, le=360),
):
    return market.summary(db, _area(db, area), _ppd_type(property_type), months)


@router.get("/market/trend")
def market_trend(
    user: CurrentUser, db: DB, area: str = Query(min_length=1, max_length=60), property_type: str | None = None
):
    return market.trend(db, _area(db, area), _ppd_type(property_type))


@router.get("/market/comparables")
def market_comparables(
    user: CurrentUser,
    db: DB,
    postcode: str,
    property_type: str | None = None,
    months: int = Query(default=24, ge=3, le=120),
):
    return market.comparables(db, postcode, property_type, months)


@router.get("/market/model-evaluation")
def market_model_evaluation(user: CurrentUser, db: DB, holdout_months: int = Query(default=3, ge=1, le=12)):
    return market.evaluate_comparables_model(db, holdout_months=holdout_months)


# --- reports ------------------------------------------------------------------------


@router.post("/analyses/{analysis_id}/reports", response_model=ReportOut, status_code=201)
def create_report(
    analysis_id: uuid.UUID, user: CurrentUser, db: DB, kind: str = Query(default="pdf", pattern="^(pdf|csv)$")
):
    analysis = deals.get_owned(db, Analysis, analysis_id, user)
    prop = db.get(Property, analysis.property_id) if analysis.property_id else None
    info = deals.property_facts(prop) if prop else None
    if prop:
        info = {**info, "address": prop.address_line, "postcode": prop.postcode}
    if kind == "pdf":
        latest = db.scalar(
            select(AIExplanation)
            .where(AIExplanation.analysis_id == analysis.id)
            .order_by(AIExplanation.created_at.desc())
        )
        comps = market.comparables(db, prop.postcode, prop.property_type) if prop and prop.postcode else None
        content = reports.analysis_pdf(
            title=analysis.name,
            results=analysis.results,
            property_info=info,
            explanation={
                "provider": latest.provider,
                "model": latest.model,
                "content": latest.content,
                "unverified_figures": latest.content.get("unverified_figures", []),
            }
            if latest
            else None,
            comparables=comps,
            generated_by=user.full_name or user.email,
        )
        ctype, ext = "application/pdf", "pdf"
    else:
        content = reports.analysis_csv(analysis.name, analysis.results, info)
        ctype, ext = "text/csv", "csv"
    digest = analysis.id.hex[:8]
    r = Report(
        owner_id=user.id,
        analysis_id=analysis.id,
        kind=kind,
        title=analysis.name,
        filename=f"prophecy-analysis-{digest}.{ext}",
        content_type=ctype,
        size_bytes=len(content),
        content=content,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


@router.get("/reports", response_model=list[ReportOut])
def list_reports(user: CurrentUser, db: DB):
    return db.scalars(
        select(Report).where(Report.owner_id == user.id).order_by(Report.created_at.desc()).limit(100)
    ).all()


@router.get("/reports/{report_id}/download")
def download_report(report_id: uuid.UUID, user: CurrentUser, db: DB):
    r = deals.get_owned(db, Report, report_id, user)
    return Response(
        r.content,
        media_type=r.content_type,
        headers={"Content-Disposition": f'attachment; filename="{r.filename}"', "Cache-Control": "no-store"},
    )


@router.delete("/reports/{report_id}", status_code=204)
def delete_report(report_id: uuid.UUID, user: CurrentUser, db: DB):
    db.delete(deals.get_owned(db, Report, report_id, user))
    db.commit()


# --- dashboard ------------------------------------------------------------------------


@router.get("/dashboard")
def dashboard(user: CurrentUser, db: DB):
    props = db.scalars(select(Property).where(Property.owner_id == user.id)).all()
    yields = [p.estimated_monthly_rent * 12 / p.asking_price * 100 for p in props if p.asking_price]
    recent = db.scalars(
        select(Analysis).where(Analysis.owner_id == user.id).order_by(Analysis.created_at.desc()).limit(6)
    ).all()
    titles = {p.id: p.title for p in props}

    def count(model) -> int:
        return db.scalar(select(func.count()).select_from(model).where(model.owner_id == user.id)) or 0

    latest_by_property: dict = {}
    for a in db.scalars(
        select(Analysis)
        .where(Analysis.owner_id == user.id, Analysis.property_id.is_not(None))
        .order_by(Analysis.created_at.desc())
    ):
        latest_by_property.setdefault(a.property_id, a)
    analysed = [
        {"property_id": str(pid), "title": titles.get(pid, ""), **deals.headline(a.results)}
        for pid, a in latest_by_property.items()
        if pid in titles
    ]
    return {
        "counts": {
            "properties": len(props),
            "demo_properties": sum(p.is_demo for p in props),
            "analyses": count(Analysis),
            "comparisons": count(Comparison),
            "watchlists": count(Watchlist),
            "reports": count(Report),
        },
        "portfolio": {
            "total_asking_price": sum(p.asking_price for p in props),
            "total_monthly_rent": sum(p.estimated_monthly_rent for p in props),
            "average_gross_yield_pct": round(sum(yields) / len(yields), 2) if yields else None,
            "best_gross_yield_pct": round(max(yields), 2) if yields else None,
            "analysed_properties": analysed,
        },
        "recent_analyses": [
            {
                "id": str(a.id),
                "name": a.name,
                "property_id": str(a.property_id) if a.property_id else None,
                "created_at": a.created_at,
                **deals.headline(a.results),
            }
            for a in recent
        ],
        "market_data": ppd.coverage(db),
    }
