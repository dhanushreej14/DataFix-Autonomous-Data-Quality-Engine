"""
Unit tests for Batch 1: Missing Value & Duplicate Detectors
"""

import io
import json
import unittest
import pandas as pd

from missing_values import detect_missing_values
from duplicate_detector import detect_duplicates


class TestBatch1Auditors(unittest.TestCase):

    def setUp(self):
        self.csv_data = """id,name,age,salary,city
1,Alice,25,50000,New York
2,Bob,30,,London
3,Charlie,,75000,Paris
4,Diana,40,90000,N/A
5,Alice,25,50000,New York
6,alice ,25,50000,new york
"""

    def test_missing_values_detection(self):
        buffer = io.StringIO(self.csv_data)
        res = detect_missing_values(buffer)

        self.assertEqual(res["status"], "success")
        self.assertGreater(res["total_missing_cells"], 0)
        self.assertIn("salary", res["affected_columns"])
        self.assertIn("age", res["affected_columns"])
        self.assertIn("city", res["affected_columns"])

        # Check strategy recommendation for numeric
        age_col = res["columns"]["age"]
        self.assertIn(age_col["recommended_strategy"], ["impute_median", "impute_mean"])

        # Verify JSON serializability
        try:
            serialized = json.dumps(res)
            self.assertIsInstance(serialized, str)
        except TypeError as e:
            self.fail(f"Missing values result is not JSON serializable: {e}")

    def test_duplicate_detection(self):
        buffer = io.StringIO(self.csv_data)
        res = detect_duplicates(buffer)

        self.assertEqual(res["status"], "success")
        # Row 0 and Row 4 are exact duplicates (id=1 and id=5 or id=1 and id=1? row 4 is Alice with id=1 or 5?)
        # in csv_data: row 0 has id 1, row 4 has id 5 (different id!).
        # But wait! Let's check row 4 in csv_data: "5,Alice,25,50000,New York"
        # It matches row 0 on (name, age, salary, city) ignoring ID, so it is a subset match!
        # And row 5: "6,alice ,25,50000,new york" matches row 0 with casing/whitespace!
        self.assertGreater(len(res["potential_duplicate_groups"]), 0)

        # Check exact duplicate with identical rows
        identical_csv = io.StringIO("a,b\n1,x\n2,y\n1,x\n")
        exact_res = detect_duplicates(identical_csv)
        self.assertEqual(exact_res["exact_duplicates_count"], 1)
        self.assertEqual(exact_res["exact_duplicate_indices"], [2])

        # Verify JSON serializability
        try:
            serialized = json.dumps(res)
            self.assertIsInstance(serialized, str)
        except TypeError as e:
            self.fail(f"Duplicate detector result is not JSON serializable: {e}")

    def test_empty_inputs(self):
        empty_csv = io.StringIO("")
        res_m = detect_missing_values(empty_csv)
        self.assertEqual(res_m["status"], "error")

        empty_csv2 = io.StringIO("")
        res_d = detect_duplicates(empty_csv2)
        self.assertEqual(res_d["status"], "error")


if __name__ == "__main__":
    unittest.main()
