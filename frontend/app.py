"""DataFix – Autonomous Data Quality Engine.

Streamlit Frontend Application.
Integrates backend ingestion, statistical profiling, cleaning transformations,
Scikit-learn Isolation Forest anomaly detection, AI recommendations, and SQLite persistence.
"""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root is available in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd
import streamlit as st

# DataFix Core Imports
from backend.upload import (
    load_dataset,
    validate_file_source,
    get_supported_formats,
    DataFixUploadError,
)
from backend.profiling import profile_dataset
from backend.cleaning import CleaningPipeline
from ai.anomaly_detector import detect_anomalies
from ai.recommender import (
    generate_recommendations,
    apply_recommendation,
    apply_all_safe_recommendations,
    RemediationRecommendation,
    DestructiveOperationBlockedError,
)
from database.manager import DatabaseManager, safe_json_dumps

# Frontend Styling and Visualizations
from frontend.styles import CUSTOM_CSS
from frontend.visualizations import (
    plot_quality_gauge,
    plot_missing_values,
    plot_column_types_pie,
    plot_outliers_box,
    plot_anomaly_scatter,
    plot_before_after_quality,
)


# ---------------------------------------------------------------------------
# Streamlit Configuration & Initialization
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="DataFix – Autonomous Data Quality Engine",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# Initialize Database Manager in Session State
if "db_manager" not in st.session_state:
    st.session_state.db_manager = DatabaseManager(db_path="datafix.db", auto_init=True)

# Initialize Core App State
if "raw_df" not in st.session_state:
    st.session_state.raw_df = None
if "dataset_name" not in st.session_state:
    st.session_state.dataset_name = None
if "file_format" not in st.session_state:
    st.session_state.file_format = None
if "run_id" not in st.session_state:
    st.session_state.run_id = None
if "initial_profile" not in st.session_state:
    st.session_state.initial_profile = None
if "anomaly_results" not in st.session_state:
    st.session_state.anomaly_results = None
if "recommendations" not in st.session_state:
    st.session_state.recommendations = []
if "pipeline" not in st.session_state:
    st.session_state.pipeline = None
if "cleaned_df" not in st.session_state:
    st.session_state.cleaned_df = None
if "cleaned_profile" not in st.session_state:
    st.session_state.cleaned_profile = None
if "applied_rec_ids" not in st.session_state:
    st.session_state.applied_rec_ids = set()


# ---------------------------------------------------------------------------
# Core Analysis & Ingestion Pipeline Runner
# ---------------------------------------------------------------------------

def process_uploaded_dataset(df: pd.DataFrame, dataset_name: str, file_format: str, file_size: Optional[int] = None) -> None:
    """Run initial profiling, anomaly detection, recommendation generation, and database persistence."""
    with st.spinner("Analyzing dataset structure, statistical profile, and anomaly patterns..."):
        # 1. State updates
        st.session_state.raw_df = df.copy()
        st.session_state.dataset_name = dataset_name
        st.session_state.file_format = file_format

        # 2. Automated Profiling
        profile = profile_dataset(df)
        st.session_state.initial_profile = profile

        # 3. Isolation Forest Anomaly Detection
        anomalies = detect_anomalies(df)
        st.session_state.anomaly_results = anomalies

        # 4. AI Recommendation Generation
        recs = generate_recommendations(df, profile=profile, anomaly_results=anomalies)
        st.session_state.recommendations = recs

        # 5. Initialize Cleaning Pipeline
        pipeline = CleaningPipeline(df)
        st.session_state.pipeline = pipeline
        st.session_state.cleaned_df = pipeline.get_cleaned_df()
        st.session_state.cleaned_profile = profile
        st.session_state.applied_rec_ids = set()
        st.session_state.persisted_audit_count = 0

        # 6. Database Persistence
        db: DatabaseManager = st.session_state.db_manager
        run_id = db.create_analysis_run(
            dataset_name=dataset_name,
            file_format=file_format,
            file_size_bytes=file_size,
        )
        st.session_state.run_id = run_id
        db.save_profiling_report(run_id, profile, stage="initial")
        db.save_recommendations(run_id, recs)

def persist_cleaning_state() -> None:
    """Persist new cleaning operations and the latest quality profile."""

    pipeline = st.session_state.pipeline
    db = st.session_state.db_manager
    run_id = st.session_state.run_id

    if pipeline is None or run_id is None:
        return

    # Save only audit entries not previously persisted.
    audit_log = pipeline.get_audit_log()
    start_index = st.session_state.persisted_audit_count

    for entry in audit_log[start_index:]:
        db.save_cleaning_step(run_id, entry)
        st.session_state.persisted_audit_count += 1
    # Update cleaned dataset and profile.
    cleaned_df = pipeline.get_cleaned_df()
    st.session_state.cleaned_df = cleaned_df

    cleaned_profile = profile_dataset(cleaned_df)
    st.session_state.cleaned_profile = cleaned_profile

    # Save latest profile and quality comparison.
    db.save_profiling_report(
        run_id,
        cleaned_profile,
        stage="post_cleaning"
    )

    db.save_quality_comparison(
        run_id,
        st.session_state.initial_profile,
        cleaned_profile
    )

def generate_sample_dataset() -> pd.DataFrame:
    """Generate an illustrative dirty dataset for instant evaluation."""
    np.random.seed(42)
    return pd.DataFrame({
        "employee_id": [101, 102, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111],
        "full_name": [
            "  alice smith ", "Bob  jones", "Bob  jones", "Charlie Brown!",
            "David Miller", "Eve Watson", "Frank   Castle", "Grace Lee",
            "Heidi Turner", "Ivan Drago", "Judy Garland", "   "
        ],
        "age": [25.0, 31.0, 31.0, 142.0, 29.0, np.nan, 22.0, 35.0, 38.0, 27.0, 150.0, 24.0],
        "salary_str": [
            "$52,000", "$64,000", "$64,000", "$75,000", "$82,000", "$58,000",
            "$49,000", "$91,000", "$67,000", "$55,000", "$89,000", "$46,000"
        ],
        "department": ["IT", "Sales", "Sales", "IT", "HR", "IT", "Sales", "HR", "Sales", "IT", None, "Sales"],
        "is_active": ["yes", "no", "no", "true", "TRUE", "false", "1", "0", "yes", "true", "no", "yes"],
        "unusable_metadata": [None, None, None, None, None, "system_flag", None, None, None, None, None, None],
    })


# ---------------------------------------------------------------------------
# Sidebar Navigation & Session Status
# ---------------------------------------------------------------------------

st.sidebar.markdown(
    """
    <div style="text-align: center; margin-bottom: 1.5rem;">
        <h2 style="margin: 0; color: #1e3c72; font-weight: 800; font-size: 1.8rem;">⚡ DataFix</h2>
        <p style="margin: 0; color: #64748b; font-size: 0.85rem;">Autonomous Data Quality Engine</p>
    </div>
    """,
    unsafe_allow_html=True,
)

nav_page = st.sidebar.radio(
    "Navigation",
    options=[
        "🏠 Home & Upload",
        "📊 Data Profiling",
        "🔍 Quality Analysis & Anomalies",
        "🤖 AI Recommendations",
        "🧹 Data Cleaning & Remediation",
        "📥 Export & History",
    ],
    index=0,
)

st.sidebar.markdown("---")

# Active Dataset Status in Sidebar
if st.session_state.raw_df is not None:
    st.sidebar.markdown("### 📁 Active Dataset")
    st.sidebar.write(f"**Name:** `{st.session_state.dataset_name}`")
    st.sidebar.write(f"**Shape:** `{st.session_state.raw_df.shape[0]}` rows × `{st.session_state.raw_df.shape[1]}` cols")

    score = st.session_state.initial_profile.get("quality_summary", {}).get("overall_score", 0.0)
    rating = st.session_state.initial_profile.get("quality_summary", {}).get("rating", "Poor")
    st.sidebar.metric("Quality Health Score", f"{score:.1f} / 100", f"Rating: {rating}")

    if st.sidebar.button("🔄 Reset / Clear Session", use_container_width=True):
        st.session_state.raw_df = None
        st.session_state.dataset_name = None
        st.session_state.initial_profile = None
        st.session_state.anomaly_results = None
        st.session_state.recommendations = []
        st.session_state.pipeline = None
        st.session_state.cleaned_df = None
        st.session_state.applied_rec_ids = set()
        if "persisted_audit_count" not in st.session_state:
            st.session_state.persisted_audit_count = 0
        st.rerun()
else:
    st.sidebar.info("Upload a dataset or load the demo dataset to start.")


# ---------------------------------------------------------------------------
# PAGE 1: HOME & UPLOAD
# ---------------------------------------------------------------------------

if nav_page == "🏠 Home & Upload":
    st.markdown(
        """
        <div class="main-header">
            <h1>⚡ DataFix – Autonomous Data Quality Engine</h1>
            <p>Automated tabular dataset inspection, machine-learning anomaly detection, AI-guided remediation recipes, and reproducible cleaning transformations.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_up, col_info = st.columns([1.2, 1.0], gap="large")

    with col_up:
        st.markdown("### 📤 Upload Dataset")
        st.write("Upload a CSV, TSV, or Excel (.xlsx) file to run automated profiling and AI quality remediation.")

        uploaded_file = st.file_uploader(
            "Choose a dataset",
            type=["csv", "tsv", "xlsx", "xls"],
            help="Supported formats: CSV, TSV, and Excel workbooks.",
        )

        if uploaded_file is not None:
            # Check if this file is already loaded to avoid re-triggering on each rerun
            if st.session_state.dataset_name != uploaded_file.name:
                try:
                    df = load_dataset(uploaded_file)
                    ext = Path(uploaded_file.name).suffix.lstrip(".").lower()
                    process_uploaded_dataset(
                        df=df,
                        dataset_name=uploaded_file.name,
                        file_format=ext,
                        file_size=uploaded_file.size,
                    )
                    st.success(f"Successfully loaded '{uploaded_file.name}' ({len(df):,} rows, {len(df.columns)} columns)!")
                    st.rerun()
                except DataFixUploadError as err:
                    st.error(f"Upload Validation Error: {err}")
                except Exception as err:
                    st.error(f"Failed to process dataset: {err}")

        st.markdown("##### Or explore with an illustrative dataset:")
        if st.button("🚀 Load Sample Hackathon Dataset", use_container_width=True):
            sample_df = generate_sample_dataset()
            process_uploaded_dataset(
                df=sample_df,
                dataset_name="hackathon_sample_dirty.csv",
                file_format="csv",
                file_size=2048,
            )
            st.success("Loaded demo dataset with deliberate anomalies, missingness, and duplicates!")
            st.rerun()

    with col_info:
        st.markdown("### 🛠️ Engine Capabilities")
        st.markdown(
            """
            - **Phase 1 Ingestion & Profiling**: CSV/TSV/Excel support, encoding fallback, dimension checks, statistical summaries, and quality scoring.
            - **Phase 2 Deterministic Remediation**: Missing value imputation, deduplication, IQR/Z-score outlier clipping, text normalization, and type casting with complete audit trails.
            - **Phase 3 AI Intelligence Layer**: Scikit-learn `IsolationForest` multivariate anomaly detection and recommendation recipes with safety approval gates.
            - **Phase 4 Persistence**: SQLite session storage, foreign key cascading, and audit history.
            """
        )

    # Active Dataset Overview & Quick Preview
    if st.session_state.raw_df is not None:
        st.markdown("---")
        st.markdown(f"### 📋 Dataset Preview: `{st.session_state.dataset_name}`")

        c1, c2, c3, c4 = st.columns(4)
        ov = st.session_state.initial_profile.get("overview", {})
        c1.metric("Total Rows", f"{ov.get('total_rows', 0):,}")
        c2.metric("Total Columns", f"{ov.get('total_columns', 0)}")
        c3.metric("Total Cells", f"{ov.get('total_cells', 0):,}")
        c4.metric("Memory Usage", f"{ov.get('memory_usage_mb', 0.0)} MB")

        st.dataframe(st.session_state.raw_df.head(10), use_container_width=True)


# ---------------------------------------------------------------------------
# PAGE 2: DATA PROFILING
# ---------------------------------------------------------------------------

elif nav_page == "📊 Data Profiling":
    st.markdown("## 📊 Automated Data Profiling")

    if st.session_state.raw_df is None:
        st.warning("Please upload a dataset on the Home page first.")
    else:
        profile = st.session_state.initial_profile
        ov = profile.get("overview", {})
        col_types = profile.get("column_types", {})
        missing = profile.get("missing_values", {})
        dups = profile.get("duplicates", {})

        # Top Metric Row
        m1, m2, m3, m4 = st.columns(4)
        m1.markdown(
            f"""<div class="metric-card"><div class="metric-label">Total Rows</div><div class="metric-value">{ov.get('total_rows', 0):,}</div></div>""",
            unsafe_allow_html=True,
        )
        m2.markdown(
            f"""<div class="metric-card"><div class="metric-label">Total Columns</div><div class="metric-value">{ov.get('total_columns', 0)}</div></div>""",
            unsafe_allow_html=True,
        )
        m3.markdown(
            f"""<div class="metric-card"><div class="metric-label">Missing Cells</div><div class="metric-value">{missing.get('total_missing_cells', 0):,} ({missing.get('missing_cells_percentage', 0.0)}%)</div></div>""",
            unsafe_allow_html=True,
        )
        m4.markdown(
            f"""<div class="metric-card"><div class="metric-label">Duplicate Rows</div><div class="metric-value">{dups.get('duplicate_rows_count', 0)} ({dups.get('duplicate_rows_percentage', 0.0)}%)</div></div>""",
            unsafe_allow_html=True,
        )

        tab_schema, tab_num, tab_cat, tab_missing = st.tabs([
            "📋 Schema & Types",
            "📈 Numerical Summaries",
            "🏷️ Categorical Summaries",
            "🧩 Missing Values Detail",
        ])

        with tab_schema:
            st.markdown("#### Column Dtypes & Cardinality")
            col_left, col_right = st.columns([1.4, 1.0])

            with col_left:
                schema_data = []
                uniques = profile.get("unique_values", {}).get("columns", {})
                for c in st.session_state.raw_df.columns:
                    col_str = str(c)
                    u_info = uniques.get(col_str, {})
                    m_info = missing.get("columns", {}).get(col_str, {})
                    schema_data.append({
                        "Column": col_str,
                        "Dtype": col_types.get("dtypes", {}).get(col_str, "unknown"),
                        "Unique Values": u_info.get("unique_count", 0),
                        "Cardinality Class": u_info.get("cardinality", "unknown"),
                        "Missing Count": m_info.get("missing_count", 0),
                        "Missing %": f"{m_info.get('missing_percentage', 0.0)}%",
                    })
                st.dataframe(pd.DataFrame(schema_data), use_container_width=True)

            with col_right:
                fig_pie = plot_column_types_pie(col_types.get("counts", {}))
                st.plotly_chart(fig_pie, use_container_width=True)

        with tab_num:
            st.markdown("#### Numerical Feature Statistics")
            num_stats = profile.get("numerical_stats", {})
            if num_stats:
                num_records = []
                for c, s in num_stats.items():
                    b = s.get("outlier_bounds", {})
                    num_records.append({
                        "Column": c,
                        "Count": s.get("count"),
                        "Mean": s.get("mean"),
                        "Std": s.get("std"),
                        "Min": s.get("min"),
                        "Q25": s.get("q25"),
                        "Median": s.get("median"),
                        "Q75": s.get("q75"),
                        "Max": s.get("max"),
                        "IQR": s.get("iqr"),
                        "Skewness": s.get("skewness"),
                        "Outliers Count": s.get("outliers_count"),
                        "Outliers %": f"{s.get('outliers_percentage', 0.0)}%",
                        "IQR Lower Bound": b.get("lower"),
                        "IQR Upper Bound": b.get("upper"),
                    })
                st.dataframe(pd.DataFrame(num_records), use_container_width=True)
            else:
                st.info("No numerical columns found in dataset.")

        with tab_cat:
            st.markdown("#### Categorical & String Feature Distributions")
            cat_stats = profile.get("categorical_stats", {})
            if cat_stats:
                for col_name, c_info in cat_stats.items():
                    with st.expander(f"📌 Column: {col_name} (Unique: {c_info.get('unique_count')}, Mode: '{c_info.get('mode')}')"):
                        c1, c2 = st.columns([1, 1.5])
                        c1.write(f"**Non-null Count:** {c_info.get('count')}")
                        c1.write(f"**Missing Count:** {c_info.get('missing_count')}")
                        c1.write(f"**Dominant Mode:** `{c_info.get('mode')}` ({c_info.get('mode_percentage')}%)")

                        top_vals = c_info.get("top_values", [])
                        if top_vals:
                            c2.dataframe(pd.DataFrame(top_vals), use_container_width=True)
            else:
                st.info("No categorical or string columns found in dataset.")

        with tab_missing:
            st.markdown("#### Missing Values Distribution")
            fig_miss = plot_missing_values(missing)
            if fig_miss:
                st.plotly_chart(fig_miss, use_container_width=True)
            else:
                st.success("🎉 Perfect completeness: Zero missing values detected across all columns!")


# ---------------------------------------------------------------------------
# PAGE 3: QUALITY ANALYSIS & ANOMALIES
# ---------------------------------------------------------------------------

elif nav_page == "🔍 Quality Analysis & Anomalies":
    st.markdown("## 🔍 Data Quality Analysis & Machine Learning Anomalies")

    if st.session_state.raw_df is None:
        st.warning("Please upload a dataset on the Home page first.")
    else:
        profile = st.session_state.initial_profile
        quality = profile.get("quality_summary", {})
        score = quality.get("overall_score", 0.0)
        rating = quality.get("rating", "Poor")

        # Top Quality Gauge & Dimension Breakdown
        col_gauge, col_dims = st.columns([1.1, 1.5], gap="medium")

        with col_gauge:
            fig_g = plot_quality_gauge(score, rating)
            st.plotly_chart(fig_g, use_container_width=True)

        with col_dims:
            st.markdown("### Quality Dimensions")
            d1, d2 = st.columns(2)
            d1.metric("Completeness (40%)", f"{quality.get('completeness_score', 0.0):.1f}%", help="Proportion of non-null cells")
            d2.metric("Uniqueness (30%)", f"{quality.get('uniqueness_score', 0.0):.1f}%", help="Proportion of non-duplicate records")
            d3, d4 = st.columns(2)
            d3.metric("Validity (15%)", f"{quality.get('validity_score', 0.0):.1f}%", help="Proportion of values within IQR bounds")
            d4.metric("Schema Structure (15%)", f"{quality.get('structural_score', 0.0):.1f}%", help="Penalized for empty or zero-variance columns")

        st.markdown("---")

        # Actionable Health Alerts
        st.markdown("### ⚠️ Data Health Alerts")
        alerts = quality.get("alerts", [])
        if alerts:
            for alert in alerts:
                lvl = alert.get("level", "info")
                msg = alert.get("message", "")
                col_name = alert.get("column", "dataset")

                if lvl == "critical":
                    st.error(f"**[CRITICAL]** `{col_name}`: {msg}")
                elif lvl == "warning":
                    st.warning(f"**[WARNING]** `{col_name}`: {msg}")
                else:
                    st.info(f"**[INFO]** `{col_name}`: {msg}")
        else:
            st.success("No critical quality health alerts triggered.")

        st.markdown("---")

        # Machine Learning Anomaly Detection (Isolation Forest)
        st.markdown("### 🌲 Isolation Forest Multivariate Anomaly Detection")
        st.write("Identifies multidimensional anomalies across combinations of numerical columns that traditional single-column thresholds cannot detect.")

        anomalies = st.session_state.anomaly_results
        if anomalies and anomalies.get("is_detected", False):
            a_count = anomalies.get("anomaly_count", 0)
            a_pct = anomalies.get("anomaly_percentage", 0.0)
            st.warning(f"Isolation Forest flagged **{a_count} anomaly records** ({a_pct}% of dataset).")

            # Plot scatter if >= 2 numeric columns
            fig_scat = plot_anomaly_scatter(st.session_state.raw_df, anomalies)
            if fig_scat:
                st.plotly_chart(fig_scat, use_container_width=True)

            # Display table of flagged anomaly records
            flagged_indices = anomalies.get("anomaly_indices", [])
            if flagged_indices:
                with st.expander("👁️ View Flagged Anomaly Rows"):
                    flagged_df = st.session_state.raw_df.loc[flagged_indices]
                    st.dataframe(flagged_df, use_container_width=True)
        else:
            st.success(anomalies.get("details", "No multivariate anomalies detected by Isolation Forest."))

        # Outlier Boxplot
        num_cols = profile.get("column_types", {}).get("numerical_columns", [])
        if num_cols:
            st.markdown("### 📦 Numerical Feature Outlier Boxplots")
            fig_box = plot_outliers_box(st.session_state.raw_df, num_cols)
            if fig_box:
                st.plotly_chart(fig_box, use_container_width=True)


# ---------------------------------------------------------------------------
# PAGE 4: AI RECOMMENDATIONS
# ---------------------------------------------------------------------------

elif nav_page == "🤖 AI Recommendations":
    st.markdown("## 🤖 AI Remediation Recommendation Engine")
    st.write("Autonomous diagnosis of data quality problems with concrete, executable remediation recipes.")

    if st.session_state.raw_df is None:
        st.warning("Please upload a dataset on the Home page first.")
    else:
        recs: List[RemediationRecommendation] = st.session_state.recommendations

        if not recs:
            st.success("🎉 No remediation actions needed! Your dataset meets all quality thresholds.")
        else:
            safe_recs = [r for r in recs if not r.is_destructive]
            dest_recs = [r for r in recs if r.is_destructive]

            # Top Summary Action Banner
            st.markdown(
                f"""
                <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 1rem; margin-bottom: 1.5rem;">
                    <strong>AI Recommendation Summary:</strong> {len(recs)} total recommendations formulated
                    ({len(safe_recs)} safe non-destructive, {len(dest_recs)} destructive requiring explicit approval).
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Apply All Safe Recommendations Button
            if safe_recs:
                col_btn, _ = st.columns([1.5, 2])
                with col_btn:
                    if st.button("⚡ Apply All Safe Recommendations", type="primary", use_container_width=True):
                        pipeline = st.session_state.pipeline
                        pipeline, res = apply_all_safe_recommendations(pipeline, safe_recs)
                        st.session_state.cleaned_df = pipeline.get_cleaned_df()
                        st.session_state.cleaned_profile = profile_dataset(st.session_state.cleaned_df)
                        st.session_state.applied_rec_ids.update(res.get("applied_ids", []))

                        # Record in Database
                        # Record cleaning changes in Database
                        persist_cleaning_state()
                        st.success(f"Applied {res.get('applied_count')} safe recommendations! Check the Data Cleaning tab.")
                        st.rerun()

            st.markdown("---")

            # Section 1: Safe Operations
            st.markdown("### 🟢 Safe Operations (Non-Destructive)")
            st.caption("These transformations impute missing values, clip outliers, normalize casing, or cast data types without deleting records or dropping columns.")

            if not safe_recs:
                st.info("No safe operations pending.")
            else:
                for rec in safe_recs:
                    is_applied = rec.id in st.session_state.applied_rec_ids
                    status_badge = '<span class="badge" style="background:#dcfce7; color:#15803d;">APPLIED</span>' if is_applied else '<span class="badge badge-safe">SAFE</span>'
                    sev_badge = f'<span class="badge badge-{rec.severity}">{rec.severity.upper()}</span>'

                    st.markdown(
                        f"""
                        <div class="rec-card">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                                <div>
                                    {status_badge}
                                    {sev_badge}
                                    <strong style="color: #64748b; font-size: 0.85rem;">{rec.id} • Target: `{rec.column}`</strong>
                                </div>
                                <span style="font-size: 0.85rem; font-weight: 600; color: #3b82f6;">Confidence: {int(rec.confidence_score * 100)}%</span>
                            </div>
                            <div class="rec-title">{rec.recommended_action}</div>
                            <p style="margin: 0.25rem 0; color: #334155;"><strong>Problem:</strong> {rec.problem_description}</p>
                            <p style="margin: 0.25rem 0; color: #475569; font-size: 0.9rem;"><strong>Rationale:</strong> {rec.rationale}</p>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    if not is_applied:
                        if st.button(f"Apply {rec.id} ({rec.pipeline_operation})", key=f"btn_safe_{rec.id}"):
                            pipeline = st.session_state.pipeline
                            pipeline, _ = apply_recommendation(pipeline, rec, approved=False)
                            st.session_state.cleaned_df = pipeline.get_cleaned_df()
                            st.session_state.cleaned_profile = profile_dataset(st.session_state.cleaned_df)
                            st.session_state.applied_rec_ids.add(rec.id)

                            # Database sync
                           # Database sync
                            persist_cleaning_state()
                            st.success(f"Executed recommendation {rec.id}!")
                            st.rerun()

            st.markdown("---")

            # Section 2: Destructive Operations
            st.markdown("### 🔴 Destructive Operations (Requires Explicit Approval)")
            st.caption("These operations permanently remove duplicate rows, discard invalid records, or drop severely unpopulated columns. Explicit user approval is mandatory.")

            if not dest_recs:
                st.info("No destructive operations required.")
            else:
                for rec in dest_recs:
                    is_applied = rec.id in st.session_state.applied_rec_ids
                    status_badge = '<span class="badge" style="background:#dcfce7; color:#15803d;">APPLIED</span>' if is_applied else '<span class="badge badge-destructive">DESTRUCTIVE</span>'
                    sev_badge = f'<span class="badge badge-{rec.severity}">{rec.severity.upper()}</span>'

                    st.markdown(
                        f"""
                        <div class="rec-card rec-card-destructive">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                                <div>
                                    {status_badge}
                                    {sev_badge}
                                    <strong style="color: #64748b; font-size: 0.85rem;">{rec.id} • Target: `{rec.column}`</strong>
                                </div>
                                <span style="font-size: 0.85rem; font-weight: 600; color: #ef4444;">Confidence: {int(rec.confidence_score * 100)}%</span>
                            </div>
                            <div class="rec-title" style="color: #991b1b;">{rec.recommended_action}</div>
                            <p style="margin: 0.25rem 0; color: #334155;"><strong>Problem:</strong> {rec.problem_description}</p>
                            <p style="margin: 0.25rem 0; color: #475569; font-size: 0.9rem;"><strong>Rationale:</strong> {rec.rationale}</p>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    if not is_applied:
                        col_check, col_act = st.columns([2, 1])
                        with col_check:
                            confirm = st.checkbox(
                                f"I confirm and approve executing destructive action {rec.id} ({rec.pipeline_operation})",
                                key=f"chk_confirm_{rec.id}",
                            )
                        with col_act:
                            if st.button(f"Execute {rec.id}", key=f"btn_dest_{rec.id}", disabled=not confirm):
                                try:
                                    pipeline = st.session_state.pipeline
                                    pipeline, _ = apply_recommendation(pipeline, rec, approved=True)
                                    st.session_state.cleaned_df = pipeline.get_cleaned_df()
                                    st.session_state.cleaned_profile = profile_dataset(st.session_state.cleaned_df)
                                    st.session_state.applied_rec_ids.add(rec.id)

                                    # Database sync
                                    # Database sync
                                    persist_cleaning_state()
                                    st.success(f"Executed destructive recommendation {rec.id} successfully!")
                                    st.rerun()
                                except DestructiveOperationBlockedError as err:
                                    st.error(f"Execution Blocked: {err}")


# ---------------------------------------------------------------------------
# PAGE 5: DATA CLEANING & REMEDIATION
# ---------------------------------------------------------------------------

elif nav_page == "🧹 Data Cleaning & Remediation":
    st.markdown("## 🧹 Data Cleaning & Remediation Pipeline")

    if st.session_state.raw_df is None:
        st.warning("Please upload a dataset on the Home page first.")
    else:
        pipeline = st.session_state.pipeline
        audit_log = pipeline.get_audit_log()
        summary = pipeline.get_summary()

        # Top Before vs After Score Delta Banner
        score_before = st.session_state.initial_profile.get("quality_summary", {}).get("overall_score", 0.0)
        score_after = st.session_state.cleaned_profile.get("quality_summary", {}).get("overall_score", 0.0)
        delta = round(score_after - score_before, 2)

        st.markdown(
            f"""
            <div style="background: linear-gradient(135deg, #065f46 0%, #047857 100%); padding: 1.2rem; border-radius: 10px; color: white; margin-bottom: 1.5rem;">
                <div style="font-size: 0.9rem; text-transform: uppercase; letter-spacing: 0.5px; opacity: 0.9;">Quality Improvement Status</div>
                <div style="font-size: 2rem; font-weight: 700;">Score: {score_before:.1f} → {score_after:.1f} ({'+' if delta >= 0 else ''}{delta:.1f} pts)</div>
                <div style="font-size: 0.95rem; opacity: 0.95;">Total Transformations Executed: {summary.get('total_steps', 0)} | Total Cells/Rows Impacted: {summary.get('total_affected', 0):,}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        tab_audit, tab_preview, tab_compare, tab_manual = st.tabs([
            "📜 Transformation Audit Trail",
            "👁️ Cleaned Data Preview",
            "📊 Before vs After Analytics",
            "🎛️ Manual Cleaning Tools",
        ])

        with tab_audit:
            st.markdown("#### Chronological Audit History")
            if not audit_log:
                st.info("No cleaning transformations have been applied yet. Apply AI recommendations or use the manual tools below.")
            else:
                audit_records = []
                for entry in audit_log:
                    audit_records.append({
                        "Step": entry.get("step"),
                        "Operation": entry.get("operation"),
                        "Strategy": entry.get("strategy"),
                        "Target Columns": ", ".join(entry.get("columns", [])),
                        "Rows Before": entry.get("rows_before"),
                        "Rows After": entry.get("rows_after"),
                        "Affected": entry.get("rows_affected"),
                        "Details": entry.get("details"),
                        "Timestamp": entry.get("timestamp"),
                    })
                st.dataframe(pd.DataFrame(audit_records), use_container_width=True)

        with tab_preview:
            st.markdown("#### Cleaned Dataset Preview")
            c1, c2 = st.columns(2)
            c1.write(f"**Shape:** `{len(st.session_state.cleaned_df)}` rows × `{len(st.session_state.cleaned_df.columns)}` columns")
            c2.write(f"**Original Shape:** `{len(st.session_state.raw_df)}` rows × `{len(st.session_state.raw_df.columns)}` columns")
            st.dataframe(st.session_state.cleaned_df.head(20), use_container_width=True)

        with tab_compare:
            st.markdown("#### Before vs After Quality Score Dimensions")
            metrics_before = st.session_state.initial_profile.get("quality_summary", {})
            metrics_after = st.session_state.cleaned_profile.get("quality_summary", {})

            fig_comp = plot_before_after_quality(
                score_before=score_before,
                score_after=score_after,
                metrics_before=metrics_before,
                metrics_after=metrics_after,
            )
            st.plotly_chart(fig_comp, use_container_width=True)

        with tab_manual:
            st.markdown("#### Targeted Manual Cleaning Toolkit")
            st.caption("Apply custom transformations directly to the working dataset copy.")

            op_choice = st.selectbox(
                "Choose transformation category:",
                options=[
                    "Missing Values Imputation",
                    "Duplicate Row Removal",
                    "Outlier Clipping / Filtering",
                    "Text Standardization",
                ],
            )

            # Manual Tool: Missing Values
    if op_choice == "Missing Values Imputation":
        cols_with_na = [
            c for c in st.session_state.cleaned_df.columns
            if st.session_state.cleaned_df[c].isna().any()
    ]

    if not cols_with_na:
        st.success("No missing values in current dataset!")
    else:
        sel_col = st.selectbox(
            "Select column with missing values:",
            cols_with_na
        )

        sel_strat = st.selectbox(
            "Imputation strategy:",
            ["median", "mean", "mode", "constant", "forward_fill", "drop_rows"]
        )

        custom_fill = None

        if sel_strat == "constant":
            custom_fill = st.text_input("Constant fill value:", value="Unknown")

        confirm_drop = True

        if sel_strat == "drop_rows":
            confirm_drop = st.checkbox(
                "I understand that rows containing missing values in this column will be deleted."
            )

        if st.button("Apply Missing Value Imputation"):
            if not confirm_drop:
                st.warning("Please confirm before deleting rows.")
            else:
                pipeline.handle_missing_values(
                    columns=[sel_col],
                    strategy=sel_strat,
                    fill_value=custom_fill
                )

                persist_cleaning_state()

                st.success(
                    f"Applied {sel_strat} imputation to column '{sel_col}'!"
                )
                st.rerun()

            # Manual Tool: Duplicates
        elif op_choice == "Duplicate Row Removal":
          dup_strat = st.selectbox(
        "Deduplication strategy:",
        ["drop_first", "drop_last", "drop_all"]
    )

    confirm_duplicates = st.checkbox(
        "I understand that duplicate rows will be permanently removed."
    )

    if st.button("Execute Deduplication"):
        if not confirm_duplicates:
            st.warning("Please confirm before removing duplicates.")
        else:
            pipeline.handle_duplicates(strategy=dup_strat)

            persist_cleaning_state()

            st.success(
                f"Executed deduplication using strategy '{dup_strat}'!"
            )
            st.rerun()

            # Manual Tool: Outliers
    elif op_choice == "Outlier Clipping / Filtering":
     num_cols = [
        c for c in st.session_state.cleaned_df.columns
        if pd.api.types.is_numeric_dtype(st.session_state.cleaned_df[c])
    ]

    if not num_cols:
        st.info("No numerical columns available for outlier remediation.")
    else:
        sel_num_col = st.selectbox("Select numerical column:", num_cols)

        outlier_strat = st.selectbox(
            "Outlier remediation:",
            ["clip", "drop", "set_null"]
        )

        iqr_factor = st.slider(
            "IQR Multiplier (factor):",
            min_value=1.0,
            max_value=3.0,
            value=1.5,
            step=0.1
        )

        confirm_outlier_drop = True

        if outlier_strat == "drop":
            confirm_outlier_drop = st.checkbox(
                "I understand that rows containing outliers will be deleted."
            )

        if st.button("Apply Outlier Remediation"):
            if not confirm_outlier_drop:
                st.warning("Please confirm before deleting rows.")
            else:
                pipeline.handle_outliers(
                    columns=[sel_num_col],
                    method="iqr",
                    strategy=outlier_strat,
                    factor=iqr_factor
                )

                persist_cleaning_state()

                st.success(
                    f"Remediated outliers in '{sel_num_col}' using '{outlier_strat}'!"
                )
                st.rerun()

            # Manual Tool: Text
    
        elif op_choice == "Text Standardization":
            str_cols = [
                c for c in st.session_state.cleaned_df.columns
                if pd.api.types.is_string_dtype(st.session_state.cleaned_df[c])
                or st.session_state.cleaned_df[c].dtype == "object"
            ]

            if not str_cols:
                st.info("No text columns available for standardization.")
            else:
                sel_text_col = st.selectbox("Select text column:", str_cols)

                strip_ws = st.checkbox(
                    "Strip leading/trailing whitespace & collapse spaces",
                    value=True
                )

                case_choice = st.selectbox(
                    "Case normalization:",
                    ["None", "title", "lower", "upper"]
                )

                case_val = None if case_choice == "None" else case_choice

                rm_special = st.checkbox(
                    "Remove special characters / punctuation",
                    value=False
                )

                if st.button("Apply Text Cleaning"):
                    pipeline.clean_text(
                        columns=[sel_text_col],
                        strip_whitespace=strip_ws,
                        case=case_val,
                        remove_special_chars=rm_special
                    )

                    persist_cleaning_state()

                    st.success(f"Cleaned text in column '{sel_text_col}'!")
                    st.rerun()


# ---------------------------------------------------------------------------
# PAGE 6: EXPORT & HISTORY
# ---------------------------------------------------------------------------

elif nav_page == "📥 Export & History":
    st.markdown("## 📥 Export Cleaned Dataset & Session History")

    if st.session_state.cleaned_df is None:
        st.warning("No active dataset loaded. Please upload a dataset first.")
    else:
        col_exp, col_hist = st.columns([1.1, 1.3], gap="large")

        with col_exp:
            st.markdown("### 💾 Export Cleaned Dataset")
            st.write("Download your remediated dataset with all quality transformations applied.")

            # CSV Download
            csv_data = st.session_state.cleaned_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📄 Download Cleaned CSV",
                data=csv_data,
                file_name=f"cleaned_{st.session_state.dataset_name}.csv",
                mime="text/csv",
                use_container_width=True,
            )

            # Excel Download (.xlsx)
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
                st.session_state.cleaned_df.to_excel(writer, index=False, sheet_name="CleanedData")
            excel_data = excel_buffer.getvalue()

            st.download_button(
                label="📊 Download Cleaned Excel (.xlsx)",
                data=excel_data,
                file_name=f"cleaned_{st.session_state.dataset_name}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

            # Audit Trail JSON Download
            pipeline = st.session_state.pipeline
            audit_json = safe_json_dumps({
                "dataset_name": st.session_state.dataset_name,
                "run_id": st.session_state.run_id,
                "summary": pipeline.get_summary() if pipeline else {},
                "audit_log": pipeline.get_audit_log() if pipeline else [],
            })
            st.download_button(
                label="📜 Download Audit Trail (JSON)",
                data=audit_json,
                file_name=f"audit_trail_{st.session_state.dataset_name}.json",
                mime="application/json",
                use_container_width=True,
            )

        with col_hist:
            st.markdown("### 🗄️ Historical Analysis Runs (SQLite)")
            st.write("Browse previous analysis runs persisted in the database.")

            db: DatabaseManager = st.session_state.db_manager
            runs = db.list_runs(limit=20)

            if not runs:
                st.info("No past runs recorded in the database.")
            else:
                runs_df = pd.DataFrame(runs)[["id", "dataset_name", "file_format", "status", "created_at"]]
                st.dataframe(runs_df, use_container_width=True)

                selected_run_id = st.selectbox(
                    "Inspect Session Details:",
                    options=[r["id"] for r in runs],
                )
                if selected_run_id:
                    session_info = db.get_complete_session(selected_run_id)
                    q_comp = session_info.get("quality_comparison")
                    if q_comp:
                        st.info(
                            f"**Run:** `{selected_run_id}` | **Quality Improvement:** "
                            f"{q_comp.get('score_before'):.1f} → {q_comp.get('score_after'):.1f} "
                            f"(+{q_comp.get('score_delta'):.1f} pts)"
                        )
                    else:
                        st.write(f"Run status: `{session_info['run']['status']}`")

                    with st.expander("View Session Details"):
                        st.write("**Initial Profiling Report**")
                        st.json(session_info.get("initial_profile") or {})

                        st.write("**Post-Cleaning Profiling Report**")
                        st.json(session_info.get("post_cleaning_profile") or {})

                        st.write("**AI Recommendations**")
                        st.json(session_info.get("recommendations") or [])

                        st.write("**Cleaning History**")
                        st.json(session_info.get("cleaning_history") or [])

