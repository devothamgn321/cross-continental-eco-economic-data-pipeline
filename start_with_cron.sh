#!/bin/sh
set -e

echo "Waiting for PostgreSQL..."

until python3 -c "import psycopg2; psycopg2.connect(host='${DB_HOST}', port='${DB_PORT}', dbname='${DB_NAME}', user='${DB_USER}', password='${DB_PASSWORD}').close()" >/dev/null 2>&1
do
  echo "PostgreSQL not ready yet. Retrying in 2 seconds..."
  sleep 2
done

echo "PostgreSQL is up."

FOOD_BACKFILL_FILE="/app/data/raw/food_prices/wfp_food_prices_master_2022_2025.csv"
WORLD_BANK_FILE="/app/data/processed/world_bank/world_bank_monthly.csv"
FOOD_PRICES_FILE="/app/data/processed/food_prices/food_prices.csv"
ENERGY_FILE="/app/data/processed/energy/energy.csv"
WEATHER_FILE="/app/data/processed/weather/weather.csv"

MASTER_TABLE_EXISTS=$(python3 - <<EOF
import os
import psycopg2

conn = psycopg2.connect(
    host=os.environ["DB_HOST"],
    port=os.environ["DB_PORT"],
    dbname=os.environ["DB_NAME"],
    user=os.environ["DB_USER"],
    password=os.environ["DB_PASSWORD"]
)

cur = conn.cursor()
cur.execute("""
    SELECT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = 'master_data'
    );
""")
exists = cur.fetchone()[0]
cur.close()
conn.close()

print("true" if exists else "false")
EOF
)

if [ -f "$FOOD_BACKFILL_FILE" ] && \
   [ -f "$WORLD_BANK_FILE" ] && \
   [ -f "$FOOD_PRICES_FILE" ] && \
   [ -f "$ENERGY_FILE" ] && \
   [ -f "$WEATHER_FILE" ] && \
   [ "$MASTER_TABLE_EXISTS" = "true" ]; then
  echo "Historical pipeline outputs and database table already exist. Skipping backfill."
else
  if [ ! -f "$FOOD_BACKFILL_FILE" ]; then
    echo "Historical food backfill file not found. Running food backfill..."
    python3 food_backfill.py
  else
    echo "Historical food backfill file already exists. Skipping food_backfill.py."
  fi

  echo "Running full backfill pipeline..."
  PIPELINE_MODE=backfill python3 master.py
fi

echo "Writing environment for cron..."
printenv | grep -E '^(DB_HOST|DB_PORT|DB_NAME|DB_USER|DB_PASSWORD|EIA_API_KEY|WEATHER_BASE_URL)=' > /app/cron.env

echo "Starting cron..."
crontab /app/cronjob
cron

echo "Starting Flask API..."
exec python3 app.py