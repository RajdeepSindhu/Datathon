# AI Mandi Chatbot — Setup & Launch Guide

A step-by-step guide to get the **AI Mandi Chatbot** running locally on your machine.

---

## Prerequisites

| Requirement         | Minimum Version | Notes                                           |
| :------------------ | :-------------- | :---------------------------------------------- |
| **Python**          | 3.12+           | Required runtime for the backend                |
| **pip**             | 23.0+           | Python package manager (ships with Python)      |
| **Git**             | Any             | Only needed if cloning the repository            |
| **Web Browser**     | Any modern      | Chrome, Edge, or Firefox recommended             |

---

## 1. Clone the Repository (if needed)

If you haven't already cloned the project:

```bash
git clone <repository-url>
cd Datathon
```

---

## 2. Create & Activate a Python Virtual Environment

### Windows (PowerShell)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Windows (Command Prompt)
```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

### Linux / macOS
```bash
python3 -m venv .venv
source .venv/bin/activate
```

> [!TIP]
> You should see `(.venv)` appear at the beginning of your terminal prompt once activated.

---

## 3. Install Dependencies

With the virtual environment activated, install all required packages:

```bash
pip install -r requirements.txt
```

This installs:
- **FastAPI** & **Uvicorn** — Web server and API framework
- **Pandas** & **NumPy** — Deterministic data analysis engine
- **RapidFuzz** — Fuzzy text matching for typo correction
- **google-genai** — Google Gemini LLM integration
- **groq** — Groq LLM fallback provider
- **Pydantic** — Request/response validation
- **python-dotenv** — Environment variable loading
- **python-multipart** — Multipart form data support

---

## 4. Configure API Keys

Create a `.env` file in the project root (if one doesn't already exist):

```
Datathon/
├── .env          ← Create this file
├── backend/
├── frontend/
└── ...
```

Add the following keys:

```env
# Google Gemini API Key (Required)
GEMINI_API_KEY=your_gemini_api_key_here

# Groq API Key (Recommended — free tier: 30 RPM, 14,400 requests/day)
GROQ_API_KEY=your_groq_api_key_here
```

### Where to get API keys

| Provider       | URL                                    | Free Tier |
| :------------- | :------------------------------------- | :-------- |
| Google Gemini  | https://aistudio.google.com/apikey     | Yes       |
| Groq           | https://console.groq.com/             | Yes       |

> [!IMPORTANT]
> The `.env` file is listed in `.gitignore` and will **not** be committed to version control. Never share your API keys publicly.

---

## 5. Verify Dataset Files

Ensure the following CSV files are present in the `cross_dataset_final/` directory:

```
cross_dataset_final/
├── arrivals_final.csv              (23,767 records — Mandi arrivals)
├── price_and_msp_final.csv         (12,000 records — Market prices & MSP)
├── transport_logistics_final.csv   (10,000 records — Warehouse logistics)
├── weather_daily.csv               (252 records   — Daily weather aggregates)
├── weather_sensors_final.csv       (15,000 records — Sensor-level weather)
└── cross_dataset_recovery_audit.csv (audit log — excluded from analytics)
```

> [!NOTE]
> All datasets should already be included in the repository. If any are missing, the server will fail to start.

---

## 6. Launch the Server

From the project root directory, run:

### Using the virtual environment Python directly (recommended)

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

### Using activated virtual environment

```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

### With auto-reload (for development)

```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

You should see output similar to:

```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

---

## 7. Access the Application

Open your web browser and navigate to:

```
http://127.0.0.1:8000
```

This loads the full interactive chatbot UI with:
- 💬 Natural language chat input
- 📊 Interactive Chart.js visualizations
- 🏷️ Applied filter badges
- 📋 Expandable verified data tables
- 🎯 Preset demonstration query chips

---

## 8. API Endpoints

| Endpoint                | Method | Description                                  |
| :---------------------- | :----- | :------------------------------------------- |
| `/`                     | GET    | Serves the chatbot frontend UI               |
| `/api/chat`             | POST   | Processes a natural language query            |
| `/api/health`           | GET    | Returns server health and dataset status      |
| `/api/datasets/info`    | GET    | Returns available entities (crops, mandis, etc.) |
| `/api/suggested-queries`| GET    | Returns preset demonstration queries          |

### Example: Chat API

```bash
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "Which 5 mandis had the highest wheat arrivals?"}'
```

---

## 9. Run Automated Tests

The test suite validates the full agentic pipeline end-to-end:

```powershell
.\.venv\Scripts\python.exe tests\test_pipeline.py
```

This tests:
1. **DataLoader** — CSV ingestion and entity indexing
2. **EntityResolver** — Typo correction (`wheet` → `Wheat`, `kapas` → `Cotton`, `ludhiyana` → `Ludhiana`)
3. **Full Pipeline** — Question Understanding → Validation → Pandas Analysis → Chart Selection → Insight Generation

Expected output:

```
=== 1. Testing DataLoader ===
DataLoader PASSED!

=== 2. Testing EntityResolver (Typo tolerance) ===
EntityResolver PASSED!

=== 3. Testing QuestionUnderstandingAgent & Pipeline on Contract Bonus Queries ===
...
ALL CONTRACT PIPELINE TESTS PASSED!
```

---

## 10. Project Structure

```
Datathon/
├── .env                        # API keys (not committed)
├── .gitignore                  # Git ignore rules
├── requirements.txt            # Python dependencies
├── PROJECT_DOCUMENTATION.md    # Full architecture documentation
├── SETUP_AND_LAUNCH.md         # This file
│
├── backend/                    # Python backend (FastAPI)
│   ├── main.py                 # Server entrypoint & API routes
│   ├── config.py               # Configuration, whitelists, model IDs
│   ├── data_loader.py          # CSV ingestion & entity indexing
│   ├── entity_resolver.py      # Fuzzy matching & typo correction
│   ├── date_resolver.py        # Natural date parsing & clamping
│   ├── validator.py            # Whitelist validation & security
│   ├── agent_understanding.py  # Agent 1: Gemini NLU → structured intent
│   ├── pandas_engine.py        # Agent 2: Deterministic Pandas calculations
│   ├── agent_chart_selector.py # Agent 3: Chart type selection
│   └── agent_insight.py        # Agent 4: AI summary generation
│
├── frontend/                   # Static frontend (served by FastAPI)
│   ├── index.html              # Main HTML page
│   └── src/
│       ├── app.js              # Chat logic & state management
│       ├── chart_renderer.js   # Chart.js rendering engine
│       └── style.css           # Design system (glassmorphism, animations)
│
├── cross_dataset_final/        # CSV datasets
│   ├── arrivals_final.csv
│   ├── price_and_msp_final.csv
│   ├── transport_logistics_final.csv
│   ├── weather_daily.csv
│   ├── weather_sensors_final.csv
│   └── cross_dataset_recovery_audit.csv
│
└── tests/
    └── test_pipeline.py        # End-to-end pipeline tests
```

---

## Troubleshooting

### Server won't start

| Symptom | Solution |
| :--- | :--- |
| `ModuleNotFoundError: No module named 'fastapi'` | Ensure virtual environment is activated and `pip install -r requirements.txt` was run |
| `FileNotFoundError: ... .csv` | Verify all CSV files exist in `cross_dataset_final/` |
| `Address already in use` | Another process is using port 8000. Use `--port 8001` or stop the other process |

### API key errors

| Symptom | Solution |
| :--- | :--- |
| `GEMINI_API_KEY not set` or `401 Unauthorized` | Verify `.env` file exists in project root with a valid API key |
| LLM responses are empty or failing | Check API key quotas at the provider console |

### Frontend not loading

| Symptom | Solution |
| :--- | :--- |
| Blank page at `http://127.0.0.1:8000` | Check browser console (F12) for JavaScript errors |
| Charts not rendering | Ensure internet access for Chart.js CDN (`cdn.jsdelivr.net`) |

### PowerShell execution policy

If `.ps1` scripts are blocked:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

---

## Quick Start (TL;DR)

```powershell
# 1. Set up environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2. Add API keys to .env file

# 3. Launch
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

# 4. Open browser → http://127.0.0.1:8000
```
