"""Market analytics over imported HM Land Registry Price Paid Data.

Nothing here fabricates data: every statistic is computed from transactions stored in
``price_paid_transactions`` and is returned with its sample size and date range. When
there is not enough data the functions say so instead of guessing.
"""

from __future__ import annotations

import threading
from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import PricePaidTransaction as T
from app.services import postcodes

PPD_TYPES = {"D": "Detached", "S": "Semi-detached", "T": "Terraced", "F": "Flat/maisonette", "O": "Other"}
# Our property types mapped to PPD codes. Bungalows are recorded as D/S/T in PPD.
TYPE_TO_PPD = {"detached": "D", "semi_detached": "S", "terraced": "T", "flat": "F", "other": "O"}
MIN_SAMPLE = 5
LOW_SAMPLE = 10


class Area:
    def __init__(self, kind: str, value: str, label: str):
        self.kind, self.value, self.label = kind, value, label

    def condition(self):
        if self.kind == "sector":
            return T.postcode_sector == self.value
        if self.kind == "district":
            return T.postcode_district == self.value
        if self.kind == "local_authority":
            return func.lower(T.local_authority) == self.value.lower()
        return func.lower(T.town) == self.value.lower()

    def as_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "value": self.value, "label": self.label}


def resolve_area(db: Session, query: str) -> Area | None:
    parsed = postcodes.parse_area(query)
    if parsed:
        kind, value = parsed
        return Area(kind, value, f"{value} ({'postcode sector' if kind == 'sector' else 'postcode district'})")
    q = query.strip()
    if not q:
        return None
    la = db.scalar(select(T.local_authority).where(func.lower(T.local_authority) == q.lower()).limit(1))
    if la:
        return Area("local_authority", la, f"{la} (local authority)")
    town = db.scalar(select(T.town).where(func.lower(T.town) == q.lower()).limit(1))
    if town:
        return Area("town", town, f"{town} (town)")
    return None


def search_areas(db: Session, q: str, limit: int = 10) -> list[dict[str, Any]]:
    q = q.strip()
    if len(q) < 2:
        return []
    like = f"{q.lower()}%"
    out: list[dict[str, Any]] = []
    for kind, col in (("local_authority", T.local_authority), ("town", T.town)):
        rows = db.execute(
            select(col, func.count())
            .where(func.lower(col).like(like))
            .group_by(col)
            .order_by(func.count().desc())
            .limit(limit)
        ).all()
        out += [{"kind": kind, "value": v, "label": v, "transactions": n} for v, n in rows if v]
    parsed = postcodes.parse_area(q)
    if parsed:
        kind, value = parsed
        col = T.postcode_sector if kind == "sector" else T.postcode_district
        n = db.scalar(select(func.count()).where(col == value)) or 0
        if n:
            out.insert(0, {"kind": kind, "value": value, "label": value, "transactions": n})
    return out[:limit]


def _frame(db: Session, cond, ppd_type: str | None = None, since: date | None = None) -> pd.DataFrame:
    stmt = select(
        T.price,
        T.date_of_transfer,
        T.property_type,
        T.new_build,
        T.tenure,
        T.postcode,
        T.paon,
        T.saon,
        T.street,
        T.town,
    ).where(cond, T.ppd_category == "A")
    if ppd_type:
        stmt = stmt.where(T.property_type == ppd_type)
    if since:
        stmt = stmt.where(T.date_of_transfer >= since)
    rows = db.execute(stmt).all()
    df = pd.DataFrame(
        rows,
        columns=["price", "date", "property_type", "new_build", "tenure", "postcode", "paon", "saon", "street", "town"],
    )
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df


def _stats(prices: pd.Series) -> dict[str, Any]:
    if prices.empty:
        return {"count": 0}
    q = prices.quantile([0.1, 0.25, 0.5, 0.75, 0.9])
    return {
        "count": int(prices.size),
        "median": float(q[0.5]),
        "mean": float(prices.mean()),
        "p10": float(q[0.1]),
        "p25": float(q[0.25]),
        "p75": float(q[0.75]),
        "p90": float(q[0.9]),
        "low_sample": bool(prices.size < LOW_SAMPLE),
    }


def _latest(db: Session, cond) -> date | None:
    return db.scalar(select(func.max(T.date_of_transfer)).where(cond, T.ppd_category == "A"))


def summary(db: Session, area: Area, ppd_type: str | None = None, months: int = 12) -> dict[str, Any]:
    latest = _latest(db, area.condition())
    if latest is None:
        return {"area": area.as_dict(), "available": False, "message": "No transactions for this area."}
    since = latest - timedelta(days=round(months * 30.44))
    df = _frame(db, area.condition(), ppd_type, since)
    by_type = []
    for code, label in PPD_TYPES.items():
        sub = df[df["property_type"] == code]["price"]
        if not sub.empty:
            by_type.append({"property_type": code, "label": label, **_stats(sub)})
    return {
        "area": area.as_dict(),
        "available": not df.empty,
        "property_type": ppd_type,
        "period": {
            "from": df["date"].min().date() if not df.empty else since,
            "to": latest,
            "months": months,
        },
        "overall": _stats(df["price"]),
        "by_property_type": by_type,
        "new_build_share_pct": round(float(df["new_build"].mean() * 100), 1) if not df.empty else None,
        "leasehold_share_pct": round(float((df["tenure"] == "L").mean() * 100), 1) if not df.empty else None,
        "histogram": _histogram(df["price"]),
        "method": "Standard price paid transactions (PPD category A) only; additional price paid "
        "entries such as repossessions and transfers to companies are excluded.",
    }


def _histogram(prices: pd.Series, bins: int = 16) -> list[dict[str, float]]:
    if prices.size < 2:
        return []
    upper = float(prices.quantile(0.98))
    clipped = prices[prices <= upper]
    counts, edges = np.histogram(clipped, bins=bins)
    return [{"from": float(edges[i]), "to": float(edges[i + 1]), "count": int(counts[i])} for i in range(len(counts))]


def trend(db: Session, area: Area, ppd_type: str | None = None) -> dict[str, Any]:
    df = _frame(db, area.condition(), ppd_type)
    if df.empty:
        return {"area": area.as_dict(), "points": []}
    monthly = df.set_index("date")["price"].resample("MS").agg(["median", "count"]).reset_index()
    points = [
        {
            "month": r["date"].strftime("%Y-%m"),
            "median": float(r["median"]) if r["count"] else None,
            "count": int(r["count"]),
            "low_sample": bool(r["count"] < LOW_SAMPLE),
        }
        for _, r in monthly.iterrows()
    ]
    return {
        "area": area.as_dict(),
        "property_type": ppd_type,
        "points": points,
        "note": "Monthly medians of recorded sale prices. Months with fewer than "
        f"{LOW_SAMPLE} sales are flagged as low-sample and are volatile. Changes in the mix of "
        "properties sold affect medians; they are not a house price index.",
    }


def comparables(
    db: Session, postcode: str | None, property_type: str | None, months: int = 24, limit: int = 15
) -> dict[str, Any]:
    pc = postcodes.normalise(postcode)
    if not pc:
        return {"available": False, "message": "A valid postcode is needed to find comparable sales."}
    ppd_type = TYPE_TO_PPD.get(property_type or "")
    levels = [("sector", postcodes.sector(pc)), ("district", postcodes.district(pc))]
    for level, value in levels:
        area = Area(level, value, value)
        latest = _latest(db, area.condition())
        if latest is None:
            continue
        since = latest - timedelta(days=round(months * 30.44))
        df = _frame(db, area.condition(), ppd_type, since)
        if len(df) >= MIN_SAMPLE:
            recent = df.sort_values("date", ascending=False).head(limit)
            return {
                "available": True,
                "level": level,
                "area": value,
                "property_type": ppd_type,
                "period": {"from": df["date"].min().date(), "to": latest},
                "stats": _stats(df["price"]),
                "sales": [
                    {
                        "date": r.date.date(),
                        "price": int(r.price),
                        "address": " ".join(x for x in [r.saon, r.paon, r.street] if x).strip(),
                        "postcode": r.postcode,
                        "property_type": PPD_TYPES.get(r.property_type, r.property_type),
                        "new_build": bool(r.new_build),
                        "tenure": {"F": "Freehold", "L": "Leasehold"}.get(r.tenure, "Unknown"),
                    }
                    for r in recent.itertuples()
                ],
            }
    return {
        "available": False,
        "message": f"Fewer than {MIN_SAMPLE} matching sales found in {pc}'s postcode sector or "
        "district in the imported data.",
    }


def valuation(comps: dict[str, Any], asking_price: float) -> dict[str, Any] | None:
    if not comps.get("available"):
        return None
    s = comps["stats"]
    n = s["count"]
    confidence = "higher" if n >= 30 else "moderate" if n >= LOW_SAMPLE else "low"
    return {
        "estimate": s["median"],
        "range_low": s["p25"],
        "range_high": s["p75"],
        "sample_size": n,
        "confidence": confidence,
        "asking_vs_median_pct": round((asking_price - s["median"]) / s["median"] * 100, 1),
        "method": f"Median of {n} recorded {('same-type ' if comps['property_type'] else '')}sales in "
        f"postcode {comps['level']} {comps['area']} between {comps['period']['from']} and "
        f"{comps['period']['to']}. The range is the interquartile range.",
        "limitations": [
            "Does not adjust for size, condition, floor area, improvements or exact location.",
            "Land Registry records are published with a lag of several weeks to months.",
            "This is a statistical reference point, not a valuation by a RICS surveyor.",
        ],
    }


_eval_cache: dict[tuple, dict[str, Any]] = {}
_eval_lock = threading.Lock()


def evaluate_comparables_model(db: Session, holdout_months: int = 3, train_months: int = 12) -> dict[str, Any]:
    """Time-split backtest of the comparables estimator on the imported data.

    Training window: ``train_months`` before the cutoff; test: sales in the final
    ``holdout_months``. Each test sale is predicted by the median of same-type sales in
    its postcode sector (>= 5 sales), falling back to its district. The baseline uses
    the district median ignoring property type.
    """
    count, latest = db.execute(
        select(func.count(T.id), func.max(T.date_of_transfer)).where(T.ppd_category == "A")
    ).one()
    if not count:
        return {"available": False, "message": "No Land Registry data has been imported."}
    key = (count, latest, holdout_months, train_months)
    with _eval_lock:
        if key in _eval_cache:
            return _eval_cache[key]

    cutoff = latest - timedelta(days=round(holdout_months * 30.44))
    start = cutoff - timedelta(days=round(train_months * 30.44))
    rows = db.execute(
        select(T.price, T.date_of_transfer, T.property_type, T.postcode_sector, T.postcode_district).where(
            T.ppd_category == "A", T.date_of_transfer >= start, T.postcode_sector.is_not(None)
        )
    ).all()
    df = pd.DataFrame(rows, columns=["price", "date", "ptype", "sector", "district"])
    train, test = df[df["date"] < cutoff], df[df["date"] >= cutoff]
    if len(train) < 100 or len(test) < 50:
        return {
            "available": False,
            "message": "Not enough data either side of the cutoff date for a meaningful evaluation.",
        }

    def medians(keys: list[str]) -> pd.DataFrame:
        g = train.groupby(keys)["price"].agg(["median", "count"]).reset_index()
        return g[g["count"] >= MIN_SAMPLE].drop(columns="count")

    t = test.merge(
        medians(["sector", "ptype"]).rename(columns={"median": "sector_pred"}), on=["sector", "ptype"], how="left"
    )
    t = t.merge(
        medians(["district", "ptype"]).rename(columns={"median": "district_pred"}),
        on=["district", "ptype"],
        how="left",
    )
    t = t.merge(medians(["district"]).rename(columns={"median": "baseline_pred"}), on="district", how="left")
    t["pred"] = t["sector_pred"].fillna(t["district_pred"])
    t["level"] = np.where(t["sector_pred"].notna(), "sector", np.where(t["district_pred"].notna(), "district", None))

    def score(pred_col: str) -> dict[str, Any]:
        s = t[t[pred_col].notna()]
        ape = (s[pred_col] - s["price"]).abs() / s["price"]
        return {
            "predicted": int(len(s)),
            "coverage_pct": round(len(s) / len(t) * 100, 1),
            "median_ape_pct": round(float(ape.median() * 100), 1) if len(s) else None,
            "mean_ape_pct": round(float(ape.mean() * 100), 1) if len(s) else None,
            "within_10_pct": round(float((ape <= 0.10).mean() * 100), 1) if len(s) else None,
            "within_20_pct": round(float((ape <= 0.20).mean() * 100), 1) if len(s) else None,
        }

    result = {
        "available": True,
        "method": "Comparable-sales median (postcode sector + property type, falling back to district).",
        "train_period": {"from": train["date"].min(), "to": train["date"].max(), "sales": int(len(train))},
        "test_period": {"from": test["date"].min(), "to": test["date"].max(), "sales": int(len(t))},
        "model": score("pred"),
        "baseline": {"description": "District median ignoring property type", **score("baseline_pred")},
        "by_level": {level: int((t["level"] == level).sum()) for level in ("sector", "district")},
        "interpretation": "APE = absolute percentage error between the estimate and the actual "
        "recorded price. Computed live from the imported data; it measures how well an area "
        "median predicts individual sale prices, which vary with size and condition.",
    }
    with _eval_lock:
        _eval_cache.clear()
        _eval_cache[key] = result
    return result
