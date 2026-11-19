"""Database Schema and DDL Definitions for DataFix Engine.

This module defines the relational SQLite schema for persisting analysis runs,
profiling reports, AI recommendations, cleaning transformation histories,
and before-and-after quality comparisons with foreign key constraints.
"""

from __future__ import annotations

import sqlite3


DDL_ANALYSIS_RUNS = """
CREATE TABLE IF NOT EXISTS analysis_runs (
    id TEXT PRIMARY KEY,
    dataset_name TEXT NOT NULL,
    file_format TEXT NOT NULL,
    file_size_bytes INTEGER,
    status TEXT NOT NULL DEFAULT 'profiled',
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

DDL_PROFILING_REPORTS = """
CREATE TABLE IF NOT EXISTS profiling_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    stage TEXT NOT NULL CHECK(stage IN ('initial', 'post_cleaning')),
    total_rows INTEGER NOT NULL,
    total_columns INTEGER NOT NULL,
    total_cells INTEGER NOT NULL,
    memory_usage_mb REAL,
    total_missing_cells INTEGER,
    missing_cells_percentage REAL,
    duplicate_rows_count INTEGER,
    duplicate_rows_percentage REAL,
    overall_quality_score REAL NOT NULL,
    quality_rating TEXT NOT NULL,
    completeness_score REAL,
    uniqueness_score REAL,
    validity_score REAL,
    structural_score REAL,
    details_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES analysis_runs(id) ON DELETE CASCADE
);
"""

DDL_AI_RECOMMENDATIONS = """
CREATE TABLE IF NOT EXISTS ai_recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    rec_code TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT NOT NULL,
    column_name TEXT,
    problem_description TEXT NOT NULL,
    recommended_action TEXT NOT NULL,
    rationale TEXT NOT NULL,
    confidence_score REAL NOT NULL,
    is_destructive INTEGER NOT NULL CHECK(is_destructive IN (0, 1)),
    pipeline_operation TEXT NOT NULL,
    pipeline_parameters_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'applied', 'rejected', 'deferred')),
    created_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES analysis_runs(id) ON DELETE CASCADE
);
"""

DDL_CLEANING_HISTORY = """
CREATE TABLE IF NOT EXISTS cleaning_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    step_number INTEGER NOT NULL,
    operation TEXT NOT NULL,
    strategy TEXT NOT NULL,
    target_columns_json TEXT NOT NULL,
    parameters_json TEXT NOT NULL,
    rows_before INTEGER NOT NULL,
    rows_after INTEGER NOT NULL,
    rows_affected INTEGER NOT NULL,
    details TEXT,
    applied_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES analysis_runs(id) ON DELETE CASCADE
);
"""

DDL_QUALITY_COMPARISONS = """
CREATE TABLE IF NOT EXISTS quality_comparisons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL UNIQUE,
    score_before REAL NOT NULL,
    score_after REAL NOT NULL,
    score_delta REAL NOT NULL,
    rating_before TEXT NOT NULL,
    rating_after TEXT NOT NULL,
    missing_before INTEGER NOT NULL,
    missing_after INTEGER NOT NULL,
    duplicates_before INTEGER NOT NULL,
    duplicates_after INTEGER NOT NULL,
    rows_before INTEGER NOT NULL,
    rows_after INTEGER NOT NULL,
    compared_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES analysis_runs(id) ON DELETE CASCADE
);
"""

DDL_INDICES = [
    "CREATE INDEX IF NOT EXISTS idx_runs_created_at ON analysis_runs(created_at DESC);",
    "CREATE INDEX IF NOT EXISTS idx_runs_status ON analysis_runs(status);",
    "CREATE INDEX IF NOT EXISTS idx_profiling_run_id ON profiling_reports(run_id);",
    "CREATE INDEX IF NOT EXISTS idx_profiling_stage ON profiling_reports(stage);",
    "CREATE INDEX IF NOT EXISTS idx_ai_recs_run_id ON ai_recommendations(run_id);",
    "CREATE INDEX IF NOT EXISTS idx_ai_recs_status ON ai_recommendations(status);",
    "CREATE INDEX IF NOT EXISTS idx_cleaning_run_id ON cleaning_history(run_id);",
    "CREATE INDEX IF NOT EXISTS idx_cleaning_step ON cleaning_history(run_id, step_number);",
    "CREATE INDEX IF NOT EXISTS idx_comparisons_run_id ON quality_comparisons(run_id);",
]


def create_schema(conn: sqlite3.Connection) -> None:
    """Execute all table and index creation statements with foreign keys enabled.

    Parameters
    ----------
    conn : sqlite3.Connection
        Active SQLite database connection.
    """
    cursor = conn.cursor()
    # Always enforce foreign keys in SQLite
    cursor.execute("PRAGMA foreign_keys = ON;")

    # Create tables
    cursor.execute(DDL_ANALYSIS_RUNS)
    cursor.execute(DDL_PROFILING_REPORTS)
    cursor.execute(DDL_AI_RECOMMENDATIONS)
    cursor.execute(DDL_CLEANING_HISTORY)
    cursor.execute(DDL_QUALITY_COMPARISONS)

    # Create indices
    for index_stmt in DDL_INDICES:
        cursor.execute(index_stmt)

    conn.commit()
