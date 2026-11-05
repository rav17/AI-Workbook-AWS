"""Stage definitions loaded from data: core file plus an optional project overlay."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from speckit_flow import plugins

ROOT = Path(__file__).resolve().parent.parent
CORE_FILE = ROOT / ".specify" / "stages" / "stages.json"
CUSTOM_FILE = ROOT / ".specify" / "custom" / "stages.json"
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{1,30}$")


class StageDefError(Exception):
    pass


@dataclass(frozen=True)
class StageDef:
    id: str
    phase: str
    optional: bool = False
    requires: tuple[str, ...] = ()
    lead: str | None = None
    description: str = ""
    custom: bool = False


def _read(path: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StageDefError(f"cannot read stages file {path.name}: {exc}") from exc
    items = data.get("stages") if isinstance(data, dict) else None
    if not isinstance(items, list) or not all(isinstance(i, dict) for i in items):
        raise StageDefError(f"{path.name}: 'stages' must be a list of objects")
    return items


def _make(item: dict[str, Any], custom: bool) -> StageDef:
    sid = item.get("id")
    if not isinstance(sid, str) or not _ID_RE.match(sid):
        raise StageDefError(f"invalid stage id {sid!r}")
    requires = item.get("requires", [])
    if not isinstance(requires, list) or not all(isinstance(r, str) for r in requires):
        raise StageDefError(f"stage {sid}: requires must be a list of stage ids")
    phase = item.get("phase")
    if not isinstance(phase, str) or not phase:
        raise StageDefError(f"stage {sid}: phase is required")
    return StageDef(
        id=sid,
        phase=phase,
        optional=bool(item.get("optional", False)),
        requires=tuple(requires),
        lead=item.get("lead") if isinstance(item.get("lead"), str) else None,
        description=str(item.get("description", "")),
        custom=custom,
    )


def load_stage_defs(core_file: Path = CORE_FILE, custom_file: Path | None = None) -> list[StageDef]:
    """Return ordered stage definitions; custom stages are optional and placed via 'after'."""
    if custom_file is None:
        custom_file = core_file.parent.parent / "custom" / "stages.json"
    stages = [_make(i, False) for i in _read(core_file)]
    ids = [s.id for s in stages]
    if len(set(ids)) != len(ids) or not stages:
        raise StageDefError("core stages must be unique and non-empty")
    if stages[0].optional and not any(not s.optional for s in stages):
        raise StageDefError("core stages need a required stage")
    overlays: list[Path] = []
    try:
        overlays = [p.stages_file for p in plugins.discover(core_file.parent.parent)]
    except plugins.PluginError as exc:
        raise StageDefError(str(exc)) from exc
    overlays.append(custom_file)
    for overlay in overlays:
        if not overlay.is_file():
            continue
        for item in _read(overlay):
            new = _make(item, True)
            after = item.get("after")
            if new.id in ids:
                raise StageDefError(f"custom stage {new.id!r} duplicates an existing stage")
            if not new.optional:
                raise StageDefError(f"custom stage {new.id!r} must be optional")
            if after not in ids:
                raise StageDefError(f"custom stage {new.id!r}: 'after' must name an existing stage")
            pos = ids.index(after) + 1
            while pos < len(stages) and stages[pos].custom and stages[pos].id != new.id:
                pos += 1
            stages.insert(pos, new)
            ids = [s.id for s in stages]
    order = {s.id: i for i, s in enumerate(stages)}
    for stage in stages:
        for req in stage.requires:
            if req not in order or order[req] >= order[stage.id]:
                raise StageDefError(f"stage {stage.id}: requires {req!r} which must come earlier")
    return stages
