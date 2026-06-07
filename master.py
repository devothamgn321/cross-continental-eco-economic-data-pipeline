#!/usr/bin/env python
# coding: utf-8

from pathlib import Path
from datetime import datetime

import pandas as pd
from sqlalchemy import create_engine, text

import food_download
import world_bank
import food_prices
import eia_energy
import weather

from config import DB_CONFIG


# Base project directory
BASE_DIR = Path(__file__).resolve().parent

# Shared processed data folder used by the individual pipeline scripts
DATA_DIR = BASE_DIR / "data"
PROCESSED_DIR = DATA_DIR / "processed"

# Country dimension used across the project
COUNTRIES = {
    "USA": "United States",
    "BRA": "Brazil",
    "IND": "India",
    "PHL": "Philippines",
    "NGA": "Nigeria",
}


def get_database_engine():
    """
    Create and return the SQLAlchemy engine used by master.py.

    This engine is used to:
    1. drop any existing project tables
    2. load the processed CSV files into PostgreSQL
    3. create the merged master_data table
    4. add database constraints after the tables are created
    """
    connection_string = (
        f"postgresql+psycopg2://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
        f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
    )
    return create_engine(connection_string)


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize dataframe column names before loading them into PostgreSQL.

    This keeps naming consistent across all pipeline outputs by:
    - trimming whitespace
    - converting names to lowercase

    This is especially useful because some source scripts still output
    mixed-case column names.
    """
    df = df.copy()
    df.columns = [str(col).strip().lower() for col in df.columns]
    return df


def run_pipelines() -> None:
    """
    Run each individual source pipeline before loading the processed outputs
    into PostgreSQL.

    Current flow:
    1. Download the latest food update raw file
    2. Run the World Bank pipeline
    3. Process food prices into the final food_prices.csv file
    4. Run the EIA energy pipeline
    5. Run the weather pipeline

    Note:
    - food_backfill.py is not called here because that is a historical
      one-time setup step rather than a normal recurring pipeline step.
    - World Bank direct DB loading is temporarily disabled here so master.py
      controls the final table rebuild.
    """
    print("Running individual pipelines...")
    print("-" * 40)

    print("Starting food download...")
    food_download.run()
    print("-" * 40)

    print("Starting World Bank pipeline...")
    # Let master own the final database rebuild.
    original_flag = world_bank.os.getenv("WORLD_BANK_LOAD_TO_DB")
    world_bank.os.environ["WORLD_BANK_LOAD_TO_DB"] = "false"
    world_bank.run()
    if original_flag is None:
        del world_bank.os.environ["WORLD_BANK_LOAD_TO_DB"]
    else:
        world_bank.os.environ["WORLD_BANK_LOAD_TO_DB"] = original_flag
    print("-" * 40)

    print("Starting food prices ingestion...")
    food_prices.run()
    print("-" * 40)

    print("Starting energy pipeline...")
    eia_energy.run()
    print("-" * 40)

    print("Starting weather pipeline...")
    weather.run()
    print("-" * 40)

    print("All pipelines complete.")


def drop_existing_tables(engine) -> None:
    """
    Drop existing project tables before rebuilding them.

    This ensures that each master pipeline run starts from a clean database
    state and avoids old schema/data conflicts.
    """
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS master_data CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS worldbank CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS food_prices CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS energy CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS weather CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS countries CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS datedim CASCADE"))
        print("Dropped existing tables if they existed.")


def create_countries_table(engine) -> pd.DataFrame:
    """
    Create the countries dimension table used by the project.

    This table stores the project country codes and readable country names
    and serves as the parent table for foreign key relationships.
    """
    df_countries = pd.DataFrame(
        [{"country_code": code, "country_name": name} for code, name in COUNTRIES.items()]
    )
    df_countries.to_sql("countries", con=engine, if_exists="replace", index=False)
    print(f"Created table 'countries': {df_countries.shape}")
    return df_countries


def create_date_dimension(engine) -> None:
    """
    Create the datedim table for monthly time analysis.

    This dimension starts at 2022-01 and extends out 10 years beyond the
    current year so the project has a reusable monthly calendar table with:
    - year_month
    - numeric year
    - numeric month
    - month name
    - quarter
    """
    print("Creating datedim table...")
    current_year = datetime.now().year
    dates = pd.date_range(start="2022-01-01", end=f"{current_year + 10}-12-01", freq="MS")
    df_date = pd.DataFrame({"date": dates})

    df_date["year_month"] = df_date["date"].dt.strftime("%Y-%m")
    df_date["year_int"] = df_date["date"].dt.year
    df_date["month_int"] = df_date["date"].dt.month
    df_date["month_name"] = df_date["date"].dt.month_name()
    df_date["quarter"] = "Q" + df_date["date"].dt.quarter.astype(str)

    df_date = df_date.drop(columns=["date"])
    df_date.to_sql("datedim", con=engine, if_exists="replace", index=False)
    print(f"Created table 'datedim' extending to {current_year + 10}.")


def load_csv_table(engine, file_path: Path, table_name: str) -> pd.DataFrame:
    """
    Read one processed CSV file, standardize its column names, load it into
    PostgreSQL, and return the dataframe.

    This function is used for each processed source table before the final
    master merge is built.
    """
    df = pd.read_csv(file_path)
    df = standardize_columns(df)
    df.to_sql(table_name, con=engine, if_exists="replace", index=False)
    print(f"Created table '{table_name}': {df.shape}")
    return df


def load_individual_tables(engine) -> dict:
    """
    Load each processed pipeline output file from the processed data folders
    and create PostgreSQL tables from them.

    Expected processed inputs:
    - world_bank/world_bank_monthly.csv
    - food_prices/food_prices.csv
    - energy/energy.csv
    - weather/weather.csv

    The loaded dataframes are returned in a dictionary so they can be merged
    into the final master table.
    """
    dataframes = {}

    dataframes["worldbank"] = load_csv_table(
        engine,
        PROCESSED_DIR / "world_bank" / "world_bank_monthly.csv",
        "worldbank",
    )

    dataframes["food_prices"] = load_csv_table(
        engine,
        PROCESSED_DIR / "food_prices" / "food_prices.csv",
        "food_prices",
    )

    dataframes["energy"] = load_csv_table(
        engine,
        PROCESSED_DIR / "energy" / "energy.csv",
        "energy",
    )

    weather_path = PROCESSED_DIR / "weather" / "weather.csv"
    if weather_path.exists():
        dataframes["weather"] = load_csv_table(engine, weather_path, "weather")
    else:
        print("weather.csv not found. Skipping weather table.")

    return dataframes


def create_master_table(engine, dataframes: dict) -> pd.DataFrame:
    """
    Merge the individual source tables into the final master_data table.

    Merge logic:
    - start with World Bank as the base dataframe
    - outer join food prices on country_code + year_month
    - outer join energy on country_code + year_month
    - outer join weather on country_code + year_month

    Outer joins are used so missing source coverage for a country/month does
    not drop otherwise valid rows from the final master dataset.
    """
    df_master = dataframes["worldbank"].copy()

    if "food_prices" in dataframes:
        df_master = pd.merge(
            df_master,
            dataframes["food_prices"],
            on=["country_code", "year_month"],
            how="outer",
        )

    if "energy" in dataframes:
        df_master = pd.merge(
            df_master,
            dataframes["energy"],
            on=["country_code", "year_month"],
            how="outer",
        )

    if "weather" in dataframes:
        df_master = pd.merge(
            df_master,
            dataframes["weather"],
            on=["country_code", "year_month"],
            how="outer",
        )

    df_master = df_master.sort_values(["country_code", "year_month"]).reset_index(drop=True)
    df_master.to_sql("master_data", con=engine, if_exists="replace", index=False)
    print(f"Created table 'master_data': {df_master.shape}")

    return df_master


def add_key_constraints(engine, include_weather: bool = False) -> None:
    """
    Add primary key and foreign key constraints after the project tables
    have been loaded.

    Keys added:
    - countries.country_code as primary key
    - source tables use (country_code, year_month) as composite primary keys
    - source tables reference countries(country_code)
    - master_data uses (country_code, year_month) as composite primary key
    """
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE countries ADD PRIMARY KEY (country_code)"))
        print("Added primary key to 'countries'")

        conn.execute(text("ALTER TABLE worldbank ADD PRIMARY KEY (country_code, year_month)"))
        conn.execute(text("ALTER TABLE worldbank ADD FOREIGN KEY (country_code) REFERENCES countries(country_code)"))
        print("Added primary key and foreign key to 'worldbank'")

        conn.execute(text("ALTER TABLE food_prices ADD PRIMARY KEY (country_code, year_month)"))
        conn.execute(text("ALTER TABLE food_prices ADD FOREIGN KEY (country_code) REFERENCES countries(country_code)"))
        print("Added primary key and foreign key to 'food_prices'")

        conn.execute(text("ALTER TABLE energy ADD PRIMARY KEY (country_code, year_month)"))
        conn.execute(text("ALTER TABLE energy ADD FOREIGN KEY (country_code) REFERENCES countries(country_code)"))
        print("Added primary key and foreign key to 'energy'")

        if include_weather:
            conn.execute(text("ALTER TABLE weather ADD PRIMARY KEY (country_code, year_month)"))
            conn.execute(text("ALTER TABLE weather ADD FOREIGN KEY (country_code) REFERENCES countries(country_code)"))
            print("Added primary key and foreign key to 'weather'")

        conn.execute(text("ALTER TABLE master_data ADD PRIMARY KEY (country_code, year_month)"))
        conn.execute(text("ALTER TABLE master_data ADD FOREIGN KEY (country_code) REFERENCES countries(country_code)"))
        print("Added primary key and foreign key to 'master_data'")

        print("-" * 40)
        print("All primary and foreign keys added successfully.")


def run() -> None:
    """
    Main entry point for the master pipeline.

    Flow:
    1. Run the individual source pipelines
    2. Connect to PostgreSQL
    3. Drop existing project tables
    4. Create supporting dimension tables
    5. Load processed source CSVs into PostgreSQL
    6. Merge the source tables into master_data
    7. Add primary and foreign key constraints
    """
    print("=" * 50)
    print("MASTER PIPELINE")
    print("=" * 50)

    run_pipelines()

    print("\nLoading to PostgreSQL...")
    print("-" * 40)

    try:
        engine = get_database_engine()

        drop_existing_tables(engine)
        create_countries_table(engine)
        create_date_dimension(engine)
        dataframes = load_individual_tables(engine)
        create_master_table(engine, dataframes)

        print("\nAdding database primary and foreign keys...")
        print("-" * 40)
        add_key_constraints(engine, include_weather=("weather" in dataframes))

        print("-" * 40)
        print("All tables created successfully.")

    except Exception as e:
        print(f"Database error: {e}")
        print("Make sure PostgreSQL is running and your .env settings are correct.")
        raise

    print("=" * 50)
    print("PIPELINE COMPLETE")
    print("=" * 50)


if __name__ == "__main__":
    run()