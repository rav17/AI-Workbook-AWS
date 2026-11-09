"""Structural operational-readiness evidence checks; never executes evidence."""

from __future__ import annotations

import hashlib
import os
import re
import stat
from pathlib import Path

from speckit_flow.models import FlowError

MAX_BYTES = 256 * 1024
SECTIONS: dict[str, tuple[str, ...]] = {
    "release.md": ("Ownership and target", "Configuration", "Verification", "Rollout", "Rollback"),
    "runbook.md": ("Ownership", "Health signals", "Alerts", "Incidents", "Rollback", "Feedback"),
}
_PLACEHOLDER = re.compile(
    r"(?i:\bTODO\b|\bTBD\b|NEEDS CLARIFICATION|ACTION REQUIRED)|\{\{.*?\}\}"
    r"|\[(?![xX]\])(?:[A-Z][A-Z _/-]*|evidence|owner|date|version|feature)\](?!\()",
)
_UNCHECKED = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\[ \]", re.MULTILINE)
_EMPTY = re.compile(r"^(?:n/?a|none|pending|unknown|not applicable|[-_.\s]*)$", re.IGNORECASE)
_EVIDENCE = re.compile(r"^\s*-\s+Evidence:\s*(.*?)\s*$", re.IGNORECASE)


def _read(feature_dir: Path, name: str) -> bytes | None:
    path = feature_dir / name
    try:
        info = path.lstat()
        if (
            not stat.S_ISREG(info.st_mode)
            or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise FlowError(f"{name} must be a regular non-symlink file")
        with path.open("rb") as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                raise FlowError(f"{name} must be a regular file")
            data = handle.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise FlowError(f"{name} exceeds size limit ({MAX_BYTES} bytes)")
        data.decode("utf-8")
        return data
    except FileNotFoundError:
        return None
    except UnicodeError as exc:
        raise FlowError(f"{name} is not valid UTF-8") from exc
    except OSError as exc:
        raise FlowError(f"cannot read {name}: {type(exc).__name__}") from exc


def fingerprints(feature_dir: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for name in SECTIONS:
        data = _read(feature_dir, name)
        if data is not None:
            result[name] = hashlib.sha256(data).hexdigest()
    return result


def _visible(text: str) -> list[str]:
    text = re.sub(r"<!--.*?(?:-->|\Z)", "", text, flags=re.DOTALL)
    lines: list[str] = []
    fence = ""
    for line in text.splitlines():
        match = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if match:
            marker, tail = match.groups()
            if not fence:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence) and not tail.strip():
                fence = ""
            continue
        if not fence:
            if not line.startswith(("    ", "\t")):
                lines.append(line)
    return lines


def _problems(name: str, text: str, required: tuple[str, ...]) -> list[str]:
    visible = _visible(text)
    problems: list[str] = []
    if _PLACEHOLDER.search("\n".join(visible)) or _UNCHECKED.search("\n".join(visible)):
        problems.append(f"{name} contains placeholders or unchecked items")
    bodies: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in visible:
        match = re.match(r"^ {0,3}(#{1,2})\s+(.+?)\s*#*\s*$", line)
        if match:
            level, title = match.groups()
            key = title.casefold()
            current = None
            if level == "##":
                if key in bodies:
                    problems.append(f"{name} has a duplicate section")
                current = bodies.setdefault(key, [])
        elif current is not None and line.strip():
            current.append(line)
    for heading in required:
        body = bodies.get(heading.casefold(), [])
        evidence = [m.group(1) for line in body if (m := _EVIDENCE.match(line))]
        substantive = [
            line
            for line in body
            if not _EVIDENCE.match(line)
            and re.search(r"\w", line)
            and not _EMPTY.fullmatch(line.strip())
        ]
        if not substantive:
            problems.append(f"{name}: '{heading}' missing substantive content")
        if not evidence or any(_EMPTY.fullmatch(item) for item in evidence):
            problems.append(f"{name}: '{heading}' missing evidence")
    return problems


def check(feature_dir: Path) -> tuple[bool, str]:
    problems: list[str] = []
    try:
        for name, headings in SECTIONS.items():
            data = _read(feature_dir, name)
            if data is None:
                problems.append(f"{name} missing")
            else:
                problems.extend(_problems(name, data.decode("utf-8"), headings))
    except FlowError as exc:
        return False, str(exc)
    if problems:
        return False, "; ".join(problems)
    return True, "readiness record structure complete; human evidence review still required"
