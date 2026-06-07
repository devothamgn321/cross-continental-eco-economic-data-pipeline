#!/usr/bin/env python
# coding: utf-8

from pathlib import Path
from datetime import datetime, timezone
import os
import time
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests
from requests.exceptions import ReadTimeout, RequestException
from sqlalchemy import create_engine, text

from config import DB_CONFIG


# Base project directory
BASE_DIR = Path(__file__).resolve().parent

# Data folder structure
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw" / "world_bank"
PROCESSED_DIR = DATA_DIR / "processed" / "world_bank"

# Ensure raw/processed folders exist before writing files
RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# Output file for processed data
OUTPUT_FILE = PROCESSED_DIR / "world_bank_monthly.csv"


COUNTRIES: Dict[str, str] = {
    "USA": "USA",
    "BRA": "BRA",
    "IND": "IND",
    "PHL": "PHL",
    "NGA": "NGA",
}

INDICATORS: Dict[str, str] = {
    "gdp": "NY.GDP.MKTP.CD",
    "inflation": "FP.CPI.TOTL.ZG",
    "population": "SP.POP.TOTL",
}

WORLD_BANK_API_TEMPLATE = "https://api.worldbank.org/v2/country/{country}/indicator/{indicator}"
REQUEST_TIMEOUT = int(os.getenv("WORLD_BANK_TIMEOUT", "90"))
MAX_RETRIES = int(os.getenv("WORLD_BANK_MAX_RETRIES", "4"))
RETRY_DELAY = int(os.getenv("WORLD_BANK_RETRY_DELAY", "5"))


def get_engine():
    """
    Create and return a SQLAlchemy engine using the shared DB config.
    This is only used if the script is allowed to load directly to PostgreSQL.
    """
    engine_url = (
        f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
        f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
    )
    return create_engine(engine_url)


def get_pipeline_mode() -> str:
    """
    Read pipeline mode from environment.
    Expected values:
    - backfill
    - incremental
    """
    return os.getenv("PIPELINE_MODE", "backfill").strip().lower()


def get_backfill_year_range() -> Tuple[int, int]:
    """
    Read configured backfill start/end years from environment variables.
    Defaults to 2022 through 2024 if not provided.
    """
    start_year = int(os.getenv("WORLD_BANK_START_YEAR", "2022"))
    end_year = int(os.getenv("WORLD_BANK_END_YEAR", "2024"))
    return start_year, end_year


def world_bank_request(country: str, indicator: str, page: int = 1, per_page: int = 20000) -> List[dict]:
    """
    Make a single request to the World Bank API for one country + indicator.
    Returns the list of data records from the payload.
    Retries automatically on timeouts and temporary request failures.
    """
    url = WORLD_BANK_API_TEMPLATE.format(country=country, indicator=indicator)
    params = {
        "format": "json",
        "per_page": per_page,
        "page": page,
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            payload = response.json()

            if not isinstance(payload, list) or len(payload) < 2 or payload[1] is None:
                return []

            return payload[1]

        except ReadTimeout:
            print(
                f"Timeout on World Bank request: country={country}, "
                f"indicator={indicator}, page={page}, "
                f"attempt={attempt}/{MAX_RETRIES}"
            )
            if attempt == MAX_RETRIES:
                raise
            time.sleep(RETRY_DELAY)

        except RequestException as e:
            print(
                f"World Bank API request failed: country={country}, "
                f"indicator={indicator}, page={page}, "
                f"attempt={attempt}/{MAX_RETRIES}, error={e}"
            )
            if attempt == MAX_RETRIES:
                raise
            time.sleep(RETRY_DELAY)

    return []


def fetch_indicator_series(country: str, indicator: str, start_year: int, end_year: int) -> pd.DataFrame:
    """
    Fetch annual data for a single country + indicator over the requested year range.

    This function also saves the extracted annual data into the raw folder
    before any monthly expansion happens.
    """
    rows: List[dict] = []
    page = 1

    while True:
        batch = world_bank_request(country=country, indicator=indicator, page=page)
        if not batch:
            break

        for item in batch:
            date_str = item.get("date")
            value = item.get("value")

            if value is None or date_str is None:
                continue

            try:
                year = int(date_str)
            except (TypeError, ValueError):
                continue

            if start_year <= year <= end_year:
                rows.append(
                    {
                        "country_code": country,
                        "year": year,
                        "value": float(value),
                    }
                )

        if len(batch) < 20000:
            break

        page += 1

    raw_df = pd.DataFrame(rows)

    # Save raw annual extract for auditing/debugging
    raw_file = RAW_DIR / f"{country}_{indicator}_raw.csv"
    raw_df.to_csv(raw_file, index=False)
    print(f"Saved raw file: {raw_file}")

    return raw_df


def get_latest_available_year_from_api() -> Optional[int]:
    """
    Check the World Bank API to estimate the latest available year across
    the selected countries, using population as the probe indicator.
    """
    latest_years: List[int] = []

    for country in COUNTRIES.values():
        try:
            batch = world_bank_request(
                country=country,
                indicator=INDICATORS["population"],
                page=1,
                per_page=200,
            )
        except requests.RequestException:
            continue

        valid_years: List[int] = []
        for item in batch:
            if item.get("value") is None:
                continue

            try:
                valid_years.append(int(item.get("date")))
            except (TypeError, ValueError):
                continue

        if valid_years:
            latest_years.append(max(valid_years))

    return max(latest_years) if latest_years else None


def get_max_loaded_year_from_db(table_name: str = "worldbank") -> Optional[int]:
    """
    Look at the existing database table and determine the latest loaded year.
    Used only in incremental mode.
    """
    try:
        engine = get_engine()
        query = text(
            f"""
            SELECT MAX(CAST(SPLIT_PART(year_month, '-', 1) AS INTEGER)) AS max_year
            FROM {table_name}
            """
        )

        with engine.connect() as conn:
            result = conn.execute(query).scalar()
            return int(result) if result is not None else None
    except Exception:
        return None


def resolve_year_range() -> Tuple[Optional[int], Optional[int], str]:
    """
    Determine which year range this pipeline should extract.

    Backfill mode:
    - uses configured start/end years

    Incremental mode:
    - compares API latest year vs current DB max year
    - only pulls new years if available
    """
    mode = get_pipeline_mode()

    if mode == "backfill":
        start_year, end_year = get_backfill_year_range()
        return start_year, end_year, "configured backfill range"

    if mode != "incremental":
        raise ValueError("PIPELINE_MODE must be either 'backfill' or 'incremental'.")

    api_latest_year = get_latest_available_year_from_api()
    if api_latest_year is None:
        return None, None, "unable to detect latest available API year"

    db_max_year = get_max_loaded_year_from_db("worldbank")

    if db_max_year is None:
        return (
            api_latest_year,
            api_latest_year,
            f"no existing DB rows found; using latest API year {api_latest_year}",
        )

    if api_latest_year <= db_max_year:
        return (
            None,
            None,
            f"no new World Bank data available; API latest year={api_latest_year}, DB loaded through={db_max_year}",
        )

    return (
        db_max_year + 1,
        api_latest_year,
        f"incremental range from DB max year {db_max_year} to API latest year {api_latest_year}",
    )


def expand_annual_to_monthly(df: pd.DataFrame, value_column: str) -> pd.DataFrame:
    """
    Expand annual indicator values to monthly rows by repeating the same annual
    value across all 12 months in that year.
    """
    if df.empty:
        return pd.DataFrame(columns=["country_code", "year_month", value_column])

    rows: List[dict] = []

    for row in df.itertuples(index=False):
        for month in range(1, 13):
            rows.append(
                {
                    "country_code": row.country_code,
                    "year_month": f"{int(row.year):04d}-{month:02d}",
                    value_column: float(row.value),
                }
            )

    return pd.DataFrame(rows)


def build_world_bank_monthly(start_year: int, end_year: int) -> pd.DataFrame:
    """
    Build the final processed monthly World Bank dataset.

    Steps:
    1. Pull each indicator for each country
    2. Save the annual extract as raw data
    3. Expand annual values to monthly rows
    4. Merge all indicators into one processed monthly table
    """
    indicator_frames: List[pd.DataFrame] = []

    for output_column, indicator_id in INDICATORS.items():
        country_frames: List[pd.DataFrame] = []

        for country_code in COUNTRIES.values():
            annual_df = fetch_indicator_series(
                country=country_code,
                indicator=indicator_id,
                start_year=start_year,
                end_year=end_year,
            )

            if annual_df.empty:
                continue

            monthly_df = expand_annual_to_monthly(annual_df, output_column)
            country_frames.append(monthly_df)

        if country_frames:
            combined = pd.concat(country_frames, ignore_index=True)
            indicator_frames.append(combined)

    if not indicator_frames:
        return pd.DataFrame(
            columns=[
                "country_code",
                "year_month",
                "gdp",
                "inflation",
                "population",
               
            ]
        )

    merged = indicator_frames[0]
    for frame in indicator_frames[1:]:
        merged = merged.merge(frame, on=["country_code", "year_month"], how="outer")

    merged = merged.sort_values(["country_code", "year_month"]).reset_index(drop=True)
   
    return merged


def save_outputs(df: pd.DataFrame) -> None:
    """
    Save the full processed monthly dataset to the processed folder.
    """
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"Saved processed file: {OUTPUT_FILE}")


def load_to_database(df: pd.DataFrame, table_name: str = "worldbank") -> None:
    """
    Optionally load the processed dataframe directly to PostgreSQL.
    In your master pipeline flow, this can be turned off so master.py
    controls the final database rebuild.
    """
    if df.empty:
        print("Skipping database load: DataFrame is empty.")
        return

    engine = get_engine()
    df.to_sql(table_name, engine, if_exists="replace", index=False)
    print(f"Successfully loaded World Bank data into the database table '{table_name}'!")


def run() -> pd.DataFrame:
    """
    Main entry point for the World Bank pipeline.

    Flow:
    1. Resolve extraction year range
    2. Build processed monthly dataset
    3. Save raw and processed outputs to disk
    4. Optionally load processed data to PostgreSQL
    """
    mode = get_pipeline_mode()
    start_year, end_year, reason = resolve_year_range()

    if start_year is None or end_year is None:
        print(f"Starting World Bank Pipeline... mode={mode}")
        print(reason)
        return pd.DataFrame()

    print(f"Starting World Bank Pipeline... mode={mode}, years={start_year}-{end_year}")
    print(f"Range selection: {reason}")

    df = build_world_bank_monthly(start_year=start_year, end_year=end_year)

    if df.empty:
        print(f"No World Bank data extracted for years {start_year}-{end_year}. Exiting without error.")
        return df

    save_outputs(df)

    print(f"\n[WORLD BANK MONTHLY (processed)] rows={len(df)} cols={len(df.columns)}")
    print(f"Countries: {sorted(df['country_code'].dropna().unique().tolist())}")
    print(f"Year_Month range: {df['year_month'].min()} to {df['year_month'].max()}")

    # Standalone runs can still load directly if needed.
    if os.getenv("WORLD_BANK_LOAD_TO_DB", "true").strip().lower() in {"1", "true", "yes", "y"}:
        load_to_database(df)

    return df


if __name__ == "__main__":
    run()