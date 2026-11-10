"""Plugin packs: optional folders that add profiles, sensors and stages without editing core."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PLUGINS_DIR_NAME = "plugins"
MANIFEST = "plugin.json"
_NAME_RE = re.compile(r"^[a-z][a-z0-9-]{1,30}$")


class PluginError(Exception):
    pass


@dataclass(frozen=True)
class Plugin:
    name: str
    version: str
    description: str
    path: Path
    enabled: bool

    @property
    def profiles_dir(self) -> Path:
        return self.path / "profiles"

    @property
    def sensors_file(self) -> Path:
        return self.path / "sensors.json"

    @property
    def stages_file(self) -> Path:
        return self.path / "stages.json"

    @property
    def contracts_dir(self) -> Path:
        return self.path / "contracts"


def plugins_root(specify_dir: Path) -> Path:
    return specify_dir / PLUGINS_DIR_NAME


def _manifest(path: Path) -> Plugin:
    try:
        data: Any = json.loads((path / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PluginError(f"plugin {path.name}: cannot read {MANIFEST}: {exc}") from exc
    if not isinstance(data, dict):
        raise PluginError(f"plugin {path.name}: {MANIFEST} must be a JSON object")
    name = data.get("name")
    if not isinstance(name, str) or not _NAME_RE.match(name):
        raise PluginError(f"plugin {path.name}: invalid name {name!r}")
    if name != path.name:
        raise PluginError(f"plugin {path.name}: name {name!r} must match its folder")
    version = data.get("version")
    if not isinstance(version, str) or not version:
        raise PluginError(f"plugin {name}: version is required")
    enabled = data.get("enabled", True)
    if not isinstance(enabled, bool):
        raise PluginError(f"plugin {name}: enabled must be true or false")
    return Plugin(name, version, str(data.get("description", "")), path, enabled)


def discover(specify_dir: Path, enabled_only: bool = True) -> list[Plugin]:
    """Plugins in name order; a folder without a manifest is an error, never ignored."""
    root = plugins_root(specify_dir)
    if not root.is_dir():
        return []
    found = [_manifest(p) for p in sorted(root.iterdir()) if p.is_dir()]
    return [p for p in found if p.enabled or not enabled_only]
