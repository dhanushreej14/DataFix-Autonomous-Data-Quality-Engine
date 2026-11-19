"""
Unit tests for Batch 3: Quality Score & Correction Engine
"""

import io
import json
import unittest
import pandas as pd

from profiler import profile_dataset
from missing_values import detect_missing_values
from duplicate_detector import detect_duplicates
from anomaly_detector import detect_anomalies
from inconsistency_detector import detect_inconsistencies
from quality_score import calculate_quality_score
from correction_engine import generate_correction_suggestions, clean_dataset


class TestBatch3Engines(unittest.TestCase):

    def setUp(self):
        self.raw_csv = """id,name,age,salary,join_date,dept
101,Alice,25,50000,2021-01-15,Engineering
102,Bob,-5,60000,2020/05/20,engineering
103,Charlie,35,unknown,15-08-2019, Engineering 
101,Alice,25,50000,2021-01-15,Engineering
"""
        self.df_original = pd.read_csv(io.StringIO(self.raw_csv))

    def test_quality_score_calculation(self):
        df_copy = self.df_original.copy()
        prof = profile_dataset(df_copy)
        miss = detect_missing_values(df_copy)
        dups = detect_duplicates(df_copy)
        anom = detect_anomalies(df_copy)
        inc = detect_inconsistencies(df_copy)

        score_res = calculate_quality_score(prof, miss, dups, anom, inc)

        self.assertEqual(score_res["status"], "success")
        self.assertIsInstance(score_res["overall_score"], float)
        self.assertGreaterEqual(score_res["overall_score"], 0.0)
        self.assertLessEqual(score_res["overall_score"], 100.0)
        self.assertIn("pillars", score_res)
        self.assertIn("deductions", score_res)

        # JSON serializable test
        try:
            serialized = json.dumps(score_res)
            self.assertIsInstance(serialized, str)
        except TypeError as e:
            self.fail(f"Quality score result is not JSON serializable: {e}")

    def test_correction_engine_non_destructive(self):
        # Verify original dataset is NOT modified
        original_copy = self.df_original.copy(deep=True)
        clean_res = clean_dataset(self.df_original, return_format="dataframe")

        self.assertEqual(clean_res["status"], "success")
        cleaned_df = clean_res["cleaned_dataframe"]

        # Ensure original DataFrame remains strictly identical
        pd.testing.assert_frame_equal(self.df_original, original_copy)

        # Ensure duplicate row was dropped in the cleaned output
        self.assertEqual(len(cleaned_df), 3)

        # Ensure whitespace and casing standardized in dept
        self.assertTrue((cleaned_df["dept"] == "Engineering").all())

        # Ensure negative age was rectified
        self.assertTrue((cleaned_df["age"] >= 0).all())

        # Test CSV export format
        csv_res = clean_dataset(self.df_original, return_format="csv")
        self.assertIn("cleaned_csv", csv_res)
        self.assertIn("Alice", csv_res["cleaned_csv"])

    def test_generate_correction_suggestions(self):
        df_copy = self.df_original.copy()
        prof = profile_dataset(df_copy)
        miss = detect_missing_values(df_copy)
        dups = detect_duplicates(df_copy)
        anom = detect_anomalies(df_copy)
        inc = detect_inconsistencies(df_copy)

        suggestions = generate_correction_suggestions(prof, miss, dups, anom, inc)
        self.assertIsInstance(suggestions, list)
        self.assertGreater(len(suggestions), 0)
        self.assertIn("action_id", suggestions[0])
        self.assertIn("title", suggestions[0])


if __name__ == "__main__":
    unittest.main()
