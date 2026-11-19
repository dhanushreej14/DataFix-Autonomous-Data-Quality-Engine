"""Automated Data Profiling Module for DataFix Engine.

This module provides comprehensive dataset inspection, statistical profiling,
missing value analysis, duplicate row detection, column-level characteristics,
and data quality scoring with automated health alerts.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Utility Conversion Helper
# ---------------------------------------------------------------------------

def _to_native_scalar(val: Any) -> Any:
    """Convert numpy scalars or NaN/inf values to standard Python types.

    Ensures JSON compatibility and eliminates serialization errors.
    """
    if val is None:
        return None
    if isinstance(val, (bool, np.bool_)):
        return bool(val)
    if isinstance(val, (int, np.integer)):
        return int(val)
    if isinstance(val, (float, np.floating)):
        if math.isnan(val) or np.isnan(val):
            return None
        if math.isinf(val) or np.isinf(val):
            return None
        return round(float(val), 4)
    if pd.isna(val):
        return None
    return str(val)


# ---------------------------------------------------------------------------
# 1. Dataset Overview
# ---------------------------------------------------------------------------

def get_dataset_overview(df: pd.DataFrame) -> Dict[str, Any]:
    """Calculate high-level structural dimensions and memory metrics of a dataset.

    Parameters
    ----------
    df : pd.DataFrame
        The dataset to inspect.

    Returns
    -------
    Dict[str, Any]
        Dictionary containing row count, column count, total cells, and memory usage.
    """
    if df is None:
        raise ValueError("DataFrame cannot be None.")

    total_rows = int(df.shape[0])
    total_columns = int(df.shape[1])
    total_cells = total_rows * total_columns

    # Deep memory calculation
    try:
        memory_bytes = int(df.memory_usage(deep=True).sum())
    except Exception:
        memory_bytes = int(df.memory_usage().sum())

    memory_mb = round(memory_bytes / (1024 * 1024), 4)

    return {
        "total_rows": total_rows,
        "total_columns": total_columns,
        "total_cells": total_cells,
        "memory_usage_bytes": memory_bytes,
        "memory_usage_mb": memory_mb,
        "is_empty": bool(df.empty),
    }


# ---------------------------------------------------------------------------
# 2. Column Names & Data Types
# ---------------------------------------------------------------------------

def get_column_types(df: pd.DataFrame) -> Dict[str, Any]:
    """Classify and map dataset columns into standard data type categories.

    Parameters
    ----------
    df : pd.DataFrame
        The dataset to inspect.

    Returns
    -------
    Dict[str, Any]
        Classification breakdown including column names, dtypes, and grouped lists.
    """
    if df is None:
        raise ValueError("DataFrame cannot be None.")

    column_types: Dict[str, str] = {}
    numerical_cols: List[str] = []
    categorical_cols: List[str] = []
    datetime_cols: List[str] = []
    boolean_cols: List[str] = []

    for col in df.columns:
        col_str = str(col)
        dtype = df[col].dtype

        if pd.api.types.is_bool_dtype(dtype):
            boolean_cols.append(col_str)
            column_types[col_str] = "boolean"
        elif pd.api.types.is_numeric_dtype(dtype):
            numerical_cols.append(col_str)
            column_types[col_str] = str(dtype)
        elif pd.api.types.is_datetime64_any_dtype(dtype):
            datetime_cols.append(col_str)
            column_types[col_str] = "datetime"
        else:
            categorical_cols.append(col_str)
            column_types[col_str] = "categorical" if isinstance(dtype, pd.CategoricalDtype) else "object"

    return {
        "columns": [str(c) for c in df.columns],
        "dtypes": column_types,
        "numerical_columns": numerical_cols,
        "categorical_columns": categorical_cols,
        "datetime_columns": datetime_cols,
        "boolean_columns": boolean_cols,
        "counts": {
            "numerical": len(numerical_cols),
            "categorical": len(categorical_cols),
            "datetime": len(datetime_cols),
            "boolean": len(boolean_cols),
            "total": len(df.columns),
        },
    }


# ---------------------------------------------------------------------------
# 3. Missing Value Analysis
# ---------------------------------------------------------------------------

def get_missing_values(df: pd.DataFrame) -> Dict[str, Any]:
    """Analyze missing (null / NaN / NaT) values across columns and rows.

    Parameters
    ----------
    df : pd.DataFrame
        The dataset to inspect.

    Returns
    -------
    Dict[str, Any]
        Per-column missing stats and global missing cell summaries.
    """
    if df is None:
        raise ValueError("DataFrame cannot be None.")

    total_rows = len(df)
    total_cells = total_rows * len(df.columns) if total_rows > 0 else 0

    null_counts = df.isna().sum()
    column_missing: Dict[str, Dict[str, Any]] = {}
    cols_with_missing: List[str] = []
    complete_cols: List[str] = []

    for col in df.columns:
        col_str = str(col)
        missing_count = int(null_counts[col])
        missing_pct = round((missing_count / total_rows * 100), 2) if total_rows > 0 else 0.0
        present_count = total_rows - missing_count
        present_pct = round(100.0 - missing_pct, 2)

        column_missing[col_str] = {
            "missing_count": missing_count,
            "missing_percentage": missing_pct,
            "present_count": present_count,
            "present_percentage": present_pct,
        }

        if missing_count > 0:
            cols_with_missing.append(col_str)
        else:
            complete_cols.append(col_str)

    total_missing_cells = int(null_counts.sum())
    missing_cells_pct = round((total_missing_cells / total_cells * 100), 2) if total_cells > 0 else 0.0

    rows_with_any_missing = int(df.isna().any(axis=1).sum()) if total_rows > 0 else 0
    rows_with_missing_pct = round((rows_with_any_missing / total_rows * 100), 2) if total_rows > 0 else 0.0

    return {
        "columns": column_missing,
        "total_missing_cells": total_missing_cells,
        "total_cells": total_cells,
        "missing_cells_percentage": missing_cells_pct,
        "columns_with_missing": cols_with_missing,
        "columns_with_missing_count": len(cols_with_missing),
        "complete_columns": complete_cols,
        "complete_columns_count": len(complete_cols),
        "rows_with_missing_count": rows_with_any_missing,
        "rows_with_missing_percentage": rows_with_missing_pct,
    }


# ---------------------------------------------------------------------------
# 4. Duplicate Row Detection
# ---------------------------------------------------------------------------

def get_duplicate_summary(df: pd.DataFrame) -> Dict[str, Any]:
    """Detect and summarize identical duplicate rows in the dataset.

    Parameters
    ----------
    df : pd.DataFrame
        The dataset to inspect.

    Returns
    -------
    Dict[str, Any]
        Duplicate counts, percentages, and duplicate existence flag.
    """
    if df is None:
        raise ValueError("DataFrame cannot be None.")

    total_rows = len(df)
    if total_rows == 0:
        return {
            "duplicate_rows_count": 0,
            "duplicate_rows_percentage": 0.0,
            "unique_rows_count": 0,
            "has_duplicates": False,
        }

    duplicate_mask = df.duplicated()
    dup_count = int(duplicate_mask.sum())
    dup_pct = round((dup_count / total_rows * 100), 2)
    unique_count = total_rows - dup_count

    return {
        "duplicate_rows_count": dup_count,
        "duplicate_rows_percentage": dup_pct,
        "unique_rows_count": unique_count,
        "has_duplicates": dup_count > 0,
    }


# ---------------------------------------------------------------------------
# 5. Unique Values & Cardinality Analysis
# ---------------------------------------------------------------------------

def get_unique_values(df: pd.DataFrame) -> Dict[str, Any]:
    """Compute unique value counts and cardinality classifications for each column.

    Parameters
    ----------
    df : pd.DataFrame
        The dataset to inspect.

    Returns
    -------
    Dict[str, Any]
        Per-column unique counts, uniqueness percentages, and cardinality classifications.
    """
    if df is None:
        raise ValueError("DataFrame cannot be None.")

    total_rows = len(df)
    unique_summary: Dict[str, Dict[str, Any]] = {}

    for col in df.columns:
        col_str = str(col)
        # Unique non-null count
        n_unique = int(df[col].nunique(dropna=True))
        unique_pct = round((n_unique / total_rows * 100), 2) if total_rows > 0 else 0.0

        is_constant = (n_unique == 1)
        is_unique = (n_unique == total_rows and total_rows > 0)

        # Cardinality category
        if is_constant:
            cardinality = "constant"
        elif n_unique == 2:
            cardinality = "binary"
        elif is_unique:
            cardinality = "unique_identifier"
        elif n_unique <= 10:
            cardinality = "low"
        elif n_unique <= 100:
            cardinality = "medium"
        else:
            cardinality = "high"

        unique_summary[col_str] = {
            "unique_count": n_unique,
            "unique_percentage": unique_pct,
            "is_constant": is_constant,
            "is_unique": is_unique,
            "cardinality": cardinality,
        }

    return {"columns": unique_summary}


# ---------------------------------------------------------------------------
# 6. Numerical Column Statistics
# ---------------------------------------------------------------------------

def get_numerical_summary(df: pd.DataFrame) -> Dict[str, Any]:
    """Calculate descriptive statistics, distributions, and IQR outliers for numeric columns.

    Parameters
    ----------
    df : pd.DataFrame
        The dataset to inspect.

    Returns
    -------
    Dict[str, Any]
        Dictionary of statistics keyed by numerical column name.
    """
    if df is None:
        raise ValueError("DataFrame cannot be None.")

    numeric_df = df.select_dtypes(include=[np.number])
    summary: Dict[str, Dict[str, Any]] = {}

    for col in numeric_df.columns:
        col_str = str(col)
        series = df[col].dropna()
        n = len(series)

        if n == 0:
            summary[col_str] = {
                "count": 0,
                "missing_count": int(df[col].isna().sum()),
                "mean": None,
                "std": None,
                "min": None,
                "q25": None,
                "median": None,
                "q75": None,
                "max": None,
                "range": None,
                "iqr": None,
                "skewness": None,
                "kurtosis": None,
                "zeros_count": 0,
                "zeros_percentage": 0.0,
                "negatives_count": 0,
                "negatives_percentage": 0.0,
                "outliers_count": 0,
                "outliers_percentage": 0.0,
                "outlier_bounds": {"lower": None, "upper": None},
            }
            continue

        q25 = float(series.quantile(0.25))
        q75 = float(series.quantile(0.75))
        median = float(series.median())
        mean = float(series.mean())
        std = float(series.std()) if n > 1 else 0.0
        c_min = float(series.min())
        c_max = float(series.max())
        c_range = c_max - c_min
        iqr = q75 - q25

        # Outlier bounds using Tukey's 1.5 * IQR rule
        lower_bound = q25 - 1.5 * iqr
        upper_bound = q75 + 1.5 * iqr
        outlier_mask = (series < lower_bound) | (series > upper_bound)
        outliers_count = int(outlier_mask.sum())
        outliers_pct = round((outliers_count / n * 100), 2)

        zeros_count = int((series == 0).sum())
        zeros_pct = round((zeros_count / n * 100), 2)

        neg_count = int((series < 0).sum())
        neg_pct = round((neg_count / n * 100), 2)

        # Skewness and kurtosis
        skew = float(series.skew()) if n >= 3 else None
        kurt = float(series.kurt()) if n >= 4 else None

        summary[col_str] = {
            "count": n,
            "missing_count": int(df[col].isna().sum()),
            "mean": _to_native_scalar(mean),
            "std": _to_native_scalar(std),
            "min": _to_native_scalar(c_min),
            "q25": _to_native_scalar(q25),
            "median": _to_native_scalar(median),
            "q75": _to_native_scalar(q75),
            "max": _to_native_scalar(c_max),
            "range": _to_native_scalar(c_range),
            "iqr": _to_native_scalar(iqr),
            "skewness": _to_native_scalar(skew),
            "kurtosis": _to_native_scalar(kurt),
            "zeros_count": zeros_count,
            "zeros_percentage": zeros_pct,
            "negatives_count": neg_count,
            "negatives_percentage": neg_pct,
            "outliers_count": outliers_count,
            "outliers_percentage": outliers_pct,
            "outlier_bounds": {
                "lower": _to_native_scalar(lower_bound),
                "upper": _to_native_scalar(upper_bound),
            },
        }

    return summary


# ---------------------------------------------------------------------------
# 7. Categorical Column Statistics
# ---------------------------------------------------------------------------

def get_categorical_summary(df: pd.DataFrame, top_n: int = 10) -> Dict[str, Any]:
    """Calculate frequency distributions, cardinality, and mode for categorical columns.

    Parameters
    ----------
    df : pd.DataFrame
        The dataset to inspect.
    top_n : int, default 10
        Maximum number of most frequent items to record per column.

    Returns
    -------
    Dict[str, Any]
        Dictionary of categorical statistics keyed by column name.
    """
    if df is None:
        raise ValueError("DataFrame cannot be None.")

    # Exclude purely numerical columns; include object, string, category, bool
    cat_df = df.select_dtypes(include=["object", "category", "string", "bool"])
    summary: Dict[str, Dict[str, Any]] = {}

    for col in cat_df.columns:
        col_str = str(col)
        series = df[col].dropna()
        n = len(series)
        missing_count = int(df[col].isna().sum())

        if n == 0:
            summary[col_str] = {
                "count": 0,
                "missing_count": missing_count,
                "unique_count": 0,
                "mode": None,
                "mode_frequency": 0,
                "mode_percentage": 0.0,
                "top_values": [],
            }
            continue

        value_counts = series.value_counts()
        n_unique = int(len(value_counts))

        top_val = value_counts.index[0]
        mode_str = str(top_val)
        mode_freq = int(value_counts.iloc[0])
        mode_pct = round((mode_freq / n * 100), 2)

        top_values_list = []
        for val, count in value_counts.head(top_n).items():
            top_values_list.append({
                "value": str(val),
                "count": int(count),
                "percentage": round((int(count) / n * 100), 2),
            })

        summary[col_str] = {
            "count": n,
            "missing_count": missing_count,
            "unique_count": n_unique,
            "mode": mode_str,
            "mode_frequency": mode_freq,
            "mode_percentage": mode_pct,
            "top_values": top_values_list,
        }

    return summary


# ---------------------------------------------------------------------------
# 8. Basic Data Quality Summary & Alerts
# ---------------------------------------------------------------------------

def get_data_quality_summary(df: pd.DataFrame) -> Dict[str, Any]:
    """Compute overall quality scores, sub-dimension metrics, and actionable quality alerts.

    Quality Dimensions:
    - Completeness (40% weight): Ratio of populated cells.
    - Uniqueness (30% weight): Ratio of non-duplicate rows.
    - Consistency / Outlier Health (15% weight): Ratio of non-outlier numeric values.
    - Structural Health (15% weight): Penalized for constant columns or entirely empty columns.

    Parameters
    ----------
    df : pd.DataFrame
        The dataset to inspect.

    Returns
    -------
    Dict[str, Any]
        Health scores, rating grade, and prioritized alert messages.
    """
    if df is None:
        raise ValueError("DataFrame cannot be None.")

    total_rows = len(df)
    total_cols = len(df.columns)
    total_cells = total_rows * total_cols

    if total_rows == 0 or total_cols == 0:
        return {
            "overall_score": 0.0,
            "rating": "Poor",
            "completeness_score": 0.0,
            "uniqueness_score": 0.0,
            "validity_score": 0.0,
            "structural_score": 0.0,
            "alerts": [{
                "level": "critical",
                "column": "all",
                "message": "Dataset is empty (contains 0 rows or 0 columns).",
            }],
            "alerts_summary": {
                "critical": 1,
                "warning": 0,
                "info": 0,
                "total": 1,
            },
        }

    alerts: List[Dict[str, Any]] = []

    # 1. Completeness Score
    null_counts = df.isna().sum()
    total_nulls = int(null_counts.sum())
    completeness_score = round(max(0.0, (1.0 - (total_nulls / total_cells))) * 100, 2)

    # 2. Uniqueness Score
    dup_count = int(df.duplicated().sum())
    uniqueness_score = round(max(0.0, (1.0 - (dup_count / total_rows))) * 100, 2)

    # 3. Validity / Outliers Score
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    total_numeric_values = 0
    total_outliers = 0

    for col in numeric_cols:
        series = df[col].dropna()
        n = len(series)
        if n >= 4:
            q25 = float(series.quantile(0.25))
            q75 = float(series.quantile(0.75))
            iqr = q75 - q25
            if iqr > 0:
                low = q25 - 1.5 * iqr
                high = q75 + 1.5 * iqr
                outliers = int(((series < low) | (series > high)).sum())
                total_outliers += outliers
                total_numeric_values += n

    if total_numeric_values > 0:
        validity_score = round(max(0.0, (1.0 - (total_outliers / total_numeric_values))) * 100, 2)
    else:
        validity_score = 100.0

    # 4. Structural Score
    constant_columns = []
    empty_columns = []
    for col in df.columns:
        col_str = str(col)
        n_missing = int(null_counts[col])
        if n_missing == total_rows:
            empty_columns.append(col_str)
        else:
            if int(df[col].nunique(dropna=True)) == 1:
                constant_columns.append(col_str)

    structural_penalty = (len(empty_columns) * 15.0) + (len(constant_columns) * 5.0)
    structural_score = round(max(0.0, 100.0 - structural_penalty), 2)

    # Overall Weighted Score
    overall_score = round(
        (completeness_score * 0.40) +
        (uniqueness_score * 0.30) +
        (validity_score * 0.15) +
        (structural_score * 0.15),
        2,
    )

    # Grade assignment
    if overall_score >= 90.0:
        rating = "Excellent"
    elif overall_score >= 75.0:
        rating = "Good"
    elif overall_score >= 60.0:
        rating = "Fair"
    else:
        rating = "Poor"

    # Generate Alert Rules
    # Rule A: Duplicates
    if dup_count > 0:
        dup_pct = round((dup_count / total_rows * 100), 2)
        alerts.append({
            "level": "warning" if dup_pct < 10.0 else "critical",
            "column": "dataset",
            "message": f"Found {dup_count} duplicate row(s) ({dup_pct}% of dataset).",
        })

    # Rule B: Missing values
    for col in df.columns:
        col_str = str(col)
        n_missing = int(null_counts[col])
        if n_missing > 0:
            missing_pct = round((n_missing / total_rows * 100), 2)
            if missing_pct == 100.0:
                alerts.append({
                    "level": "critical",
                    "column": col_str,
                    "message": f"Column '{col_str}' is completely empty (100% missing values).",
                })
            elif missing_pct >= 50.0:
                alerts.append({
                    "level": "critical",
                    "column": col_str,
                    "message": f"Column '{col_str}' has severe missingness: {n_missing} missing ({missing_pct}%).",
                })
            elif missing_pct >= 15.0:
                alerts.append({
                    "level": "warning",
                    "column": col_str,
                    "message": f"Column '{col_str}' has moderate missingness: {n_missing} missing ({missing_pct}%).",
                })
            elif missing_pct > 0.0:
                alerts.append({
                    "level": "info",
                    "column": col_str,
                    "message": f"Column '{col_str}' contains {n_missing} missing value(s) ({missing_pct}%).",
                })

    # Rule C: Constant columns
    for col_str in constant_columns:
        alerts.append({
            "level": "warning",
            "column": col_str,
            "message": f"Column '{col_str}' has zero variance (constant single value across all rows).",
        })

    # Rule D: High Outliers in Numerical columns
    for col in numeric_cols:
        col_str = str(col)
        series = df[col].dropna()
        n = len(series)
        if n >= 10:
            q25 = float(series.quantile(0.25))
            q75 = float(series.quantile(0.75))
            iqr = q75 - q25
            if iqr > 0:
                outliers = int(((series < (q25 - 1.5 * iqr)) | (series > (q75 + 1.5 * iqr))).sum())
                outlier_pct = round((outliers / n * 100), 2)
                if outlier_pct >= 10.0:
                    alerts.append({
                        "level": "warning",
                        "column": col_str,
                        "message": f"Column '{col_str}' contains high outlier concentration: {outliers} outliers ({outlier_pct}%).",
                    })

    # Rule E: High cardinality in categorical columns (potential unindexed IDs)
    cat_cols = df.select_dtypes(include=["object", "string"]).columns
    for col in cat_cols:
        col_str = str(col)
        n_unique = int(df[col].nunique(dropna=True))
        if total_rows > 20 and n_unique == total_rows:
            alerts.append({
                "level": "info",
                "column": col_str,
                "message": f"Column '{col_str}' has 100% unique values (potential identifier or index column).",
            })

    # Alert counts
    crit_count = sum(1 for a in alerts if a["level"] == "critical")
    warn_count = sum(1 for a in alerts if a["level"] == "warning")
    info_count = sum(1 for a in alerts if a["level"] == "info")

    return {
        "overall_score": overall_score,
        "rating": rating,
        "completeness_score": completeness_score,
        "uniqueness_score": uniqueness_score,
        "validity_score": validity_score,
        "structural_score": structural_score,
        "alerts": alerts,
        "alerts_summary": {
            "critical": crit_count,
            "warning": warn_count,
            "info": info_count,
            "total": len(alerts),
        },
    }


# ---------------------------------------------------------------------------
# 9. Main Unified Profiling Function
# ---------------------------------------------------------------------------

def profile_dataset(df: pd.DataFrame) -> Dict[str, Any]:
    """Execute automated end-to-end data profiling on a Pandas DataFrame.

    Aggregates dataset overview, column data types, missing value analysis,
    duplicate row metrics, unique value cardinality, numerical distributions,
    categorical frequencies, and overall data quality score with actionable alerts.

    Parameters
    ----------
    df : pd.DataFrame
        The dataset to profile.

    Returns
    -------
    Dict[str, Any]
        A comprehensive, JSON-serializable dictionary containing all profiling results.

    Raises
    ------
    ValueError
        If input is None or not a Pandas DataFrame.
    """
    if df is None:
        raise ValueError("Input dataset cannot be None.")
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Expected a pandas.DataFrame, but got {type(df).__name__}.")

    overview = get_dataset_overview(df)
    column_types = get_column_types(df)
    missing_values = get_missing_values(df)
    duplicates = get_duplicate_summary(df)
    unique_values = get_unique_values(df)
    numerical_stats = get_numerical_summary(df)
    categorical_stats = get_categorical_summary(df)
    quality_summary = get_data_quality_summary(df)

    return {
        "overview": overview,
        "column_types": column_types,
        "missing_values": missing_values,
        "duplicates": duplicates,
        "unique_values": unique_values,
        "numerical_stats": numerical_stats,
        "categorical_stats": categorical_stats,
        "quality_summary": quality_summary,
    }
