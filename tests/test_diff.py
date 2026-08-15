from __future__ import annotations

import unittest

from review_replay.diff import parse_old_regions


class DiffParserTests(unittest.TestCase):
    def test_parses_modified_deleted_and_missing_regions(self) -> None:
        patch = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -4,2 +4,2 @@
-old
-old
+new
+new
@@ -12,1 +11,0 @@
-gone
@@ -20,0 +20,2 @@
+missing
+behavior
"""
        regions = parse_old_regions(patch)

        self.assertEqual(
            [(item.start_line, item.end_line, item.change_type) for item in regions],
            [(4, 5, "modified"), (12, 12, "deleted"), (20, 20, "missing")],
        )
        self.assertEqual([item.id for item in regions], ["R001", "R002", "R003"])

    def test_parses_quoted_paths(self) -> None:
        patch = '''diff --git "a/a file.py" "b/a file.py"
--- "a/a file.py"
+++ "b/a file.py"
@@ -2 +2 @@
-broken
+fixed
'''
        self.assertEqual(parse_old_regions(patch)[0].path, "a file.py")


if __name__ == "__main__":
    unittest.main()
