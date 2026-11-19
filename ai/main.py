"""
DataFix - Autonomous Data Quality Engine
Module: Main Integration Gateway & Orchestrator (main.py)

Primary entrypoint for the AI/ML module. Provides clean, production-ready
interfaces for backend services (FastAPI, Flask, Express, Django) and local CLI usage.
"""

import argparse
import datetime
import io
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import pandas as pd

from profiler import profile_dataset, load_dataset
from missing_values import detect_missing_values
from duplicate_detector import detect_duplicates
from anomaly_detector import detect_anomalies
from inconsistency_detector import detect_inconsistencies
from quality_score import calculate_quality_score
from correction_engine import generate_correction_suggestions, clean_dataset


def analyze_dataset(
    data: Union[str, Path, io.IOBase, pd.DataFrame],
    anomaly_contamination: float = 0.1
) -> Dict[str, Any]:
    """
    Main analytical pipeline function.
    Ingests a CSV dataset, runs all profiling and detection engines, computes
    the transparent quality score, and generates prioritized correction suggestions.

    Args:
        data: CSV file path, file buffer (StringIO/BytesIO/UploadedFile), or pd.DataFrame.
        anomaly_contamination: Proportion of expected outliers for anomaly detection.

    Returns:
        Structured, 100% JSON-compatible dictionary.
    """
    try:
        # Load safely to check connectivity and viability
        df = load_dataset(data)
    except Exception as e:
        return {
            "status": "error",
            "error_message": str(e),
            "execution_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "quality_score": {"overall_score": 0.0, "grade": "F"},
            "profiling": {},
            "missing_values": {},
            "duplicates": {},
            "anomalies": {},
            "inconsistencies": {},
            "correction_suggestions": []
        }

    # Execute all audit engines across the dataset
    profile_rep = profile_dataset(df)
    missing_rep = detect_missing_values(df)
    duplicate_rep = detect_duplicates(df)
    anomaly_rep = detect_anomalies(df, contamination=anomaly_contamination)
    inconsistency_rep = detect_inconsistencies(df)

    # Compute overall transparent quality score (0 - 100)
    score_rep = calculate_quality_score(
        profile_data=profile_rep,
        missing_data=missing_rep,
        duplicate_data=duplicate_rep,
        anomaly_data=anomaly_rep,
        inconsistency_data=inconsistency_rep
    )

    # Generate prioritized, actionable correction suggestions
    suggestions = generate_correction_suggestions(
        profile_data=profile_rep,
        missing_data=missing_rep,
        duplicate_data=duplicate_rep,
        anomaly_data=anomaly_rep,
        inconsistency_data=inconsistency_rep
    )

    return {
        "status": "success",
        "dataset_name": Path(data).name if isinstance(data, (str, Path)) else "in_memory_dataset",
        "execution_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "quality_score": score_rep,
        "profiling": profile_rep,
        "missing_values": missing_rep,
        "duplicates": duplicate_rep,
        "anomalies": anomaly_rep,
        "inconsistencies": inconsistency_rep,
        "correction_suggestions": suggestions
    }


class DataQualityEngine:
    """
    Object-oriented API wrapper for backend engineers.
    Allows easy instantiation and re-use in backend microservices.
    """

    def __init__(self, default_anomaly_contamination: float = 0.1):
        self.default_contamination = default_anomaly_contamination

    def analyze(self, data: Union[str, Path, io.IOBase, pd.DataFrame]) -> Dict[str, Any]:
        """Runs the complete data quality analysis."""
        return analyze_dataset(data, anomaly_contamination=self.default_contamination)

    def clean(
        self,
        data: Union[str, Path, io.IOBase, pd.DataFrame],
        enabled_actions: Optional[List[str]] = None,
        return_format: str = "dataframe"
    ) -> Dict[str, Any]:
        """
        Executes safe, non-destructive cleaning.
        Does NOT modify the original dataset.
        """
        return clean_dataset(data, enabled_actions=enabled_actions, return_format=return_format)


def main():
    """Command-line interface (CLI) for DataFix AI Engine."""
    parser = argparse.ArgumentParser(
        description="DataFix – Autonomous Data Quality Engine (AI Module)"
    )
    parser.add_argument("csv_path", type=str, help="Path to the CSV dataset to analyze")
    parser.add_argument(
        "--clean",
        type=str,
        default=None,
        metavar="OUTPUT_CSV",
        help="Optional path to save cleaned CSV output"
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Print indented, colorized JSON summary"
    )

    args = parser.parse_args()
    csv_path = Path(args.csv_path)

    if not csv_path.exists():
        print(f"Error: File '{csv_path}' not found.")
        return

    print(f"[*] Analyzing dataset: {csv_path.name}...")
    report = analyze_dataset(csv_path)

    if args.clean:
        print(f"[*] Executing non-destructive cleaning pipeline...")
        clean_res = clean_dataset(csv_path, return_format="csv")
        out_path = Path(args.clean)
        out_path.write_text(clean_res["cleaned_csv"], encoding="utf-8")
        print(f"[+] Cleaned CSV successfully written to: {out_path}")
        print(f"    Transformations applied: {clean_res['total_transformations_count']}")
        for t in clean_res["transformations_applied"]:
            print(f"    - {t}")

    # Output high-level scorecard to terminal
    qs = report.get("quality_score", {})
    print("\n" + "=" * 55)
    print(" DATAFIX - DATA QUALITY AUDIT REPORT")
    print("=" * 55)
    print(f" Overall Score: {qs.get('overall_score', 0)} / 100")
    print(f" Letter Grade:  {qs.get('grade', 'N/A')}")
    print("-" * 55)
    pillars = qs.get("pillars", {})
    for p_name, p_data in pillars.items():
        print(f" {p_name.capitalize():<15}: {p_data.get('score', 0):>4.1f} / {p_data.get('max', 0):>2.0f} ({p_data.get('percentage', 0)}%)")
    print("-" * 55)
    print(f" Rows Analyzed : {report.get('profiling', {}).get('rows', 0)}")
    print(f" Columns       : {report.get('profiling', {}).get('columns', 0)}")
    print(f" Missing Cells : {report.get('missing_values', {}).get('total_missing_cells', 0)}")
    print(f" Duplicates    : {report.get('duplicates', {}).get('exact_duplicates_count', 0)}")
    print(f" Anomalies (ML): {report.get('anomalies', {}).get('anomalies_count', 0)}")
    print(f" Inconsistencies: {report.get('inconsistencies', {}).get('inconsistencies_count', 0)}")
    print(f" Suggested Fixes: {len(report.get('correction_suggestions', []))}")
    print("=" * 55)

    if args.pretty:
        print("\nFull JSON Payload:")
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
