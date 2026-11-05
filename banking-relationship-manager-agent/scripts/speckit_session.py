"""Copilot sessionStart hook: print a one-line summary of the active feature. Never fails."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def summary() -> str:
    sys.path.insert(0, str(ROOT))
    from speckit_flow import agents, session

    active = next((i for i in session.list_intents(ROOT) if i.active), None)
    if active is None:
        return ""
    text = f"speckit: active={active.name} profile={active.profile} stage={active.current_stage}"
    try:
        roster = agents.load_roster()
        lead = next((a.id for a in roster.values() if active.current_stage in a.leads), None)
        if lead:
            text += f" lead=speckit-{lead}"
    except Exception:
        pass
    if active.pending_gate:
        text += f" gate={active.pending_gate}"
    try:
        from speckit_flow import state as flow_state

        st = flow_state.load_state(ROOT / "specs" / active.name)
        off = [
            k
            for k, v in flow_state.profile_for(
                ROOT / "specs" / active.name, st.profile, None
            ).ceremony.items()
            if not v
        ]
        if off:
            text += f" skips={','.join(off)}"
    except Exception:
        pass
    if active.parked:
        text += " [parked]"
    return text


def main() -> int:
    try:
        text = summary()
        if text:
            print(text)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
