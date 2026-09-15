import logging
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
from .data_loader import DataLoader
from .config import HIGH_ARRIVAL_PERCENTILE, LOW_PRICE_PERCENTILE, DATASET_START_DATE, DATASET_END_DATE

logger = logging.getLogger("mandi_chatbot.pandas_engine")

class PandasAnalysisEngine:
    def __init__(self):
        self.loader = DataLoader.get_instance()

    def execute(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes deterministic Pandas calculations based on validated intent JSON.
        Returns a dict containing:
        - records: list of dicts for charting/table
        - calculated_summary: computed scalar stats
        - metadata: applied filters, row counts, thresholds
        """
        intent_type = intent.get("intent", "lookup")
        datasets = intent.get("datasets", ["arrivals"])
        filters = intent.get("filters", {})
        metric = intent.get("metric")
        group_by = intent.get("group_by", [])
        operation = intent.get("operation", "highest")
        top_n = intent.get("top_n")

        # Route by intent or multi-condition filter
        if filters.get("multi_condition") == "high_arrivals_low_prices":
            return self._execute_high_arrivals_low_prices(intent)
        elif intent_type == "ranking" or (top_n is not None and intent_type in ["aggregation", "lookup"]):
            return self._execute_ranking(intent)
        elif intent_type == "trend":
            return self._execute_trend(intent)
        elif intent_type == "period_comparison":
            return self._execute_period_comparison(intent)
        elif intent_type == "comparison":
            return self._execute_comparison(intent)
        elif intent_type == "msp_analysis":
            return self._execute_msp_analysis(intent)
        elif intent_type == "cross_dataset_analysis" or (intent_type == "weather_analysis" and len(datasets) > 1):
            return self._execute_cross_dataset(intent)
        elif intent_type == "logistics_analysis":
            return self._execute_logistics(intent)
        elif intent_type == "mandi_summary":
            return self._execute_mandi_summary(intent)
        else:
            return self._execute_standard_aggregation(intent)

    def _filter_df(self, df: pd.DataFrame, filters: Dict[str, Any]) -> pd.DataFrame:
        filtered = df.copy()
        if not filters:
            return filtered

        # Crop filter
        if filters.get("crop_name") and "crop_name" in filtered.columns:
            filtered = filtered[filtered["crop_name"].str.lower() == str(filters["crop_name"]).lower()]

        # Mandi filter (Strict: NEVER impute missing mandi_id)
        if filters.get("mandi_name") and "mandi_name" in filtered.columns:
            filtered = filtered[filtered["mandi_name"].str.lower() == str(filters["mandi_name"]).lower()]
        elif filters.get("mandi_id") and "mandi_id" in filtered.columns:
            filtered = filtered[filtered["mandi_id"].str.upper() == str(filters["mandi_id"]).upper()]

        # District filter
        if filters.get("district"):
            d_val = str(filters["district"]).lower()
            if "district_final" in filtered.columns:
                filtered = filtered[filtered["district_final"].str.lower() == d_val]
            elif "district" in filtered.columns:
                filtered = filtered[filtered["district"].str.lower() == d_val]

        # Date range filter
        d_start = filters.get("date_start")
        d_end = filters.get("date_end")
        if "date" in filtered.columns:
            if d_start:
                filtered = filtered[filtered["date"] >= d_start]
            if d_end:
                filtered = filtered[filtered["date"] <= d_end]

        return filtered

    def _execute_ranking(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        ds_name = intent["datasets"][0]
        df = self.loader.get_dataset(ds_name)
        if df is None or df.empty:
            return {"error": f"Dataset {ds_name} is empty or not found."}

        filtered = self._filter_df(df, intent.get("filters", {}))
        metric = intent.get("metric") or ("arrival_quantity_qtl" if ds_name == "arrivals" else "modal_price")
        group_cols = intent.get("group_by") or (["mandi_name"] if "mandi_name" in filtered.columns else ["mandi_id"])
        # Adjust group_cols if column does not exist in dataset (e.g. mandi_name in prices)
        actual_group_cols = []
        for c in group_cols:
            if c in filtered.columns:
                actual_group_cols.append(c)
            elif c == "mandi_name" and "mandi_id" in filtered.columns:
                actual_group_cols.append("mandi_id")
            elif c == "mandi_id" and "mandi_name" in filtered.columns:
                actual_group_cols.append("mandi_name")
        if not actual_group_cols:
            actual_group_cols = ["mandi_id"] if "mandi_id" in filtered.columns else [filtered.columns[0]]

        # Exclude missing group keys (Section 13: never guess missing mandi ID)
        for c in actual_group_cols:
            filtered = filtered[filtered[c].notna()]
        filtered = filtered[filtered[metric].notna()]

        agg_func = intent.get("aggregation", "sum") if ds_name == "arrivals" else "average"
        if agg_func in ["average", "mean", "avg"]:
            grouped = filtered.groupby(actual_group_cols)[metric].mean().reset_index()
        elif agg_func in ["max", "maximum"]:
            grouped = filtered.groupby(actual_group_cols)[metric].max().reset_index()
        elif agg_func in ["min", "minimum"]:
            grouped = filtered.groupby(actual_group_cols)[metric].min().reset_index()
        else:
            grouped = filtered.groupby(actual_group_cols)[metric].sum().reset_index()

        ascending = (intent.get("operation") in ["lowest", "bottom", "min"])
        grouped = grouped.sort_values(by=metric, ascending=ascending)

        top_n = intent.get("top_n") or 5
        top_df = grouped.head(top_n).copy()

        # If grouped by mandi_id, attach mandi_name for display
        if "mandi_id" in top_df.columns and "mandi_name" not in top_df.columns:
            top_df["mandi_name"] = top_df["mandi_id"].apply(
                lambda mid: self.loader.mandi_id_to_name.get(str(mid).lower(), str(mid))
            )

        records = top_df.round(2).to_dict(orient="records")
        return {
            "records": records,
            "metric": metric,
            "group_by": "mandi_name" if "mandi_name" in top_df.columns else actual_group_cols[0],
            "total_records_analyzed": len(filtered),
            "operation": "lowest" if ascending else "highest",
            "top_n": top_n
        }

    def _execute_trend(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        ds_name = intent["datasets"][0]
        df = self.loader.get_dataset(ds_name)
        filtered = self._filter_df(df, intent.get("filters", {}))

        metric = intent.get("metric") or ("modal_price" if ds_name == "prices" else "arrival_quantity_qtl")
        filtered = filtered[filtered["date"].notna() & filtered[metric].notna()]

        # Group by date
        agg_func = "mean" if ds_name in ["prices", "weather_daily"] else "sum"
        if agg_func == "mean":
            grouped = filtered.groupby("date")[metric].mean().reset_index()
        else:
            grouped = filtered.groupby("date")[metric].sum().reset_index()

        grouped = grouped.sort_values(by="date")
        grouped[metric] = grouped[metric].round(2)
        records = grouped.to_dict(orient="records")

        # Trend analysis
        start_val = records[0][metric] if records else None
        end_val = records[-1][metric] if records else None
        overall_change = (end_val - start_val) if (start_val is not None and end_val is not None) else 0

        return {
            "records": records,
            "metric": metric,
            "start_date": records[0]["date"] if records else None,
            "end_date": records[-1]["date"] if records else None,
            "start_value": start_val,
            "end_value": end_val,
            "change": round(overall_change, 2),
            "trend_direction": "upward" if overall_change > 0 else "downward" if overall_change < 0 else "stable"
        }

    def _execute_comparison(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        ds_name = intent["datasets"][0]
        df = self.loader.get_dataset(ds_name)
        filters = intent.get("filters", {})
        metric = intent.get("metric") or ("modal_price" if ds_name == "prices" else "arrival_quantity_qtl")

        # Comparison entities: either mandis or crops
        compare_entities = intent.get("compare_entities", [])
        if not compare_entities and filters.get("mandi_name"):
            compare_entities = [filters["mandi_name"]]

        results = []
        for ent in compare_entities:
            sub_filter = filters.copy()
            if "crop" in intent.get("comparison_type", ""):
                sub_filter["crop_name"] = ent
                sub_df = self._filter_df(df, sub_filter)
                val = sub_df[metric].mean() if ds_name == "prices" else sub_df[metric].sum()
                results.append({"entity": ent, metric: round(val, 2) if pd.notna(val) else None})
            else:
                sub_filter["mandi_name"] = ent
                sub_df = self._filter_df(df, sub_filter)
                val = sub_df[metric].mean() if ds_name == "prices" else sub_df[metric].sum()
                results.append({"entity": ent, metric: round(val, 2) if pd.notna(val) else None})

        return {
            "records": results,
            "metric": metric,
            "comparison_dimension": intent.get("group_by", ["mandi_name"])[0] if intent.get("group_by") else "entity"
        }

    def _execute_period_comparison(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """Compares two distinct periods e.g. January vs August."""
        ds_name = intent["datasets"][0]
        df = self.loader.get_dataset(ds_name)
        filters = intent.get("filters", {})
        metric = intent.get("metric") or ("modal_price" if ds_name == "prices" else "arrival_quantity_qtl")

        p1_start = intent.get("period1_start", "2026-01-01")
        p1_end = intent.get("period1_end", "2026-01-31")
        p2_start = intent.get("period2_start", "2026-08-01")
        p2_end = intent.get("period2_end", "2026-08-31")

        f1 = self._filter_df(df, {**filters, "date_start": p1_start, "date_end": p1_end})
        f2 = self._filter_df(df, {**filters, "date_start": p2_start, "date_end": p2_end})

        val1 = f1[metric].mean() if ds_name == "prices" else f1[metric].sum()
        val2 = f2[metric].mean() if ds_name == "prices" else f2[metric].sum()

        records = [
            {"period": intent.get("period1_label", "Period 1"), metric: round(val1, 2) if pd.notna(val1) else None},
            {"period": intent.get("period2_label", "Period 2"), metric: round(val2, 2) if pd.notna(val2) else None},
        ]
        diff = (val2 - val1) if (pd.notna(val1) and pd.notna(val2)) else 0
        pct = (diff / val1 * 100) if (pd.notna(val1) and val1 != 0) else 0

        return {
            "records": records,
            "metric": metric,
            "period1_value": round(val1, 2) if pd.notna(val1) else None,
            "period2_value": round(val2, 2) if pd.notna(val2) else None,
            "absolute_diff": round(diff, 2),
            "percentage_change": round(pct, 2)
        }

    def _execute_msp_analysis(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """Analyzes market prices vs Minimum Support Price (MSP)."""
        df = self.loader.get_dataset("prices")
        filtered = self._filter_df(df, intent.get("filters", {}))
        filtered = filtered[filtered["modal_price"].notna() & filtered["msp"].notna()]

        # Compute difference and below MSP flag
        grouped = filtered.groupby("crop_name").agg(
            avg_modal_price=("modal_price", "mean"),
            msp=("msp", "first"),
            count=("record_id", "count")
        ).reset_index()

        grouped["difference"] = grouped["avg_modal_price"] - grouped["msp"]
        grouped["pct_diff"] = (grouped["difference"] / grouped["msp"]) * 100
        grouped["is_below_msp"] = grouped["avg_modal_price"] < grouped["msp"]

        records = grouped.round(2).to_dict(orient="records")
        below_msp_crops = [r["crop_name"] for r in records if r["is_below_msp"]]

        return {
            "records": records,
            "below_msp_crops": below_msp_crops,
            "metric": "avg_modal_price"
        }

    def _execute_cross_dataset(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """
        Cross-dataset analysis (Section 25 & 34):
        Weather (rainfall/temp) + Arrivals or Prices joined on date.
        Calculates Pearson correlation.
        Enforces: "The system may report correlation. It must NOT automatically claim causation."
        """
        w_df = self.loader.get_dataset("weather_daily")
        crop_filter = intent.get("filters", {}).get("crop_name", "Wheat")

        if "arrivals" in intent.get("datasets", []):
            target_df = self.loader.get_dataset("arrivals")
            target_metric = "arrival_quantity_qtl"
            target_name = "arrivals"
        else:
            target_df = self.loader.get_dataset("prices")
            target_metric = "modal_price"
            target_name = "prices"

        filtered_target = self._filter_df(target_df, {"crop_name": crop_filter})
        agg_func = "sum" if target_name == "arrivals" else "mean"
        daily_target = filtered_target.groupby("date")[target_metric].agg(agg_func).reset_index()

        # Merge on date
        merged = pd.merge(w_df, daily_target, on="date", how="inner")
        x_col = intent.get("x_metric", "total_rainfall_mm")
        if x_col not in merged.columns:
            x_col = "total_rainfall_mm" if "total_rainfall_mm" in merged.columns else "avg_temperature_c"

        merged = merged[[x_col, target_metric, "date"]].dropna()

        # Correlation calculation
        if len(merged) > 2 and merged[x_col].std() > 0 and merged[target_metric].std() > 0:
            corr_val = float(merged[x_col].corr(merged[target_metric]))
        else:
            corr_val = 0.0

        records = merged.round(2).to_dict(orient="records")
        return {
            "records": records,
            "x_metric": x_col,
            "y_metric": target_metric,
            "crop": crop_filter,
            "correlation": round(corr_val, 4),
            "correlation_strength": "positive" if corr_val > 0.3 else "negative" if corr_val < -0.3 else "weak",
            "relationship_statement": f"{x_col.replace('_', ' ').title()} and {crop_filter} {target_name} showed a {'positive' if corr_val > 0 else 'negative'} correlation of {corr_val:.2f} during the available period. This indicates a relationship but does not establish causation."
        }

    def _execute_high_arrivals_low_prices(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """
        Section 35: High Arrivals / Low Price
        High arrivals >= 75th percentile
        Low price <= 25th percentile
        The answer must state the threshold used.
        """
        arr_df = self.loader.get_dataset("arrivals")
        pr_df = self.loader.get_dataset("prices")
        crop_filter = intent.get("filters", {}).get("crop_name", "Wheat")

        arr_filtered = self._filter_df(arr_df, {"crop_name": crop_filter})
        pr_filtered = self._filter_df(pr_df, {"crop_name": crop_filter})

        # Filter records with valid mandi_id and mandi_name
        arr_mandi = arr_filtered.groupby(["mandi_id", "mandi_name"])["arrival_quantity_qtl"].sum().reset_index()
        # In prices, drop records where mandi_id is null (Section 13)
        pr_valid = pr_filtered[pr_filtered["mandi_id"].notna()]
        pr_mandi = pr_valid.groupby("mandi_id")["modal_price"].mean().reset_index()

        # Inner join on mandi_id
        merged = pd.merge(arr_mandi, pr_mandi, on="mandi_id", how="inner")

        # Compute 75th percentile of arrivals and 25th percentile of prices
        p75_arrival = float(merged["arrival_quantity_qtl"].quantile(HIGH_ARRIVAL_PERCENTILE))
        p25_price = float(merged["modal_price"].quantile(LOW_PRICE_PERCENTILE))

        matched = merged[
            (merged["arrival_quantity_qtl"] >= p75_arrival) &
            (merged["modal_price"] <= p25_price)
        ].copy()

        matched = matched.sort_values(by="arrival_quantity_qtl", ascending=False)
        records = matched.round(2).to_dict(orient="records")

        return {
            "records": records,
            "crop": crop_filter,
            "p75_arrival_threshold": round(p75_arrival, 2),
            "p25_price_threshold": round(p25_price, 2),
            "matched_mandis": [r["mandi_name"] for r in records],
            "threshold_statement": f"Defined thresholds: High arrivals >= 75th percentile ({p75_arrival:.2f} qtl) and Low price <= 25th percentile (₹{p25_price:.2f})."
        }

    def _execute_logistics(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        df = self.loader.get_dataset("transport")
        filtered = self._filter_df(df, intent.get("filters", {}))
        metric = intent.get("metric") or "transit_hours_final"
        group_by = intent.get("group_by") or ["destination_warehouse"]

        col = group_by[0]
        grouped = filtered.groupby(col).agg(
            avg_metric=(metric, "mean"),
            trip_count=("trip_id", "count"),
            avg_distance=("distance_km", "mean")
        ).reset_index()

        sort_col = "trip_count" if "warehouse" in col else "avg_metric"
        grouped = grouped.sort_values(by=sort_col, ascending=False)
        top_n = intent.get("top_n") or 5
        records = grouped.head(top_n).round(2).to_dict(orient="records")

        return {
            "records": records,
            "group_by": col,
            "metric": metric,
            "top_n": top_n
        }

    def _execute_mandi_summary(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """Provides a comprehensive overview for a specific mandi."""
        mandi_name = intent.get("filters", {}).get("mandi_name", "")
        mandi_id = intent.get("filters", {}).get("mandi_id", "")

        arr_df = self.loader.get_dataset("arrivals")
        pr_df = self.loader.get_dataset("prices")
        tr_df = self.loader.get_dataset("transport")

        sub_arr = self._filter_df(arr_df, {"mandi_name": mandi_name, "mandi_id": mandi_id})
        sub_pr = self._filter_df(pr_df, {"mandi_id": mandi_id}) if mandi_id else pd.DataFrame()
        sub_tr = self._filter_df(tr_df, {"mandi_name": mandi_name, "mandi_id": mandi_id})

        top_crops = sub_arr.groupby("crop_name")["arrival_quantity_qtl"].sum().sort_values(ascending=False).head(5)
        crop_records = [{"crop_name": k, "arrival_quantity_qtl": round(v, 2)} for k, v in top_crops.items()]

        avg_price = sub_pr["modal_price"].mean() if not sub_pr.empty and "modal_price" in sub_pr.columns else None
        total_arrivals = sub_arr["arrival_quantity_qtl"].sum() if not sub_arr.empty else 0
        total_trips = len(sub_tr)

        return {
            "mandi_name": mandi_name or mandi_id,
            "total_arrivals_qtl": round(total_arrivals, 2),
            "avg_modal_price": round(avg_price, 2) if avg_price is not None and pd.notna(avg_price) else None,
            "total_transport_trips": total_trips,
            "top_crops": crop_records,
            "records": crop_records
        }

    def _execute_standard_aggregation(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        datasets_list = intent.get("datasets") or ["arrivals"]
        ds_name = datasets_list[0] if datasets_list else "arrivals"
        df = self.loader.get_dataset(ds_name)
        filtered = self._filter_df(df, intent.get("filters", {}))
        metric = intent.get("metric") or ("arrival_quantity_qtl" if ds_name == "arrivals" else "modal_price")

        agg_op = intent.get("aggregation", "average")
        vals = filtered[metric].dropna()

        if agg_op in ["sum", "total"]:
            res_val = vals.sum()
        elif agg_op in ["min", "minimum"]:
            res_val = vals.min()
        elif agg_op in ["max", "maximum"]:
            res_val = vals.max()
        elif agg_op in ["count"]:
            res_val = float(len(vals))
        elif agg_op in ["median"]:
            res_val = vals.median()
        else:
            res_val = vals.mean()

        # Composition / Crop share if requested
        if intent.get("chart_type") == "pie" or intent.get("operation") == "share":
            comp = filtered.groupby("crop_name")[metric].sum().reset_index()
            comp = comp.sort_values(by=metric, ascending=False)
            records = comp.round(2).to_dict(orient="records")
            return {
                "records": records,
                "value": round(res_val, 2) if pd.notna(res_val) else None,
                "metric": metric,
                "operation": "share"
            }

        return {
            "records": [{"metric": metric, "value": round(res_val, 2) if pd.notna(res_val) else None}],
            "value": round(res_val, 2) if pd.notna(res_val) else None,
            "metric": metric,
            "total_records_analyzed": len(vals)
        }
