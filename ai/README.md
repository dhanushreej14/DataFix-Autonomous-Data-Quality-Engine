# DataFix – Autonomous Data Quality Engine
## AI/ML Module

The **AI/ML Module** of **DataFix** is an autonomous, non-destructive data quality auditing and correction engine. It ingests CSV datasets (via file path, in-memory file buffers, or pandas DataFrames), detects multidimensional quality problems, calculates an explainable 0–100 Data Quality Score, and generates intelligent, prioritized correction recommendations with a non-destructive cleaner.

---

## 📁 Module Structure

```text
ai/
├── main.py                     # Unified API gateway & CLI orchestrator
├── profiler.py                 # Data profiling (dimensions, types, memory, summaries)
├── missing_values.py           # Missing & null value audit with type-aware strategy recommender
├── duplicate_detector.py       # Exact duplicate indices & fuzzy text/subset near-duplicate detector
├── anomaly_detector.py         # ML anomaly detection (Isolation Forest) with human-readable explanations
├── inconsistency_detector.py   # Mixed date formats, categorical casing/typos, contaminated types, suspicious values
├── correction_engine.py        # Actionable recommendations & non-destructive cleaning pipeline
├── quality_score.py            # Transparent 0–100 scoring engine across 4 quality pillars
├── requirements.txt            # Minimal, lightweight dependencies (pandas, numpy, scikit-learn, python-dateutil)
├── sample_test.csv             # Benchmark dirty dataset featuring real-world quality defects
├── test_profiler.py            # Unit tests for profiler
├── test_batch1.py              # Unit tests for missing values and duplicate detectors
├── test_batch2.py              # Unit tests for anomaly and inconsistency detectors
└── test_batch3.py              # Unit tests for quality score and correction engines
```

---

## 🚀 Quick Start & CLI Usage

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Analyze a CSV Dataset via CLI
```bash
python main.py sample_test.csv
```
**Sample Terminal Output:**
```text
=======================================================
 DATAFIX - DATA QUALITY AUDIT REPORT
=======================================================
 Overall Score: 72.2 / 100
 Letter Grade:  C (Fair)
-------------------------------------------------------
 Completeness   : 28.6 / 30 (95.4%)
 Uniqueness     : 17.1 / 20 (85.5%)
 Consistency    : 12.5 / 25 (50.0%)
 Validity       : 14.0 / 25 (55.8%)
-------------------------------------------------------
 Rows Analyzed : 14
 Columns       : 7
 Missing Cells : 3
 Duplicates    : 1
 Anomalies (ML): 3
 Inconsistencies: 5
 Suggested Fixes: 10
=======================================================
```

### 3. Generate a Cleaned Output File (Non-Destructive)
```bash
python main.py sample_test.csv --clean cleaned_dataset.csv
```
*Note: The original dataset is never modified. Cleaned data is saved strictly to the specified output.*

### 4. Run the Full Test Suite
```bash
python -m unittest discover -s . -p "test_*.py"
```
*(All 15 automated unit & integration tests execute in < 0.7s).*

---

## 🔌 Backend Integration Guide

For the **Backend Developer**, integrating the AI module into your API service (FastAPI or Flask) requires only **1 import**:

### Python Function Interface
```python
from main import analyze_dataset, clean_dataset

# 1. Analyze an uploaded CSV file (accepts file path, UploadFile buffer, or DataFrame)
report = analyze_dataset("uploaded_file.csv")

# 2. Generate a separate, non-destructive cleaned CSV string or DataFrame
cleaned_result = clean_dataset("uploaded_file.csv", return_format="csv")
cleaned_csv_string = cleaned_result["cleaned_csv"]
```

### FastAPI Integration Example
```python
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse, Response
import io
from ai.main import analyze_dataset, clean_dataset

app = FastAPI(title="DataFix Backend API")

@app.post("/api/audit")
async def audit_dataset(file: UploadFile = File(...)):
    """Receives an uploaded CSV and returns full JSON data quality report."""
    contents = await file.read()
    buffer = io.BytesIO(contents)
    report = analyze_dataset(buffer)
    return JSONResponse(content=report)

@app.post("/api/clean")
async def clean_csv(file: UploadFile = File(...)):
    """Returns the non-destructively cleaned CSV file for download."""
    contents = await file.read()
    buffer = io.BytesIO(contents)
    clean_res = clean_dataset(buffer, return_format="csv")
    
    return Response(
        content=clean_res["cleaned_csv"],
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=cleaned_{file.filename}"}
    )
```

### Flask Integration Example
```python
from flask import Flask, request, jsonify, Response
from ai.main import analyze_dataset, clean_dataset

app = Flask(__name__)

@app.route("/api/audit", methods=["POST"])
def audit():
    uploaded_file = request.files.get("file")
    if not uploaded_file:
        return jsonify({"error": "No file uploaded"}), 400
    report = analyze_dataset(uploaded_file)
    return jsonify(report)

@app.route("/api/clean", methods=["POST"])
def clean():
    uploaded_file = request.files.get("file")
    clean_res = clean_dataset(uploaded_file, return_format="csv")
    return Response(
        clean_res["cleaned_csv"],
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=cleaned_dataset.csv"}
    )
```

---

## 📊 Structured JSON Output Contract

The JSON returned by `analyze_dataset()` contains the following top-level keys:

```json
{
  "status": "success",
  "dataset_name": "sample_test.csv",
  "execution_timestamp": "2026-11-19T12:00:00Z",
  "quality_score": {
    "overall_score": 72.2,
    "grade": "C (Fair)",
    "pillars": {
      "completeness": {"score": 28.6, "max": 30.0, "percentage": 95.4},
      "uniqueness": {"score": 17.1, "max": 20.0, "percentage": 85.5},
      "consistency": {"score": 12.5, "max": 25.0, "percentage": 50.0},
      "validity": {"score": 14.0, "max": 25.0, "percentage": 55.8}
    },
    "total_points_deducted": 27.8,
    "deductions": [
      {"pillar": "Consistency", "points_deducted": 4.0, "reason": "1 column(s) have data type pollution..."},
      {"pillar": "Validity", "points_deducted": 3.2, "reason": "Anomalies detected: 21.43% of rows flagged..."}
    ],
    "summary": { "formula": "...", "explanation": "..." }
  },
  "profiling": {
    "rows": 14,
    "columns": 7,
    "column_names": ["id", "full_name", "age", "salary", "join_date", "department", "status"],
    "columns_profile": { ... }
  },
  "missing_values": {
    "total_missing_cells": 3,
    "overall_missing_percentage": 3.06,
    "affected_columns": ["age", "salary", "department"],
    "recommendations": [ ... ]
  },
  "duplicates": {
    "exact_duplicates_count": 1,
    "exact_duplicate_indices": [11],
    "potential_duplicates_count": 2,
    "potential_duplicate_groups": [ ... ]
  },
  "anomalies": {
    "algorithm_used": "Isolation Forest",
    "anomalies_count": 3,
    "anomalous_records": [
      {
        "row_index": 6,
        "anomaly_score": 1.0,
        "record": { "full_name": "Eva Davis", "salary": "9999999", ... },
        "reasons": ["Column 'salary' value 9999999.0 is 139.9x higher than median..."]
      }
    ]
  },
  "inconsistencies": {
    "date_inconsistencies": [ ... ],
    "categorical_inconsistencies": [ ... ],
    "type_inconsistencies": [ ... ],
    "suspicious_values": [ ... ]
  },
  "correction_suggestions": [
    {
      "action_id": "drop_exact_duplicates",
      "category": "Uniqueness",
      "priority": "HIGH",
      "title": "Remove Exact Duplicate Records",
      "description": "Drop 1 exact duplicate row(s)...",
      "auto_apply": true
    }
  ]
}
```

---

## 🛡️ Non-Destructive Guarantee

In compliance with enterprise data engineering standards:
- The engine **never mutates or overwrites** original dataset files or input memory buffers.
- Cleaned datasets are produced on a separate DataFrame copy (`df.copy()`) and delivered only upon explicit user/backend request.
