import os
import json
import logging
import re
from typing import Dict, Any, Optional, Tuple
from dotenv import load_dotenv

from .config import (
    ALLOWED_INTENTS,
    ALLOWED_DATASETS,
    APPROVED_METRICS,
    APPROVED_DIMENSIONS,
    DATASET_START_DATE,
    DATASET_END_DATE,
    GEMINI_MODEL_ID,
    FALLBACK_GEMINI_MODEL_ID,
)
from .date_resolver import resolve_date_range

load_dotenv()
logger = logging.getLogger("mandi_chatbot.agent_understanding")

SYSTEM_PROMPT = f"""You are the Question Understanding Agent (Agent 1) in the AI Mandi Chatbot.
Your job is strictly language understanding, intent extraction, entity identification, typo detection, and date conversion.
You do NOT calculate answers or guess numbers. You must output ONLY a valid JSON object.

Allowed intents: {list(ALLOWED_INTENTS)}
Allowed datasets: {list(ALLOWED_DATASETS)}
Dataset period: {DATASET_START_DATE} to {DATASET_END_DATE}
Golden Rule:
Never guess numerical results. Map user intent into structured JSON:

JSON Schema:
{{
  "intent": "ranking" | "lookup" | "aggregation" | "comparison" | "trend" | "period_comparison" | "msp_analysis" | "logistics_analysis" | "weather_analysis" | "cross_dataset_analysis" | "mandi_summary" | "multi_condition" | "clarification" | "unsupported",
  "datasets": ["arrivals" | "prices" | "transport" | "weather_daily" | "weather_sensors"],
  "metric": "arrival_quantity_qtl" | "modal_price" | "min_price" | "max_price" | "msp" | "distance_km" | "transit_hours_final" | "avg_temperature_c" | "total_rainfall_mm" | null,
  "aggregation": "sum" | "average" | "minimum" | "maximum" | "count" | "median" | null,
  "filters": {{
    "crop_name": string | null,
    "mandi_id": string | null,
    "mandi_name": string | null,
    "district": string | null,
    "state": string | null,
    "date_start": string | null,
    "date_end": string | null,
    "multi_condition": string | null
  }},
  "group_by": [string] | null,
  "operation": "highest" | "lowest" | null,
  "top_n": integer | null,
  "chart_required": boolean,
  "chart_type": "bar" | "line" | "scatter" | "pie" | "kpi" | "table" | null,
  "unsupported_reason": string | null
}}

Guidelines:
1. "wheet" -> crop_name: "Wheat", "ludhiyana" -> mandi_name: "Ludhiana"
2. "What's wheat selling for?" / "Show wheat rate" -> intent: "lookup", datasets: ["prices"], metric: "modal_price", crop_name: "Wheat"
3. "Predict wheat prices next year" -> intent: "unsupported", unsupported_reason: "The current dataset supports historical analysis but does not contain a price-prediction model."
4. "What is today's live mandi price?" -> intent: "unsupported", unsupported_reason: "Live prices are not available. The dataset covers historical records from 2026-01-01 to 2026-09-09."
5. "Which mandis had high arrivals but low prices?" -> intent: "cross_dataset_analysis", datasets: ["arrivals", "prices"], filters: {{"crop_name": "Wheat", "multi_condition": "high_arrivals_low_prices"}}, chart_type: "bar"
6. "Did rainfall affect wheat arrivals?" -> intent: "cross_dataset_analysis", datasets: ["weather_daily", "arrivals"], metric: "arrival_quantity_qtl", filters: {{"crop_name": "Wheat"}}, chart_type: "scatter"
7. "Show wheat prices from January to September" / "Show prices over time" / "trend of..." -> intent: "trend", datasets: ["prices"], metric: "modal_price", group_by: ["date"], filters: {{"crop_name": "Wheat", "date_start": "2026-01-01", "date_end": "2026-09-09"}}, chart_type: "line"
8. "Which 5 mandis had the highest wheat arrivals?" / "highest / lowest" -> intent: "ranking", datasets: ["arrivals"], metric: "arrival_quantity_qtl", operation: "highest", top_n: 5, group_by: ["mandi_name"], filters: {{"crop_name": "Wheat"}}, chart_type: "bar"
9. "What share of arrivals came from each crop?" / "share / composition" -> intent: "aggregation", datasets: ["arrivals"], metric: "arrival_quantity_qtl", group_by: ["crop_name"], chart_type: "pie"
10. "What was the average wheat price?" -> intent: "aggregation", aggregation: "average", datasets: ["prices"], metric: "modal_price", filters: {{"crop_name": "Wheat"}}, chart_type: "kpi"
11. Return ONLY the JSON object.
"""

class QuestionUnderstandingAgent:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.client = None
        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
                logger.info("Gemini client initialized for QuestionUnderstandingAgent.")
            except Exception as e:
                logger.warning(f"Could not initialize Gemini client: {e}")
        else:
            logger.warning("GEMINI_API_KEY not set. Will use heuristic parser only.")

    def _call_gemini(self, model: str, prompt: str) -> Optional[str]:
        """Calls Gemini with JSON output mode. Returns text or None."""
        if not self.client:
            return None
        try:
            from google.genai import types as genai_types
            response = self.client.models.generate_content(
                model=model,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                    max_output_tokens=512,
                )
            )
            text = response.text.strip() if response and response.text else None
            if text:
                # Strip markdown code fences if model wraps JSON in them
                if text.startswith("```"):
                    text = re.sub(r"^```[a-z]*\n?", "", text)
                    text = re.sub(r"\n?```$", "", text).strip()
                # Fix trailing commas before } or ] (common LLM mistake)
                text = re.sub(r",\s*([}\]])", r"\1", text)
                logger.info(f"[Gemini:{model}] Response length: {len(text)} chars")
            return text
        except Exception as e:
            logger.warning(f"Gemini call failed for model {model}: {e}")
            return None

    def understand(self, user_question: str, history: list = []) -> Dict[str, Any]:
        """
        Parses user question into structured intent JSON.
        history: list of {"role": "user"|"assistant", "content": "..."} dicts (last N turns).
        Priority: Gemini primary -> Gemini fallback -> Heuristic parser.
        """
        # Build conversation context string from history
        history_text = ""
        if history:
            history_lines = []
            for msg in history[-6:]:  # last 3 turns (6 messages)
                role = "User" if msg.get("role") == "user" else "Assistant"
                history_lines.append(f"{role}: {msg.get('content', '')}")
            history_text = "\n\nPrevious conversation:\n" + "\n".join(history_lines) + "\n"

        prompt = f"{SYSTEM_PROMPT}{history_text}\nUser Question:\n{user_question}"
        logger.info(f"[Gemini] Sending query to model | prompt chars: {len(prompt)} | history turns: {len(history)}")

        # 1. Try primary model
        text = self._call_gemini(GEMINI_MODEL_ID, prompt)
        if text:
            try:
                intent_json = json.loads(text)
                self._enrich_dates(user_question, intent_json)
                return intent_json
            except json.JSONDecodeError as e:
                logger.warning(f"Primary model returned invalid JSON: {e}")

        # 2. Try fallback model
        text = self._call_gemini(FALLBACK_GEMINI_MODEL_ID, prompt)
        if text:
            try:
                intent_json = json.loads(text)
                self._enrich_dates(user_question, intent_json)
                return intent_json
            except json.JSONDecodeError as e:
                logger.warning(f"Fallback model returned invalid JSON: {e}")

        # 3. Deterministic heuristic parser
        logger.info("Using heuristic parser for question understanding.")
        return self._heuristic_parse(user_question)

    def _enrich_dates(self, user_question: str, intent_json: Dict[str, Any]):
        filters = intent_json.setdefault("filters", {})
        if not filters.get("date_start") and not filters.get("date_end"):
            d_start, d_end = resolve_date_range(user_question)
            if d_start:
                filters["date_start"] = d_start
            if d_end:
                filters["date_end"] = d_end

    def _heuristic_parse(self, q: str) -> Dict[str, Any]:
        """
        Deterministic semantic parser supporting contract requirements and bonus queries.
        """
        q_lower = q.lower().strip()

        # Check unsupported queries
        if any(w in q_lower for w in ["predict", "forecast", "future", "next year", "tomorrow"]):
            return {
                "intent": "unsupported",
                "datasets": ["prices"],
                "unsupported_reason": "The current dataset supports historical analysis but does not contain a price-prediction model."
            }

        if any(w in q_lower for w in ["live price", "realtime", "real-time", "today's live"]):
            return {
                "intent": "unsupported",
                "datasets": ["prices"],
                "unsupported_reason": "Live market feeds are not connected. The dataset covers historical mandi records from 2026-01-01 to 2026-09-09."
            }

        # Date resolution
        d_start, d_end = resolve_date_range(q)

        # Extract crop (with typo tolerance)
        crop = None
        crop_patterns = [
            (r"\b(wheet|wheat|gehun)\b", "Wheat"),
            (r"\b(kapas|cotton)\b", "Cotton"),
            (r"\b(paddy|dhan|rice)\b", "Paddy"),
            (r"\b(mustard|sarson)\b", "Mustard"),
            (r"\b(sugarcane|sugar cane)\b", "Sugarcane"),
            (r"\b(maize|makka|corn)\b", "Maize"),
            (r"\b(gram|chana)\b", "Gram"),
            (r"\b(potato|aloo)\b", "Potato"),
            (r"\b(onion|pyaz)\b", "Onion"),
            (r"\b(soybean|soya)\b", "Soybean"),
        ]
        for pat, cname in crop_patterns:
            if re.search(pat, q_lower):
                crop = cname
                break

        # Extract mandi (with typo tolerance)
        mandi = None
        mandi_patterns = [
            (r"\b(ludhiyana|ludhiana)\b", "Ludhiana Mandi"),
            (r"\b(khanna)\b", "Khanna Mandi"),
            (r"\b(amritsar)\b", "Amritsar Mandi"),
            (r"\b(patiala|bathinda)\b", "Bathinda Grain Market"),
            (r"\b(hisar|fatehabad)\b", "Hisar Market"),
            (r"\b(bareilly|bilaspur)\b", "Bilaspur Mandi"),
        ]
        for pat, mname in mandi_patterns:
            if re.search(pat, q_lower):
                mandi = mname
                break

        # 1. High arrivals / low prices (Section 35)
        if ("high arrival" in q_lower or "highest arrival" in q_lower) and ("low price" in q_lower or "lowest price" in q_lower):
            return {
                "intent": "cross_dataset_analysis",
                "datasets": ["arrivals", "prices"],
                "metric": "arrival_quantity_qtl",
                "filters": {"crop_name": crop or "Wheat", "multi_condition": "high_arrivals_low_prices"},
                "chart_required": True,
                "chart_type": "bar"
            }

        # 2. Cross-dataset / correlation (Section 34, Bonus 1 & 2)
        if ("rainfall" in q_lower or "rain" in q_lower or "weather" in q_lower or "temperature" in q_lower) and ("arrival" in q_lower or "price" in q_lower):
            target_ds = "prices" if "price" in q_lower else "arrivals"
            target_metric = "modal_price" if target_ds == "prices" else "arrival_quantity_qtl"
            x_metric = "avg_temperature_c" if "temperature" in q_lower else "total_rainfall_mm"
            return {
                "intent": "cross_dataset_analysis",
                "datasets": ["weather_daily", target_ds],
                "metric": target_metric,
                "x_metric": x_metric,
                "filters": {"crop_name": crop or "Wheat", "date_start": d_start, "date_end": d_end},
                "chart_required": True,
                "chart_type": "scatter"
            }

        # 3. Share / Composition (Section 22, Bonus 2)
        if "share" in q_lower or "composition" in q_lower or "percentage of arrival" in q_lower:
            return {
                "intent": "aggregation",
                "datasets": ["arrivals"],
                "metric": "arrival_quantity_qtl",
                "operation": "share",
                "group_by": ["crop_name"],
                "filters": {"date_start": d_start, "date_end": d_end},
                "chart_required": True,
                "chart_type": "pie"
            }

        # 4. Trend / Time series (Section 16 #7, Bonus 1 & 2)
        if "trend" in q_lower or "over time" in q_lower or ("from" in q_lower and "to" in q_lower) or ("january to september" in q_lower) or "change" in q_lower:
            ds = "prices" if ("price" in q_lower or "rate" in q_lower) else "arrivals"
            metric = "modal_price" if ds == "prices" else "arrival_quantity_qtl"
            return {
                "intent": "trend",
                "datasets": [ds],
                "metric": metric,
                "group_by": ["date"],
                "filters": {"crop_name": crop or "Wheat", "mandi_name": mandi, "date_start": d_start, "date_end": d_end},
                "chart_required": True,
                "chart_type": "line"
            }

        # 5. Period comparison (Section 16 #8)
        if "compare" in q_lower and ("january" in q_lower and "august" in q_lower):
            ds = "prices" if "price" in q_lower else "arrivals"
            return {
                "intent": "period_comparison",
                "datasets": [ds],
                "metric": "modal_price" if ds == "prices" else "arrival_quantity_qtl",
                "period1_start": "2026-01-01",
                "period1_end": "2026-01-31",
                "period1_label": "January 2026",
                "period2_start": "2026-08-01",
                "period2_end": "2026-08-31",
                "period2_label": "August 2026",
                "filters": {"crop_name": crop or "Wheat"},
                "chart_required": True,
                "chart_type": "bar"
            }

        # 6. Comparison between two mandis (Section 16 #6)
        if "compare" in q_lower and ("ludhiana" in q_lower and "khanna" in q_lower):
            return {
                "intent": "comparison",
                "datasets": ["prices" if "price" in q_lower else "arrivals"],
                "metric": "modal_price" if "price" in q_lower else "arrival_quantity_qtl",
                "compare_entities": ["Ludhiana Mandi", "Khanna Mandi"],
                "group_by": ["mandi_name"],
                "filters": {"crop_name": crop or "Wheat", "date_start": d_start, "date_end": d_end},
                "chart_required": True,
                "chart_type": "bar"
            }

        # 7. Ranking / Top N / Bottom N (Section 16 #3, #4, #5)
        if any(w in q_lower for w in ["highest", "lowest", "top", "bottom", "ranking", "most"]):
            ds = "prices" if "price" in q_lower else "arrivals"
            metric = "modal_price" if ds == "prices" else "arrival_quantity_qtl"
            operation = "lowest" if any(w in q_lower for w in ["lowest", "bottom", "least"]) else "highest"
            
            top_match = re.search(r"\b(?:top|bottom)\s+(\d+)\b", q_lower)
            top_n = int(top_match.group(1)) if top_match else 5

            return {
                "intent": "ranking",
                "datasets": [ds],
                "metric": metric,
                "aggregation": "average" if ds == "prices" else "sum",
                "group_by": ["mandi_name"],
                "operation": operation,
                "top_n": top_n,
                "filters": {"crop_name": crop or "Wheat", "date_start": d_start, "date_end": d_end},
                "chart_required": True,
                "chart_type": "bar"
            }

        # 8. MSP Analysis (Section 16 #9)
        if "msp" in q_lower or "below msp" in q_lower:
            return {
                "intent": "msp_analysis",
                "datasets": ["prices"],
                "metric": "modal_price",
                "filters": {"crop_name": crop, "date_start": d_start, "date_end": d_end},
                "chart_required": True,
                "chart_type": "bar"
            }

        # 9. Mandi Analysis / Summary (Section 16 #10)
        if mandi and any(w in q_lower for w in ["tell me about", "summary", "overview", "detail"]):
            return {
                "intent": "mandi_summary",
                "datasets": ["arrivals", "prices", "transport"],
                "filters": {"mandi_name": mandi},
                "chart_required": True,
                "chart_type": "bar"
            }

        # 10. Logistics analysis (Section 16 #11, #12)
        if "transit" in q_lower or "warehouse" in q_lower or "logistics" in q_lower:
            return {
                "intent": "logistics_analysis",
                "datasets": ["transport"],
                "metric": "transit_hours_final" if "transit" in q_lower else "trip_id",
                "group_by": ["destination_warehouse"] if "warehouse" in q_lower else ["mandi_name"],
                "chart_required": True,
                "chart_type": "bar"
            }

        # 11. Weather lookup/aggregation (Section 16 #13)
        if "rainfall" in q_lower or "temperature" in q_lower:
            return {
                "intent": "weather_analysis",
                "datasets": ["weather_daily"],
                "metric": "total_rainfall_mm" if "rainfall" in q_lower else "avg_temperature_c",
                "operation": "highest" if "highest" in q_lower else "average",
                "filters": {"date_start": d_start, "date_end": d_end},
                "chart_required": True,
                "chart_type": "kpi"
            }

        # 12. Single value / Aggregation / Lookup (Section 16 #1, #2)
        # "What is the wheat price?", "What was the average wheat price?"
        if any(w in q_lower for w in ["price", "rate", "cost", "selling", "arrival", "how much", "average", "total"]):
            ds = "prices" if any(w in q_lower for w in ["price", "rate", "cost", "selling"]) else "arrivals"
            metric = "modal_price" if ds == "prices" else "arrival_quantity_qtl"
            if "minimum" in q_lower or "min" in q_lower:
                metric = "min_price"
            elif "maximum" in q_lower or "max" in q_lower:
                metric = "max_price"

            return {
                "intent": "aggregation",
                "datasets": [ds],
                "metric": metric,
                "aggregation": "average" if ("average" in q_lower or "avg" in q_lower) else ("sum" if ds == "arrivals" else "average"),
                "filters": {"crop_name": crop or "Wheat", "mandi_name": mandi, "date_start": d_start, "date_end": d_end},
                "chart_required": True,
                "chart_type": "kpi"
            }

        # 13. Fallback — unclear or conversational input
        return {
            "intent": "clarification",
            "datasets": [],
            "filters": {},
            "chart_required": False,
            "chart_type": None,
            "unsupported_reason": None
        }
