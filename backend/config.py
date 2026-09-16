import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "cross_dataset_final"

# Dataset file paths
DATASET_FILES = {
    "arrivals": DATA_DIR / "arrivals_final.csv",
    "prices": DATA_DIR / "price_and_msp_final.csv",
    "transport": DATA_DIR / "transport_logistics_final.csv",
    "weather_daily": DATA_DIR / "weather_daily.csv",
    "weather_sensors": DATA_DIR / "weather_sensors_final.csv",
    "recovery_audit": DATA_DIR / "cross_dataset_recovery_audit.csv",
}

# Contract Date Boundaries
DATASET_START_DATE = "2026-01-01"
DATASET_END_DATE = "2026-09-09"

# Allowed intents
ALLOWED_INTENTS = {
    "lookup",
    "aggregation",
    "ranking",
    "comparison",
    "trend",
    "period_comparison",
    "msp_analysis",
    "logistics_analysis",
    "weather_analysis",
    "cross_dataset_analysis",
    "multi_condition",
    "mandi_summary",
    "clarification",
    "unsupported",
}

# Allowed datasets for analytical queries (recovery audit explicitly excluded)
ALLOWED_DATASETS = {
    "arrivals",
    "prices",
    "transport",
    "weather_daily",
    "weather_sensors",
}

# Approved analytical columns per contract specifications
APPROVED_COLUMNS = {
    "arrivals": {
        "arrival_id",
        "date",
        "mandi_id",
        "crop_name",
        "variety",
        "farmer_count",
        "arrival_quantity_qtl",
        "mandi_name",
        "district",
        "state",
        "mandi_type",
    },
    "prices": {
        "record_id",
        "date",
        "mandi_id",
        "district_final",
        "crop_name",
        "min_price",
        "max_price",
        "modal_price",
        "msp",
    },
    "transport": {
        "trip_id",
        "mandi_id",
        "destination_warehouse",
        "distance_km",
        "departure_datetime",
        "arrival_datetime",
        "transit_hours_final",
        "vehicle_no_clean",
        "mandi_name",
        "district",
        "state",
        "mandi_type",
    },
    "weather_daily": {
        "date",
        "avg_temperature_c",
        "total_rainfall_mm",
        "avg_humidity",
        "sensor_count",
    },
    "weather_sensors": {
        "sensor_id",
        "timestamp_ist",
        "date",
        "temperature_c",
        "rainfall_mm",
        "humidity_percent",
    },
}

# Approved dimensions for filtering and grouping
APPROVED_DIMENSIONS = {
    "date",
    "mandi_id",
    "mandi_name",
    "district",
    "district_final",
    "state",
    "mandi_type",
    "crop_name",
    "variety",
    "destination_warehouse",
    "vehicle_no_clean",
    "sensor_id",
}

# Approved metrics per contract
APPROVED_METRICS = {
    "arrivals": ["arrival_quantity_qtl", "farmer_count"],
    "prices": ["modal_price", "min_price", "max_price", "msp"],
    "transport": ["distance_km", "transit_hours_final"],
    "weather_daily": ["avg_temperature_c", "total_rainfall_mm", "avg_humidity", "sensor_count"],
    "weather_sensors": ["temperature_c", "rainfall_mm", "humidity_percent"],
}

# Allowed aggregations
ALLOWED_AGGREGATIONS = {
    "sum",
    "average",
    "minimum",
    "maximum",
    "count",
    "median",
}

# Percentiles for High Arrivals / Low Price queries (Section 35)
HIGH_ARRIVAL_PERCENTILE = 0.75
LOW_PRICE_PERCENTILE = 0.25

# LLM Model Configuration
GEMINI_MODEL_ID = "gemini-2.5-flash"
FALLBACK_GEMINI_MODEL_ID = "gemini-2.5-flash"
GROQ_MODEL_ID = "openai/gpt-oss-120b"
FALLBACK_GROQ_MODEL_ID = "openai/gpt-oss-20b"
