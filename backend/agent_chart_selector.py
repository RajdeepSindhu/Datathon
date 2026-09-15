from typing import Dict, Any, Optional

class ChartSelectionAgent:
    """
    Agent 3 — Chart Selection
    Selects correct chart type and generates the chart specification according to contract rules:
    - Rankings, Top N, Bottom N, Comparisons -> Bar
    - Time series, Trends, Ordered dates -> Line
    - Relationships, Correlation, 2 numerical variables -> Scatter
    - Part-to-whole composition with few categories -> Pie
    - Single numerical answer -> KPI
    - Detailed multi-column records -> Table
    """

    def select_and_build_spec(self, intent: Dict[str, Any], engine_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        intent_type = intent.get("intent", "lookup")
        records = engine_result.get("records", [])
        metric = engine_result.get("metric", intent.get("metric", "value"))
        filters = intent.get("filters", {})
        crop_name = filters.get("crop_name", "")

        # 1. Single Value -> KPI
        if "value" in engine_result and not engine_result.get("operation") == "share" and len(records) <= 1:
            val = engine_result.get("value")
            title = f"{'Average ' if intent.get('aggregation') == 'average' else ''}{crop_name} {metric.replace('_', ' ').title()}".strip()
            unit = "₹ / Quintal" if "price" in metric else "Quintals" if "arrival" in metric else ""
            return {
                "type": "kpi",
                "title": title,
                "value": val,
                "unit": unit,
                "metric": metric,
                "data": records
            }

        # 2. Correlation / Cross-dataset -> Scatter
        if intent_type in ["cross_dataset_analysis", "weather_analysis"] and "correlation" in engine_result:
            x_metric = engine_result.get("x_metric", "total_rainfall_mm")
            y_metric = engine_result.get("y_metric", "arrival_quantity_qtl")
            title = f"{x_metric.replace('_', ' ').title()} vs {crop_name} {y_metric.replace('_', ' ').title()}"
            scatter_data = [
                {"x": r[x_metric], "y": r[y_metric], "date": r.get("date", "")}
                for r in records if r.get(x_metric) is not None and r.get(y_metric) is not None
            ]
            return {
                "type": "scatter",
                "title": title,
                "x": x_metric,
                "x_label": x_metric.replace('_', ' ').title() + (" (mm)" if "rainfall" in x_metric else " (°C)" if "temp" in x_metric else ""),
                "y": y_metric,
                "y_label": y_metric.replace('_', ' ').title() + " (qtl)",
                "correlation": engine_result.get("correlation"),
                "correlation_strength": engine_result.get("correlation_strength"),
                "data": scatter_data
            }

        # 3. Trends / Time series -> Line
        if intent_type == "trend" or (records and "date" in records[0] and len(records) > 1):
            title = f"{crop_name} {metric.replace('_', ' ').title()} Trend"
            line_data = [
                {"date": r["date"], metric: r[metric]}
                for r in records if r.get("date") and r.get(metric) is not None
            ]
            return {
                "type": "line",
                "title": title,
                "x": "date",
                "x_label": "Date (2026)",
                "y": metric,
                "y_label": "Price (₹)" if "price" in metric else "Arrivals (qtl)" if "arrival" in metric else metric,
                "data": line_data
            }

        # 4. Composition / Share -> Pie
        if intent.get("chart_type") == "pie" or engine_result.get("operation") == "share" or intent_type == "composition":
            title = f"Crop Arrival Share"
            pie_data = [
                {"category": r.get("crop_name", "Unknown"), "value": r.get(metric, 0)}
                for r in records[:8]  # Limit to 8 slices for readability as per contract
            ]
            return {
                "type": "pie",
                "title": title,
                "category_key": "category",
                "value_key": "value",
                "data": pie_data
            }

        # 5. Ranking / Top N / Comparison -> Bar
        if intent_type in ["ranking", "comparison", "period_comparison", "logistics_analysis"] or (
            records and len(records) > 1 and not (len(records) > 30 and "date" in records[0])
        ):
            x_key = engine_result.get("group_by") or (
                "mandi_name" if "mandi_name" in records[0] else
                "entity" if "entity" in records[0] else
                "period" if "period" in records[0] else
                "destination_warehouse" if "destination_warehouse" in records[0] else
                list(records[0].keys())[0]
            )
            y_key = metric if (metric and metric in records[0]) else (
                "arrival_quantity_qtl" if "arrival_quantity_qtl" in records[0] else
                "modal_price" if "modal_price" in records[0] else
                list(records[0].keys())[1]
            )
            metric_label = (metric or y_key).replace('_', ' ').title()
            title = f"Top {intent.get('top_n', len(records))} {crop_name} {metric_label} by {x_key.replace('_', ' ').title()}" if intent_type == "ranking" else f"Comparison of {crop_name} {metric_label}"

            bar_data = [
                {"label": str(r[x_key]), "value": r[y_key]}
                for r in records if r.get(x_key) and r.get(y_key) is not None
            ]

            return {
                "type": "bar",
                "title": title,
                "x": x_key,
                "x_label": x_key.replace('_', ' ').title(),
                "y": y_key,
                "y_label": "Price (₹)" if "price" in y_key else "Arrivals (qtl)" if "arrival" in y_key else y_key.replace('_', ' ').title(),
                "data": bar_data
            }

        # 6. Fallback -> Table
        if records and len(records) > 1:
            return {
                "type": "table",
                "title": f"{crop_name} Analytical Records",
                "columns": list(records[0].keys()),
                "data": records
            }

        return None
