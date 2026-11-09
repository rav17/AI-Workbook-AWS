from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAN_PATHS = [
    "aria",
    "cdk",
    "tests",
    "scripts",
    "docs",
    "specs",
    ".github",
    "README.md",
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
]


def main() -> int:
    scanner = shutil.which("detect-secrets")
    if scanner is None:
        executable = "detect-secrets.exe" if sys.platform == "win32" else "detect-secrets"
        scanner = str(Path(sys.executable).resolve().parent / executable)
    completed = subprocess.run(
        [scanner, "scan", "--force-use-all-plugins", *SCAN_PATHS],
        cwd=ROOT,
        capture_output=True,
        check=True,
        text=True,
    )
    report = json.loads(completed.stdout)
    findings = report.get("results", {})
    if findings:
        print(json.dumps(findings, indent=2, sort_keys=True), file=sys.stderr)
        return 1
    print(f"Secret scan passed with {len(report.get('plugins_used', []))} plugins.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
