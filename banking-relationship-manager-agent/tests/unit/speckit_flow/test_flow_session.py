from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from speckit_flow import audit, session
from speckit_flow import state as flow_state
from speckit_flow.cli import main
from speckit_flow.models import FlowError

ROOT = Path(__file__).resolve().parents[3]
NONE = "none.json"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / ".specify").mkdir()
    for name in ("014-a", "015-b"):
        d = tmp_path / "specs" / name
        d.mkdir(parents=True)
        flow_state.init_state(d, "express", "human:t")
    return tmp_path


def cli(repo: Path, name: str, *args: str, actor: str = "human:t") -> int:
    d = repo / "specs" / name
    return main([*args, "--feature-dir", str(d), "--actor", actor, "--sensors-file", NONE])


def test_list_and_switch(repo: Path) -> None:
    (repo / "specs" / "099-empty").mkdir()
    assert [i.name for i in session.list_intents(repo)] == ["014-a", "015-b"]
    assert not any(i.active for i in session.list_intents(repo))
    session.switch_intent(repo, "015-b", "human:t")
    assert [i.name for i in session.list_intents(repo) if i.active] == ["015-b"]
    assert "intent_switched" in (repo / "specs" / "015-b" / "audit.jsonl").read_text("utf-8")
    for bad in ("099-empty", "../x", "nope"):
        with pytest.raises(FlowError):
            session.switch_intent(repo, bad, "human:t")
    assert [i.name for i in session.list_intents(repo) if i.active] == ["015-b"]


def test_park_blocks_stage_start_until_resumed(repo: Path) -> None:
    d = repo / "specs" / "014-a"
    session.park(d, "human:t", "waiting")
    assert audit.is_parked(d)
    assert session.list_intents(repo)[0].parked
    assert cli(repo, "014-a", "stage", "start", "specify") == 1
    with pytest.raises(FlowError):
        session.park(d, "human:t")
    session.unpark(d, "human:t")
    assert not audit.is_parked(d)
    assert cli(repo, "014-a", "stage", "start", "specify") == 0
    with pytest.raises(FlowError):
        session.unpark(d, "human:t")


def advance(repo: Path, name: str) -> Path:
    d = repo / "specs" / name
    assert cli(repo, name, "stage", "start", "specify") == 0
    assert cli(repo, name, "stage", "done", "specify") == 0
    return d


def test_redo_resets_later_stages_and_gate(repo: Path) -> None:
    d = advance(repo, "014-a")
    assert flow_state.load_state(d).pending_gate == "specify"
    st = session.redo_stage(d, "specify", "human:t", "scope changed")
    assert st.pending_gate is None
    assert st.current_stage == "specify"
    assert st.stages["specify"].status == "pending"
    assert "stage_redone" in (d / "audit.jsonl").read_text("utf-8")
    assert audit.verify_chain(d) is None


def test_redo_refusals(repo: Path) -> None:
    d = advance(repo, "014-a")
    with pytest.raises(FlowError):
        session.redo_stage(d, "specify", "agent:conductor", "x")
    with pytest.raises(FlowError):
        session.redo_stage(d, "specify", "human:t", "  ")
    with pytest.raises(FlowError):
        session.redo_stage(d, "tasks", "human:t", "forward")
    assert cli(repo, "014-a", "jump", "specify", "--reason", "back") == 0
    assert cli(repo, "014-a", "jump", "tasks", "--reason", "forward") == 1


def test_cli_intents(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("speckit_flow.cli._REPO_ROOT", repo)
    assert main(["intents", "list"]) == 0
    assert main(["intents", "switch", "014-a", "--actor", "human:t"]) == 0
    assert main(["intents", "park", "--reason", "pause", "--actor", "human:t"]) == 0
    assert main(["intents", "unpark", "--actor", "human:t"]) == 0
    assert main(["intents", "switch", "nope"]) == 1


def test_session_hook_script(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    spec = importlib.util.spec_from_file_location("sess", ROOT / "scripts" / "speckit_session.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.ROOT = repo
    assert mod.main() == 0
    assert capsys.readouterr().out == ""
    session.switch_intent(repo, "014-a", "human:t")
    assert mod.main() == 0
    assert "active=014-a" in capsys.readouterr().out
    (repo / ".specify" / "feature.json").write_text("{bad", encoding="utf-8")
    assert mod.main() == 0


def test_hook_config_valid() -> None:
    data = json.loads((ROOT / ".github" / "hooks" / "speckit-session.json").read_text("utf-8"))
    assert data["hooks"]["sessionStart"][0]["type"] == "command"
