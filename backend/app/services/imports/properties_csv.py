"""Import a user's own property shortlist from CSV.

Every row is validated with the same schema as the API (``PropertyCreate``); rows that
fail are reported with the row number and field, and nothing invalid is stored.
"""

from __future__ import annotations

import hashlib
import io
from datetime import UTC, datetime

import pandas as pd
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.models import DataImport, Property
from app.schemas import PropertyCreate

MAX_ROWS = 5_000
REQUIRED = ["title", "asking_price", "estimated_monthly_rent"]
OPTIONAL = [
    "address_line",
    "town",
    "postcode",
    "region",
    "property_type",
    "tenure",
    "bedrooms",
    "bathrooms",
    "floor_area_sqm",
    "rent_source",
    "listing_url",
    "notes",
]
TEMPLATE = (
    ",".join(REQUIRED + OPTIONAL)
    + "\n"
    + "2 bed flat near station,185000,1050,Flat 4 Example House,Leeds,LS6 1AA,england,flat,"
    "leasehold,2,1,62,agent_quote,,Rent quote from a local agent\n"
)
NUMERIC = {"asking_price", "estimated_monthly_rent", "floor_area_sqm"}
INTEGER = {"bedrooms", "bathrooms"}


def _clean(value: str, column: str):
    v = value.strip()
    if v == "":
        return None
    if column in NUMERIC:
        return v.replace(",", "").replace("£", "")
    if column in INTEGER:
        return v
    if column in {"region", "property_type", "tenure", "rent_source"}:
        return v.lower().replace(" ", "_").replace("-", "_")
    return v


def import_properties_csv(db: Session, content: bytes, filename: str, owner_id) -> DataImport:
    record = DataImport(
        owner_id=owner_id,
        kind="properties_csv",
        status="processing",
        filename=filename[:255],
        sha256=hashlib.sha256(content).hexdigest(),
        source_name="User-supplied CSV",
        licence=None,
        attribution="Property details and rent figures supplied by the user; not independently verified.",
    )
    db.add(record)
    db.flush()

    errors: list[dict] = []
    imported = 0
    try:
        df = pd.read_csv(io.BytesIO(content), dtype=str, keep_default_na=False, encoding="utf-8-sig")
    except (pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError) as e:
        record.status = "failed"
        record.errors = [{"row": 0, "error": f"could not parse CSV: {e}"[:500]}]
        record.completed_at = datetime.now(UTC)
        db.commit()
        return record

    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    missing = [c for c in REQUIRED if c not in df.columns]
    unknown = [c for c in df.columns if c not in REQUIRED + OPTIONAL]
    if missing or len(df) == 0 or len(df) > MAX_ROWS:
        msg = (
            f"missing required columns: {', '.join(missing)}"
            if missing
            else "the file contained no data rows"
            if len(df) == 0
            else f"too many rows ({len(df)}); the limit is {MAX_ROWS}"
        )
        record.status = "failed"
        record.rows_total = len(df)
        record.errors = [{"row": 0, "error": msg}]
        record.completed_at = datetime.now(UTC)
        db.commit()
        return record
    if unknown:
        errors.append({"row": 0, "error": f"ignored unknown columns: {', '.join(unknown)}"})

    for i, raw in enumerate(df.to_dict(orient="records"), start=2):  # row 1 is the header
        data = {k: _clean(v, k) for k, v in raw.items() if k in REQUIRED + OPTIONAL and _clean(v, k) is not None}
        try:
            item = PropertyCreate.model_validate(data)
        except ValidationError as e:
            for err in e.errors()[:5]:
                field = ".".join(str(p) for p in err["loc"]) or "row"
                errors.append({"row": i, "field": field, "error": err["msg"]})
            continue
        db.add(
            Property(
                owner_id=owner_id,
                data_source="csv_import",
                import_id=record.id,
                **item.model_dump(),
            )
        )
        imported += 1

    rejected = len({e["row"] for e in errors if e["row"] > 0})
    record.rows_total = len(df)
    record.rows_imported = imported
    record.rows_rejected = rejected
    record.errors = errors[:200]
    record.status = "failed" if imported == 0 else "completed_with_errors" if rejected else "completed"
    record.completed_at = datetime.now(UTC)
    db.commit()
    db.refresh(record)
    return record
