# Prophecy AI: property investment intelligence

[![CI](https://github.com/Amoory2610-cpu/prophecy-ai-property-intelligence/actions/workflows/ci.yml/badge.svg)](https://github.com/Amoory2610-cpu/prophecy-ai-property-intelligence/actions/workflows/ci.yml)

A full-stack platform for analysing UK buy-to-let deals. Enter a price and a rent and
Prophecy works out stamp duty, the mortgage, voids, running costs, tax scenarios, cash flow and
long-run returns, and **shows the formula and inputs behind every figure**. It stress-tests
deals, compares properties on equal terms, pulls real comparable sales from HM Land Registry
data and explains each deal in plain English, grounded in the calculated numbers.

![Analysis page](docs/screenshots/05-analysis.png)

## What it does

| Area | What's implemented |
| --- | --- |
| Deal analysis | Deposit, LTV, mortgage (repayment or interest-only, fee upfront or added), gross/net yield, net yield on total cost, operating costs and voids, cash flow before and after financing, cash-on-cash, lender interest-cover stress test, 1 to 40-year projection, exit with selling costs and CGT, IRR, equity multiple |
| Property tax | SDLT (England and NI) including first-time buyer relief, the 5% additional-dwelling surcharge and the 2% non-resident surcharge; LBTT (Scotland) with ADS; LTT (Wales) higher rates. Band-by-band breakdown, rules dated and linked to official sources |
| Income tax scenarios | Individual (Section 24 finance-cost credit), limited company (corporation tax with marginal relief) or tax excluded; clearly labelled as simplified, not advice |
| "Show the working" | Every metric carries its formula, the concrete inputs and whether it is a calculation or an estimate |
| What would need to change | Break-even rent, maximum mortgage rate, maximum voids, maximum price, price for a target yield, all solved numerically against the engine |
| Simulator | Live sliders and every assumption editable; sensitivity tornado chart; base, optimistic and pessimistic scenarios with per-driver attribution |
| Comparison | 2 to 6 properties under shared assumptions, per-measure leaders and laggards, generated trade-off notes, CSV export; no "best overall" verdict |
| Market data | HM Land Registry Price Paid Data importer (validated, upserts, change/delete records), area summaries, monthly trends with low-sample flags, price distributions, same-type comparable sales, comparables-based reference value |
| Model evaluation | Live time-split backtest of the comparables estimator against a naive baseline, computed from whatever data is imported |
| AI explanations | Provider-independent: Claude (Anthropic SDK structured output), any OpenAI-compatible endpoint, or a deterministic rule-based explainer that works with no key. Unverifiable figures are flagged |
| Reports | PDF (assumptions, formulas, tax bands, projection, sensitivity, comparables, explanation, provenance, limitations, timestamp) and CSV exports |
| Accounts | Registration, login, profile, password change (revokes other sessions), sign out everywhere, account deletion, default assumptions |
| Data management | Property CSV import with row-level errors, import history with hashes, licences, attribution and date ranges, freshness indicators |

Seeded demo properties are labelled as demonstration data everywhere they appear, including
reports. Their prices and rents are illustrative. Comparable sales shown alongside them are
real Land Registry records.

## Technology

* **Frontend:** Next.js 16 (App Router, Cache Components), React 19, TypeScript, Tailwind CSS 4,
  shadcn/ui (Base UI), TanStack Query, Recharts. Vitest and Testing Library for unit tests,
  Playwright for end-to-end tests.
* **Backend:** Python 3.13, FastAPI, SQLAlchemy 2, Alembic, Pydantic 2, pandas, NumPy,
  ReportLab, Argon2, PyJWT, Anthropic SDK. pytest and Ruff.
* **Data:** PostgreSQL 16.
* **Infrastructure:** Docker Compose, GitHub Actions CI (lint, type check, unit tests, migration
  drift check, PostgreSQL-backed API tests, production build, Dockerised end-to-end tests).

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the design, data model, security model
and trade-offs.

```
backend/   FastAPI app, finance engine, services, Alembic migrations, tests
frontend/  Next.js app, components, unit tests (src/__tests__), Playwright tests (e2e/)
data/      Sample HM Land Registry extract (OGL v3.0)
docs/      Architecture notes and screenshots
```

## Quick start with Docker

Prerequisites: Docker Desktop (or Docker Engine with Compose v2).

```bash
cp .env.example .env
# Set SECRET_KEY (python -c "import secrets; print(secrets.token_urlsafe(48))") and POSTGRES_PASSWORD
docker compose up --build
```

Open http://localhost:3000, create an account and choose **Load the demo portfolio**.

On first start the backend applies migrations and imports the bundled Land Registry sample
(3,963 real 2024 sales in the seven demo postcode districts) when `IMPORT_SAMPLE_DATA=true`.
If ports 3000, 8000 or 5433 are taken, set `FRONTEND_PORT`, `BACKEND_PORT` or `POSTGRES_PORT`
in `.env`.

### Loading the full Land Registry dataset

Download a yearly file from
[GOV.UK Price Paid Data](https://www.gov.uk/government/statistical-data-sets/price-paid-data-downloads)
(for example `pp-2025.csv`, about 150 MB), place it in `data/`, then:

```bash
docker compose exec backend python -m app.cli import-ppd /data/pp-2025.csv
```

The 2024 file (929,467 sales) imports in about 75 seconds. Monthly update files can be
imported the same way: changed and deleted records are applied.

### Administrator access

Land Registry data is shared by all accounts, so uploading it through the web interface needs
an administrator:

```bash
docker compose exec backend python -m app.cli make-admin you@example.com
```

## Local development without Docker

Prerequisites: Python 3.12+, Node.js 22+, and a PostgreSQL 16 database (for example
`docker compose up -d db`, which listens on port 5433).

```bash
# Backend
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt      # Windows: .venv\Scripts\pip
cp ../.env.example .env                             # then set DATABASE_URL and SECRET_KEY
.venv/bin/alembic upgrade head
.venv/bin/python -m app.cli import-ppd ../data/samples/pp-2024-demo-districts.csv
.venv/bin/uvicorn app.main:app --reload --port 8000

# Frontend (another terminal)
cd frontend
npm ci
npm run dev                                         # http://localhost:3000
```

The API documentation is served at http://localhost:8000/api/docs.

## Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql+psycopg://prophecy:prophecy@localhost:5432/prophecy` | SQLAlchemy URL; `postgres://` URLs from hosting providers are accepted |
| `ENVIRONMENT` | `development` | `production` enforces a real `SECRET_KEY` and `COOKIE_SECURE=true` |
| `SECRET_KEY` | development placeholder | JWT signing key; 32+ random characters in production |
| `COOKIE_SECURE` | `false` | Set `true` behind HTTPS |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated allowed browser origins (also used for the CSRF Origin check) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `480` | Session length |
| `MAX_UPLOAD_MB` | `50` | Land Registry upload limit (property CSVs are capped at 10 MB) |
| `LOGIN_RATE_LIMIT_PER_MINUTE` | `10` | Failed and successful login attempts per IP and email |
| `AI_PROVIDER` | `none` | `none`, `anthropic` or `openai` |
| `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` | none / `claude-opus-5-5` | Claude explanations |
| `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL` | none | Any OpenAI-compatible endpoint |
| `IMPORT_SAMPLE_DATA` | `true` (Docker) | Import the bundled sample on container start |
| `API_ORIGIN` | `http://localhost:8000` | Where Next.js proxies `/api` (needed at build time) |
| `FRONTEND_PORT`, `BACKEND_PORT`, `POSTGRES_PORT` | 3000, 8000, 5433 | Docker Compose host ports |

Without an AI key the platform works fully and explanations come from the rule-based engine.

## Database migrations

```bash
cd backend
alembic upgrade head                                     # apply
alembic revision --autogenerate -m "describe change"     # create after editing app/models
alembic check                                            # fail if models and migrations differ
```

The Docker entrypoint runs `alembic upgrade head` before starting the API.

## Tests

```bash
# Backend: 169 test cases from 128 test functions (14 are parametrised over several inputs),
# covering the finance engine, tax rules, API, security, imports, reports and config
cd backend
pytest                                   # SQLite by default
TEST_DATABASE_URL=postgresql+psycopg://user:pass@localhost:5433/prophecy_test pytest
pytest --cov                             # coverage report (92% at last run)
ruff check app tests

# Frontend: 16 unit tests, lint, types, production build
cd frontend
npm test
npm run lint && npm run typecheck && npm run build

# End-to-end: 5 Playwright tests against a running stack (docker compose up)
cd frontend
npx playwright install chromium
BASE_URL=http://localhost:3000 npx playwright test
SCREENSHOTS=1 BASE_URL=http://localhost:3000 npx playwright test   # also refreshes docs/screenshots
```

The finance tests check figures against hand-worked band arithmetic and published values (for
example £200,000 over 25 years at 5% repayment is £1,169.18 a month), plus edge cases: cash
purchases, 0% and 100% deposits, 0% interest, zero rent, holding periods longer than the
mortgage term, falling prices, invalid inputs and break-even solutions that must return zero
cash flow.

**Not covered by automated tests:** live calls to the Anthropic and OpenAI APIs (the providers
are exercised through the fallback path and a fake provider only), and the Render deployment
blueprint.

## Deployment

The app is container-ready: both services have production Dockerfiles, the API has a health
check (`/api/health`, which also checks the database) and migrations run on start.

`render.yaml` is a [Render](https://render.com) Blueprint for a PostgreSQL database plus the
two services. It is prepared but **has not been verified on a live account**. To use it:

1. Push this repository to GitHub and create a new Blueprint on Render from it.
2. After the first deploy, set `CORS_ORIGINS` on `prophecy-api` to the frontend URL and
   `API_ORIGIN` on `prophecy-web` to the API URL, then redeploy the frontend (the proxy target
   is fixed at build time).
3. Import market data: `python -m app.cli import-ppd ...` from the API service shell, or make
   yourself an admin and upload a monthly file.
4. Optionally set `AI_PROVIDER=anthropic` and `ANTHROPIC_API_KEY`.

Any platform that runs Docker images and provides PostgreSQL (Fly.io, Railway, a VPS with
Compose) works the same way: set the environment variables above with
`ENVIRONMENT=production`, `COOKIE_SECURE=true` and a random `SECRET_KEY`.

## Data sources and limitations

* **HM Land Registry Price Paid Data** for sales in England and Wales. Contains HM Land Registry
  data © Crown copyright and database right. Licensed under the Open Government Licence v3.0.
  The bundled sample covers 2024 only; the UI shows how old the newest imported sale is.
* **Rents are user-supplied.** There is no free licensable UK rental comparables source, so
  every rent is labelled by where it came from.
* **No live listings.** Property portals do not offer public APIs and are not scraped.
* **Tax rules** were reviewed on 9 October 2026 and are simplified. The Autumn Budget 2025
  announced separate property income tax rates from April 2027; the rate can be overridden
  per analysis. Nothing here is financial, tax or mortgage advice.

## Licence

Code: all rights reserved by the author unless a licence file is added. Bundled Land Registry
data: Open Government Licence v3.0.
