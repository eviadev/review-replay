"""Small, local-only Git adapter with no shell interpolation."""

from __future__ import annotations

import subprocess
from pathlib import Path


class GitError(RuntimeError):
    """Raised when Git cannot provide the requested evidence."""


class GitRepository:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).resolve()
        if not self.path.is_dir():
            raise GitError(f"repository does not exist: {self.path}")
        self.run("rev-parse", "--git-dir")

    def run(self, *args: str) -> str:
        command = ["git", "-C", str(self.path), *args]
        try:
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except subprocess.CalledProcessError as exc:
            message = (exc.stderr or exc.stdout or "Git command failed").strip()
            raise GitError(message) from exc
        return result.stdout

    def resolve_commit(self, revision: str) -> str:
        return self.run("rev-parse", "--verify", f"{revision}^{{commit}}").strip()

    def parent_of(self, commit: str) -> str:
        lineage = self.run("rev-list", "--parents", "-n", "1", commit).strip().split()
        if len(lineage) != 2:
            raise GitError("the fix commit must have exactly one inspectable parent")
        return lineage[1]

    def subject(self, commit: str) -> str:
        return self.run("show", "-s", "--format=%s", commit).strip()

    def zero_context_diff(self, parent: str, commit: str) -> str:
        return self.run(
            "diff",
            "--no-ext-diff",
            "--no-color",
            "--find-renames",
            "--unified=0",
            parent,
            commit,
            "--",
        )

    def changed_files(self, parent: str, commit: str) -> list[str]:
        output = self.run("diff", "--name-only", "-z", parent, commit, "--")
        return [item for item in output.split("\0") if item]

    def file_at(self, commit: str, path: str) -> str:
        return self.run("show", f"{commit}:{path}")
