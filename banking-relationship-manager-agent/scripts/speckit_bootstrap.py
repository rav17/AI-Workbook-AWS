from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
INSTALL_MANIFEST = ".specify/speckit-portable-manifest.json"
FEATURE_POINTER = ".specify/feature.json"
SCHEMA_VERSION = 1
CATEGORIES = {
    "agents",
    "configuration",
    "documentation",
    "engine",
    "hooks",
    "integration",
    "instructions",
    "plugins",
    "scripts",
    "skills",
    "templates",
    "workflow",
}


@dataclass(frozen=True)
class BundleFile:
    source: str
    destination: str
    category: str
    content: bytes
    seed: bool = False


@dataclass(frozen=True)
class PlannedWrite:
    path: str
    content: bytes
    action: str


@dataclass(frozen=True)
class InstallResult:
    actions: tuple[tuple[str, str], ...]
    conflicts: tuple[str, ...]

    @property
    def exit_code(self) -> int:
        return 1 if self.conflicts else 0


def _relative_path(value: Any, label: str) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in value.split("/")):
        raise ValueError(f"unsafe {label}: {value!r}")
    if any(char in value for char in '\\:<>"|?*\0') or any(
        part.endswith((" ", "."))
        or part.split(".")[0].upper()
        in {
            "CON",
            "PRN",
            "AUX",
            "NUL",
            *(f"COM{i}" for i in range(1, 10)),
            *(f"LPT{i}" for i in range(1, 10)),
        }
        for part in path.parts
    ):
        raise ValueError(f"unsafe {label}: {value!r}")
    return path


def _resolve_within(root: Path, relative: PurePosixPath, label: str) -> Path:
    root_resolved = root.resolve()
    candidate = root_resolved.joinpath(*relative.parts)
    current = root_resolved
    for index, part in enumerate(relative.parts):
        current = current / part
        if current.is_symlink():
            raise ValueError(f"{label} must not traverse symlinks: {relative.as_posix()}")
        if index < len(relative.parts) - 1 and current.exists() and not current.is_dir():
            raise ValueError(f"{label} parent is not a directory: {current}")
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root_resolved):
        raise ValueError(f"{label} escapes its root: {relative.as_posix()}")
    return candidate


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _collect_bundle(source_root: Path, bundle_file: Path) -> tuple[str, list[BundleFile]]:
    try:
        bundle = json.loads(bundle_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read bundle manifest {bundle_file}: {exc}") from exc
    if not isinstance(bundle, dict) or not isinstance(bundle.get("files"), list):
        raise ValueError("bundle manifest must contain a files list")
    version = bundle.get("bundle_version")
    if not isinstance(version, str) or not version:
        raise ValueError("bundle_version must be a non-empty string")

    collected: dict[str, BundleFile] = {}
    for entry in bundle["files"]:
        if not isinstance(entry, dict):
            raise ValueError("each bundle entry must be an object")
        source_rel = _relative_path(entry.get("source"), "source")
        destination_rel = _relative_path(entry.get("destination"), "destination")
        category = entry.get("category")
        if not isinstance(category, str) or category not in CATEGORIES:
            raise ValueError(f"unknown bundle category: {category!r}")
        seed = entry.get("seed", False)
        if not isinstance(seed, bool):
            raise ValueError("bundle seed flag must be boolean")
        source = _resolve_within(source_root, source_rel, "bundle source")
        if not source.exists():
            raise ValueError(f"bundle source does not exist: {source_rel.as_posix()}")
        if source.is_file():
            sources = [source]
        elif source.is_dir():
            included = entry.get("include")
            if not isinstance(included, list) or not included:
                raise ValueError(
                    f"directory bundle source needs an explicit include list: {source}"
                )
            sources = [
                _resolve_within(source, _relative_path(name, "included file"), "included file")
                for name in included
            ]
        else:
            raise ValueError(f"bundle source is not a regular file or directory: {source}")

        for source_file in sources:
            if not source_file.is_file():
                raise ValueError(f"included source is not a regular file: {source_file}")
            suffix = source_file.relative_to(source) if source.is_dir() else Path()
            destination = destination_rel.joinpath(*suffix.parts)
            destination_text = destination.as_posix()
            destination_key = destination_text.casefold()
            for existing in [*collected, INSTALL_MANIFEST, FEATURE_POINTER]:
                if (
                    destination_key == existing
                    or destination_key.startswith(existing + "/")
                    or existing.startswith(destination_key + "/")
                ):
                    raise ValueError(
                        f"bundle destination collision: {destination_text} / {existing}"
                    )
            content = source_file.read_bytes()
            if category == "plugins" and source_file.name == "plugin.json":
                plugin = json.loads(content)
                if not isinstance(plugin, dict):
                    raise ValueError(f"plugin manifest must be an object: {source_file}")
                plugin["enabled"] = False
                content = (json.dumps(plugin, indent=2) + "\n").encode("utf-8")
            collected[destination_key] = BundleFile(
                source=source_file.relative_to(source_root).as_posix(),
                destination=destination_text,
                category=category,
                content=content,
                seed=seed,
            )
    return version, list(collected.values())


def _read_install_manifest(path: Path) -> tuple[str, dict[str, str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read install manifest {path}: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported portable install manifest schema")
    version = data.get("bundle_version")
    files = data.get("files")
    if not isinstance(version, str) or not isinstance(files, list):
        raise ValueError("invalid portable install manifest")
    installed: dict[str, str] = {}
    for item in files:
        if not isinstance(item, dict):
            raise ValueError("invalid installed file record")
        path_value = _relative_path(item.get("path"), "installed path").as_posix()
        digest = item.get("sha256")
        if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise ValueError(f"invalid installed hash for {path_value}")
        if path_value in installed:
            raise ValueError(f"duplicate installed path: {path_value}")
        installed[path_value] = digest
    return version, installed


def _default_feature_pointer(target: Path) -> bytes:
    specs_dir = target / "specs"
    greatest = 0
    if specs_dir.is_symlink():
        raise ValueError("target specs directory must not be a symlink")
    if specs_dir.is_dir():
        for child in specs_dir.iterdir():
            match = re.match(r"^(\d{3})-", child.name)
            if child.is_dir() and match:
                greatest = max(greatest, int(match.group(1)))
    feature_dir = f"specs/{greatest + 1:03d}-new-feature"
    return (json.dumps({"feature_directory": feature_dir}, indent=2) + "\n").encode("utf-8")


def _manifest_bytes(version: str, digests: dict[str, str]) -> bytes:
    data = {
        "schema_version": SCHEMA_VERSION,
        "bundle_version": version,
        "files": [{"path": path, "sha256": digest} for path, digest in sorted(digests.items())],
    }
    return (json.dumps(data, indent=2) + "\n").encode("utf-8")


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def apply_bundle(
    action: str,
    target: Path,
    *,
    source_root: Path = ROOT,
    bundle_file: Path | None = None,
    dry_run: bool = False,
) -> InstallResult:
    if action not in {"install", "update"}:
        raise ValueError(f"unsupported action: {action}")
    if not target.exists() or not target.is_dir():
        raise ValueError(f"target must be an existing directory: {target}")
    target = target.resolve()
    manifest_path = _resolve_within(
        target, _relative_path(INSTALL_MANIFEST, "install manifest"), "install manifest"
    )
    source_root = source_root.resolve()
    if target.is_relative_to(source_root) or source_root.is_relative_to(target):
        raise ValueError("source and target directories must not overlap")
    bundle_path = bundle_file or source_root / "scripts" / "speckit-portable-bundle.json"
    if not bundle_path.is_file():
        raise ValueError(f"bundle manifest does not exist: {bundle_path}")
    version, files = _collect_bundle(source_root, bundle_path)

    if action == "install" and manifest_path.exists():
        raise ValueError("workflow is already installed; use the update action")
    previous: dict[str, str] = {}
    if action == "update":
        if not manifest_path.is_file():
            raise ValueError("workflow is not installed; use the install action")
        _, previous = _read_install_manifest(manifest_path)

    writes: list[PlannedWrite] = []
    conflicts: list[str] = []
    next_digests = dict(previous)
    for bundle_file_item in files:
        relative = _relative_path(bundle_file_item.destination, "destination")
        destination = _resolve_within(target, relative, "destination")
        source_digest = _sha256(bundle_file_item.content)
        previous_digest = previous.get(relative.as_posix())
        if not destination.exists():
            if previous_digest is not None:
                conflicts.append(f"{relative.as_posix()} (previously installed file is missing)")
                continue
            writes.append(PlannedWrite(relative.as_posix(), bundle_file_item.content, "CREATE"))
            next_digests[relative.as_posix()] = source_digest
            continue
        if not destination.is_file():
            conflicts.append(f"{relative.as_posix()} (destination is not a regular file)")
            continue
        if action == "update" and bundle_file_item.seed:
            writes.append(PlannedWrite(relative.as_posix(), b"", "PRESERVE"))
            continue
        current_digest = _sha256(destination.read_bytes())
        if current_digest == source_digest:
            writes.append(PlannedWrite(relative.as_posix(), bundle_file_item.content, "UNCHANGED"))
            if previous_digest is not None:
                next_digests[relative.as_posix()] = source_digest
        elif action == "update" and previous_digest == current_digest:
            writes.append(PlannedWrite(relative.as_posix(), bundle_file_item.content, "UPDATE"))
            next_digests[relative.as_posix()] = source_digest
        else:
            conflicts.append(f"{relative.as_posix()} (destination differs from bundle)")

    feature_rel = _relative_path(FEATURE_POINTER, "feature pointer")
    feature_path = _resolve_within(target, feature_rel, "feature pointer")
    if not feature_path.exists():
        writes.append(PlannedWrite(FEATURE_POINTER, _default_feature_pointer(target), "CREATE"))
    elif not feature_path.is_file():
        conflicts.append(f"{FEATURE_POINTER} (destination is not a regular file)")
    else:
        writes.append(PlannedWrite(FEATURE_POINTER, feature_path.read_bytes(), "PRESERVE"))

    result_actions = tuple((item.action, item.path) for item in writes)
    if conflicts:
        return InstallResult(result_actions, tuple(conflicts))
    if not dry_run:
        for item in writes:
            if item.action in {"CREATE", "UPDATE"}:
                destination = _resolve_within(
                    target, _relative_path(item.path, "destination"), "destination"
                )
                _atomic_write(destination, item.content)
        _atomic_write(manifest_path, _manifest_bytes(version, next_digests))
    return InstallResult(result_actions, ())


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Install or update portable Spec Kit workflow files."
    )
    subparsers = parser.add_subparsers(dest="action", required=True)
    for action in ("install", "update"):
        command = subparsers.add_parser(action)
        command.add_argument(
            "--target", type=Path, required=True, help="existing target project directory"
        )
        command.add_argument("--dry-run", action="store_true", help="show actions without writing")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = apply_bundle(args.action, args.target, dry_run=args.dry_run)
    except (OSError, ValueError) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2
    for status, path in result.actions:
        print(f"{status} {path}")
    for conflict in result.conflicts:
        print(f"CONFLICT {conflict}")
    if result.conflicts:
        print("No files written; resolve the conflicts before retrying.")
        return 1
    print(f"{'DRY RUN ' if args.dry_run else ''}{args.action} complete")
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
