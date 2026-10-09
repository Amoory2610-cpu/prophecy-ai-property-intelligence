from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import DB, CurrentUser, SettingsDep
from app.finance.inputs import DealInputs
from app.finance.insights import (
    DEFAULT_OPTIMISTIC,
    DEFAULT_PESSIMISTIC,
    ScenarioAdjustments,
    scenarios,
)
from app.finance.sdlt import RULES_REVIEWED_ON, SOURCES, estimate_transaction_tax
from app.finance.tax import TAX_RULES_REVIEWED_ON
from app.models import AIExplanation, Analysis, AssumptionProfile, Property
from app.schemas import AnalysisOut, AnalysisSummary, AssumptionsIn, AssumptionsOut, ExplanationOut
from app.services import deals, market
from app.services.ai.service import build_context, explain

router = APIRouter(tags=["analysis"])


@router.post("/calculate")
def calculate(inputs: DealInputs, user: CurrentUser):
    """Stateless calculation used by the live calculator and scenario simulator."""
    return deals.full_analysis(inputs)


class ScenarioRequest(BaseModel):
    inputs: DealInputs
    optimistic: ScenarioAdjustments = DEFAULT_OPTIMISTIC
    pessimistic: ScenarioAdjustments = DEFAULT_PESSIMISTIC


@router.post("/scenarios")
def run_scenarios(body: ScenarioRequest, user: CurrentUser):
    results = scenarios(body.inputs, body.optimistic, body.pessimistic)
    return {
        "scenarios": [r.model_dump(mode="json") for r in results],
        "note": "Driver impacts apply each adjustment on its own to the base case; combined effects "
        "interact, so impacts need not sum to the total difference.",
    }


@router.get("/rules")
def rules():
    """Tax rule metadata so the UI can show freshness and sources."""
    examples = {region: estimate_transaction_tax(250_000, region, "additional_property").total for region in SOURCES}
    return {
        "transaction_tax_rules_reviewed_on": RULES_REVIEWED_ON,
        "income_tax_rules_reviewed_on": TAX_RULES_REVIEWED_ON,
        "sources": SOURCES,
        "example_additional_property_250k": examples,
    }


@router.get("/assumptions", response_model=AssumptionsOut)
def get_assumptions(user: CurrentUser, db: DB):
    p = deals.get_profile(db, user)
    values = dict(p.values) if p else {}
    return AssumptionsOut(
        values=values, effective={**deals.DEFAULT_ASSUMPTIONS, **values}, updated_at=p.updated_at if p else None
    )


@router.put("/assumptions", response_model=AssumptionsOut)
def put_assumptions(body: AssumptionsIn, user: CurrentUser, db: DB):
    p = deals.get_profile(db, user)
    if p is None:
        p = AssumptionProfile(owner_id=user.id, name="Default", is_default=True, values={})
        db.add(p)
    p.values = body.values
    db.commit()
    db.refresh(p)
    return AssumptionsOut(values=p.values, effective={**deals.DEFAULT_ASSUMPTIONS, **p.values}, updated_at=p.updated_at)


@router.get("/analyses", response_model=list[AnalysisSummary])
def list_analyses(user: CurrentUser, db: DB, limit: int = Query(default=50, ge=1, le=200)):
    rows = db.scalars(
        select(Analysis).where(Analysis.owner_id == user.id).order_by(Analysis.created_at.desc()).limit(limit)
    ).all()
    out = []
    for r in rows:
        s = AnalysisSummary.model_validate(r)
        s.headline = deals.headline(r.results)
        out.append(s)
    return out


class AdhocAnalysisIn(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    inputs: DealInputs


@router.post("/analyses", response_model=AnalysisOut, status_code=201)
def save_adhoc(body: AdhocAnalysisIn, user: CurrentUser, db: DB):
    row = deals.save_analysis(db, user, None, body.inputs, body.name)
    out = AnalysisOut.model_validate(row)
    out.headline = deals.headline(row.results)
    return out


@router.get("/analyses/{analysis_id}", response_model=AnalysisOut)
def get_analysis(analysis_id: uuid.UUID, user: CurrentUser, db: DB):
    r = deals.get_owned(db, Analysis, analysis_id, user)
    out = AnalysisOut.model_validate(r)
    out.headline = deals.headline(r.results)
    return out


@router.delete("/analyses/{analysis_id}", status_code=204)
def delete_analysis(analysis_id: uuid.UUID, user: CurrentUser, db: DB):
    db.delete(deals.get_owned(db, Analysis, analysis_id, user))
    db.commit()


def _explanation_context(db, analysis: Analysis) -> dict[str, Any]:
    prop = db.get(Property, analysis.property_id) if analysis.property_id else None
    results = analysis.results
    extras: dict[str, Any] = {
        "break_even": results.get("break_even", []),
        "sensitivity": results.get("sensitivity", {}).get("rows", []),
        "scenarios": [
            {k: s[k] for k in ("name", "monthly_cash_flow", "irr_pct", "net_yield_pct")}
            for s in results.get("scenarios", [])
        ],
    }
    if prop and prop.postcode:
        comps = market.comparables(db, prop.postcode, prop.property_type)
        if comps.get("available"):
            extras["comparables"] = {
                "source": "HM Land Registry Price Paid Data",
                "level": comps["level"],
                "area": comps["area"],
                "period": comps["period"],
                "stats": comps["stats"],
            }
    return build_context(results, deals.property_facts(prop) if prop else None, extras)


@router.post("/analyses/{analysis_id}/explanations", response_model=ExplanationOut, status_code=201)
def create_explanation(analysis_id: uuid.UUID, user: CurrentUser, db: DB, settings: SettingsDep):
    analysis = deals.get_owned(db, Analysis, analysis_id, user)
    context = _explanation_context(db, analysis)
    result = explain(context, settings)
    row = AIExplanation(
        analysis_id=analysis.id,
        provider=result.provider,
        model=result.model,
        content={
            **result.content.model_dump(mode="json"),
            "unverified_figures": result.unverified_figures,
            "notice": result.notice,
        },
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/analyses/{analysis_id}/explanations", response_model=list[ExplanationOut])
def list_explanations(analysis_id: uuid.UUID, user: CurrentUser, db: DB):
    analysis = deals.get_owned(db, Analysis, analysis_id, user)
    return sorted(analysis.explanations, key=lambda e: e.created_at, reverse=True)


@router.get("/ai/status")
def ai_status(user: CurrentUser, settings: SettingsDep):
    return {
        "configured": settings.ai_configured,
        "provider": settings.ai_provider if settings.ai_configured else "rule_based",
        "model": (
            settings.anthropic_model
            if settings.ai_provider == "anthropic"
            else settings.openai_model
            if settings.ai_provider == "openai"
            else "prophecy-rules-v1"
        )
        if settings.ai_configured
        else "prophecy-rules-v1",
    }
