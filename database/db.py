"""
DataFix - Database Module (db.py)
---------------------------------
This module manages the SQLite database for the DataFix project.
It handles storing uploaded dataset details, detected quality issues,
and data repair logs.

Database: datafix.db
Tables:
    1. uploads         - Stores metadata about uploaded datasets.
    2. quality_issues  - Stores issues detected in columns (missing, duplicates, etc.).
    3. repair_logs     - Stores records of fixes applied to columns.
"""

import os
import sqlite3
from datetime import datetime

# ---------------------------------------------------------------------------
# Database File Path Configuration
# ---------------------------------------------------------------------------
# We locate 'datafix.db' inside the same directory as this script (database/).
# This ensures any part of the project can find the database reliably.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "datafix.db")


# ---------------------------------------------------------------------------
# Connection Helper Function
# ---------------------------------------------------------------------------
def get_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """
    Creates and returns a connection to the SQLite database.

    Important Note on SQLite Foreign Keys:
    By default in SQLite, foreign key enforcement is turned OFF!
    We must run 'PRAGMA foreign_keys = ON;' every time a new connection
    is opened so SQLite will validate parent-child relationships.
    """
    conn = sqlite3.connect(db_path)
    # Enable foreign key constraint checking
    conn.execute("PRAGMA foreign_keys = ON;")
    # row_factory lets us access columns by name (e.g., row["filename"])
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# 1. Initialize the Database (Create Tables)
# ---------------------------------------------------------------------------
def init_db(db_path: str = DEFAULT_DB_PATH) -> bool:
    """
    Creates all necessary tables if they do not already exist.

    Tables created:
    1. uploads:
       - upload_id (INTEGER PRIMARY KEY AUTOINCREMENT)
       - filename (TEXT NOT NULL)
       - upload_time (TEXT NOT NULL)
       - num_rows (INTEGER NOT NULL)
       - num_columns (INTEGER NOT NULL)

    2. quality_issues:
       - issue_id (INTEGER PRIMARY KEY AUTOINCREMENT)
       - upload_id (INTEGER NOT NULL, FOREIGN KEY -> uploads)
       - column_name (TEXT NOT NULL)
       - issue_type (TEXT NOT NULL)
       - num_issues (INTEGER NOT NULL)

    3. repair_logs:
       - repair_id (INTEGER PRIMARY KEY AUTOINCREMENT)
       - upload_id (INTEGER NOT NULL, FOREIGN KEY -> uploads)
       - column_name (TEXT NOT NULL)
       - repair_type (TEXT NOT NULL)
       - repaired_rows (INTEGER NOT NULL)
       - repair_date (TEXT NOT NULL)
    """
    create_uploads_table = """
    CREATE TABLE IF NOT EXISTS uploads (
        upload_id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL,
        upload_time TEXT NOT NULL,
        num_rows INTEGER NOT NULL,
        num_columns INTEGER NOT NULL
    );
    """

    create_quality_issues_table = """
    CREATE TABLE IF NOT EXISTS quality_issues (
        issue_id INTEGER PRIMARY KEY AUTOINCREMENT,
        upload_id INTEGER NOT NULL,
        column_name TEXT NOT NULL,
        issue_type TEXT NOT NULL,
        num_issues INTEGER NOT NULL,
        FOREIGN KEY (upload_id) REFERENCES uploads (upload_id) ON DELETE CASCADE
    );
    """

    create_repair_logs_table = """
    CREATE TABLE IF NOT EXISTS repair_logs (
        repair_id INTEGER PRIMARY KEY AUTOINCREMENT,
        upload_id INTEGER NOT NULL,
        column_name TEXT NOT NULL,
        repair_type TEXT NOT NULL,
        repaired_rows INTEGER NOT NULL,
        repair_date TEXT NOT NULL,
        FOREIGN KEY (upload_id) REFERENCES uploads (upload_id) ON DELETE CASCADE
    );
    """

    conn = None
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()

        # Execute table creation queries
        cursor.execute(create_uploads_table)
        cursor.execute(create_quality_issues_table)
        cursor.execute(create_repair_logs_table)

        conn.commit()
        print(f"[DB INFO] Database initialized successfully at '{db_path}'.")
        return True

    except sqlite3.Error as error:
        print(f"[DB ERROR] Error initializing database: {error}")
        if conn:
            conn.rollback()
        return False

    finally:
        if conn:
            conn.close()


# ---------------------------------------------------------------------------
# 2. Save Uploaded File Details
# ---------------------------------------------------------------------------
def save_upload_details(
    filename: str,
    num_rows: int,
    num_columns: int,
    upload_time: str = None,
    db_path: str = DEFAULT_DB_PATH
) -> int:
    """
    Saves a newly uploaded dataset record into the 'uploads' table.

    Parameters:
        filename (str): Name of the uploaded file (e.g. 'sales_data.csv').
        num_rows (int): Total number of rows in the dataset.
        num_columns (int): Total number of columns in the dataset.
        upload_time (str, optional): Date and time of upload. Defaults to current time.
        db_path (str, optional): Path to the SQLite database.

    Returns:
        int: The generated upload_id (Primary Key), or None if an error occurs.
    """
    if upload_time is None:
        upload_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    sql = """
    INSERT INTO uploads (filename, upload_time, num_rows, num_columns)
    VALUES (?, ?, ?, ?);
    """

    conn = None
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()

        # Use parameterized queries (?) to protect against SQL Injection
        cursor.execute(sql, (filename, upload_time, num_rows, num_columns))
        conn.commit()

        # cursor.lastrowid contains the AUTOINCREMENT ID of the inserted row
        new_upload_id = cursor.lastrowid
        print(f"[DB INFO] Upload saved with ID: {new_upload_id} ('{filename}')")
        return new_upload_id

    except sqlite3.Error as error:
        print(f"[DB ERROR] Failed to save upload details for '{filename}': {error}")
        if conn:
            conn.rollback()
        return None

    finally:
        if conn:
            conn.close()


# ---------------------------------------------------------------------------
# 3. Save Quality Issues
# ---------------------------------------------------------------------------
def save_quality_issue(
    upload_id: int,
    column_name: str,
    issue_type: str,
    num_issues: int,
    db_path: str = DEFAULT_DB_PATH
) -> int:
    """
    Saves a detected data quality issue into the 'quality_issues' table.

    Parameters:
        upload_id (int): Foreign key matching 'upload_id' in uploads table.
        column_name (str): Name of the column with the issue (e.g., 'email', 'age').
        issue_type (str): Type of issue (e.g., 'Missing Values', 'Duplicates', 'Outliers').
        num_issues (int): How many issues were found in that column.
        db_path (str, optional): Path to the SQLite database.

    Returns:
        int: The generated issue_id, or None if an error occurs.
    """
    sql = """
    INSERT INTO quality_issues (upload_id, column_name, issue_type, num_issues)
    VALUES (?, ?, ?, ?);
    """

    conn = None
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()

        cursor.execute(sql, (upload_id, column_name, issue_type, num_issues))
        conn.commit()

        new_issue_id = cursor.lastrowid
        print(f"[DB INFO] Quality issue saved with ID: {new_issue_id} for Upload #{upload_id}")
        return new_issue_id

    except sqlite3.Error as error:
        print(f"[DB ERROR] Failed to save quality issue for Upload #{upload_id}: {error}")
        if conn:
            conn.rollback()
        return None

    finally:
        if conn:
            conn.close()


# ---------------------------------------------------------------------------
# 4. Save Repair History
# ---------------------------------------------------------------------------
def save_repair_history(
    upload_id: int,
    column_name: str,
    repair_type: str,
    repaired_rows: int,
    repair_date: str = None,
    db_path: str = DEFAULT_DB_PATH
) -> int:
    """
    Saves an action taken to fix or clean data into the 'repair_logs' table.

    Parameters:
        upload_id (int): Foreign key matching 'upload_id' in uploads table.
        column_name (str): Name of the column that was repaired.
        repair_type (str): The repair action applied (e.g. 'Imputed with Mean', 'Removed Duplicates').
        repaired_rows (int): Number of rows altered/repaired.
        repair_date (str, optional): Timestamp of the repair. Defaults to current time.
        db_path (str, optional): Path to the SQLite database.

    Returns:
        int: The generated repair_id, or None if an error occurs.
    """
    if repair_date is None:
        repair_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    sql = """
    INSERT INTO repair_logs (upload_id, column_name, repair_type, repaired_rows, repair_date)
    VALUES (?, ?, ?, ?, ?);
    """

    conn = None
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()

        cursor.execute(sql, (upload_id, column_name, repair_type, repaired_rows, repair_date))
        conn.commit()

        new_repair_id = cursor.lastrowid
        print(f"[DB INFO] Repair log saved with ID: {new_repair_id} for Upload #{upload_id}")
        return new_repair_id

    except sqlite3.Error as error:
        print(f"[DB ERROR] Failed to save repair log for Upload #{upload_id}: {error}")
        if conn:
            conn.rollback()
        return None

    finally:
        if conn:
            conn.close()


# ---------------------------------------------------------------------------
# 5. Fetch Functions (Helper Functions to Retrieve Data)
# ---------------------------------------------------------------------------
def get_upload_history(db_path: str = DEFAULT_DB_PATH) -> list:
    """
    Retrieves all records from the 'uploads' table, ordered from newest to oldest.

    Returns:
        list of sqlite3.Row: List of rows, or empty list if none found.
    """
    sql = "SELECT upload_id, filename, upload_time, num_rows, num_columns FROM uploads ORDER BY upload_id DESC;"

    conn = None
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute(sql)
        rows = cursor.fetchall()
        return rows
    except sqlite3.Error as error:
        print(f"[DB ERROR] Error fetching upload history: {error}")
        return []
    finally:
        if conn:
            conn.close()


def get_repair_history(upload_id: int = None, db_path: str = DEFAULT_DB_PATH) -> list:
    """
    Retrieves records from the 'repair_logs' table.
    If upload_id is provided, only retrieves repairs for that specific upload.

    Returns:
        list of sqlite3.Row: List of repair rows.
    """
    conn = None
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()

        if upload_id is not None:
            sql = """
            SELECT repair_id, upload_id, column_name, repair_type, repaired_rows, repair_date
            FROM repair_logs
            WHERE upload_id = ?
            ORDER BY repair_id DESC;
            """
            cursor.execute(sql, (upload_id,))
        else:
            sql = """
            SELECT repair_id, upload_id, column_name, repair_type, repaired_rows, repair_date
            FROM repair_logs
            ORDER BY repair_id DESC;
            """
            cursor.execute(sql)

        rows = cursor.fetchall()
        return rows
    except sqlite3.Error as error:
        print(f"[DB ERROR] Error fetching repair history: {error}")
        return []
    finally:
        if conn:
            conn.close()


def get_quality_issues(upload_id: int = None, db_path: str = DEFAULT_DB_PATH) -> list:
    """
    Retrieves quality issues, optionally filtered by upload_id.

    Returns:
        list of sqlite3.Row: List of quality issue rows.
    """
    conn = None
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()

        if upload_id is not None:
            sql = """
            SELECT issue_id, upload_id, column_name, issue_type, num_issues
            FROM quality_issues
            WHERE upload_id = ?
            ORDER BY issue_id ASC;
            """
            cursor.execute(sql, (upload_id,))
        else:
            sql = """
            SELECT issue_id, upload_id, column_name, issue_type, num_issues
            FROM quality_issues
            ORDER BY issue_id ASC;
            """
            cursor.execute(sql)

        return cursor.fetchall()
    except sqlite3.Error as error:
        print(f"[DB ERROR] Error fetching quality issues: {error}")
        return []
    finally:
        if conn:
            conn.close()


# ---------------------------------------------------------------------------
# 6. Display Functions (Print Formatted Tables in Console)
# ---------------------------------------------------------------------------
def display_upload_history(db_path: str = DEFAULT_DB_PATH) -> None:
    """
    Prints a clean, formatted table of all uploaded datasets to the terminal.
    """
    rows = get_upload_history(db_path)

    print("\n" + "=" * 80)
    print(" " * 30 + "UPLOAD HISTORY")
    print("=" * 80)

    if not rows:
        print("  No upload records found in database.")
        print("=" * 80 + "\n")
        return

    # Table Header
    print(f"{'ID':<6} | {'Filename':<30} | {'Upload Time':<20} | {'Rows':<8} | {'Cols':<6}")
    print("-" * 6 + "-+-" + "-" * 30 + "-+-" + "-" * 20 + "-+-" + "-" * 8 + "-+-" + "-" * 6)

    # Table Rows
    for row in rows:
        print(
            f"{row['upload_id']:<6} | "
            f"{row['filename'][:30]:<30} | "
            f"{row['upload_time']:<20} | "
            f"{row['num_rows']:<8} | "
            f"{row['num_columns']:<6}"
        )

    print("=" * 80 + "\n")


def display_repair_history(upload_id: int = None, db_path: str = DEFAULT_DB_PATH) -> None:
    """
    Prints a clean, formatted table of data repairs to the terminal.
    """
    rows = get_repair_history(upload_id, db_path)

    header_title = f"REPAIR HISTORY (Upload #{upload_id})" if upload_id else "REPAIR HISTORY (All Uploads)"

    print("\n" + "=" * 96)
    print(" " * 32 + header_title)
    print("=" * 96)

    if not rows:
        print("  No repair records found in database.")
        print("=" * 96 + "\n")
        return

    # Table Header
    print(
        f"{'Repair ID':<10} | {'Upload ID':<10} | {'Column Name':<18} | "
        f"{'Repair Type':<24} | {'Repaired':<9} | {'Repair Date':<20}"
    )
    print(
        "-" * 10 + "-+-" +
        "-" * 10 + "-+-" +
        "-" * 18 + "-+-" +
        "-" * 24 + "-+-" +
        "-" * 9 + "-+-" +
        "-" * 20
    )

    # Table Rows
    for row in rows:
        print(
            f"{row['repair_id']:<10} | "
            f"{row['upload_id']:<10} | "
            f"{row['column_name'][:18]:<18} | "
            f"{row['repair_type'][:24]:<24} | "
            f"{row['repaired_rows']:<9} | "
            f"{row['repair_date']:<20}"
        )

    print("=" * 96 + "\n")


# ---------------------------------------------------------------------------
# 7. Helper & Analysis Functions (Summary, Delete, Export)
# ---------------------------------------------------------------------------
def get_dataset_summary(upload_id: int, db_path: str = DEFAULT_DB_PATH) -> dict:
    """
    Computes a consolidated health and repair summary for a specific upload.

    Calculates:
      - Total data cells (rows * columns)
      - Total issues detected
      - Total rows repaired
      - Data Health Score % (100% minus the proportion of problematic cells)
      - Repair Progress % (repaired rows / total issues)

    Returns:
      dict: Summary statistics, or None if upload_id is not found.
    """
    conn = None
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()

        # 1. Fetch upload metadata
        cursor.execute(
            "SELECT upload_id, filename, upload_time, num_rows, num_columns FROM uploads WHERE upload_id = ?;",
            (upload_id,)
        )
        upload = cursor.fetchone()
        if not upload:
            print(f"[DB WARNING] Upload #{upload_id} not found.")
            return None

        # 2. Fetch total issues found
        cursor.execute(
            "SELECT COALESCE(SUM(num_issues), 0), COUNT(issue_id) FROM quality_issues WHERE upload_id = ?;",
            (upload_id,)
        )
        total_issues, issue_columns_count = cursor.fetchone()

        # 3. Fetch total repairs logged
        cursor.execute(
            "SELECT COALESCE(SUM(repaired_rows), 0), COUNT(repair_id) FROM repair_logs WHERE upload_id = ?;",
            (upload_id,)
        )
        total_repaired, repair_actions_count = cursor.fetchone()

        # 4. Calculate health score and repair rate
        total_cells = upload["num_rows"] * upload["num_columns"]
        if total_cells > 0:
            error_rate = min(1.0, total_issues / total_cells)
            health_score = round(max(0.0, (1.0 - error_rate) * 100), 1)
        else:
            health_score = 100.0

        if total_issues > 0:
            repair_progress = round(min(100.0, (total_repaired / total_issues) * 100), 1)
        else:
            repair_progress = 100.0

        status = "Fully Cleaned" if total_repaired >= total_issues and total_issues > 0 else (
            "No Issues Detected" if total_issues == 0 else "Pending Repairs"
        )

        return {
            "upload_id": upload["upload_id"],
            "filename": upload["filename"],
            "upload_time": upload["upload_time"],
            "num_rows": upload["num_rows"],
            "num_columns": upload["num_columns"],
            "total_cells": total_cells,
            "total_issues": total_issues,
            "issue_columns_count": issue_columns_count,
            "total_repaired": total_repaired,
            "repair_actions_count": repair_actions_count,
            "health_score_pct": health_score,
            "repair_progress_pct": repair_progress,
            "status": status,
        }

    except sqlite3.Error as error:
        print(f"[DB ERROR] Error generating dataset summary for Upload #{upload_id}: {error}")
        return None
    finally:
        if conn:
            conn.close()


def display_dataset_summary(upload_id: int, db_path: str = DEFAULT_DB_PATH) -> None:
    """
    Prints a formatted, presentation-ready health card of a dataset to the console.
    """
    summary = get_dataset_summary(upload_id, db_path)
    if not summary:
        print(f"No summary available for Upload #{upload_id}.")
        return

    print("\n" + "=" * 76)
    print(f"             DATA QUALITY HEALTH REPORT (Upload #{summary['upload_id']})")
    print("=" * 76)
    print(f"  Dataset File       : {summary['filename']}")
    print(f"  Upload Timestamp   : {summary['upload_time']}")
    print(f"  Dimensions         : {summary['num_rows']:,} rows x {summary['num_columns']} columns ({summary['total_cells']:,} total cells)")
    print("-" * 76)
    print(f"  Issues Detected    : {summary['total_issues']:,} issue(s) across {summary['issue_columns_count']} column(s)")
    print(f"  Repairs Applied    : {summary['total_repaired']:,} row(s) fixed across {summary['repair_actions_count']} action(s)")
    print(f"  Repair Progress    : {summary['repair_progress_pct']}% completed")
    print(f"  Data Health Score  : {summary['health_score_pct']}% / 100%")
    print(f"  Status             : {summary['status']}")
    print("=" * 76 + "\n")


def delete_upload(upload_id: int, db_path: str = DEFAULT_DB_PATH) -> bool:
    """
    Deletes an upload from the 'uploads' table.

    Because 'ON DELETE CASCADE' is defined on our Foreign Keys,
    SQLite will automatically delete all matching rows from 'quality_issues'
    and 'repair_logs' as well!

    Returns:
      bool: True if an upload was deleted, False if not found or error occurred.
    """
    conn = None
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM uploads WHERE upload_id = ?;", (upload_id,))
        conn.commit()

        if cursor.rowcount > 0:
            print(f"[DB INFO] Upload #{upload_id} and all related issues/repairs were deleted.")
            return True
        else:
            print(f"[DB WARNING] Upload #{upload_id} not found. Nothing deleted.")
            return False

    except sqlite3.Error as error:
        print(f"[DB ERROR] Error deleting Upload #{upload_id}: {error}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()


def export_upload_to_dict(upload_id: int, db_path: str = DEFAULT_DB_PATH) -> dict:
    """
    Exports all details of a dataset (upload info, detected issues, and repair logs)
    into a clean nested dictionary. Perfect for returning as JSON in REST APIs!

    Returns:
      dict: Nested data structure or None if not found.
    """
    summary = get_dataset_summary(upload_id, db_path)
    if not summary:
        return None

    raw_issues = get_quality_issues(upload_id, db_path)
    raw_repairs = get_repair_history(upload_id, db_path)

    # Convert sqlite3.Row objects to standard Python dicts
    issues = [dict(issue) for issue in raw_issues]
    repairs = [dict(repair) for repair in raw_repairs]

    return {
        "summary": summary,
        "issues": issues,
        "repairs": repairs
    }


# ---------------------------------------------------------------------------
# Direct Script Execution (Quick Check)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("Initializing DataFix Database...")
    init_db()
    print("Done! Use 'test_db.py' or 'test_database.py' to run tests.")
