"""Deterministic, one-to-one localization scoring."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class PredictionError(ValueError):
    """Raised when a prediction packet is malformed."""


def _interval(item: dict[str, Any]) -> tuple[int, int]:
    try:
        start = int(item["start_line"])
        end = int(item.get("end_line", start))
    except (KeyError, TypeError, ValueError) as exc:
        raise PredictionError("each finding needs integer start_line and end_line") from exc
    if start < 1 or end < start:
        raise PredictionError("finding lines must satisfy 1 <= start_line <= end_line")
    return start, end


def _overlap(left: tuple[int, int], right: tuple[int, int], tolerance: int) -> int:
    start = max(left[0], right[0] - tolerance)
    end = min(left[1], right[1] + tolerance)
    return max(0, end - start + 1)


def score_predictions(
    oracle: dict[str, Any], predictions: dict[str, Any], tolerance: int = 0
) -> dict[str, Any]:
    if tolerance < 0:
        raise PredictionError("tolerance cannot be negative")
    if predictions.get("case_id") != oracle.get("case_id"):
        raise PredictionError("prediction case_id does not match the oracle")

    regions = oracle.get("regions")
    findings = predictions.get("findings")
    if not isinstance(regions, list) or not regions:
        raise PredictionError("oracle contains no regions")
    if not isinstance(findings, list):
        raise PredictionError("predictions.findings must be a list")

    unmatched = set(range(len(regions)))
    matches: list[dict[str, Any]] = []
    false_positives: list[dict[str, Any]] = []

    for prediction_index, finding in enumerate(findings):
        if not isinstance(finding, dict) or not isinstance(finding.get("path"), str):
            raise PredictionError("each finding needs a string path")
        predicted_interval = _interval(finding)
        candidates: list[tuple[int, int]] = []
        for region_index in unmatched:
            region = regions[region_index]
            if finding["path"] != region["path"]:
                continue
            amount = _overlap(
                predicted_interval,
                (int(region["start_line"]), int(region["end_line"])),
                tolerance,
            )
            if amount:
                candidates.append((amount, region_index))

        if not candidates:
            false_positives.append({"prediction_index": prediction_index, "finding": finding})
            continue

        _, region_index = max(candidates)
        unmatched.remove(region_index)
        matches.append(
            {
                "prediction_index": prediction_index,
                "region_id": regions[region_index]["id"],
            }
        )

    matched = len(matches)
    precision = matched / len(findings) if findings else 0.0
    recall = matched / len(regions)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "schema_version": "1.0",
        "case_id": oracle["case_id"],
        "metrics": {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "matched": matched,
            "predictions": len(findings),
            "regions": len(regions),
        },
        "matches": matches,
        "false_positives": false_positives,
        "missed_regions": [regions[index] for index in sorted(unmatched)],
        "tolerance": tolerance,
    }


def score_suite(
    cases_root: str | Path, predictions_root: str | Path, tolerance: int = 0
) -> dict[str, Any]:
    """Score every oracle below cases_root against predictions named by case id."""

    cases_directory = Path(cases_root)
    predictions_directory = Path(predictions_root)
    oracle_paths = sorted(cases_directory.rglob("oracle.json"))
    if not oracle_paths:
        raise PredictionError(f"no oracle.json files found below {cases_directory}")

    case_results: list[dict[str, Any]] = []
    missing_predictions: list[str] = []
    totals = {"matched": 0, "predictions": 0, "regions": 0}

    for oracle_path in oracle_paths:
        oracle = json.loads(oracle_path.read_text(encoding="utf-8"))
        if not isinstance(oracle, dict) or not isinstance(oracle.get("case_id"), str):
            raise PredictionError(f"invalid oracle: {oracle_path}")
        prediction_path = predictions_directory / f"{oracle['case_id']}.json"
        if not prediction_path.is_file():
            missing_predictions.append(oracle["case_id"])
            continue
        predictions = json.loads(prediction_path.read_text(encoding="utf-8"))
        if not isinstance(predictions, dict):
            raise PredictionError(f"invalid predictions: {prediction_path}")
        result = score_predictions(oracle, predictions, tolerance)
        case_results.append(result)
        for key in totals:
            totals[key] += int(result["metrics"][key])

    precision = totals["matched"] / totals["predictions"] if totals["predictions"] else 0.0
    recall = totals["matched"] / totals["regions"] if totals["regions"] else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    macro_f1 = (
        sum(float(case["metrics"]["f1"]) for case in case_results) / len(case_results)
        if case_results
        else 0.0
    )
    return {
        "schema_version": "1.0",
        "metrics": {
            "micro_precision": round(precision, 4),
            "micro_recall": round(recall, 4),
            "micro_f1": round(f1, 4),
            "macro_f1": round(macro_f1, 4),
            **totals,
            "cases_scored": len(case_results),
            "cases_discovered": len(oracle_paths),
        },
        "missing_predictions": missing_predictions,
        "cases": case_results,
        "tolerance": tolerance,
    }
