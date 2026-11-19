
"""Isolation Forest Anomaly Detection Module for DataFix Engine.

This module provides unsupervised multivariate anomaly detection for tabular data
using Scikit-learn's Isolation Forest algorithm. It handles missing values, feature scaling,
and small or non-numeric datasets safely.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Union

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler


def detect_anomalies(
    df: pd.DataFrame,
    contamination: float = 0.05,
    random_state: int = 42,
    columns: Optional[Sequence[str]] = None,
    n_estimators: int = 100,
) -> Dict[str, Any]:
    """Detect multivariate anomalies in numerical dataset columns using Isolation Forest.

    Parameters
    ----------
    df : pd.DataFrame
        The tabular dataset to evaluate.
    contamination : float, default 0.05
        The expected proportion of outliers in the data set (between 0.001 and 0.5).
    random_state : int, default 42
        Seed for reproducibility of tree splits.
    columns : Optional[Sequence[str]], default None
        Specific numerical column names to evaluate. If None, evaluates all numeric columns.
    n_estimators : int, default 100
        Number of decision trees in the ensemble.

    Returns
    -------
    Dict[str, Any]
        Dictionary containing detected anomaly indices, anomaly count, percentage,
        anomaly scores, evaluated columns, and explanatory metadata.
    """
    if df is None:
        raise ValueError("Input DataFrame cannot be None.")
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Expected a pandas.DataFrame, got {type(df).__name__}.")

    total_rows = len(df)

    # Empty or very small dataset guard
    if total_rows < 3:
        return {
            "is_detected": False,
            "anomaly_indices": [],
            "anomaly_count": 0,
            "anomaly_percentage": 0.0,
            "anomaly_scores": [],
            "evaluated_columns": [],
            "top_contributing_columns": {},
            "details": f"Dataset has {total_rows} row(s); minimum 3 rows required for Isolation Forest.",
        }

    # Identify target numerical columns
    if columns is not None:
        target_cols = [c for c in columns if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
    else:
        target_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]

    if not target_cols:
        return {
            "is_detected": False,
            "anomaly_indices": [],
            "anomaly_count": 0,
            "anomaly_percentage": 0.0,
            "anomaly_scores": [],
            "evaluated_columns": [],
            "top_contributing_columns": {},
            "details": "No numerical columns available for Isolation Forest detection.",
        }

    # Prepare feature matrix X
    sub_df = df[target_cols].copy()

    # Safely impute missing values for model training using column median (or 0.0 if all-null)
    for col in target_cols:
        if sub_df[col].isna().any():
            med = sub_df[col].median()
            fill_val = 0.0 if pd.isna(med) else float(med)
            sub_df[col] = sub_df[col].fillna(fill_val)

    # Check for zero variance across all features
    variance_sum = float(sub_df.var().sum())
    if variance_sum == 0.0:
        return {
            "is_detected": False,
            "anomaly_indices": [],
            "anomaly_count": 0,
            "anomaly_percentage": 0.0,
            "anomaly_scores": [0.0] * total_rows,
            "evaluated_columns": target_cols,
            "top_contributing_columns": {},
            "details": "Numerical columns have zero variance (all values are identical); no anomalies detected.",
        }

    # Standardize numerical features
    scaler = StandardScaler()
    try:
        X_scaled = scaler.fit_transform(sub_df)
    except Exception as err:
        return {
            "is_detected": False,
            "anomaly_indices": [],
            "anomaly_count": 0,
            "anomaly_percentage": 0.0,
            "anomaly_scores": [],
            "evaluated_columns": target_cols,
            "top_contributing_columns": {},
            "details": f"Failed to scale feature matrix: {err}",
        }

    # Clamp contamination to valid range (0.001 to 0.5)
    valid_contamination = max(0.001, min(0.5, float(contamination)))

    # Fit Isolation Forest model
    clf = IsolationForest(
        contamination=valid_contamination,
        random_state=random_state,
        n_estimators=n_estimators,
    )
    clf.fit(X_scaled)

    # -1 represents an anomaly, 1 represents an inlier
    preds = clf.predict(X_scaled)
    # decision_function gives continuous score (lower = more abnormal)
    decision_scores = clf.decision_function(X_scaled)

    anomaly_mask = (preds == -1)
    anomaly_indices = [int(idx) if isinstance(idx, (int, np.integer)) else idx for idx in df.index[anomaly_mask]]
    anomaly_count = len(anomaly_indices)
    anomaly_pct = round((anomaly_count / total_rows * 100), 2)
    native_scores = [round(float(s), 4) for s in decision_scores]

    # Calculate top contributing features for anomalous records
    top_contributors: Dict[Union[int, str], List[str]] = {}
    if anomaly_count > 0 and len(target_cols) > 1:
        abs_zscores = np.abs(X_scaled[anomaly_mask])
        for row_idx, z_row in zip(anomaly_indices, abs_zscores):
            # Sort columns by absolute deviation
            sorted_feat_indices = np.argsort(-z_row)
            top_feats = [target_cols[i] for i in sorted_feat_indices[:3]]
            top_contributors[row_idx] = top_feats

    return {
        "is_detected": anomaly_count > 0,
        "anomaly_indices": anomaly_indices,
        "anomaly_count": anomaly_count,
        "anomaly_percentage": anomaly_pct,
        "anomaly_scores": native_scores,
        "evaluated_columns": target_cols,
        "top_contributing_columns": top_contributors,
        "details": (
            f"Evaluated {len(target_cols)} numerical column(s). "
            f"Detected {anomaly_count} multivariate anomaly record(s) ({anomaly_pct}%)."
        ),
    }
