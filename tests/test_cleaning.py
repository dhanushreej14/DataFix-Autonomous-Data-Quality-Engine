"""Unit tests for backend.cleaning module."""

import json
import numpy as np
import pandas as pd
import pytest

from backend.cleaning import (
    handle_missing_values,
    handle_duplicates,
    handle_outliers,
    clean_text_columns,
    cast_column_types,
    CleaningPipeline,
    AuditLogEntry,
    DataFixCleaningError,
    InvalidStrategyError,
    ColumnNotFoundError,
)


@pytest.fixture
def dirty_sample_df():
    """Create a dirty DataFrame containing missing values, duplicates, outliers, and dirty text."""
    return pd.DataFrame({
        "id": [1, 2, 2, 3, 4, 5, 6],
        "name": ["  alice smith ", "Bob  Jones", "Bob  Jones", "Charlie!", "david", np.nan, "   "],
        "age": [25.0, 30.0, 30.0, 150.0, np.nan, 28.0, 22.0],  # 150 is outlier, 1 NaN, row 2 is duplicate
        "salary_str": ["$50,000", "$60,000", "$60,000", "$75,000", "$80,000", "$52,000", "$45,000"],
        "is_active_str": ["yes", "no", "no", "true", "FALSE", "1", "0"],
        "join_date_str": ["2026-01-10", "2026-02-15", "2026-02-15", "2026-03-01", "2026-04-12", "invalid_date", "2026-05-20"],
    })


# ---------------------------------------------------------------------------
# 1. Immutability Tests
# ---------------------------------------------------------------------------

def test_original_dataframe_immutability(dirty_sample_df):
    original_copy = dirty_sample_df.copy(deep=True)

    # Apply various functions
    handle_missing_values(dirty_sample_df, strategy="drop_rows")
    handle_duplicates(dirty_sample_df, strategy="drop_first")
    handle_outliers(dirty_sample_df, columns=["age"], strategy="clip")
    clean_text_columns(dirty_sample_df, columns=["name"], case="lower")

    # Original DataFrame must remain completely untouched
    pd.testing.assert_frame_equal(dirty_sample_df, original_copy)


# ---------------------------------------------------------------------------
# 2. Missing Value Remediation Tests
# ---------------------------------------------------------------------------

def test_missing_values_mean(dirty_sample_df):
    clean_df, entry = handle_missing_values(dirty_sample_df, columns=["age"], strategy="mean")
    assert clean_df["age"].isna().sum() == 0
    # Mean of non-NaN ages (25, 30, 30, 150, 28, 22) = 285 / 6 = 47.5
    assert clean_df.loc[4, "age"] == 47.5
    assert entry.rows_affected == 1
    assert entry.strategy == "mean"


def test_missing_values_median(dirty_sample_df):
    clean_df, entry = handle_missing_values(dirty_sample_df, columns=["age"], strategy="median")
    assert clean_df["age"].isna().sum() == 0
    # Median of [22, 25, 28, 30, 30, 150] is (28 + 30) / 2 = 29.0
    assert clean_df.loc[4, "age"] == 29.0
    assert entry.rows_affected == 1


def test_missing_values_mode():
    df = pd.DataFrame({"category": ["A", "B", "A", None, "C", "A"]})
    clean_df, entry = handle_missing_values(df, columns=["category"], strategy="mode")
    assert clean_df["category"].isna().sum() == 0
    assert clean_df.loc[3, "category"] == "A"
    assert entry.rows_affected == 1


def test_missing_values_constant():
    df = pd.DataFrame({"score": [10.0, None, 30.0]})
    clean_df, entry = handle_missing_values(df, columns=["score"], strategy="constant", fill_value=0.0)
    assert clean_df["score"].isna().sum() == 0
    assert clean_df.loc[1, "score"] == 0.0
    assert entry.rows_affected == 1


def test_missing_values_forward_backward_fill():
    df = pd.DataFrame({"val": [10, None, None, 40]})
    clean_ffill, _ = handle_missing_values(df, columns=["val"], strategy="forward_fill")
    assert list(clean_ffill["val"]) == [10, 10, 10, 40]

    clean_bfill, _ = handle_missing_values(df, columns=["val"], strategy="backward_fill")
    assert list(clean_bfill["val"]) == [10, 40, 40, 40]


def test_missing_values_drop_rows(dirty_sample_df):
    clean_df, entry = handle_missing_values(dirty_sample_df, columns=["age"], strategy="drop_rows")
    assert clean_df["age"].isna().sum() == 0
    assert len(clean_df) == len(dirty_sample_df) - 1
    assert entry.rows_affected == 1


def test_missing_values_drop_column(dirty_sample_df):
    clean_df, entry = handle_missing_values(dirty_sample_df, columns=["age"], strategy="drop_column")
    assert "age" not in clean_df.columns
    assert len(clean_df) == len(dirty_sample_df)


def test_missing_values_invalid_strategy(dirty_sample_df):
    with pytest.raises(InvalidStrategyError):
        handle_missing_values(dirty_sample_df, strategy="magic_impute")


def test_missing_values_mean_on_non_numeric():
    df = pd.DataFrame({"name": ["Alice", None, "Bob"]})
    with pytest.raises(InvalidStrategyError):
        handle_missing_values(df, columns=["name"], strategy="mean")


def test_missing_values_constant_without_fill_value():
    df = pd.DataFrame({"val": [1, None, 3]})
    with pytest.raises(ValueError):
        handle_missing_values(df, columns=["val"], strategy="constant", fill_value=None)


# ---------------------------------------------------------------------------
# 3. Duplicate Handling Tests
# ---------------------------------------------------------------------------

def test_handle_duplicates_drop_first(dirty_sample_df):
    clean_df, entry = handle_duplicates(dirty_sample_df, strategy="drop_first")
    assert len(clean_df) == len(dirty_sample_df) - 1
    assert entry.rows_affected == 1
    assert clean_df.iloc[1]["id"] == 2


def test_handle_duplicates_drop_last(dirty_sample_df):
    clean_df, entry = handle_duplicates(dirty_sample_df, strategy="drop_last")
    assert len(clean_df) == len(dirty_sample_df) - 1
    assert entry.rows_affected == 1


def test_handle_duplicates_drop_all():
    df = pd.DataFrame({"a": [1, 2, 2, 3]})
    clean_df, entry = handle_duplicates(df, strategy="drop_all")
    assert len(clean_df) == 2
    assert list(clean_df["a"]) == [1, 3]
    assert entry.rows_affected == 2


def test_handle_duplicates_subset():
    df = pd.DataFrame({
        "id": [1, 1, 2],
        "version": ["v1", "v2", "v1"]
    })
    # If checking whole row, all 3 are distinct
    clean_all, _ = handle_duplicates(df, strategy="drop_first")
    assert len(clean_all) == 3

    # If checking subset=['id'], row 2 is duplicate
    clean_sub, entry = handle_duplicates(df, subset=["id"], strategy="drop_first")
    assert len(clean_sub) == 2
    assert entry.rows_affected == 1


def test_handle_duplicates_invalid_strategy(dirty_sample_df):
    with pytest.raises(InvalidStrategyError):
        handle_duplicates(dirty_sample_df, strategy="keep_random")


def test_handle_duplicates_column_not_found(dirty_sample_df):
    with pytest.raises(ColumnNotFoundError):
        handle_duplicates(dirty_sample_df, subset=["non_existent_col"])


# ---------------------------------------------------------------------------
# 4. Outlier Remediation Tests
# ---------------------------------------------------------------------------

def test_handle_outliers_iqr_clip(dirty_sample_df):
    # age has outlier 150.0
    clean_df, entry = handle_outliers(
        dirty_sample_df,
        columns=["age"],
        method="iqr",
        strategy="clip",
        factor=1.5
    )
    assert clean_df.loc[3, "age"] < 150.0
    assert entry.rows_affected >= 1
    assert "bounds" in entry.parameters


def test_handle_outliers_iqr_drop(dirty_sample_df):
    clean_df, entry = handle_outliers(
        dirty_sample_df,
        columns=["age"],
        method="iqr",
        strategy="drop",
        factor=1.5
    )
    assert len(clean_df) < len(dirty_sample_df)
    assert 150.0 not in clean_df["age"].values


def test_handle_outliers_iqr_set_null(dirty_sample_df):
    clean_df, entry = handle_outliers(
        dirty_sample_df,
        columns=["age"],
        method="iqr",
        strategy="set_null",
        factor=1.5
    )
    assert np.isnan(clean_df.loc[3, "age"])
    assert entry.rows_affected >= 1


def test_handle_outliers_zscore_clip():
    df = pd.DataFrame({"val": [10.0, 10.1, 9.9, 10.0, 10.2, 9.8, 100.0]})
    clean_df, entry = handle_outliers(df, columns=["val"], method="zscore", strategy="clip", factor=2.0)
    assert clean_df.loc[6, "val"] < 100.0
    assert entry.rows_affected >= 1


def test_handle_outliers_non_numeric_error(dirty_sample_df):
    with pytest.raises(InvalidStrategyError):
        handle_outliers(dirty_sample_df, columns=["name"])


def test_handle_outliers_invalid_method(dirty_sample_df):
    with pytest.raises(InvalidStrategyError):
        handle_outliers(dirty_sample_df, columns=["age"], method="unknown_method")


# ---------------------------------------------------------------------------
# 5. Text Standardization Tests
# ---------------------------------------------------------------------------

def test_clean_text_columns_casing_and_strip(dirty_sample_df):
    clean_df, entry = clean_text_columns(
        dirty_sample_df,
        columns=["name"],
        strip_whitespace=True,
        case="title",
        remove_special_chars=True,
        replace_empty_with_nan=True,
    )
    # "  alice smith " -> "Alice Smith"
    assert clean_df.loc[0, "name"] == "Alice Smith"
    # "Charlie!" -> "Charlie" (special char removed)
    assert clean_df.loc[3, "name"] == "Charlie"
    # "   " -> NaN (empty string converted to NaN)
    assert pd.isna(clean_df.loc[6, "name"])
    assert entry.rows_affected >= 1


def test_clean_text_columns_lower_upper():
    df = pd.DataFrame({"city": ["  New York  ", "san francisco"]})
    clean_upper, _ = clean_text_columns(df, columns=["city"], case="upper")
    assert clean_upper.loc[0, "city"] == "NEW YORK"
    assert clean_upper.loc[1, "city"] == "SAN FRANCISCO"

    clean_lower, _ = clean_text_columns(df, columns=["city"], case="lower")
    assert clean_lower.loc[0, "city"] == "new york"


def test_clean_text_invalid_case(dirty_sample_df):
    with pytest.raises(InvalidStrategyError):
        clean_text_columns(dirty_sample_df, columns=["name"], case="invalid_case")


# ---------------------------------------------------------------------------
# 6. Type Casting Tests
# ---------------------------------------------------------------------------

def test_cast_column_types_numeric_and_bool_and_date(dirty_sample_df):
    type_map = {
        "salary_str": "float",
        "is_active_str": "boolean",
        "join_date_str": "datetime",
    }
    clean_df, entry = cast_column_types(dirty_sample_df, type_map=type_map)

    # Check numeric conversion from "$50,000" to 50000.0
    assert pd.api.types.is_float_dtype(clean_df["salary_str"])
    assert clean_df.loc[0, "salary_str"] == 50000.0

    # Check boolean mapping: "yes" -> True, "no" -> False
    assert str(clean_df["is_active_str"].dtype) == "boolean"
    assert clean_df.loc[0, "is_active_str"] is True or clean_df.loc[0, "is_active_str"] == True
    assert clean_df.loc[1, "is_active_str"] is False or clean_df.loc[1, "is_active_str"] == False

    # Check datetime conversion: invalid_date should become NaT
    assert pd.api.types.is_datetime64_any_dtype(clean_df["join_date_str"])
    assert pd.isna(clean_df.loc[5, "join_date_str"])
    assert entry.rows_affected >= 1


def test_cast_column_types_int():
    df = pd.DataFrame({"count_str": ["10", "20.0", "$30", None]})
    clean_df, entry = cast_column_types(df, type_map={"count_str": "int"})
    assert str(clean_df["count_str"].dtype) == "Int64"
    assert clean_df.loc[0, "count_str"] == 10
    assert clean_df.loc[2, "count_str"] == 30
    assert pd.isna(clean_df.loc[3, "count_str"])


def test_cast_column_types_invalid_target_type(dirty_sample_df):
    with pytest.raises(InvalidStrategyError):
        cast_column_types(dirty_sample_df, type_map={"name": "unsupported_type"})


# ---------------------------------------------------------------------------
# 7. Cleaning Pipeline & Execution Tests
# ---------------------------------------------------------------------------

def test_cleaning_pipeline_end_to_end(dirty_sample_df):
    pipeline = CleaningPipeline(dirty_sample_df)

    pipeline.handle_duplicates(strategy="drop_first") \
            .clean_text(columns=["name"], case="title", remove_special_chars=True) \
            .handle_outliers(columns=["age"], method="iqr", strategy="clip") \
            .handle_missing_values(columns=["age"], strategy="median") \
            .cast_types({"salary_str": "float", "is_active_str": "boolean"})

    cleaned_df = pipeline.get_cleaned_df()
    original_df = pipeline.get_original_df()
    audit_log = pipeline.get_audit_log()
    summary = pipeline.get_summary()

    # Original DataFrame must remain unchanged
    pd.testing.assert_frame_equal(original_df, dirty_sample_df)

    # Cleaned DataFrame assertions
    assert len(cleaned_df) == len(dirty_sample_df) - 1  # 1 duplicate removed
    assert cleaned_df["age"].isna().sum() == 0          # missing value imputed
    assert cleaned_df["salary_str"].dtype == np.float64 # casted to float

    # Pipeline summary assertions
    assert summary["total_steps"] == 5
    assert len(audit_log) == 5
    assert summary["rows_delta"] == -1
    assert summary["operations_executed"] == [
        "handle_duplicates",
        "clean_text_columns",
        "handle_outliers",
        "handle_missing_values",
        "cast_column_types",
    ]

    # Audit log is JSON serializable
    json_log = json.dumps(audit_log)
    assert isinstance(json_log, str)


def test_empty_dataframe_pipeline():
    empty_df = pd.DataFrame(columns=["a", "b"])
    pipeline = CleaningPipeline(empty_df)
    pipeline.handle_duplicates().clean_text().handle_missing_values()

    cleaned = pipeline.get_cleaned_df()
    assert len(cleaned) == 0
    assert pipeline.step_count == 3


def test_invalid_input_to_pipeline():
    with pytest.raises(ValueError):
        CleaningPipeline(None)

    with pytest.raises(TypeError):
        CleaningPipeline([1, 2, 3])
