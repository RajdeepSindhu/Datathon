import re
from typing import Optional, Tuple, Dict, Any
try:
    from rapidfuzz import process, fuzz
    HAS_RAPIDFUZZ = True
except ImportError:
    import difflib
    HAS_RAPIDFUZZ = False

from .data_loader import DataLoader

def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text

class EntityResolver:
    _instance: Optional["EntityResolver"] = None

    def __init__(self, data_loader: Optional[DataLoader] = None):
        self.loader = data_loader or DataLoader.get_instance()
        # Aliases & synonyms mapping (common Indian agricultural terms & typos)
        self.crop_aliases = {
            "wheet": "Wheat",
            "wheat": "Wheat",
            "gehun": "Wheat",
            "kapas": "Cotton",
            "sarson": "Mustard",
            "chana": "Gram",
            "dhan": "Rice",
            "paddy": "Rice",
            "aloo": "Potato",
            "tamatar": "Tomato",
            "pyaz": "Onion",
            "makka": "Maize",
            "corn": "Maize",
            "sugar cane": "Sugarcane",
        }

    @classmethod
    def get_instance(cls) -> "EntityResolver":
        if cls._instance is None:
            cls._instance = EntityResolver()
        return cls._instance

    def resolve_crop(self, query_crop: Optional[str]) -> Tuple[Optional[str], float, Optional[str]]:
        """
        Returns (resolved_crop, confidence, clarification_prompt)
        """
        if not query_crop or not query_crop.strip():
            return None, 1.0, None

        raw = query_crop.strip()
        norm = normalize_text(raw)

        # Check aliases first
        if norm in self.crop_aliases:
            alias_target = self.crop_aliases[norm]
            for c in self.loader.crops:
                if c.lower() == alias_target.lower():
                    return c, 1.0, None

        # 1. Exact match
        for c in self.loader.crops:
            if c.lower() == raw.lower():
                return c, 1.0, None

        # 2. Normalized match
        for c in self.loader.crops:
            if normalize_text(c) == norm:
                return c, 0.95, None

        # 3. Fuzzy match (comparing lowercase to lowercase)
        crops_list = list(self.loader.crops)
        crops_lower = [c.lower() for c in crops_list]
        if not crops_list:
            return raw, 0.5, f"Did you mean '{raw}'? Please confirm crop name."

        if HAS_RAPIDFUZZ:
            match = process.extractOne(norm, crops_lower, scorer=fuzz.ratio)
            if match:
                best_lower, score, idx = match
                confidence = score / 100.0
                best_name = crops_list[idx]
                if confidence >= 0.70:
                    return best_name, confidence, None
                elif confidence >= 0.45:
                    return None, confidence, f"Did you mean '{best_name}'? Please clarify."
        else:
            matches = difflib.get_close_matches(norm, crops_lower, n=1, cutoff=0.6)
            if matches:
                matched_norm = matches[0]
                for c in crops_list:
                    if c.lower() == matched_norm:
                        return c, 0.85, None

        return None, 0.0, f"Could not find crop '{query_crop}'. Available crops: {', '.join(sorted(crops_list)[:10])}..."

    def resolve_mandi(self, query_mandi: Optional[str]) -> Tuple[Optional[str], Optional[str], float, Optional[str]]:
        """
        Returns (resolved_mandi_name, resolved_mandi_id, confidence, clarification_prompt)
        """
        if not query_mandi or not query_mandi.strip():
            return None, None, 1.0, None

        raw = query_mandi.strip()
        norm = normalize_text(raw)

        # Direct Mandi ID match
        raw_upper = raw.upper()
        if raw_upper in self.loader.mandi_ids:
            mname = self.loader.mandi_id_to_name.get(raw.lower(), raw_upper)
            return mname, raw_upper, 1.0, None

        # 1. Exact match by name
        for m in self.loader.mandi_names:
            if m.lower() == raw.lower():
                mid = self.loader.mandi_name_to_id.get(m.lower())
                return m, mid, 1.0, None

        # 2. Substring / normalized match (e.g. "ludhiana" matches "Ludhiana Mandi")
        for m in self.loader.mandi_names:
            norm_m = normalize_text(m)
            if norm == norm_m or norm in norm_m.split():
                mid = self.loader.mandi_name_to_id.get(m.lower())
                return m, mid, 0.95, None

        # Also check if token is inside mandi name
        for m in self.loader.mandi_names:
            if norm in normalize_text(m):
                mid = self.loader.mandi_name_to_id.get(m.lower())
                return m, mid, 0.90, None

        # 3. Fuzzy match (comparing lowercase to lowercase)
        mandis_list = list(self.loader.mandi_names)
        mandis_lower = [m.lower() for m in mandis_list]
        if HAS_RAPIDFUZZ:
            match = process.extractOne(norm, mandis_lower, scorer=fuzz.partial_ratio)
            if match:
                best_lower, score, idx = match
                confidence = score / 100.0
                best_name = mandis_list[idx]
                if confidence >= 0.70:
                    mid = self.loader.mandi_name_to_id.get(best_name.lower())
                    return best_name, mid, confidence, None
                elif confidence >= 0.45:
                    return None, None, confidence, f"Did you mean '{best_name}'? Please clarify."

        return None, None, 0.0, f"Could not find mandi '{query_mandi}'. Please check the mandi name."
