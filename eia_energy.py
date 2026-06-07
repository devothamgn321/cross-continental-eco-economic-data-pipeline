#!/usr/bin/env python
# coding: utf-8

import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd
import requests

from config import EIA_API_KEY


# Base project directory
BASE_DIR = Path(__file__).resolve().parent

# Data folder structure
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw" / "energy"
PROCESSED_DIR = DATA_DIR / "processed" / "energy"

# Ensure raw/processed folders exist before writing files
RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

COUNTRIES = ["USA", "BRA", "IND", "PHL", "NGA"]

PRODUCTS = [
    {"product_id": "79", "activity_id": "1", "name": "electricity_production"},
    {"product_id": "79", "activity_id": "2", "name": "electricity_consumption"},
    {"product_id": "12", "activity_id": "1", "name": "petroleum_production"},
    {"product_id": "12", "activity_id": "2", "name": "petroleum_consumption"},
    {"product_id": "26", "activity_id": "1", "name": "natural_gas_production"},
    {"product_id": "26", "activity_id": "2", "name": "natural_gas_consumption"},
]


def get_pipeline_mode() -> str:
    """
    Read pipeline mode from environment.
    Expected values:
    - backfill
    - incremental
    """
    return os.getenv("PIPELINE_MODE", "backfill").strip().lower()


def world_safe_latest_year() -> int:
    """
    Conservative latest year for annual EIA international data.
    Uses the prior year to avoid assuming the current year is fully available.
    """
    return datetime.now().year - 1


def get_year_range() -> Tuple[int, int]:
    """
    Determine the year range for extraction.

    backfill:
    - 2022 through the latest safely available full year

    incremental:
    - latest safely available full year only
    """
    mode = get_pipeline_mode()
    latest_year = world_safe_latest_year()

    if mode == "incremental":
        return latest_year, latest_year

    return 2022, latest_year


def fetch_eia_annual(country_code: str, product_id: str, activity_id: str) -> pd.DataFrame:
    """
    Fetch annual EIA international energy data for one country/product/activity
    combination over the selected year range.

    This function also saves the raw annual extract to the raw folder so the
    original API pull is preserved before monthly transformation.
    """
    url = "https://api.eia.gov/v2/international/data/"
    start_year, end_year = get_year_range()

    params = {
        "api_key": EIA_API_KEY,
        "frequency": "annual",
        "data[0]": "value",
        "facets[countryRegionId][]": country_code,
        "facets[productId][]": product_id,
        "facets[activityId][]": activity_id,
        "start": str(start_year),
        "end": str(end_year),
        "length": 5000,
    }

    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        records = data.get("response", {}).get("data", [])

        if records:
            raw_df = pd.DataFrame(records)

            # Save raw annual API extract for auditing/debugging
            raw_path = RAW_DIR / f"{country_code}_{product_id}_{activity_id}_raw.csv"
            raw_df.to_csv(raw_path, index=False)
            print(f"Saved raw file: {raw_path}")

            return raw_df

    except Exception as e:
        print(f"Error fetching {country_code} ({product_id}, {activity_id}): {e}")

    return pd.DataFrame()


def interpolate_to_monthly(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert annual values to monthly values by dividing each annual total
    equally across all 12 months of the year.
    """
    rows = []

    for _, row in df.iterrows():
        try:
            year = int(row["period"])
            annual_value = float(row.get("value"))
        except (ValueError, TypeError):
            continue

        if pd.isna(annual_value):
            continue

        monthly_value = annual_value / 12

        for month in range(1, 13):
            rows.append(
                {
                    "year": year,
                    "month": month,
                    "value": round(monthly_value, 4),
                    "unit": row.get("unit", ""),
                }
            )

    return pd.DataFrame(rows)


def run() -> Optional[pd.DataFrame]:
    """
    Main entry point for the EIA energy pipeline.

    Flow:
    1. Determine year range based on pipeline mode
    2. Fetch raw annual data for each country/product/activity combination
    3. Save raw extracts to disk
    4. Convert annual data to monthly values
    5. Pivot to the final processed table shape
    6. Save processed output to the processed folder
    """
    if not EIA_API_KEY:
        raise ValueError(
            "Missing EIA_API_KEY. Add it to your .env file before running the pipeline."
        )

    start_year, end_year = get_year_range()
    mode = get_pipeline_mode()

    print(f"Fetching EIA energy data... mode={mode}, years={start_year}-{end_year}")
    all_data: List[pd.DataFrame] = []

    for country_code in COUNTRIES:
        for product in PRODUCTS:
            df_annual = fetch_eia_annual(
                country_code,
                product["product_id"],
                product["activity_id"],
            )

            if df_annual.empty:
                continue

            df_monthly = interpolate_to_monthly(df_annual)

            if df_monthly.empty:
                continue

            df_monthly["Country_Code"] = country_code
            df_monthly["metric"] = product["name"]
            all_data.append(df_monthly)

    if not all_data:
        print("No data retrieved.")
        return None

    energy_df = pd.concat(all_data, ignore_index=True)

    energy_df["Year_Month"] = (
        energy_df["year"].astype(str) + "-" + energy_df["month"].astype(str).str.zfill(2)
    )

    energy_pivot = energy_df.pivot_table(
        index=["Country_Code", "Year_Month"],
        columns="metric",
        values="value",
        aggfunc="first",
    ).reset_index()

    energy_pivot.columns.name = None

    output_path = PROCESSED_DIR / "energy.csv"
    energy_pivot.to_csv(output_path, index=False)
    print(f"Saved processed file: {output_path} {energy_pivot.shape}")

    return energy_pivot


if __name__ == "__main__":
    run()