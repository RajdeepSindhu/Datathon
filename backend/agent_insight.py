import os
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from .config import GEMINI_MODEL_ID, FALLBACK_GEMINI_MODEL_ID

load_dotenv()
logger = logging.getLogger("mandi_chatbot.agent_insight")

class InsightAgent:
    """
    Agent 4 — Insight & Explanation Agent
    Produces natural language explanations grounded strictly in the calculated Pandas output.
    Enforces contract rule: Never invent numbers, explain correlation without claiming causation.
    """

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.client = None
        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
                logger.info("Gemini client initialized for InsightAgent.")
            except Exception as e:
                logger.warning(f"Could not initialize Gemini client in InsightAgent: {e}")
        else:
            logger.warning("GEMINI_API_KEY not set. InsightAgent will use deterministic summaries only.")

    def _call_gemini(self, prompt: str, max_tokens: int = 500, json_mode: bool = False) -> Optional[str]:
        """Calls Gemini for plain text insight. Tries primary then fallback. Returns text or None."""
        if not self.client:
            return None
        for model in [GEMINI_MODEL_ID, FALLBACK_GEMINI_MODEL_ID]:
            try:
                from google.genai import types as genai_types
                config = genai_types.GenerateContentConfig(
                    temperature=0.2,
                    max_output_tokens=max_tokens,
                    response_mime_type="application/json" if json_mode else "text/plain",
                )
                response = self.client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=config,
                )
                text = response.text.strip() if response and response.text else None
                if text:
                    return text
            except Exception as e:
                logger.warning(f"InsightAgent Gemini call failed for model {model}: {e}")
        return None

    def generate_summary_and_answer(self, intent: Dict[str, Any], engine_result: Dict[str, Any], chart_spec: Optional[Dict[str, Any]]) -> Dict[str, str]:
        """
        Returns {"answer": "...", "summary": "..."}
        """
        if intent.get("intent") == "unsupported":
            msg = intent.get("unsupported_reason", "This query cannot be answered with historical mandi data.")
            return {"answer": msg, "summary": msg}

        # Always compute deterministic summary first — grounded in Pandas output
        deterministic_res = self._deterministic_summary(intent, engine_result, chart_spec)

        # Detect if user wants a deep/detailed explanation
        user_query = intent.get("_user_query", "")
        deep_mode = intent.get("_deep_mode", False)
        history = intent.get("_history", [])

        # Build history context for the prompt
        history_context = ""
        if history:
            last_pairs = history[-4:]  # last 2 turns
            lines = []
            for m in last_pairs:
                role = "User" if m.get("role") == "user" else "Assistant"
                content = m.get("content", "")[:300]  # truncate long summaries
                lines.append(f"{role}: {content}")
            history_context = "\n\nRecent conversation:\n" + "\n".join(lines)

        sentence_count = "6-8" if deep_mode else "3-5"
        max_tokens = 900 if deep_mode else 500

        prompt = f"""You are the Insight Agent in the AI Mandi Chatbot.
You must return a JSON object with two fields: "answer" and "summary".

STRICT CONTRACT RULES:
1. Ground every statement in the numbers provided below. Do not guess or modify numbers.
2. If this is a correlation query, NEVER claim causation — only state correlation.
3. Include specific numbers, mandi names, crop names, and date ranges where available.
4. Write in a professional but conversational tone.
5. End the summary with one practical observation or takeaway for a farmer or market analyst.
6. Use the recent conversation context to make the response feel connected and continuous.{' Write a thorough deep-dive since the user asked for depth.' if deep_mode else ''}

FIELD INSTRUCTIONS:
- "answer": Write 2-3 sentences. Strong, informative heading shown above the chart. Directly answer the user question with the key finding and top numbers.
- "summary": Write {sentence_count} sentences (~{max_tokens // 5} words). Detailed analysis shown below the chart. Explain patterns, comparisons, what numbers mean, and why it matters.{' Since user asked for depth: expand on seasonal effects, supply-demand dynamics, and give actionable insights.' if deep_mode else ''}

User Intent: {intent.get('intent')}
Calculated Findings: {deterministic_res['summary']}
Engine Result Data: {engine_result.get('records', [])[:8]}{history_context}

Return ONLY a JSON object like: {{"answer": "...", "summary": "..."}}"""

        ai_result = self._call_gemini(prompt, max_tokens=max_tokens, json_mode=True)

        if ai_result:
            try:
                import json, re
                # Strip markdown fences if present
                cleaned = re.sub(r"^```[a-z]*\n?", "", ai_result)
                cleaned = re.sub(r"\n?```$", "", cleaned).strip()
                parsed = json.loads(cleaned)
                return {
                    "answer": parsed.get("answer") or deterministic_res["answer"],
                    "summary": parsed.get("summary") or deterministic_res["summary"]
                }
            except Exception:
                pass

        return {
            "answer": deterministic_res["answer"],
            "summary": ai_result if ai_result else deterministic_res["summary"]
        }

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
