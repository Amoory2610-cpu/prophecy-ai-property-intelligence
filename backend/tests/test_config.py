import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_production_requires_real_secret():
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings(environment="production", cookie_secure=True)


def test_production_requires_secure_cookie():
    with pytest.raises(ValidationError, match="COOKIE_SECURE"):
        Settings(environment="production", secret_key="x" * 48, cookie_secure=False)


def test_production_ok_with_secure_settings():
    s = Settings(environment="production", secret_key="x" * 48, cookie_secure=True)
    assert s.environment == "production"


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("postgres://u:p@h:5432/d", "postgresql+psycopg://u:p@h:5432/d"),
        ("postgresql://u:p@h/d", "postgresql+psycopg://u:p@h/d"),
        ("sqlite:///x.db", "sqlite:///x.db"),
    ],
)
def test_database_url_normalised_for_hosting_providers(url, expected):
    assert Settings(database_url=url).database_url == expected


def test_cors_origins_from_comma_list():
    assert Settings(cors_origins="http://a.test, http://b.test").cors_origins == ["http://a.test", "http://b.test"]


def test_ai_configured_only_with_key():
    assert not Settings(ai_provider="anthropic").ai_configured
    assert Settings(ai_provider="anthropic", anthropic_api_key="k").ai_configured
    assert not Settings(ai_provider="none", anthropic_api_key="k").ai_configured
