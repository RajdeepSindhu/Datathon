import os
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from .config import GEMINI_MODEL_ID, GROQ_MODEL_ID

load_dotenv()
logger = logging.getLogger("mandi_chatbot.agent_insight")

class InsightAgent:
    """
    Agent 4 — Insight & Explanation Agent
    Produces natural language explanations grounded strictly in the calculated Pandas output.
    Enforces contract rule: Never invent numbers, explain correlation without claiming causation.
    """

    def __init__(self):
        # 1. Initialize Groq client
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.groq_client = None
        if self.groq_api_key:
            try:
                from groq import Groq
                self.groq_client = Groq(api_key=self.groq_api_key)
                logger.info("Initialized Groq client in InsightAgent.")
            except Exception as e:
                logger.warning(f"Could not initialize Groq client in InsightAgent: {e}")

        # 2. Initialize Gemini client
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.gemini_client = None
        if self.api_key:
            try:
                from google import genai
                self.gemini_client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Could not initialize google-genai client in InsightAgent: {e}")

    def generate_summary_and_answer(self, intent: Dict[str, Any], engine_result: Dict[str, Any], chart_spec: Optional[Dict[str, Any]]) -> Dict[str, str]:
        """
        Returns {"answer": "...", "summary": "..."}
        """
        # If unsupported intent
        if intent.get("intent") == "unsupported":
            msg = intent.get("unsupported_reason", "This query cannot be answered with historical mandi data.")
            return {"answer": msg, "summary": msg}

        # Deterministic summary generation first
        deterministic_res = self._deterministic_summary(intent, engine_result, chart_spec)

        prompt = f"""You are the Insight Agent in the AI Mandi Chatbot.
Your task is to write a concise 1-2 sentence AI Summary of the calculated results.

STRICT CONTRACT RULES:
1. Ground every statement in the numbers provided below. Do not guess or modify numbers.
2. If this is a correlation query, you must report correlation and NEVER claim causation (e.g. state 'showed a correlation of X. This indicates a relationship but does not establish causation').
3. Keep the summary professional, clear, and focused on key findings.

User Intent: {intent.get('intent')}
Calculated Findings: {deterministic_res['summary']}
Engine Result Data: {engine_result.get('records', [])[:5]}

Generate a crisp 1-2 sentence summary:"""

        # 1. Try Groq (Ultra-fast, high rate limits)
        if self.groq_client:
            try:
                completion = self.groq_client.chat.completions.create(
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    model=GROQ_MODEL_ID,
                    temperature=0.2,
                    max_tokens=200,
                    timeout=15,
                )
                groq_text = completion.choices[0].message.content.strip()
                if groq_text:
                    return {
                        "answer": deterministic_res["answer"],
                        "summary": groq_text
                    }
            except Exception as e:
                logger.warning(f"Insight Agent Groq generation fallback: {e}")

        # 2. Try Gemini (with timeout to prevent hanging)
        if self.gemini_client:
            try:
                resp = self.gemini_client.models.generate_content(
                    model=GEMINI_MODEL_ID,
                    contents=prompt,
                    config={"timeout": 10}
                )
                gemini_text = resp.text.strip()
                if gemini_text:
                    return {
                        "answer": deterministic_res["answer"],
                        "summary": gemini_text
                    }
            except Exception as e:
                logger.warning(f"Insight Agent Gemini generation fallback: {e}")

        return deterministic_res

    def _deterministic_summary(self, intent: Dict[str, Any], engine_result: Dict[str, Any], chart_spec: Optional[Dict[str, Any]]) -> Dict[str, str]:
        intent_type = intent.get("intent", "lookup")
        records = engine_result.get("records", [])
        crop = intent.get("filters", {}).get("crop_name", "the crop")

        # 1. Ranking
        if intent_type == "ranking":
            if not records:
                return {"answer": f"No records found for {crop}.", "summary": "No data available."}
            top_rec = records[0]
            mandi = top_rec.get("mandi_name") or top_rec.get("mandi_id") or "Unknown"
            metric = engine_result.get("metric", "arrival_quantity_qtl")
            val = top_rec.get(metric, 0)
            op = engine_result.get("operation", "highest")
            
            unit = "₹ / Quintal" if "price" in metric else "Quintals"
            ans = f"{mandi} recorded the {op} {crop} {metric.replace('_', ' ')} of {val:,.2f} {unit}."
            top_list = ", ".join([f"{r.get('mandi_name', r.get('mandi_id'))} ({r.get(metric):,.2f})" for r in records[:3]])
            summary = f"Among analyzed mandis, {mandi} led with {val:,.2f} {unit}. Leading mandis include: {top_list}."
            return {"answer": ans, "summary": summary}

        # 2. Trend
        if intent_type == "trend":
            direction = engine_result.get("trend_direction", "stable")
            start_v = engine_result.get("start_value")
            end_v = engine_result.get("end_value")
            chg = engine_result.get("change", 0)
            metric_label = "modal price" if "price" in engine_result.get("metric", "") else "arrivals"
            unit = "₹" if "price" in metric_label else "Quintals"

            if start_v is not None and end_v is not None:
                ans = f"{crop} {metric_label} showed an overall {direction} trend, moving from {unit}{start_v:,.2f} to {unit}{end_v:,.2f} (change: {unit}{chg:+,.2f})."
                summary = f"{crop} {metric_label} recorded an overall {direction} pattern from {engine_result.get('start_date')} to {engine_result.get('end_date')}, shifting from {unit}{start_v:,.2f} to {unit}{end_v:,.2f}."
            else:
                ans = f"{crop} trend data analyzed."
                summary = f"Trend records analyzed for {crop} across the period."
            return {"answer": ans, "summary": summary}

        # 3. Cross-Dataset Correlation & Multi-condition
        if intent.get("filters", {}).get("multi_condition") == "high_arrivals_low_prices":
            matched = engine_result.get("matched_mandis", [])
            thresh = engine_result.get("threshold_statement", "")
            if matched:
                m_str = ", ".join(matched[:5])
                ans = f"Mandis with high {crop} arrivals (>= 75th percentile) and low price (<= 25th percentile) include: {m_str}."
                summary = f"{len(matched)} mandis met both conditions (high arrivals & low price): {m_str}. {thresh}"
            else:
                ans = f"No mandis simultaneously met both the 75th percentile arrival and 25th percentile price thresholds for {crop}."
                summary = f"No records fell within the top 25% arrivals and bottom 25% price simultaneously. {thresh}"
            return {"answer": ans, "summary": summary}

        if intent_type in ["cross_dataset_analysis", "weather_analysis"] and "correlation" in engine_result:
            r_stmt = engine_result.get("relationship_statement")
            corr = engine_result.get("correlation", 0.0)
            x_name = engine_result.get("x_metric", "Rainfall").replace("_", " ").title()
            ans = f"{x_name} and {crop} arrivals showed a correlation of {corr:.2f} during the available period."
            summary = r_stmt or f"{x_name} and {crop} arrivals recorded a correlation of {corr:.2f}. This indicates a statistical relationship but does not establish causation."
            return {"answer": ans, "summary": summary}

        # 4. Crop Share / Composition (Pie)
        if intent.get("chart_type") == "pie" or engine_result.get("operation") == "share":
            top_crops = [f"{r.get('crop_name')}: {r.get('arrival_quantity_qtl', 0):,.0f} qtl" for r in records[:4]]
            ans = f"Arrivals breakdown across {len(records)} crops."
            summary = f"Arrival distribution across crops: {', '.join(top_crops)}. Showing interactive composition chart."
            return {"answer": ans, "summary": summary}

        # 5. Period comparison
        if intent_type == "period_comparison":
            p1_v = engine_result.get("period1_value", 0)
            p2_v = engine_result.get("period2_value", 0)
            diff = engine_result.get("absolute_diff", 0)
            pct = engine_result.get("percentage_change", 0)
            ans = f"{crop} shifted from {p1_v:,.2f} in Period 1 to {p2_v:,.2f} in Period 2 (change: {diff:+,.2f} or {pct:+.1f}%)."
            summary = f"Period comparison shows a {pct:+.1f}% difference between the selected timeframes, changing by {diff:+,.2f}."
            return {"answer": ans, "summary": summary}

        # 6. Single value / Aggregation
        if "value" in engine_result:
            val = engine_result["value"]
            metric = engine_result.get("metric", "value")
            unit = "₹ / Quintal" if "price" in metric else "Quintals" if "arrival" in metric else ""
            ans = f"The {intent.get('aggregation', 'average')} {crop} {metric.replace('_', ' ')} was {val:,.2f} {unit}."
            summary = f"Calculated {intent.get('aggregation', 'average')} for {crop} {metric.replace('_', ' ')} across {engine_result.get('total_records_analyzed', 0)} verified records: {val:,.2f} {unit}."
            return {"answer": ans, "summary": summary}

        # Fallback
        return {
            "answer": f"Analysis completed for {crop}.",
            "summary": f"Calculated {len(records)} verified data points according to query parameters."
        }
