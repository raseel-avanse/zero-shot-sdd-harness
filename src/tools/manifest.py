"""Dependency manifest parsing for CVE matching (read-only)."""
from __future__ import annotations

import json
import os
import re


def parse_manifest(base_path: str, rel_file: str) -> list[dict]:
    """Return [{name, version}] for a supported manifest; [] if unparseable."""
    abs_path = os.path.join(base_path, rel_file)
    name = os.path.basename(rel_file)
    try:
        text = _read(abs_path)
    except OSError:
        return []

    if name == "requirements.txt" or name == "Pipfile":
        return _parse_requirements(text)
    if name in ("package.json", "composer.json"):
        return _parse_json_deps(text)
    if name == "pyproject.toml":
        return _parse_pyproject(text)
    if name == "go.mod":
        return _parse_gomod(text)
    return []


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def _parse_requirements(text: str) -> list[dict]:
    deps: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        m = re.match(r"^([A-Za-z0-9_.\-]+)\s*(?:[=<>!~]=?\s*([0-9][^\s;]*))?", line)
        if m:
            deps.append({"name": m.group(1), "version": m.group(2) or ""})
    return deps


def _parse_json_deps(text: str) -> list[dict]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    deps: list[dict] = []
    for key in ("dependencies", "devDependencies", "require", "require-dev"):
        section = data.get(key)
        if isinstance(section, dict):
            for pkg, ver in section.items():
                deps.append({"name": pkg, "version": str(ver)})
    return deps


def _parse_pyproject(text: str) -> list[dict]:
    deps: list[dict] = []
    # [project] dependencies = ["pkg==1.2.3", ...]  — bounded regex parse.
    for m in re.finditer(r'"([A-Za-z0-9_.\-]+)\s*(?:[=<>!~]=?\s*([0-9][^"\s;]*))?"', text):
        deps.append({"name": m.group(1), "version": m.group(2) or ""})
    return deps


def _parse_gomod(text: str) -> list[dict]:
    deps: list[dict] = []
    for m in re.finditer(r"^\s*([\w./\-]+)\s+v([0-9][^\s]*)", text, re.MULTILINE):
        deps.append({"name": m.group(1), "version": m.group(2)})
    return deps
