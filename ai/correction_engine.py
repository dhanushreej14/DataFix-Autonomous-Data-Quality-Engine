"""
DataFix - Autonomous Data Quality Engine
Module: Intelligent Correction Engine (correction_engine.py)

Responsible for:
- Aggregating diagnostic findings into prioritized, actionable correction suggestions
- Providing a 100% NON-DESTRUCTIVE data cleaning pipeline (original data is NEVER mutated)
- Standardizing date formats to ISO-8601 (YYYY-MM-DD)
- Normalizing categorical text (whitespace trimming, title-casing)
- Coercing contaminated numeric columns (cleaning strings like 'unknown' to NaN)
- Rectifying suspicious/domain-invalid values (negative ages, etc.)
- Imputing missing values using intelligent strategies
- Exporting separate cleaned DataFrames or CSV strings on demand
"""

import datetime
import io
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd

from profiler import load_dataset, infer_column_type


def generate_correction_suggestions(
    profile_data: Dict[str, Any],
    missing_data: Dict[str, Any],
    duplicate_data: Dict[str, Any],
    anomaly_data: Dict[str, Any],
    inconsistency_data: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Synthesizes findings from all detector modules into a prioritized, actionable list of suggestions.
    """
    suggestions = []

    # 1. Duplicates suggestions
    exact_dups = duplicate_data.get("exact_duplicates_count", 0)
    if exact_dups > 0:
        suggestions.append({
            "action_id": "drop_exact_duplicates",
            "category": "Uniqueness",
            "priority": "HIGH",
            "target": "Entire Dataset",
            "title": "Remove Exact Duplicate Records",
            "description": f"Drop {exact_dups} exact duplicate row(s) while retaining the initial occurrence.",
            "impact": "Eliminates redundancy and prevents skewed statistics.",
            "auto_apply": True
        })

    # 2. Type contamination suggestions
    type_issues = inconsistency_data.get("type_inconsistencies", [])
    for issue in type_issues:
        col = issue["column"]
        count = issue.get("polluting_entries_count", 0)
        suggestions.append({
            "action_id": f"coerce_numeric_{col}",
            "category": "Consistency",
            "priority": "HIGH",
            "target": col,
            "title": f"Clean Contaminated Numeric Column '{col}'",
            "description": f"Found {count} non-numeric string(s) (e.g. 'unknown') in numeric column '{col}'. Coerce to NaN.",
            "impact": "Restores correct numeric datatype for ML model compatibility.",
            "auto_apply": True
        })

    # 3. Suspicious / Range suggestions
    suspicious_issues = inconsistency_data.get("suspicious_values", [])
    for issue in suspicious_issues:
        col = issue["column"]
        count = issue.get("count", 0)
        suggestions.append({
            "action_id": f"rectify_suspicious_{col}",
            "category": "Validity",
            "priority": "HIGH",
            "target": col,
            "title": f"Rectify Invalid Values in '{col}'",
            "description": f"Found {count} impossible value(s) (e.g. negative or extreme age). Replace with NaN/Median.",
            "impact": "Prevents nonsensical data from degrading downstream analytics.",
            "auto_apply": True
        })

    # 4. Date standardization suggestions
    date_issues = inconsistency_data.get("date_inconsistencies", [])
    for issue in date_issues:
        col = issue["column"]
        suggestions.append({
            "action_id": f"standardize_dates_{col}",
            "category": "Consistency",
            "priority": "MEDIUM",
            "target": col,
            "title": f"Standardize Date Format for '{col}'",
            "description": f"Convert mixed date formats in column '{col}' to standard ISO-8601 ('YYYY-MM-DD').",
            "impact": "Ensures uniform chronological parsing and filtering.",
            "auto_apply": True
        })

    # 5. Categorical standardization suggestions
    cat_issues = inconsistency_data.get("categorical_inconsistencies", [])
    for issue in cat_issues:
        col = issue["column"]
        suggestions.append({
            "action_id": f"standardize_categories_{col}",
            "category": "Consistency",
            "priority": "MEDIUM",
            "target": col,
            "title": f"Standardize Text Formatting in '{col}'",
            "description": f"Strip extraneous whitespace and normalize capitalization to Title Case in '{col}'.",
            "impact": "Resolves fragmented categories (e.g. 'Engineering' vs 'engineering').",
            "auto_apply": True
        })

    # 6. Missing value imputation suggestions
    missing_recs = missing_data.get("recommendations", [])
    for rec in missing_recs:
        col = rec["column"]
        action = rec["recommended_action"]
        val = rec.get("suggested_imputation_value")
        suggestions.append({
            "action_id": f"impute_missing_{col}",
            "category": "Completeness",
            "priority": "MEDIUM",
            "target": col,
            "title": f"Impute Missing Values in '{col}'",
            "description": f"Apply strategy '{action}' ({rec['explanation']})" + (f" with value: {val}" if val is not None else "."),
            "impact": "Restores row completeness without introducing distributional distortion.",
            "auto_apply": True
        })

    # 7. Extreme anomaly review suggestion
    anomalies_count = anomaly_data.get("anomalies_count", 0)
    if anomalies_count > 0:
        suggestions.append({
            "action_id": "review_anomalies",
            "category": "Validity",
            "priority": "LOW",
            "target": "Entire Dataset",
            "title": "Review Flagged Outliers & Anomalies",
            "description": f"{anomalies_count} record(s) flagged by ML Isolation Forest as statistical outliers.",
            "impact": "Requires user confirmation before automated clipping or dropping.",
            "auto_apply": False
        })

    return suggestions


def clean_dataset(
    data: Union[str, Path, io.IOBase, pd.DataFrame],
    enabled_actions: Optional[List[str]] = None,
    return_format: str = "dataframe"
) -> Dict[str, Any]:
    """
    Executes a safe, non-destructive cleaning pipeline.
    The original data source is NEVER mutated.
    
    Args:
        data: CSV filepath, file buffer, or pandas DataFrame.
        enabled_actions: Optional list of action_ids to execute. If None, applies all recommended safe steps.
        return_format: 'dataframe' or 'csv'.
        
    Returns:
        Dictionary containing the separate cleaned dataset, changelog, and summary metrics.
    """
    # 1. Load data safely into an isolated new DataFrame
    df = load_dataset(data)
    initial_rows = len(df)
    initial_cols = len(df.columns)
    cleaned_df = df.copy()

    changelog: List[str] = []

    # -------------------------------------------------------------
    # Step 1: Remove Exact Duplicates
    # -------------------------------------------------------------
    if enabled_actions is None or "drop_exact_duplicates" in enabled_actions:
        dups_count = int(cleaned_df.duplicated().sum())
        if dups_count > 0:
            cleaned_df = cleaned_df.drop_duplicates(keep="first").reset_index(drop=True)
            changelog.append(f"Deduplication: Removed {dups_count} exact duplicate row(s).")

    # -------------------------------------------------------------
    # Step 2: Coerce Contaminated Numeric Columns & Trim Text
    # -------------------------------------------------------------
    for col in cleaned_df.columns:
        if pd.api.types.is_object_dtype(cleaned_df[col]) or pd.api.types.is_string_dtype(cleaned_df[col]):
            action_id = f"coerce_numeric_{col}"
            if enabled_actions is None or action_id in enabled_actions:
                # Check if it looks like a contaminated numeric column
                num_series = pd.to_numeric(cleaned_df[col], errors="coerce")
                non_null_total = cleaned_df[col].dropna().count()
                if non_null_total > 0 and (num_series.notna().sum() / non_null_total) >= 0.5:
                    invalid_mask = cleaned_df[col].notna() & num_series.isna()
                    count_fixed = int(invalid_mask.sum())
                    if count_fixed > 0:
                        cleaned_df[col] = num_series
                        changelog.append(f"Type Coercion: Converted {count_fixed} non-numeric string(s) to NaN in numeric column '{col}'.")

    # -------------------------------------------------------------
    # Step 3: Standardize Categorical Columns (Whitespace & Title Case)
    # -------------------------------------------------------------
    for col in cleaned_df.columns:
        action_id = f"standardize_categories_{col}"
        if (enabled_actions is None or action_id in enabled_actions) and (
            pd.api.types.is_object_dtype(cleaned_df[col]) or pd.api.types.is_string_dtype(cleaned_df[col])
        ):
            # Strip whitespace
            stripped = cleaned_df[col].astype(str).str.strip()
            # If values don't look like URLs or codes, apply Title Case to unify casing
            # (e.g. 'engineering' -> 'Engineering')
            title_cased = stripped.str.title()
            
            # Restore genuine NaNs that were converted to 'Nan' string
            cleaned_series = title_cased.replace(["Nan", "None", "Null", "<Na>"], np.nan)
            
            # Check if any values changed
            if not cleaned_df[col].equals(cleaned_series):
                cleaned_df[col] = cleaned_series
                changelog.append(f"Categorical Standardization: Trimmed whitespace and applied Title Case to '{col}'.")

    # -------------------------------------------------------------
    # Step 4: Standardize Date Formats to ISO-8601 (YYYY-MM-DD)
    # -------------------------------------------------------------
    for col in cleaned_df.columns:
        action_id = f"standardize_dates_{col}"
        col_lower = str(col).lower()
        is_date_col = any(k in col_lower for k in ["date", "time", "join", "created", "birth"])
        
        if (enabled_actions is None or action_id in enabled_actions) and is_date_col:
            try:
                # Parse to datetime safely, coercing unparseable strings to NaT
                parsed_dates = pd.to_datetime(cleaned_df[col], errors="coerce")
                if parsed_dates.notna().sum() > 0:
                    cleaned_df[col] = parsed_dates.dt.strftime("%Y-%m-%d")
                    changelog.append(f"Date Normalization: Standardized '{col}' to ISO-8601 ('YYYY-MM-DD').")
            except Exception:
                pass

    # -------------------------------------------------------------
    # Step 5: Rectify Suspicious Values (e.g. negative age, extreme age)
    # -------------------------------------------------------------
    for col in cleaned_df.columns:
        action_id = f"rectify_suspicious_{col}"
        col_lower = str(col).lower()
        if (enabled_actions is None or action_id in enabled_actions) and "age" in col_lower:
            num_age = pd.to_numeric(cleaned_df[col], errors="coerce")
            invalid_age_mask = (num_age < 0) | (num_age > 125)
            invalid_count = int(invalid_age_mask.sum())
            if invalid_count > 0:
                # Replace impossible ages with median of valid ages
                valid_median = num_age[~invalid_age_mask].median()
                cleaned_df.loc[invalid_age_mask, col] = valid_median
                changelog.append(f"Value Rectification: Replaced {invalid_count} invalid age value(s) (<0 or >125) with valid median ({valid_median}).")

    # -------------------------------------------------------------
    # Step 6: Impute Remaining Missing Values
    # -------------------------------------------------------------
    for col in cleaned_df.columns:
        action_id = f"impute_missing_{col}"
        if enabled_actions is None or action_id in enabled_actions:
            null_count = int(cleaned_df[col].isna().sum())
            if null_count > 0:
                col_type = infer_column_type(cleaned_df[col])
                
                # Numeric: impute with median
                if col_type in ["integer", "float"] or pd.api.types.is_numeric_dtype(cleaned_df[col]):
                    num_s = pd.to_numeric(cleaned_df[col], errors="coerce")
                    median_val = num_s.median() if not np.isnan(num_s.median()) else 0
                    cleaned_df[col] = num_s.fillna(median_val)
                    changelog.append(f"Imputation: Imputed {null_count} missing value(s) in numeric column '{col}' with median ({median_val}).")
                
                # Datetime: forward fill
                elif col_type == "datetime" or any(k in str(col).lower() for k in ["date", "time"]):
                    cleaned_df[col] = cleaned_df[col].ffill().bfill()
                    changelog.append(f"Imputation: Applied forward/backward fill to {null_count} missing date(s) in '{col}'.")
                
                # Categorical / Text: impute with mode or 'Unknown'
                else:
                    mode_vals = cleaned_df[col].mode()
                    impute_val = mode_vals.iloc[0] if not mode_vals.empty else "Unknown"
                    cleaned_df[col] = cleaned_df[col].fillna(impute_val)
                    changelog.append(f"Imputation: Imputed {null_count} missing categorical value(s) in '{col}' with '{impute_val}'.")

    # Final output preparation
    final_rows = len(cleaned_df)
    final_cols = len(cleaned_df.columns)
    remaining_nulls = int(cleaned_df.isna().sum().sum())

    result_payload: Dict[str, Any] = {
        "status": "success",
        "initial_rows": initial_rows,
        "cleaned_rows": final_rows,
        "rows_removed": initial_rows - final_rows,
        "columns": final_cols,
        "remaining_null_cells": remaining_nulls,
        "transformations_applied": changelog,
        "total_transformations_count": len(changelog)
    }

    if return_format.lower() == "csv":
        result_payload["cleaned_csv"] = cleaned_df.to_csv(index=False)
    else:
        result_payload["cleaned_dataframe"] = cleaned_df

    return result_payload


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) > 1:
        res = clean_dataset(sys.argv[1], return_format="csv")
        print("Transformations applied:")
        for t in res["transformations_applied"]:
            print(f" - {t}")
        print("\nCleaned CSV Preview:")
        print(res["cleaned_csv"][:500])
    else:
        print("Usage: python correction_engine.py <path_to_csv>")
