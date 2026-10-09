"""PDF and CSV report generation."""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

INK = colors.HexColor("#14213D")
MUTED = colors.HexColor("#5C6378")
RULE = colors.HexColor("#D8DCE5")
ACCENT = colors.HexColor("#1F6F5C")
WARN = colors.HexColor("#9A3B1E")

LIMITATIONS = [
    "This report is an analytical aid, not financial, tax, legal or mortgage advice.",
    "Rent, operating costs, growth and exit assumptions are user estimates and are not verified.",
    "Transaction tax and income tax figures are simplified estimates based on rules as reviewed on the "
    "stated date; reliefs, exemptions and personal circumstances are not fully modelled.",
    "Projected returns depend heavily on capital growth and interest rate assumptions, which are "
    "uncertain. Past sale prices do not predict future values.",
    "Comparable sales (where shown) are HM Land Registry recorded prices and do not account for size, "
    "condition or exact location.",
]


def _fmt(value: Any, unit: str) -> str:
    if value is None:
        return "n/a"
    if unit in ("gbp", "gbp_month"):
        s = f"£{abs(value):,.0f}" if abs(value) >= 100 else f"£{abs(value):,.2f}"
        s = ("-" if value < 0 else "") + s
        return s + (" /mo" if unit == "gbp_month" else "")
    if unit == "percent":
        return f"{value:.2f}%"
    if unit == "multiple":
        return f"{value:.2f}x"
    return str(value)


def _styles():
    ss = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "t",
            parent=ss["Title"],
            fontName="Helvetica-Bold",
            fontSize=20,
            textColor=INK,
            alignment=TA_LEFT,
            spaceAfter=4,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=ss["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12.5,
            textColor=INK,
            spaceBefore=12,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "b", parent=ss["BodyText"], fontName="Helvetica", fontSize=9, leading=12.5, textColor=INK
        ),
        "small": ParagraphStyle(
            "s", parent=ss["BodyText"], fontName="Helvetica", fontSize=7.5, leading=10, textColor=MUTED
        ),
        "warn": ParagraphStyle(
            "w", parent=ss["BodyText"], fontName="Helvetica", fontSize=8.5, leading=11.5, textColor=WARN
        ),
        "cell": ParagraphStyle("c", fontName="Helvetica", fontSize=7.5, leading=9.5, textColor=INK),
        "cellmuted": ParagraphStyle("cm", fontName="Helvetica", fontSize=7, leading=9, textColor=MUTED),
    }


def _table(data, widths, header=True, zebra=True):
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    style = [
        ("FONT", (0, 0), (-1, -1), "Helvetica", 8),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK) if header else ("LINEBELOW", (0, 0), (-1, 0), 0, RULE),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, RULE),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if header:
        style.append(("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8))
    t.setStyle(TableStyle(style))
    return t


def analysis_pdf(
    *,
    title: str,
    results: dict[str, Any],
    property_info: dict[str, Any] | None,
    explanation: dict[str, Any] | None,
    comparables: dict[str, Any] | None,
    generated_by: str,
) -> bytes:
    st = _styles()
    buf = io.BytesIO()
    generated = datetime.now(UTC)

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(
            18 * mm,
            10 * mm,
            f"Prophecy AI · generated {generated:%d %b %Y %H:%M} UTC · "
            f"engine v{results.get('engine_version')} · not financial advice",
        )
        canvas.drawRightString(192 * mm, 10 * mm, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=18 * mm,
        title=title,
        author="Prophecy AI",
    )
    story: list = [Paragraph(title, st["title"])]
    story.append(
        Paragraph(
            f"Property investment analysis · generated {generated:%d %B %Y %H:%M} UTC for {generated_by}", st["small"]
        )
    )
    story.append(Spacer(1, 6))

    # Provenance
    prov = [["Item", "Source"]]
    if property_info:
        prov += [
            ["Property record", property_info.get("data_source", "manual").replace("_", " ")],
            ["Rent figure", property_info.get("rent_source", "user_estimate").replace("_", " ")],
        ]
        if property_info.get("is_demo"):
            story.append(
                Paragraph(
                    "<b>DEMONSTRATION DATA.</b> The price and rent for this property are illustrative figures, "
                    "not a real listing or market evidence.",
                    st["warn"],
                )
            )
            story.append(Spacer(1, 4))
    tt = results["transaction_tax"]
    prov += [
        ["Financial assumptions", "User-supplied (see inputs)"],
        [
            tt["name"],
            f"Estimated from rules reviewed {tt['rules_reviewed_on']}"
            if not tt["overridden"]
            else "User-supplied figure",
        ],
        ["Tax scenario", f"Simplified rules reviewed {results.get('tax_rules_reviewed_on')}"],
    ]
    if comparables and comparables.get("available"):
        prov.append(["Comparable sales", "HM Land Registry Price Paid Data (OGL v3.0)"])
    if explanation:
        prov.append(["Narrative explanation", f"{explanation['provider']} ({explanation['model']})"])
    story.append(Paragraph("Data provenance", st["h2"]))
    story.append(_table(prov, [55 * mm, 119 * mm]))

    # Property
    if property_info:
        story.append(Paragraph("Property", st["h2"]))
        rows = [["Field", "Value"]] + [
            [k.replace("_", " ").capitalize(), str(v)]
            for k, v in property_info.items()
            if v not in (None, "") and k not in ("data_source", "rent_source", "is_demo")
        ]
        story.append(_table(rows, [55 * mm, 119 * mm]))

    # Key metrics
    story.append(Paragraph("Key figures (year one unless stated)", st["h2"]))
    rows = [["Metric", "Value", "Basis", "Formula"]]
    for m in results["metrics"]:
        rows.append(
            [
                Paragraph(m["label"], st["cell"]),
                _fmt(m["value"], m["unit"]),
                m["basis"],
                Paragraph(m["formula"], st["cellmuted"]),
            ]
        )
    story.append(_table(rows, [52 * mm, 26 * mm, 18 * mm, 78 * mm]))

    if results.get("warnings"):
        story.append(Paragraph("Warnings", st["h2"]))
        for w in results["warnings"]:
            story.append(Paragraph(f"• {w}", st["warn"]))

    # Transaction tax
    story.append(Paragraph(f"{tt['name']} breakdown", st["h2"]))
    rows = [["Band", "Rate", "Taxable", "Tax"]]
    for b in tt["bands"]:
        upper = f"£{b['upper']:,.0f}" if b["upper"] else "and above"
        rows.append(
            [
                f"£{b['lower']:,.0f} – {upper}",
                f"{b['rate_pct']:g}%",
                f"£{b['taxable_amount']:,.0f}",
                f"£{b['tax']:,.0f}",
            ]
        )
    rows.append(["Total", f"{tt['effective_rate_pct']:.2f}% effective", "", f"£{tt['total']:,.0f}"])
    story.append(_table(rows, [64 * mm, 36 * mm, 37 * mm, 37 * mm]))
    for a in tt["assumptions"]:
        story.append(Paragraph(f"• {a}", st["small"]))
    story.append(Paragraph(f"Source: {tt['source_url']}", st["small"]))

    # Break-even and sensitivity
    if results.get("break_even"):
        story.append(Paragraph("What would need to change", st["h2"]))
        rows = [["Threshold", "Value", "Current"]]
        for b in results["break_even"]:
            rows.append([Paragraph(b["label"], st["cell"]), _fmt(b["value"], b["unit"]), _fmt(b["current"], b["unit"])])
        story.append(_table(rows, [94 * mm, 40 * mm, 40 * mm]))
    if results.get("sensitivity"):
        story.append(Paragraph("Sensitivity (monthly pre-tax cash flow / IRR)", st["h2"]))
        rows = [["Driver", "Downside", "Upside", "Swing"]]
        for r in results["sensitivity"]["rows"]:
            rows.append(
                [
                    Paragraph(
                        f"{r['driver']}<br/><font size=6.5 color='#5C6378'>{r['description']}</font>", st["cell"]
                    ),
                    f"{_fmt(r['low']['monthly_cash_flow'], 'gbp')} / {_fmt(r['low']['irr_pct'], 'percent')}",
                    f"{_fmt(r['high']['monthly_cash_flow'], 'gbp')} / {_fmt(r['high']['irr_pct'], 'percent')}",
                    _fmt(r["cash_flow_swing"], "gbp"),
                ]
            )
        story.append(_table(rows, [62 * mm, 42 * mm, 42 * mm, 28 * mm]))
    if results.get("scenarios"):
        story.append(Paragraph("Scenarios", st["h2"]))
        rows = [["Scenario", "Monthly CF", "Net yield", "Cash-on-cash", "IRR", "Total profit"]]
        for s in results["scenarios"]:
            rows.append(
                [
                    s["name"],
                    _fmt(s["monthly_cash_flow"], "gbp"),
                    _fmt(s["net_yield_pct"], "percent"),
                    _fmt(s["cash_on_cash_pct"], "percent"),
                    _fmt(s["irr_pct"], "percent"),
                    _fmt(s["total_profit"], "gbp"),
                ]
            )
        story.append(_table(rows, [30 * mm, 28 * mm, 28 * mm, 30 * mm, 24 * mm, 34 * mm]))

    # Projection and sale
    story.append(PageBreak())
    story.append(Paragraph(f"{len(results['projection'])}-year projection", st["h2"]))
    rows = [["Yr", "Rent", "Op. costs", "Mortgage", "Pre-tax CF", "Tax", "After-tax CF", "Value", "Loan"]]
    for p in results["projection"]:
        rows.append(
            [p["year"]]
            + [
                f"{p[k]:,.0f}"
                for k in (
                    "collected_rent",
                    "operating_expenses",
                    "debt_service",
                    "pre_tax_cash_flow",
                    "tax",
                    "after_tax_cash_flow",
                    "property_value",
                    "loan_balance",
                )
            ]
        )
    story.append(_table(rows, [9 * mm] + [20.6 * mm] * 8))
    s = results["sale"]
    story.append(Paragraph("Exit", st["h2"]))
    rows = [
        ["Item", "Amount"],
        ["Sale price", _fmt(s["sale_price"], "gbp")],
        ["Selling costs", _fmt(-s["selling_costs"], "gbp")],
        ["Loan repaid", _fmt(-s["loan_repayment"], "gbp")],
        ["Capital gain (before tax)", _fmt(s["gain"], "gbp")],
        ["Capital gains tax (estimate)", _fmt(-s["capital_gains_tax"], "gbp")],
        ["Net sale proceeds", _fmt(s["net_sale_proceeds"], "gbp")],
    ]
    story.append(_table(rows, [94 * mm, 80 * mm]))
    story.append(Paragraph(s["cgt_formula"], st["small"]))

    if comparables and comparables.get("available"):
        cs = comparables["stats"]
        story.append(Paragraph("Comparable sales (HM Land Registry)", st["h2"]))
        story.append(
            Paragraph(
                f"{cs['count']} recorded sales in postcode {comparables['level']} {comparables['area']} "
                f"between {comparables['period']['from']} and {comparables['period']['to']}: median "
                f"£{cs['median']:,.0f}, interquartile range £{cs['p25']:,.0f} – £{cs['p75']:,.0f}.",
                st["body"],
            )
        )
        rows = [["Date", "Price", "Address", "Type"]]
        for c in comparables["sales"][:10]:
            rows.append(
                [
                    str(c["date"]),
                    f"£{c['price']:,.0f}",
                    Paragraph(f"{c['address']}, {c['postcode']}", st["cell"]),
                    c["property_type"],
                ]
            )
        story.append(_table(rows, [24 * mm, 26 * mm, 94 * mm, 30 * mm]))
        story.append(
            Paragraph(
                "Contains HM Land Registry data © Crown copyright and database right. Licensed under the Open "
                "Government Licence v3.0.",
                st["small"],
            )
        )

    if explanation:
        c = explanation["content"]
        block = [
            Paragraph("Narrative explanation", st["h2"]),
            Paragraph(
                f"Generated by {explanation['provider']} ({explanation['model']}). "
                "Grounded in the figures above; verify before relying on it.",
                st["small"],
            ),
            Spacer(1, 3),
            Paragraph(c["summary"], st["body"]),
        ]
        for heading, items in (
            ("Strengths", c["strengths"]),
            ("Weaknesses", c["weaknesses"]),
            ("Improvements", c["improvements"]),
        ):
            block.append(Paragraph(f"<b>{heading}</b>", st["body"]))
            block += [Paragraph(f"• {i}", st["body"]) for i in items]
        block.append(Paragraph("<b>Risks</b>", st["body"]))
        block += [Paragraph(f"• <b>{r['title']}</b> ({r['severity']}): {r['detail']}", st["body"]) for r in c["risks"]]
        if explanation.get("unverified_figures"):
            block.append(
                Paragraph(
                    "Figures not matched to calculated values: " + ", ".join(explanation["unverified_figures"]),
                    st["warn"],
                )
            )
        story.append(KeepTogether(block[:4]))
        story += block[4:]

    story.append(Paragraph("Inputs", st["h2"]))
    inp = results["inputs"]
    rows = [["Input", "Value"]] + [[k.replace("_", " "), str(v)] for k, v in inp.items()]
    story.append(_table(rows, [94 * mm, 80 * mm]))
    story.append(Paragraph("Assumptions", st["h2"]))
    for a in results["assumptions"]:
        story.append(Paragraph(f"• {a}", st["body"]))
    story.append(Paragraph("Limitations", st["h2"]))
    for line in LIMITATIONS:
        story.append(Paragraph(f"• {line}", st["body"]))

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()


def analysis_csv(title: str, results: dict[str, Any], property_info: dict[str, Any] | None) -> bytes:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["report", title])
    w.writerow(["generated_utc", datetime.now(UTC).isoformat(timespec="seconds")])
    w.writerow(["engine_version", results.get("engine_version")])
    if property_info:
        w.writerow(["property_data_source", property_info.get("data_source")])
        w.writerow(["rent_source", property_info.get("rent_source")])
        w.writerow(["demonstration_data", property_info.get("is_demo")])
    w.writerow(["disclaimer", "Estimates based on user assumptions; not financial or tax advice."])
    w.writerow([])
    w.writerow(["section", "key", "label", "value", "unit", "basis", "formula"])
    for m in results["metrics"]:
        w.writerow(["metric", m["key"], m["label"], m["value"], m["unit"], m["basis"], m["formula"]])
    w.writerow([])
    w.writerow(["section", "input", "value"])
    for k, v in results["inputs"].items():
        w.writerow(["input", k, v])
    w.writerow([])
    cols = list(results["projection"][0].keys()) if results["projection"] else []
    w.writerow(["section"] + cols)
    for p in results["projection"]:
        w.writerow(["projection"] + [p[c] for c in cols])
    w.writerow([])
    w.writerow(["section", "assumption"])
    for a in results["assumptions"]:
        w.writerow(["assumption", a])
    for a in results["warnings"]:
        w.writerow(["warning", a])
    return out.getvalue().encode("utf-8-sig")


def comparison_csv(name: str, rows: list[dict[str, Any]], assumptions: dict[str, Any]) -> bytes:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["comparison", name])
    w.writerow(["generated_utc", datetime.now(UTC).isoformat(timespec="seconds")])
    w.writerow(["shared_assumptions", "; ".join(f"{k}={v}" for k, v in assumptions.items()) or "profile defaults"])
    w.writerow(["disclaimer", "Estimates based on user assumptions; not financial or tax advice."])
    w.writerow([])
    if rows:
        keys = [k for k in rows[0] if k != "property_id"]
        w.writerow(keys)
        for r in rows:
            w.writerow([r[k] for k in keys])
    return out.getvalue().encode("utf-8-sig")
