#!/usr/bin/env sh

# Docker init script - runs migrations and then starts the application
# This script should be executed as the entrypoint for the container

set -e

echo "Starting initialization..."

# Run migrations
if [ -f /app/scripts/migrate.sh ]; then
    sh /app/scripts/migrate.sh
else
    echo "Warning: migrate.sh not found, skipping migrations"
fi

# Execute the main command (uvicorn)
echo "Starting application..."
exec "$@"
