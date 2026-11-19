"""Unit tests for database module (SQLite Persistence Layer)."""

import numpy as np
import pandas as pd
import pytest

from database import (
    DatabaseManager,
    DatabaseError,
    RecordNotFoundError,
    DestructiveActionConfirmationRequiredError,
    safe_json_dumps,
    safe_json_loads,
)
from backend.cleaning import CleaningPipeline, AuditLogEntry
from backend.profiling import profile_dataset
from ai.recommender import RemediationRecommendation


@pytest.fixture
def mem_db():
    """Create an ephemeral in-memory database manager for testing."""
    manager = DatabaseManager(db_path=":memory:", auto_init=True)
    yield manager
    manager.close()


@pytest.fixture
def sample_profile_data():
    """Generate sample profiling output using backend.profiling."""
    df = pd.DataFrame({
        "id": [1, 2, 3, 4],
        "val": [10.0, None, 30.0, 40.0],
        "status": ["A", "B", "A", "B"],
    })
    return profile_dataset(df)


# ---------------------------------------------------------------------------
# 1. Schema & Connection Tests
# ---------------------------------------------------------------------------

def test_schema_tables_exist_in_memory(mem_db):
    with mem_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cursor.fetchall()}

    expected_tables = {
        "analysis_runs",
        "profiling_reports",
        "ai_recommendations",
        "cleaning_history",
        "quality_comparisons",
    }
    assert expected_tables.issubset(tables)


def test_file_based_db_initialization(tmp_path):
    db_file = tmp_path / "datafix_test.db"
    manager = DatabaseManager(db_path=str(db_file), auto_init=True)
    assert db_file.exists()

    run_id = manager.create_analysis_run(dataset_name="test.csv", file_format="csv")
    assert run_id is not None
    manager.close()


# ---------------------------------------------------------------------------
# 2. Analysis Runs CRUD Tests
# ---------------------------------------------------------------------------

def test_analysis_run_lifecycle(mem_db):
    # Create
    run_id = mem_db.create_analysis_run(
        dataset_name="sales.csv",
        file_format="csv",
        file_size_bytes=1024,
        notes="Initial quarterly review",
    )
    assert run_id is not None

    # Retrieve
    run = mem_db.get_run(run_id)
    assert run is not None
    assert run["id"] == run_id
    assert run["dataset_name"] == "sales.csv"
    assert run["status"] == "profiled"
    assert run["notes"] == "Initial quarterly review"

    # Update status
    mem_db.update_run_status(run_id, status="cleaned", notes="Cleaned 2 duplicate rows")
    updated_run = mem_db.get_run(run_id)
    assert updated_run["status"] == "cleaned"
    assert updated_run["notes"] == "Cleaned 2 duplicate rows"

    # List
    runs = mem_db.list_runs(limit=10)
    assert len(runs) >= 1
    assert runs[0]["id"] == run_id


def test_delete_run_requires_confirmation(mem_db):
    run_id = mem_db.create_analysis_run("test.csv", "csv")

    # Calling without confirm=True must raise
    with pytest.raises(DestructiveActionConfirmationRequiredError):
        mem_db.delete_run(run_id, confirm=False)

    # Calling with confirm=True succeeds
    deleted = mem_db.delete_run(run_id, confirm=True)
    assert deleted is True
    assert mem_db.get_run(run_id) is None


def test_foreign_key_cascade_deletion(mem_db, sample_profile_data):
    run_id = mem_db.create_analysis_run("cascade_test.csv", "csv")

    # Save child records across all 4 tables
    mem_db.save_profiling_report(run_id, sample_profile_data, stage="initial")

    rec = RemediationRecommendation(
        rec_id="REC-001",
        category="missing_values",
        severity="medium",
        column="val",
        problem_description="Missing values",
        recommended_action="Impute with median",
        rationale="Robust",
        confidence_score=0.9,
        is_destructive=False,
        pipeline_operation="handle_missing_values",
        pipeline_parameters={"columns": ["val"], "strategy": "median"},
    )
    mem_db.save_recommendations(run_id, [rec])

    mem_db.save_cleaning_step(
        run_id,
        AuditLogEntry(
            step=1,
            operation="handle_missing_values",
            columns=["val"],
            strategy="median",
            parameters={},
            rows_before=4,
            rows_after=4,
            rows_affected=1,
            details="Imputed 1 value",
        ),
    )

    mem_db.save_quality_comparison(run_id, sample_profile_data, sample_profile_data)

    # Verify child records exist
    assert mem_db.get_profiling_report(run_id, stage="initial") is not None
    assert len(mem_db.get_recommendations(run_id)) == 1
    assert len(mem_db.get_cleaning_history(run_id)) == 1
    assert mem_db.get_quality_comparison(run_id) is not None

    # Delete run with confirmation
    mem_db.delete_run(run_id, confirm=True)

    # Child records must be cascade deleted
    assert mem_db.get_profiling_report(run_id, stage="initial") is None
    assert len(mem_db.get_recommendations(run_id)) == 0
    assert len(mem_db.get_cleaning_history(run_id)) == 0
    assert mem_db.get_quality_comparison(run_id) is None


# ---------------------------------------------------------------------------
# 3. Profiling Report Persistence Tests
# ---------------------------------------------------------------------------

def test_profiling_report_persistence(mem_db, sample_profile_data):
    run_id = mem_db.create_analysis_run("profiling_test.csv", "csv")

    report_id = mem_db.save_profiling_report(run_id, sample_profile_data, stage="initial")
    assert report_id > 0

    saved_report = mem_db.get_profiling_report(run_id, stage="initial")
    assert saved_report is not None
    assert saved_report["total_rows"] == 4
    assert saved_report["total_columns"] == 3
    assert saved_report["overall_quality_score"] > 0
    assert "overview" in saved_report["details"]
    assert "missing_values" in saved_report["details"]


# ---------------------------------------------------------------------------
# 4. AI Recommendations Persistence Tests
# ---------------------------------------------------------------------------

def test_ai_recommendations_persistence_and_status_update(mem_db):
    run_id = mem_db.create_analysis_run("recs_test.csv", "csv")

    rec1 = RemediationRecommendation(
        rec_id="REC-001",
        category="duplicates",
        severity="high",
        column="dataset",
        problem_description="Duplicate rows found",
        recommended_action="Remove duplicates",
        rationale="Inflates sample weights",
        confidence_score=0.98,
        is_destructive=True,
        pipeline_operation="handle_duplicates",
        pipeline_parameters={"strategy": "drop_first"},
    )
    rec2 = RemediationRecommendation(
        rec_id="REC-002",
        category="missing_values",
        severity="medium",
        column="val",
        problem_description="Missing values found",
        recommended_action="Impute with median",
        rationale="Symmetric",
        confidence_score=0.89,
        is_destructive=False,
        pipeline_operation="handle_missing_values",
        pipeline_parameters={"columns": ["val"], "strategy": "median"},
    )

    ids = mem_db.save_recommendations(run_id, [rec1, rec2])
    assert len(ids) == 2

    recs = mem_db.get_recommendations(run_id)
    assert len(recs) == 2
    assert recs[0]["rec_code"] == "REC-001"
    assert recs[0]["is_destructive"] is True
    assert recs[0]["status"] == "pending"

    # Update recommendation status
    mem_db.update_recommendation_status(ids[0], status="applied")
    applied_recs = mem_db.get_recommendations(run_id, status="applied")
    assert len(applied_recs) == 1
    assert applied_recs[0]["id"] == ids[0]


# ---------------------------------------------------------------------------
# 5. Cleaning History & Pipeline Integration Tests
# ---------------------------------------------------------------------------

def test_cleaning_pipeline_history_persistence(mem_db):
    run_id = mem_db.create_analysis_run("pipeline_history.csv", "csv")

    df = pd.DataFrame({
        "id": [1, 2, 2, 3],
        "name": ["  alice ", "Bob", "Bob", "Charlie"],
        "score": [10.0, 20.0, 20.0, None],
    })
    pipeline = CleaningPipeline(df)
    pipeline.handle_duplicates().clean_text(columns=["name"]).handle_missing_values(columns=["score"], strategy="mean")

    saved_step_ids = mem_db.save_cleaning_pipeline_history(run_id, pipeline)
    assert len(saved_step_ids) == 3

    history = mem_db.get_cleaning_history(run_id)
    assert len(history) == 3
    assert history[0]["operation"] == "handle_duplicates"
    assert history[1]["operation"] == "clean_text_columns"
    assert history[2]["operation"] == "handle_missing_values"
    assert isinstance(history[0]["parameters"], dict)


# ---------------------------------------------------------------------------
# 6. Quality Comparison & Session Aggregation Tests
# ---------------------------------------------------------------------------

def test_quality_comparison_and_complete_session(mem_db):
    run_id = mem_db.create_analysis_run("complete_session.csv", "csv")

    raw_df = pd.DataFrame({"a": [1, 2, 2, None], "b": [10, 20, 20, 40]})
    clean_df = pd.DataFrame({"a": [1.0, 2.0, 3.0], "b": [10, 20, 40]})

    profile_before = profile_dataset(raw_df)
    profile_after = profile_dataset(clean_df)

    mem_db.save_profiling_report(run_id, profile_before, stage="initial")
    mem_db.save_profiling_report(run_id, profile_after, stage="post_cleaning")
    mem_db.save_quality_comparison(run_id, profile_before, profile_after)

    comp = mem_db.get_quality_comparison(run_id)
    assert comp is not None
    assert comp["score_before"] == profile_before["quality_summary"]["overall_score"]
    assert comp["score_after"] == profile_after["quality_summary"]["overall_score"]
    assert comp["score_delta"] == round(comp["score_after"] - comp["score_before"], 2)

    # Complete session retrieval
    session = mem_db.get_complete_session(run_id)
    assert session["run"]["id"] == run_id
    assert session["initial_profile"] is not None
    assert session["post_cleaning_profile"] is not None
    assert session["quality_comparison"] is not None


# ---------------------------------------------------------------------------
# 7. Safe JSON Serialization Tests
# ---------------------------------------------------------------------------

def test_safe_json_dumps_numpy_pandas():
    complex_dict = {
        "np_int": np.int64(42),
        "np_float": np.float64(3.1415),
        "np_nan": np.nan,
        "np_inf": np.inf,
        "pd_timestamp": pd.Timestamp("2026-11-19 12:00:00"),
        "np_array": np.array([1, 2, 3]),
    }
    serialized = safe_json_dumps(complex_dict)
    assert isinstance(serialized, str)

    deserialized = safe_json_loads(serialized)
    assert deserialized["np_int"] == 42
    assert deserialized["np_float"] == 3.1415
    assert deserialized["np_nan"] is None
    assert deserialized["np_inf"] is None
    assert deserialized["np_array"] == [1, 2, 3]
