
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

"""
DataFix - Autonomous Data Quality Engine
Module: Anomaly Detection Engine (anomaly_detector.py)

Responsible for:
- Detecting unusual numerical records using unsupervised Machine Learning (Isolation Forest)
- Providing robust statistical fallback (Modified Z-Score / IQR Ensemble) if scikit-learn is absent
- Generating plain-English, explainable reasons for every flagged anomaly (why it's anomalous)
- Returning 100% JSON-serializable diagnostic structures
"""

import io
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd

from ai.profiler import load_dataset, _to_serializable

# Try importing scikit-learn IsolationForest
try:
    from sklearn.ensemble import IsolationForest
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


def detect_anomalies(
    data: Union[str, Path, io.IOBase, pd.DataFrame],
    contamination: float = 0.1,
    random_state: int = 42
) -> Dict[str, Any]:
    """
    Detects multivariate and univariate numerical anomalies in the dataset.
    
    Args:
        data: CSV filepath, file buffer, or pandas DataFrame.
        contamination: Expected proportion of outliers in the data (0.01 to 0.5).
        random_state: Seed for reproducibility.
        
    Returns:
        Structured JSON-compatible dictionary with flagged anomalies, scores, and explanations.
    """
    try:
        df = load_dataset(data)
    except Exception as e:
        return {
            "status": "error",
            "error_message": str(e),
            "anomalies_count": 0,
            "anomalies_percentage": 0.0,
            "anomalous_records": []
        }

    total_rows = len(df)
    if total_rows < 3:
        return {
            "status": "success",
            "total_rows": total_rows,
            "anomalies_count": 0,
            "anomalies_percentage": 0.0,
            "algorithm_used": "None",
            "numerical_features_analyzed": [],
            "anomalous_records": [],
            "summary": {
                "has_anomalies": False,
                "explanation": "Dataset contains fewer than 3 rows. Insufficient data for anomaly detection."
            }
        }

    # Extract numerical columns or columns where at least 60% of non-null values can convert to numeric
    numeric_cols = []
    converted_df = pd.DataFrame(index=df.index)

    for col in df.columns:
        series = df[col]
        # Ignore ID/index columns
        if any(term in str(col).lower() for term in ["id", "index", "key", "uuid", "pk"]):
            continue

        num_converted = pd.to_numeric(series, errors="coerce")
        valid_ratio = num_converted.notna().sum() / total_rows
        if valid_ratio >= 0.5 and num_converted.nunique() > 1:
            numeric_cols.append(str(col))
            # Median imputation for model training stability
            col_median = num_converted.median() if not np.isnan(num_converted.median()) else 0.0
            converted_df[str(col)] = num_converted.fillna(col_median)

    if len(numeric_cols) == 0:
        return {
            "status": "success",
            "total_rows": total_rows,
            "anomalies_count": 0,
            "anomalies_percentage": 0.0,
            "algorithm_used": "None",
            "numerical_features_analyzed": [],
            "anomalous_records": [],
            "summary": {
                "has_anomalies": False,
                "explanation": "No numeric features found to evaluate for anomalies."
            }
        }

    X = converted_df[numeric_cols].values
    is_anomaly_mask = np.zeros(total_rows, dtype=bool)
    anomaly_scores = np.zeros(total_rows, dtype=float)
    algorithm_used = ""

    # 1. Run Machine Learning Detection (Isolation Forest)
    if SKLEARN_AVAILABLE and len(numeric_cols) >= 1 and total_rows >= 5:
        algorithm_used = "Isolation Forest (scikit-learn)"
        try:
            iso = IsolationForest(
                contamination=max(0.01, min(0.5, contamination)),
                random_state=random_state,
                n_estimators=100
            )
            preds = iso.fit_predict(X)  # -1 for anomaly, 1 for inlier
            is_anomaly_mask = (preds == -1)
            # decision_function gives negative scores for anomalies
            raw_scores = iso.decision_function(X)
            # Invert and normalize to [0, 1] range where higher = more anomalous
            min_s, max_s = raw_scores.min(), raw_scores.max()
            if max_s > min_s:
                anomaly_scores = 1.0 - ((raw_scores - min_s) / (max_s - min_s))
            else:
                anomaly_scores = np.where(is_anomaly_mask, 0.9, 0.1)
        except Exception:
            # Fallback if isolation forest encounters collinearity or numerical errors
            algorithm_used = "Robust Multi-Factor IQR/Z-Score (Fallback)"
            is_anomaly_mask, anomaly_scores = _robust_statistical_detector(converted_df[numeric_cols])
    else:
        # 2. Pure Statistical ML Ensemble (IQR + Median Absolute Deviation)
        algorithm_used = "Robust Multi-Factor IQR/Z-Score (NumPy)"
        is_anomaly_mask, anomaly_scores = _robust_statistical_detector(converted_df[numeric_cols])

    # 3. Generate Human-Readable Explanations for each flagged anomaly
    stats_dict = {}
    for col in numeric_cols:
        s = converted_df[col]
        q1 = s.quantile(0.25)
        q3 = s.quantile(0.75)
        iqr = q3 - q1
        mean = s.mean()
        std = s.std() if s.std() > 0 else 1.0
        median = s.median()
        stats_dict[col] = {
            "q1": q1, "q3": q3, "iqr": iqr,
            "lower_bound": q1 - 1.5 * iqr,
            "upper_bound": q3 + 1.5 * iqr,
            "mean": mean, "std": std, "median": median
        }

    anomalous_records = []
    anomaly_indices = np.where(is_anomaly_mask)[0]

    for idx in anomaly_indices:
        reasons = []
        row_dict = {str(k): _to_serializable(v) for k, v in df.iloc[idx].to_dict().items()}

        for col in numeric_cols:
            val = converted_df[col].iloc[idx]
            original_val = df[col].iloc[idx]
            col_stat = stats_dict[col]

            # Z-score check
            z_score = abs(val - col_stat["mean"]) / col_stat["std"]

            # Outlier check via IQR
            is_extreme = val < col_stat["lower_bound"] or val > col_stat["upper_bound"]

            if is_extreme or z_score >= 2.5:
                direction = "above" if val > col_stat["median"] else "below"
                diff_ratio = (
                    round(abs(val / col_stat["median"]), 1)
                    if col_stat["median"] != 0 else round(abs(val), 1)
                )

                if val > col_stat["upper_bound"]:
                    reasons.append(
                        f"Column '{col}' value {val} is {diff_ratio}x higher than median ({round(col_stat['median'], 2)}) "
                        f"and exceeds statistical upper bound ({round(col_stat['upper_bound'], 2)})."
                    )
                elif val < col_stat["lower_bound"]:
                    reasons.append(
                        f"Column '{col}' value {val} is unusually low (median = {round(col_stat['median'], 2)}) "
                        f"and falls below statistical lower bound ({round(col_stat['lower_bound'], 2)})."
                    )
                elif z_score >= 2.5:
                    reasons.append(
                        f"Column '{col}' value {val} is {round(z_score, 1)} standard deviations {direction} mean."
                    )

        if not reasons:
            reasons.append("Multi-dimensional feature interaction flagged as atypical by Isolation Forest.")

        anomalous_records.append({
            "row_index": int(idx),
            "anomaly_score": float(round(anomaly_scores[idx], 3)),
            "record": row_dict,
            "reasons": reasons
        })

    # Sort records by anomaly score descending (highest anomalies first)
    anomalous_records.sort(key=lambda x: x["anomaly_score"], reverse=True)

    anomalies_count = len(anomalous_records)
    anomalies_percentage = round((anomalies_count / total_rows) * 100, 2)

    return {
        "status": "success",
        "total_rows": total_rows,
        "anomalies_count": anomalies_count,
        "anomalies_percentage": anomalies_percentage,
        "algorithm_used": algorithm_used,
        "numerical_features_analyzed": numeric_cols,
        "anomalous_records": anomalous_records,
        "summary": {
            "has_anomalies": anomalies_count > 0,
            "anomalies_count": anomalies_count,
            "anomalies_percentage": anomalies_percentage,
            "explanation": (
                f"Identified {anomalies_count} anomalous record(s) ({anomalies_percentage}% of dataset) "
                f"using {algorithm_used}."
                if anomalies_count > 0 else "No anomalous records detected."
            )
        }
    }


def _robust_statistical_detector(num_df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """
    Computes multivariate outlier scores using Median Absolute Deviation (MAD) & IQR.
    """
    total_rows = len(num_df)
    score_matrix = np.zeros((total_rows, len(num_df.columns)))

    for i, col in enumerate(num_df.columns):
        s = num_df[col]
        median = s.median()
        mad = (s - median).abs().median()
        if mad > 0:
            # Modified Z-score: 0.6745 * (x - median) / MAD
            mod_z = 0.6745 * (s - median).abs() / mad
        else:
            std = s.std() if s.std() > 0 else 1.0
            mod_z = (s - s.mean()).abs() / std

        score_matrix[:, i] = mod_z.values

    # Max score across features determines the record's outlier degree
    record_scores = np.max(score_matrix, axis=1)

    # Flag as anomaly if modified Z-score exceeds 3.5 (standard threshold in robust statistics)
    is_anomaly = record_scores > 3.5

    # Normalize scores to [0, 1] range for intuitive API consumption
    max_val = max(1.0, float(np.max(record_scores)))
    normalized_scores = np.clip(record_scores / max_val, 0.0, 1.0)

    return is_anomaly, normalized_scores


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) > 1:
        res = detect_anomalies(sys.argv[1])
        print(json.dumps(res, indent=2))
    else:
        print("Usage: python anomaly_detector.py <path_to_csv>")
