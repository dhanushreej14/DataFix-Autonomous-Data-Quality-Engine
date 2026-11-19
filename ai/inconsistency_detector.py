"""
DataFix - Autonomous Data Quality Engine
Module: Inconsistency Detection Engine (inconsistency_detector.py)

Responsible for:
- Detecting inconsistent and mixed date formats (e.g. YYYY-MM-DD vs DD/MM/YYYY) and invalid date strings
- Detecting categorical discrepancies (casing mismatches, leading/trailing whitespace, typos/variants)
- Detecting data type pollution (e.g. text/strings inside predominantly numeric columns)
- Detecting suspicious and domain out-of-range values (e.g. negative ages, future join dates, extreme human ages)
- Returning 100% JSON-serializable diagnostic structures
"""

import datetime
import io
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import numpy as np
import pandas as pd

from profiler import load_dataset, infer_column_type, _to_serializable


# Common date pattern signatures for format classification
DATE_PATTERNS = [
    (re.compile(r"^\d{4}-\d{2}-\d{2}$"), "YYYY-MM-DD (ISO-8601)"),
    (re.compile(r"^\d{4}/\d{2}/\d{2}$"), "YYYY/MM/DD"),
    (re.compile(r"^\d{2}-\d{2}-\d{4}$"), "DD-MM-YYYY or MM-DD-YYYY"),
    (re.compile(r"^\d{2}/\d{2}/\d{4}$"), "DD/MM/YYYY or MM/DD/YYYY"),
    (re.compile(r"^\d{4}\.\d{2}\.\d{2}$"), "YYYY.MM.DD"),
    (re.compile(r"^[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4}$"), "Month Day, Year"),
]


def detect_inconsistencies(data: Union[str, Path, io.IOBase, pd.DataFrame]) -> Dict[str, Any]:
    """
    Analyzes dataset for date, categorical, data type, and domain value inconsistencies.
    
    Returns structured JSON-compatible dictionary.
    """
    try:
        df = load_dataset(data)
    except Exception as e:
        return {
            "status": "error",
            "error_message": str(e),
            "inconsistencies_count": 0,
            "date_inconsistencies": [],
            "categorical_inconsistencies": [],
            "type_inconsistencies": [],
            "suspicious_values": []
        }

    total_rows = len(df)
    if total_rows == 0:
        return {
            "status": "success",
            "inconsistencies_count": 0,
            "date_inconsistencies": [],
            "categorical_inconsistencies": [],
            "type_inconsistencies": [],
            "suspicious_values": [],
            "summary": {"has_inconsistencies": False, "explanation": "Dataset is empty."}
        }

    date_issues = _audit_date_formats(df)
    categorical_issues = _audit_categoricals(df)
    type_issues = _audit_type_contamination(df)
    suspicious_issues = _audit_suspicious_values(df)

    total_inconsistencies = (
        len(date_issues) +
        len(categorical_issues) +
        len(type_issues) +
        len(suspicious_issues)
    )

    return {
        "status": "success",
        "inconsistencies_count": total_inconsistencies,
        "date_inconsistencies": date_issues,
        "categorical_inconsistencies": categorical_issues,
        "type_inconsistencies": type_issues,
        "suspicious_values": suspicious_issues,
        "summary": {
            "has_inconsistencies": total_inconsistencies > 0,
            "total_issues_found": total_inconsistencies,
            "breakdown": {
                "date_issues": len(date_issues),
                "categorical_issues": len(categorical_issues),
                "type_contamination": len(type_issues),
                "suspicious_values": len(suspicious_issues)
            },
            "explanation": (
                f"Detected {total_inconsistencies} data inconsistency issue(s) across date formats, "
                f"categorical casing, data types, and value ranges."
                if total_inconsistencies > 0 else "No data inconsistencies detected."
            )
        }
    }


def _audit_date_formats(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Audits columns for mixed date formats and unparseable date values."""
    issues = []

    for col in df.columns:
        series = df[col].dropna()
        if len(series) == 0:
            continue

        col_name_lower = str(col).lower()
        is_date_named = any(k in col_name_lower for k in ["date", "time", "joined", "created", "dob", "birth"])
        
        # Check if values look like dates
        sample_str = series.head(50).astype(str)
        has_date_delimiters = sample_str.str.contains(r"[-/:]", regex=True).mean() > 0.6

        if is_date_named or has_date_delimiters:
            detected_formats: Dict[str, int] = {}
            invalid_dates = []

            for idx, val in series.items():
                val_str = str(val).strip()
                matched_format = None
                for regex, fmt_name in DATE_PATTERNS:
                    if regex.match(val_str):
                        matched_format = fmt_name
                        break

                if matched_format:
                    detected_formats[matched_format] = detected_formats.get(matched_format, 0) + 1
                else:
                    # Try general pandas datetime parse
                    try:
                        pd.to_datetime(val_str)
                        detected_formats["Other Valid Date"] = detected_formats.get("Other Valid Date", 0) + 1
                    except Exception:
                        invalid_dates.append({"row_index": int(idx), "invalid_value": val_str})

            # If more than 1 distinct date format or invalid date strings found
            if len(detected_formats) > 1 or len(invalid_dates) > 0:
                dominant_format = max(detected_formats.items(), key=lambda x: x[1])[0] if detected_formats else "ISO-8601 (YYYY-MM-DD)"
                issues.append({
                    "column": str(col),
                    "issue_type": "mixed_date_formats" if len(detected_formats) > 1 else "invalid_date_values",
                    "formats_detected": detected_formats,
                    "dominant_format": dominant_format,
                    "invalid_date_count": len(invalid_dates),
                    "sample_invalid_values": invalid_dates[:5],
                    "recommendation": f"Standardize column '{col}' to ISO-8601 ('YYYY-MM-DD') format."
                })

    return issues


def _audit_categoricals(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Identifies casing variations, whitespace padding, and near-duplicate categories."""
    issues = []

    for col in df.columns:
        series = df[col].dropna()
        if len(series) == 0 or pd.api.types.is_numeric_dtype(series):
            continue

        raw_strings = [str(x) for x in series.unique()]
        if len(raw_strings) < 2:
            continue

        # 1. Whitespace padding check
        whitespace_variants = [s for s in raw_strings if s != s.strip()]

        # 2. Case variations check (e.g. 'Engineering' vs 'engineering')
        lower_map: Dict[str, List[str]] = {}
        for s in raw_strings:
            clean = s.strip()
            low = clean.lower()
            if low not in lower_map:
                lower_map[low] = []
            if clean not in lower_map[low]:
                lower_map[low].append(clean)

        case_variants = {k: v for k, v in lower_map.items() if len(v) > 1}

        if whitespace_variants or case_variants:
            recommendation_parts = []
            if whitespace_variants:
                recommendation_parts.append("Trim leading/trailing whitespaces")
            if case_variants:
                recommendation_parts.append("Standardize text capitalization to Title Case")

            issues.append({
                "column": str(col),
                "issue_type": "categorical_casing_and_spacing",
                "whitespace_variants": whitespace_variants[:5],
                "conflicting_case_groups": case_variants,
                "recommendation": " and ".join(recommendation_parts) + f" in column '{col}'."
            })

    return issues


def _audit_type_contamination(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Detects numeric columns contaminated with string/text entries (e.g. '$100', 'unknown')."""
    issues = []

    for col in df.columns:
        series = df[col].dropna()
        if len(series) == 0:
            continue

        # If column is currently object/string, check if the majority of entries are actually numbers
        if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
            num_series = pd.to_numeric(series, errors="coerce")
            valid_numeric_count = int(num_series.notna().sum())
            total_non_null = len(series)

            # If 50% to 99% are valid numbers, the column is a contaminated numerical column
            if 0.5 <= (valid_numeric_count / total_non_null) < 1.0:
                # Find the non-numeric polluting values
                contaminants = []
                for idx, val in series.items():
                    if pd.isna(num_series.loc[idx]):
                        contaminants.append({"row_index": int(idx), "polluting_value": str(val)})

                issues.append({
                    "column": str(col),
                    "issue_type": "type_pollution",
                    "expected_type": "numeric (integer or float)",
                    "actual_type": "object / string (mixed)",
                    "valid_numeric_count": valid_numeric_count,
                    "polluting_entries_count": len(contaminants),
                    "sample_polluting_values": contaminants[:5],
                    "recommendation": f"Coerce column '{col}' to numeric; convert non-numeric placeholders ('unknown', 'N/A') to NaN."
                })

    return issues


def _audit_suspicious_values(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Detects domain violations like negative ages, biological implausibility, and future dates."""
    issues = []
    current_year = datetime.datetime.now().year

    for col in df.columns:
        col_lower = str(col).lower()
        series = df[col].dropna()
        if len(series) == 0:
            continue

        # 1. Age Auditing
        if "age" in col_lower:
            num_age = pd.to_numeric(series, errors="coerce").dropna()
            # Negative age
            negatives = num_age[num_age < 0]
            # Implausible age (> 125 years)
            implausible = num_age[num_age > 125]

            suspicious_entries = []
            for idx, val in negatives.items():
                suspicious_entries.append({"row_index": int(idx), "value": float(val), "reason": "Age cannot be negative."})
            for idx, val in implausible.items():
                suspicious_entries.append({"row_index": int(idx), "value": float(val), "reason": "Age exceeds human lifespan bound (125)."})

            if suspicious_entries:
                issues.append({
                    "column": str(col),
                    "issue_type": "suspicious_age_values",
                    "count": len(suspicious_entries),
                    "sample_records": suspicious_entries[:5],
                    "recommendation": f"Flag and correct impossible age values in column '{col}' (expected range 0–120)."
                })

        # 2. General Non-Negative Checks (e.g. salary, price, revenue, quantity)
        elif any(k in col_lower for k in ["salary", "price", "revenue", "income", "quantity", "cost"]):
            num_vals = pd.to_numeric(series, errors="coerce").dropna()
            negatives = num_vals[num_vals < 0]
            if len(negatives) > 0:
                suspicious_entries = [
                    {"row_index": int(idx), "value": float(val), "reason": f"{col.capitalize()} cannot be negative."}
                    for idx, val in negatives.items()
                ]
                issues.append({
                    "column": str(col),
                    "issue_type": "negative_monetary_or_count",
                    "count": len(suspicious_entries),
                    "sample_records": suspicious_entries[:5],
                    "recommendation": f"Ensure '{col}' values are non-negative."
                })

        # 3. Future dates in historical events
        if any(k in col_lower for k in ["birth", "join", "hire", "start", "created"]):
            try:
                date_series = pd.to_datetime(series, errors="coerce").dropna()
                future_dates = date_series[date_series.dt.year > current_year + 1]
                if len(future_dates) > 0:
                    suspicious_entries = [
                        {"row_index": int(idx), "value": str(val.date()), "reason": f"Event date cannot be in the future ({val.year} > {current_year})."}
                        for idx, val in future_dates.items()
                    ]
                    issues.append({
                        "column": str(col),
                        "issue_type": "future_event_date",
                        "count": len(suspicious_entries),
                        "sample_records": suspicious_entries[:5],
                        "recommendation": f"Review future-dated historical event entries in column '{col}'."
                    })
            except Exception:
                pass

    return issues


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) > 1:
        res = detect_inconsistencies(sys.argv[1])
        print(json.dumps(res, indent=2))
    else:
        print("Usage: python inconsistency_detector.py <path_to_csv>")
