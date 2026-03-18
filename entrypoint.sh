#!/bin/bash
set -e

echo "Running Alembic migrations..."
alembic upgrade head || {
    echo "Migration failed, stamping head and retrying..."
    alembic stamp head
    alembic upgrade head
}

echo "Starting scheduler..."
exec xvfb-run card-retrieval schedule
