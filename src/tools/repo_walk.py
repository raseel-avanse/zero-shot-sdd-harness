"""Read-only, scoped repository inventory. Never persists raw source."""
from __future__ import annotations

import os

# Directories never worth scanning.
_SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", ".venv", "venv", "__pycache__",
    ".mypy_cache", ".pytest_cache", "dist", "build", ".next", ".idea", ".tox",
}

_EXT_LANG = {
    ".py": "python", ".js": "javascript", ".jsx": "javascript",
    ".ts": "typescript", ".tsx": "typescript", ".rb": "ruby", ".go": "go",
    ".php": "php", ".java": "java", ".c": "c", ".cpp": "cpp", ".cs": "csharp",
    ".sh": "shell", ".sql": "sql", ".html": "html", ".yaml": "yaml", ".yml": "yaml",
}

_MANIFEST_NAMES = {
    "requirements.txt", "pyproject.toml", "Pipfile", "package.json",
    "package-lock.json", "yarn.lock", "pom.xml", "build.gradle", "go.mod",
    "Gemfile", "composer.json",
}

# Bound the inventory so recon prompts and walk time stay small.
_MAX_FILES = 2000


def walk(path: str) -> dict:
    """Return {files, languages, manifests} for a scoped repo path (read-only)."""
    if not os.path.isdir(path):
        raise FileNotFoundError(f"target path is not a readable directory: {path}")

    files: list[str] = []
    languages: dict[str, int] = {}
    manifests: list[str] = []

    for root, dirs, names in os.walk(path):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        for name in names:
            abs_path = os.path.join(root, name)
            rel = os.path.relpath(abs_path, path)
            if len(files) < _MAX_FILES:
                files.append(rel)
            _, ext = os.path.splitext(name)
            lang = _EXT_LANG.get(ext.lower())
            if lang:
                languages[lang] = languages.get(lang, 0) + 1
            if name in _MANIFEST_NAMES:
                manifests.append(rel)

    return {"files": files, "languages": languages, "manifests": manifests}
