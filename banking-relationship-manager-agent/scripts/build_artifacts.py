from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "build-artifacts"
MAX_LAMBDA_UNCOMPRESSED_BYTES = 250 * 1024 * 1024
PYTHON_PLATFORMS = {
    "lambda": "x86_64-manylinux2014",
    "runtime": "x86_64-manylinux_2_28",
}
FORBIDDEN_PARTS = {
    ".git",
    ".venv",
    ".venv311",
    "__pycache__",
    ".pytest_cache",
    ".hypothesis",
    "tests",
    "tmp-strands-sessions",
    "cdk.out",
    "graphify-out",
}


def _run(arguments: list[str]) -> None:
    subprocess.run(arguments, cwd=ROOT, check=True)


def _target_python(target: str) -> str:
    if target == "lambda":
        return sys.executable

    version = "3.13"
    result = subprocess.run(
        ["uv", "python", "find", version],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        _run(["uv", "python", "install", version])
        result = subprocess.run(
            ["uv", "python", "find", version],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    return result.stdout.strip()


def _validate_python() -> None:
    if sys.version_info[:2] != (3, 11):
        raise RuntimeError("Build deployment artifacts with Python 3.11")


def _python_platform(target: str) -> str:
    try:
        return PYTHON_PLATFORMS[target]
    except KeyError as exc:
        raise ValueError(f"Unsupported artifact target: {target}") from exc


def _validate_bundle(bundle: Path, target: str) -> int:
    total_bytes = 0
    for path in bundle.rglob("*"):
        relative_parts = path.relative_to(bundle).parts
        if relative_parts and relative_parts[0] in FORBIDDEN_PARTS:
            raise RuntimeError(f"Forbidden path in {target} artifact: {path.relative_to(bundle)}")
        if path.is_file():
            total_bytes += path.stat().st_size

    if target == "lambda" and total_bytes > MAX_LAMBDA_UNCOMPRESSED_BYTES:
        raise RuntimeError(
            f"Lambda artifact is {total_bytes} bytes; limit is "
            f"{MAX_LAMBDA_UNCOMPRESSED_BYTES} uncompressed bytes"
        )
    return total_bytes


def build_target(target: str) -> tuple[Path, int]:
    _validate_python()
    lockfile = ROOT / "uv.lock"
    if not lockfile.is_file():
        raise FileNotFoundError("uv.lock is required; run `uv lock --python 3.11` first")

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"aria-{target}-", dir=OUTPUT_ROOT) as temp:
        bundle = Path(temp) / target
        bundle.mkdir()
        shutil.copytree(
            ROOT / "aria",
            bundle / "aria",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", ".hypothesis"),
        )
        if target == "runtime":
            cdk_package = bundle / "cdk"
            cdk_package.mkdir()
            shutil.copy2(ROOT / "cdk" / "__init__.py", cdk_package / "__init__.py")
            shutil.copytree(ROOT / "cdk" / "custom_resources", cdk_package / "custom_resources")
        requirements = Path(temp) / "requirements.txt"
        _run(
            [
                "uv",
                "export",
                "--frozen",
                "--no-dev",
                "--no-emit-project",
                "--format",
                "requirements.txt",
                "--output-file",
                str(requirements),
            ]
        )
        target_python = _target_python(target)
        _run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                target_python,
                "--python-platform",
                _python_platform(target),
                "--target",
                str(bundle),
                "--no-compile",
                "--only-binary",
                ":all:",
                "--requirement",
                str(requirements),
            ]
        )
        total_bytes = _validate_bundle(bundle, target)
        (bundle / ".aria-artifact").write_text(f"{target}\n", encoding="ascii")
        destination = OUTPUT_ROOT / target
        if destination.exists():
            marker = destination / ".aria-artifact"
            if not marker.is_file() or marker.read_text(encoding="ascii").strip() != target:
                raise RuntimeError(
                    f"Refusing to replace unrecognized artifact directory: {destination}"
                )
            shutil.rmtree(destination)
        shutil.copytree(bundle, destination)
        return destination, total_bytes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", choices=("lambda", "runtime", "all"), default="all")
    args = parser.parse_args()
    targets = ("lambda", "runtime") if args.target == "all" else (args.target,)
    for target in targets:
        path, total_bytes = build_target(target)
        print(f"{target}: {path.relative_to(ROOT)} ({total_bytes} uncompressed bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
