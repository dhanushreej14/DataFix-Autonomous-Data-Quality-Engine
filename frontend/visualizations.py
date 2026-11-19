"""Interactive Plotly Visualization Components for DataFix Engine."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def plot_quality_gauge(score: float, rating: str) -> go.Figure:
    """Render a semi-circular quality health gauge chart."""
    # Determine needle and bar color
    if score >= 90:
        bar_color = "#10b981"
    elif score >= 75:
        bar_color = "#3b82f6"
    elif score >= 60:
        bar_color = "#f59e0b"
    else:
        bar_color = "#ef4444"

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=score,
            number={"suffix": "/100", "font": {"size": 36, "color": "#1e293b"}},
            title={"text": f"Data Quality Score • {rating}", "font": {"size": 18, "color": "#475569"}},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "#94a3b8"},
                "bar": {"color": bar_color, "thickness": 0.28},
                "bgcolor": "#f1f5f9",
                "borderwidth": 0,
                "steps": [
                    {"range": [0, 60], "color": "rgba(239, 68, 68, 0.15)"},
                    {"range": [60, 75], "color": "rgba(245, 158, 11, 0.15)"},
                    {"range": [75, 90], "color": "rgba(59, 130, 246, 0.15)"},
                    {"range": [90, 100], "color": "rgba(16, 185, 129, 0.15)"},
                ],
                "threshold": {
                    "line": {"color": bar_color, "width": 4},
                    "thickness": 0.75,
                    "value": score,
                },
            },
        )
    )
    fig.update_layout(
        height=260,
        margin={"t": 40, "b": 10, "l": 25, "r": 25},
        paper_bgcolor="rgba(0,0,0,0)",
        font={"family": "sans-serif"},
    )
    return fig


def plot_missing_values(missing_dict: Dict[str, Any]) -> Optional[go.Figure]:
    """Render a horizontal bar chart of column missingness percentages."""
    col_missing = missing_dict.get("columns", {})
    if not col_missing:
        return None

    cols = []
    pcts = []
    counts = []

    for c, stats in col_missing.items():
        pct = stats.get("missing_percentage", 0.0)
        cnt = stats.get("missing_count", 0)
        if cnt > 0:
            cols.append(c)
            pcts.append(pct)
            counts.append(cnt)

    if not cols:
        return None

    # Sort descending by missing %
    sorted_pairs = sorted(zip(cols, pcts, counts), key=lambda x: x[1])
    cols_s, pcts_s, counts_s = zip(*sorted_pairs)

    colors = [
        "#ef4444" if p >= 50 else ("#f59e0b" if p >= 15 else "#3b82f6")
        for p in pcts_s
    ]

    fig = go.Figure(
        go.Bar(
            x=pcts_s,
            y=cols_s,
            orientation="h",
            marker={"color": colors, "line": {"width": 0}},
            text=[f"{p:.1f}% ({c} rows)" for p, c in zip(pcts_s, counts_s)],
            textposition="auto",
        )
    )
    fig.update_layout(
        title={"text": "Missing Values by Column (%)", "font": {"size": 16}},
        xaxis={"title": "Missing Percentage (%)", "range": [0, max(100, max(pcts_s) + 5)]},
        yaxis={"title": "Columns"},
        height=max(250, len(cols) * 32),
        margin={"t": 40, "b": 30, "l": 100, "r": 20},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(248,250,252,0.6)",
    )
    return fig


def plot_column_types_pie(counts_dict: Dict[str, int]) -> go.Figure:
    """Render a donut chart representing dataset column type breakdown."""
    labels = []
    values = []
    color_map = {
        "numerical": "#3b82f6",
        "categorical": "#8b5cf6",
        "datetime": "#10b981",
        "boolean": "#f59e0b",
    }
    slice_colors = []

    for k, v in counts_dict.items():
        if k != "total" and v > 0:
            labels.append(k.capitalize())
            values.append(v)
            slice_colors.append(color_map.get(k, "#94a3b8"))

    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.55,
            marker={"colors": slice_colors},
            textinfo="label+value",
        )
    )
    fig.update_layout(
        title={"text": "Schema Dtype Distribution", "font": {"size": 16}},
        height=260,
        margin={"t": 40, "b": 10, "l": 20, "r": 20},
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=True,
    )
    return fig


def plot_outliers_box(df: pd.DataFrame, num_cols: List[str]) -> Optional[go.Figure]:
    """Render an interactive box plot of numeric features to display outliers."""
    if not num_cols or df.empty:
        return None

    # Limit to top 8 numeric columns for clean chart visualization
    display_cols = num_cols[:8]
    sub_df = df[display_cols].melt(var_name="Feature", value_name="Value").dropna()

    fig = px.box(
        sub_df,
        x="Feature",
        y="Value",
        color="Feature",
        points="outliers",
        title="Numerical Features Outlier Distribution (Boxplot)",
    )
    fig.update_layout(
        height=340,
        margin={"t": 40, "b": 20, "l": 40, "r": 20},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(248,250,252,0.6)",
        showlegend=False,
    )
    return fig


def plot_anomaly_scatter(df: pd.DataFrame, anomaly_results: Dict[str, Any]) -> Optional[go.Figure]:
    """Render a 2D scatter plot highlighting Isolation Forest detected anomalies."""
    if not anomaly_results.get("is_detected", False):
        return None

    eval_cols = anomaly_results.get("evaluated_columns", [])
    if len(eval_cols) < 2 or df.empty:
        return None

    x_col, y_col = eval_cols[0], eval_cols[1]
    plot_df = df[[x_col, y_col]].copy().dropna()
    anomaly_indices = set(anomaly_results.get("anomaly_indices", []))

    plot_df["Status"] = [
        "Anomaly (Isolation Forest)" if idx in anomaly_indices else "Normal Record"
        for idx in plot_df.index
    ]

    fig = px.scatter(
        plot_df,
        x=x_col,
        y=y_col,
        color="Status",
        color_discrete_map={
            "Normal Record": "#3b82f6",
            "Anomaly (Isolation Forest)": "#ef4444",
        },
        title=f"Multivariate Anomaly Scatter ({x_col} vs {y_col})",
        opacity=0.8,
    )
    fig.update_layout(
        height=340,
        margin={"t": 40, "b": 20, "l": 40, "r": 20},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(248,250,252,0.6)",
    )
    return fig


def plot_before_after_quality(
    score_before: float,
    score_after: float,
    metrics_before: Dict[str, float],
    metrics_after: Dict[str, float],
) -> go.Figure:
    """Render a side-by-side grouped bar chart comparing quality metrics before and after cleaning."""
    categories = [
        "Overall Health",
        "Completeness",
        "Uniqueness",
        "Validity (Outliers)",
        "Structure (Schema)",
    ]

    before_vals = [
        score_before,
        metrics_before.get("completeness_score", 0.0),
        metrics_before.get("uniqueness_score", 0.0),
        metrics_before.get("validity_score", 0.0),
        metrics_before.get("structural_score", 0.0),
    ]

    after_vals = [
        score_after,
        metrics_after.get("completeness_score", 0.0),
        metrics_after.get("uniqueness_score", 0.0),
        metrics_after.get("validity_score", 0.0),
        metrics_after.get("structural_score", 0.0),
    ]

    fig = go.Figure(
        data=[
            go.Bar(name="Raw Dataset (Before)", x=categories, y=before_vals, marker_color="#94a3b8"),
            go.Bar(name="Cleaned Dataset (After)", x=categories, y=after_vals, marker_color="#10b981"),
        ]
    )
    fig.update_layout(
        barmode="group",
        title={"text": "Quality Score Dimension Comparison (Before vs. After)", "font": {"size": 16}},
        yaxis={"range": [0, 105], "title": "Score (0 - 100)"},
        height=320,
        margin={"t": 40, "b": 20, "l": 40, "r": 20},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(248,250,252,0.6)",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
    )
    return fig
