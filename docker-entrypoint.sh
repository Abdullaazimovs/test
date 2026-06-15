#!/usr/bin/env bash
# Container entrypoint.
#
# When RUN_MIGRATIONS=1 (set for the API service) it waits for the database to
# accept connections, applies Alembic migrations, then execs the given command.
# Worker/beat containers skip migrations and just run their command.
set -euo pipefail

if [[ "${RUN_MIGRATIONS:-0}" == "1" ]]; then
  echo "Waiting for the database to become available..."
  python - <<'PY'
import asyncio, os, sys
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings

async def wait():
    for attempt in range(30):
        try:
            engine = create_async_engine(settings.database_url)
            async with engine.connect():
                pass
            await engine.dispose()
            print("Database is ready.")
            return
        except Exception as exc:  # noqa: BLE001
            print(f"  not ready yet ({attempt + 1}/30): {exc}")
            await asyncio.sleep(2)
    print("Database did not become ready in time.", file=sys.stderr)
    sys.exit(1)

asyncio.run(wait())
PY

  echo "Applying database migrations..."
  alembic upgrade head
fi

exec "$@"
