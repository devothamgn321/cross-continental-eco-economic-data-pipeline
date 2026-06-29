# Cross-Continental Eco-Economic Data Pipeline

**Platform Product Case Study — Analyst-Facing Eco-Economic Intelligence Platform**

This is a data platform product, not just an engineering project. The design question isn't "how do we move data?" — it's "what does a policy analyst or researcher need to understand the relationship between climate, energy, food prices, and macroeconomic indicators, and how do we build infrastructure that makes that possible?"

---

## The Problem

Climate anomalies and energy resource shifts have direct, rapid impacts on food security and macroeconomic indicators — but the data to understand those ripple effects is scattered across government APIs, NGO databases, and financial data providers.

**Fragmented data sources.** A researcher studying drought impact on food prices needs to pull weather data, World Bank economic indicators, EIA energy production figures, and commodity price feeds — from multiple APIs with different authentication methods.

**No unified temporal alignment.** Weather readings, monthly commodity prices, and annual economic indicators are timestamped differently.

**No reusable infrastructure.** Each research question requires rebuilding the same data plumbing from scratch.

**Result:** analysts spend 60-70% of their time on data acquisition — leaving little time for the analysis that drives decisions.

---

## Target Users

| Persona | Core Need | Pain |
|---|---|---|
| Policy Analyst | Cross-domain queries across weather, energy, food | Manually joining 4+ datasets |
| NGO Research Lead | Reproducible data without engineering support | Rebuilds ETL every project |
| Academic Researcher | Clean, citable data across geographies | Raw API access is inconsistent |
| Supply-Chain Risk Officer | Multi-country economic + weather time series | No unified tool exists |

---

## Data Sources & Countries

**5 Countries:** USA, Brazil, India, Philippines, Nigeria

**4 Data Sources:**
- Open-Meteo API: Monthly weather per country capital (weather.py)
- World Bank API: GDP, inflation, economic indicators (world_bank.py)
- EIA: Energy production and consumption (eia_energy.py)
- FAO / Food Price Feeds: Commodity price indices (food_prices.py, food_download.py)

---

## Core Product Features

### 1. Modular Source Connectors
Each source is an isolated Python module. Each handles its own auth, pagination, error recovery, and output format independently.

**PM decision:** Modular connectors over monolithic ETL. A researcher adding a new source shouldn't touch existing pipelines.

### 2. Normalization & Temporal Alignment
Resolves schema mismatches, aligns time series to monthly grain, handles missing data with documented imputation rules. Output written to data/processed/ per source before merging.

**PM decision:** Every data quality decision is traceable — data lineage is a product feature, not an afterthought.

### 3. PostgreSQL Warehouse (Star Schema)
master.py loads processed CSVs into PostgreSQL, creates a merged master_data table, adds constraints. Schema optimized for analytical queries, not ingestion convenience.

**PM decision:** Rejected flat table approach. Query performance matters — an analyst waiting 40 seconds abandons the tool.

### 4. Flask REST API
app.py exposes pre-joined, filterable endpoints. Analysts query by country, date range, indicator type — no SQL needed.

**PM decision:** API design started from analyst questions, not data structure. No analyst should need to write a JOIN.

### 5. Automated Orchestration (Cron + Docker)
start_with_cron.sh runs scheduled ingestion. run_incremental.sh handles delta updates. Docker Compose packages the full stack.

**PM decision:** Reproducibility is a trust feature. If an analyst can't reproduce a result from 6 months ago, the platform is unreliable.

---

## Product Strategy & PM Thinking

**Core insight:** The bottleneck is not analysis capability — it's data access. Analysts can derive insights if they have clean, aligned, cross-domain data. This product eliminates the 60-70% of time spent on wrangling.

**Scope:** 5 countries chosen for data availability across all 4 sources. Expanding scope before the core pipeline is reliable creates compounding quality problems.

**Deferred:** Real-time ingestion, UI/dashboard layer, predictive modeling — all out of scope until data quality is validated.

### Metrics

| Metric | Target |
|---|---|
| Data Freshness | <= 30 days lag |
| Schema Coverage | > 90% of source fields mapped |
| Query Response Time | < 2 seconds |
| Imputation Rate | < 10% of values |
| API Uptime | > 99% |

### Risks & Tradeoffs

| Risk | Mitigation |
|---|---|
| API source changes schema | Connectors are isolated; each fails independently |
| Data quality varies by country | Coverage metadata exposed via API |
| Temporal misalignment | Per-source normalization, audit trail |
| Scope creep | Modular design; new sources don't touch existing |

---

## Roadmap

| Phase | Features | Milestone |
|---|---|---|
| MVP (Done) | 4-source ingestion, normalization, PostgreSQL, Flask API, Docker, cron | Working platform across 5 countries |
| Phase 2 | Airflow orchestration, data quality scoring, 20-country coverage | Research-grade reliability |
| Phase 3 | Lightweight analyst query UI, UN OCHA / WFP integrations | Platform-grade product |
| Phase 4 | Predictive module: weather + energy -> food price forecasting | Policy intelligence product |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Ingestion | Python (requests, pandas, beautifulsoup4) |
| Normalization | Python (per-source transformation pipeline) |
| Warehouse | PostgreSQL via SQLAlchemy |
| API Layer | Flask |
| Orchestration | Cron (cronjob, start_with_cron.sh) |
| Containerization | Docker + Docker Compose |
| Smoke Testing | api_smoke_test.py, api_check.ipynb |

---

## Repository Structure

cross-continental-eco-economic-data-pipeline/
- weather.py           Open-Meteo ingestion (5 countries, monthly)
- world_bank.py        World Bank GDP + inflation connector
- eia_energy.py        EIA energy production connector
- food_prices.py       Food price index connector
- food_download.py     Food data download helper
- food_backfill.py     Historical food price backfill
- master.py            Orchestrator: load CSVs -> PostgreSQL -> master_data
- app.py               Flask REST API
- config.py            DB config + API base URLs
- api_smoke_test.py    API endpoint smoke tests
- api_check.ipynb      Interactive API validation notebook
- run_incremental.sh   Incremental update script
- start_with_cron.sh   Cron-scheduled ingestion
- docker-compose.yml   Full-stack container orchestration
- PRODUCT_SPEC.md      Full product specification

---

## Run Locally

git clone https://github.com/devothamgn321/cross-continental-eco-economic-data-pipeline.git
cd cross-continental-eco-economic-data-pipeline
cp env.example .env
docker-compose up --build

Or without Docker:
pip install -r requirements.txt
python master.py
python app.py

---

## About

**Devothama GN**
AI Product Manager | Platform Products | MS Engineering Management @ Johns Hopkins
Ex-Mercedes-Benz ADAS | TEDxJHU Speaker

[Portfolio](https://devothamagn.netlify.app) · [LinkedIn](https://linkedin.com/in/devothamagn) · [GitHub](https://github.com/devothamgn321)

---

*Positioned as an analyst-facing data platform product — demonstrating product thinking applied to data infrastructure: starting from user needs, designing for the query not the schema, and building for reproducibility and trust.*
