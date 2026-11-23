"""Build the static context the findings Lambda gives Bedrock when it advises on an alert.

The Lambda is packaged on its own (standard library + boto3 only), so it cannot read the
repository at run time. At synth time this module reads ``playbooks/*.yml``,
``config/playbook_mapping.yml`` and ``config/denied_commands.yml`` and writes one JSON file
next to the handler:

* ``playbooks``: what each playbook does and which alerts it is mapped to. Bedrock may
  recommend only a playbook from this list.
* ``denied_patterns``: the same patterns the ECS task's PlanValidator enforces. The Lambda
  drops any AI-suggested manual step that matches one of them.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

CONTEXT_FILENAME = "advisory_context.json"

MAX_DESCRIPTION_CHARS = 400
MAX_TASKS_PER_PLAYBOOK = 12
_NON_ASCII = re.compile(r"[^\x20-\x7e]")


def _ascii(text: str) -> str:
    """Drop non-ASCII characters (some playbook comments contain mojibake dashes)."""
    return " ".join(_NON_ASCII.sub(" ", text).split())


def _leading_comment(text: str) -> str:
    """Return the comment block at the top of a playbook as one line."""
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if line in ("", "---"):
            if lines:
                break
            continue
        if not line.startswith("#"):
            break
        lines.append(line.lstrip("#").strip())
    return _ascii(" ".join(lines))[:MAX_DESCRIPTION_CHARS]


def _alerts_by_playbook(mapping_file: Path) -> dict[str, list[str]]:
    """Map playbook path -> alert names, from the rules in playbook_mapping.yml."""
    if not mapping_file.is_file():
        return {}
    data = yaml.safe_load(mapping_file.read_text(encoding="utf-8")) or {}
    alerts: dict[str, list[str]] = {}
    for rule in data.get("rules", []) or []:
        path = str(rule.get("playbook_path", "")).replace("\\", "/")
        alert = (rule.get("conditions") or {}).get("alert_name")
        if path and alert and alert not in alerts.setdefault(path, []):
            alerts[path].append(str(alert))
    return alerts


def _describe_playbook(path: Path, rel_path: str, alerts: list[str]) -> dict[str, Any]:
    """Summarise one playbook: first play name, task names, leading comment, alerts."""
    text = path.read_text(encoding="utf-8")
    plays = yaml.safe_load(text) or []
    summary = ""
    tasks: list[str] = []
    if isinstance(plays, list):
        for play in plays:
            if not isinstance(play, dict):
                continue
            summary = summary or _ascii(str(play.get("name", "")))
            for task in play.get("tasks", []) or []:
                if isinstance(task, dict) and task.get("name"):
                    tasks.append(_ascii(str(task["name"]))[:120])
    return {
        "path": rel_path,
        "summary": summary,
        "description": _leading_comment(text),
        "tasks": tasks[:MAX_TASKS_PER_PLAYBOOK],
        "alerts": alerts,
    }


def build_advisory_context(repo_root: Path) -> dict[str, Any]:
    """Return ``{"playbooks": [...], "denied_patterns": [...]}`` for the repository."""
    playbook_dir = repo_root / "playbooks"
    alerts = _alerts_by_playbook(repo_root / "config" / "playbook_mapping.yml")
    playbooks = [
        _describe_playbook(
            p, f"playbooks/{p.name}", alerts.get(f"playbooks/{p.name}", [])
        )
        for p in sorted(playbook_dir.glob("*.yml"))
    ]

    denied_file = repo_root / "config" / "denied_commands.yml"
    denied: list[dict[str, str]] = []
    if denied_file.is_file():
        data = yaml.safe_load(denied_file.read_text(encoding="utf-8")) or {}
        for entry in data.get("denied_patterns", []) or []:
            pattern = str(entry.get("pattern", ""))
            if pattern:
                denied.append(
                    {"pattern": pattern, "reason": str(entry.get("reason", ""))}
                )
    return {"playbooks": playbooks, "denied_patterns": denied}


def write_advisory_context(repo_root: Path, destination: Path) -> Path:
    """Write the context JSON into ``destination`` (the Lambda asset directory).

    Rewrites the file only when its content changes so the asset hash stays stable.
    """
    target = destination / CONTEXT_FILENAME
    content = (
        json.dumps(build_advisory_context(repo_root), indent=1, sort_keys=True) + "\n"
    )
    if not target.is_file() or target.read_text(encoding="utf-8") != content:
        target.write_text(content, encoding="utf-8")
    return target
