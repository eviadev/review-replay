"""Parse the old-side locations of a zero-context unified diff."""

from __future__ import annotations

import re
import shlex
from dataclasses import asdict, dataclass


HUNK = re.compile(
    r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? "
    r"\+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@"
)


@dataclass(frozen=True)
class Region:
    id: str
    path: str
    start_line: int
    end_line: int
    change_type: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _path_from_marker(line: str) -> str | None:
    payload = line[4:].split("\t", 1)[0]
    parts = shlex.split(payload)
    value = parts[0] if parts else payload
    if value == "/dev/null":
        return None
    if value.startswith(("a/", "b/")):
        value = value[2:]
    return value


def parse_old_regions(diff: str) -> list[Region]:
    """Return regions in the buggy (old) snapshot changed by the fix."""

    regions: list[Region] = []
    old_path: str | None = None
    new_path: str | None = None

    for line in diff.splitlines():
        if line.startswith("diff --git "):
            parts = shlex.split(line[len("diff --git ") :])
            old_path = parts[0][2:] if parts and parts[0].startswith("a/") else None
            new_path = parts[1][2:] if len(parts) > 1 and parts[1].startswith("b/") else None
            continue
        if line.startswith("--- "):
            old_path = _path_from_marker(line)
            continue
        if line.startswith("+++ "):
            new_path = _path_from_marker(line)
            continue

        match = HUNK.match(line)
        if not match:
            continue

        old_start = int(match.group("old_start"))
        old_count = int(match.group("old_count") or "1")
        new_count = int(match.group("new_count") or "1")
        path = old_path or new_path
        if path is None:
            continue

        if old_count == 0:
            start = end = max(1, old_start)
            change_type = "missing"
        else:
            start = max(1, old_start)
            end = start + old_count - 1
            change_type = "deleted" if new_count == 0 else "modified"

        regions.append(
            Region(
                id=f"R{len(regions) + 1:03d}",
                path=path,
                start_line=start,
                end_line=end,
                change_type=change_type,
            )
        )

    return regions
