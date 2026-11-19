"""
DataFix - Autonomous Data Quality Engine
Module: Duplicate Detection Engine (duplicate_detector.py)

Responsible for:
- Detecting 100% identical exact duplicate rows and recording their row indices
- Detecting potential / near duplicates:
    * Normalized text variations (whitespace trimming, case insensitivity)
    * Subset key duplicates (identical records ignoring ID/primary key columns)
- Clustering duplicate candidates into actionable groups with confidence scores
- Recommending deduplication strategies (e.g. keep first occurrence, review candidates)
- Returning 100% JSON-serializable diagnostic structures
"""

import io
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd

from profiler import load_dataset


def detect_duplicates(
    data: Union[str, Path, io.IOBase, pd.DataFrame],
    check_potential_duplicates: bool = True
) -> Dict[str, Any]:
    """
    Detects both exact and potential/near duplicates in the dataset.
    
    Args:
        data: CSV filepath, file buffer, or pandas DataFrame.
        check_potential_duplicates: Whether to run fuzzy and subset matching.
        
    Returns:
        Structured JSON-compatible dictionary detailing duplicate counts, row indices, and clusters.
    """
    try:
        df = load_dataset(data)
    except Exception as e:
        return {
            "status": "error",
            "error_message": str(e),
            "exact_duplicates_count": 0,
            "exact_duplicate_indices": [],
            "potential_duplicates_count": 0,
            "potential_duplicate_groups": []
        }

    total_rows = len(df)
    total_cols = len(df.columns)

    if total_rows <= 1 or total_cols == 0:
        return {
            "status": "success",
            "total_rows": total_rows,
            "exact_duplicates_count": 0,
            "exact_duplicates_percentage": 0.0,
            "exact_duplicate_indices": [],
            "potential_duplicates_count": 0,
            "potential_duplicate_groups": [],
            "summary": {
                "has_duplicates": False,
                "recommended_action": "none_needed",
                "explanation": "No duplicates possible with current row count."
            }
        }

    # 1. Exact Duplicate Detection
    # keep='first' marks duplicates as True except for the first occurrence
    exact_mask = df.duplicated(keep="first")
    exact_duplicate_indices = [int(idx) for idx in df[exact_mask].index.tolist()]
    exact_duplicates_count = len(exact_duplicate_indices)
    exact_duplicates_percentage = round((exact_duplicates_count / total_rows) * 100, 2)

    # 2. Potential / Near Duplicate Detection
    potential_groups: List[Dict[str, Any]] = []
    potential_row_indices_set = set()

    if check_potential_duplicates and total_rows > 1:
        # Create a normalized copy of string columns (lowercased, stripped of whitespace)
        norm_df = df.copy()
        for col in norm_df.columns:
            if pd.api.types.is_object_dtype(norm_df[col]) or pd.api.types.is_string_dtype(norm_df[col]):
                norm_df[col] = norm_df[col].astype(str).str.strip().str.lower()

        # A. Normalized exact duplicates (catches casing and whitespace differences)
        norm_mask = norm_df.duplicated(keep=False)
        # Exclude rows that are already exact duplicates
        norm_dups = norm_df[norm_mask]

        if not norm_dups.empty:
            # Group by all normalized columns to find clusters
            grouped = norm_dups.groupby(list(norm_df.columns), as_index=False, dropna=False)
            group_id = 1
            for _, group in grouped:
                indices = [int(i) for i in group.index.tolist()]
                # If group contains rows beyond exact matches, it's a near match
                if len(indices) > 1 and not all(i in exact_duplicate_indices for i in indices[1:]):
                    sample_dict = {
                        str(k): (str(v) if pd.notna(v) else None)
                        for k, v in df.loc[indices[0]].to_dict().items()
                    }
                    potential_groups.append({
                        "group_id": group_id,
                        "type": "text_normalization_match",
                        "row_indices": indices,
                        "confidence_score": 0.95,
                        "explanation": f"Rows {indices} are identical after trimming whitespace and normalizing letter casing.",
                        "sample_record": sample_dict
                    })
                    potential_row_indices_set.update(indices)
                    group_id += 1

        # B. Non-ID subset matches (catches duplicate records that only differ by an auto-increment or ID column)
        id_candidates = [
            c for c in df.columns
            if any(term in str(c).lower() for term in ["id", "index", "key", "uuid", "pk"])
            or df[c].nunique() == total_rows
        ]

        if id_candidates and len(id_candidates) < total_cols:
            subset_cols = [c for c in norm_df.columns if c not in id_candidates]
            if subset_cols:
                subset_mask = norm_df.duplicated(subset=subset_cols, keep=False)
                subset_dups = norm_df[subset_mask]
                if not subset_dups.empty:
                    grouped_sub = subset_dups.groupby(subset_cols, as_index=False, dropna=False)
                    for _, group in grouped_sub:
                        sub_indices = [int(i) for i in group.index.tolist()]
                        # Don't duplicate groups already flagged by text normalization
                        if len(sub_indices) > 1 and tuple(sub_indices) not in [tuple(g["row_indices"]) for g in potential_groups]:
                            sample_dict = {
                                str(k): (str(v) if pd.notna(v) else None)
                                for k, v in df.loc[sub_indices[0]].to_dict().items()
                            }
                            potential_groups.append({
                                "group_id": len(potential_groups) + 1,
                                "type": "subset_match_ignoring_id",
                                "row_indices": sub_indices,
                                "confidence_score": 0.85,
                                "explanation": f"Rows {sub_indices} have identical attributes across non-ID columns ({', '.join(subset_cols[:3])}...).",
                                "sample_record": sample_dict
                            })
                            potential_row_indices_set.update(sub_indices)

    # Compile recommendations
    if exact_duplicates_count > 0:
        recommended_action = "drop_exact_duplicates"
        action_explanation = (
            f"Found {exact_duplicates_count} exact duplicate rows ({exact_duplicates_percentage}% of dataset). "
            f"Recommend dropping duplicate rows while retaining the first occurrence."
        )
    elif len(potential_groups) > 0:
        recommended_action = "review_potential_duplicates"
        action_explanation = (
            f"No exact duplicates found, but detected {len(potential_groups)} potential duplicate group(s) "
            f"due to casing, whitespace, or matching attributes. Review before merging."
        )
    else:
        recommended_action = "none_needed"
        action_explanation = "All records in the dataset are distinct and unique."

    return {
        "status": "success",
        "total_rows": total_rows,
        "exact_duplicates_count": exact_duplicates_count,
        "exact_duplicates_percentage": exact_duplicates_percentage,
        "exact_duplicate_indices": exact_duplicate_indices,
        "potential_duplicates_count": len(potential_row_indices_set),
        "potential_duplicate_groups": potential_groups,
        "summary": {
            "has_duplicates": exact_duplicates_count > 0 or len(potential_groups) > 0,
            "recommended_action": recommended_action,
            "explanation": action_explanation
        }
    }


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) > 1:
        res = detect_duplicates(sys.argv[1])
        print(json.dumps(res, indent=2))
    else:
        print("Usage: python duplicate_detector.py <path_to_csv>")
