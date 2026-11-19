"""
DataFix - Autonomous Data Quality Engine
Module: Quality Score Engine (quality_score.py)

Responsible for:
- Computing a transparent, weighted Data Quality Score (0 to 100)
- Evaluating 4 core quality pillars:
    1. Completeness (30% weight) - Missing and null values
    2. Uniqueness (20% weight)   - Exact and potential duplicates
    3. Consistency (25% weight)  - Date formats, categorical casing, type pollution
    4. Validity (25% weight)     - Outliers, anomalies, domain range violations
- Providing transparent mathematical breakdown and itemized deductions
- Assigning human-readable letter grades (A, B, C, D, F)
"""

from typing import Any, Dict, List, Optional


def calculate_quality_score(
    profile_data: Dict[str, Any],
    missing_data: Dict[str, Any],
    duplicate_data: Dict[str, Any],
    anomaly_data: Dict[str, Any],
    inconsistency_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Calculates an explainable 0–100 Data Quality Score based on the findings
    of the profiling and detection sub-engines.

    Returns structured JSON-compatible dictionary with breakdown and explanations.
    """
    total_rows = profile_data.get("rows", 0)
    total_cols = profile_data.get("columns", 0)

    if total_rows == 0 or total_cols == 0:
        return {
            "status": "success",
            "overall_score": 0.0,
            "grade": "F",
            "pillars": {
                "completeness": 0.0,
                "uniqueness": 0.0,
                "consistency": 0.0,
                "validity": 0.0
            },
            "deductions": ["Dataset is empty. Score is 0."],
            "summary": "Empty dataset cannot be scored."
        }

    deductions: List[Dict[str, Any]] = []

    # ---------------------------------------------------------
    # 1. Completeness Pillar (Max 30 Points)
    # ---------------------------------------------------------
    completeness_max = 30.0
    missing_pct = missing_data.get("overall_missing_percentage", 0.0)
    # Deduct proportionally to missing cell percentage
    completeness_deduction = round((missing_pct / 100.0) * completeness_max * 1.5, 2)
    completeness_deduction = min(completeness_max, completeness_deduction)
    completeness_score = round(completeness_max - completeness_deduction, 2)

    if completeness_deduction > 0:
        deductions.append({
            "pillar": "Completeness",
            "points_deducted": completeness_deduction,
            "reason": f"Missing values present: {missing_pct}% of total cells are null or empty."
        })

    # ---------------------------------------------------------
    # 2. Uniqueness Pillar (Max 20 Points)
    # ---------------------------------------------------------
    uniqueness_max = 20.0
    dup_pct = duplicate_data.get("exact_duplicates_percentage", 0.0)
    # Deduct proportionally to duplicate row percentage
    dup_deduction = round((dup_pct / 100.0) * uniqueness_max * 1.5, 2)
    
    # Small penalty for potential/fuzzy duplicate clusters (up to 2 points)
    potential_groups = len(duplicate_data.get("potential_duplicate_groups", []))
    fuzzy_deduction = min(3.0, potential_groups * 0.75)
    
    uniqueness_deduction = min(uniqueness_max, round(dup_deduction + fuzzy_deduction, 2))
    uniqueness_score = round(uniqueness_max - uniqueness_deduction, 2)

    if dup_deduction > 0:
        deductions.append({
            "pillar": "Uniqueness",
            "points_deducted": dup_deduction,
            "reason": f"Exact duplicates found: {dup_pct}% of rows are completely duplicate."
        })
    if fuzzy_deduction > 0:
        deductions.append({
            "pillar": "Uniqueness",
            "points_deducted": fuzzy_deduction,
            "reason": f"Detected {potential_groups} cluster(s) of potential/near duplicates."
        })

    # ---------------------------------------------------------
    # 3. Consistency Pillar (Max 25 Points)
    # ---------------------------------------------------------
    consistency_max = 25.0
    consistency_deduction = 0.0

    date_issues = len(inconsistency_data.get("date_inconsistencies", []))
    cat_issues = len(inconsistency_data.get("categorical_inconsistencies", []))
    type_issues = len(inconsistency_data.get("type_inconsistencies", []))

    if date_issues > 0:
        pts = min(8.0, date_issues * 3.5)
        consistency_deduction += pts
        deductions.append({
            "pillar": "Consistency",
            "points_deducted": pts,
            "reason": f"{date_issues} column(s) contain mixed or invalid date formats."
        })

    if cat_issues > 0:
        pts = min(7.0, cat_issues * 2.5)
        consistency_deduction += pts
        deductions.append({
            "pillar": "Consistency",
            "points_deducted": pts,
            "reason": f"{cat_issues} categorical column(s) have casing or whitespace discrepancies."
        })

    if type_issues > 0:
        pts = min(10.0, type_issues * 4.0)
        consistency_deduction += pts
        deductions.append({
            "pillar": "Consistency",
            "points_deducted": pts,
            "reason": f"{type_issues} column(s) have data type pollution (e.g. text in numeric fields)."
        })

    consistency_deduction = min(consistency_max, round(consistency_deduction, 2))
    consistency_score = round(consistency_max - consistency_deduction, 2)

    # ---------------------------------------------------------
    # 4. Validity & Normality Pillar (Max 25 Points)
    # ---------------------------------------------------------
    validity_max = 25.0
    validity_deduction = 0.0

    anomaly_pct = anomaly_data.get("anomalies_percentage", 0.0)
    suspicious_count = len(inconsistency_data.get("suspicious_values", []))

    if anomaly_pct > 0:
        pts = min(15.0, round((anomaly_pct / 100.0) * validity_max * 1.5, 2))
        validity_deduction += pts
        deductions.append({
            "pillar": "Validity",
            "points_deducted": pts,
            "reason": f"Anomalies detected: {anomaly_pct}% of rows flagged as statistical outliers."
        })

    if suspicious_count > 0:
        pts = min(10.0, suspicious_count * 3.0)
        validity_deduction += pts
        deductions.append({
            "pillar": "Validity",
            "points_deducted": pts,
            "reason": f"{suspicious_count} column(s) contain suspicious or domain-invalid values (e.g. negative age)."
        })

    validity_deduction = min(validity_max, round(validity_deduction, 2))
    validity_score = round(validity_max - validity_deduction, 2)

    # ---------------------------------------------------------
    # Overall Score & Letter Grade
    # ---------------------------------------------------------
    total_score = round(completeness_score + uniqueness_score + consistency_score + validity_score, 1)
    total_score = max(0.0, min(100.0, total_score))

    if total_score >= 90.0:
        grade = "A (Excellent)"
    elif total_score >= 80.0:
        grade = "B (Good)"
    elif total_score >= 70.0:
        grade = "C (Fair)"
    elif total_score >= 60.0:
        grade = "D (Poor)"
    else:
        grade = "F (Critical Issues)"

    total_points_lost = round(100.0 - total_score, 1)

    return {
        "status": "success",
        "overall_score": total_score,
        "grade": grade,
        "pillars": {
            "completeness": {
                "score": completeness_score,
                "max": completeness_max,
                "percentage": round((completeness_score / completeness_max) * 100, 1)
            },
            "uniqueness": {
                "score": uniqueness_score,
                "max": uniqueness_max,
                "percentage": round((uniqueness_score / uniqueness_max) * 100, 1)
            },
            "consistency": {
                "score": consistency_score,
                "max": consistency_max,
                "percentage": round((consistency_score / consistency_max) * 100, 1)
            },
            "validity": {
                "score": validity_score,
                "max": validity_max,
                "percentage": round((validity_score / validity_max) * 100, 1)
            }
        },
        "total_points_deducted": total_points_lost,
        "deductions": deductions,
        "summary": {
            "formula": "Score = Completeness (30 pts) + Uniqueness (20 pts) + Consistency (25 pts) + Validity (25 pts)",
            "explanation": (
                f"Dataset scored {total_score}/100 ({grade}). "
                f"Lost {total_points_lost} point(s) primarily due to "
                + (deductions[0]["reason"] if deductions else "no issues detected.")
            )
        }
    }


if __name__ == "__main__":
    import json
    # Quick test demonstration
    dummy_prof = {"rows": 100, "columns": 5}
    dummy_miss = {"overall_missing_percentage": 5.0}
    dummy_dup = {"exact_duplicates_percentage": 2.0, "potential_duplicate_groups": [1]}
    dummy_anom = {"anomalies_percentage": 3.0}
    dummy_inc = {
        "date_inconsistencies": [1],
        "categorical_inconsistencies": [1],
        "type_inconsistencies": [],
        "suspicious_values": [1]
    }
    res = calculate_quality_score(dummy_prof, dummy_miss, dummy_dup, dummy_anom, dummy_inc)
    print(json.dumps(res, indent=2))
