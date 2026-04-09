#!/usr/bin/env sh
set -eu
cd /app
alembic upgrade head
exec python -m logpilot
