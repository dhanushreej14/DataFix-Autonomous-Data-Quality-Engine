"""Unit tests for backend.profiling module."""

import json
import numpy as np
import pandas as pd
import pytest

from backend.profiling import (
    profile_dataset,
    get_dataset_overview,
    get_column_types,
    get_missing_values,
    get_duplicate_summary,
    get_unique_values,
    get_numerical_summary,
    get_categorical_summary,
    get_data_quality_summary,
)


@pytest.fixture
def sample_dataframe():
    """Create a diverse sample DataFrame for profiling tests."""
    return pd.DataFrame({
        "id": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "name": ["Alice", "Bob", "Charlie", "David", "Eve", "Frank", "Grace", "Heidi", "Ivan", "Judy"],
        "age": [25, 30, 35, 40, None, 28, 32, 120, 22, 29],  # 1 missing, 1 outlier (120)
        "salary": [50000.0, 60000.0, 75000.0, 80000.0, 95000.0, 52000.0, 68000.0, 250000.0, 48000.0, 61000.0],
        "department": ["IT", "HR", "IT", "Sales", "IT", "HR", "Sales", "IT", "Sales", "IT"],
        "is_active": [True, True, False, True, False, True, True, True, False, True],
        "country": ["USA", "USA", "USA", "USA", "USA", "USA", "USA", "USA", "USA", "USA"],  # Constant
    })


def test_get_dataset_overview(sample_dataframe):
    overview = get_dataset_overview(sample_dataframe)
    assert overview["total_rows"] == 10
    assert overview["total_columns"] == 7
    assert overview["total_cells"] == 70
    assert overview["memory_usage_bytes"] > 0
    assert overview["is_empty"] is False


def test_get_column_types(sample_dataframe):
    col_types = get_column_types(sample_dataframe)
    assert "id" in col_types["numerical_columns"]
    assert "age" in col_types["numerical_columns"]
    assert "salary" in col_types["numerical_columns"]
    assert "department" in col_types["categorical_columns"]
    assert "country" in col_types["categorical_columns"]
    assert "is_active" in col_types["boolean_columns"]
    assert col_types["counts"]["total"] == 7


def test_get_missing_values(sample_dataframe):
    missing = get_missing_values(sample_dataframe)
    assert missing["total_missing_cells"] == 1
    assert "age" in missing["columns_with_missing"]
    assert missing["columns"]["age"]["missing_count"] == 1
    assert missing["columns"]["age"]["missing_percentage"] == 10.0
    assert "name" in missing["complete_columns"]
    assert missing["columns_with_missing_count"] == 1


def test_get_duplicate_summary():
    df_with_dups = pd.DataFrame({
        "a": [1, 2, 2, 3],
        "b": ["x", "y", "y", "z"],
    })
    dup_info = get_duplicate_summary(df_with_dups)
    assert dup_info["has_duplicates"] is True
    assert dup_info["duplicate_rows_count"] == 1
    assert dup_info["duplicate_rows_percentage"] == 25.0
    assert dup_info["unique_rows_count"] == 3


def test_get_unique_values(sample_dataframe):
    uniques = get_unique_values(sample_dataframe)
    cols = uniques["columns"]
    # country is constant
    assert cols["country"]["is_constant"] is True
    assert cols["country"]["unique_count"] == 1
    assert cols["country"]["cardinality"] == "constant"

    # id is unique identifier
    assert cols["id"]["is_unique"] is True
    assert cols["id"]["cardinality"] == "unique_identifier"

    # department is low cardinality
    assert cols["department"]["cardinality"] == "low"
    assert cols["department"]["unique_count"] == 3


def test_get_numerical_summary(sample_dataframe):
    num_summary = get_numerical_summary(sample_dataframe)
    assert "salary" in num_summary
    assert "age" in num_summary

    sal = num_summary["salary"]
    assert sal["count"] == 10
    assert sal["min"] == 48000.0
    assert sal["max"] == 250000.0
    assert sal["median"] == 64500.0
    assert sal["iqr"] > 0
    # Outlier detection: 250,000 should be detected as an outlier
    assert sal["outliers_count"] >= 1


def test_get_categorical_summary(sample_dataframe):
    cat_summary = get_categorical_summary(sample_dataframe)
    assert "department" in cat_summary

    dept = cat_summary["department"]
    assert dept["count"] == 10
    assert dept["unique_count"] == 3
    assert dept["mode"] == "IT"
    assert dept["mode_frequency"] == 5
    assert dept["mode_percentage"] == 50.0
    assert len(dept["top_values"]) == 3


def test_get_data_quality_summary(sample_dataframe):
    quality = get_data_quality_summary(sample_dataframe)
    assert "overall_score" in quality
    assert 0.0 <= quality["overall_score"] <= 100.0
    assert quality["rating"] in ["Excellent", "Good", "Fair", "Poor"]
    assert quality["completeness_score"] > 90.0
    assert quality["uniqueness_score"] == 100.0

    # Constant column alert should be generated for 'country'
    alert_messages = [a["message"] for a in quality["alerts"]]
    assert any("country" in msg and "zero variance" in msg for msg in alert_messages)


def test_profile_dataset_end_to_end_and_json_serializable(sample_dataframe):
    profile = profile_dataset(sample_dataframe)
    expected_keys = [
        "overview",
        "column_types",
        "missing_values",
        "duplicates",
        "unique_values",
        "numerical_stats",
        "categorical_stats",
        "quality_summary",
    ]
    for key in expected_keys:
        assert key in profile

    # Ensure profile output is fully JSON serializable (no unhandled numpy scalars or NaN)
    json_str = json.dumps(profile)
    assert isinstance(json_str, str)
    assert len(json_str) > 0


def test_profile_dataset_invalid_input():
    with pytest.raises(ValueError):
        profile_dataset(None)

    with pytest.raises(TypeError):
        profile_dataset([1, 2, 3])  # Not a DataFrame


def test_empty_dataframe_profiling():
    empty_df = pd.DataFrame()
    overview = get_dataset_overview(empty_df)
    assert overview["total_rows"] == 0
    assert overview["total_columns"] == 0
    assert overview["is_empty"] is True

    quality = get_data_quality_summary(empty_df)
    assert quality["overall_score"] == 0.0
    assert quality["rating"] == "Poor"


def test_edge_case_all_nan_column():
    df = pd.DataFrame({
        "all_nan": [None, np.nan, None],
        "values": [1, 2, 3],
    })
    missing = get_missing_values(df)
    assert missing["columns"]["all_nan"]["missing_percentage"] == 100.0

    quality = get_data_quality_summary(df)
    alerts = [a for a in quality["alerts"] if a["column"] == "all_nan"]
    assert len(alerts) > 0
    assert alerts[0]["level"] == "critical"


def test_edge_case_single_row_dataframe():
    df = pd.DataFrame({
        "val": [42.0],
        "cat": ["single"],
    })
    profile = profile_dataset(df)
    assert profile["overview"]["total_rows"] == 1
    assert profile["numerical_stats"]["val"]["count"] == 1
    assert profile["numerical_stats"]["val"]["mean"] == 42.0
    assert profile["numerical_stats"]["val"]["std"] == 0.0


def test_edge_case_datetime_column():
    df = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=5, freq="D"),
        "measure": [10, 20, 30, 40, 50],
    })
    col_types = get_column_types(df)
    assert "timestamp" in col_types["datetime_columns"]
    assert col_types["dtypes"]["timestamp"] == "datetime"
