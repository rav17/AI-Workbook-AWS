"""Bounded, path-only inventory for optional existing-codebase analysis."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from speckit_flow.models import FlowError

ROOT = Path(__file__).resolve().parent.parent
SOURCE_EXTENSIONS = frozenset(
    {
        ".py",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".mjs",
        ".cjs",
        ".java",
        ".kt",
        ".kts",
        ".go",
        ".rs",
        ".cs",
        ".fs",
        ".vb",
        ".rb",
        ".php",
        ".c",
        ".h",
        ".cc",
        ".cpp",
        ".hpp",
        ".swift",
        ".m",
        ".mm",
        ".scala",
        ".clj",
        ".ex",
        ".exs",
        ".erl",
        ".hs",
        ".lua",
        ".r",
        ".dart",
        ".vue",
        ".svelte",
        ".sql",
        ".tf",
        ".sh",
        ".ps1",
    }
)
EXCLUDED_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".github",
        ".claude",
        ".kiro",
        ".specify",
        ".agents",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "node_modules",
        "vendor",
        "dist",
        "build",
        "build-artifacts",
        "target",
        "bin",
        "obj",
        "out",
        "coverage",
        "htmlcov",
        ".next",
        ".nuxt",
        ".gradle",
        ".terraform",
        "cdk.out",
        ".agentcore-generated",
        ".agentcore-preview",
        ".idea",
        ".vscode",
        "venv",
        "env",
    }
)
ROOT_TOOLKIT_DIRS = frozenset({"speckit_flow", "specs", "graphify-out"})
TOOLKIT_SCRIPTS = frozenset(
    {
        "scripts/speckit_guard.py",
        "scripts/speckit_session.py",
        "scripts/speckit_bootstrap.py",
    }
)
MANIFESTS = frozenset(
    {
        "pyproject.toml",
        "requirements.txt",
        "setup.py",
        "setup.cfg",
        "pipfile",
        "package.json",
        "go.mod",
        "cargo.toml",
        "pom.xml",
        "build.gradle",
        "build.gradle.kts",
        "gemfile",
        "composer.json",
        "mix.exs",
        "pubspec.yaml",
        "package.swift",
        "cmakelists.txt",
    }
)


@dataclass(frozen=True)
class Inventory:
    sources: tuple[str, ...]
    tests: tuple[str, ...]
    manifests: tuple[str, ...]
    examined_entries: int

    @property
    def existing(self) -> bool:
        return bool(self.sources)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sources": list(self.sources),
            "tests": list(self.tests),
            "manifests": list(self.manifests),
            "examined_entries": self.examined_entries,
            "existing": self.existing,
        }

    def markdown(self) -> str:
        lines = [
            "# Codebase inventory",
            "",
            f"Recognized source present: {self.existing}. "
            f"Entries examined: {self.examined_entries}.",
            "Path inventory only; no architecture verification or tests executed.",
            "",
        ]
        for title, paths in (
            ("Sources", self.sources),
            ("Tests", self.tests),
            ("Manifests", self.manifests),
        ):
            lines.extend([f"## {title}", ""])
            lines.extend(f"- {p}" for p in paths)
            if not paths:
                lines.append("- None recognized")
            lines.append("")
        return "\n".join(lines)


def _is_test(relative: Path) -> bool:
    name = relative.name.lower()
    return (
        any(
            p.lower() in {"test", "tests", "__tests__", "spec", "specs"}
            for p in relative.parts[:-1]
        )
        or name.startswith("test_")
        or name == "conftest.py"
        or ".test." in name
        or ".spec." in name
        or "_test." in name
    )


def _is_link(info: os.stat_result) -> bool:
    return bool(
        stat.S_ISLNK(info.st_mode)
        or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    )


def scan(root: Path | None = None, *, max_entries: int = 10_000) -> Inventory:
    """List paths without opening file contents; never traverse symlinks or junctions."""
    root = ROOT if root is None else root
    if max_entries < 1:
        raise FlowError("codebase scan limit must be positive")
    sources: list[str] = []
    tests: list[str] = []
    manifests: list[str] = []
    pending = [root]
    examined = 0
    try:
        root_stat = root.lstat()
        if not stat.S_ISDIR(root_stat.st_mode) or _is_link(root_stat):
            raise FlowError("codebase scan root must be a non-symlink directory")
        while pending:
            directory = pending.pop()
            children: list[Path] = []
            with os.scandir(directory) as entries:
                for entry in entries:
                    examined += 1
                    if examined > max_entries:
                        raise FlowError(f"codebase scan exceeded entry limit ({max_entries})")
                    info = entry.stat(follow_symlinks=False)
                    if _is_link(info):
                        continue
                    path = Path(entry.path)
                    relative = path.relative_to(root)
                    name = entry.name.lower()
                    if stat.S_ISDIR(info.st_mode):
                        if (
                            name in EXCLUDED_DIRS
                            or name.startswith(".venv")
                            or name.endswith(".egg-info")
                            or (directory == root and name in ROOT_TOOLKIT_DIRS)
                        ):
                            continue
                        children.append(path)
                    elif stat.S_ISREG(info.st_mode):
                        label = relative.as_posix()
                        if label.lower() in TOOLKIT_SCRIPTS:
                            continue
                        if name in MANIFESTS or path.suffix.lower() in {".csproj", ".fsproj"}:
                            manifests.append(label)
                        if path.suffix.lower() in SOURCE_EXTENSIONS:
                            sources.append(label)
                            if _is_test(relative):
                                tests.append(label)
            pending.extend(sorted(children, reverse=True))
    except OSError as exc:
        raise FlowError(f"cannot scan codebase: {exc}") from exc
    return Inventory(
        tuple(sorted(sources)), tuple(sorted(tests)), tuple(sorted(manifests)), examined
    )
