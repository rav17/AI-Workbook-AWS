from __future__ import annotations

from pathlib import Path
from typing import Any

from speckit_flow import profiles, sensors

CUSTOM_DIR_NAME = "custom"


def custom_dir(profiles_dir: Path) -> Path:
    return profiles_dir.parent / CUSTOM_DIR_NAME


def describe(profiles_dir: Path, sensors_file: Path) -> dict[str, Any]:
    """List overlay items and whether each adds to or overrides a core item."""
    root = custom_dir(profiles_dir)
    core_profiles = {p.stem for p in profiles_dir.glob("*.json")}
    items: list[dict[str, str]] = []
    overlay = root / "profiles"
    if overlay.is_dir():
        for path in sorted(overlay.glob("*.json")):
            kind = "override" if path.stem in core_profiles else "add"
            items.append({"type": "profile", "id": path.stem, "effect": kind})
    overlay_sensors = root / "sensors.json"
    if overlay_sensors.is_file():
        core_ids = {s.id for s in sensors._read_sensors(sensors_file)}
        for sensor in sensors._read_sensors(overlay_sensors):
            kind = "override" if sensor.id in core_ids else "add"
            items.append({"type": "sensor", "id": sensor.id, "effect": kind})
    return {"items": items}


def validate(profiles_dir: Path, sensors_file: Path) -> dict[str, Any]:
    """Load the merged configuration; any invalid overlay raises FlowError."""
    merged_profiles = profiles.load_profiles(profiles_dir)
    merged_sensors = sensors.load_sensors(sensors_file) if sensors_file.is_file() else []
    return {"profiles": len(merged_profiles), "sensors": len(merged_sensors)}
