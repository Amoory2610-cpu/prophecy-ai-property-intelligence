from __future__ import annotations

import logging
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import text

from app.api.routes import analyses, auth, comparisons, data, properties, watchlists
from app.core.config import get_settings
from app.core.db import SessionLocal

log = logging.getLogger("prophecy")
settings = get_settings()

app = FastAPI(
    title="Prophecy AI API",
    version="1.0.0",
    description="UK buy-to-let investment analysis API. Figures are estimates, not financial advice.",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

_UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


@app.middleware("http")
async def security_headers_and_origin_check(request: Request, call_next):
    # CSRF defence in depth (alongside SameSite=Lax cookies): reject cross-site unsafe
    # requests whose Origin is not an allowed frontend origin.
    origin = request.headers.get("origin")
    if request.method in _UNSAFE and origin and origin not in settings.cors_origins:
        host = request.headers.get("host", "")
        if urlparse(origin).netloc != host:
            return JSONResponse({"detail": "Cross-origin request blocked"}, status_code=403)
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    if request.url.path.startswith("/api/") and "cache-control" not in response.headers:
        response.headers["Cache-Control"] = "no-store"
    return response


def _clean_errors(errors) -> list[dict]:
    out = []
    for e in errors:
        loc = [str(p) for p in e.get("loc", []) if p not in ("body",)]
        out.append({"field": ".".join(loc), "message": e.get("msg", "invalid value")})
    return out


@app.exception_handler(RequestValidationError)
async def request_validation_handler(_: Request, exc: RequestValidationError):
    return JSONResponse({"detail": "Validation failed", "errors": _clean_errors(exc.errors())}, status_code=422)


@app.exception_handler(ValidationError)
async def model_validation_handler(_: Request, exc: ValidationError):
    return JSONResponse({"detail": "Validation failed", "errors": _clean_errors(exc.errors())}, status_code=422)


@app.exception_handler(Exception)
async def unhandled(_: Request, exc: Exception):  # pragma: no cover - safety net
    log.exception("Unhandled error", exc_info=exc)
    return JSONResponse({"detail": "Internal server error"}, status_code=500)


for module in (auth, properties, analyses, comparisons, watchlists, data):
    app.include_router(module.router, prefix="/api")


@app.get("/api/health", tags=["meta"])
def health():
    db_ok = True
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception:  # pragma: no cover - depends on infrastructure
        db_ok = False
    return JSONResponse(
        {
            "status": "ok" if db_ok else "degraded",
            "database": db_ok,
            "version": app.version,
            "ai_provider": settings.ai_provider if settings.ai_configured else "rule_based",
        },
        status_code=200 if db_ok else 503,
    )
