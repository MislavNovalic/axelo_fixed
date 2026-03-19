#!/bin/sh
set -e

echo "=== Axelo Backend Starting ==="

# ── Wait for DB to be ready (DO managed DB can take a moment on cold start) ───
echo "--- Waiting for database ---"
MAX_TRIES=30
i=0
until python -c "
from app.database import engine
from sqlalchemy import text
with engine.connect() as c: c.execute(text('SELECT 1'))
print('DB ready')
" 2>/dev/null; do
  i=$((i + 1))
  if [ "$i" -ge "$MAX_TRIES" ]; then
    echo "ERROR: Database not reachable after ${MAX_TRIES} attempts."
    exit 1
  fi
  echo "  Waiting for DB... attempt $i/$MAX_TRIES"
  sleep 2
done

# ── Create any missing tables ─────────────────────────────────────────────────
echo "--- Ensuring tables exist ---"
python -c "
from app.database import Base, engine
import app.models
Base.metadata.create_all(bind=engine)
print('Tables OK')
"

# ── Run Alembic migrations ────────────────────────────────────────────────────
echo "--- Running Alembic migrations ---"
alembic upgrade head && echo "Migrations OK" || echo "WARNING: Migration issue (may be OK on fresh DB)"

# ── Seed demo data — non-fatal so app always starts ──────────────────────────
echo "--- Seeding demo data ---"
python -c "
try:
    from app.seed import seed
    seed()
    print('Seed OK')
except Exception as e:
    print(f'WARNING: Seed skipped: {e}')
" || true

# ── Start API ─────────────────────────────────────────────────────────────────
echo "--- Starting uvicorn ---"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 \
    --proxy-headers \
    --forwarded-allow-ips "*"
