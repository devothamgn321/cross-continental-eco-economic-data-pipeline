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

if [ -f "$FOOD_BACKFILL_FILE" ] && \
   [ -f "$WORLD_BANK_FILE" ] && \
   [ -f "$FOOD_PRICES_FILE" ] && \
   [ -f "$ENERGY_FILE" ] && \
   [ -f "$WEATHER_FILE" ]; then
  echo "Historical pipeline outputs already exist. Skipping backfill."
else
  echo "Historical outputs not found. Running food backfill..."
  python3 food_backfill.py

  echo "Running full backfill pipeline..."
  PIPELINE_MODE=backfill python3 master.py
fi

echo "Starting Flask API..."
exec python3 app.py