"""
Unit tests and verification for Data Quality Profiler (profiler.py)
"""

import io
import json
import os
import unittest
import pandas as pd
from profiler import profile_dataset, infer_column_type, load_dataset


class TestDataQualityProfiler(unittest.TestCase):

    def setUp(self):
        # Create a sample dirty CSV dataset
        self.sample_csv_content = """id,name,age,salary,join_date,department,is_active
101,Alice Smith,28,75000.50,2021-04-12,Engineering,True
102,Bob Jones,34,,2020-01-15,Marketing,False
103,Charlie Brown,,82000.00,2019-11-23,Engineering,True
104,Diana Prince,45,120000.00,2018-07-01,Executive,True
105,Evan Wright,29,62000.00,2022-03-30,,False
101,Alice Smith,28,75000.50,2021-04-12,Engineering,True
"""
        self.csv_buffer = io.StringIO(self.sample_csv_content)

    def test_profiling_valid_dataset(self):
        result = profile_dataset(self.csv_buffer)

        # Basic validations
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["rows"], 6)
        self.assertEqual(result["columns"], 7)
        self.assertIn("salary", result["column_names"])

        # Check duplicate count (row 101 is duplicated once)
        self.assertEqual(result["summary"]["duplicate_rows"], 1)

        # Check missing values
        self.assertGreater(result["summary"]["missing_cells"], 0)

        # Check type inferences
        col_prof = result["columns_profile"]
        self.assertEqual(col_prof["id"]["inferred_type"], "integer")
        self.assertEqual(col_prof["join_date"]["inferred_type"], "datetime")
        self.assertEqual(col_prof["is_active"]["inferred_type"], "boolean")

        # Verify JSON serializability
        try:
            serialized = json.dumps(result)
            self.assertIsInstance(serialized, str)
        except TypeError as e:
            self.fail(f"Profiler result is not JSON serializable: {e}")

    def test_empty_dataset(self):
        empty_csv = io.StringIO("")
        result = profile_dataset(empty_csv)
        self.assertEqual(result["status"], "error")
        self.assertIn("error_message", result)

    def test_nonexistent_file(self):
        result = profile_dataset("non_existent_file_path_12345.csv")
        self.assertEqual(result["status"], "error")
        self.assertIn("error_message", result)

    def test_direct_dataframe_input(self):
        df = pd.DataFrame({
            "col_a": [1, 2, 3, 4],
            "col_b": ["apple", "banana", "apple", "banana"]
        })
        result = profile_dataset(df)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["rows"], 4)
        self.assertEqual(result["columns"], 2)


if __name__ == "__main__":
    unittest.main()
