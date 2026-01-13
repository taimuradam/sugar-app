#!/bin/sh
set -e

echo "Waiting for database..."
python - <<'PY'
import os, time
from sqlalchemy import create_engine, text

url = os.getenv("DATABASE_URL")
if not url:
    raise SystemExit("DATABASE_URL is not set")

engine = create_engine(url, pool_pre_ping=True)
deadline = time.time() + 60
last_err = None

while time.time() < deadline:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        raise SystemExit(0)
    except Exception as e:
        last_err = e
        time.sleep(1)

raise SystemExit(f"Database not ready after 60s: {last_err}")
PY

if [ "${AUTO_MIGRATE:-1}" = "1" ]; then
  echo "Running database migrations..."
  alembic upgrade head
fi

if [ "${AUTO_SEED_ADMIN:-1}" = "1" ]; then
  echo "Ensuring admin user exists..."
  python -m app.seed
fi

if [ "$#" -gt 0 ]; then
  exec "$@"
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000