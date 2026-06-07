#!/bin/sh
set -e

cd /app || exit 1

# Load environment variables written by start_with_cron.sh for cron jobs
if [ -f /app/cron.env ]; then
  export $(grep -v '^#' /app/cron.env | xargs)
fi

DB_HOST="${DB_HOST:-db}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-t9pipe}"
DB_USER="${DB_USER:-jhu}"
DB_PASSWORD="${DB_PASSWORD:-jhu123}"

export DB_HOST DB_PORT DB_NAME DB_USER DB_PASSWORD

echo "===== $(date) ====="
echo "DB_HOST=$DB_HOST"

echo "Waiting for PostgreSQL..."

until python3 -c "import psycopg2; psycopg2.connect(host='${DB_HOST}', port='${DB_PORT}', dbname='${DB_NAME}', user='${DB_USER}', password='${DB_PASSWORD}').close()" >/dev/null 2>&1
do
  echo "PostgreSQL not ready yet. Retrying in 2 seconds..."
  sleep 2
done

echo "PostgreSQL is up."

echo "Running incremental master pipeline..."
PIPELINE_MODE=incremental python3 master.py

echo "Incremental run complete."