from __future__ import annotations

import json
from pathlib import Path

import pytest

from speckit_flow import cli
from speckit_flow.models import FIRST_STAGE, OPTIONAL_STAGES, STAGE_REQUIRES, STAGES
from speckit_flow.stagedefs import CORE_FILE, StageDefError, load_stage_defs


def _write(path: Path, data: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _core(tmp_path: Path) -> Path:
    return _write(tmp_path / "stages" / "stages.json", json.loads(CORE_FILE.read_text("utf-8")))


def _custom(tmp_path: Path, *items: dict) -> None:
    _write(tmp_path / "custom" / "stages.json", {"stages": list(items)})


def test_core_data_matches_expected_stages() -> None:
    assert STAGES == (
        "ideation", "specify", "clarify", "plan", "tasks",
        "analyze", "implement", "deploy", "operate",
    )  # fmt: skip
    assert OPTIONAL_STAGES == ("ideation", "deploy", "operate")
    assert FIRST_STAGE == "specify"
    assert STAGE_REQUIRES == {"deploy": ("implement",), "operate": ("deploy",)}


def test_custom_stage_is_inserted_after_anchor(tmp_path: Path) -> None:
    core = _core(tmp_path)
    _custom(
        tmp_path,
        {
            "id": "nfr-design",
            "phase": "design",
            "optional": True,
            "after": "plan",
            "lead": "architect",
        },
        {"id": "perf-check", "phase": "design", "optional": True, "after": "plan"},
    )
    ids = [s.id for s in load_stage_defs(core)]
    assert ids.index("plan") + 1 == ids.index("nfr-design")
    assert ids.index("nfr-design") + 1 == ids.index("perf-check")
    assert ids.index("perf-check") < ids.index("tasks")


@pytest.mark.parametrize(
    "item",
    [
        {"id": "plan", "phase": "x", "optional": True, "after": "specify"},
        {"id": "extra", "phase": "x", "after": "plan"},
        {"id": "extra", "phase": "x", "optional": True, "after": "nope"},
        {"id": "Bad Id", "phase": "x", "optional": True, "after": "plan"},
        {"id": "extra", "phase": "x", "optional": True, "after": "plan", "requires": ["tasks"]},
    ],
)
def test_invalid_custom_stage_is_refused(tmp_path: Path, item: dict) -> None:
    core = _core(tmp_path)
    _custom(tmp_path, item)
    with pytest.raises(StageDefError):
        load_stage_defs(core)


def test_malformed_core_file_is_refused(tmp_path: Path) -> None:
    bad = _write(tmp_path / "stages" / "stages.json", {"stages": "nope"})
    with pytest.raises(StageDefError):
        load_stage_defs(bad)


def test_stages_command_lists_core_stages(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["stages", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert [s["id"] for s in data["stages"]] == list(STAGES)
