import re
from datetime import datetime
from typing import Optional, Tuple
from .config import DATASET_START_DATE, DATASET_END_DATE

MONTHS_MAP = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12
}

def resolve_date_range(text: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Parses natural language date mentions into explicit (date_start, date_end) strings (YYYY-MM-DD),
    clamped to the dataset boundaries 2026-01-01 to 2026-09-09.
    """
    if not text:
        return None, None

    text_lower = text.lower().strip()

    # Relative expressions relative to latest data date (2026-09-09)
    if "today" in text_lower:
        return DATASET_END_DATE, DATASET_END_DATE
    if "yesterday" in text_lower:
        return "2026-09-08", "2026-09-08"
    if "this month" in text_lower:
        return "2026-09-01", DATASET_END_DATE
    if "last month" in text_lower:
        return "2026-08-01", "2026-08-31"

    # Quarters
    if "q1" in text_lower or "first quarter" in text_lower:
        return "2026-01-01", "2026-03-31"
    if "q2" in text_lower or "second quarter" in text_lower:
        return "2026-04-01", "2026-06-30"
    if "q3" in text_lower or "third quarter" in text_lower:
        return "2026-07-01", DATASET_END_DATE

    # Date range expressions: e.g. "from march to june", "january to september", "january to august"
    range_match = re.search(r"(?:from\s+)?([a-z]+)(?:\s+2026)?\s+(?:to|until|-)\s+([a-z]+)(?:\s+2026)?", text_lower)
    if range_match:
        m1, m2 = range_match.group(1), range_match.group(2)
        if m1 in MONTHS_MAP and m2 in MONTHS_MAP:
            start_m = MONTHS_MAP[m1]
            end_m = MONTHS_MAP[m2]
            start_date = f"2026-{start_m:02d}-01"
            if end_m == 9:
                end_date = DATASET_END_DATE
            elif end_m in [1, 3, 5, 7, 8, 10, 12]:
                end_date = f"2026-{end_m:02d}-31"
            elif end_m == 2:
                end_date = "2026-02-28"
            else:
                end_date = f"2026-{end_m:02d}-30"
            return clamp_date(start_date), clamp_date(end_date)

    # Single Month: e.g. "january", "august", "january 2026"
    for month_name, m_num in MONTHS_MAP.items():
        if re.search(rf"\b{month_name}\b", text_lower):
            start_date = f"2026-{m_num:02d}-01"
            if m_num == 9:
                end_date = DATASET_END_DATE
            elif m_num in [1, 3, 5, 7, 8, 10, 12]:
                end_date = f"2026-{m_num:02d}-31"
            elif m_num == 2:
                end_date = "2026-02-28"
            else:
                end_date = f"2026-{m_num:02d}-30"
            return clamp_date(start_date), clamp_date(end_date)

    # Explicit ISO date pattern: YYYY-MM-DD
    iso_dates = re.findall(r"\b2026-\d{2}-\d{2}\b", text)
    if len(iso_dates) == 1:
        d = clamp_date(iso_dates[0])
        return d, d
    elif len(iso_dates) >= 2:
        return clamp_date(iso_dates[0]), clamp_date(iso_dates[1])

    return None, None

def clamp_date(d_str: str) -> str:
    """Clamps date string strictly within available dataset range."""
    if d_str < DATASET_START_DATE:
        return DATASET_START_DATE
    if d_str > DATASET_END_DATE:
        return DATASET_END_DATE
    return d_str
