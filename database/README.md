# 🗄️ DataFix – Database Module Cheat Sheet

Welcome to the **DataFix Database Module**! This guide is designed for the entire team (Backend, AI Engine, and Frontend) to easily connect and interact with our SQLite database (`datafix.db`).

---

## 🚀 Quick Start (How to Import)

All database functions are pre-packaged and ready to use in any script across the project:

```python
from database.db import (
    init_db,
    save_upload_details,
    save_quality_issue,
    save_repair_history,
    get_upload_history,
    get_quality_issues,
    get_repair_history,
    display_upload_history,
    display_repair_history,
)
```

---

## 📌 Complete Workflow Example

Here is how the entire DataFix engine interacts with the database in 4 steps:

```python
# 1. Initialize DB at server startup
init_db()

# 2. When a user uploads a dataset
upload_id = save_upload_details(
    filename="customer_data.csv",
    num_rows=1500,
    num_columns=12
)
# Returns: 1 (Primary Key)

# 3. When the AI Engine detects an issue
issue_id = save_quality_issue(
    upload_id=upload_id,
    column_name="email",
    issue_type="Missing Values",
    num_issues=45
)

# 4. When the Repair Engine fixes the issue
repair_id = save_repair_history(
    upload_id=upload_id,
    column_name="email",
    repair_type="Imputed Default / Placeholder",
    repaired_rows=45
)

# 5. Display summary in the terminal
display_upload_history()
display_repair_history()
```

---

## 📚 Function Reference

### 1. `init_db()`
Creates the database file and all required tables if they don't already exist.
* **When to call**: Once at application / backend startup.
* **Returns**: `True` if successful, `False` on error.

```python
init_db()
```

---

### 2. `save_upload_details(filename, num_rows, num_columns, upload_time=None)`
Saves metadata of an uploaded file into the `uploads` table.
* **Parameters**:
  * `filename` *(str)*: Name of the uploaded file (e.g. `"sales.csv"`).
  * `num_rows` *(int)*: Total number of rows in the dataset.
  * `num_columns` *(int)*: Total number of columns.
  * `upload_time` *(str, optional)*: Timestamp. Defaults to current local time.
* **Returns**: `upload_id` *(int)* – Pass this ID to the AI engine and repair logs.

```python
upload_id = save_upload_details("sales.csv", num_rows=1000, num_columns=10)
```

---

### 3. `save_quality_issue(upload_id, column_name, issue_type, num_issues)`
Logs a detected data quality issue into the `quality_issues` table.
* **Parameters**:
  * `upload_id` *(int)*: The ID of the dataset upload (Foreign Key).
  * `column_name` *(str)*: The column containing issues (e.g. `"age"`, `"email"`).
  * `issue_type` *(str)*: Category (e.g. `"Missing Values"`, `"Duplicates"`, `"Outliers"`).
  * `num_issues` *(int)*: Count of issues found.
* **Returns**: `issue_id` *(int)* or `None` if `upload_id` does not exist.

```python
save_quality_issue(upload_id=1, column_name="age", issue_type="Outliers", num_issues=12)
```

---

### 4. `save_repair_history(upload_id, column_name, repair_type, repaired_rows, repair_date=None)`
Logs a repair action performed on a dataset into the `repair_logs` table.
* **Parameters**:
  * `upload_id` *(int)*: The ID of the dataset upload (Foreign Key).
  * `column_name` *(str)*: The column repaired.
  * `repair_type` *(str)*: The operation applied (e.g. `"Mean Imputation"`, `"Trimmed Whitespace"`).
  * `repaired_rows` *(int)*: Number of rows modified.
  * `repair_date` *(str, optional)*: Timestamp. Defaults to current local time.
* **Returns**: `repair_id` *(int)* or `None` on error.

```python
save_repair_history(
    upload_id=1,
    column_name="age",
    repair_type="Capped at Maximum (100)",
    repaired_rows=12
)
```

---

### 5. Data Retrieval Functions (For APIs & Frontend)

#### `get_upload_history()`
Fetches all uploaded files ordered from newest to oldest.
* **Returns**: `list` of rows. Access columns by name:
  ```python
  uploads = get_upload_history()
  for u in uploads:
      print(u["upload_id"], u["filename"], u["num_rows"])
  ```

#### `get_quality_issues(upload_id=None)`
Fetches detected issues. If `upload_id` is given, filters for that upload.
* **Returns**: `list` of issue rows.
  ```python
  issues = get_quality_issues(upload_id=1)
  for item in issues:
      print(item["column_name"], item["issue_type"], item["num_issues"])
  ```

#### `get_repair_history(upload_id=None)`
Fetches repair logs. If `upload_id` is given, filters for that upload.
* **Returns**: `list` of repair rows.
  ```python
  repairs = get_repair_history(upload_id=1)
  for r in repairs:
      print(r["column_name"], r["repair_type"], r["repaired_rows"])
  ```

#### `get_dataset_summary(upload_id)`
Calculates a consolidated health and repair metric card for a specific upload.
* **Returns**: `dict` containing `health_score_pct`, `repair_progress_pct`, `total_issues`, `total_repaired`, `total_cells`, and `status`.
  ```python
  summary = get_dataset_summary(upload_id=1)
  print(summary["health_score_pct"])     # e.g., 98.5%
  print(summary["repair_progress_pct"])  # e.g., 100.0%
  ```

#### `export_upload_to_dict(upload_id)`
Exports upload info + issues + repairs in a single nested dictionary ready for REST API JSON responses:
  ```python
  data = export_upload_to_dict(upload_id=1)
  # Returns: {"summary": {...}, "issues": [...], "repairs": [...]}
  ```

#### `delete_upload(upload_id)`
Deletes an upload. Automatically cascades and deletes all related issues and repair logs:
  ```python
  success = delete_upload(upload_id=1)
  ```

---

### 6. Terminal Display Functions (For CLI & Demos)

* **`display_upload_history()`**: Prints a formatted table of all uploads.
* **`display_repair_history(upload_id=None)`**: Prints a formatted table of all repairs.

---

## 🗄️ Database Tables Schema

### 1. `uploads`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `upload_id` | `INTEGER` | `PRIMARY KEY AUTOINCREMENT` | Unique upload identifier |
| `filename` | `TEXT` | `NOT NULL` | Original filename |
| `upload_time` | `TEXT` | `NOT NULL` | Upload date and time |
| `num_rows` | `INTEGER` | `NOT NULL` | Total rows in dataset |
| `num_columns` | `INTEGER` | `NOT NULL` | Total columns in dataset |

### 2. `quality_issues`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `issue_id` | `INTEGER` | `PRIMARY KEY AUTOINCREMENT` | Unique issue identifier |
| `upload_id` | `INTEGER` | `FOREIGN KEY (uploads)` | Links to the uploaded file |
| `column_name` | `TEXT` | `NOT NULL` | Name of the column with issues |
| `issue_type` | `TEXT` | `NOT NULL` | E.g., Missing, Duplicate, Outlier |
| `num_issues` | `INTEGER` | `NOT NULL` | Count of affected rows |

### 3. `repair_logs`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `repair_id` | `INTEGER` | `PRIMARY KEY AUTOINCREMENT` | Unique repair identifier |
| `upload_id` | `INTEGER` | `FOREIGN KEY (uploads)` | Links to the uploaded file |
| `column_name` | `TEXT` | `NOT NULL` | Column that was fixed |
| `repair_type` | `TEXT` | `NOT NULL` | Operation applied |
| `repaired_rows` | `INTEGER` | `NOT NULL` | Number of rows modified |
| `repair_date` | `TEXT` | `NOT NULL` | Timestamp of fix |

---

## 🧪 Testing the Database

To run the full test suite and verify functionality, run:

```powershell
python test_database.py
```
