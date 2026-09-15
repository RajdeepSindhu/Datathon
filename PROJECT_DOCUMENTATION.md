# AI Mandi Chatbot — Project Architecture & Technology Stack

This document explains the end-to-end working mechanism of the **AI Mandi Chatbot**, detailing each architectural layer, the technologies employed, and exactly where and why each technology is used across the codebase.

---

## 1. System Overview & Golden Rule

The AI Mandi Chatbot is an enterprise-grade agricultural analytics assistant built strictly according to the **AI Mandi Chatbot Final Technical & Agentic Graph AI Contract**. 

The core philosophy of the system is the **Golden Rule of Agentic Graph AI**:
```text
Gemini = Understand ──> Backend = Validate ──> Pandas = Calculate ──> Chart Engine = Render ──> Gemini = Explain
```

### Why this design?
Traditional LLM chatbots hallucinate numbers or perform inaccurate mental math on large tabular datasets. In this project:
- **LLMs are NEVER used as numerical calculators.**
- **Every number, ranking, average, trendline, correlation, and percentile is deterministically computed by Pandas from verified CSV datasets.**
- **Missing values are preserved (`NaN ≠ 0`), and missing Mandi IDs are never guessed.**

---

## 2. End-to-End Workflow

The chatbot processes every question through a 5-stage sequential agentic pipeline:

```
                            [ User Enters Question ]
                                       │
                                       ▼
 ┌───────────────────────────────────────────────────────────────────────────┐
 │ 1. QUESTION UNDERSTANDING (Gemini 3.8 Flash / Semantic NLU)               │
 │    - Ingests natural colloquial queries ("What's wheat selling for?")    │
 │    - Resolves typos & regional terms ("wheet" -> Wheat, "ludhiyana")      │
 │    - Normalizes dates into ISO bounds (2026-01-01 to 2026-09-09)          │
 │    - Emits Structured Intent JSON                                         │
 └─────────────────────────────────────┬─────────────────────────────────────┘
                                       │
                                       ▼
 ┌───────────────────────────────────────────────────────────────────────────┐
 │ 2. VALIDATION & SECURITY LAYER (Backend Whitelist)                        │
 │    - Rejects arbitrary code execution attempts                            │
 │    - Checks datasets against ALLOWED_DATASETS whitelist                   │
 │    - Validates metrics, dimensions, crops, mandis, and join relationships │
 │    - Excludes cross_dataset_recovery_audit from analytical queries        │
 └─────────────────────────────────────┬─────────────────────────────────────┘
                                       │
                                       ▼
 ┌───────────────────────────────────────────────────────────────────────────┐
 │ 3. DATA ANALYSIS ENGINE (Deterministic Pandas Engine)                     │
 │    - Filters records by crop, mandi, district, date bounds                │
 │    - Joins datasets on mandi_id, (date, mandi_id, crop), or date          │
 │    - Calculates aggregations (Sum, Avg, Min, Max, Count, Median)          │
 │    - Computes P75 arrivals and P25 prices for multi-condition queries      │
 │    - Computes Pearson correlation (r) for weather + market data           │
 └─────────────────────────────────────┬─────────────────────────────────────┘
                                       │ Verified Result
                    ┌──────────────────┴──────────────────┐
                    ▼                                     ▼
 ┌──────────────────────────────────────┐   ┌────────────────────────────────┐
 │ 4. CHART SELECTION AGENT             │   │ 5. INSIGHT & EXPLANATION AGENT │
 │    - Ranking / Comparison ──> Bar    │   │    - Grounded strictly in      │
 │    - Time Series / Trend ───> Line   │   │      Pandas calculated output  │
 │    - Correlation / Rel ─────> Scatter│   │    - Explains correlation      │
 │    - Composition / Share ───> Pie    │   │      without claiming          │
 │    - Single Metric ─────────> KPI    │   │      causation                 │
 │    - Multi-column ──────────> Table  │   │    - States exact thresholds   │
 └──────────────────┬───────────────────┘   └────────────────┬───────────────┘
                    │ Chart Specification                    │ AI Text Summary
                    └──────────────────┬─────────────────────┘
                                       ▼
 ┌───────────────────────────────────────────────────────────────────────────┐
 │ CLIENT-SIDE INTERACTIVE UI                                                │
 │ - Renders 📊 AI SUMMARY badge & explanation                               │
 │ - Renders interactive Chart.js visualization with hover tooltips          │
 │ - Renders applied filter tags & expandable verified data table            │
 └───────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Technologies Used & Where They Are Used

| Technology | Layer / Category | Specific Files Where Used | Exact Role & Justification |
| :--- | :--- | :--- | :--- |
| **Google Gemini 3.8 Flash** | Language & Reasoning Layer | [`backend/agent_understanding.py`](file:///c:/Users/Rajdeep/Desktop/Datathon/backend/agent_understanding.py)<br>[`backend/agent_insight.py`](file:///c:/Users/Rajdeep/Desktop/Datathon/backend/agent_insight.py) | **Agent 1 (Question Understanding)** converts arbitrary natural language questions into structured JSON intents. **Agent 4 (Insight Agent)** translates the verified Pandas numerical results into natural-language explanations. |
| **Python 3.12** | Core Backend Runtime | Entire `backend/` & `tests/` directories | High-performance execution runtime for data processing, server hosting, and agent pipeline orchestration. |
| **Pandas (v3.0+)** | Deterministic Calculation Engine | [`backend/pandas_engine.py`](file:///c:/Users/Rajdeep/Desktop/Datathon/backend/pandas_engine.py)<br>[`backend/data_loader.py`](file:///c:/Users/Rajdeep/Desktop/Datathon/backend/data_loader.py) | **Agent 2 (Data Analysis)**: Numerical source of truth. Handles slicing, grouping, multi-table joins, percentiles (75th & 25th), time series ordering, and statistical correlation calculations without hallucination. |
| **NumPy** | Numerical Operations | [`backend/pandas_engine.py`](file:///c:/Users/Rajdeep/Desktop/Datathon/backend/pandas_engine.py) | Vectorized percentile calculations and missing value handling (`NaN ≠ 0`). |
| **RapidFuzz** | Fuzzy Text Matching & Typo Resolution | [`backend/entity_resolver.py`](file:///c:/Users/Rajdeep/Desktop/Datathon/backend/entity_resolver.py) | Powers the 3-step entity resolution hierarchy (Exact -> Normalized -> Fuzzy) to resolve typos like `wheet` -> `Wheat` and `ludhiyana` -> `Ludhiana`. |
| **FastAPI** | Web Framework & API Layer | [`backend/main.py`](file:///c:/Users/Rajdeep/Desktop/Datathon/backend/main.py) | Provides high-speed asynchronous REST endpoints (`/api/chat`, `/api/health`, `/api/datasets/info`, `/api/suggested-queries`) and serves static UI assets. |
| **Uvicorn** | ASGI Server | Run script / Server daemon | Lightweight, high-throughput asynchronous web server powering FastAPI on `http://127.0.0.1:8000`. |
| **Pydantic (v2.x)** | Data Modeling & Validation | [`backend/main.py`](file:///c:/Users/Rajdeep/Desktop/Datathon/backend/main.py) | Request body validation for incoming chat queries. |
| **HTML5 (Semantic)** | Frontend Structure | [`frontend/index.html`](file:///c:/Users/Rajdeep/Desktop/Datathon/frontend/index.html) | Semantic markup for sidebar navigation, dataset metadata display, chat stream, and input controls. |
| **Vanilla CSS3** | Styling & Design System | [`frontend/src/style.css`](file:///c:/Users/Rajdeep/Desktop/Datathon/frontend/src/style.css) | Custom design system using deep slate glassmorphism (`backdrop-filter: blur`), agricultural emerald & amber palettes, modern typography (Outfit & Inter), and micro-animations. |
| **JavaScript (ES6+)** | Frontend Logic & State Management | [`frontend/src/app.js`](file:///c:/Users/Rajdeep/Desktop/Datathon/frontend/src/app.js) | Orchestrates chat message creation, asynchronous API fetching, thinking states, filter badge generation, and table toggling. |
| **Chart.js (v4.4)** | Interactive Data Visualization | [`frontend/src/chart_renderer.js`](file:///c:/Users/Rajdeep/Desktop/Datathon/frontend/src/chart_renderer.js) | Renders canvas-based Bar charts, smooth Line charts, Scatter plots with cross-dataset points, and Donut/Pie charts with responsive hover tooltips. |

---

## 4. Detailed Component Breakdown

### 4.1. Data Ingestion & Indexing ([`backend/data_loader.py`](file:///c:/Users/Rajdeep/Desktop/Datathon/backend/data_loader.py))
Loads and caches the 5 approved analytical CSV datasets on server startup:
1. `arrivals_final.csv` (23,767 records) — Mandi arrivals and quantities (`arrival_quantity_qtl`).
2. `price_and_msp_final.csv` (12,000 records) — Market prices (`modal_price`, `min_price`, `max_price`) and MSP benchmarks.
3. `transport_logistics_final.csv` (10,000 records) — Warehouse logistics, distances, and transit hours.
4. `weather_daily.csv` (252 records) — Daily temperature, rainfall, and humidity.
5. `weather_sensors_final.csv` (15,000 records) — Sensor-level weather records.
*Note: `cross_dataset_recovery_audit.csv` is explicitly excluded from analytical queries per Section 11.*

Pre-indexes 7 unique crops, 57 mandis, 18 districts, and 6 warehouses for fast fuzzy lookup.

### 4.2. Entity & Spelling Resolution ([`backend/entity_resolver.py`](file:///c:/Users/Rajdeep/Desktop/Datathon/backend/entity_resolver.py))
Implements Section 18 of the contract:
- **Exact match**: Direct case-insensitive match.
- **Normalized match**: Punctuation and whitespace stripped.
- **Fuzzy match**: Levenshtein / Token ratio using RapidFuzz.
- **Synonym & Alias handling**: `kapas` -> `Cotton`, `gehun` -> `Wheat`, `sarson` -> `Mustard`, `dhan`/`rice` -> `Rice`.

### 4.3. Date Understanding ([`backend/date_resolver.py`](file:///c:/Users/Rajdeep/Desktop/Datathon/backend/date_resolver.py))
Implements Section 19 of the contract:
- Parses relative terms: "today", "yesterday", "this month", "last month".
- Parses calendar terms: "January", "first quarter", "from March to June".
- Strictly clamps dates within the available dataset range: `2026-01-01` to `2026-09-09`.

### 4.4. Backend Whitelist Validation ([`backend/validator.py`](file:///c:/Users/Rajdeep/Desktop/Datathon/backend/validator.py))
Implements Section 24 & 37 (Security Rules):
- Validates that the requested dataset is in `ALLOWED_DATASETS`.
- Validates that metrics and dimensions exist in `APPROVED_COLUMNS` and `APPROVED_DIMENSIONS`.
- Validates joins:
  - `arrivals` + `prices` join on `(date, mandi_id, crop_name)`.
  - `arrivals` / `prices` + `weather_daily` join on `date`.
  - `arrivals` + `transport` join on `mandi_id`.
- Rejects missing `mandi_id` attribution: Records in `prices` with missing `mandi_id` are never assigned by guessing.

### 4.5. Deterministic Pandas Engine ([`backend/pandas_engine.py`](file:///c:/Users/Rajdeep/Desktop/Datathon/backend/pandas_engine.py))
Executes deterministic Pandas routines for all 16 contract query types:
- **Ranking / Top N / Bottom N**: Groups and sorts top mandis/crops.
- **Trend Analysis**: Daily time-series calculations across 252 dates.
- **Period Comparison**: Comparative differences (absolute & percentage) between periods (e.g. Jan vs Aug).
- **MSP Analysis**: Identifies crops trading below MSP and calculates margins.
- **Cross-Dataset Correlation**: Merges weather with crop arrivals on `date` and calculates the Pearson correlation coefficient ($r$).
- **Multi-Condition Analysis (Section 35)**: Identifies mandis having High Arrivals ($\ge$ 75th percentile) and Low Price ($\le$ 25th percentile).

### 4.6. Chart Selection Agent ([`backend/agent_chart_selector.py`](file:///c:/Users/Rajdeep/Desktop/Datathon/backend/agent_chart_selector.py))
Implements the Section 30 Chart Selection Table:
- Rankings, Top N, Comparisons $\rightarrow$ **Bar**
- Time series, Trends $\rightarrow$ **Line**
- Two-variable correlation (e.g. Rainfall vs Arrivals) $\rightarrow$ **Scatter**
- Share / Composition $\rightarrow$ **Pie / Donut**
- Single numeric aggregation $\rightarrow$ **KPI Card**
- Complex multi-attribute records $\rightarrow$ **Data Table**

### 4.7. Insight & Summary Agent ([`backend/agent_insight.py`](file:///c:/Users/Rajdeep/Desktop/Datathon/backend/agent_insight.py))
- Translates Pandas outputs into concise 1-2 sentence summaries.
- Enforces Section 34: Explains correlation without claiming causation (*"Rainfall and wheat arrivals showed a positive correlation of 0.01 during the available period. This indicates a relationship but does not establish causation."*).

### 4.8. Frontend Presentation ([`frontend/`](file:///c:/Users/Rajdeep/Desktop/Datathon/frontend/))
- **Interactive Charts**: Rendered with smooth tooltips, INR currency formatting (`₹`), and quintal indicators (`qtl`).
- **Collapsible Data Table**: Allows inspecting the underlying verified Pandas tabular records.
- **Preset Demonstration Chips**: Quick-access chips to test all bonus capabilities.

---

## 5. Contract Bonus Capabilities Implemented

| Bonus Criterion | Points | Query Demonstrated | Chart Selected |
| :--- | :---: | :--- | :--- |
| **Bonus 1 — Natural Language Understanding** | 10 pts | *"Which 5 mandis had the highest wheat arrivals?"*<br>*"What's wheat selling for?"*<br>*"Show wheat prices from January to September."* | Understood without rigid syntax. |
| **Bonus 2 — Correct Chart Selection & Rendering** | 10 pts | Ranking $\rightarrow$ Bar<br>Trend $\rightarrow$ Line<br>Correlation $\rightarrow$ Scatter<br>Composition $\rightarrow$ Pie<br>Single Value $\rightarrow$ KPI | Verified interactive rendering in browser with real data. |
| **Bonus 3 — Text Summary + Graph** | 10 pts | Analytical queries provide both 📊 AI SUMMARY and 📊 INTERACTIVE GRAPH, grounded strictly in the calculated data. | Fully verified. |

---

## 6. How to Run the Application

### 1. Activate Environment & Start Server
```powershell
cd c:\Users\Rajdeep\Desktop\Datathon
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

### 2. Access the Chatbot
Open your web browser and navigate to:
```
http://127.0.0.1:8000
```

### 3. Run Automated Tests
```powershell
.\.venv\Scripts\python.exe tests\test_pipeline.py
```
