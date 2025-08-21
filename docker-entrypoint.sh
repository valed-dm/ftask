#!/bin/sh

# Exit immediately if a command exits with a non-zero status.
set -e

# Wait for the database to be ready
echo "Waiting for postgres..."

while ! nc -z $POSTGRES_HOST $POSTGRES_PORT; do
  sleep 0.1
done

echo "PostgreSQL started"

# Run database migrations
echo "Running database migrations..."
alembic -c /app/alembic.ini upgrade head

# Start the application
echo "Starting application..."
exec "$@"
