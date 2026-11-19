"""
End-to-End Integration Tests for DataFix AI Engine (main.py)
"""

import io
import json
import unittest
from pathlib import Path
import pandas as pd

from main import analyze_dataset, clean_dataset, DataQualityEngine


class TestDataFixIntegration(unittest.TestCase):

    def setUp(self):
        self.csv_path = Path(__file__).parent / "sample_test.csv"

    def test_full_pipeline_analysis(self):
        report = analyze_dataset(self.csv_path)

        self.assertEqual(report["status"], "success")
        self.assertIn("quality_score", report)
        self.assertIn("profiling", report)
        self.assertIn("missing_values", report)
        self.assertIn("duplicates", report)
        self.assertIn("anomalies", report)
        self.assertIn("inconsistencies", report)
        self.assertIn("correction_suggestions", report)

        # Ensure quality score is a valid float
        score = report["quality_score"]["overall_score"]
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 100.0)

        # Ensure 100% JSON-serializable
        try:
            dumped = json.dumps(report)
            self.assertIsInstance(dumped, str)
        except TypeError as e:
            self.fail(f"Integration report failed JSON serialization: {e}")

    def test_engine_class_interface(self):
        engine = DataQualityEngine()
        report = engine.analyze(self.csv_path)
        self.assertEqual(report["status"], "success")

        clean_res = engine.clean(self.csv_path, return_format="dataframe")
        self.assertEqual(clean_res["status"], "success")
        self.assertIsInstance(clean_res["cleaned_dataframe"], pd.DataFrame)
        self.assertGreater(clean_res["total_transformations_count"], 0)

    def test_invalid_csv_handling(self):
        empty_stream = io.StringIO("")
        report = analyze_dataset(empty_stream)
        self.assertEqual(report["status"], "error")
        self.assertIn("error_message", report)


if __name__ == "__main__":
    unittest.main()
