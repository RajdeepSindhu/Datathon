# AI Mandi Chatbot

An agricultural market analytics assistant that lets users query Indian mandi (market) data in plain English and receive deterministic, verifiable answers backed by Pandas — not LLM-generated numbers.

---

## Overview

The AI Mandi Chatbot is an agentic pipeline application built around a single architectural principle:

> **LLMs understand language. Pandas calculates numbers. Never the other way around.**

Every ranking, average, trend line, correlation coefficient, and percentile threshold is computed deterministically from verified CSV datasets. LLMs are used exclusively to parse natural-language questions into structured intent JSON and to paraphrase the computed results into readable prose.

The system covers 57 mandis, 7+ crops, and 60,000+ records across five datasets spanning January to September 2026.

---

## Features

- Natural-language query processing with typo and synonym tolerance (`wheet` to Wheat, `ludhiyana` to Ludhiana, `kapas` to Cotton)
- 12 supported query types: ranking, aggregation, trend analysis, period comparison, MSP analysis, cross-dataset correlation, high-arrivals/low-price multi-condition analysis, logistics analysis, crop share composition, mandi summaries, single-value KPI lookups, and unsupported-query detection
- Interactive Chart.js visualizations: bar (rankings/comparisons), line (trends), scatter (correlations), pie/doughnut (composition), KPI card (single values), and tabular display
- Collapsible verified data tables showing the raw Pandas records behind every answer
- Explicit refusal of unsupported queries — predictions, live prices, and out-of-range dates are rejected with an explanation
- Enforces correlation-not-causation language in all weather correlation summaries
- LLM fallback chain: Groq (primary) to Gemini to deterministic heuristic parser — the application functions fully offline without any API keys

---

## Architecture

The chatbot processes every question through a five-stage sequential pipeline:

```
User Question
     |
     v
[1] Question Understanding Agent     Groq -> Gemini -> Heuristic parser
     |                               Emits structured intent JSON
     v
[2] Validation Layer                 Whitelist check, entity resolution,
     |                               date bounds, join legality
     v
[3] Pandas Analysis Engine           Deterministic calculation — rankings,
     |                               trends, correlations, aggregations
     |
     +---> [4] Chart Selection Agent     Picks chart type, builds spec
     |
     +---> [5] Insight Agent             Grounds text summary in Pandas output,
                                         optionally polishes with LLM
     |
     v
JSON Response -> Frontend (Chart.js + Vanilla JS)
```

**The frontend is served by FastAPI.** There is no separate frontend server or build step. Opening the root URL loads the complete application.

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| API Framework | FastAPI 0.110+ | REST endpoints, CORS, static file serving |
| ASGI Server | Uvicorn 0.28+ | Runs the FastAPI application |
| Data Engine | Pandas 2.2+ / NumPy 1.26+ | All deterministic calculations |
| Fuzzy Matching | RapidFuzz 3.6+ | Typo resolution for crop and mandi names |
| Primary LLM | Groq (`openai/gpt-oss-120b`) | Fast question parsing and insight polish |
| Fallback LLM | Google Gemini 2.5 Flash | Secondary NLU and insight generation |
| Validation | Pydantic v2 | Request/response schema enforcement |
| Config | python-dotenv | `.env` file loading |
| Frontend | Vanilla HTML5 / CSS3 / JS ES6+ | No framework, no build toolchain |
| Charts | Chart.js 4.4.1 (CDN) | Interactive visualizations |

---

## Prerequisites

| Requirement | Minimum Version |
|---|---|
| Python | 3.12+ |
| pip | 23.0+ |

---

## Running Locally

### 1. Create and activate a virtual environment

**Windows (PowerShell)**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If the activation script is blocked by execution policy:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**Linux / macOS**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure API keys

Create a `.env` file in the project root:

```env
# Groq API Key (recommended — used first; free tier: 30 RPM, 14,400 requests/day)
GROQ_API_KEY=your_groq_api_key_here

# Google Gemini API Key (used as fallback)
GEMINI_API_KEY=your_gemini_api_key_here
```

The `.env` file is listed in `.gitignore` and will not be committed.

| Provider | URL | Free Tier |
|---|---|---|
| Groq | https://console.groq.com | Yes |
| Google Gemini | https://aistudio.google.com/apikey | Yes |

> **Note:** API keys are optional. Without them, the application falls back to a deterministic rule-based parser for question understanding and produces grounded text summaries without LLM polish. All data calculations are unaffected.

### 4. Start the server

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

For development with auto-reload:
```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

### 5. Open the application

Navigate to `http://127.0.0.1:8000` in any modern browser.

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Serves the frontend application |
| POST | `/api/chat` | Main query endpoint — accepts `{"query": "..."}` |
| GET | `/api/health` | Server health check, dataset stats, and loaded entity counts |
| GET | `/api/datasets/info` | Entity dictionaries (all crops, mandis, districts) |
| GET | `/api/suggested-queries` | Preset demonstration queries for all supported intents |

### Example request

```bash
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "Which 5 mandis had the highest wheat arrivals?"}'
```

---

## Dataset Reference

All CSV files are located in `cross_dataset_final/`. They are loaded once at startup into memory.

| File | Records | Description |
|---|---|---|
| `arrivals_final.csv` | ~23,767 | Mandi crop arrival records (quantity in quintals, mandi, crop, date) |
| `price_and_msp_final.csv` | ~12,000 | Market prices and Minimum Support Price (modal/min/max price in Rs/quintal) |
| `transport_logistics_final.csv` | ~10,000 | Logistics trips (distance, transit hours, destination warehouse) |
| `weather_daily.csv` | 252 | Daily aggregated weather (temperature, rainfall, humidity) |
| `weather_sensors_final.csv` | ~15,000 | Sensor-level weather readings |
| `cross_dataset_recovery_audit.csv` | — | Audit log only — excluded from all analytical queries |

---

## Project Structure

```
Datathon/
├── .env                              # API keys (not committed)
├── requirements.txt
├── README.md
├── PROJECT_DOCUMENTATION.md
├── SETUP_AND_LAUNCH.md
│
├── backend/
│   ├── main.py                       # FastAPI app, all routes, pipeline orchestration
│   ├── config.py                     # Constants: paths, whitelists, model IDs, thresholds
│   ├── data_loader.py                # Singleton CSV loader and entity index builder
│   ├── entity_resolver.py            # Singleton fuzzy matcher (exact > normalized > RapidFuzz)
│   ├── date_resolver.py              # NL date parser clamped to dataset date range
│   ├── validator.py                  # Whitelist validation, entity resolution, join legality
│   ├── agent_understanding.py        # Agent 1 — NLU: Groq > Gemini > heuristic parser
│   ├── pandas_engine.py              # Agent 2 — All deterministic Pandas calculations
│   ├── agent_chart_selector.py       # Agent 3 — Chart type selection and spec building
│   └── agent_insight.py              # Agent 4 — Deterministic summary + optional LLM polish
│
├── frontend/
│   ├── index.html                    # App shell: sidebar, chat thread, input bar
│   └── src/
│       ├── app.js                    # Chat state management, API calls, DOM rendering
│       ├── chart_renderer.js         # ChartRenderer — all six chart types via Chart.js
│       └── style.css                 # Design system: CSS custom properties, glassmorphism
│
├── cross_dataset_final/              # CSV datasets (see Dataset Reference above)
│
└── tests/
    └── test_pipeline.py              # End-to-end pipeline tests for all supported query types
```

---

## Running Tests

```powershell
.\.venv\Scripts\python.exe tests\test_pipeline.py
```

---

## Example Queries

| Intent Type | Example Query | Chart |
|---|---|---|
| Ranking | Which 5 mandis had the highest wheat arrivals? | Bar |
| Trend | Show wheat prices from January to September | Line |
| Correlation | Did rainfall affect wheat arrivals? | Scatter |
| Composition | What share of arrivals came from each crop? | Pie |
| KPI | What was the average wheat price? | KPI card |
| Comparison | Compare wheat prices in Ludhiana and Khanna | Bar |
| MSP Analysis | Which crops are trading below MSP? | Bar |
| Multi-condition | Which mandis had high arrivals but low prices? | Bar |
| Typo tolerance | Which mandi had highest wheet price? | Bar |
| Unsupported | Predict wheat prices next year | Rejection message |

---

## Design Principles

**No hallucinated numbers.** The LLM never performs arithmetic. Groq and Gemini receive the Pandas-computed result and are asked only to paraphrase it.

**Graceful degradation.** If both LLM providers fail or no API keys are configured, the deterministic heuristic parser handles question understanding and the deterministic summary engine generates the response. The application never crashes due to an unavailable LLM.

**Strict data provenance.** Missing mandi IDs are never imputed. Missing values remain `NaN` throughout the pipeline — they are never silently coerced to zero. Every filter applied to a query is reflected in the response as visible filter badges.

**Separation of concerns.** Language understanding, data calculation, visualization, and explanation are handled by four distinct, independently testable agents.
