"""
test_database.py
----------------
Test script for the DataFix Database Module.

This script tests all required database functions in 6 simple steps:
1. Initialize the database.
2. Insert one sample upload.
3. Insert sample quality issues.
4. Insert a repair record.
5. Display upload history.
6. Display repair history.
"""

import os
import sys

# Ensure Python can find the database module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.db import (
    init_db,
    save_upload_details,
    save_quality_issue,
    save_repair_history,
    display_upload_history,
    display_repair_history,
    display_dataset_summary,
    export_upload_to_dict,
)


def main():
    print("=" * 65)
    print("             DATAFIX DATABASE MODULE TEST")
    print("=" * 65)

    # -------------------------------------------------------------
    # Step 1: Initialize database
    # -------------------------------------------------------------
    print("\n--- Step 1: Initializing Database ---")
    init_db()

    # -------------------------------------------------------------
    # Step 2: Insert one sample upload
    # -------------------------------------------------------------
    print("\n--- Step 2: Inserting One Sample Upload ---")
    upload_id = save_upload_details(
        filename="employees_dataset.csv",
        num_rows=1200,
        num_columns=8
    )
    print(f"Sample file recorded! Generated Upload ID: {upload_id}")

    # -------------------------------------------------------------
    # Step 3: Insert sample quality issues
    # -------------------------------------------------------------
    print("\n--- Step 3: Inserting Sample Quality Issues ---")
    save_quality_issue(
        upload_id=upload_id,
        column_name="salary",
        issue_type="Missing Values",
        num_issues=15
    )
    save_quality_issue(
        upload_id=upload_id,
        column_name="email",
        issue_type="Invalid Format",
        num_issues=8
    )
    print("Quality issues logged successfully!")

    # -------------------------------------------------------------
    # Step 4: Insert a repair record
    # -------------------------------------------------------------
    print("\n--- Step 4: Inserting a Repair Record ---")
    save_repair_history(
        upload_id=upload_id,
        column_name="salary",
        repair_type="Imputed with Median Salary",
        repaired_rows=15
    )
    print("Repair record logged successfully!")

    # -------------------------------------------------------------
    # Step 5: Display upload history
    # -------------------------------------------------------------
    print("\n--- Step 5: Display Upload History ---")
    display_upload_history()

    # -------------------------------------------------------------
    # Step 6: Display repair history
    # -------------------------------------------------------------
    print("--- Step 6: Display Repair History ---")
    display_repair_history()

    # -------------------------------------------------------------
    # Step 7: Display Dataset Health Summary Card
    # -------------------------------------------------------------
    print("--- Step 7: Display Dataset Health Summary Card ---")
    display_dataset_summary(upload_id)

    # -------------------------------------------------------------
    # Step 8: Export Complete Data as Dictionary (API-ready JSON)
    # -------------------------------------------------------------
    print("--- Step 8: Export Dataset to Nested Dictionary ---")
    exported = export_upload_to_dict(upload_id)
    print(f"Exported successfully! Keys: {list(exported.keys())}")
    print(f"Health Score: {exported['summary']['health_score_pct']}%")

    print("\n" + "=" * 65)
    print("       ALL DATABASE TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 65)


if __name__ == "__main__":
    main()
