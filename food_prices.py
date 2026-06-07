#!/usr/bin/env python
# coding: utf-8

from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine

from config import DB_CONFIG


# Base project directory
BASE_DIR = Path(__file__).resolve().parent

# Data folder structure
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw" / "food_prices"
PROCESSED_DIR = DATA_DIR / "processed" / "food_prices"

# Ensure processed folder exists before writing files
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# Raw input files
INPUT_FILE = RAW_DIR / "wfp_food_prices_master_2022_2025.csv"
LATEST_FILE = RAW_DIR / "latest_food_prices.csv"

# Final processed output file
OUTPUT_FILE = PROCESSED_DIR / "food_prices.csv"


def get_engine():
    """
    Create and return a SQLAlchemy engine using the shared DB config.
    This is used when loading the processed food prices table to PostgreSQL.
    """
    engine_url = (
        f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
        f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
    )
    return create_engine(engine_url)


def run():
    """
    Main entry point for the food prices pipeline.

    Flow:
    1. Read the historical raw master file created by food_backfill.py
    2. Read the latest raw update file if it exists
    3. Merge historical and latest raw data
    4. Filter to the target countries and retail prices
    5. Classify commodity rows into rice, maize, or wheat using partial matching
    6. Aggregate monthly average prices
    7. Pivot into the final processed table shape
    8. Save the processed file and load it to PostgreSQL
    """
    print("Starting Food Prices Pipeline...")

    try:
        df_base = pd.read_csv(INPUT_FILE)
        print(f"Successfully loaded the master WFP file: {INPUT_FILE.name}")
    except Exception as e:
        print(f"Error reading the master CSV file: {e}")
        raise

    if LATEST_FILE.exists():
        try:
            df_latest = pd.read_csv(LATEST_FILE)
            print(f"Successfully loaded latest downloaded food file: {LATEST_FILE.name}")
            df = pd.concat([df_base, df_latest], ignore_index=True).drop_duplicates()
            print("Merged historical and latest food data.")
        except Exception as e:
            print(f"Error reading latest downloaded food file: {e}")
            raise
    else:
        df = df_base
        print("No latest_food_prices.csv found. Using base file only.")

    # Keep only the target countries required for the project.
    # Including USA and BRA is safe even if the raw WFP data has no matching rows for them.
    target_countries = ["USA", "BRA", "IND", "PHL", "NGA"]

    df_filtered = df[
        (df["pricetype"] == "Retail")
        & (df["countryiso3"].isin(target_countries))
    ].copy()

    # Use partial matching so the pipeline captures commodity variants
    # such as "Rice (local)", "Rice (imported)", "Maize flour", etc.
    df_filtered["crop_type"] = None
    df_filtered.loc[
        df_filtered["commodity"].str.contains("Rice", case=False, na=False),
        "crop_type",
    ] = "Rice"
    df_filtered.loc[
        df_filtered["commodity"].str.contains("Maize", case=False, na=False),
        "crop_type",
    ] = "Maize"
    df_filtered.loc[
        df_filtered["commodity"].str.contains("Wheat", case=False, na=False),
        "crop_type",
    ] = "Wheat"

    # Keep only rows that matched one of the target crop groups
    df_filtered = df_filtered[df_filtered["crop_type"].notna()].copy()

    # Build a year-month key for joining with the other project datasets
    df_filtered["year_month"] = pd.to_datetime(df_filtered["date"]).dt.strftime("%Y-%m")
    df_filtered.rename(columns={"countryiso3": "country_code"}, inplace=True)

    # Average prices at the country / month / crop group level
    df_grouped = (
        df_filtered.groupby(["country_code", "year_month", "crop_type"], as_index=False)["usdprice"]
        .mean()
    )

    # Pivot crop group rows into separate processed columns
    df_clean = (
        df_grouped.pivot(
            index=["country_code", "year_month"],
            columns="crop_type",
            values="usdprice",
        )
        .reset_index()
    )

    df_clean.columns.name = None

    # Rename columns to clear final metric names
    df_clean.rename(
        columns={
            "Maize": "maize_price_usd_per_kg",
            "Rice": "rice_price_usd_per_kg",
            "Wheat": "wheat_price_usd_per_kg",
        },
        inplace=True,
    )

    # Sort final processed output for cleaner inspection and downstream loading
    df_clean = df_clean.sort_values(["country_code", "year_month"]).reset_index(drop=True)

    # Save processed output to the processed folder
    df_clean.to_csv(OUTPUT_FILE, index=False)
    print(f"Saved processed file: {OUTPUT_FILE.name}")

    try:
        engine = get_engine()
        df_clean.to_sql("food_prices", engine, if_exists="replace", index=False)
        print("Successfully loaded food prices into the database table 'food_prices'!")
    except Exception as e:
        print(f"Error loading to database: {e}")
        raise

    return df_clean


if __name__ == "__main__":
    run()