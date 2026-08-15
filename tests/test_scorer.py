from __future__ import annotations

import unittest
import json
import tempfile
from pathlib import Path

from review_replay.scorer import PredictionError, score_predictions, score_suite


class ScorerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.oracle = {
            "case_id": "rr-demo",
            "regions": [
                {"id": "R001", "path": "app.py", "start_line": 10, "end_line": 12},
                {"id": "R002", "path": "app.py", "start_line": 30, "end_line": 30},
            ],
        }

    def test_scores_one_to_one_and_reports_failures(self) -> None:
        predictions = {
            "case_id": "rr-demo",
            "findings": [
                {"path": "app.py", "start_line": 11, "end_line": 11, "message": "bug"},
                {"path": "app.py", "start_line": 11, "end_line": 11, "message": "duplicate"},
            ],
        }

        result = score_predictions(self.oracle, predictions)

        self.assertEqual(result["metrics"]["precision"], 0.5)
        self.assertEqual(result["metrics"]["recall"], 0.5)
        self.assertEqual(result["metrics"]["f1"], 0.5)
        self.assertEqual(len(result["false_positives"]), 1)
        self.assertEqual(result["missed_regions"][0]["id"], "R002")

    def test_tolerance_allows_nearby_localization(self) -> None:
        predictions = {
            "case_id": "rr-demo",
            "findings": [
                {"path": "app.py", "start_line": 8, "end_line": 8, "message": "nearby"}
            ],
        }
        self.assertEqual(score_predictions(self.oracle, predictions, tolerance=2)["metrics"]["matched"], 1)

    def test_rejects_cross_case_predictions(self) -> None:
        with self.assertRaises(PredictionError):
            score_predictions(self.oracle, {"case_id": "other", "findings": []})

    def test_aggregates_suite_and_reports_missing_cases(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cases = root / "cases"
            predictions = root / "predictions"
            (cases / "one").mkdir(parents=True)
            (cases / "two").mkdir(parents=True)
            predictions.mkdir()
            (cases / "one" / "oracle.json").write_text(json.dumps(self.oracle), encoding="utf-8")
            missing_oracle = {**self.oracle, "case_id": "rr-missing"}
            (cases / "two" / "oracle.json").write_text(
                json.dumps(missing_oracle), encoding="utf-8"
            )
            prediction = {
                "case_id": "rr-demo",
                "findings": [
                    {"path": "app.py", "start_line": 10, "end_line": 10, "message": "bug"}
                ],
            }
            (predictions / "rr-demo.json").write_text(json.dumps(prediction), encoding="utf-8")

            result = score_suite(cases, predictions)

            self.assertEqual(result["metrics"]["cases_scored"], 1)
            self.assertEqual(result["metrics"]["cases_discovered"], 2)
            self.assertEqual(result["metrics"]["micro_precision"], 1.0)
            self.assertEqual(result["metrics"]["micro_recall"], 0.5)
            self.assertEqual(result["missing_predictions"], ["rr-missing"])


if __name__ == "__main__":
    unittest.main()
