# Cross-Continental Eco-Economic Data Pipeline

## Overview

This project is an end-to-end automated data engineering platform that integrates environmental and economic datasets from multiple global sources into a centralized PostgreSQL data warehouse.

The platform collects, transforms, standardizes, and serves data through a REST API, enabling cross-country analysis of weather, food prices, energy production/consumption, and macroeconomic indicators.

Target countries include:
* United States
* Brazil
* India
* Philippines
* Nigeria

The system is fully containerized using Docker and supports automated refreshes through scheduled cron-based workflows.

---

## Key Features

### Automated Data Ingestion
* World Bank Open Data API
* U.S. Energy Information Administration (EIA) API
* Open-Meteo Weather API
* World Food Programme (WFP) Food Price Dataset

### Data Engineering Pipeline
* Historical backfill support
* Incremental update processing
* Data standardization using `country_code` and `year_month`
* Deduplication and validation checks
* Automated ETL orchestration

### Backend Services
* Flask REST API
* PostgreSQL data warehouse
* JSON-based analytical endpoints

### Infrastructure & Automation
* Dockerized deployment
* Docker Compose orchestration
* Cron-based scheduled refreshes
* Environment-based configuration management


## Project Structure
* `config.py` — shared configuration
* `.env.example` — environment template
* `requirements.txt` — Python dependencies
* `Dockerfile` — app container definition
* `docker-compose.yml` — multi-container setup
* `start.sh` — Docker startup script for backfill and API launch
* `start_with_cron.sh` — Docker startup script for backfill, cron, and API launch
* `run_incremental.sh` — incremental refresh runner
* `master.py` — main orchestration script for full backfill
* `world_bank.py` — World Bank ingestion and transformation
* `eia_energy.py` — EIA energy ingestion
* `weather.py` — weather ingestion
* `food_download.py` — downloads the latest WFP food prices file
* `food_backfill.py` — builds the historical food prices backfill file
* `food_prices.py` — merges historical and latest WFP food data
* `app.py` — Flask API
* `api_smoke_test.py` — simple API smoke test script
* `api_check.ipynb` — notebook for API checks and validation
* `data/raw/` — raw source extracts
* `data/processed/` — processed source outputs


## Data Sources
1. World Bank API — macroeconomic indicators  
2. EIA API — energy data  
3. WFP Dataset via HDX — food prices  
4. Open-Meteo API — weather data  

## Warehouse Join Keys
- `country_code`
- `year_month`

## Execution Modes

### Backfill mode
Backfill mode performs a full historical warehouse build from scratch. This is the default startup path and is used for clean initialization.

### Incremental mode
Incremental mode supports scheduled or manual refreshes by pulling only the newest available source data window or latest available period, depending on the source.

## Requirements

### For Docker run
Install:
- Docker Desktop

### For local Python run
Install:
- Python 3.9 or newer
- PostgreSQL
- pip

## Environment Configuration

This project requires an API key for the U.S. Energy Information Administration API.

### EIA API key setup

Register for a free API key at:
[https://www.eia.gov/opendata/](https://www.eia.gov/opendata/)

After you receive the key, create a `.env` file in the project root.

### Option 1: copy from template

cp .env.example .env

Then open the `.env` file and replace the placeholder value with your EIA API key.

Example:

EIA_API_KEY=your_actual_api_key_here

## Setup and Run

From the project root, build and start the containers with:

docker compose up --build



 
 
 








