"""FPL StormForce ETA Lambda — calculate_eta_plausibility, calculate_eta_from_location."""

import re
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo
from shared import dispatch_tool

PACE_MPH = 31.25
TZ = ZoneInfo("America/New_York")

_DISTANCE_CACHE = {
    "juno beach, fl": 0.0, "west palm beach, fl": 15.0, "jupiter, fl": 5.0,
    "boca raton, fl": 30.0, "fort lauderdale, fl": 55.0, "miami, fl": 85.0,
    "orlando, fl": 160.0, "tampa, fl": 200.0, "jacksonville, fl": 340.0,
    "tallahassee, fl": 470.0, "fort myers, fl": 150.0, "naples, fl": 160.0,
    "gainesville, fl": 290.0, "daytona beach, fl": 200.0, "atlanta, ga": 550.0,
    "savannah, ga": 420.0, "birmingham, al": 700.0, "charlotte, nc": 680.0,
    "nashville, tn": 870.0, "new orleans, la": 850.0, "houston, tx": 1100.0,
}


def _resolve(location: str) -> float | None:
    loc = location.strip().lower()
    if loc in _DISTANCE_CACHE:
        return _DISTANCE_CACHE[loc]
    for key, dist in _DISTANCE_CACHE.items():
        if key.split(",")[0].strip() in loc:
            return dist
    return None


def _parse_time(s: str) -> datetime:
    if s == "now":
        return datetime.now(TZ)
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        pass
    today = datetime.now(TZ).date()
    s2 = s.strip().lower()
    m = re.match(r'^(\d{1,2})(?::(\d{2}))?\s*(am|pm)$', s2)
    if m:
        h, mn = int(m.group(1)), int(m.group(2) or 0)
        if m.group(3) == 'pm' and h != 12: h += 12
        if m.group(3) == 'am' and h == 12: h = 0
        return datetime(today.year, today.month, today.day, h, mn, tzinfo=TZ)
    m = re.match(r'^(\d{1,2}):(\d{2})$', s2)
    if m:
        return datetime(today.year, today.month, today.day, int(m.group(1)), int(m.group(2)), tzinfo=TZ)
    return datetime.now(TZ)


def calculate_eta_plausibility(args: dict[str, Any]) -> dict[str, Any]:
    dep_loc = args.get("departure_location", "")
    dest = args.get("processing_site_address", "")
    dep_time = args.get("departure_time", "")
    provided_eta = args.get("provided_eta", "")
    if not dep_loc or not dest or not dep_time or not provided_eta:
        return {"success": False, "error": "departure_location, processing_site_address, departure_time, provided_eta all required"}

    o, d = _resolve(dep_loc), _resolve(dest)
    if o is None or d is None:
        return {"result": {"is_plausible": "unconfirmed", "validation_skipped": True,
                           "reason": f"Unknown location", "provided_arrival_time": provided_eta}}

    distance = abs(o - d)
    hours = distance / PACE_MPH
    dep = _parse_time(dep_time)
    expected = dep + timedelta(hours=hours)
    provided = _parse_time(provided_eta)
    if hours == 0:
        return {"result": {"is_plausible": True, "variance_percent": 0.0, "distance_miles": distance}}

    diff_hours = (provided - expected).total_seconds() / 3600
    variance_pct = abs(diff_hours / hours) * 100
    is_too_fast = diff_hours < 0 and variance_pct > 10.0

    return {"result": {
        "distance_miles": round(distance, 1), "expected_duration_hours": round(hours, 2),
        "expected_arrival_time": expected.isoformat(), "provided_arrival_time": provided_eta,
        "variance_percent": round(variance_pct, 1), "is_plausible": not is_too_fast,
        "is_slow": diff_hours > 0 and variance_pct > 10.0,
    }}


def calculate_eta_from_location(args: dict[str, Any]) -> dict[str, Any]:
    origin = args.get("last_known_location", "")
    dest = args.get("processing_site_address", "")
    if not origin or not dest:
        return {"success": False, "error": "last_known_location and processing_site_address required"}

    o, d = _resolve(origin), _resolve(dest)
    if o is None or d is None:
        return {"result": {"error": "Unknown location", "distance_miles": -1}}

    distance = abs(o - d)
    hours = distance / PACE_MPH
    arrival = datetime.now(TZ) + timedelta(hours=hours)
    return {"result": {"distance_miles": round(distance, 1), "expected_duration_hours": round(hours, 2),
                        "expected_arrival_time": arrival.isoformat()}}


TOOL_MAP = {
    "calculate_eta_plausibility": calculate_eta_plausibility,
    "calculate_eta_from_location": calculate_eta_from_location,
}


def lambda_handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    return dispatch_tool(event, TOOL_MAP)
