"""Concrete explanation providers."""

from __future__ import annotations

import json
from typing import Any

import anthropic
import httpx

from .base import SYSTEM_PROMPT, ExplanationContent, Risk


class ProviderError(RuntimeError):
    pass


def _user_message(context: dict[str, Any]) -> str:
    return (
        "Explain this deal using only the data below.\n\n<deal_data>\n"
        + json.dumps(context, indent=1, sort_keys=True, default=str)
        + "\n</deal_data>"
    )


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str, model: str, timeout: float):
        self.model = model
        self._client = anthropic.Anthropic(api_key=api_key, timeout=timeout, max_retries=2)

    def generate(self, context: dict[str, Any]) -> ExplanationContent:
        try:
            response = self._client.messages.parse(
                model=self.model,
                max_tokens=16000,
                system=SYSTEM_PROMPT,
                output_config={"effort": "medium"},
                messages=[{"role": "user", "content": _user_message(context)}],
                output_format=ExplanationContent,
            )
        except anthropic.AuthenticationError as e:
            raise ProviderError("Anthropic API key was rejected") from e
        except anthropic.RateLimitError as e:
            raise ProviderError("Anthropic rate limit reached; try again shortly") from e
        except anthropic.APIStatusError as e:
            raise ProviderError(f"Anthropic API error ({e.status_code})") from e
        except anthropic.APIConnectionError as e:
            raise ProviderError("Could not reach the Anthropic API") from e
        if response.stop_reason == "refusal":
            raise ProviderError("The model declined to produce an explanation")
        if response.stop_reason == "max_tokens" or response.parsed_output is None:
            raise ProviderError("The model response was incomplete")
        return response.parsed_output


class OpenAICompatibleProvider:
    """Any endpoint implementing the OpenAI Chat Completions API with JSON-schema output."""

    name = "openai"

    def __init__(self, api_key: str, base_url: str, model: str, timeout: float):
        self.model = model
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._timeout = timeout

    def generate(self, context: dict[str, Any]) -> ExplanationContent:
        schema = ExplanationContent.model_json_schema()
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _user_message(context)},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "explanation", "schema": schema},
            },
        }
        try:
            r = httpx.post(self._url, json=body, headers=self._headers, timeout=self._timeout)
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"]
            return ExplanationContent.model_validate_json(text)
        except httpx.HTTPStatusError as e:
            raise ProviderError(f"AI provider error ({e.response.status_code})") from e
        except (httpx.HTTPError, KeyError, ValueError) as e:
            raise ProviderError("AI provider returned an unusable response") from e


def _gbp(x: float | None) -> str:
    return "n/a" if x is None else f"£{x:,.0f}"


def _pct(x: float | None, places: int = 1) -> str:
    return "n/a" if x is None else f"{x:.{places}f}%"


class RuleBasedProvider:
    """Deterministic explanation built from thresholds on the calculated figures.

    Used when no AI provider is configured or when the configured provider fails, so
    explanations are always available and fully reproducible.
    """

    name = "rule_based"
    model = "prophecy-rules-v1"

    def generate(self, context: dict[str, Any]) -> ExplanationContent:
        m = {k: v["value"] for k, v in context["metrics"].items()}
        inputs = context["inputs"]
        be = {b["key"]: b for b in context.get("break_even", [])}
        sens = context.get("sensitivity", [])
        gross, net = m.get("gross_yield"), m.get("net_yield")
        cf, coc, icr, irr = (
            m.get("monthly_cash_flow"),
            m.get("cash_on_cash"),
            m.get("icr"),
            m.get("irr"),
        )
        cf_tax = m.get("monthly_cash_flow_after_tax")
        ltv = m.get("ltv") or 0
        strengths: list[str] = []
        weaknesses: list[str] = []
        risks: list[Risk] = []

        if gross is not None:
            if gross >= 7:
                strengths.append(f"A gross yield of {_pct(gross)} is high for UK residential property.")
            elif gross >= 5:
                strengths.append(f"A gross yield of {_pct(gross)} is moderate.")
            else:
                weaknesses.append(f"A gross yield of {_pct(gross)} is low; rent covers a small share of the price.")
        if cf is not None:
            if cf > 0:
                strengths.append(f"Positive pre-tax cash flow of {_gbp(cf)} a month after mortgage payments.")
            else:
                weaknesses.append(
                    f"Cash flow is {_gbp(cf)} a month before tax, so the investor must top up the property."
                )
        if cf_tax is not None and cf is not None and cf > 0 and cf_tax <= 0:
            weaknesses.append(
                f"After the estimated tax the monthly cash flow falls to {_gbp(cf_tax)}, which erodes "
                "the income return."
            )
        if icr is not None:
            req = inputs.get("required_icr_pct", 125)
            if icr < req:
                risks.append(
                    Risk(
                        title="Lender stress test",
                        detail=f"Interest cover of {_pct(icr, 0)} is below the {req:g}% benchmark, so "
                        f"lenders may cap the loan at about {_gbp(m.get('max_loan_by_icr'))}.",
                        severity="high",
                    )
                )
            else:
                strengths.append(f"Interest cover of {_pct(icr, 0)} passes a {req:g}% stress test.")

        rate_be = be.get("break_even_rate")
        if rate_be and rate_be["value"] is not None:
            buffer = rate_be["value"] - inputs["interest_rate_pct"]
            sev = "high" if buffer < 1 else "medium" if buffer < 2 else "low"
            risks.append(
                Risk(
                    title="Interest-rate risk",
                    detail=f"Cash flow turns negative above a {_pct(rate_be['value'], 2)} mortgage rate, "
                    f"{buffer:.2f} percentage points above the assumed {_pct(inputs['interest_rate_pct'], 2)}.",
                    severity=sev,
                )
            )
        vac_be = be.get("break_even_vacancy")
        if vac_be and vac_be["value"] is not None:
            sev = "high" if vac_be["value"] < 8 else "medium" if vac_be["value"] < 15 else "low"
            risks.append(
                Risk(
                    title="Void periods",
                    detail=f"The deal can absorb voids of up to {_pct(vac_be['value'])} of the year before "
                    f"cash flow turns negative (assumed {_pct(inputs['vacancy_pct'])}).",
                    severity=sev,
                )
            )
        if ltv > 75:
            risks.append(
                Risk(
                    title="High leverage",
                    detail=f"A loan-to-value of {_pct(ltv, 0)} magnifies losses if prices fall.",
                    severity="medium",
                )
            )
        if inputs.get("mortgage_type") == "interest_only" and ltv > 0:
            risks.append(
                Risk(
                    title="Interest-only repayment",
                    detail="The loan balance is not reduced, so the exit relies on selling or refinancing.",
                    severity="medium",
                )
            )
        if irr is not None and inputs.get("capital_growth_pct", 0) > 0:
            risks.append(
                Risk(
                    title="Dependence on capital growth",
                    detail=f"The {_pct(irr)} annualised return assumes {inputs['capital_growth_pct']:g}% "
                    "annual price growth, which is an assumption rather than a forecast.",
                    severity="medium",
                )
            )

        improvements: list[str] = []
        rent_be = be.get("break_even_rent")
        if cf is not None and cf < 0 and rent_be and rent_be["value"] is not None:
            improvements.append(
                f"Rent would need to reach about {_gbp(rent_be['value'])} a month to break even "
                f"(currently {_gbp(inputs['monthly_rent'])})."
            )
        price_be = be.get("max_price_break_even")
        if cf is not None and cf < 0 and price_be and price_be["value"]:
            improvements.append(
                f"At the current rent, a purchase price of about {_gbp(price_be['value'])} would break even."
            )
        target = be.get("price_for_target_yield")
        if target and target["value"] and target["value"] < inputs["purchase_price"]:
            improvements.append(
                f"{target['label']}: about {_gbp(target['value'])} versus {_gbp(inputs['purchase_price'])}."
            )
        if rate_be and rate_be["value"] is not None and cf is not None and cf < 0:
            improvements.append(
                f"A mortgage rate at or below {_pct(rate_be['value'], 2)} would remove the monthly shortfall."
            )
        if not improvements:
            improvements.append(
                "The deal already breaks even on the current assumptions; the main lever is "
                "negotiating price to widen the safety margin."
            )

        if sens:
            top = sens[0]
            sensitivity_text = (
                f"{top['driver']} has the largest effect on monthly cash flow: "
                f"{top['description'].lower()} moves it between {_gbp(top['low']['monthly_cash_flow'])} and "
                f"{_gbp(top['high']['monthly_cash_flow'])}. "
            )
            growth = next((s for s in sens if s["driver"] == "Capital growth"), None)
            if growth and growth["low"]["irr_pct"] is not None and growth["high"]["irr_pct"] is not None:
                sensitivity_text += (
                    f"Capital growth does not change year-one cash flow but moves the annualised return "
                    f"between {_pct(growth['low']['irr_pct'])} and {_pct(growth['high']['irr_pct'])}."
                )
        else:
            sensitivity_text = "Sensitivity analysis was not available."

        prop = context.get("property", {})
        summary = (
            f"At {_gbp(inputs['purchase_price'])} with rent of {_gbp(inputs['monthly_rent'])} a month, "
            f"this deal shows a {_pct(gross)} gross and {_pct(net)} net yield, "
            f"{_gbp(cf)} monthly pre-tax cash flow and an estimated {_pct(irr)} annualised return over "
            f"{inputs['holding_years']} years."
        )
        if prop.get("is_demo"):
            summary += " This is demonstration data, so the figures are illustrative only."

        caveats = [
            "Generated by deterministic rules from the calculated figures; no AI model was used.",
            "Rent, costs and growth rates are the user's assumptions, not verified market data.",
            "Tax figures are simplified estimates and not personal tax advice.",
        ]
        if context.get("comparables"):
            caveats.append("Comparable sales come from HM Land Registry records and do not reflect condition or size.")
        return ExplanationContent(
            summary=summary,
            strengths=strengths or ["No standout strengths on the current assumptions."],
            weaknesses=weaknesses or ["No major weaknesses on the current assumptions."],
            risks=risks,
            yield_and_cash_flow=(
                f"Gross yield {_pct(gross)}, net yield {_pct(net)} before financing. After mortgage "
                f"payments, cash flow is {_gbp(cf)} a month before tax and {_gbp(cf_tax)} after the "
                f"estimated tax, a pre-tax cash-on-cash return of {_pct(coc)} on "
                f"{_gbp(m.get('initial_cash_required'))} invested."
            ),
            sensitivity=sensitivity_text,
            improvements=improvements,
            caveats=caveats,
        )
