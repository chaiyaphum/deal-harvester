#!/bin/bash
set -e

echo "Initializing database..."
card-retrieval init-db

echo "Running Alembic migrations..."
alembic upgrade head

echo "Starting scheduler..."
exec xvfb-run card-retrieval schedule
