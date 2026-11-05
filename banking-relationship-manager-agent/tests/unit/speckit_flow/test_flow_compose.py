from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from speckit_flow import audit, compose, state
from speckit_flow.cli import main
from speckit_flow.models import FlowError

H = "human:tester"


@pytest.fixture
def fdir(tmp_path: Path) -> Path:
    d = tmp_path / "specs" / "012-demo"
    d.mkdir(parents=True)
    return d


def _route(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "custom-012-demo",
        "description": "composed",
        "stages": ["specify", "plan", "implement"],
        "depth": "standard",
        "gates": ["plan"],
        "exemptions": ["implement-without-tasks"],
        "reasons": {"specify": "capture", "plan": "design", "implement": "build"},
    }
    base.update(over)
    return base


def test_valid_route_saved_and_used(fdir: Path) -> None:
    route = compose.parse_route(_route(), fdir.name)
    st = compose.save_route(fdir, route, H, confirm=True)
    assert st.profile == "custom-012-demo"
    assert json.loads((fdir / "route.json").read_text())["reasons"]["plan"] == "design"
    assert "route_composed" in [e.type for e in audit.read_events(fdir)]
    state.start_stage(fdir, "specify", H)
    state.done_stage(fdir, "specify", H)
    state.start_stage(fdir, "plan", H)
    assert state.done_stage(fdir, "plan", H).pending_gate == "plan"


def test_confirm_required(fdir: Path) -> None:
    route = compose.parse_route(_route(), fdir.name)
    with pytest.raises(FlowError, match="--confirm"):
        compose.save_route(fdir, route, H, confirm=False)
    assert not (fdir / "route.json").exists()


@pytest.mark.parametrize(
    "bad",
    [
        {"stages": ["plan", "specify"]},
        {"stages": ["specify", "implement"], "exemptions": []},
        {"stages": ["specify", "deploy"], "reasons": {"specify": "a", "deploy": "b"}},
        {"id": "other"},
        {"reasons": {"specify": "capture", "plan": "design"}},
        {"reasons": {"specify": "capture", "plan": " ", "implement": "x"}},
        {"gates": ["tasks"]},
    ],
)
def test_invalid_routes_rejected(fdir: Path, bad: dict[str, Any]) -> None:
    with pytest.raises(FlowError):
        compose.parse_route(_route(**bad), fdir.name)


def test_missing_reasons_object_rejected(fdir: Path) -> None:
    data = _route()
    del data["reasons"]
    with pytest.raises(FlowError, match="reasons"):
        compose.parse_route(data, fdir.name)


def test_cannot_compose_twice(fdir: Path) -> None:
    route = compose.parse_route(_route(), fdir.name)
    compose.save_route(fdir, route, H, confirm=True)
    with pytest.raises(FlowError, match="already initialized"):
        compose.save_route(fdir, route, H, confirm=True)


def test_rebuild_with_custom_route(fdir: Path) -> None:
    compose.save_route(fdir, compose.parse_route(_route(), fdir.name), H, confirm=True)
    (fdir / "state.json").unlink()
    assert state.rebuild_state(fdir, H).profile == "custom-012-demo"


def test_cli_init_route_file_and_compose_validate(fdir: Path, tmp_path: Path) -> None:
    route_file = tmp_path / "r.json"
    route_file.write_text(json.dumps(_route()), encoding="utf-8")
    base = ["--feature-dir", str(fdir), "--actor", "tester"]
    assert main(["compose", "validate", "--file", str(route_file), *base]) == 0
    assert main(["init", "--route-file", str(route_file), *base]) == 0
    assert state.load_state(fdir).profile == "custom-012-demo"
    route_file.write_text(json.dumps(_route(id="bad")), encoding="utf-8")
    assert main(["compose", "validate", "--file", str(route_file), *base]) == 1
