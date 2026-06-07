#!/usr/bin/env python
# coding: utf-8

from pathlib import Path
from typing import List

import pandas as pd
import requests


# Base project directory
BASE_DIR = Path(__file__).resolve().parent

# Data folder structure
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw" / "food_prices"

# Ensure raw folder exists before writing files
RAW_DIR.mkdir(parents=True, exist_ok=True)

# Historical yearly backfill file URLs
BACKFILL_FILES = {
    "2022": "https://data.humdata.org/dataset/31579af5-3895-4002-9ee3-c50857480785/resource/747fe8d0-83e7-4da7-a40e-3afdd11832c9/download/wfp_food_prices_global_2022.csv",
    "2023": "https://data.humdata.org/dataset/31579af5-3895-4002-9ee3-c50857480785/resource/e96b8f67-c4de-4173-a814-2f7d84c47475/download/wfp_food_prices_global_2023.csv",
    "2024": "https://data.humdata.org/dataset/31579af5-3895-4002-9ee3-c50857480785/resource/5867679b-7ef4-4117-84b8-2bb4ddd7817f/download/wfp_food_prices_global_2024.csv",
    "2025": "https://data.humdata.org/dataset/31579af5-3895-4002-9ee3-c50857480785/resource/d62af4be-cff6-437b-89a3-67f8fa4c53bf/download/wfp_food_prices_global_2025.csv",
}

# Final merged historical raw file
MASTER_FILE = RAW_DIR / "wfp_food_prices_master_2022_2025.csv"


def download_file(url: str, output_path: Path) -> Path:
    """
    Download one yearly WFP food prices CSV and save it to the raw folder.
    """
    response = requests.get(url, timeout=120)
    response.raise_for_status()

    with open(output_path, "wb") as f:
        f.write(response.content)

    print(f"Downloaded: {output_path}")
    return output_path


def download_backfill_files() -> List[Path]:
    """
    Download each yearly backfill CSV (2022 through 2025) into the raw folder.
    Returns a list of downloaded file paths.
    """
    downloaded_files: List[Path] = []

    for year, url in BACKFILL_FILES.items():
        output_path = RAW_DIR / f"wfp_food_prices_global_{year}.csv"
        download_file(url, output_path)
        downloaded_files.append(output_path)

    return downloaded_files


def combine_backfill_files(file_paths: List[Path]) -> pd.DataFrame:
    """
    Read all downloaded yearly CSVs, concatenate them into one historical
    raw dataframe, remove exact duplicate rows, and save the merged file.
    """
    frames = []

    for file_path in file_paths:
        df = pd.read_csv(file_path)
        print(f"Loaded: {file_path.name} {df.shape}")
        frames.append(df)

    combined_df = pd.concat(frames, ignore_index=True).drop_duplicates()
    combined_df.to_csv(MASTER_FILE, index=False)

    print(f"Saved merged historical raw file: {MASTER_FILE}")
    print(f"Merged shape: {combined_df.shape}")

    return combined_df


def run() -> pd.DataFrame:
    """
    Main entry point for the food prices historical backfill step.

    Flow:
    1. Download yearly raw WFP food price files for 2022 through 2025
    2. Save them individually in the raw folder
    3. Combine them into one historical master raw file
    """
    print("Starting food prices backfill download...")
    downloaded_files = download_backfill_files()

    print("-" * 40)
    print("Combining yearly backfill files...")
    combined_df = combine_backfill_files(downloaded_files)

    print("-" * 40)
    print("Food prices historical backfill complete.")

    return combined_df


if __name__ == "__main__":
    run()