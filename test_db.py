"""
Test Script for DataFix Database Module
---------------------------------------
This script tests and demonstrates all database functionality:
1. Initializing tables
2. Storing uploaded dataset details
3. Storing detected quality issues
4. Storing repair logs
5. Displaying upload and repair history
6. Proving Foreign Key constraint enforcement
7. Demonstrating error handling
"""

import sys
import os
import sqlite3

# Ensure Python can import from the project root
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.db import (
    init_db,
    save_upload_details,
    save_quality_issue,
    save_repair_history,
    display_upload_history,
    display_repair_history,
    get_quality_issues,
    get_connection,
    DEFAULT_DB_PATH,
)


def run_all_tests():
    print("=" * 70)
    print("      STARTING DATAFIX DATABASE VERIFICATION TESTS")
    print("=" * 70)

    # -----------------------------------------------------------------------
    # TEST 1: Initialize the Database
    # -----------------------------------------------------------------------
    print("\n[TEST 1] Initializing database tables...")
    success = init_db()
    assert success is True, "Database initialization failed!"
    print(">>> PASS: Database and all 3 tables created successfully.")

    # -----------------------------------------------------------------------
    # TEST 2: Save Upload Details
    # -----------------------------------------------------------------------
    print("\n[TEST 2] Saving uploaded dataset details...")
    upload_id_1 = save_upload_details(
        filename="customer_churn_dataset.csv",
        num_rows=1500,
        num_columns=14
    )
    assert upload_id_1 is not None and upload_id_1 > 0, "Failed to insert first upload!"

    upload_id_2 = save_upload_details(
        filename="hospital_patient_records.csv",
        num_rows=8420,
        num_columns=22
    )
    assert upload_id_2 is not None and upload_id_2 > 0, "Failed to insert second upload!"

    print(f">>> PASS: Uploads inserted successfully with IDs {upload_id_1} and {upload_id_2}.")

    # -----------------------------------------------------------------------
    # TEST 3: Save Quality Issues
    # -----------------------------------------------------------------------
    print("\n[TEST 3] Saving quality issues for Upload #1...")
    issue_1 = save_quality_issue(
        upload_id=upload_id_1,
        column_name="email",
        issue_type="Missing Values",
        num_issues=85
    )
    issue_2 = save_quality_issue(
        upload_id=upload_id_1,
        column_name="phone_number",
        issue_type="Invalid Format",
        num_issues=34
    )
    issue_3 = save_quality_issue(
        upload_id=upload_id_1,
        column_name="customer_id",
        issue_type="Duplicate Rows",
        num_issues=12
    )
    assert all([issue_1, issue_2, issue_3]), "Failed to record quality issues!"

    # Also save one issue for upload 2
    save_quality_issue(
        upload_id=upload_id_2,
        column_name="patient_age",
        issue_type="Out of Range",
        num_issues=7
    )
    print(">>> PASS: Quality issues successfully linked to uploads.")

    # -----------------------------------------------------------------------
    # TEST 4: Save Repair History
    # -----------------------------------------------------------------------
    print("\n[TEST 4] Saving repair history logs...")
    repair_1 = save_repair_history(
        upload_id=upload_id_1,
        column_name="email",
        repair_type="Imputed Default / Placeholder",
        repaired_rows=85
    )
    repair_2 = save_repair_history(
        upload_id=upload_id_1,
        column_name="customer_id",
        repair_type="Removed Duplicate Rows",
        repaired_rows=12
    )
    repair_3 = save_repair_history(
        upload_id=upload_id_2,
        column_name="patient_age",
        repair_type="Capped at Maximum (100)",
        repaired_rows=7
    )
    assert all([repair_1, repair_2, repair_3]), "Failed to record repair logs!"
    print(">>> PASS: Repair logs successfully saved.")

    # -----------------------------------------------------------------------
    # TEST 5: Display Upload History
    # -----------------------------------------------------------------------
    print("\n[TEST 5] Testing display_upload_history():")
    display_upload_history()

    # -----------------------------------------------------------------------
    # TEST 6: Display Repair History
    # -----------------------------------------------------------------------
    print("\n[TEST 6] Testing display_repair_history():")
    display_repair_history()

    print("\nTesting display_repair_history() filtered by Upload ID 1:")
    display_repair_history(upload_id=upload_id_1)

    # -----------------------------------------------------------------------
    # TEST 7: Foreign Key Enforcement Test
    # -----------------------------------------------------------------------
    print("\n[TEST 7] Verifying Foreign Key constraint enforcement...")
    print("Attempting to insert a quality issue with non-existent upload_id=999999...")

    # We expect this to fail with an IntegrityError because upload_id 999999 does not exist
    invalid_id = save_quality_issue(
        upload_id=999999,
        column_name="fake_col",
        issue_type="Missing Values",
        num_issues=10
    )

    if invalid_id is None:
        print(">>> PASS: Foreign key constraint successfully prevented orphan record!")
    else:
        print(">>> FAIL: Foreign key constraint was NOT enforced!")
        sys.exit(1)

    # -----------------------------------------------------------------------
    # TEST 8: Verify Querying Quality Issues
    # -----------------------------------------------------------------------
    print("\n[TEST 8] Verifying get_quality_issues() function...")
    issues = get_quality_issues(upload_id=upload_id_1)
    print(f"Found {len(issues)} quality issues recorded for Upload #{upload_id_1}:")
    for iss in issues:
        print(f"  - Column '{iss['column_name']}': {iss['num_issues']} issues ({iss['issue_type']})")
    assert len(issues) == 3, f"Expected 3 issues, but found {len(issues)}"
    print(">>> PASS: Quality issues query returned expected records.")

    print("\n" + "=" * 70)
    print("       ALL DATABASE TESTS COMPLETED SUCCESSFULLY! (8/8 PASSED)")
    print("=" * 70)


if __name__ == "__main__":
    run_all_tests()
