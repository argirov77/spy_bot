#!/bin/sh
set -e

until pg_isready -h db -U postgres -d spy; do
  echo 'Waiting for Postgres...'
  sleep 1
done

alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
