"""AI-Based Remediation Recommendation Engine for DataFix Engine.

This module analyzes dataset profiling results and Isolation Forest anomaly signals
to autonomously formulate prioritized data quality remediation recommendations,
strictly enforcing non-destructive safety gates before applying changes to the CleaningPipeline.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import pandas as pd

from backend.cleaning import CleaningPipeline
from backend.profiling import profile_dataset
from ai.anomaly_detector import detect_anomalies


# ---------------------------------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------------------------------

class DestructiveOperationBlockedError(Exception):
    """Raised when an attempt is made to execute a destructive operation without explicit approval."""
    pass


# ---------------------------------------------------------------------------
# Recommendation Data Class
# ---------------------------------------------------------------------------

class RemediationRecommendation:
    """Represents an actionable data quality cleaning recommendation."""

    def __init__(
        self,
        rec_id: str,
        category: str,
        severity: str,
        column: Optional[str],
        problem_description: str,
        recommended_action: str,
        rationale: str,
        confidence_score: float,
        is_destructive: bool,
        pipeline_operation: str,
        pipeline_parameters: Dict[str, Any],
    ) -> None:
        self.id = rec_id
        self.category = category
        self.severity = severity
        self.column = column
        self.problem_description = problem_description
        self.recommended_action = recommended_action
        self.rationale = rationale
        self.confidence_score = round(confidence_score, 2)
        self.is_destructive = is_destructive
        self.pipeline_operation = pipeline_operation
        self.pipeline_parameters = pipeline_parameters

    def to_dict(self) -> Dict[str, Any]:
        """Convert recommendation object to a JSON-serializable dictionary."""
        return {
            "id": self.id,
            "category": self.category,
            "severity": self.severity,
            "column": self.column,
            "problem_description": self.problem_description,
            "recommended_action": self.recommended_action,
            "rationale": self.rationale,
            "confidence_score": self.confidence_score,
            "is_destructive": self.is_destructive,
            "pipeline_operation": self.pipeline_operation,
            "pipeline_parameters": self.pipeline_parameters,
        }

    def __repr__(self) -> str:
        return (
            f"<RemediationRecommendation id={self.id} col={self.column} "
            f"cat={self.category} destructive={self.is_destructive} conf={self.confidence_score}>"
        )


# ---------------------------------------------------------------------------
# Recommendation Engine Heuristics
# ---------------------------------------------------------------------------

_CURRENCY_NUMERIC_PATTERN = re.compile(r"^\s*[$€£]?\s*-?\d+(?:,\d{3})*(?:\.\d+)?%?\s*$")


def generate_recommendations(
    df: pd.DataFrame,
    profile: Optional[Dict[str, Any]] = None,
    anomaly_results: Optional[Dict[str, Any]] = None,
) -> List[RemediationRecommendation]:
    """Analyze dataset profiling and anomaly detection metrics to generate remediation recommendations.

    Parameters
    ----------
    df : pd.DataFrame
        The dataset to inspect.
    profile : Optional[Dict[str, Any]], default None
        Pre-computed dataset profile from `backend.profiling.profile_dataset`.
        If None, computed automatically.
    anomaly_results : Optional[Dict[str, Any]], default None
        Pre-computed anomaly detection results from `ai.anomaly_detector.detect_anomalies`.
        If None, computed automatically.

    Returns
    -------
    List[RemediationRecommendation]
        A prioritized list of actionable recommendations.
    """
    if df is None:
        raise ValueError("Input DataFrame cannot be None.")
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Expected a pandas.DataFrame, got {type(df).__name__}.")

    if profile is None:
        profile = profile_dataset(df)
    if anomaly_results is None:
        anomaly_results = detect_anomalies(df)

    recommendations: List[RemediationRecommendation] = []
    counter = 1

    # -----------------------------------------------------------------------
    # 1. Duplicates
    # -----------------------------------------------------------------------
    dup_info = profile.get("duplicates", {})
    if dup_info.get("has_duplicates", False):
        dup_count = dup_info.get("duplicate_rows_count", 0)
        dup_pct = dup_info.get("duplicate_rows_percentage", 0.0)
        recommendations.append(
            RemediationRecommendation(
                rec_id=f"REC-{counter:03d}",
                category="duplicates",
                severity="high" if dup_pct >= 5.0 else "medium",
                column="dataset",
                problem_description=f"Dataset contains {dup_count} duplicate row(s) ({dup_pct}% of total records).",
                recommended_action="Remove duplicate rows, retaining the first occurrence.",
                rationale="Redundant identical rows distort sample weights, inflate metrics, and bias ML model training.",
                confidence_score=0.98,
                is_destructive=True,  # Deletes rows
                pipeline_operation="handle_duplicates",
                pipeline_parameters={"strategy": "drop_first"},
            )
        )
        counter += 1

    # -----------------------------------------------------------------------
    # 2. Missing Values
    # -----------------------------------------------------------------------
    missing_info = profile.get("missing_values", {})
    col_missing = missing_info.get("columns", {})
    num_stats = profile.get("numerical_stats", {})
    col_types = profile.get("column_types", {})
    num_cols = set(col_types.get("numerical_columns", []))

    for col, m_stats in col_missing.items():
        missing_count = m_stats.get("missing_count", 0)
        missing_pct = m_stats.get("missing_percentage", 0.0)

        if missing_count == 0:
            continue

        # Critical missingness: >= 70% missing
        if missing_pct >= 70.0:
            recommendations.append(
                RemediationRecommendation(
                    rec_id=f"REC-{counter:03d}",
                    category="missing_values",
                    severity="critical",
                    column=col,
                    problem_description=f"Column '{col}' has severe missingness: {missing_count} missing values ({missing_pct}%).",
                    recommended_action=f"Drop column '{col}' from the dataset.",
                    rationale="Columns with over 70% missing values introduce noise and artificial bias when imputed.",
                    confidence_score=0.95,
                    is_destructive=True,  # Deletes column
                    pipeline_operation="handle_missing_values",
                    pipeline_parameters={"columns": [col], "strategy": "drop_column"},
                )
            )
            counter += 1
            continue

        # Numeric missingness
        if col in num_cols:
            skew = num_stats.get(col, {}).get("skewness")
            # If skewed (|skew| > 1.0) or skew is unknown, recommend median; otherwise mean
            if skew is not None and abs(skew) > 1.0:
                recommendations.append(
                    RemediationRecommendation(
                        rec_id=f"REC-{counter:03d}",
                        category="missing_values",
                        severity="medium",
                        column=col,
                        problem_description=(
                            f"Column '{col}' has {missing_count} missing values ({missing_pct}%) "
                            f"with a skewed distribution (skewness = {skew})."
                        ),
                        recommended_action=f"Impute missing values in '{col}' using the column median.",
                        rationale="Median imputation is resistant to skewness and extreme values, preserving data distribution.",
                        confidence_score=0.92,
                        is_destructive=False,
                        pipeline_operation="handle_missing_values",
                        pipeline_parameters={"columns": [col], "strategy": "median"},
                    )
                )
            else:
                recommendations.append(
                    RemediationRecommendation(
                        rec_id=f"REC-{counter:03d}",
                        category="missing_values",
                        severity="low" if missing_pct < 10.0 else "medium",
                        column=col,
                        problem_description=(
                            f"Column '{col}' has {missing_count} missing values ({missing_pct}%) "
                            "with an approximately symmetric distribution."
                        ),
                        recommended_action=f"Impute missing values in '{col}' using the column mean.",
                        rationale="Mean imputation preserves the central tendency for normally distributed numerical data.",
                        confidence_score=0.89,
                        is_destructive=False,
                        pipeline_operation="handle_missing_values",
                        pipeline_parameters={"columns": [col], "strategy": "mean"},
                    )
                )
            counter += 1

        # Categorical / String missingness
        else:
            recommendations.append(
                RemediationRecommendation(
                    rec_id=f"REC-{counter:03d}",
                    category="missing_values",
                    severity="low" if missing_pct < 10.0 else "medium",
                    column=col,
                    problem_description=f"Categorical column '{col}' has {missing_count} missing values ({missing_pct}%).",
                    recommended_action=f"Impute missing values in '{col}' using the most frequent value (mode).",
                    rationale="Mode imputation fills categorical gaps using the highest-probability observed class.",
                    confidence_score=0.85,
                    is_destructive=False,
                    pipeline_operation="handle_missing_values",
                    pipeline_parameters={"columns": [col], "strategy": "mode"},
                )
            )
            counter += 1

    # -----------------------------------------------------------------------
    # 3. Numerical Outliers
    # -----------------------------------------------------------------------
    for col, stats in num_stats.items():
        outlier_count = stats.get("outliers_count", 0)
        outlier_pct = stats.get("outliers_percentage", 0.0)
        bounds = stats.get("outlier_bounds", {})
        low = bounds.get("lower")
        high = bounds.get("upper")

        if outlier_count > 0 and low is not None and high is not None:
            recommendations.append(
                RemediationRecommendation(
                    rec_id=f"REC-{counter:03d}",
                    category="outliers",
                    severity="high" if outlier_pct >= 10.0 else "medium",
                    column=col,
                    problem_description=(
                        f"Column '{col}' contains {outlier_count} outlier(s) ({outlier_pct}%) "
                        f"outside Tukey's 1.5x IQR boundaries [{low}, {high}]."
                    ),
                    recommended_action=f"Winsorize (clip) outliers in '{col}' to the boundary thresholds [{low}, {high}].",
                    rationale="Clipping mitigates the distortive influence of extreme values while preserving sample size.",
                    confidence_score=0.88,
                    is_destructive=False,
                    pipeline_operation="handle_outliers",
                    pipeline_parameters={"columns": [col], "method": "iqr", "strategy": "clip", "factor": 1.5},
                )
            )
            counter += 1

    # -----------------------------------------------------------------------
    # 4. Text & String Standardization
    # -----------------------------------------------------------------------
    str_cols = [c for c in df.columns if pd.api.types.is_string_dtype(df[c]) or df[c].dtype == "object"]
    for col in str_cols:
        series_clean = df[col].dropna()
        if len(series_clean) == 0:
            continue

        sample_vals = series_clean.astype(str).head(50)
        has_whitespace_issues = any(s != s.strip() or "  " in s for s in sample_vals)
        has_empty_strings = any(s == "" or s.isspace() for s in sample_vals)

        if has_whitespace_issues or has_empty_strings:
            recommendations.append(
                RemediationRecommendation(
                    rec_id=f"REC-{counter:03d}",
                    category="text_cleaning",
                    severity="low",
                    column=col,
                    problem_description=f"Column '{col}' contains unstripped whitespace or empty string artifacts.",
                    recommended_action=f"Standardize text in '{col}' by stripping extra whitespace and converting empty strings to NaN.",
                    rationale="Inconsistent whitespace creates false distinct categories and hampers grouping and indexing.",
                    confidence_score=0.93,
                    is_destructive=False,
                    pipeline_operation="clean_text",
                    pipeline_parameters={
                        "columns": [col],
                        "strip_whitespace": True,
                        "case": None,
                        "replace_empty_with_nan": True,
                    },
                )
            )
            counter += 1

    # -----------------------------------------------------------------------
    # 5. Type Casting (e.g. numeric stored as formatted string)
    # -----------------------------------------------------------------------
    for col in str_cols:
        series_clean = df[col].dropna()
        if len(series_clean) >= 3:
            sample_strs = series_clean.astype(str).head(30)
            numeric_match_count = sum(1 for s in sample_strs if _CURRENCY_NUMERIC_PATTERN.match(s))
            if numeric_match_count >= int(len(sample_strs) * 0.8):
                # Detected numeric values stored as string with symbols
                recommendations.append(
                    RemediationRecommendation(
                        rec_id=f"REC-{counter:03d}",
                        category="type_casting",
                        severity="medium",
                        column=col,
                        problem_description=(
                            f"Column '{col}' is stored as text but contains numerical formatting "
                            f"(currency, commas, or percentages) in {numeric_match_count}/{len(sample_strs)} sampled values."
                        ),
                        recommended_action=f"Cast column '{col}' to numeric float.",
                        rationale="Numerical data stored as string prevents mathematical operations and modeling.",
                        confidence_score=0.91,
                        is_destructive=False,
                        pipeline_operation="cast_types",
                        pipeline_parameters={"type_map": {col: "float"}},
                    )
                )
                counter += 1

    # -----------------------------------------------------------------------
    # 6. Multivariate Anomalies (Isolation Forest)
    # -----------------------------------------------------------------------
    if anomaly_results.get("is_detected", False):
        a_count = anomaly_results.get("anomaly_count", 0)
        a_pct = anomaly_results.get("anomaly_percentage", 0.0)
        evaluated_cols = anomaly_results.get("evaluated_columns", [])
        recommendations.append(
            RemediationRecommendation(
                rec_id=f"REC-{counter:03d}",
                category="anomalies",
                severity="high" if a_pct >= 10.0 else "medium",
                column="dataset",
                problem_description=(
                    f"Isolation Forest identified {a_count} multivariate anomaly record(s) ({a_pct}%) "
                    f"across numerical features: {evaluated_cols}."
                ),
                recommended_action="Inspect anomalous records and consider clipping extreme boundary outliers.",
                rationale="Multivariate anomalies exhibit unusual feature correlations that distort joint probability distributions.",
                confidence_score=0.86,
                is_destructive=False,
                pipeline_operation="handle_outliers",
                pipeline_parameters={"columns": evaluated_cols, "method": "iqr", "strategy": "clip", "factor": 1.5},
            )
        )
        counter += 1

    return recommendations


# ---------------------------------------------------------------------------
# Recommendation Execution & Safety Enforcers
# ---------------------------------------------------------------------------

def apply_recommendation(
    pipeline: CleaningPipeline,
    recommendation: RemediationRecommendation,
    approved: bool = False,
) -> Tuple[CleaningPipeline, Dict[str, Any]]:
    """Apply a single recommendation to the CleaningPipeline with safety approval checks.

    Parameters
    ----------
    pipeline : CleaningPipeline
        The cleaning pipeline instance to execute the transformation on.
    recommendation : RemediationRecommendation
        The recommendation to execute.
    approved : bool, default False
        Must be explicitly True for destructive recommendations (e.g. dropping rows or columns).

    Returns
    -------
    Tuple[CleaningPipeline, Dict[str, Any]]
        Updated pipeline and execution status dictionary.

    Raises
    ------
    DestructiveOperationBlockedError
        If recommendation is destructive and approved is False.
    ValueError
        If pipeline or recommendation is None.
    """
    if pipeline is None:
        raise ValueError("Pipeline cannot be None.")
    if recommendation is None:
        raise ValueError("Recommendation cannot be None.")

    # Safety Enforcement Gate
    if recommendation.is_destructive and not approved:
        raise DestructiveOperationBlockedError(
            f"Blocked destructive operation '{recommendation.pipeline_operation}' on '{recommendation.column}'. "
            f"Explicit approval (approved=True) is required to delete rows or columns."
        )

    op = recommendation.pipeline_operation
    params = recommendation.pipeline_parameters

    if op == "handle_missing_values":
        pipeline.handle_missing_values(**params)
    elif op == "handle_duplicates":
        pipeline.handle_duplicates(**params)
    elif op == "handle_outliers":
        pipeline.handle_outliers(**params)
    elif op == "clean_text":
        pipeline.clean_text(**params)
    elif op == "cast_types":
        pipeline.cast_types(**params)
    else:
        raise ValueError(f"Unknown pipeline operation '{op}'.")

    return pipeline, {
        "status": "applied",
        "recommendation_id": recommendation.id,
        "operation": op,
        "is_destructive": recommendation.is_destructive,
    }


def apply_all_safe_recommendations(
    pipeline: CleaningPipeline,
    recommendations: Sequence[RemediationRecommendation],
) -> Tuple[CleaningPipeline, Dict[str, Any]]:
    """Execute all non-destructive recommendations automatically, skipping destructive operations.

    Parameters
    ----------
    pipeline : CleaningPipeline
        The cleaning pipeline instance to execute transformations on.
    recommendations : Sequence[RemediationRecommendation]
        List of recommendations generated by the recommendation engine.

    Returns
    -------
    Tuple[CleaningPipeline, Dict[str, Any]]
        Updated pipeline and summary of applied safe actions vs. deferred destructive actions.
    """
    if pipeline is None:
        raise ValueError("Pipeline cannot be None.")
    if recommendations is None:
        raise ValueError("Recommendations cannot be None.")

    applied_ids: List[str] = []
    deferred_destructive_ids: List[str] = []

    for rec in recommendations:
        if rec.is_destructive:
            deferred_destructive_ids.append(rec.id)
            continue

        try:
            apply_recommendation(pipeline, rec, approved=False)
            applied_ids.append(rec.id)
        except Exception:
            pass

    return pipeline, {
        "applied_count": len(applied_ids),
        "applied_ids": applied_ids,
        "deferred_destructive_count": len(deferred_destructive_ids),
        "deferred_destructive_ids": deferred_destructive_ids,
    }
