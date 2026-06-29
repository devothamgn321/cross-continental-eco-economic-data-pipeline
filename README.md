# Cross-Continental Eco-Economic Data Pipeline

**Platform Product Case Study — Analyst-Facing Eco-Economic Intelligence Platform**

This project is a **data platform product**, not just an engineering project. The design question is not "how do we move data?" — it is "what does an analyst need to understand the relationship between climate disasters and commodity markets, and how do we build infrastructure that makes that possible?"

---

## The Problem

Climate disasters do not stay in the atmosphere. They ripple into food prices, commodity markets, and macroeconomic indicators — but the data to understand those effects is scattered across government APIs, NGO databases, financial data providers, and academic repositories, each with different schemas, update frequencies, and access patterns.

**Fragmented data sources.** An analyst studying drought impact on wheat prices needs to pull FEWS NET disaster data, World Bank commodity feeds, FAO agricultural statistics, and country-level economic indicators — from 4 different APIs with 4 different authentication methods and response formats.

**No unified temporal alignment.** Disaster events are timestamped differently from commodity price updates. Monthly agricultural reports do not align with weekly market data. Analysts spend more time wrangling timestamps than deriving insights.

**No reusable infrastructure.** Each research question requires rebuilding the same data plumbing from scratch. There is no shared platform where analysts can query across domains without writing custom ETL.

**The result:** policy analysts, researchers, and NGO teams spend 60-70% of their time on data acquisition and cleaning — leaving little time for the analysis that drives decisions.

---

## Target Users

| Persona | Role | Core Need | Pain |
|---|---|---|---|
| **Policy Analyst** | Advises on food security, climate response, trade policy | Cross-domain queries: "How did the 2022 Pakistan floods affect global wheat prices?" | No unified source; manually joining 4+ datasets |
| **NGO Research Lead** | Designs aid programs, tracks commodity volatility | Reproducible, up-to-date data without engineering support | Rebuilds ETL scripts every project cycle |
| **Academic Researcher** | Studies climate-economic correlations | Clean, structured, citable data across geographies | Raw API access is inconsistent; data quality varies |
| **Data Journalist** | Reports on climate impact on food systems | Fast access to multi-country time series | No tool exists at the intersection of climate and economics |

---

## The Product Solution

A unified eco-economic data warehouse that ingests, normalizes, and exposes multi-source data through a clean Flask API — so analysts can query cross-domain questions without touching raw APIs or writing ETL scripts.

**The product decision:** Build for the analyst, not the data engineer. The API response schema is designed around the analytical question ("what happened to maize prices in Kenya in the 6 months after a major drought?"), not around the source system schema.

**What It Does:**
- Ingests climate disaster events, commodity prices, and macroeconomic indicators from 4 heterogeneous APIs across 5 countries
- Normalizes schemas, aligns temporal granularity, and resolves geographic identifiers into a consistent PostgreSQL warehouse
- Exposes a clean REST API with analyst-facing endpoints that return pre-joined, analysis-ready datasets
- Containerizes the full stack with Docker for reproducibility

---

## Core Product Features

### 1. Multi-Source Ingestion Layer
Pulls from 4 APIs: FEWS NET (disaster/food security events), World Bank (commodity price indices), FAO (agricultural production data), and country-level economic databases. Each connector handles authentication, rate limiting, pagination, and error recovery independently.

**PM decision:** Designed each source connector as an isolated module, not a monolithic ETL script. This lets analysts add new data sources without touching existing pipelines — critical for a research platform where the data universe keeps expanding.

### 2. Normalization and Temporal Alignment Engine
Resolves schema mismatches (e.g., "ZWE" vs "Zimbabwe" vs "ZIM" for geographic identifiers), aligns time series to a consistent monthly grain, and handles missing data with documented imputation rules rather than silent drops.

**PM decision:** Every imputation decision is logged in the data warehouse as metadata. An analyst querying the API can see "this value was interpolated because the source reported quarterly" — data lineage is a product feature, not an afterthought.

### 3. PostgreSQL Warehouse with Analyst-Oriented Schema
Structured as a star schema optimized for time-series analytical queries: fact tables for events and prices, dimension tables for countries, commodities, and disaster types. Indexes designed around the queries analysts actually run, not around ingestion convenience.

**PM decision:** Rejected a flat "dump everything into one table" approach because query performance at analytical scale matters. An analyst waiting 40 seconds for a query abandons the tool. Schema design is a product quality decision.

### 4. Flask REST API (Analyst-Facing)
Exposes pre-joined, analysis-ready endpoints. Example: GET /api/impact?country=KEN&disaster_type=drought&commodity=maize&window=6m returns aligned time series of disaster events and commodity prices for Kenya, ready to plot.

**PM decision:** API design started from analyst questions, not from data structure. The 10 most common analytical questions became the endpoint design. No analyst should need to write a JOIN.

### 5. Docker Containerization
Full stack (ingestion workers + PostgreSQL + Flask API) runs in Docker Compose. Researchers can reproduce the exact environment, run historical backfills, and deploy on any cloud provider without environment configuration.

**PM decision:** Reproducibility is a trust feature for research users. If an analyst cannot reproduce a result from 6 months ago, the platform is unreliable regardless of how accurate the data is.

---

## System Architecture

```
External APIs (4 sources)
  FEWS NET · World Bank · FAO · Country Economic DBs
        |
        v
Ingestion Layer
  Source-specific connectors
  Auth, rate limiting, pagination, error recovery
        |
        v
Normalization Engine
  Schema mapping + geo resolution
  Temporal alignment (monthly grain)
  Imputation with audit log
        |
        v
PostgreSQL Warehouse
  Star schema, time-series optimized
  Fact: events, prices, indicators
  Dim: countries, commodities, disaster types, time
        |
        v
Flask REST API
  Analyst-facing endpoints
  Pre-joined, analysis-ready
  Filterable by country, commodity, disaster type, date range
        |
        v
  Analyst / Researcher / Policy Tool
```

---

## Product Strategy & PM Thinking

### Problem Framing

The bottleneck is not analysis capability — it is data access. Policy analysts and researchers are sophisticated. They can derive insights if they have clean, aligned, cross-domain data. The product eliminates the 60-70% of time spent on data wrangling.

### Prioritization

Started with the narrowest viable data scope: 5 countries with the highest data availability and 3 commodity categories with the clearest disaster-price correlation evidence. Expanding scope before the core pipeline is reliable creates compounding data quality problems.

**Explicitly deferred:**
- Real-time ingestion (scheduled batch is sufficient for monthly policy analysis)
- UI/dashboard layer (analysts prefer API + their own visualization tools)
- Predictive modeling (out of scope until historical data quality is validated)

### Metrics That Matter

| Metric | Target | Why |
|---|---|---|
| **Data Freshness** | <= 30 days lag for all sources | Policy relevance degrades with stale data |
| **Schema Coverage** | > 90% of source fields mapped | Low coverage means analysts discover gaps mid-project |
| **Query Response Time** | < 2 seconds for standard queries | Slow queries kill adoption |
| **Imputation Rate** | < 10% of values imputed | High imputation signals underlying data reliability issues |
| **API Uptime** | > 99% | Research workflows block on platform availability |

### Risks and Tradeoffs

| Risk | Mitigation |
|---|---|
| API source goes offline or changes schema | Source connectors are isolated; schema versioning in warehouse |
| Data quality varies by country | Coverage metadata exposed in API; analysts can filter by data quality tier |
| Temporal misalignment across sources | Normalization engine logs all alignment decisions; audit trail in warehouse |
| Scope creep from analyst requests | Modular connector design; new sources do not touch existing pipeline |

### What I Would Do Differently in Production

- Replace scheduled batch ingestion with Airflow DAGs for better observability and failure recovery
- Add a data quality scoring layer so analysts can filter by confidence tier
- Build a lightweight analyst query UI to reduce API learning curve for non-technical users
- Add data versioning so analysts can reproduce historical queries after source data corrections

---

## Roadmap

| Phase | Features | Milestone |
|---|---|---|
| **MVP (Done)** | 4-source ingestion, normalization engine, PostgreSQL warehouse, Flask API, Docker | Working data platform for 5 countries |
| **Phase 2** | Airflow orchestration, data quality scoring, 20-country coverage | Research-grade reliability |
| **Phase 3** | Analyst query UI, API authentication, rate limiting | Platform-grade product |
| **Phase 4** | Predictive module (disaster-to-price impact forecasting), partner integrations | Policy intelligence product |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Ingestion | Python (requests, pandas) |
| Normalization | Python (custom transformation pipeline) |
| Warehouse | PostgreSQL (star schema) |
| API Layer | Flask + SQLAlchemy |
| Containerization | Docker + Docker Compose |
| Data Sources | FEWS NET API, World Bank API, FAO API, Country Economic DBs |

---

## Run Locally

```bash
git clone https://github.com/devothamgn321/cross-continental-eco-economic-data-pipeline.git
cd cross-continental-eco-economic-data-pipeline
docker-compose up --build
docker exec -it pipeline python ingestion/run_all.py
```

API is live at http://localhost:5000

Example query:
```
curl "http://localhost:5000/api/impact?country=KEN&commodity=maize&window=6m"
```

---

## About

**Devothama GN (Ruby)**
AI Product Manager | Platform Products | JHU Engineering Management
Ex-Mercedes-Benz ADAS | TEDxJHU Speaker

[Portfolio](https://devothamagn.netlify.app) · [LinkedIn](https://linkedin.com/in/devothamagn) · [GitHub](https://github.com/devothamgn321)

---

*Positioned as an analyst-facing data platform product — demonstrating how product thinking applies to data infrastructure: starting from user needs, designing for the query not the schema, and building for reproducibility and trust.*
