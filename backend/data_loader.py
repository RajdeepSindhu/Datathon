import logging
from typing import Dict, Any, List, Set, Optional
import pandas as pd
import numpy as np
from .config import DATASET_FILES, APPROVED_COLUMNS, DATASET_START_DATE, DATASET_END_DATE

logger = logging.getLogger("mandi_chatbot.data_loader")

class DataLoader:
    _instance: Optional["DataLoader"] = None

    def __init__(self):
        self.datasets: Dict[str, pd.DataFrame] = {}
        self.crops: Set[str] = set()
        self.mandi_names: Set[str] = set()
        self.mandi_ids: Set[str] = set()
        self.districts: Set[str] = set()
        self.warehouses: Set[str] = set()
        self.mandi_name_to_id: Dict[str, str] = {}
        self.mandi_id_to_name: Dict[str, str] = {}
        self._load_datasets()

    @classmethod
    def get_instance(cls) -> "DataLoader":
        if cls._instance is None:
            cls._instance = DataLoader()
        return cls._instance

    def _load_datasets(self):
        logger.info("Loading datasets into memory...")

        # 1. arrivals_final.csv
        if DATASET_FILES["arrivals"].exists():
            df_arr = pd.read_csv(DATASET_FILES["arrivals"], low_memory=False)
            # Filter to approved analytical columns
            cols = [c for c in df_arr.columns if c in APPROVED_COLUMNS["arrivals"]]
            df_arr = df_arr[cols].copy()
            df_arr["date"] = pd.to_datetime(df_arr["date"]).dt.strftime("%Y-%m-%d")
            df_arr["arrival_quantity_qtl"] = pd.to_numeric(df_arr["arrival_quantity_qtl"], errors="coerce")
            df_arr["farmer_count"] = pd.to_numeric(df_arr["farmer_count"], errors="coerce")
            self.datasets["arrivals"] = df_arr
            logger.info(f"Loaded arrivals: {len(df_arr)} rows")
        else:
            logger.error(f"Missing arrivals dataset at {DATASET_FILES['arrivals']}")

        # 2. price_and_msp_final.csv
        if DATASET_FILES["prices"].exists():
            df_pr = pd.read_csv(DATASET_FILES["prices"], low_memory=False)
            cols = [c for c in df_pr.columns if c in APPROVED_COLUMNS["prices"] or c == "msp_was_imputed"]
            df_pr = df_pr[cols].copy()
            df_pr["date"] = pd.to_datetime(df_pr["date"]).dt.strftime("%Y-%m-%d")
            for num_col in ["min_price", "max_price", "modal_price", "msp"]:
                if num_col in df_pr.columns:
                    df_pr[num_col] = pd.to_numeric(df_pr[num_col], errors="coerce")
            self.datasets["prices"] = df_pr
            logger.info(f"Loaded prices: {len(df_pr)} rows")
        else:
            logger.error(f"Missing prices dataset at {DATASET_FILES['prices']}")

        # 3. transport_logistics_final.csv
        if DATASET_FILES["transport"].exists():
            df_tr = pd.read_csv(DATASET_FILES["transport"], low_memory=False)
            cols = [c for c in df_tr.columns if c in APPROVED_COLUMNS["transport"] or c == "transit_hours_imputed"]
            df_tr = df_tr[cols].copy()
            df_tr["distance_km"] = pd.to_numeric(df_tr["distance_km"], errors="coerce")
            df_tr["transit_hours_final"] = pd.to_numeric(df_tr["transit_hours_final"], errors="coerce")
            self.datasets["transport"] = df_tr
            logger.info(f"Loaded transport: {len(df_tr)} rows")
        else:
            logger.error(f"Missing transport dataset at {DATASET_FILES['transport']}")

        # 4. weather_daily.csv
        if DATASET_FILES["weather_daily"].exists():
            df_wd = pd.read_csv(DATASET_FILES["weather_daily"], low_memory=False)
            cols = [c for c in df_wd.columns if c in APPROVED_COLUMNS["weather_daily"]]
            df_wd = df_wd[cols].copy()
            df_wd["date"] = pd.to_datetime(df_wd["date"]).dt.strftime("%Y-%m-%d")
            for num_col in ["avg_temperature_c", "total_rainfall_mm", "avg_humidity", "sensor_count"]:
                if num_col in df_wd.columns:
                    df_wd[num_col] = pd.to_numeric(df_wd[num_col], errors="coerce")
            self.datasets["weather_daily"] = df_wd
            logger.info(f"Loaded weather_daily: {len(df_wd)} rows")
        else:
            logger.error(f"Missing weather_daily dataset at {DATASET_FILES['weather_daily']}")

        # 5. weather_sensors_final.csv
        if DATASET_FILES["weather_sensors"].exists():
            df_ws = pd.read_csv(DATASET_FILES["weather_sensors"], low_memory=False)
            cols = [c for c in df_ws.columns if c in APPROVED_COLUMNS["weather_sensors"]]
            df_ws = df_ws[cols].copy()
            df_ws["date"] = pd.to_datetime(df_ws["date"]).dt.strftime("%Y-%m-%d")
            for num_col in ["temperature_c", "rainfall_mm", "humidity_percent"]:
                if num_col in df_ws.columns:
                    df_ws[num_col] = pd.to_numeric(df_ws[num_col], errors="coerce")
            self.datasets["weather_sensors"] = df_ws
            logger.info(f"Loaded weather_sensors: {len(df_ws)} rows")
        else:
            logger.error(f"Missing weather_sensors dataset at {DATASET_FILES['weather_sensors']}")

        # Build Entity Indexes
        self._build_indexes()

    def _build_indexes(self):
        # Unique crops
        crops = set()
        if "arrivals" in self.datasets:
            crops.update(self.datasets["arrivals"]["crop_name"].dropna().unique())
        if "prices" in self.datasets:
            crops.update(self.datasets["prices"]["crop_name"].dropna().unique())
        self.crops = {str(c).strip() for c in crops if str(c).strip()}

        # Mandis & mapping
        mandi_map = {}
        id_map = {}
        if "arrivals" in self.datasets:
            sub = self.datasets["arrivals"][["mandi_id", "mandi_name"]].dropna().drop_duplicates()
            for _, r in sub.iterrows():
                mid = str(r["mandi_id"]).strip()
                mname = str(r["mandi_name"]).strip()
                if mid and mname:
                    mandi_map[mname.lower()] = mid
                    id_map[mid.lower()] = mname
                    self.mandi_names.add(mname)
                    self.mandi_ids.add(mid)

        if "transport" in self.datasets:
            sub = self.datasets["transport"][["mandi_id", "mandi_name"]].dropna().drop_duplicates()
            for _, r in sub.iterrows():
                mid = str(r["mandi_id"]).strip()
                mname = str(r["mandi_name"]).strip()
                if mid and mname:
                    mandi_map[mname.lower()] = mid
                    id_map[mid.lower()] = mname
                    self.mandi_names.add(mname)
                    self.mandi_ids.add(mid)

        self.mandi_name_to_id = mandi_map
        self.mandi_id_to_name = id_map

        # Districts
        districts = set()
        if "arrivals" in self.datasets and "district" in self.datasets["arrivals"].columns:
            districts.update(self.datasets["arrivals"]["district"].dropna().unique())
        if "prices" in self.datasets and "district_final" in self.datasets["prices"].columns:
            districts.update(self.datasets["prices"]["district_final"].dropna().unique())
        self.districts = {str(d).strip() for d in districts if str(d).strip()}

        # Warehouses
        if "transport" in self.datasets and "destination_warehouse" in self.datasets["transport"].columns:
            self.warehouses = {str(w).strip() for w in self.datasets["transport"]["destination_warehouse"].dropna().unique() if str(w).strip()}

        logger.info(f"Indexed {len(self.crops)} crops, {len(self.mandi_names)} mandis, {len(self.districts)} districts, {len(self.warehouses)} warehouses.")

    def get_dataset(self, name: str) -> Optional[pd.DataFrame]:
        return self.datasets.get(name)

    def get_entity_dictionaries(self) -> Dict[str, Any]:
        return {
            "crops": sorted(list(self.crops)),
            "mandis": sorted(list(self.mandi_names)),
            "mandi_ids": sorted(list(self.mandi_ids)),
            "districts": sorted(list(self.districts)),
            "warehouses": sorted(list(self.warehouses)),
            "date_range": {"start": DATASET_START_DATE, "end": DATASET_END_DATE}
        }
