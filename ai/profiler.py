"""
DataFix - Autonomous Data Quality Engine
Module: Data Quality Profiler (profiler.py)

Responsible for:
- Ingesting CSV files, file-like objects, or pandas DataFrames
- Calculating dataset dimensions (rows, columns, cells)
- Inferring semantic data types (numeric, datetime, categorical, boolean, text)
- Auditing missing values and duplicates
- Generating column-level statistics and high-level dataset health metrics
- Returning clean, 100% JSON-serializable dictionaries for backend APIs
"""

import io
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd


def _to_serializable(val: Any) -> Any:
    """Helper to convert NumPy and pandas types into native JSON-serializable Python types."""
    if pd.isna(val) or val is None:
        return None
    if isinstance(val, (np.integer, int)):
        return int(val)
    if isinstance(val, (np.floating, float)):
        if np.isnan(val) or np.isinf(val):
            return None
        return float(round(val, 4))
    if isinstance(val, (np.bool_, bool)):
        return bool(val)
    if isinstance(val, (pd.Timestamp, np.datetime64)):
        return str(val)
    return str(val)


def infer_column_type(series: pd.Series) -> str:
    """
    Infers the high-level semantic type of a series.
    Returns one of: 'integer', 'float', 'datetime', 'boolean', 'categorical', 'text', 'empty'
    """
    non_null = series.dropna()
    if len(non_null) == 0:
        return "empty"

    # Boolean detection
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if non_null.isin([True, False, 0, 1, "true", "false", "True", "False", "TRUE", "FALSE"]).all() and non_null.nunique() <= 2:
        return "boolean"

    # Numeric detection
    if pd.api.types.is_integer_dtype(series):
        return "integer"
    if pd.api.types.is_float_dtype(series):
        # Check if float values are actually whole numbers
        if (non_null % 1 == 0).all():
            return "integer"
        return "float"

    # Datetime detection
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"

    # Try parsing sample strings as datetime if object type
    if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
        sample = non_null.head(50).astype(str)
        # Check if strings look like dates (at least contains hyphens, slashes, or colons)
        date_like_candidates = sample.str.contains(r"[-/:]", regex=True)
        if date_like_candidates.mean() > 0.8:
            try:
                pd.to_datetime(sample, errors="raise")
                return "datetime"
            except (ValueError, TypeError):
                pass

        # Try parsing strings as numeric
        try:
            converted = pd.to_numeric(sample, errors="raise")
            if (converted % 1 == 0).all():
                return "integer"
            return "float"
        except (ValueError, TypeError):
            pass

        # Categorical vs free text based on cardinality ratio
        unique_ratio = non_null.nunique() / len(non_null)
        if unique_ratio < 0.2 or non_null.nunique() <= 20:
            return "categorical"
        return "text"

    return "text"


def load_dataset(data: Union[str, Path, io.IOBase, pd.DataFrame]) -> pd.DataFrame:
    """
    Safely loads a CSV source (filepath, buffer, or DataFrame) into a pandas DataFrame.
    Raises ValueError on invalid formats or empty files.
    """
    if isinstance(data, pd.DataFrame):
        return data.copy()

    try:
        if isinstance(data, (str, Path)):
            path_obj = Path(data)
            if not path_obj.exists():
                raise FileNotFoundError(f"File not found: {data}")
            if path_obj.stat().st_size == 0:
                raise ValueError("The provided CSV file is completely empty (0 bytes).")
            df = pd.read_csv(data)
        elif hasattr(data, "read"):
            # File-like object (StringIO, BytesIO, UploadedFile)
            df = pd.read_csv(data)
        else:
            raise ValueError(f"Unsupported data input type: {type(data)}")

        return df

    except pd.errors.EmptyDataError:
        raise ValueError("The provided CSV contains no data or headers.")
    except Exception as e:
        raise ValueError(f"Failed to parse CSV dataset: {str(e)}")


def profile_dataset(data: Union[str, Path, io.IOBase, pd.DataFrame]) -> Dict[str, Any]:
    """
    Main profiling entrypoint.
    Inspects rows, columns, types, missingness, duplicate records, and summary statistics.

    Returns a structured, JSON-serializable dictionary.
    """
    try:
        df = load_dataset(data)
    except Exception as e:
        return {
            "status": "error",
            "error_message": str(e),
            "rows": 0,
            "columns": 0,
            "columns_profile": {},
            "summary": {}
        }

    total_rows = len(df)
    total_cols = len(df.columns)

    if total_rows == 0 or total_cols == 0:
        return {
            "status": "success",
            "rows": total_rows,
            "columns": total_cols,
            "column_names": list(df.columns),
            "columns_profile": {},
            "summary": {
                "total_cells": 0,
                "missing_cells": 0,
                "missing_percentage": 0.0,
                "duplicate_rows": 0,
                "duplicate_percentage": 0.0,
                "complete_rows": 0,
                "memory_usage_kb": 0.0
            }
        }

    # Count duplicates
    duplicate_rows_count = int(df.duplicated().sum())
    duplicate_percentage = round((duplicate_rows_count / total_rows) * 100, 2)

    # Missing counts
    total_cells = total_rows * total_cols
    total_missing_cells = int(df.isna().sum().sum())
    missing_percentage = round((total_missing_cells / total_cells) * 100, 2)
    complete_rows_count = int((~df.isna().any(axis=1)).sum())

    # Memory usage in KB
    memory_usage_kb = round(df.memory_usage(deep=True).sum() / 1024, 2)

    # Column-level profiles
    columns_profile: Dict[str, Any] = {}
    type_counts: Dict[str, int] = {}

    for col in df.columns:
        series = df[col]
        col_type = infer_column_type(series)
        type_counts[col_type] = type_counts.get(col_type, 0) + 1

        null_count = int(series.isna().sum())
        non_null_count = total_rows - null_count
        null_pct = round((null_count / total_rows) * 100, 2)
        unique_count = int(series.nunique(dropna=True))
        unique_pct = round((unique_count / non_null_count * 100), 2) if non_null_count > 0 else 0.0

        # Sample preview (first 5 unique non-null values)
        sample_vals = [_to_serializable(x) for x in series.dropna().unique()[:5]]

        col_stat: Dict[str, Any] = {
            "name": str(col),
            "inferred_type": col_type,
            "pandas_dtype": str(series.dtype),
            "non_null_count": non_null_count,
            "null_count": null_count,
            "null_percentage": null_pct,
            "unique_count": unique_count,
            "unique_percentage": unique_pct,
            "sample_values": sample_vals
        }

        # Numeric statistics
        if pd.api.types.is_numeric_dtype(series) and non_null_count > 0:
            col_stat["stats"] = {
                "min": _to_serializable(series.min()),
                "max": _to_serializable(series.max()),
                "mean": _to_serializable(series.mean()),
                "median": _to_serializable(series.median()),
                "std": _to_serializable(series.std()) if non_null_count > 1 else 0.0
            }
        elif col_type == "categorical" and non_null_count > 0:
            val_counts = series.value_counts(dropna=True).head(5).to_dict()
            col_stat["stats"] = {
                "top_categories": {str(k): int(v) for k, v in val_counts.items()}
            }

        columns_profile[str(col)] = col_stat

    return {
        "status": "success",
        "rows": total_rows,
        "columns": total_cols,
        "column_names": [str(c) for c in df.columns],
        "type_distribution": type_counts,
        "summary": {
            "total_cells": total_cells,
            "missing_cells": total_missing_cells,
            "missing_percentage": missing_percentage,
            "duplicate_rows": duplicate_rows_count,
            "duplicate_percentage": duplicate_percentage,
            "complete_rows": complete_rows_count,
            "complete_rows_percentage": round((complete_rows_count / total_rows) * 100, 2),
            "memory_usage_kb": memory_usage_kb
        },
        "columns_profile": columns_profile
    }


if __name__ == "__main__":
    import json
    import sys

    # Quick CLI test for developer
    if len(sys.argv) > 1:
        result = profile_dataset(sys.argv[1])
        print(json.dumps(result, indent=2))
    else:
        print("Usage: python profiler.py <path_to_csv>")
