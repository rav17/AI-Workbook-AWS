from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from speckit_flow import audit
from speckit_flow import state as flow_state
from speckit_flow.models import FeatureState, FlowError, Route


def parse_route(payload: Any, feature: str) -> Route:
    """Validate a proposed route with the same rules as shipped profiles."""
    route = Route.from_dict(payload)
    route.validate(feature)
    return route


def load_route_file(path: Path, feature: str) -> Route:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FlowError(f"cannot read route file: {exc}") from exc
    return parse_route(payload, feature)


def save_route(feature_dir: Path, route: Route, actor: str, confirm: bool) -> FeatureState:
    """Write route.json, initialize state from it and audit the composition."""
    if not confirm:
        raise FlowError("saving a composed route requires --confirm")
    route.validate(feature_dir.name)
    for reason in route.reasons.values():
        audit.check_redaction(reason)
    if not feature_dir.is_dir():
        raise FlowError(f"feature directory not found: {feature_dir}")
    if (feature_dir / flow_state.STATE_FILE).exists():
        raise FlowError("already initialized; use 'switch' to change the profile")
    flow_state.atomic_write(
        feature_dir / flow_state.ROUTE_FILE, json.dumps(route.to_dict(), indent=2) + "\n"
    )
    audit.append_event(
        feature_dir,
        "route_composed",
        None,
        actor,
        f"route={route.profile.id} stages={','.join(route.profile.stages)}",
    )
    return flow_state.init_from_route(feature_dir, route, actor)
