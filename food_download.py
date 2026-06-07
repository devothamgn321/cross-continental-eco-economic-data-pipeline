#!/usr/bin/env python
# coding: utf-8

from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


# Source dataset page for the latest WFP global food prices file
DATASET_URL = "https://data.humdata.org/dataset/global-wfp-food-prices"

# Base project directory
BASE_DIR = Path(__file__).resolve().parent

# Data folder structure
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw" / "food_prices"

# Ensure raw folder exists before writing files
RAW_DIR.mkdir(parents=True, exist_ok=True)

# Output file for the latest raw update download
OUTPUT_FILE = RAW_DIR / "latest_food_prices.csv"


def find_latest_csv_link() -> str:
    """
    Scrape the WFP dataset page and try to find a usable downloadable CSV link.

    The logic:
    1. Load the dataset page HTML
    2. Collect candidate links that look like CSV/download resources
    3. Prefer links that appear to be actual resource/download URLs
    """
    response = requests.get(DATASET_URL, timeout=60)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    candidate_links = []

    for link in soup.find_all("a", href=True):
        href = link["href"]
        href_lower = href.lower()

        # Skip metadata/export links
        if "download_metadata" in href_lower:
            continue

        # Look for actual downloadable CSV resource links
        if ".csv" in href_lower or "download" in href_lower:
            full_url = urljoin(DATASET_URL, href)
            candidate_links.append(full_url)

    # Prefer links that look like actual resource/download links
    for url in candidate_links:
        url_lower = url.lower()
        if "resource" in url_lower or "download" in url_lower:
            return url

    if candidate_links:
        return candidate_links[0]

    raise RuntimeError("Could not find a usable CSV download link on the WFP dataset page.")


def download_latest_food_file() -> Path:
    """
    Download the latest available WFP food prices CSV and save it into the
    raw food_prices folder for later processing.
    """
    csv_url = find_latest_csv_link()
    print(f"Found CSV link: {csv_url}")

    response = requests.get(csv_url, timeout=120)
    response.raise_for_status()

    with open(OUTPUT_FILE, "wb") as f:
        f.write(response.content)

    print(f"Downloaded latest food file to: {OUTPUT_FILE}")
    return OUTPUT_FILE


def run() -> Path:
    """
    Main entry point for the latest food prices download step.

    Flow:
    1. Find the newest downloadable CSV link from the WFP dataset page
    2. Download the raw CSV file
    3. Save it into data/raw/food_prices/latest_food_prices.csv
    """
    print("Starting food download step...")
    return download_latest_food_file()


if __name__ == "__main__":
    run()