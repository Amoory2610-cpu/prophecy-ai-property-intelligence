from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import PROPERTY, _register


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["database"] is True
    assert r.headers["x-content-type-options"] == "nosniff"


class TestAuth:
    def test_register_sets_httponly_cookie(self, client):
        r = client.post("/api/auth/register", json={"email": "Cookie@Example.com", "password": "abcdef1234!"})
        assert r.status_code == 201
        cookie = r.headers["set-cookie"].lower()
        assert "httponly" in cookie and "samesite=lax" in cookie
        assert r.json()["user"]["email"] == "cookie@example.com"
        assert "password" not in r.text.lower().replace("password_hash", "")

    def test_duplicate_email_case_insensitive(self, client, user):
        r = client.post("/api/auth/register", json={"email": user["email"].upper(), "password": "abcdef1234!"})
        assert r.status_code == 409

    def test_weak_passwords_rejected(self, client):
        for pw in ("short1", "alllettersonly", "1234567890123"):
            r = client.post("/api/auth/register", json={"email": "weak@example.com", "password": pw})
            assert r.status_code == 422, pw

    def test_invalid_email_rejected(self, client):
        r = client.post("/api/auth/register", json={"email": "not-an-email", "password": "abcdef1234!"})
        assert r.status_code == 422
        assert r.json()["errors"][0]["field"] == "email"

    def test_login_and_me(self, user):
        with TestClient(app) as fresh:
            assert fresh.get("/api/auth/me").status_code == 401
            r = fresh.post("/api/auth/login", json={"email": user["email"], "password": user["password"]})
            assert r.status_code == 200
            assert fresh.get("/api/auth/me").json()["email"] == user["email"]

    def test_bearer_token_auth(self, user):
        with TestClient(app) as fresh:
            r = fresh.get("/api/auth/me", headers={"Authorization": f"Bearer {user['token']}"})
            assert r.status_code == 200

    def test_wrong_password_and_unknown_user_same_error(self, client, user):
        a = client.post("/api/auth/login", json={"email": user["email"], "password": "wrong-pass-1"})
        b = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "wrong-pass-1"})
        assert a.status_code == b.status_code == 401
        assert a.json() == b.json()

    def test_login_rate_limited(self, client, user):
        codes = [
            client.post("/api/auth/login", json={"email": user["email"], "password": "nope-nope-1"}).status_code
            for _ in range(7)
        ]
        assert codes[:5] == [401] * 5
        assert codes[-1] == 429

    def test_tampered_token_rejected(self, user):
        with TestClient(app) as fresh:
            bad = user["token"][:-4] + "abcd"
            assert fresh.get("/api/auth/me", headers={"Authorization": f"Bearer {bad}"}).status_code == 401

    def test_logout_clears_cookie(self, client, user):
        assert client.post("/api/auth/logout").status_code == 204
        assert client.get("/api/auth/me").status_code == 401

    def test_password_change_revokes_old_tokens(self, client, user):
        old = user["token"]
        r = client.post(
            "/api/auth/me/password",
            json={"current_password": user["password"], "new_password": "new-password-99"},
        )
        assert r.status_code == 200
        with TestClient(app) as fresh:
            assert fresh.get("/api/auth/me", headers={"Authorization": f"Bearer {old}"}).status_code == 401
        assert client.get("/api/auth/me").status_code == 200  # new cookie issued

    def test_password_change_requires_current(self, client, user):
        r = client.post("/api/auth/me/password", json={"current_password": "wrong", "new_password": "new-password-99"})
        assert r.status_code == 400

    def test_update_profile(self, client, user):
        r = client.patch("/api/auth/me", json={"full_name": "Jo Investor"})
        assert r.json()["full_name"] == "Jo Investor"

    def test_delete_account_removes_data(self, client, user):
        client.post("/api/properties", json=PROPERTY)
        assert client.request("DELETE", "/api/auth/me", json={"password": "wrong"}).status_code == 400
        assert client.request("DELETE", "/api/auth/me", json={"password": user["password"]}).status_code == 204
        with TestClient(app) as fresh:
            r = fresh.post("/api/auth/login", json={"email": user["email"], "password": user["password"]})
            assert r.status_code == 401


class TestIsolation:
    """Users must never see or modify another user's records."""

    def test_cannot_access_other_users_property(self, client, prop, other_client):
        pid = prop["id"]
        assert other_client.get(f"/api/properties/{pid}").status_code == 404
        assert other_client.patch(f"/api/properties/{pid}", json={"title": "x"}).status_code == 404
        assert other_client.delete(f"/api/properties/{pid}").status_code == 404
        assert other_client.post(f"/api/properties/{pid}/analyses", json={}).status_code == 404
        assert other_client.get("/api/properties").json()["total"] == 0

    def test_cannot_reference_other_users_property(self, client, prop, other_client):
        mine = other_client.post("/api/properties", json=PROPERTY).json()
        r = other_client.post("/api/comparisons", json={"name": "x", "property_ids": [mine["id"], prop["id"]]})
        assert r.status_code == 404
        wl = other_client.post("/api/watchlists", json={"name": "W"}).json()
        assert (
            other_client.post(f"/api/watchlists/{wl['id']}/items", json={"property_id": prop["id"]}).status_code == 404
        )

    def test_cannot_read_other_users_analysis_or_report(self, client, prop, other_client):
        a = client.post(f"/api/properties/{prop['id']}/analyses", json={}).json()
        rep = client.post(f"/api/analyses/{a['id']}/reports?kind=csv").json()
        assert other_client.get(f"/api/analyses/{a['id']}").status_code == 404
        assert other_client.post(f"/api/analyses/{a['id']}/explanations").status_code == 404
        assert other_client.get(f"/api/reports/{rep['id']}/download").status_code == 404
        assert other_client.get("/api/analyses").json() == []

    def test_endpoints_require_auth(self):
        with TestClient(app) as anon:
            for path in ("/api/properties", "/api/analyses", "/api/dashboard", "/api/market/coverage", "/api/reports"):
                assert anon.get(path).status_code == 401, path
            assert anon.post("/api/calculate", json={"purchase_price": 1, "monthly_rent": 1}).status_code == 401


def test_cross_origin_unsafe_request_blocked(client, user):
    r = client.post("/api/properties", json=PROPERTY, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    ok = client.post("/api/properties", json=PROPERTY, headers={"Origin": "http://localhost:3000"})
    assert ok.status_code == 201


def test_admin_only_market_import(client, user):
    r = client.post("/api/imports/land-registry", files={"file": ("pp.csv", b"x", "text/csv")})
    assert r.status_code == 403


def test_second_user_registration_is_independent():
    with TestClient(app) as a, TestClient(app) as b:
        _register(a)
        _register(b)
        a.post("/api/properties", json=PROPERTY)
        assert b.get("/api/properties").json()["total"] == 0
