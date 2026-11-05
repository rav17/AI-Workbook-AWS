from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from speckit_flow import plugins

ROOT = Path(__file__).resolve().parents[3]
PACK = ROOT / ".specify" / "plugins" / "aidlc-extras"


def _run(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(cwd)}
    return subprocess.run(
        [sys.executable, "-m", "speckit_flow", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
    )


@pytest.fixture
def isolated(tmp_path: Path) -> Path:
    """A private copy of the tool and config; stages load at import, so use a subprocess."""
    shutil.copytree(ROOT / "speckit_flow", tmp_path / "speckit_flow")
    shutil.copytree(ROOT / ".specify", tmp_path / ".specify")
    shutil.copytree(ROOT / ".github" / "agents", tmp_path / ".github" / "agents")
    return tmp_path


def _enable(root: Path) -> None:
    path = root / ".specify" / "plugins" / "aidlc-extras" / "plugin.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["enabled"] = True
    path.write_text(json.dumps(data), encoding="utf-8")


def test_shipped_pack_is_disabled_and_valid() -> None:
    found = plugins.discover(ROOT / ".specify", enabled_only=False)
    pack = next(p for p in found if p.name == "aidlc-extras")
    assert pack.enabled is False


def test_templates_exist_for_each_stage() -> None:
    stages = json.loads((PACK / "stages.json").read_text(encoding="utf-8"))["stages"]
    assert len(stages) == 3
    for stage in stages:
        assert (PACK / "templates" / f"{stage['id']}.md").is_file()


def test_disabled_pack_adds_nothing(isolated: Path) -> None:
    out = _run(isolated, "stages").stdout
    assert "market-research" not in out
    assert "nfr-design" not in out


def test_enabled_pack_adds_stages_profiles_and_passes_doctor(isolated: Path) -> None:
    _enable(isolated)
    stages = _run(isolated, "stages").stdout
    for stage in ("market-research", "nfr-design", "perf-validation"):
        assert stage in stages
    profiles = _run(isolated, "profiles", "list").stdout
    assert "discovery" in profiles
    assert "nfr-hardening" in profiles
    doc = _run(isolated, "doctor")
    assert doc.returncode == 0, doc.stdout + doc.stderr
    assert "stages: 12 stage(s), 3 custom" in doc.stdout
