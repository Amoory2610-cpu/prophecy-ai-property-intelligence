#!/bin/sh
set -e
# Apply database migrations before serving.
alembic upgrade head
# Optionally load the bundled Land Registry sample on first start.
if [ "${IMPORT_SAMPLE_DATA:-false}" = "true" ] && [ -f /data/samples/pp-2024-demo-districts.csv ]; then
  python -m app.cli import-ppd /data/samples/pp-2024-demo-districts.csv || true
fi
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips="*"
