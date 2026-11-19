"""Database Manager Module for DataFix Engine.

This module provides thread-safe, transaction-guarded SQLite persistence
for analysis sessions, profiling reports, AI recommendations, cleaning audit histories,
and quality score comparisons using Python's built-in sqlite3.
"""

from __future__ import annotations

import contextlib
import datetime
import json
import math
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Sequence, Union

import numpy as np
import pandas as pd

from database.schema import create_schema


# ---------------------------------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------------------------------

class DatabaseError(Exception):
    """Base exception for all persistence and database operations in DataFix."""
    pass


class RecordNotFoundError(DatabaseError):
    """Raised when a requested database record cannot be found."""
    pass


class DestructiveActionConfirmationRequiredError(DatabaseError):
    """Raised when a destructive deletion is attempted without explicit confirmation."""
    pass


# ---------------------------------------------------------------------------
# Robust JSON Serialization Helpers
# ---------------------------------------------------------------------------

def sanitize_for_json(data: Any) -> Any:
    """Recursively convert NumPy/Pandas objects, NaN, and inf into standard JSON-compliant types."""
    if data is None:
        return None
    if isinstance(data, (bool, np.bool_)):
        return bool(data)
    if isinstance(data, (int, np.integer)):
        return int(data)
    if isinstance(data, (float, np.floating)):
        if math.isnan(data) or np.isnan(data) or math.isinf(data) or np.isinf(data):
            return None
        return float(data)
    if isinstance(data, (datetime.datetime, datetime.date, pd.Timestamp)):
        return data.isoformat()
    if isinstance(data, np.ndarray):
        return [sanitize_for_json(x) for x in data.tolist()]
    if isinstance(data, (pd.Series, pd.Index)):
        return [sanitize_for_json(x) for x in data.tolist()]
    if isinstance(data, pd.DataFrame):
        return [sanitize_for_json(row) for row in data.to_dict(orient="records")]
    if hasattr(data, "to_dict") and callable(data.to_dict):
        return sanitize_for_json(data.to_dict())
    if isinstance(data, dict):
        return {str(k): sanitize_for_json(v) for k, v in data.items()}
    if isinstance(data, (list, tuple, set)):
        return [sanitize_for_json(x) for x in data]
    if np.isscalar(data) and pd.isna(data):
        return None
    return str(data)


def safe_json_dumps(data: Any) -> str:
    """Serialize data to a JSON string with safe handling of NumPy/Pandas types, NaNs, and infs."""
    sanitized = sanitize_for_json(data)
    return json.dumps(sanitized, ensure_ascii=False)


def safe_json_loads(json_str: Optional[str]) -> Any:
    """Deserialize a JSON string safely, returning empty dict if input is None/empty."""
    if not json_str:
        return {}
    try:
        return json.loads(json_str)
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# DatabaseManager Implementation
# ---------------------------------------------------------------------------

class DatabaseManager:
    """High-level SQLite database manager for DataFix.

    Supports both file-based and in-memory databases with automatic schema
    initialization, transaction safety, and parameterized queries.
    """

    def __init__(self, db_path: str = "datafix.db", auto_init: bool = True) -> None:
        """Initialize the DatabaseManager.

        Parameters
        ----------
        db_path : str, default 'datafix.db'
            Path to the SQLite database file or ':memory:' for an ephemeral database.
        auto_init : bool, default True
            Whether to automatically initialize tables and indices upon creation.
        """
        self.db_path = str(db_path)
        self.is_memory = (self.db_path == ":memory:")

        # For in-memory databases, maintain a persistent connection so tables persist across calls
        self._memory_conn: Optional[sqlite3.Connection] = None
        if self.is_memory:
            self._memory_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._memory_conn.row_factory = sqlite3.Row
            self._memory_conn.execute("PRAGMA foreign_keys = ON;")

        if auto_init:
            self.init_schema()

    def init_schema(self) -> None:
        """Initialize database tables and indices."""
        with self.get_connection() as conn:
            create_schema(conn)

    @contextlib.contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager providing an active SQLite connection with transaction management.

        Enforces `PRAGMA foreign_keys = ON;`, `row_factory = sqlite3.Row`,
        commits upon successful block exit, and rolls back on unhandled exceptions.
        """
        if self.is_memory and self._memory_conn is not None:
            conn = self._memory_conn
            conn.execute("PRAGMA foreign_keys = ON;")
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        else:
            # File-based database
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def close(self) -> None:
        """Close persistent in-memory connection if active."""
        if self._memory_conn is not None:
            try:
                self._memory_conn.close()
            except Exception:
                pass
            self._memory_conn = None

    # -----------------------------------------------------------------------
    # 1. Analysis Run Management
    # -----------------------------------------------------------------------

    def create_analysis_run(
        self,
        dataset_name: str,
        file_format: str,
        file_size_bytes: Optional[int] = None,
        run_id: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> str:
        """Create a new analysis run entry.

        Parameters
        ----------
        dataset_name : str
            Name of the ingested dataset or file.
        file_format : str
            File format extension or identifier ('csv', 'excel', etc.).
        file_size_bytes : Optional[int], default None
            Size of the file in bytes.
        run_id : Optional[str], default None
            Explicit run identifier. If None, a unique UUID string is generated.
        notes : Optional[str], default None
            Optional user or session notes.

        Returns
        -------
        str
            The created run ID.
        """
        run_id = run_id or str(uuid.uuid4())
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        sql = """
        INSERT INTO analysis_runs (id, dataset_name, file_format, file_size_bytes, status, notes, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """
        try:
            with self.get_connection() as conn:
                conn.execute(sql, (run_id, dataset_name, file_format, file_size_bytes, "profiled", notes, now_iso, now_iso))
        except sqlite3.Error as err:
            raise DatabaseError(f"Failed to create analysis run: {err}") from err

        return run_id

    def update_run_status(
        self,
        run_id: str,
        status: str,
        notes: Optional[str] = None,
    ) -> None:
        """Update the status and optional notes of an analysis run."""
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        sql = """
        UPDATE analysis_runs
        SET status = ?, notes = COALESCE(?, notes), updated_at = ?
        WHERE id = ?;
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(sql, (status, notes, now_iso, run_id))
                if cursor.rowcount == 0:
                    raise RecordNotFoundError(f"Analysis run '{run_id}' not found.")
        except sqlite3.Error as err:
            raise DatabaseError(f"Failed to update run status: {err}") from err

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve an analysis run record by its ID."""
        sql = "SELECT * FROM analysis_runs WHERE id = ?;"
        try:
            with self.get_connection() as conn:
                row = conn.execute(sql, (run_id,)).fetchone()
                return dict(row) if row else None
        except sqlite3.Error as err:
            raise DatabaseError(f"Failed to retrieve run '{run_id}': {err}") from err

    def list_runs(
        self,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List analysis runs ordered by creation date descending with optional status filtering."""
        if status:
            sql = "SELECT * FROM analysis_runs WHERE status = ? ORDER BY created_at DESC LIMIT ? OFFSET ?;"
            params = (status, limit, offset)
        else:
            sql = "SELECT * FROM analysis_runs ORDER BY created_at DESC LIMIT ? OFFSET ?;"
            params = (limit, offset)

        try:
            with self.get_connection() as conn:
                rows = conn.execute(sql, params).fetchall()
                return [dict(r) for r in rows]
        except sqlite3.Error as err:
            raise DatabaseError(f"Failed to list runs: {err}") from err

    def delete_run(self, run_id: str, confirm: bool = False) -> bool:
        """Delete an analysis run and cascade-delete all associated records.

        Parameters
        ----------
        run_id : str
            The run ID to delete.
        confirm : bool, default False
            Explicit confirmation parameter. Must be True to proceed with deletion.

        Returns
        -------
        bool
            True if a record was deleted, False if run was not found.

        Raises
        ------
        DestructiveActionConfirmationRequiredError
            If confirm is False.
        """
        if not confirm:
            raise DestructiveActionConfirmationRequiredError(
                f"Deleting analysis run '{run_id}' is a destructive operation and requires explicit confirmation (confirm=True)."
            )

        sql = "DELETE FROM analysis_runs WHERE id = ?;"
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(sql, (run_id,))
                return cursor.rowcount > 0
        except sqlite3.Error as err:
            raise DatabaseError(f"Failed to delete run '{run_id}': {err}") from err

    # -----------------------------------------------------------------------
    # 2. Profiling Reports
    # -----------------------------------------------------------------------

    def save_profiling_report(
        self,
        run_id: str,
        profile_dict: Dict[str, Any],
        stage: str = "initial",
    ) -> int:
        """Persist a dataset profiling summary report for a given analysis run.

        Parameters
        ----------
        run_id : str
            Analysis run ID foreign key.
        profile_dict : Dict[str, Any]
            Profile output produced by `backend.profiling.profile_dataset`.
        stage : str, default 'initial'
            Stage of profiling: 'initial' or 'post_cleaning'.

        Returns
        -------
        int
            Inserted profiling report database ID.
        """
        if stage not in {"initial", "post_cleaning"}:
            raise ValueError(f"Invalid stage '{stage}'. Must be 'initial' or 'post_cleaning'.")

        overview = profile_dict.get("overview", {})
        missing = profile_dict.get("missing_values", {})
        dups = profile_dict.get("duplicates", {})
        quality = profile_dict.get("quality_summary", {})

        total_rows = int(overview.get("total_rows", 0))
        total_cols = int(overview.get("total_columns", 0))
        total_cells = int(overview.get("total_cells", total_rows * total_cols))
        memory_mb = float(overview.get("memory_usage_mb", 0.0))

        total_missing = int(missing.get("total_missing_cells", 0))
        missing_pct = float(missing.get("missing_cells_percentage", 0.0))

        dup_count = int(dups.get("duplicate_rows_count", 0))
        dup_pct = float(dups.get("duplicate_rows_percentage", 0.0))

        overall_score = float(quality.get("overall_score", 0.0))
        rating = str(quality.get("rating", "Poor"))
        completeness = float(quality.get("completeness_score", 0.0))
        uniqueness = float(quality.get("uniqueness_score", 0.0))
        validity = float(quality.get("validity_score", 0.0))
        structural = float(quality.get("structural_score", 0.0))

        details_json = safe_json_dumps(profile_dict)
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        sql = """
        INSERT INTO profiling_reports (
            run_id, stage, total_rows, total_columns, total_cells,
            memory_usage_mb, total_missing_cells, missing_cells_percentage,
            duplicate_rows_count, duplicate_rows_percentage,
            overall_quality_score, quality_rating,
            completeness_score, uniqueness_score, validity_score, structural_score,
            details_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        params = (
            run_id, stage, total_rows, total_cols, total_cells,
            memory_mb, total_missing, missing_pct,
            dup_count, dup_pct,
            overall_score, rating,
            completeness, uniqueness, validity, structural,
            details_json, now_iso,
        )

        try:
            with self.get_connection() as conn:
                cursor = conn.execute(sql, params)
                return int(cursor.lastrowid)
        except sqlite3.IntegrityError as err:
            raise DatabaseError(f"Foreign key constraint or integrity error for run '{run_id}': {err}") from err
        except sqlite3.Error as err:
            raise DatabaseError(f"Failed to save profiling report: {err}") from err

    def get_profiling_report(
        self,
        run_id: str,
        stage: str = "initial",
    ) -> Optional[Dict[str, Any]]:
        """Retrieve a profiling report for a run, with deserialized details JSON."""
        sql = "SELECT * FROM profiling_reports WHERE run_id = ? AND stage = ? ORDER BY id DESC LIMIT 1;"
        try:
            with self.get_connection() as conn:
                row = conn.execute(sql, (run_id, stage)).fetchone()
                if not row:
                    return None
                data = dict(row)
                data["details"] = safe_json_loads(data.get("details_json"))
                return data
        except sqlite3.Error as err:
            raise DatabaseError(f"Failed to retrieve profiling report: {err}") from err

    # -----------------------------------------------------------------------
    # 3. AI Recommendations
    # -----------------------------------------------------------------------

    def save_recommendations(
        self,
        run_id: str,
        recommendations: Sequence[Any],
    ) -> List[int]:
        """Persist a list of AI remediation recommendations for a run.

        Parameters
        ----------
        run_id : str
            Analysis run ID foreign key.
        recommendations : Sequence[Any]
            List of `RemediationRecommendation` objects or matching dictionaries.

        Returns
        -------
        List[int]
            List of inserted recommendation database primary keys.
        """
        if not recommendations:
            return []

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        sql = """
        INSERT INTO ai_recommendations (
            run_id, rec_code, category, severity, column_name,
            problem_description, recommended_action, rationale,
            confidence_score, is_destructive, pipeline_operation,
            pipeline_parameters_json, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """

        inserted_ids: List[int] = []
        try:
            with self.get_connection() as conn:
                for rec in recommendations:
                    if hasattr(rec, "to_dict"):
                        d = rec.to_dict()
                    elif isinstance(rec, dict):
                        d = rec
                    else:
                        continue

                    rec_code = str(d.get("id", "REC-000"))
                    category = str(d.get("category", "general"))
                    severity = str(d.get("severity", "medium"))
                    column_name = d.get("column")
                    problem = str(d.get("problem_description", ""))
                    action = str(d.get("recommended_action", ""))
                    rationale = str(d.get("rationale", ""))
                    conf = float(d.get("confidence_score", 0.0))
                    is_dest = 1 if d.get("is_destructive", False) else 0
                    op = str(d.get("pipeline_operation", ""))
                    params_json = safe_json_dumps(d.get("pipeline_parameters", {}))
                    status = str(d.get("status", "pending"))

                    cursor = conn.execute(sql, (
                        run_id, rec_code, category, severity, column_name,
                        problem, action, rationale, conf, is_dest, op,
                        params_json, status, now_iso
                    ))
                    inserted_ids.append(int(cursor.lastrowid))
        except sqlite3.Error as err:
            raise DatabaseError(f"Failed to save AI recommendations: {err}") from err

        return inserted_ids

    def get_recommendations(
        self,
        run_id: str,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve stored recommendations for a run, with deserialized parameters."""
        if status:
            sql = "SELECT * FROM ai_recommendations WHERE run_id = ? AND status = ? ORDER BY id ASC;"
            params = (run_id, status)
        else:
            sql = "SELECT * FROM ai_recommendations WHERE run_id = ? ORDER BY id ASC;"
            params = (run_id,)

        try:
            with self.get_connection() as conn:
                rows = conn.execute(sql, params).fetchall()
                results = []
                for r in rows:
                    item = dict(r)
                    item["pipeline_parameters"] = safe_json_loads(item.get("pipeline_parameters_json"))
                    item["is_destructive"] = bool(item.get("is_destructive", 0))
                    results.append(item)
                return results
        except sqlite3.Error as err:
            raise DatabaseError(f"Failed to retrieve recommendations: {err}") from err

    def update_recommendation_status(self, rec_db_id: int, status: str) -> None:
        """Update recommendation review status ('applied', 'rejected', 'deferred')."""
        if status not in {"pending", "applied", "rejected", "deferred"}:
            raise ValueError(f"Invalid recommendation status '{status}'.")

        sql = "UPDATE ai_recommendations SET status = ? WHERE id = ?;"
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(sql, (status, rec_db_id))
                if cursor.rowcount == 0:
                    raise RecordNotFoundError(f"Recommendation with id '{rec_db_id}' not found.")
        except sqlite3.Error as err:
            raise DatabaseError(f"Failed to update recommendation status: {err}") from err

    # -----------------------------------------------------------------------
    # 4. Cleaning History & Auditing
    # -----------------------------------------------------------------------

    def save_cleaning_step(
        self,
        run_id: str,
        audit_entry: Any,
    ) -> int:
        """Persist a single cleaning transformation audit record."""
        if hasattr(audit_entry, "to_dict"):
            d = audit_entry.to_dict()
        elif isinstance(audit_entry, dict):
            d = audit_entry
        else:
            raise TypeError(f"Expected AuditLogEntry or dict, got {type(audit_entry).__name__}.")

        now_iso = d.get("timestamp") or datetime.datetime.now(datetime.timezone.utc).isoformat()
        sql = """
        INSERT INTO cleaning_history (
            run_id, step_number, operation, strategy,
            target_columns_json, parameters_json,
            rows_before, rows_after, rows_affected,
            details, applied_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        params = (
            run_id,
            int(d.get("step", 1)),
            str(d.get("operation", "unknown")),
            str(d.get("strategy", "unknown")),
            safe_json_dumps(d.get("columns", [])),
            safe_json_dumps(d.get("parameters", {})),
            int(d.get("rows_before", 0)),
            int(d.get("rows_after", 0)),
            int(d.get("rows_affected", 0)),
            str(d.get("details", "")),
            now_iso,
        )

        try:
            with self.get_connection() as conn:
                cursor = conn.execute(sql, params)
                return int(cursor.lastrowid)
        except sqlite3.Error as err:
            raise DatabaseError(f"Failed to save cleaning step: {err}") from err

    def save_cleaning_pipeline_history(
        self,
        run_id: str,
        pipeline: Any,
    ) -> List[int]:
        """Save the full chronological audit history from a CleaningPipeline instance."""
        if not hasattr(pipeline, "get_audit_log"):
            raise TypeError("Expected a CleaningPipeline instance with get_audit_log method.")

        audit_log = pipeline.get_audit_log()
        inserted_ids: List[int] = []
        for entry in audit_log:
            step_id = self.save_cleaning_step(run_id, entry)
            inserted_ids.append(step_id)
        return inserted_ids

    def get_cleaning_history(self, run_id: str) -> List[Dict[str, Any]]:
        """Retrieve the ordered transformation audit history for a run."""
        sql = "SELECT * FROM cleaning_history WHERE run_id = ? ORDER BY step_number ASC;"
        try:
            with self.get_connection() as conn:
                rows = conn.execute(sql, (run_id,)).fetchall()
                history = []
                for r in rows:
                    item = dict(r)
                    item["target_columns"] = safe_json_loads(item.get("target_columns_json"))
                    item["parameters"] = safe_json_loads(item.get("parameters_json"))
                    history.append(item)
                return history
        except sqlite3.Error as err:
            raise DatabaseError(f"Failed to retrieve cleaning history: {err}") from err

    # -----------------------------------------------------------------------
    # 5. Quality Score Comparison
    # -----------------------------------------------------------------------

    def save_quality_comparison(
        self,
        run_id: str,
        initial_profile: Dict[str, Any],
        cleaned_profile: Dict[str, Any],
    ) -> int:
        """Calculate and store before-and-after quality metric deltas.

        Parameters
        ----------
        run_id : str
            Analysis run ID foreign key.
        initial_profile : Dict[str, Any]
            Profiling report of the raw dataset.
        cleaned_profile : Dict[str, Any]
            Profiling report of the cleaned dataset.

        Returns
        -------
        int
            Inserted quality comparison record ID.
        """
        init_q = initial_profile.get("quality_summary", {})
        clean_q = cleaned_profile.get("quality_summary", {})

        init_ov = initial_profile.get("overview", {})
        clean_ov = cleaned_profile.get("overview", {})

        init_miss = initial_profile.get("missing_values", {})
        clean_miss = cleaned_profile.get("missing_values", {})

        init_dup = initial_profile.get("duplicates", {})
        clean_dup = cleaned_profile.get("duplicates", {})

        score_before = float(init_q.get("overall_score", 0.0))
        score_after = float(clean_q.get("overall_score", 0.0))
        score_delta = round(score_after - score_before, 2)

        rating_before = str(init_q.get("rating", "Poor"))
        rating_after = str(clean_q.get("rating", "Poor"))

        missing_before = int(init_miss.get("total_missing_cells", 0))
        missing_after = int(clean_miss.get("total_missing_cells", 0))

        dup_before = int(init_dup.get("duplicate_rows_count", 0))
        dup_after = int(clean_dup.get("duplicate_rows_count", 0))

        rows_before = int(init_ov.get("total_rows", 0))
        rows_after = int(clean_ov.get("total_rows", 0))

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        sql = """
        INSERT INTO quality_comparisons (
            run_id, score_before, score_after, score_delta,
            rating_before, rating_after,
            missing_before, missing_after,
            duplicates_before, duplicates_after,
            rows_before, rows_after, compared_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(run_id) DO UPDATE SET
            score_before=excluded.score_before,
            score_after=excluded.score_after,
            score_delta=excluded.score_delta,
            rating_before=excluded.rating_before,
            rating_after=excluded.rating_after,
            missing_before=excluded.missing_before,
            missing_after=excluded.missing_after,
            duplicates_before=excluded.duplicates_before,
            duplicates_after=excluded.duplicates_after,
            rows_before=excluded.rows_before,
            rows_after=excluded.rows_after,
            compared_at=excluded.compared_at;
        """
        params = (
            run_id, score_before, score_after, score_delta,
            rating_before, rating_after,
            missing_before, missing_after,
            dup_before, dup_after,
            rows_before, rows_after, now_iso,
        )

        try:
            with self.get_connection() as conn:
                cursor = conn.execute(sql, params)
                return int(cursor.lastrowid)
        except sqlite3.Error as err:
            raise DatabaseError(f"Failed to save quality comparison: {err}") from err

    def get_quality_comparison(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve quality score comparison record for a run."""
        sql = "SELECT * FROM quality_comparisons WHERE run_id = ?;"
        try:
            with self.get_connection() as conn:
                row = conn.execute(sql, (run_id,)).fetchone()
                return dict(row) if row else None
        except sqlite3.Error as err:
            raise DatabaseError(f"Failed to retrieve quality comparison: {err}") from err

    # -----------------------------------------------------------------------
    # 6. Complete Session Aggregator
    # -----------------------------------------------------------------------

    def get_complete_session(self, run_id: str) -> Dict[str, Any]:
        """Retrieve complete unified analysis session details.

        Aggregates run metadata, initial and post-cleaning profiles,
        recommendations, cleaning history, and before-and-after quality comparisons.

        Parameters
        ----------
        run_id : str
            The analysis run ID.

        Returns
        -------
        Dict[str, Any]
            Complete session dictionary.

        Raises
        ------
        RecordNotFoundError
            If run does not exist.
        """
        run = self.get_run(run_id)
        if not run:
            raise RecordNotFoundError(f"Analysis run '{run_id}' not found.")

        initial_profile = self.get_profiling_report(run_id, stage="initial")
        post_profile = self.get_profiling_report(run_id, stage="post_cleaning")
        recommendations = self.get_recommendations(run_id)
        cleaning_history = self.get_cleaning_history(run_id)
        comparison = self.get_quality_comparison(run_id)

        return {
            "run": run,
            "initial_profile": initial_profile,
            "post_cleaning_profile": post_profile,
            "recommendations": recommendations,
            "cleaning_history": cleaning_history,
            "quality_comparison": comparison,
        }
