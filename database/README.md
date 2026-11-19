# 🗄️ DataFix – Autonomous Data Quality Engine

DataFix is an AI-powered data quality management application designed to analyze, identify, and improve the quality of structured datasets.

It combines statistical profiling, automated anomaly detection, AI-driven recommendations, data-cleaning operations, and database-backed analysis history in an interactive Streamlit dashboard.

---

## 🚀 Key Features

### 1. Dataset Upload
- Upload CSV and Excel datasets.
- Validate supported file formats.
- Preview uploaded datasets.
- Generate a sample dataset for demonstration.

### 2. Data Profiling
- Dataset overview and column information.
- Missing value analysis.
- Duplicate record detection.
- Numerical and categorical statistics.
- Unique value analysis.
- Data quality summary.

### 3. Data Quality Analysis
- Calculate dataset quality scores.
- Identify missing values and duplicates.
- Analyze numerical outliers.
- Visualize data quality information.
- Detect anomalies using machine learning.

### 4. AI-Powered Recommendations
- Generate automated data-cleaning recommendations.
- Identify potential data quality problems.
- Apply safe recommendations.
- Require approval before destructive AI operations.

### 5. Data Cleaning and Remediation
- Missing value imputation.
- Duplicate row removal.
- Outlier clipping and filtering.
- Text standardization.
- Cleaning audit history.
- Before-and-after data comparison.
- Confirmation before destructive manual operations.

### 6. Data Export
- Export cleaned datasets as CSV.
- Export cleaned datasets as Excel.
- Download cleaning audit information as JSON.

### 7. Analysis History
- View previous analysis sessions.
- Inspect profiling reports.
- Review AI recommendations.
- View cleaning history.
- Compare initial and post-cleaning quality scores.

Note: Previous session history stores analysis information and reports; it does not currently restore the original or cleaned DataFrame.

---

## 🛠️ Technology Stack

| Component | Technology |
|---|---|
| Programming Language | Python |
| Frontend | Streamlit |
| Data Processing | Pandas, NumPy |
| Machine Learning | Scikit-learn |
| Data Visualization | Plotly |
| Database | SQLite |
| Excel Processing | OpenPyXL |
| Testing | Pytest |

---

## 🏗️ System Architecture

DataFix is organized into four major functional layers.

**1. Frontend Layer**
- Streamlit dashboard.
- Dataset upload and preview.
- Profiling and visualization.
- Cleaning controls.
- Export and history management.

**2. Backend Layer**
- Dataset ingestion and validation.
- Statistical profiling.
- Data-cleaning pipeline.

**3. AI Layer**
- Anomaly detection.
- Missing value analysis.
- Duplicate detection.
- Inconsistency detection.
- Quality scoring.
- Automated recommendations and correction support.

**4. Database Layer**
- Analysis session management.
- Profiling report storage.
- AI recommendation storage.
- Cleaning audit history.
- Quality comparison records.

---

## 📁 Project Structure

```text
DataFix-Autonomous-Data-Quality-Engine/
│
├── ai/
│   ├── anomaly_detector.py
│   ├── correction_engine.py
│   ├── duplicate_detector.py
│   ├── inconsistency_detector.py
│   ├── main.py
│   ├── missing_values.py
│   ├── profiler.py
│   ├── quality_score.py
│   └── recommender.py
│
├── backend/
│   ├── cleaning.py
│   ├── profiling.py
│   └── upload.py
│
├── database/
│   ├── db.py
│   ├── manager.py
│   └── schema.py
│
├── frontend/
│   ├── app.py
│   ├── index.html
│   ├── script.js
│   ├── style.css
│   ├── styles.py
│   └── visualizations.py
│
├── tests/
│   ├── test_ai.py
│   ├── test_cleaning.py
│   ├── test_database.py
│   ├── test_profiling.py
│   └── test_upload.py
│
├── .gitignore
├── datafix.db
├── pytest.ini
├── requirements.txt
├── README.md
├── test_database.py
└── test_db.py
```

---

## ⚙️ Installation and Setup

### Prerequisites

- Python 3.13 or compatible Python environment.
- pip package manager.
- Git.

### Step 1: Clone the Repository

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
```

### Step 2: Navigate to the Project

```bash
cd DataFix-Autonomous-Data-Quality-Engine
```

### Step 3: Create a Virtual Environment

```bash
python -m venv .venv
```

### Step 4: Activate the Environment

**Windows PowerShell:**

```powershell
.venv\Scripts\activate
```

### Step 5: Install Dependencies

```bash
pip install -r requirements.txt
```

---

## ▶️ Running the Application

Start the Streamlit application using:

```bash
streamlit run frontend/app.py
```

The application will open in your browser.

---

## 🗄️ Database Architecture

DataFix uses SQLite for persistent storage.

Two database modules are maintained:

### 1. Legacy Database – `database/db.py`

Handles:
- Uploaded dataset metadata.
- Detected quality issues.
- Repair history.
- Upload and repair summaries.

Tables:
- `uploads`
- `quality_issues`
- `repair_logs`

### 2. Analysis Database – `database/manager.py`

Handles:
- Analysis sessions.
- Initial and post-cleaning profiling reports.
- AI recommendations.
- Cleaning history.
- Before-and-after quality comparisons.

Tables:
- `analysis_runs`
- `profiling_reports`
- `ai_recommendations`
- `cleaning_history`
- `quality_comparisons`

---

## 🧪 Testing

The project uses Pytest for automated testing.

Run the complete test suite using:

```bash
python -m pytest
```

Run an individual test module using:

```bash
python -m pytest tests/test_cleaning.py
```

---

## 🎯 Project Objective

The primary objective of DataFix is to simplify data quality management through automated analysis, machine-learning-based anomaly detection, intelligent recommendations, and structured data-cleaning workflows.

The application aims to reduce manual data-cleaning effort while improving data reliability, transparency, and usability.

---

## 👥 Project Information

**Project Name:** DataFix – Autonomous Data Quality Engine

**Category:** AI / Machine Learning / Data Engineering

**Application Type:** Interactive Data Quality Management System