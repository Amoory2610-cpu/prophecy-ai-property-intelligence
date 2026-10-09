"""Test configuration.

API tests run against ``TEST_DATABASE_URL`` when set (CI uses PostgreSQL), otherwise a
temporary SQLite file. The environment is configured before the app is imported.
"""

import os
import tempfile
import uuid
from pathlib import Path

_tmp = Path(tempfile.mkdtemp())
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", f"sqlite:///{(_tmp / 'test.db').as_posix()}")
os.environ["ENVIRONMENT"] = "test"
os.environ["AI_PROVIDER"] = "none"
os.environ["LOGIN_RATE_LIMIT_PER_MINUTE"] = "5"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.db import Base, SessionLocal, engine  # noqa: E402
from app.core.security import login_limiter  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def _reset_limiter():
    login_limiter.reset()


@pytest.fixture
def db():
    with SessionLocal() as s:
        yield s


def _register(client: TestClient, email: str | None = None, password: str = "correct-horse-42") -> dict:
    email = email or f"user-{uuid.uuid4().hex[:10]}@example.com"
    r = client.post("/api/auth/register", json={"email": email, "password": password, "full_name": "Test User"})
    assert r.status_code == 201, r.text
    return {"email": email, "password": password, "token": r.json()["access_token"]}


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def user(client):
    """A registered user; the client carries their session cookie."""
    return _register(client)


@pytest.fixture
def other_client():
    with TestClient(app) as c:
        _register(c)
        yield c


@pytest.fixture
def admin_client(db):
    with TestClient(app) as c:
        info = _register(c)
        u = db.query(User).filter_by(email=info["email"]).one()
        u.is_admin = True
        db.commit()
        yield c


PROPERTY = {
    "title": "2 bed terrace",
    "town": "Leeds",
    "postcode": "ls6 1aa",
    "property_type": "terraced",
    "tenure": "freehold",
    "bedrooms": 2,
    "asking_price": 200000,
    "estimated_monthly_rent": 1100,
}


@pytest.fixture
def prop(client, user):
    r = client.post("/api/properties", json=PROPERTY)
    assert r.status_code == 201, r.text
    return r.json()
