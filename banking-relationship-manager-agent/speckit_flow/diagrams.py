from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from speckit_flow.models import FlowError


def validate(feature_dir: Path) -> tuple[dict[str, object], str]:
    """Validate draw.io XML files in a feature's architecture diagram directory."""
    diagrams_dir = feature_dir / "architecture" / "diagrams"
    if not diagrams_dir.is_dir():
        raise FlowError(f"diagram directory not found: {diagrams_dir}")

    paths = sorted(diagrams_dir.glob("*.drawio"))
    if not paths:
        raise FlowError(f"no .drawio files found in {diagrams_dir}")

    validated: list[str] = []
    for path in paths:
        if path.is_symlink() or not path.is_file():
            raise FlowError(f"diagram must be a regular file: {path}")
        try:
            content = path.read_bytes()
        except OSError as exc:
            raise FlowError(f"cannot read diagram {path}: {exc}") from exc

        lowered = content.lower()
        if b"<!doctype" in lowered or b"<!entity" in lowered:
            raise FlowError(f"DOCTYPE and entity declarations are not allowed: {path}")
        try:
            document = ET.fromstring(content)
        except ET.ParseError as exc:
            raise FlowError(f"invalid draw.io XML in {path}: {exc}") from exc

        if document.tag != "mxfile":
            raise FlowError(f"expected an mxfile root element in {path}")
        diagrams = document.findall("diagram")
        if not diagrams:
            raise FlowError(f"no diagram elements found in {path}")

        for diagram in diagrams:
            model = diagram.find("mxGraphModel")
            root = model.find("root") if model is not None else None
            if root is None:
                name = diagram.get("name", "<unnamed>")
                raise FlowError(f"diagram {name!r} has no graph root in {path}")
            cells = root.findall("mxCell")
            ids = [cell.get("id") for cell in cells]
            if any(cell_id is None or not cell_id for cell_id in ids):
                raise FlowError(f"diagram contains a cell without an id in {path}")
            if len(ids) != len(set(ids)):
                raise FlowError(f"diagram contains duplicate cell ids in {path}")
            id_set = set(ids)
            for cell in cells:
                for reference in ("parent", "source", "target"):
                    value = cell.get(reference)
                    if value is not None and value not in id_set:
                        raise FlowError(
                            f"diagram cell {cell.get('id')!r} has missing {reference} "
                            f"reference {value!r} in {path}"
                        )

        validated.append(path.relative_to(feature_dir).as_posix())

    payload: dict[str, object] = {"valid": validated, "count": len(validated)}
    text = f"{len(validated)} draw.io diagram(s) valid"
    return payload, text
