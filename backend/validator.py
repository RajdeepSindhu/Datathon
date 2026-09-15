from typing import Dict, Any, List, Optional, Tuple
from .config import (
    ALLOWED_INTENTS,
    ALLOWED_DATASETS,
    APPROVED_COLUMNS,
    APPROVED_DIMENSIONS,
    APPROVED_METRICS,
    ALLOWED_AGGREGATIONS,
    DATASET_START_DATE,
    DATASET_END_DATE,
)
from .data_loader import DataLoader
from .entity_resolver import EntityResolver

class IntentValidator:
    def __init__(self):
        self.loader = DataLoader.get_instance()
        self.resolver = EntityResolver.get_instance()

    def validate(self, intent_dict: Dict[str, Any]) -> Tuple[bool, Dict[str, Any], Optional[str]]:
        """
        Validates structured intent against contract rules.
        Returns: (is_valid, validated_intent, error_or_clarification_message)
        """
        intent = intent_dict.get("intent", "").lower()
        if intent not in ALLOWED_INTENTS:
            return False, intent_dict, f"Unsupported intent '{intent}'. Allowed: {', '.join(sorted(ALLOWED_INTENTS))}"

        # If already flagged as clarification or unsupported by understanding agent
        if intent in ["clarification", "unsupported"]:
            return True, intent_dict, None

        # 1. Dataset validation
        datasets = intent_dict.get("datasets", [])
        if not datasets:
            return False, intent_dict, "No dataset specified for query."
        for ds in datasets:
            if ds not in ALLOWED_DATASETS:
                return False, intent_dict, f"Dataset '{ds}' is not approved for analytical queries. Allowed: {', '.join(sorted(ALLOWED_DATASETS))}"

        # 2. Relationship / Join validation
        if len(datasets) > 1:
            valid_join = False
            ds_set = set(datasets)
            if ds_set.issubset({"arrivals", "prices", "transport"}):
                valid_join = True  # shared mandi_id, or (date, mandi_id, crop_name)
            elif "weather_daily" in ds_set and (ds_set.issubset({"weather_daily", "arrivals"}) or ds_set.issubset({"weather_daily", "prices"})):
                valid_join = True  # shared date
            elif "weather_sensors" in ds_set and (ds_set.issubset({"weather_sensors", "arrivals"}) or ds_set.issubset({"weather_sensors", "prices"})):
                valid_join = True  # shared date
            elif ds_set.issubset({"arrivals", "prices", "weather_daily"}):
                valid_join = True

            if not valid_join:
                return False, intent_dict, f"No approved join relationship between datasets: {datasets}."

        # 3. Metric validation
        metric = intent_dict.get("metric")
        if metric:
            approved = False
            for ds in datasets:
                if metric in APPROVED_COLUMNS.get(ds, set()):
                    approved = True
                    break
            if not approved:
                return False, intent_dict, f"Metric '{metric}' is not an approved analytical column in datasets: {datasets}."

        # 4. Dimension / Group by validation
        group_by = intent_dict.get("group_by") or []
        for dim in group_by:
            if dim not in APPROVED_DIMENSIONS:
                return False, intent_dict, f"Dimension '{dim}' is not an approved grouping column."

        # 5. Entity resolution & validation
        filters = intent_dict.get("filters", {}) or {}
        
        # Crop validation
        crop_query = filters.get("crop_name")
        if crop_query:
            resolved_crop, conf, clarification = self.resolver.resolve_crop(crop_query)
            if clarification:
                return False, intent_dict, clarification
            filters["crop_name"] = resolved_crop

        # Mandi validation
        mandi_query = filters.get("mandi_name")
        if mandi_query:
            resolved_name, resolved_id, conf, clarification = self.resolver.resolve_mandi(mandi_query)
            if clarification:
                return False, intent_dict, clarification
            filters["mandi_name"] = resolved_name
            if resolved_id:
                filters["mandi_id"] = resolved_id

        # Section 13: Never assign a missing mandi ID by guessing
        # If mandi_id filter is specified, check existence
        if filters.get("mandi_id"):
            mid = filters["mandi_id"].strip().upper()
            if mid not in self.loader.mandi_ids:
                return False, intent_dict, f"Mandi ID '{mid}' does not exist in the database."

        # 6. Date validation
        d_start = filters.get("date_start")
        d_end = filters.get("date_end")
        if d_start and d_start > DATASET_END_DATE:
            return False, intent_dict, f"Requested date {d_start} is outside the available dataset period (2026-01-01 to 2026-09-09)."
        if d_end and d_end < DATASET_START_DATE:
            return False, intent_dict, f"Requested date {d_end} is outside the available dataset period (2026-01-01 to 2026-09-09)."

        # 7. Aggregation validation
        agg = intent_dict.get("aggregation")
        if agg:
            agg_map = {
                "mean": "average",
                "avg": "average",
                "total": "sum",
                "max": "maximum",
                "min": "minimum"
            }
            norm_agg = agg_map.get(agg.lower(), agg.lower())
            if norm_agg not in ALLOWED_AGGREGATIONS:
                return False, intent_dict, f"Aggregation '{agg}' is not supported. Allowed: {', '.join(sorted(ALLOWED_AGGREGATIONS))}"
            intent_dict["aggregation"] = norm_agg

        intent_dict["filters"] = filters
        return True, intent_dict, None
