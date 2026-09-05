#!/bin/sh
set -eu

echo "waiting for postgres..."
python - <<'PY'
import os, time
import psycopg
url = os.environ.get("DATABASE_URL", "postgresql+psycopg://catshort:catshort@postgres:5432/catshort")
dsn = url.replace("postgresql+psycopg://", "postgresql://")
for i in range(60):
    try:
        with psycopg.connect(dsn) as conn:
            conn.execute("SELECT 1")
        print("postgres ready")
        break
    except Exception as exc:
        print(f"  retry {i+1}: {exc}")
        time.sleep(1)
else:
    raise SystemExit("postgres not ready")
PY

cd /app
python - <<'PY'
import fcntl
from pathlib import Path
import subprocess
lock = Path("/data/.migrate.lock")
lock.parent.mkdir(parents=True, exist_ok=True)
with lock.open("w") as fh:
    fcntl.flock(fh, fcntl.LOCK_EX)
    subprocess.check_call(["alembic", "upgrade", "head"])
PY

python /app/scripts/generate_bed.py
python /app/scripts/generate_sample.py "${DRIVE_INBOX_DIR:-/data/inbox}/sample-cat.mp4"

exec "$@"
