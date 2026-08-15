"""Mine blind review tasks and private oracles from historical fixes."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .diff import Region, parse_old_regions
from .git import GitError, GitRepository


SCHEMA_VERSION = "1.0"
TEST_PATH = re.compile(r"(^|/)(tests?|specs?)(/|$)|(^|[_./-])(test|spec)([_./-]|$)", re.I)


def is_test_path(path: str) -> bool:
    return bool(TEST_PATH.search(path))


def _case_id(repository: Path, fix_commit: str) -> str:
    material = f"{repository.name}\0{fix_commit}".encode()
    return f"rr-{hashlib.sha256(material).hexdigest()[:12]}"


def _file_packet(repository: GitRepository, parent: str, path: str) -> dict[str, Any]:
    content = repository.file_at(parent, path)
    return {
        "path": path,
        "line_count": len(content.splitlines()),
        "content": content,
    }


def mine_case(repo_path: str | Path, fix_revision: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Create a model-safe task and a separate scoring oracle."""

    repository = GitRepository(repo_path)
    fix_commit = repository.resolve_commit(fix_revision)
    parent_commit = repository.parent_of(fix_commit)
    all_regions = parse_old_regions(repository.zero_context_diff(parent_commit, fix_commit))
    changed_files = repository.changed_files(parent_commit, fix_commit)
    test_files = sorted(path for path in changed_files if is_test_path(path))
    regions = [region for region in all_regions if not is_test_path(region.path)]

    if not regions:
        raise GitError("the selected fix has no scorable non-test regions")

    paths = list(dict.fromkeys(region.path for region in regions))
    files: list[dict[str, Any]] = []
    skipped_paths: list[str] = []
    for path in paths:
        try:
            files.append(_file_packet(repository, parent_commit, path))
        except GitError:
            # A newly created file has no buggy-side content to review.
            skipped_paths.append(path)

    scorable_paths = {item["path"] for item in files}
    scorable_regions = [region for region in regions if region.path in scorable_paths]
    if not scorable_regions:
        raise GitError("the selected fix only creates new files; no buggy snapshot can be replayed")

    case_id = _case_id(repository.path, fix_commit)
    task = {
        "schema_version": SCHEMA_VERSION,
        "case_id": case_id,
        "task": "Review the supplied buggy snapshot and report distinct defects.",
        "protocol": {
            "allowed_evidence": "Only the files embedded in this packet.",
            "forbidden_evidence": "Repository history, future commits, and oracle.json.",
            "prediction_schema": {
                "case_id": "string",
                "findings": [
                    {
                        "path": "string",
                        "start_line": "positive integer",
                        "end_line": "positive integer",
                        "message": "string",
                    }
                ],
            },
        },
        "files": files,
    }
    oracle = {
        "schema_version": SCHEMA_VERSION,
        "case_id": case_id,
        "provenance": {
            "repository": repository.path.name,
            "parent_commit": parent_commit,
            "fix_commit": fix_commit,
            "fix_subject": repository.subject(fix_commit),
        },
        "regions": [region.to_dict() for region in scorable_regions],
        "test_evidence": {
            "tests_changed_with_fix": bool(test_files),
            "paths": test_files,
        },
        "limitations": {
            "skipped_paths_without_buggy_snapshot": skipped_paths,
            "ground_truth": "Changed old-side lines are a localization proxy, not proof that every changed line is independently defective.",
        },
    }
    return task, oracle


def write_case(task: dict[str, Any], oracle: dict[str, Any], output: str | Path) -> tuple[Path, Path]:
    directory = Path(output)
    directory.mkdir(parents=True, exist_ok=True)
    task_path = directory / "task.json"
    oracle_path = directory / "oracle.json"
    task_path.write_text(json.dumps(task, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    oracle_path.write_text(json.dumps(oracle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return task_path, oracle_path
