import io
import uuid
from datetime import date, timedelta

import pytest

from app.core.config import get_settings
from app.services.ai.base import ExplanationContent, Risk, find_unverified_figures
from app.services.ai.providers import ProviderError
from app.services.ai.service import explain
from tests.conftest import PROPERTY


class TestProperties:
    def test_create_normalises_postcode_and_computes_yield(self, prop):
        assert prop["postcode"] == "LS6 1AA"
        assert prop["gross_yield_pct"] == 6.6
        assert prop["data_source"] == "manual" and prop["is_demo"] is False

    @pytest.mark.parametrize(
        "bad",
        [
            {"postcode": "NOT A POSTCODE"},
            {"asking_price": 0},
            {"asking_price": -5},
            {"estimated_monthly_rent": -1},
            {"title": ""},
            {"property_type": "castle"},
            {"listing_url": "javascript:alert(1)"},
            {"assumption_overrides": {"interest_rate_pct": 99}},
            {"assumption_overrides": {"made_up_field": 1}},
        ],
    )
    def test_validation(self, client, user, bad):
        r = client.post("/api/properties", json={**PROPERTY, **bad})
        assert r.status_code == 422, bad
        assert r.json()["errors"]

    def test_update_and_delete(self, client, prop):
        r = client.patch(f"/api/properties/{prop['id']}", json={"estimated_monthly_rent": 1200})
        assert r.json()["gross_yield_pct"] == 7.2
        assert client.patch(f"/api/properties/{prop['id']}", json={"asking_price": None}).status_code == 422
        assert client.delete(f"/api/properties/{prop['id']}").status_code == 204
        assert client.get(f"/api/properties/{prop['id']}").status_code == 404

    def test_search_filters_and_sort(self, client, user):
        for title, price, rent, town in [("Cheap flat", 100_000, 700, "Hull"), ("Pricey house", 400_000, 1500, "York")]:
            client.post(
                "/api/properties",
                json={**PROPERTY, "title": title, "asking_price": price, "estimated_monthly_rent": rent, "town": town},
            )
        assert client.get("/api/properties?q=hull").json()["total"] == 1
        assert client.get("/api/properties?max_price=150000").json()["total"] == 1
        assert client.get("/api/properties?min_yield=8").json()["items"][0]["title"] == "Cheap flat"
        items = client.get("/api/properties?sort=price_desc").json()["items"]
        assert items[0]["title"] == "Pricey house"
        page = client.get("/api/properties?page_size=1&page=2").json()
        assert page["total"] == 2 and len(page["items"]) == 1

    def test_demo_portfolio_is_labelled_and_idempotent(self, client, user):
        first = client.post("/api/properties/demo").json()
        second = client.post("/api/properties/demo").json()
        assert len(first) == len(second) == 7
        assert all(p["is_demo"] and p["data_source"] == "demo" and p["rent_source"] == "demo" for p in first)
        assert client.get("/api/properties?demo=true").json()["total"] == 7
        assert client.delete("/api/properties/demo").status_code == 204
        assert client.get("/api/properties").json()["total"] == 0


def test_public_preview(client):
    r = client.post("/api/public/preview", json={"purchase_price": 200000, "monthly_rent": 1100})
    assert r.status_code == 200
    keys = [m["key"] for m in r.json()["metrics"]]
    assert keys[0] == "gross_yield" and r.json()["metrics"][0]["value"] == 6.6
    assert client.post("/api/public/preview", json={"purchase_price": 0, "monthly_rent": 1}).status_code == 422


class TestAnalysis:
    def test_calculate_returns_explained_metrics(self, client, user):
        r = client.post("/api/calculate", json={"purchase_price": 200000, "monthly_rent": 1100})
        assert r.status_code == 200
        body = r.json()
        assert {m["key"] for m in body["metrics"]} >= {"gross_yield", "net_yield", "irr", "cash_on_cash"}
        assert body["break_even"] and body["sensitivity"]["rows"] and len(body["scenarios"]) == 3

    def test_calculate_validates(self, client, user):
        r = client.post("/api/calculate", json={"purchase_price": -1, "monthly_rent": 1100})
        assert r.status_code == 422
        assert r.json()["errors"][0]["field"] == "purchase_price"

    def test_scenarios_endpoint_custom_adjustments(self, client, user):
        r = client.post(
            "/api/scenarios",
            json={
                "inputs": {"purchase_price": 200000, "monthly_rent": 1100},
                "pessimistic": {"interest_rate_change_pp": 3},
            },
        )
        names = [s["name"] for s in r.json()["scenarios"]]
        assert names == ["Base", "Optimistic", "Pessimistic"]
        pess = r.json()["scenarios"][2]
        assert [d["assumption"] for d in pess["drivers"]] == ["Mortgage rate"]

    def test_assumption_profile_flows_into_analysis(self, client, prop):
        r = client.put("/api/assumptions", json={"values": {"interest_rate_pct": 6.5, "deposit_pct": 40}})
        assert r.json()["effective"]["interest_rate_pct"] == 6.5
        assert client.put("/api/assumptions", json={"values": {"vacancy_pct": 500}}).status_code == 422
        a = client.post(f"/api/properties/{prop['id']}/analyses", json={}).json()
        assert a["inputs"]["interest_rate_pct"] == 6.5
        assert a["inputs"]["deposit_pct"] == 40
        # request overrides win over the profile
        b = client.post(f"/api/properties/{prop['id']}/analyses", json={"overrides": {"interest_rate_pct": 4}}).json()
        assert b["inputs"]["interest_rate_pct"] == 4

    def test_saved_analysis_lifecycle(self, client, prop):
        a = client.post(f"/api/properties/{prop['id']}/analyses", json={"name": "Offer at asking"}).json()
        assert a["headline"]["gross_yield"] == 6.6
        assert client.get("/api/analyses").json()[0]["id"] == a["id"]
        assert client.get(f"/api/properties/{prop['id']}/analyses").json()[0]["name"] == "Offer at asking"
        assert client.delete(f"/api/analyses/{a['id']}").status_code == 204
        assert client.get(f"/api/analyses/{a['id']}").status_code == 404

    def test_adhoc_analysis(self, client, user):
        r = client.post(
            "/api/analyses", json={"name": "Quick check", "inputs": {"purchase_price": 150000, "monthly_rent": 900}}
        )
        assert r.status_code == 201 and r.json()["property_id"] is None

    def test_explanation_without_ai_provider_uses_rules(self, client, prop):
        a = client.post(f"/api/properties/{prop['id']}/analyses", json={}).json()
        r = client.post(f"/api/analyses/{a['id']}/explanations")
        assert r.status_code == 201
        e = r.json()
        assert e["provider"] == "rule_based"
        assert e["content"]["notice"].startswith("No AI provider is configured")
        assert e["content"]["summary"] and e["content"]["risks"] and e["content"]["improvements"]
        assert client.get(f"/api/analyses/{a['id']}/explanations").json()[0]["id"] == e["id"]
        assert client.get("/api/ai/status").json()["provider"] == "rule_based"


class TestAIService:
    def _context(self, client):
        from app.services.ai.service import build_context

        results = client.post("/api/calculate", json={"purchase_price": 200000, "monthly_rent": 1100}).json()
        return build_context(
            results, None, {"break_even": results["break_even"], "sensitivity": results["sensitivity"]["rows"]}
        )

    def test_rule_based_explanation_figures_are_all_grounded(self, client, user):
        ctx = self._context(client)
        result = explain(ctx, get_settings())
        assert find_unverified_figures(result.content, ctx) == []

    def test_failing_provider_falls_back(self, client, user):
        class Broken:
            name, model = "broken", "x"

            def generate(self, context):
                raise ProviderError("boom")

        result = explain(self._context(client), get_settings(), provider=Broken())
        assert result.provider == "rule_based"
        assert "unavailable" in result.notice

    def test_invented_figures_are_flagged(self, client, user):
        ctx = self._context(client)

        class Hallucinating:
            name, model = "fake", "fake-1"

            def generate(self, context):
                return ExplanationContent(
                    summary="Gross yield is 6.6% and local prices rose 14.3% last year to £987,654.",
                    strengths=[],
                    weaknesses=[],
                    risks=[Risk(title="x", detail="y", severity="low")],
                    yield_and_cash_flow="",
                    sensitivity="",
                    improvements=[],
                    caveats=[],
                )

        result = explain(ctx, get_settings(), provider=Hallucinating())
        assert result.provider == "fake"
        assert "14.3%" in result.unverified_figures and "£987,654" in result.unverified_figures
        assert "6.6%" not in result.unverified_figures


class TestComparisonsAndWatchlists:
    def _props(self, client, n=3):
        specs = [(200000, 1100), (150000, 950), (320000, 1500)]
        return [
            client.post(
                "/api/properties", json={**PROPERTY, "title": f"P{i}", "asking_price": p, "estimated_monthly_rent": r}
            ).json()
            for i, (p, r) in enumerate(specs[:n])
        ]

    def test_comparison_uses_shared_assumptions_and_reports_tradeoffs(self, client, user):
        ps = self._props(client)
        c = client.post(
            "/api/comparisons",
            json={
                "name": "Shortlist",
                "property_ids": [p["id"] for p in ps],
                "assumptions": {"interest_rate_pct": 5.5},
            },
        ).json()
        res = client.get(f"/api/comparisons/{c['id']}/results").json()
        assert len(res["rows"]) == 3
        assert res["shared_assumptions"]["interest_rate_pct"] == 5.5
        assert res["leaders"]["gross_yield"]["best_property_id"] == ps[1]["id"]
        assert res["leaders"]["initial_cash_required"]["best_property_id"] == ps[1]["id"]
        assert isinstance(res["tradeoffs"], list) and "No single property is ranked best" in res["note"]
        assert "ltv" not in res["leaders"]  # identical 75% LTV everywhere: no leader

    def test_comparison_validation(self, client, user):
        ps = self._props(client, 2)
        assert client.post("/api/comparisons", json={"name": "x", "property_ids": [ps[0]["id"]]}).status_code == 422
        assert client.post("/api/comparisons", json={"name": "x", "property_ids": [ps[0]["id"]] * 2}).status_code == 422
        r = client.post("/api/comparisons", json={"name": "x", "property_ids": [ps[0]["id"], str(uuid.uuid4())]})
        assert r.status_code == 404

    def test_comparison_update_and_export(self, client, user):
        ps = self._props(client)
        c = client.post("/api/comparisons", json={"name": "A", "property_ids": [ps[0]["id"], ps[1]["id"]]}).json()
        u = client.patch(
            f"/api/comparisons/{c['id']}", json={"property_ids": [ps[2]["id"], ps[0]["id"]], "name": "B"}
        ).json()
        assert u["property_ids"] == [ps[2]["id"], ps[0]["id"]] and u["name"] == "B"
        rep = client.post(f"/api/comparisons/{c['id']}/export").json()
        csv_text = client.get(f"/api/reports/{rep['id']}/download").content.decode("utf-8-sig")
        assert "gross_yield" in csv_text and "P2" in csv_text and "not financial or tax advice" in csv_text

    def test_watchlists(self, client, prop):
        w = client.post("/api/watchlists", json={"name": "Leeds", "description": "North"}).json()
        assert client.post("/api/watchlists", json={"name": "Leeds"}).status_code == 409
        w = client.post(
            f"/api/watchlists/{w['id']}/items", json={"property_id": prop["id"], "note": "viewing Sat"}
        ).json()
        assert w["items"][0]["property"]["title"] == PROPERTY["title"]
        assert client.post(f"/api/watchlists/{w['id']}/items", json={"property_id": prop["id"]}).status_code == 409
        assert client.delete(f"/api/watchlists/{w['id']}/items/{prop['id']}").status_code == 204
        assert client.get(f"/api/watchlists/{w['id']}").json()["items"] == []
        assert client.delete(f"/api/watchlists/{w['id']}").status_code == 204


def _ppd_rows(n_valid: int = 30, start: date = date(2024, 1, 5)) -> list[str]:
    rows = []
    for i in range(n_valid):
        tid = "{" + str(uuid.uuid4()).upper() + "}"
        d = start + timedelta(days=i * 11)
        ptype = "T" if i % 2 else "F"
        rows.append(
            f'"{tid}","{180000 + i * 1500}","{d} 00:00","LS6 1A{chr(65 + i % 26)}","{ptype}","N","F","{i}","",'
            f'"TEST STREET","","LEEDS","LEEDS","WEST YORKSHIRE","A","A"'
        )
    return rows


class TestImports:
    def test_properties_csv_valid_and_invalid_rows(self, client, user):
        csv_body = (
            "title,asking_price,estimated_monthly_rent,postcode,property_type,region\n"
            'Good one,"£150,000",900,M14 5RG,Terraced,England\n'
            "Bad price,-10,900,M14 5RG,terraced,england\n"
            "Bad postcode,150000,900,ZZZ,terraced,england\n"
            ",150000,900,,flat,england\n"
        ).encode()
        r = client.post("/api/imports/properties", files={"file": ("mine.csv", csv_body, "text/csv")})
        assert r.status_code == 201, r.text
        rec = r.json()
        assert rec["status"] == "completed_with_errors"
        assert rec["rows_total"] == 4 and rec["rows_imported"] == 1 and rec["rows_rejected"] == 3
        assert {e["row"] for e in rec["errors"]} == {3, 4, 5}
        props = client.get("/api/properties").json()["items"]
        assert props[0]["data_source"] == "csv_import" and props[0]["import_id"] == rec["id"]
        assert client.get(f"/api/imports/{rec['id']}").json()["sha256"] == rec["sha256"]

    def test_properties_csv_missing_columns(self, client, user):
        r = client.post("/api/imports/properties", files={"file": ("x.csv", b"name,price\na,1\n", "text/csv")})
        assert r.json()["status"] == "failed"
        assert "missing required columns" in r.json()["errors"][0]["error"]

    def test_rejects_non_csv(self, client, user):
        r = client.post("/api/imports/properties", files={"file": ("x.xlsx", b"PK", "application/zip")})
        assert r.status_code == 415

    def test_template_download(self, client, user):
        r = client.get("/api/imports/templates/properties.csv")
        assert r.text.startswith("title,asking_price,estimated_monthly_rent")

    def test_land_registry_import_validation_upsert_and_delete(self, admin_client, db):
        rows = _ppd_rows(30)
        bad = [
            '"not-a-guid","100000","2024-02-01 00:00","LS6 1AA","T","N","F","1","","X","","LEEDS","LEEDS","WY","A","A"',
            '"{11111111-2222-3333-4444-555555555555}","abc","2024-02-01 00:00","LS6 1AA","T","N","F","1","","X","","LEEDS","LEEDS","WY","A","A"',
            '"{11111111-2222-3333-4444-555555555556}","100000","2024-13-45 00:00","LS6 1AA","T","N","F","1","","X","","LEEDS","LEEDS","WY","A","A"',
            '"{11111111-2222-3333-4444-555555555557}","100000","2024-02-01 00:00","LS6 1AA","Q","N","F","1","","X","","LEEDS","LEEDS","WY","A","A"',
        ]
        body = ("\n".join(rows + bad) + "\n").encode()
        r = admin_client.post("/api/imports/land-registry", files={"file": ("pp-test.csv", body, "text/csv")})
        assert r.status_code == 201, r.text
        rec = r.json()
        assert rec["rows_total"] == 34 and rec["rows_imported"] == 30 and rec["rows_rejected"] == 4
        assert rec["status"] == "completed_with_errors"
        assert "Open Government Licence" in rec["licence"] and "Crown copyright" in rec["attribution"]
        reasons = {e["error"] for e in rec["errors"]}
        assert any("GUID" in x for x in reasons) and any("price" in x for x in reasons)
        assert any("date" in x for x in reasons) and any("property_type" in x for x in reasons)

        # Same file again is refused.
        dup = admin_client.post("/api/imports/land-registry", files={"file": ("pp-test.csv", body, "text/csv")})
        assert dup.status_code == 409

        # A change (C) record updates price; a deletion (D) record removes the sale.
        first, second = rows[0].split(","), rows[1].split(",")
        change = ",".join([first[0], '"999999"'] + first[2:-1] + ['"C"'])
        deletion = ",".join(second[:-1] + ['"D"'])
        r2 = admin_client.post(
            "/api/imports/land-registry",
            files={"file": ("pp-update.csv", f"{change}\n{deletion}\n".encode(), "text/csv")},
        )
        assert r2.json()["status"] == "completed"
        cov = admin_client.get("/api/market/coverage").json()
        assert cov["transactions"] == 29
        from app.models import PricePaidTransaction

        changed_id = first[0].strip('"')
        deleted_id = second[0].strip('"')
        assert db.query(PricePaidTransaction).filter_by(transaction_id=changed_id).one().price == 999999
        assert db.query(PricePaidTransaction).filter_by(transaction_id=deleted_id).first() is None

    def test_market_endpoints_on_imported_data(self, admin_client):
        rows = _ppd_rows(40, start=date(2023, 3, 1))
        admin_client.post(
            "/api/imports/land-registry",
            files={"file": ("pp-market.csv", ("\n".join(rows) + "\n").encode(), "text/csv")},
        )
        s = admin_client.get("/api/market/summary?area=LS6&months=24").json()
        assert s["available"] and s["overall"]["count"] >= 20
        assert s["overall"]["p25"] <= s["overall"]["median"] <= s["overall"]["p75"]
        assert admin_client.get("/api/market/summary?area=Leeds").json()["area"]["kind"] == "local_authority"
        assert admin_client.get("/api/market/summary?area=Atlantis").status_code == 404
        assert admin_client.get("/api/market/summary?area=LS6&property_type=Z").status_code == 422
        t = admin_client.get("/api/market/trend?area=LS6 1").json()
        assert t["points"] and all("low_sample" in p for p in t["points"])
        areas = admin_client.get("/api/market/areas?q=lee").json()
        assert any(a["value"] == "Leeds" for a in areas)
        comps = admin_client.get("/api/market/comparables?postcode=LS6 1ZZ&property_type=terraced").json()
        assert comps["available"] and all(c["property_type"] == "Terraced" for c in comps["sales"])
        assert admin_client.get("/api/market/comparables?postcode=nonsense").json()["available"] is False


class TestReports:
    def test_pdf_and_csv_reports(self, client, prop):
        a = client.post(f"/api/properties/{prop['id']}/analyses", json={}).json()
        client.post(f"/api/analyses/{a['id']}/explanations")
        pdf = client.post(f"/api/analyses/{a['id']}/reports?kind=pdf").json()
        assert pdf["content_type"] == "application/pdf" and pdf["size_bytes"] > 3000
        data = client.get(f"/api/reports/{pdf['id']}/download")
        assert data.content[:4] == b"%PDF"
        assert "attachment" in data.headers["content-disposition"]
        csv_rep = client.post(f"/api/analyses/{a['id']}/reports?kind=csv").json()
        text = client.get(f"/api/reports/{csv_rep['id']}/download").content.decode("utf-8-sig")
        assert "generated_utc" in text and "gross_yield" in text and "assumption" in text
        assert client.post(f"/api/analyses/{a['id']}/reports?kind=docx").status_code == 422
        assert len(client.get("/api/reports").json()) == 2
        assert client.delete(f"/api/reports/{pdf['id']}").status_code == 204

    def test_dashboard(self, client, prop):
        client.post(f"/api/properties/{prop['id']}/analyses", json={})
        d = client.get("/api/dashboard").json()
        assert d["counts"]["properties"] == 1 and d["counts"]["analyses"] == 1
        assert d["portfolio"]["average_gross_yield_pct"] == 6.6
        assert d["portfolio"]["analysed_properties"][0]["gross_yield"] == 6.6
        assert "attribution" in d["market_data"]


def test_unverified_figures_ignores_derived_values():
    ctx = {"metrics": {"a": {"value": 1000}, "b": {"value": 250}}}
    content = ExplanationContent(
        summary="Rent of £1,000 less £250 leaves £750; that is £12,000 a year.",
        strengths=[],
        weaknesses=[],
        risks=[],
        yield_and_cash_flow="",
        sensitivity="",
        improvements=[],
        caveats=[],
    )
    assert find_unverified_figures(content, ctx) == []


def test_pdf_is_valid_bytes_for_cash_purchase(client, prop):
    a = client.post(f"/api/properties/{prop['id']}/analyses", json={"overrides": {"financing": "cash"}}).json()
    pdf = client.post(f"/api/analyses/{a['id']}/reports?kind=pdf").json()
    assert io.BytesIO(client.get(f"/api/reports/{pdf['id']}/download").content).read(4) == b"%PDF"
