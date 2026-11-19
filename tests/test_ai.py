"""Unit tests for ai module (Anomaly Detection and Remediation Recommender)."""

import json
import numpy as np
import pandas as pd
import pytest

from ai import (
    detect_anomalies,
    generate_recommendations,
    apply_recommendation,
    apply_all_safe_recommendations,
    RemediationRecommendation,
    DestructiveOperationBlockedError,
)
from backend.cleaning import CleaningPipeline


@pytest.fixture
def sample_numeric_df():
    """Create a dataset with standard cluster and injected multivariate anomalies."""
    np.random.seed(42)
    # 40 normal clustered data points
    x = np.random.normal(loc=50.0, scale=5.0, size=40)
    y = np.random.normal(loc=100.0, scale=10.0, size=40)
    # 2 injected extreme anomalies
    x = np.append(x, [500.0, -200.0])
    y = np.append(y, [1000.0, -500.0])
    return pd.DataFrame({"feat_a": x, "feat_b": y})


@pytest.fixture
def multi_issue_df():
    """Create a dataset with missingness, duplicates, outliers, formatted text, and currency strings."""
    return pd.DataFrame({
        "id": [1, 2, 2, 3, 4, 5, 6, 7],
        "name": ["  alice ", "Bob", "Bob", "Charlie", "David", "Eve", "Frank", "   "],
        "age": [25.0, 30.0, 30.0, 150.0, 28.0, 22.0, None, 29.0],  # 150 is outlier, 1 missing, row 2 duplicate
        "salary_str": ["$50,000", "$60,000", "$60,000", "$75,000", "$80,000", "$52,000", "$45,000", "$62,000"],
        "unusable_col": [None, None, None, None, None, None, "data", None],  # 87.5% missing
    })


# ---------------------------------------------------------------------------
# 1. Isolation Forest Anomaly Detection Tests
# ---------------------------------------------------------------------------

def test_detect_anomalies_finds_injected_outliers(sample_numeric_df):
    results = detect_anomalies(sample_numeric_df, contamination=0.05, random_state=42)
    assert results["is_detected"] is True
    assert results["anomaly_count"] >= 2
    assert results["anomaly_percentage"] > 0.0
    assert len(results["anomaly_scores"]) == len(sample_numeric_df)

    # Injected anomalies at index 40 and 41 should be flagged
    flagged = set(results["anomaly_indices"])
    assert 40 in flagged or 41 in flagged


def test_detect_anomalies_small_dataset():
    small_df = pd.DataFrame({"a": [1.0, 2.0]})
    results = detect_anomalies(small_df)
    assert results["is_detected"] is False
    assert results["anomaly_count"] == 0
    assert "minimum 3 rows required" in results["details"]


def test_detect_anomalies_no_numeric_columns():
    text_df = pd.DataFrame({"cat": ["A", "B", "C", "D"]})
    results = detect_anomalies(text_df)
    assert results["is_detected"] is False
    assert results["anomaly_count"] == 0
    assert "No numerical columns available" in results["details"]


def test_detect_anomalies_with_nans():
    df_with_nans = pd.DataFrame({
        "x": [10.0, 12.0, 11.0, None, 13.0, 500.0],
        "y": [20.0, None, 22.0, 21.0, 23.0, 900.0],
    })
    results = detect_anomalies(df_with_nans, contamination=0.2)
    assert results["is_detected"] is True
    assert 5 in results["anomaly_indices"]


def test_detect_anomalies_zero_variance():
    df_const = pd.DataFrame({"x": [5.0, 5.0, 5.0, 5.0], "y": [10.0, 10.0, 10.0, 10.0]})
    results = detect_anomalies(df_const)
    assert results["is_detected"] is False
    assert results["anomaly_count"] == 0


def test_detect_anomalies_invalid_input():
    with pytest.raises(ValueError):
        detect_anomalies(None)

    with pytest.raises(TypeError):
        detect_anomalies([1, 2, 3])


# ---------------------------------------------------------------------------
# 2. Recommendation Engine Tests
# ---------------------------------------------------------------------------

def test_generate_recommendations_fields(multi_issue_df):
    recs = generate_recommendations(multi_issue_df)
    assert len(recs) > 0

    for rec in recs:
        # Verify required contract fields
        assert hasattr(rec, "id") and rec.id.startswith("REC-")
        assert rec.problem_description != ""
        assert rec.recommended_action != ""
        assert rec.rationale != ""
        assert 0.0 <= rec.confidence_score <= 1.0
        assert isinstance(rec.is_destructive, bool)
        assert rec.pipeline_operation != ""
        assert isinstance(rec.pipeline_parameters, dict)


def test_generate_recommendations_severe_missing(multi_issue_df):
    recs = generate_recommendations(multi_issue_df)
    # unusable_col has >70% missing values
    col_recs = [r for r in recs if r.column == "unusable_col"]
    assert len(col_recs) >= 1
    severe_rec = col_recs[0]
    assert severe_rec.severity == "critical"
    assert severe_rec.is_destructive is True
    assert severe_rec.pipeline_parameters["strategy"] == "drop_column"


def test_generate_recommendations_duplicates(multi_issue_df):
    recs = generate_recommendations(multi_issue_df)
    dup_recs = [r for r in recs if r.category == "duplicates"]
    assert len(dup_recs) == 1
    rec = dup_recs[0]
    assert rec.is_destructive is True
    assert rec.pipeline_operation == "handle_duplicates"


def test_generate_recommendations_type_casting(multi_issue_df):
    recs = generate_recommendations(multi_issue_df)
    cast_recs = [r for r in recs if r.category == "type_casting" and r.column == "salary_str"]
    assert len(cast_recs) == 1
    assert cast_recs[0].pipeline_operation == "cast_types"
    assert cast_recs[0].is_destructive is False


def test_generate_recommendations_text_cleaning(multi_issue_df):
    recs = generate_recommendations(multi_issue_df)
    text_recs = [r for r in recs if r.category == "text_cleaning" and r.column == "name"]
    assert len(text_recs) == 1
    assert text_recs[0].is_destructive is False
    assert text_recs[0].pipeline_operation == "clean_text"


# ---------------------------------------------------------------------------
# 3. Execution Safety Bridge Tests
# ---------------------------------------------------------------------------

def test_destructive_operation_blocked_without_approval(multi_issue_df):
    recs = generate_recommendations(multi_issue_df)
    destructive_recs = [r for r in recs if r.is_destructive]
    assert len(destructive_recs) > 0

    target_rec = destructive_recs[0]
    pipeline = CleaningPipeline(multi_issue_df)

    # Calling without approved=True must raise DestructiveOperationBlockedError
    with pytest.raises(DestructiveOperationBlockedError) as exc_info:
        apply_recommendation(pipeline, target_rec, approved=False)

    assert "Explicit approval" in str(exc_info.value)
    # Pipeline must remain completely untouched
    assert pipeline.step_count == 0


def test_destructive_operation_allowed_with_approval(multi_issue_df):
    recs = generate_recommendations(multi_issue_df)
    destructive_recs = [r for r in recs if r.is_destructive and r.category == "duplicates"]
    assert len(destructive_recs) == 1

    dup_rec = destructive_recs[0]
    pipeline = CleaningPipeline(multi_issue_df)

    # With explicit approval=True, operation executes successfully
    updated_pipeline, res = apply_recommendation(pipeline, dup_rec, approved=True)
    assert res["status"] == "applied"
    assert updated_pipeline.step_count == 1
    assert len(updated_pipeline.get_cleaned_df()) == len(multi_issue_df) - 1


def test_apply_all_safe_recommendations_defers_destructive(multi_issue_df):
    recs = generate_recommendations(multi_issue_df)
    pipeline = CleaningPipeline(multi_issue_df)

    updated_pipeline, summary = apply_all_safe_recommendations(pipeline, recs)
    # Safe recommendations should be applied
    assert summary["applied_count"] > 0
    # Destructive recommendations should be deferred/skipped
    assert summary["deferred_destructive_count"] > 0

    # Verify no destructive operation was executed
    executed_ops = [entry["operation"] for entry in updated_pipeline.get_audit_log()]
    assert "handle_duplicates" not in executed_ops
    for entry in updated_pipeline.get_audit_log():
        if entry["operation"] == "handle_missing_values":
            assert entry["strategy"] != "drop_column"
            assert entry["strategy"] != "drop_rows"


def test_recommendation_serialization():
    rec = RemediationRecommendation(
        rec_id="REC-001",
        category="missing_values",
        severity="medium",
        column="age",
        problem_description="Age has 10% missing values.",
        recommended_action="Impute with median.",
        rationale="Robust to outliers.",
        confidence_score=0.92,
        is_destructive=False,
        pipeline_operation="handle_missing_values",
        pipeline_parameters={"columns": ["age"], "strategy": "median"},
    )
    rec_dict = rec.to_dict()
    assert rec_dict["confidence_score"] == 0.92
    json_str = json.dumps(rec_dict)
    assert isinstance(json_str, str)
