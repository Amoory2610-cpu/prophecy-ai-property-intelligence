"""Provider-independent contract for AI investment explanations."""

from __future__ import annotations

import re
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field


class Risk(BaseModel):
    title: str
    detail: str
    severity: Literal["low", "medium", "high"]


class ExplanationContent(BaseModel):
    summary: str = Field(description="Two to four sentence overview of the deal's investment case.")
    strengths: list[str]
    weaknesses: list[str]
    risks: list[Risk]
    yield_and_cash_flow: str = Field(description="What the yields and cash flow mean for the investor.")
    sensitivity: str = Field(description="How interest rates, rent, vacancy and price changes affect the outcome.")
    improvements: list[str] = Field(
        description="Specific changes that would make the deal more attractive, using the break-even figures."
    )
    caveats: list[str]


class ExplanationResult(BaseModel):
    provider: str
    model: str
    content: ExplanationContent
    unverified_figures: list[str] = []
    notice: str | None = None


class ExplanationProvider(Protocol):
    name: str
    model: str

    def generate(self, context: dict[str, Any]) -> ExplanationContent: ...


SYSTEM_PROMPT = """You are an analyst inside a UK buy-to-let analysis tool. You explain one \
property deal to an investor using ONLY the JSON data supplied in the user message.

Rules:
- Every figure you mention must come from the supplied data, or be simple arithmetic on it \
(e.g. a difference between two supplied values). Quote figures in the same units.
- Do not invent property facts, comparable sales, local market statistics, forecasts or \
news. If the data does not cover something (for example local demand), say it is not covered.
- Treat assumptions (rent, growth, costs) as the user's estimates, not facts. Say so where it matters.
- Tax figures are simplified estimates. Never present them as personal tax advice.
- If the property is marked as demonstration data, mention that the figures are illustrative.
- Be balanced: describe trade-offs rather than declaring the deal good or bad.
- Use British English and £. Keep each list item to one or two sentences."""


_NUM_RE = re.compile(r"(£\s?-?[\d,]+(?:\.\d+)?k?|-?[\d,]+(?:\.\d+)?\s?%)")


_PCT_HINTS = ("pct", "yield", "irr", "rate", "ltv", "icr", "cash_on_cash", "vacancy")


def _collect_numbers(obj: Any, pct: list[float], money: list[float], key: str = "") -> None:
    """Split supplied numbers into percentage-like and money-like values using units/keys."""
    if isinstance(obj, bool):
        return
    if isinstance(obj, int | float):
        target = pct if any(h in key.lower() for h in _PCT_HINTS) else money
        target.append(abs(float(obj)))
    elif isinstance(obj, dict):
        unit = obj.get("unit")
        if unit in ("percent", "multiple") and "value" in obj:
            if isinstance(obj["value"], int | float):
                pct.append(abs(float(obj["value"])))
            rest = {k: v for k, v in obj.items() if k != "value"}
        elif unit in ("gbp", "gbp_month") and "value" in obj:
            if isinstance(obj["value"], int | float):
                money.append(abs(float(obj["value"])))
            rest = {k: v for k, v in obj.items() if k != "value"}
        else:
            rest = obj
        for k, v in rest.items():
            _collect_numbers(v, pct, money, k if not isinstance(v, dict | list) else k)
    elif isinstance(obj, list | tuple):
        for v in obj:
            _collect_numbers(v, pct, money, key)


def _parse(token: str) -> float | None:
    t = token.replace("£", "").replace(",", "").replace("%", "").strip()
    mult = 1.0
    if t.lower().endswith("k"):
        mult, t = 1000.0, t[:-1]
    try:
        return abs(float(t) * mult)
    except ValueError:
        return None


def find_unverified_figures(content: ExplanationContent, context: dict[str, Any]) -> list[str]:
    """Return £ and % figures in the text that do not match any supplied number.

    Percentages are matched against supplied percentage values (and percentage-point
    differences between them); £ amounts against supplied money values, their monthly or
    annual restatements, and sums or differences of two supplied amounts. This is a heuristic guard that surfaces likely
    hallucinated numbers to the user; it does not prove correctness.
    """
    pct_vals: list[float] = []
    money_vals: list[float] = []
    _collect_numbers(context, pct_vals, money_vals)
    pct_known = sorted(set(round(v, 4) for v in pct_vals))
    money_known = sorted(set(round(v, 2) for v in money_vals if v >= 1))
    # Percentages: supplied values and percentage-point differences between them.
    pct_pool = set(pct_known)
    for i, a in enumerate(pct_known):
        for b in pct_known[i + 1 :]:
            pct_pool.add(round(abs(a - b), 4))
    # Money: supplied values, monthly/annual restatements, and sums/differences of pairs.
    money_pool = set(money_known)
    for v in money_known:
        money_pool.update((round(v * 12, 2), round(v / 12, 2)))
    for i, a in enumerate(money_known):
        for b in money_known[i + 1 :]:
            money_pool.update((round(abs(a - b), 2), round(a + b, 2)))

    def matches(x: float, is_pct: bool) -> bool:
        if is_pct:
            tol = max(0.06, x * 0.01)
            return any(abs(x - k) <= tol for k in pct_pool)
        tol = max(1.0, x * 0.015)
        return any(abs(x - k) <= tol for k in money_pool)

    text = " ".join(
        [content.summary, content.yield_and_cash_flow, content.sensitivity]
        + content.strengths
        + content.weaknesses
        + content.improvements
        + content.caveats
        + [f"{r.title} {r.detail}" for r in content.risks]
    )
    bad: list[str] = []
    for token in _NUM_RE.findall(text):
        value = _parse(token)
        if value is None or value == 0:
            continue
        if not matches(value, token.strip().endswith("%")) and token not in bad:
            bad.append(token.strip())
    return bad
