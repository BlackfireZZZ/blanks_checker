#!/usr/bin/env sh

# Script for running Alembic migrations
# This script is used during Docker container startup

set -e

echo "Running database migrations..."

cd /app

# Wait for database to be ready
until pg_isready -h ${DB_HOST:-db} -p ${DB_PORT:-5432} -U ${DB_USER:-postgres}; do
  echo "Waiting for database to be ready..."
  sleep 1
done

echo "Database is ready. Running migrations..."

# Run migrations
alembic upgrade head

echo "Migrations completed successfully!"
