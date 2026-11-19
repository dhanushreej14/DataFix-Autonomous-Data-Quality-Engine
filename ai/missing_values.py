"""
DataFix - Autonomous Data Quality Engine
Module: Missing Value Detection & Strategy Engine (missing_values.py)

Responsible for:
- Auditing missing, null, and empty string values across all columns
- Calculating missing value percentages and row completeness
- Assessing distribution skewness for numerical features
- Recommending tailored imputation or removal strategies based on data type and missing ratio
- Returning structured, JSON-serializable diagnostic reports
"""

import io
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd

from profiler import infer_column_type, load_dataset


# Standard representation of nulls in raw text/csv
COMMON_NA_VALUES = {"", " ", "na", "n/a", "null", "none", "nan", "?", "-", "missing", "undefined"}


def detect_missing_values(
    data: Union[str, Path, io.IOBase, pd.DataFrame],
    treat_common_na_strings: bool = True
) -> Dict[str, Any]:
    """
    Analyzes missing values in a dataset.
    
    Args:
        data: CSV filepath, file buffer, or pandas DataFrame.
        treat_common_na_strings: If True, treats strings like 'N/A', '?', 'null' as missing.
        
    Returns:
        Structured JSON-compatible dictionary with missing statistics and strategy recommendations.
    """
    try:
        df = load_dataset(data)
    except Exception as e:
        return {
            "status": "error",
            "error_message": str(e),
            "total_missing_cells": 0,
            "overall_missing_percentage": 0.0,
            "columns": {}
        }

    total_rows = len(df)
    total_cols = len(df.columns)

    if total_rows == 0 or total_cols == 0:
        return {
            "status": "success",
            "total_rows": total_rows,
            "total_cols": total_cols,
            "total_missing_cells": 0,
            "overall_missing_percentage": 0.0,
            "affected_columns_count": 0,
            "columns": {},
            "recommendations": []
        }

    # Working copy to count standard + pseudo missing values
    work_df = df.copy()
    if treat_common_na_strings:
        for col in work_df.columns:
            if pd.api.types.is_object_dtype(work_df[col]) or pd.api.types.is_string_dtype(work_df[col]):
                # Map common placeholder strings to np.nan
                mask = work_df[col].astype(str).str.strip().str.lower().isin(COMMON_NA_VALUES)
                work_df.loc[mask, col] = np.nan

    total_cells = total_rows * total_cols
    col_missing_counts = work_df.isna().sum()
    total_missing_cells = int(col_missing_counts.sum())
    overall_missing_percentage = round((total_missing_cells / total_cells) * 100, 2)

    columns_report: Dict[str, Any] = {}
    recommendations: List[Dict[str, Any]] = []
    affected_columns: List[str] = []

    for col in df.columns:
        null_count = int(col_missing_counts[col])
        null_pct = round((null_count / total_rows) * 100, 2)
        non_null_count = total_rows - null_count
        series = work_df[col].dropna()
        col_type = infer_column_type(df[col])

        strategy, reason, alternatives = _recommend_strategy(
            col_name=str(col),
            series=series,
            col_type=col_type,
            null_count=null_count,
            null_pct=null_pct,
            total_rows=total_rows
        )

        col_data = {
            "column_name": str(col),
            "inferred_type": col_type,
            "null_count": null_count,
            "non_null_count": non_null_count,
            "null_percentage": null_pct,
            "has_missing": null_count > 0,
            "recommended_strategy": strategy,
            "reason": reason,
            "alternative_strategies": alternatives
        }

        columns_report[str(col)] = col_data

        if null_count > 0:
            affected_columns.append(str(col))
            recommendations.append({
                "column": str(col),
                "inferred_type": col_type,
                "null_count": null_count,
                "null_percentage": null_pct,
                "recommended_action": strategy,
                "explanation": reason,
                "suggested_imputation_value": _compute_suggested_value(series, strategy)
            })

    # Sort recommendations by missing percentage descending
    recommendations.sort(key=lambda x: x["null_percentage"], reverse=True)

    return {
        "status": "success",
        "total_rows": total_rows,
        "total_cols": total_cols,
        "total_missing_cells": total_missing_cells,
        "overall_missing_percentage": overall_missing_percentage,
        "affected_columns_count": len(affected_columns),
        "affected_columns": affected_columns,
        "columns": columns_report,
        "recommendations": recommendations
    }


def _recommend_strategy(
    col_name: str,
    series: pd.Series,
    col_type: str,
    null_count: int,
    null_pct: float,
    total_rows: int
) -> tuple[str, str, List[str]]:
    """Determines the optimal handling method based on data type, skewness, and missing percentage."""
    if null_count == 0:
        return "none_needed", "No missing values detected in this column.", []

    # High missingness threshold (> 60%)
    if null_pct > 60.0:
        return (
            "drop_column",
            f"High missingness ({null_pct}%). Imputing over 60% of values risks introducing severe bias.",
            ["flag_as_missing_indicator", "impute_with_constant"]
        )

    # Very low missingness in large dataset (< 2% and rows > 100)
    if null_pct < 2.0 and total_rows >= 100:
        return (
            "drop_rows",
            f"Very low missingness ({null_pct}%). Dropping missing rows preserves original data distribution without significant data loss.",
            ["impute_median" if col_type in ["integer", "float"] else "impute_mode"]
        )

    # Numerical columns
    if col_type in ["integer", "float"]:
        numeric_series = pd.to_numeric(series, errors="coerce").dropna()
        if len(numeric_series) > 2:
            skewness = float(numeric_series.skew())
            # Skewed distributions benefit from median over mean
            if abs(skewness) > 1.0:
                return (
                    "impute_median",
                    f"Distribution is skewed (skewness = {round(skewness, 2)}). Median is robust to outliers and preserves distribution center.",
                    ["impute_mean", "knn_impute", "drop_rows"]
                )
            else:
                return (
                    "impute_mean",
                    f"Distribution is approximately symmetric (skewness = {round(skewness, 2)}). Mean imputation preserves feature average.",
                    ["impute_median", "knn_impute", "drop_rows"]
                )
        return (
            "impute_median",
            "Median imputation recommended for numerical feature.",
            ["impute_mean", "impute_zero", "drop_rows"]
        )

    # Categorical columns
    if col_type == "categorical":
        if len(series) > 0:
            top_val = series.mode().iloc[0] if not series.mode().empty else "Unknown"
            top_freq = (series == top_val).mean()
            if top_freq > 0.6:
                return (
                    "impute_mode",
                    f"Dominant category '{top_val}' accounts for {round(top_freq * 100, 1)}% of values.",
                    ["impute_constant_unknown", "drop_rows"]
                )
        return (
            "impute_constant_unknown",
            "Imputing with a separate 'Unknown' or 'Missing' category avoids introducing artificial frequency bias.",
            ["impute_mode", "drop_rows"]
        )

    # Datetime columns
    if col_type == "datetime":
        return (
            "forward_fill",
            "Temporal data typically follows chronological order. Forward fill carries the last known valid timestamp.",
            ["backward_fill", "drop_rows"]
        )

    # Boolean columns
    if col_type == "boolean":
        return (
            "impute_mode",
            "Mode imputation fills missing booleans with the most frequent state.",
            ["impute_false_default", "drop_rows"]
        )

    # Fallback for text / other
    return (
        "impute_constant_unknown",
        "Imputing with 'Unknown' placeholder preserves row completeness for downstream tasks.",
        ["drop_rows"]
    )


def _compute_suggested_value(series: pd.Series, strategy: str) -> Any:
    """Computes a preview of the suggested replacement value for display in the UI."""
    if len(series) == 0:
        return None

    try:
        if strategy == "impute_median":
            num_s = pd.to_numeric(series, errors="coerce").dropna()
            return float(round(num_s.median(), 2)) if not num_s.empty else None
        elif strategy == "impute_mean":
            num_s = pd.to_numeric(series, errors="coerce").dropna()
            return float(round(num_s.mean(), 2)) if not num_s.empty else None
        elif strategy == "impute_mode":
            mode_vals = series.mode()
            return str(mode_vals.iloc[0]) if not mode_vals.empty else None
        elif strategy == "impute_constant_unknown":
            return "Unknown"
        elif strategy == "impute_zero":
            return 0
        elif strategy == "impute_false_default":
            return False
    except Exception:
        return None

    return None


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) > 1:
        res = detect_missing_values(sys.argv[1])
        print(json.dumps(res, indent=2))
    else:
        print("Usage: python missing_values.py <path_to_csv>")
