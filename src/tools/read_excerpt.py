"""Read bounded code excerpts. Whole files are never returned/persisted."""
from __future__ import annotations

import os

# Hard caps keep prompts small and guarantee raw whole-files never leave the box.
_MAX_LINES = 400
_MAX_CHARS = 24_000


def read_excerpt(base_path: str, rel_file: str, start: int = 1, end: int | None = None) -> str:
    """Read lines [start, end] (1-indexed, inclusive) from a file, bounded."""
    abs_path = os.path.join(base_path, rel_file)
    with open(abs_path, "r", encoding="utf-8", errors="replace") as fh:
        lines = fh.readlines()

    start = max(1, start)
    if end is None:
        end = start + _MAX_LINES - 1
    end = min(end, start + _MAX_LINES - 1, len(lines))

    numbered = []
    for i in range(start - 1, end):
        numbered.append(f"{i + 1}: {lines[i].rstrip(chr(10))}")
    excerpt = "\n".join(numbered)
    return excerpt[:_MAX_CHARS]


def read_head(base_path: str, rel_file: str, max_lines: int = _MAX_LINES) -> str:
    """Bounded read of the top of a file (for scanning)."""
    return read_excerpt(base_path, rel_file, 1, max_lines)
