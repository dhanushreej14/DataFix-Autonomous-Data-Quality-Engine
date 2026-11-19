"""
Unit tests for Batch 2: Anomaly Detection & Inconsistency Detection
"""

import io
import json
import unittest
import pandas as pd

from anomaly_detector import detect_anomalies
from inconsistency_detector import detect_inconsistencies


class TestBatch2Detectors(unittest.TestCase):

    def setUp(self):
        # Sample dataset featuring anomalies and inconsistencies
        self.csv_data = """id,age,salary,join_date,department
1,25,50000,2021-01-15,Engineering
2,30,55000,2020/05/20,engineering
3,28,52000,10-12-2019, Engineering 
4,-5,60000,2018-03-01,Marketing
5,250,9999999,invalid_date,Marketing
6,32,unknown,2022-07-10,Sales
"""

    def test_anomaly_detection(self):
        buffer = io.StringIO(self.csv_data)
        res = detect_anomalies(buffer)

        self.assertEqual(res["status"], "success")
        self.assertGreater(res["anomalies_count"], 0)

        # Flagged anomalies should have reasons
        first_anomaly = res["anomalous_records"][0]
        self.assertIn("reasons", first_anomaly)
        self.assertGreater(len(first_anomaly["reasons"]), 0)
        self.assertIn("anomaly_score", first_anomaly)

        # Verify JSON serializability
        try:
            serialized = json.dumps(res)
            self.assertIsInstance(serialized, str)
        except TypeError as e:
            self.fail(f"Anomaly detector result is not JSON serializable: {e}")

    def test_inconsistency_detection(self):
        buffer = io.StringIO(self.csv_data)
        res = detect_inconsistencies(buffer)

        self.assertEqual(res["status"], "success")
        self.assertGreater(res["inconsistencies_count"], 0)

        # 1. Date format inconsistency
        date_issues = res["date_inconsistencies"]
        self.assertGreater(len(date_issues), 0)
        self.assertEqual(date_issues[0]["column"], "join_date")

        # 2. Categorical casing/whitespace
        cat_issues = res["categorical_inconsistencies"]
        self.assertGreater(len(cat_issues), 0)
        self.assertEqual(cat_issues[0]["column"], "department")

        # 3. Type pollution ('unknown' in salary)
        type_issues = res["type_inconsistencies"]
        self.assertGreater(len(type_issues), 0)
        self.assertEqual(type_issues[0]["column"], "salary")

        # 4. Suspicious values (negative age -5, implausible age 250)
        susp_issues = res["suspicious_values"]
        self.assertGreater(len(susp_issues), 0)
        self.assertEqual(susp_issues[0]["column"], "age")

        # Verify JSON serializability
        try:
            serialized = json.dumps(res)
            self.assertIsInstance(serialized, str)
        except TypeError as e:
            self.fail(f"Inconsistency detector result is not JSON serializable: {e}")


if __name__ == "__main__":
    unittest.main()
