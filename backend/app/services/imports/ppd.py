"""Importer for HM Land Registry Price Paid Data (PPD).

Accepts the official CSV files (no header, 16 columns) published at
https://www.gov.uk/government/statistical-data-sets/price-paid-data-downloads as well as
copies that include a header row. Rows are validated column-by-column with pandas;
invalid rows are rejected with a reason and never imported.

Record status handling follows the PPD specification: ``A`` (addition) and ``C``
(change) rows are upserted on ``transaction_id``; ``D`` (deletion) rows remove the
transaction.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import delete, func, select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import Session

from app.models import DataImport, PricePaidTransaction

COLUMNS = [
    "transaction_id",
    "price",
    "date_of_transfer",
    "postcode",
    "property_type",
    "new_build",
    "duration",
    "paon",
    "saon",
    "street",
    "locality",
    "town_city",
    "district",
    "county",
    "ppd_category_type",
    "record_status",
]

SOURCE_NAME = "HM Land Registry Price Paid Data"
SOURCE_URL = "https://www.gov.uk/government/statistical-data-sets/price-paid-data-downloads"
LICENCE = "Open Government Licence v3.0"
ATTRIBUTION = (
    "Contains HM Land Registry data © Crown copyright and database right. "
    "This data is licensed under the Open Government Licence v3.0."
)

MAX_STORED_ERRORS = 200
CHUNK_SIZE = 50_000
_TID_RE = r"\{[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\}"
_PC_RE = r"[A-Z]{1,2}[0-9][A-Z0-9]? [0-9][A-Z]{2}"


class DuplicateImportError(Exception):
    def __init__(self, existing: DataImport):
        self.existing = existing
        super().__init__(f"file already imported on {existing.created_at:%Y-%m-%d}")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _has_header(path: Path) -> bool:
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        first = f.readline().strip().strip('"').lower()
    return first.startswith("transaction")


def validate_chunk(df: pd.DataFrame, first_row_number: int) -> tuple[pd.DataFrame, list[dict]]:
    """Return ``(valid_rows, errors)``; row numbers are 1-based data rows."""
    df = df.copy()
    for col in COLUMNS:
        df[col] = df[col].fillna("").astype(str).str.strip()

    reasons = pd.Series([""] * len(df), index=df.index, dtype=object)

    def flag(mask: pd.Series, reason: str) -> None:
        reasons[mask & (reasons == "")] = reason

    flag(~df["transaction_id"].str.fullmatch(_TID_RE), "transaction_id is not a Land Registry GUID")
    price = pd.to_numeric(df["price"], errors="coerce")
    flag(price.isna(), "price is not a number")
    flag(price.notna() & ((price <= 0) | (price > 1_000_000_000)), "price out of range")
    dates = pd.to_datetime(df["date_of_transfer"].str[:10], format="%Y-%m-%d", errors="coerce")
    flag(dates.isna(), "date_of_transfer is not a valid date")
    flag(dates.notna() & (dates.dt.year < 1995), "date_of_transfer before 1995")
    flag(~df["property_type"].isin(list("DSTFO")), "property_type must be D, S, T, F or O")
    flag(~df["new_build"].isin(["Y", "N"]), "new_build must be Y or N")
    flag(~df["duration"].isin(["F", "L", "U"]), "duration must be F, L or U")
    flag(~df["ppd_category_type"].isin(["A", "B"]), "ppd_category_type must be A or B")
    status = df["record_status"].replace("", "A")
    flag(~status.isin(["A", "C", "D"]), "record_status must be A, C or D")

    bad = reasons != ""
    errors = [
        {
            "row": int(first_row_number + pos),
            "transaction_id": df.at[idx, "transaction_id"][:40],
            "error": reasons[idx],
        }
        for pos, idx in enumerate(df.index)
        if bad[idx]
    ]

    good = df[~bad].copy()
    good["price"] = price[~bad].astype("int64")
    good["date_of_transfer"] = dates[~bad].dt.date
    good["record_status"] = status[~bad]
    pc = good["postcode"].str.upper().str.replace(r"\s+", " ", regex=True)
    pc_ok = pc.str.fullmatch(_PC_RE)
    good["postcode"] = pc.where(pc_ok, None)
    good["postcode_district"] = good["postcode"].str.split(" ").str[0]
    good["postcode_sector"] = good["postcode"].str[:-2]
    for col in ("street", "locality", "town_city", "district", "county"):
        good[col] = good[col].str.title()
    return good, errors


def _upsert(db: Session, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    dialect = db.get_bind().dialect.name
    insert = postgresql.insert if dialect == "postgresql" else sqlite.insert
    stmt = insert(PricePaidTransaction)
    update_cols = {c: getattr(stmt.excluded, c) for c in rows[0] if c not in ("transaction_id",)}
    stmt = stmt.on_conflict_do_update(index_elements=["transaction_id"], set_=update_cols)
    for start in range(0, len(rows), 5_000):
        db.execute(stmt, rows[start : start + 5_000])


def import_price_paid(
    db: Session,
    path: Path,
    filename: str,
    owner_id=None,
    allow_duplicate: bool = False,
    max_rows: int | None = None,
) -> DataImport:
    digest = sha256_file(path)
    if not allow_duplicate:
        existing = db.scalar(
            select(DataImport).where(
                DataImport.kind == "land_registry_ppd",
                DataImport.sha256 == digest,
                DataImport.status != "failed",
            )
        )
        if existing:
            raise DuplicateImportError(existing)

    record = DataImport(
        owner_id=owner_id,
        kind="land_registry_ppd",
        status="processing",
        filename=filename[:255],
        sha256=digest,
        source_name=SOURCE_NAME,
        source_url=SOURCE_URL,
        licence=LICENCE,
        attribution=ATTRIBUTION,
    )
    db.add(record)
    db.flush()

    total = imported = rejected = 0
    errors: list[dict] = []
    date_min = date_max = None
    try:
        reader = pd.read_csv(
            path,
            header=None,
            names=COLUMNS,
            skiprows=1 if _has_header(path) else 0,
            dtype=str,
            keep_default_na=False,
            chunksize=CHUNK_SIZE,
            nrows=max_rows,
            on_bad_lines="skip",
            encoding="utf-8",
            encoding_errors="replace",
        )
        for chunk in reader:
            if list(chunk.columns) != COLUMNS:
                raise ValueError("unexpected column layout; expected 16 PPD columns")
            good, chunk_errors = validate_chunk(chunk, total + 1)
            total += len(chunk)
            rejected += len(chunk_errors)
            room = MAX_STORED_ERRORS - len(errors)
            if room > 0:
                errors.extend(chunk_errors[:room])

            deletes = good[good["record_status"] == "D"]["transaction_id"].tolist()
            if deletes:
                db.execute(delete(PricePaidTransaction).where(PricePaidTransaction.transaction_id.in_(deletes)))
            upserts = good[good["record_status"] != "D"]
            if not upserts.empty:
                cmin, cmax = upserts["date_of_transfer"].min(), upserts["date_of_transfer"].max()
                date_min = cmin if date_min is None else min(date_min, cmin)
                date_max = cmax if date_max is None else max(date_max, cmax)
            rows = [
                {
                    "transaction_id": r.transaction_id,
                    "price": int(r.price),
                    "date_of_transfer": r.date_of_transfer,
                    "postcode": r.postcode,
                    "postcode_district": r.postcode_district,
                    "postcode_sector": r.postcode_sector,
                    "property_type": r.property_type,
                    "new_build": r.new_build == "Y",
                    "tenure": r.duration,
                    "paon": r.paon[:120],
                    "saon": r.saon[:120],
                    "street": r.street[:120],
                    "locality": r.locality[:120],
                    "town": r.town_city[:120],
                    "local_authority": r.district[:120],
                    "county": r.county[:120],
                    "ppd_category": r.ppd_category_type,
                    "import_id": record.id,
                }
                for r in upserts.itertuples(index=False)
            ]
            _upsert(db, rows)
            imported += len(good)
        record.status = "completed_with_errors" if rejected else "completed"
        if total == 0:
            record.status = "failed"
            errors = [{"row": 0, "error": "the file contained no data rows"}]
    except (ValueError, pd.errors.ParserError, UnicodeDecodeError) as e:
        db.rollback()
        db.add(record)
        record.status = "failed"
        errors = [{"row": 0, "error": f"could not parse file: {e}"[:500]}]
        imported = 0

    record.rows_total = total
    record.rows_imported = imported
    record.rows_rejected = rejected
    record.errors = errors
    record.data_from = date_min
    record.data_to = date_max
    record.completed_at = datetime.now(UTC)
    db.commit()
    db.refresh(record)
    return record


def coverage(db: Session) -> dict[str, Any]:
    count, dmin, dmax = db.execute(
        select(
            func.count(PricePaidTransaction.id),
            func.min(PricePaidTransaction.date_of_transfer),
            func.max(PricePaidTransaction.date_of_transfer),
        )
    ).one()
    last = db.scalar(
        select(DataImport)
        .where(DataImport.kind == "land_registry_ppd", DataImport.status != "failed")
        .order_by(DataImport.created_at.desc())
    )
    return {
        "transactions": int(count or 0),
        "earliest_transaction": dmin,
        "latest_transaction": dmax,
        "last_imported_at": last.completed_at if last else None,
        "source_name": SOURCE_NAME,
        "source_url": SOURCE_URL,
        "licence": LICENCE,
        "attribution": ATTRIBUTION,
        "days_since_latest_transaction": (datetime.now(UTC).date() - dmax).days if dmax else None,
    }
