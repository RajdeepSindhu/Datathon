import logging
from typing import Dict, Any, Optional
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .config import DATASET_START_DATE, DATASET_END_DATE
from .data_loader import DataLoader
from .entity_resolver import EntityResolver
from .validator import IntentValidator
from .agent_understanding import QuestionUnderstandingAgent
from .pandas_engine import PandasAnalysisEngine
from .agent_chart_selector import ChartSelectionAgent
from .agent_insight import InsightAgent

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("mandi_chatbot.main")

app = FastAPI(title="AI Mandi Chatbot", description="Agentic Graph AI Chatbot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize core pipeline singletons
data_loader = DataLoader.get_instance()
entity_resolver = EntityResolver.get_instance()
validator = IntentValidator()
understanding_agent = QuestionUnderstandingAgent()
analysis_engine = PandasAnalysisEngine()
chart_agent = ChartSelectionAgent()
insight_agent = InsightAgent()

class ChatRequest(BaseModel):
    query: str

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "datasets_loaded": list(data_loader.datasets.keys()),
        "total_crops": len(data_loader.crops),
        "total_mandis": len(data_loader.mandi_names),
        "date_bounds": {
            "start": DATASET_START_DATE,
            "end": DATASET_END_DATE
        }
    }

@app.get("/api/datasets/info")
def datasets_info():
    return data_loader.get_entity_dictionaries()

@app.get("/api/suggested-queries")
def suggested_queries():
    return [
        {
            "category": "Bonus 1 — Ranking",
            "query": "Which 5 mandis had the highest wheat arrivals?",
            "expected_chart": "bar"
        },
        {
            "category": "Bonus 2 — Trend Analysis",
            "query": "Show wheat prices from January to September.",
            "expected_chart": "line"
        },
        {
            "category": "Bonus 3 — Cross-Dataset Correlation",
            "query": "Did rainfall affect wheat arrivals?",
            "expected_chart": "scatter"
        },
        {
            "category": "Spelling Correction",
            "query": "Which mandi had highest wheet price?",
            "expected_chart": "bar"
        },
        {
            "category": "High Arrivals / Low Prices (P75 / P25)",
            "query": "Which mandis had high arrivals but low prices?",
            "expected_chart": "bar"
        },
        {
            "category": "Composition / Share",
            "query": "What share of arrivals came from each crop?",
            "expected_chart": "pie"
        },
        {
            "category": "Single Value / KPI",
            "query": "What was the average wheat price?",
            "expected_chart": "kpi"
        },
        {
            "category": "Comparison",
            "query": "Compare wheat prices in Ludhiana and Khanna.",
            "expected_chart": "bar"
        },
        {
            "category": "Unsupported Boundary",
            "query": "Predict wheat prices next year.",
            "expected_chart": None
        }
    ]

@app.post("/api/chat")
def process_chat(req: ChatRequest):
    user_query = req.query.strip()
    if not user_query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    logger.info(f"Processing query: '{user_query}'")

    # Step 1: Question Understanding (Gemini 3.8 Flash)
    raw_intent = understanding_agent.understand(user_query)
    logger.info(f"Structured intent extracted: {raw_intent}")

    # Handle explicitly unsupported or clarification queries (e.g. greetings, general questions)
    if raw_intent.get("intent") in ["unsupported", "clarification"]:
        is_clarification = raw_intent.get("intent") == "clarification"
        default_msg = (
            "Hello! I am your AI Mandi Intelligence Assistant. You can ask me about crop arrivals, modal prices, ranking mandis, trends over time, logistics, and weather correlations (e.g. 'Which 5 mandis had the highest wheat arrivals?' or 'Show wheat prices from January to September')."
            if is_clarification else
            "The current dataset supports historical analysis (2026-01-01 to 2026-09-09) but does not contain a predictive model."
        )
        msg = raw_intent.get("unsupported_reason") or default_msg
        return {
            "answer": msg,
            "summary": msg,
            "data": [],
            "chart": None,
            "filters_applied": {},
            "data_range": {
                "start": DATASET_START_DATE,
                "end": DATASET_END_DATE
            },
            "clarification_required": is_clarification
        }

    # Step 2: Validation Layer (Whitelist, bounds, existence)
    is_valid, validated_intent, error_or_clarification = validator.validate(raw_intent)
    if not is_valid:
        logger.warning(f"Validation failed or clarification requested: {error_or_clarification}")
        return {
            "answer": error_or_clarification,
            "summary": error_or_clarification,
            "data": [],
            "chart": None,
            "filters_applied": raw_intent.get("filters", {}),
            "data_range": {
                "start": DATASET_START_DATE,
                "end": DATASET_END_DATE
            },
            "clarification_required": True
        }

    # Step 3: Deterministic Data Analysis (Pandas Engine)
    engine_result = analysis_engine.execute(validated_intent)
    logger.info(f"Pandas calculated {len(engine_result.get('records', []))} records.")

    # Step 4: Chart Selection Agent
    chart_spec = chart_agent.select_and_build_spec(validated_intent, engine_result)

    # Step 5: Insight Agent (Text Summary & Direct Answer)
    explanations = insight_agent.generate_summary_and_answer(validated_intent, engine_result, chart_spec)

    # Build Section 38 standard response object
    response_obj = {
        "answer": explanations["answer"],
        "summary": explanations["summary"],
        "data": engine_result.get("records", []),
        "chart": chart_spec,
        "filters_applied": validated_intent.get("filters", {}),
        "data_range": {
            "start": DATASET_START_DATE,
            "end": DATASET_END_DATE
        }
    }

    return response_obj

# Serve frontend static assets
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
    if (FRONTEND_DIR / "src").exists():
        app.mount("/src", StaticFiles(directory=FRONTEND_DIR / "src"), name="src")

    @app.get("/")
    def serve_ui():
        return FileResponse(FRONTEND_DIR / "index.html")
