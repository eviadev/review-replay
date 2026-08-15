"""Command-line interface for mining and scoring ReviewReplay cases."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .git import GitError
from .miner import mine_case, write_case
from .scorer import PredictionError, score_predictions, score_suite


def _load_json(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PredictionError(f"expected a JSON object in {path}")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="review-replay",
        description="Build and score blind code-review cases from historical bug fixes.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    mine = subcommands.add_parser("mine", help="mine one fix commit into task.json and oracle.json")
    mine.add_argument("--repo", required=True, help="path to a local Git repository")
    mine.add_argument("--fix", required=True, help="bug-fix commit or revision")
    mine.add_argument("--output", required=True, help="output directory")

    score = subcommands.add_parser("score", help="score a prediction packet")
    score.add_argument("--oracle", required=True)
    score.add_argument("--predictions", required=True)
    score.add_argument("--tolerance", type=int, default=0)
    score.add_argument("--json", action="store_true", dest="as_json")

    suite = subcommands.add_parser("score-suite", help="aggregate a directory of replay cases")
    suite.add_argument("--cases", required=True, help="directory containing oracle.json files")
    suite.add_argument(
        "--predictions",
        required=True,
        help="directory containing <case-id>.json prediction files",
    )
    suite.add_argument("--tolerance", type=int, default=0)
    suite.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "mine":
            task, oracle = mine_case(args.repo, args.fix)
            task_path, oracle_path = write_case(task, oracle, args.output)
            print(f"case: {task['case_id']}")
            print(f"task: {task_path}")
            print(f"oracle: {oracle_path}")
            print(f"scorable regions: {len(oracle['regions'])}")
            return 0

        if args.command == "score":
            oracle = _load_json(args.oracle)
            predictions = _load_json(args.predictions)
            result = score_predictions(oracle, predictions, args.tolerance)
        else:
            result = score_suite(args.cases, args.predictions, args.tolerance)
        if args.as_json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            metrics = result["metrics"]
            if args.command == "score":
                print(
                    f"precision={metrics['precision']:.4f} "
                    f"recall={metrics['recall']:.4f} f1={metrics['f1']:.4f}"
                )
                print(
                    f"matched={metrics['matched']}/{metrics['regions']} "
                    f"false_positives={len(result['false_positives'])}"
                )
            else:
                print(
                    f"micro_precision={metrics['micro_precision']:.4f} "
                    f"micro_recall={metrics['micro_recall']:.4f} "
                    f"micro_f1={metrics['micro_f1']:.4f} "
                    f"macro_f1={metrics['macro_f1']:.4f}"
                )
                print(
                    f"cases={metrics['cases_scored']}/{metrics['cases_discovered']} "
                    f"missing={len(result['missing_predictions'])}"
                )
        return 0
    except (GitError, PredictionError, json.JSONDecodeError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
