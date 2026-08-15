from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from review_replay.miner import mine_case, write_case


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


class MinerTests(unittest.TestCase):
    def test_mines_buggy_snapshot_without_leaking_fix_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            git(repo, "init", "-b", "main")
            git(repo, "config", "user.email", "test@example.com")
            git(repo, "config", "user.name", "Test")
            (repo / "price.py").write_text(
                "def total(price, quantity):\n    return price - quantity\n",
                encoding="utf-8",
            )
            (repo / "tests").mkdir()
            (repo / "tests" / "test_price.py").write_text("# missing regression\n", encoding="utf-8")
            git(repo, "add", ".")
            git(repo, "commit", "-m", "feat: calculate totals")

            (repo / "price.py").write_text(
                "def total(price, quantity):\n    return price * quantity\n",
                encoding="utf-8",
            )
            (repo / "tests" / "test_price.py").write_text(
                "from price import total\n\nassert total(4, 3) == 12\n",
                encoding="utf-8",
            )
            git(repo, "add", ".")
            git(repo, "commit", "-m", "fix: multiply price by quantity")
            fix = git(repo, "rev-parse", "HEAD")

            task, oracle = mine_case(repo, fix)

            self.assertNotIn("fix_commit", str(task))
            self.assertIn("return price - quantity", task["files"][0]["content"])
            self.assertEqual(oracle["regions"][0]["path"], "price.py")
            self.assertEqual(oracle["regions"][0]["start_line"], 2)
            self.assertTrue(oracle["test_evidence"]["tests_changed_with_fix"])
            self.assertEqual(oracle["test_evidence"]["paths"], ["tests/test_price.py"])

            task_path, oracle_path = write_case(task, oracle, repo / "case")
            self.assertTrue(task_path.is_file())
            self.assertTrue(oracle_path.is_file())


if __name__ == "__main__":
    unittest.main()
